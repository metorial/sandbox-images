#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from build import ROOT, discover

MAX_ASSET_BYTES = 25 * 1024 * 1024


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def archive_context(context):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for path in sorted(context.rglob('*')):
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise ValueError(f'Unsupported build context entry: {path}')
                if path.is_dir():
                    continue
                data = path.read_bytes()
                entry = tarfile.TarInfo(path.relative_to(context).as_posix())
                entry.size = len(data)
                entry.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(entry, io.BytesIO(data))
    return output.getvalue()


def asset(output, base_url, relative, data):
    if len(data) > MAX_ASSET_BYTES:
        raise ValueError(f'{relative} exceeds the Cloudflare Pages 25 MiB limit')
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return dict(url=f'{base_url}/{relative}', bytes=len(data), sha256=checksum(data))


def fetch(url):
    return urlopen(Request(url, headers={'User-Agent': 'metorial-sandbox-catalog/1'}), timeout=60)


def retain_releases(output, base_url):
    try:
        with fetch(f'{base_url}/releases.json') as response:
            previous = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return []
        raise
    if previous.get('schemaVersion') != 1 or not isinstance(previous.get('releases'), list):
        raise ValueError('Invalid previous release inventory')
    for release in previous['releases']:
        for field in ['manifest', 'build']:
            descriptor = release[field]
            prefix = base_url + '/templates/'
            if not descriptor['url'].startswith(prefix):
                raise ValueError('Previous asset URL is outside this catalog')
            relative = descriptor['url'][len(base_url) + 1:]
            if '..' in Path(relative).parts or '?' in relative or '#' in relative:
                raise ValueError('Unsafe previous asset path')
            with fetch(descriptor['url']) as response:
                data = response.read(MAX_ASSET_BYTES + 1)
            if len(data) != descriptor['bytes'] or checksum(data) != descriptor['sha256']:
                raise ValueError(f'Previous asset failed integrity verification: {relative}')
            asset(output, base_url, relative, data)
    return previous['releases']


def pack(output, base_url, root=ROOT, retain=False, allow_unpublished=False):
    parsed = urlparse(base_url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment or parsed.path not in ['', '/']:
        raise ValueError('Catalog base URL must be an HTTPS origin')
    base_url = base_url.rstrip('/')
    templates = discover(root)
    if not allow_unpublished and any(manifest['version'] == 0 for _, manifest in templates):
        raise ValueError('Publish every image before packing the production catalog')
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Catalog output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    releases = retain_releases(output, base_url) if retain else []
    entries = []
    for path, manifest in templates:
        context = archive_context(path.parent / 'build')
        document = encode(manifest)
        release_hash = checksum(document + context)
        prefix = f"templates/{manifest['id']}/v{manifest['version']}/{release_hash}"
        entry = dict(id=manifest['id'], name=manifest['name'], version=manifest['version'],
                     platform=manifest['platform'], runtime=manifest['runtime'],
                     runtimeVersion=manifest['runtimeVersion'], published=manifest['version'] > 0,
                     manifest=asset(output, base_url, f'{prefix}/manifest.json', document),
                     build=dict(asset(output, base_url, f'{prefix}/build.tar.gz', context),
                                format='tar_gzip', dockerfilePath='Dockerfile', contextPath='.',
                                buildArgs={'SOURCE_DATE_EPOCH': '0'}))
        entries.append(entry)
        if entry not in releases:
            releases.append(entry)
    asset(output, base_url, 'index.json', encode(dict(schemaVersion=1, templates=entries)))
    asset(output, base_url, 'releases.json', encode(dict(schemaVersion=1, releases=releases)))
    (output / '_headers').write_text(
        '/index.json\n  Cache-Control: no-cache\n'
        '/releases.json\n  Cache-Control: no-cache\n'
        '/templates/*\n  Cache-Control: public, max-age=31536000, immutable\n'
        '/*\n  Access-Control-Allow-Origin: *\n  X-Content-Type-Options: nosniff\n')
    (output / '404.html').write_text('Catalog asset not found.\n')
    if sum(path.is_file() for path in output.rglob('*')) > 20000:
        raise ValueError('Catalog exceeds the Cloudflare Pages file limit')
    return entries


def main():
    parser = argparse.ArgumentParser(description='Pack the Genesis template catalog for Cloudflare Pages.')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--retain-releases', action='store_true')
    parser.add_argument('--allow-unpublished', action='store_true', help='Preview only; includes version-zero templates')
    args = parser.parse_args()
    entries = pack(args.output, args.base_url, retain=args.retain_releases,
                   allow_unpublished=args.allow_unpublished)
    print(f'Packed {len(entries)} templates into {args.output}')


if __name__ == '__main__':
    main()
