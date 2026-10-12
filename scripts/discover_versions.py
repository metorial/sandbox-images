#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    if not url.startswith(('https://hub.docker.com/', 'https://mcr.microsoft.com/',
                           'https://raw.githubusercontent.com/docker-library/official-images/master/library/')):
        raise ValueError('Unexpected upstream pagination URL')
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'metorial-sandbox-image-discovery'})
            with urllib.request.urlopen(request, timeout=60) as response:
                if 'raw.githubusercontent.com' in url:
                    return response.read().decode('utf-8')
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise RuntimeError(f'Failed to fetch {url}')
            time.sleep(2 ** attempt)


def upstream_tags(source):
    if source['repository'].startswith('library/'):
        text = fetch('https://raw.githubusercontent.com/docker-library/official-images/master/library/'
                     + source['repository'].split('/')[1])
        tags = []
        for block in text.split('\n\n'):
            architectures = re.search(r'^Architectures: (.+)$', block, re.MULTILINE)
            if not architectures or 'arm64v8' not in architectures[1].split(', '):
                continue
            for match in re.finditer(r'^(?:Tags|SharedTags): (.+)$', block, re.MULTILINE):
                tags.extend({'name': name} for name in match[1].split(', '))
        return tags

    if source.get('registry') == 'mcr':
        tags = fetch(f"https://mcr.microsoft.com/v2/{source['repository']}/tags/list")['tags']
        return [{'name': tag} for tag in tags]

    query = urllib.parse.urlencode({'page_size': 100, 'name': source['filter']})
    url = f"https://hub.docker.com/v2/repositories/{source['repository']}/tags?{query}"
    tags = []
    while url:
        page = fetch(url)
        tags.extend(page['results'])
        url = page.get('next')
    return tags


def version_key(track):
    return tuple(int(part) for part in track.split('.'))


def candidates(source, tags, root=ROOT):
    baseline = source['seed'].removeprefix(source['family'] + '-')
    found = {}
    for tag in tags:
        match = re.fullmatch(source['pattern'], tag['name'])
        if not match:
            continue
        track = match['track']
        if version_key(track) <= version_key(baseline):
            continue
        if source.get('javaLtsOnly') and (int(track) - 25) % 4:
            continue
        if source.get('ltsOnly') and int(track.split('.')[0]) % 2:
            continue
        if 'images' in tag and not any(i.get('os') == 'linux' and i.get('architecture') == 'arm64' for i in tag['images']):
            continue
        identifier = source['family'] + '-' + track
        if (root / identifier).exists():
            continue
        if track not in found or (source['family'] == 'deno' and
                version_key(tag['name'].removeprefix('debian-')) > version_key(found[track].removeprefix('debian-'))):
            found[track] = tag['name']
    return [(track, found[track]) for track in sorted(found, key=version_key)]


def create_template(source, track, tag, root=ROOT):
    seed = root / source['seed']
    identifier = source['family'] + '-' + track
    destination = root / identifier
    manifest = json.loads((seed / 'manifest.json').read_text())
    old_track = source['seed'].removeprefix(source['family'] + '-')
    old_name = manifest['name']
    manifest.update(id=identifier, name=old_name.replace(old_track, track),
                    runtimeVersion=track, version=0, image=None, digest=None)
    manifest['description'] = manifest['description'].replace(old_name, manifest['name'])

    dockerfile = (seed / 'build/Dockerfile').read_text()
    lines = dockerfile.splitlines()
    final_from = max(i for i, line in enumerate(lines) if line.startswith('FROM '))
    lines[final_from] = 'FROM ' + source['from'].format(track=track, tag=tag)
    shutil.copytree(seed / 'build', destination / 'build')
    (destination / 'build/Dockerfile').write_text('\n'.join(lines) + '\n')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return identifier


def main():
    parser = argparse.ArgumentParser(description='Discover newer stable upstream language/OS tracks.')
    parser.add_argument('--write', action='store_true', help='Create missing template directories')
    parser.add_argument('--output', type=Path, help='Write JSON list of missing/new template ids')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'scripts/version-sources.json').read_text())
    pending = []
    for source in sources:
        for track, tag in candidates(source, upstream_tags(source)):
            pending.append((source, track, tag))
            print(f"Missing {source['family']}-{track}: {tag}", flush=True)

    identifiers = []
    for source, track, tag in pending:
        identifier = source['family'] + '-' + track
        if args.write:
            identifier = create_template(source, track, tag)
        identifiers.append(identifier)
    if args.output:
        args.output.write_text(json.dumps(identifiers) + '\n')
    print(f'{len(identifiers)} missing tracks', flush=True)


if __name__ == '__main__':
    main()
