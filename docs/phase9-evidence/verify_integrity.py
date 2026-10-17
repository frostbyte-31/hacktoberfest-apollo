#!/usr/bin/env python3
"""Seal once or verify Phase9 artifacts; preserve every prior-phase byte."""
import argparse
import datetime
import json
from pathlib import PurePosixPath
import sys

sys.dont_write_bytecode = True
from run_alignment import HERE, ROOT, sha, save, verify_prior


def inventory():
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
             and p != HERE/'package-manifest.json']
    files += [ROOT/'docs/PHASE9_IMU_ALIGNMENT.md']
    return {p.relative_to(ROOT).as_posix(): p for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    prior = verify_prior()
    if not prior['ok']:
        raise ValueError('Prior evidence changed: '+repr(prior['changed_or_missing']))
    manifest = HERE/'package-manifest.json'
    files = inventory()
    if args.seal:
        if manifest.exists():
            raise ValueError('Preserve the existing manifest; never overwrite the seal')
        if any(p.is_symlink() for p in files.values()):
            raise ValueError('Refuse package symlinks')
        save(manifest, {'sealed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'classification': 'VERIFIED original P51 synthetic alignment and P63 R02 acceptance; no descent',
            'prior_files_preserved': prior['files_checked'], 'files': {name: sha(path) for name, path in files.items()}})
    record = json.loads(manifest.read_text())
    failures = []
    for name, expected in record['files'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe sealed path')
        path = ROOT/name
        if path.is_symlink() or not path.is_file() or sha(path) != expected:
            failures.append(name)
    extra = sorted(set(files)-set(record['files']))
    result = {'status': 'VERIFIED' if not failures and not extra else 'FAILED',
        'files_checked': len(record['files']), 'prior_files_preserved': prior['files_checked'],
        'changed_or_missing': failures, 'unlisted_files': extra, 'manifest_sha256': sha(manifest)}
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
