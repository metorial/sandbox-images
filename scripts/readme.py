#!/usr/bin/env python3
import argparse

from build import ROOT, discover


def cell(value):
    return value.replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ')


def render(root=ROOT):
    lines = [
        '# Sandbox Images',
        '',
        '| Template | Runtime | Version | Description |',
        '| --- | --- | --- | --- |'
    ]
    for _, manifest in discover(root):
        identifier = manifest['id']
        lines.append(
            f"| [{identifier}]({identifier}/) | {cell(manifest['runtime'])} | "
            f"{cell(manifest['runtimeVersion'])} | {cell(manifest['description'])} |"
        )
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Generate the README template list from manifests.')
    parser.add_argument('--check', action='store_true', help='Fail if the README is out of date')
    args = parser.parse_args()

    document = render()
    path = ROOT / 'README.md'
    if args.check:
        if not path.is_file() or path.read_text() != document:
            parser.exit(1, 'README.md is out of date; run python3 scripts/readme.py\n')
    else:
        path.write_text(document)


if __name__ == '__main__':
    main()
