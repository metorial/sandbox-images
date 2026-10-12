#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r'sha256:[0-9a-f]{64}')
IDENTIFIER = re.compile(r'[a-z0-9]+(?:[.-][a-z0-9]+)*')


def run(*args):
    subprocess.run(args, check=True)


def discover(root=ROOT):
    templates = []
    for path in sorted(root.glob('*/manifest.json')):
        manifest = json.loads(path.read_text())
        identifier = manifest.get('id', '')
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise ValueError(f'{path}: invalid id')
        if identifier != path.parent.name or type(manifest.get('schemaVersion')) is not int or manifest['schemaVersion'] != 1:
            raise ValueError(f'{path}: id must match directory and schemaVersion must be 1')
        for field in ['name', 'description', 'runtime', 'runtimeVersion']:
            if not isinstance(manifest.get(field), str) or not manifest[field]:
                raise ValueError(f'{path}: {field} must be a nonempty string')
        if manifest.get('platform') != 'linux/arm64':
            raise ValueError(f'{path}: Genesis requires linux/arm64')

        version = manifest.get('version')
        digest = manifest.get('digest')
        image = manifest.get('image')
        if type(version) is not int or version < 0:
            raise ValueError(f'{path}: version must be a nonnegative integer')
        if version == 0:
            if digest is not None or image is not None:
                raise ValueError(f'{path}: unpublished templates must have null image/digest')
        elif (not isinstance(digest, str) or not DIGEST.fullmatch(digest)
              or not isinstance(image, str) or not image.endswith('@' + digest)):
            raise ValueError(f'{path}: published templates require a digest-pinned image')

        smoke = manifest.get('smokeTest')
        if not isinstance(smoke, list) or not smoke or not all(isinstance(s, str) and s for s in smoke):
            raise ValueError(f'{path}: smokeTest must be a nonempty command array')
        if not (path.parent / 'build' / 'Dockerfile').is_file():
            raise ValueError(f'{path}: missing build/Dockerfile')
        for source, lock in [('requirements.in', 'requirements.txt'), ('package.json', 'package-lock.json')]:
            context = path.parent / 'build'
            if (context / source).is_file() and not (context / lock).is_file():
                raise ValueError(f'{path}: {source} requires a committed {lock}')
        templates.append((path, manifest))

    if not templates:
        raise ValueError('No templates found')
    return templates


def next_manifest(manifest, digest, repository):
    if not DIGEST.fullmatch(digest):
        raise ValueError('Invalid build digest')
    if manifest['image'] is not None and manifest['image'].split('@')[0] != repository:
        raise ValueError('Registry changed; explicitly migrate published manifests first')
    if manifest['digest'] == digest:
        return None

    return dict(manifest, version=manifest['version'] + 1,
                digest=digest, image=f'{repository}@{digest}')


def build(path, manifest, directory):
    identifier = manifest['id']
    archive = directory / f'{identifier}.tar'
    metadata = directory / f'{identifier}.json'
    tag = f'sandbox-template-check/{identifier}:latest'

    run('docker', 'buildx', 'build', '--pull', '--no-cache',
        '--platform', manifest['platform'], '--provenance=false', '--sbom=false',
        '--build-arg', 'SOURCE_DATE_EPOCH=0', '--metadata-file', str(metadata),
        '--tag', tag,
        '--output', f'type=oci,dest={archive},rewrite-timestamp=true',
        '--output', 'type=docker,rewrite-timestamp=true', str(path.parent / 'build'))

    digest = json.loads(metadata.read_text())['containerimage.digest']
    if not DIGEST.fullmatch(digest):
        raise ValueError(f'{identifier}: missing valid image digest')

    try:
        smoke = manifest['smokeTest']
        run('docker', 'run', '--rm', '--platform', manifest['platform'],
            '--entrypoint', smoke[0], tag, *smoke[1:])
        run('docker', 'run', '--rm', '--platform', manifest['platform'],
            '--entrypoint', 'bash', tag, '-ec',
            'test "$PWD" = /workspace; test "$(id -u)" = 0; '
            'for tool in bash curl git ssh cc make ps unzip; do command -v "$tool"; done')
    finally:
        run('docker', 'image', 'rm', tag)

    return archive, digest


def publish(archive, repository, version, authfile):
    run('skopeo', 'copy', '--all', '--preserve-digests', '--authfile', str(authfile),
        f'oci-archive:{archive}', f'docker://{repository}:v{version}')


def main():
    parser = argparse.ArgumentParser(description='Build, test and optionally publish sandbox templates.')
    parser.add_argument('--validate', action='store_true', help='Validate manifests without Docker')
    parser.add_argument('--template', help='Build only this template (local checks only)')
    parser.add_argument('--prune-build-cache', action='store_true',
                        help='Prune the selected dedicated Buildx builder after every build (CI)')
    parser.add_argument('--publish', action='store_true', help='Publish changed images and update manifests')
    parser.add_argument('--registry', default='ghcr.io/metorial/sandbox-images')
    parser.add_argument('--authfile', type=Path, default=Path.home() / '.docker' / 'config.json')
    args = parser.parse_args()

    templates = discover()
    if args.validate:
        print(f'Validated {len(templates)} templates')
        return
    if args.publish and args.template:
        parser.error('--publish always builds the entire catalog')
    if not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]+)?/[a-z0-9/._-]+', args.registry):
        parser.error('--registry must be a lowercase registry/repository prefix')
    if args.template:
        templates = [(p, m) for p, m in templates if m['id'] == args.template]
        if not templates:
            parser.error('Unknown template')

    with tempfile.TemporaryDirectory(prefix='sandbox-images-') as temp:
        pending = []
        for path, manifest in templates:
            print(f"Building {manifest['id']}", flush=True)
            archive, digest = build(path, manifest, Path(temp))
            if args.prune_build_cache:
                run('docker', 'buildx', 'prune', '--all', '--force')
            repository = f"{args.registry}/{manifest['id']}"
            updated = next_manifest(manifest, digest, repository)
            if updated is None:
                archive.unlink()
                print(f"{manifest['id']}: unchanged", flush=True)
            else:
                pending.append((path, updated, archive, repository))
                print(f"{manifest['id']}: would publish v{updated['version']} ({digest})", flush=True)

        if not args.publish:
            print(f'{len(pending)} changed images; manifests untouched (check mode)')
            return

        for path, updated, archive, repository in pending:
            publish(archive, repository, updated['version'], args.authfile)

        for path, updated, archive, repository in pending:
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(updated, indent=2) + '\n')
            os.replace(temporary, path)
        print(f'Published and updated {len(pending)} templates')


if __name__ == '__main__':
    main()
