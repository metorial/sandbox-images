import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build', Path(__file__).parents[1] / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

DIGEST_A = 'sha256:' + 'a' * 64
DIGEST_B = 'sha256:' + 'b' * 64
REPOSITORY = 'ghcr.io/metorial/sandbox-images/ubuntu-24.04'


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = copy.deepcopy(dict(build.discover())[build.ROOT / 'ubuntu-24.04/manifest.json'])
        self.manifest.update(version=0, image=None, digest=None)

    def test_initial_publish_and_unchanged_rebuild(self):
        first = build.next_manifest(self.manifest, DIGEST_A, REPOSITORY)
        self.assertEqual(first['version'], 1)
        self.assertEqual(first['image'], REPOSITORY + '@' + DIGEST_A)
        self.assertIsNone(build.next_manifest(first, DIGEST_A, REPOSITORY))
        self.assertEqual(self.manifest['version'], 0)

    def test_changed_output_increments_only_once(self):
        first = build.next_manifest(self.manifest, DIGEST_A, REPOSITORY)
        second = build.next_manifest(first, DIGEST_B, REPOSITORY)
        self.assertEqual(second['version'], 2)
        self.assertIsNone(build.next_manifest(second, DIGEST_B, REPOSITORY))

    def test_rejects_invalid_digest_and_registry_migration(self):
        with self.assertRaises(ValueError):
            build.next_manifest(self.manifest, 'bad', REPOSITORY)
        first = build.next_manifest(self.manifest, DIGEST_A, REPOSITORY)
        with self.assertRaises(ValueError):
            build.next_manifest(first, DIGEST_A, 'ghcr.io/other/image')

    def test_catalog_rejects_inconsistent_published_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / self.manifest['id']
            (template / 'build').mkdir(parents=True)
            (template / 'build/Dockerfile').write_text('FROM ubuntu:24.04\n')
            self.manifest['version'] = 1
            (template / 'manifest.json').write_text(json.dumps(self.manifest))
            with self.assertRaises(ValueError):
                build.discover(root)

    def test_build_failure_does_not_publish_or_write_manifests(self):
        before = (build.ROOT / 'ubuntu-24.04/manifest.json').read_bytes()
        with patch('sys.argv', ['build.py', '--publish']), patch.object(build, 'publish') as publish:
            with patch.object(build, 'build', side_effect=[(Path('unused.tar'), DIGEST_A), RuntimeError('failed build')]):
                with self.assertRaises(RuntimeError):
                    build.main()
            publish.assert_not_called()
        self.assertEqual((build.ROOT / 'ubuntu-24.04/manifest.json').read_bytes(), before)


    def test_registry_failure_does_not_update_any_manifests(self):
        snapshots = {path: path.read_bytes() for path, _ in build.discover()}
        with patch('sys.argv', ['build.py', '--publish']):
            with patch.object(build, 'build', return_value=(Path('unused.tar'), DIGEST_A)):
                with patch.object(build, 'publish', side_effect=[None, RuntimeError('registry unavailable')]):
                    with self.assertRaises(RuntimeError):
                        build.main()
        for path, before in snapshots.items():
            self.assertEqual(path.read_bytes(), before)

    def test_catalog_requires_dependency_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / self.manifest['id']
            (template / 'build').mkdir(parents=True)
            (template / 'build/Dockerfile').write_text('FROM ubuntu:24.04\n')
            (template / 'manifest.json').write_text(json.dumps(self.manifest))
            for source, lock in [('requirements.in', 'requirements.txt'), ('package.json', 'package-lock.json')]:
                (template / 'build' / source).write_text('')
                with self.assertRaises(ValueError):
                    build.discover(root)
                (template / 'build' / lock).write_text('')
                self.assertEqual(len(build.discover(root)), 1)

    def test_matrix_lists_every_template(self):
        with patch('sys.argv', ['build.py', '--matrix']), patch('builtins.print') as output:
            build.main()
        matrix = json.loads(output.call_args.args[0])
        self.assertEqual(matrix['template'], [manifest['id'] for _, manifest in build.discover()])

    def test_single_template_publish_updates_only_selected_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps(self.manifest))
            other = dict(self.manifest, id='other')
            with patch('sys.argv', ['build.py', '--publish', '--template', self.manifest['id']]):
                with patch.object(build, 'discover', return_value=[(path, self.manifest), (Path('other'), other)]):
                    with patch.object(build, 'build', return_value=(Path('unused.tar'), DIGEST_A)) as builder:
                        with patch.object(build, 'publish') as publisher:
                            build.main()
            builder.assert_called_once()
            publisher.assert_called_once()
            self.assertEqual(json.loads(path.read_text()), build.next_manifest(self.manifest, DIGEST_A, REPOSITORY))

    def test_merge_requires_complete_valid_results_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source'
            results = Path(directory) / 'results'
            results.mkdir()
            for identifier in [self.manifest['id'], 'other']:
                template = root / identifier
                (template / 'build').mkdir(parents=True)
                (template / 'build/Dockerfile').write_text('FROM ubuntu:24.04\n')
                (template / 'manifest.json').write_text(json.dumps(dict(self.manifest, id=identifier)))
                (results / identifier).mkdir()
            before = {path: path.read_bytes() for path, _ in build.discover(root)}
            updated = build.next_manifest(self.manifest, DIGEST_A, REPOSITORY)
            (results / self.manifest['id'] / 'manifest.json').write_text(json.dumps(updated))
            with self.assertRaises(ValueError):
                build.merge_manifests(results, 'ghcr.io/metorial/sandbox-images', root)
            other = dict(self.manifest, id='other')
            result_path = results / 'other' / 'manifest.json'
            result_path.write_text(json.dumps(dict(other, name='unexpected modification')))
            with self.assertRaises(ValueError):
                build.merge_manifests(results, 'ghcr.io/metorial/sandbox-images', root)
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            result_path.write_text(json.dumps(other))
            self.assertEqual(build.merge_manifests(results, 'ghcr.io/metorial/sandbox-images', root), 1)
            self.assertEqual(json.loads((root / self.manifest['id'] / 'manifest.json').read_text()), updated)
            self.assertEqual(build.merge_manifests(results, 'ghcr.io/metorial/sandbox-images', root), 0)
            (results / 'unexpected').mkdir()
            (results / 'unexpected/manifest.json').write_text(json.dumps(other))
            with self.assertRaises(ValueError):
                build.merge_manifests(results, 'ghcr.io/metorial/sandbox-images', root)


if __name__ == '__main__':
    unittest.main()
