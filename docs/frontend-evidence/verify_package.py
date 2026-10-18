#!/usr/bin/env python3
"""Read-only final frontend package seal and protected historical-file check."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if __name__ == '__main__':
    prior = subprocess.run([sys.executable, '-B', str(HERE / 'check_integrity.py')], capture_output=True, text=True)
    manifest = json.loads((HERE / 'checksums.json').read_text())['sha256']
    problems = []
    for name, expected in manifest.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe package path')
        target = ROOT / name
        if not target.is_file() or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            problems.append(name)
    result = {'verified': prior.returncode == 0 and not problems,
              'protected': json.loads(prior.stdout), 'package_files': len(manifest), 'package_mismatches': problems}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['verified'] else 1)
