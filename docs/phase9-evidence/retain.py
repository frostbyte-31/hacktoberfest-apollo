#!/usr/bin/env python3
"""Losslessly retain a fresh Phase9 run, with explicit rebuildable omissions."""
import argparse
import gzip
import hashlib
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from run_alignment import HERE, ROOT, sha, save


def retain(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir() or source == destination or destination.exists():
        raise ValueError('Choose an actual source directory and a fresh evidence destination')
    if HERE not in destination.parents:
        raise ValueError('Retained output must be in new Phase9 evidence')
    destination.mkdir(parents=True, exist_ok=False)
    files, omitted = {}, []
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Refuse evidence symlink: '+str(path))
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        raw = path.read_bytes()
        metadata = {'source': str(path), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw)}
        if ('source' in relative.parts or '__pycache__' in relative.parts or
                relative.parts[0] == 'yaYUL' or path.suffix in ('.so', '.o', '.a', '.symtab', '.bin', '.agc') or
                raw[:4] in (b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf')):
            omitted.append({**metadata, 'path': str(relative),
                'reason': 'Rebuilt host binary/generated symbol-table path data or original source extraction; exact pinned archive/source hashes and commands retained.'})
            continue
        target = destination/relative
        compressed = path.suffix == '.jsonl' or len(raw) > 1024*1024
        if compressed:
            target = target.with_name(target.name+'.gz')
            stored = gzip.compress(raw, mtime=0)
            if gzip.decompress(stored) != raw:
                raise ValueError('Lossless compression failed')
        else:
            stored = raw
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(stored)
        files[str(target.relative_to(destination))] = {**metadata, 'compressed': compressed, 'stored_sha256': sha(target)}
    save(destination/'retention.json', {'source': str(source), 'files': files, 'omitted_rebuildable': omitted,
        'note': 'Actual bytes only. JSONL lossless gzip decompresses byte-for-byte; failed attempts remain failures.'})
    print(str(destination)+': '+str(len(files))+' retained files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    retain(args.source, args.output)


if __name__ == '__main__':
    main()
