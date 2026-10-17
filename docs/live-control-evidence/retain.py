#!/usr/bin/env python3
"""Retain a fresh live run losslessly; never replace an evidence directory."""
import argparse
import datetime
import gzip
import hashlib
from pathlib import Path
import shutil

from live_common import HERE, ROOT, digest, write_json


def retain(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    allowed = HERE / 'runs'
    if not source.is_dir() or target.exists() or allowed not in target.parents:
        raise ValueError('A real source directory and a fresh live-control-evidence/runs destination are required')
    files = sorted(source.rglob('*'))
    if any(p.is_symlink() for p in files):
        raise ValueError('Unexpected source symlink; do not follow it into retained evidence')
    target.mkdir(parents=True)
    copied, compressed, omitted = [], [], []
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        record = {'source_path': str(path), 'relative_path': relative.as_posix(),
                  'sha256': digest(path), 'bytes': path.stat().st_size}
        parts = relative.parts
        extracted = any(parts[i:i+2] == ('assets', 'source') for i in range(len(parts)-1))
        if extracted:
            omitted.append({**record, 'reason': 'Rebuildable original source extraction; exact per-file hashes and retained Phase 6 archive establish provenance'})
            continue
        if path.suffix in ('.so', '.dylib', '.o', '.a'):
            omitted.append({**record, 'reason': 'Rebuildable host binary; compile commands, inputs and binary SHA-256 retained'})
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == '.jsonl':
            destination = destination.with_suffix('.jsonl.gz')
            with path.open('rb') as src, destination.open('xb') as output:
                with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as archive:
                    shutil.copyfileobj(src, archive)
            raw = gzip.decompress(destination.read_bytes())
            if hashlib.sha256(raw).hexdigest() != record['sha256']:
                raise ValueError('Lossless trace retention failed')
            compressed.append({**record, 'retained_path': str(destination.relative_to(target)),
                               'gzip_sha256': digest(destination), 'gzip_bytes': destination.stat().st_size})
        else:
            shutil.copyfile(path, destination)
            if digest(destination) != record['sha256']:
                raise ValueError('Retained copy does not match source bytes')
            copied.append({**record, 'retained_path': str(destination.relative_to(target))})
    write_json(target / 'retention.json', {
        'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_directory': str(source), 'copied': copied,
        'lossless_trace_compression': compressed, 'omitted_rebuildable_files': omitted,
        'source_archive': 'docs/phase6-evidence/corresponding-source.tar.gz',
        'source_archive_sha256': digest(ROOT / 'docs/phase6-evidence/corresponding-source.tar.gz'),
        'note': 'Raw JSONL remains byte-identical after decompression; no observations have been recreated'})
    print({'target': str(target), 'copied': len(copied), 'compressed_traces': len(compressed), 'omitted_rebuildable': len(omitted)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    retain(args.source, args.output)


if __name__ == '__main__':
    main()
