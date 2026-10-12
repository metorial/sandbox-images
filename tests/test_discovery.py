import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('discovery', Path(__file__).parents[1] / 'scripts/discover_versions.py')
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)
SOURCES = json.loads((discovery.ROOT / 'scripts/version-sources.json').read_text())


class DiscoveryTests(unittest.TestCase):
    def test_stable_new_arm64_tracks_only(self):
        source = next(s for s in SOURCES if s['family'] == 'bun')
        tags = [{'name': n, 'images': [{'os': 'linux', 'architecture': arch}]} for n, arch in [
            ('1.4-debian', 'arm64'), ('1.3-debian', 'arm64'), ('1.4.1-debian', 'arm64'),
            ('1.5-canary-debian', 'arm64'), ('2.0-debian', 'amd64')]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(discovery.candidates(source, tags, root), [('1.4', '1.4-debian')])
            (root / 'bun-1.4').mkdir()
            self.assertEqual(discovery.candidates(source, tags, root), [])

    def test_ubuntu_lts_only(self):
        source = next(s for s in SOURCES if s['family'] == 'ubuntu')
        with tempfile.TemporaryDirectory() as directory:
            result = discovery.candidates(source, [{'name': n} for n in ['25.04','26.04','26.10','28.04']], Path(directory))
            self.assertEqual(result, [('26.04','26.04'), ('28.04','28.04')])

    def test_java_lts_only(self):
        source = next(s for s in SOURCES if s['family'] == 'java')
        with tempfile.TemporaryDirectory() as directory:
            result = discovery.candidates(source, [{'name': n} for n in ['3-eclipse-temurin-26', '3-eclipse-temurin-27', '3-eclipse-temurin-29']], Path(directory))
            self.assertEqual(result, [('29', '3-eclipse-temurin-29')])

    def test_deno_uses_latest_stable_patch_for_new_major(self):
        source = next(s for s in SOURCES if s['family'] == 'deno')
        with tempfile.TemporaryDirectory() as directory:
            result = discovery.candidates(source, [{'name': n} for n in ['debian-2.10.0','debian-3.0.2','debian-3.0.10']], Path(directory))
            self.assertEqual(result, [('3', 'debian-3.0.10')])

    def test_generated_template_resets_publication_and_keeps_stages(self):
        source = next(s for s in SOURCES if s['family'] == 'java')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / source['seed']
            (seed / 'build').mkdir(parents=True)
            original = json.loads((discovery.ROOT / source['seed'] / 'manifest.json').read_text())
            original.update(version=8, image='published', digest='digest')
            (seed / 'manifest.json').write_text(json.dumps(original))
            (seed / 'build/Dockerfile').write_text('FROM gradle:9.1.0-jdk25 AS gradle\nFROM maven:3.9-eclipse-temurin-25\n')
            identifier = discovery.create_template(source, '26', '3.9-eclipse-temurin-26', root)
            manifest = json.loads((root / identifier / 'manifest.json').read_text())
            self.assertEqual((manifest['version'],manifest['image'],manifest['digest']), (0,None,None))
            self.assertEqual(manifest['runtimeVersion'], '26')
            self.assertEqual((root / identifier / 'build/Dockerfile').read_text(),
                'FROM gradle:9.1.0-jdk25 AS gradle\nFROM maven:3-eclipse-temurin-26\n')


if __name__ == '__main__':
    unittest.main()
