#!/usr/bin/env python3
"""Seal or verify this live-control evidence package and its current code."""
import argparse
import datetime
import json
from pathlib import Path, PurePosixPath
import sys

sys.dont_write_bytecode = True
from live_common import HERE, ROOT, digest, verify_prior, write_json


def inventory():
    paths = [p for base in (HERE, ROOT / 'backend', ROOT / 'frontend')
             for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT / 'Makefile', ROOT / 'README.md', ROOT / 'docs/LIVE_ATTITUDE_CONTROL.md']
    return {p.relative_to(ROOT).as_posix(): p for p in paths if p != HERE / 'package-manifest.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true', help='Create once; never overwrite a retained manifest.')
    args = parser.parse_args()
    manifest = HERE / 'package-manifest.json'
    preservation = verify_prior()
    if not preservation['ok']:
        raise ValueError('Prior evidence changed: ' + repr(preservation['changed_or_missing']))
    paths = inventory()
    if args.seal:
        if manifest.exists():
            raise ValueError('Manifest already exists; preserve the sealed package.')
        if any(path.is_symlink() for path in paths.values()):
            raise ValueError('Package symlinks are not accepted')
        write_json(manifest, {'schema': 1, 'sealed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'base_revision': preservation['source_revision'],
            'classification': 'VERIFIED bounded live native yaw/pitch controls; no descent',
            'prior_preservation': preservation, 'files': {name: digest(path) for name, path in sorted(paths.items())}})
    record = json.loads(manifest.read_text())
    failures = []
    for name, expected in record['files'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe package path')
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            failures.append(name)
    extra = sorted(set(paths)-set(record['files']))
    result = {'status': 'VERIFIED' if not failures and not extra else 'FAILED',
              'files_checked': len(record['files']), 'prior_files_preserved': preservation['files_checked'],
              'changed_or_missing': failures, 'unlisted_files': extra, 'manifest_sha256': digest(manifest)}
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
