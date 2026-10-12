import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import pack

BASE_URL = 'https://sandbox-images.pages.dev'


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.template = self.root / 'example-1'
        self.context = self.template / 'build'
        self.context.mkdir(parents=True)
        (self.context / 'Dockerfile').write_text('FROM ubuntu:24.04\n')
        (self.context / 'nested').mkdir()
        (self.context / 'nested/hello.sh').write_text('echo hello\n')
        self.manifest = dict(schemaVersion=1, id='example-1', name='Example', description='Example image',
                             platform='linux/arm64', runtime='example', runtimeVersion='1', version=1,
                             digest='sha256:' + 'a' * 64,
                             image='ghcr.io/example/image@sha256:' + 'a' * 64, smokeTest=['bash', '--version'])
        (self.template / 'manifest.json').write_text(json.dumps(self.manifest))
        self.output = self.root / 'dist'

    def test_archive_is_deterministic_and_extracts_at_context_root(self):
        first = pack.archive_context(self.context)
        (self.context / 'Dockerfile').touch()
        self.assertEqual(first, pack.archive_context(self.context))
        with tarfile.open(fileobj=io.BytesIO(first), mode='r:gz') as archive:
            self.assertEqual(archive.getnames(), ['Dockerfile', 'nested/hello.sh'])
            self.assertTrue(all(entry.uid == 0 and entry.mtime == 0 for entry in archive))

    def test_catalog_descriptors_match_served_assets_and_input_changes_change_urls(self):
        entries = pack.pack(self.output, BASE_URL, root=self.root)
        self.assertEqual(json.loads((self.output / 'index.json').read_text())['templates'], entries)
        for field in ['manifest', 'build']:
            descriptor = entries[0][field]
            data = (self.output / descriptor['url'].removeprefix(BASE_URL + '/')).read_bytes()
            self.assertEqual(descriptor['bytes'], len(data))
            self.assertEqual(descriptor['sha256'], pack.checksum(data))
        (self.context / 'Dockerfile').write_text('FROM ubuntu:26.04\n')
        next_entries = pack.pack(self.root / 'next', BASE_URL, root=self.root)
        self.assertNotEqual(entries[0]['build']['url'], next_entries[0]['build']['url'])

    def test_production_rejects_unpublished_templates(self):
        self.manifest.update(version=0, image=None, digest=None)
        (self.template / 'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            pack.pack(self.output, BASE_URL, root=self.root)
        entries = pack.pack(self.output, BASE_URL, root=self.root, allow_unpublished=True)
        self.assertFalse(entries[0]['published'])

    def test_retains_old_release_files_and_rejects_corruption(self):
        old = self.root / 'old'
        entries = pack.pack(old, BASE_URL, root=self.root)
        def fetch(request, timeout):
            url = request.full_url
            return io.BytesIO((old / url.removeprefix(BASE_URL + '/')).read_bytes())
        (self.context / 'Dockerfile').write_text('FROM ubuntu:26.04\n')
        with patch.object(pack, 'urlopen', side_effect=fetch):
            pack.pack(self.output, BASE_URL, root=self.root, retain=True)
        inventory = json.loads((self.output / 'releases.json').read_text())['releases']
        self.assertEqual(len(inventory), 2)
        self.assertTrue((self.output / entries[0]['build']['url'].removeprefix(BASE_URL + '/')).exists())
        (old / entries[0]['build']['url'].removeprefix(BASE_URL + '/')).write_bytes(b'corrupt')
        with patch.object(pack, 'urlopen', side_effect=fetch), self.assertRaises(ValueError):
            pack.pack(self.root / 'bad', BASE_URL, root=self.root, retain=True)

    def test_context_rejects_symlinks(self):
        (self.context / 'unsafe').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            pack.archive_context(self.context)

    def test_rejects_unsafe_origin_and_oversized_asset(self):
        for url in ['http://example.com', 'https://example.com?token=x', 'https://example.com/catalog']:
            with self.assertRaises(ValueError):
                pack.pack(self.output, url, root=self.root)
        with patch.object(pack, 'MAX_ASSET_BYTES', 1), self.assertRaises(ValueError):
            pack.pack(self.output, BASE_URL, root=self.root)
