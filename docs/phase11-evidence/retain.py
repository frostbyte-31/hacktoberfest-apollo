#!/usr/bin/env python3
"""Losslessly retain a completed fresh validation, without copying build caches."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_capture(source, target):
    target.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.json', '.h', '.py', '.c', '.stdout', '.stderr'):
            shutil.copyfile(path, target/path.name)
    if (source/'source-integrity').is_dir():
        shutil.copytree(source/'source-integrity', target/'source-integrity')
    trace = source/'trace.jsonl'
    expected = json.loads((source/'trace-sha256.json').read_text())
    if expected != {'sha256': sha(trace), 'bytes': trace.stat().st_size}:
        raise ValueError('Capture checksum mismatch before retention')
    with trace.open('rb') as incoming, (target/'trace.jsonl.gz').open('xb') as out:
        with gzip.GzipFile(fileobj=out, mode='wb', filename='', mtime=0) as archive:
            shutil.copyfileobj(incoming, archive)
    raw = gzip.decompress((target/'trace.jsonl.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != expected['sha256']:
        raise ValueError('Lossless raw retention check failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    source = args.validation.resolve()
    if ROOT/'.build/phase11' not in source.parents:
        raise ValueError('Require a validation output below .build/phase11')
    completion = json.loads((source/'completion.json').read_text())
    if not completion.get('phase10_canonical_raw_trace_identical'):
        raise ValueError('Incomplete or failed validation')
    runs, validation = HERE/'runs/verified', HERE/'validation'
    runs.mkdir(parents=True, exist_ok=False)
    validation.mkdir(exist_ok=False)
    for name in ('zero', 'positive', 'negative', 'disconnected', 'repeat'):
        case = source/'runs'/name
        copy_capture(case/'native', runs/name)
        shutil.copyfile(case/'staging.json', runs/name/'baseline-staging.json')
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.json', '.stdout', '.stderr'):
            shutil.copyfile(path, validation/path.name)
    copy_capture(source/'phase10-baseline', validation/'phase10-baseline')
    shutil.copytree(source/'runs/zero/dependencies/setups', validation/'source-preparation')
    report = ROOT/'docs/PHASE11_PIPA_NAVIGATION.md'
    entries = {str(report.relative_to(ROOT)): sha(report)}
    entries.update({str(path.relative_to(ROOT)): sha(path) for path in sorted(HERE.rglob('*'))
                    if path.is_file() and path.name != 'checksums.json' and '__pycache__' not in path.parts})
    # The package seal does not include itself. Nested older check manifests
    # are included below, since they remain useful evidence in their own right.
    for path in sorted(HERE.rglob('checksums.json')):
        if path != HERE/'checksums.json':
            entries[str(path.relative_to(ROOT))] = sha(path)
    (HERE/'checksums.json').write_text(json.dumps({'classification': 'VERIFIED retained diagnostic evidence',
        'sha256': entries, 'files': len(entries), 'gzip': 'lossless, mtime=0; raw hashes remain in each capture'}, indent=2)+'\n')
    print(json.dumps({'retained_cases': 5, 'files_sealed': len(entries)}))


if __name__ == '__main__':
    main()
