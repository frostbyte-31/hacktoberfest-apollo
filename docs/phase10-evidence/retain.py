#!/usr/bin/env python3
"""Retain actual new results, with deterministic compression and omission hashes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def retain(source, name):
    source = Path(source).resolve()
    destination = HERE/'runs'/name
    destination.mkdir(parents=True, exist_ok=False)
    records = []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        raw = path.read_bytes()
        record = {'source_path': str(relative), 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest()}
        if path.name == 'engine.so':
            record['omitted'] = 'Host-specific build product; reproduce from verified original engine sources and retained command/header'
        else:
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.jsonl':
                target = target.with_name(target.name+'.gz')
                target.write_bytes(gzip.compress(raw, mtime=0))
            else:
                shutil.copyfile(path, target)
            record.update(retained_path=str(target.relative_to(destination)), retained_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        records.append(record)
    (destination/'retention.json').write_text(json.dumps({'source': str(source), 'files': records,
        'note': 'Fresh Phase10 work only; compressed logs are actual captured bytes, not reconstructed historical evidence'}, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('name')
    args = parser.parse_args()
    if '/' in args.name or args.name in ('.', '..'):
        raise ValueError('Use a simple new evidence label')
    retain(args.source, args.name)
