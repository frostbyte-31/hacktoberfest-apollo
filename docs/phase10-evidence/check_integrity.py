#!/usr/bin/env python3
"""Read-only verification of prior files, new files and captured log packaging."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from run_mission import preserve, p9


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE/'checksums.json').read_text())
    mismatches = [name for name, expected in manifest['sha256'].items()
                  if not (ROOT/name).is_file() or (ROOT/name).is_symlink() or p9.sha(ROOT/name) != expected]
    packaged, broken = 0, []
    for inventory in (HERE/'runs').glob('*/retention.json'):
        for record in json.loads(inventory.read_text())['files']:
            if 'retained_path' not in record:
                continue
            path = inventory.parent/record['retained_path']
            retained = path.read_bytes()
            raw = gzip.decompress(retained) if path.suffix == '.gz' and record['source_path'].endswith('.jsonl') else retained
            packaged += 1
            if hashlib.sha256(raw).hexdigest() != record['raw_sha256'] or hashlib.sha256(retained).hexdigest() != record['retained_sha256']:
                broken.append(str(path.relative_to(ROOT)))
    prior = preserve()
    result = {'all_pass': prior['ok'] and not mismatches and not broken, 'prior': prior,
              'new_files_checked': len(manifest['sha256']), 'new_mismatches': mismatches,
              'retained_files_checked': packaged, 'retention_mismatches': broken,
              'manifest_sha256': p9.sha(HERE/'checksums.json')}
    if args.output:
        if ROOT/'.build' not in args.output.resolve().parents or args.output.exists():
            raise ValueError('Verification output must be a new file under .build')
        p9.save(args.output, result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_pass'] else 1)
