#!/usr/bin/env python3
"""Read-only check of preserved prior evidence and the final MVP package."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def verify(entries):
    problems = []
    for name, expected in entries.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe inventory path: ' + name)
        path = ROOT / name
        if not path.is_file():
            problems.append({'path': name, 'error': 'missing'})
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append({'path': name, 'error': 'SHA-256 mismatch'})
    return problems


def main():
    previous = json.loads((HERE / 'prior-evidence.json').read_text())['sha256']
    current = json.loads((HERE / 'checksums.json').read_text())['sha256']
    problems = verify(previous) + verify(current)
    result = {'verified': not problems, 'prior_evidence_files': len(previous),
              'mvp_files': len(current), 'problems': problems,
              'scope': 'Evidence/package integrity; not an AGC execution or UI test'}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
