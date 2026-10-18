#!/usr/bin/env python3
"""Verify immutable backend, Apollo evidence and original attitude application."""
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if __name__ == '__main__':
    manifest = json.loads((HERE / 'baseline.json').read_text())
    changed = [name for name, expected in manifest['protected_sha256'].items()
               if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    result = {'verified': not changed, 'protected_files': len(manifest['protected_sha256']),
              'changed_or_missing': changed,
              'scope': 'Historical evidence/backend preservation; new frontend behavior is tested separately.'}
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if changed else 0)
