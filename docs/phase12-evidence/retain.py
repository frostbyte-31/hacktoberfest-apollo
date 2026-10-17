#!/usr/bin/env python3
"""Losslessly package fresh Phase 12 captures; preserve earlier phase evidence."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def inventory():
    paths = [ROOT/'docs/PHASE12_DESCENT_PROPULSION.md']
    paths += [p for p in sorted(HERE.rglob('*')) if p.is_file()
              and p != HERE/'checksums.json' and '__pycache__' not in p.parts]
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def check_raw():
    result = {}
    for name in ('sink', 'connected', 'no-feedback', 'repeat'):
        path = HERE/'runs/verified'/name
        expected = json.loads((path/'trace-sha256.json').read_text())
        value, size = hashlib.sha256(), 0
        with gzip.open(path/'trace.jsonl.gz', 'rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                value.update(block)
                size += len(block)
        if expected != {'sha256': value.hexdigest(), 'bytes': size}:
            raise ValueError('Lossless capture mismatch: '+name)
        result[name] = expected
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--validation', type=Path)
    mode.add_argument('--seal', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.validation:
        source = args.validation.resolve()
        if ROOT/'.build/phase12' not in source.parents:
            raise ValueError('Require a fresh local Phase 12 validation')
        completed = json.loads((source/'completion.json').read_text())
        if completed.get('all_native_and_causal_checks_pass') is not True:
            raise ValueError('Failed or incomplete validation cannot be packaged')
        spec = importlib.util.spec_from_file_location('original_capture_retention',
                                                      ROOT/'docs/phase11-evidence/retain.py')
        retained = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retained)
        runs, validation = HERE/'runs/verified', HERE/'validation'
        runs.mkdir(parents=True, exist_ok=False)
        validation.mkdir(exist_ok=False)
        for name in ('sink', 'connected', 'no-feedback', 'repeat'):
            case = source/'runs'/name
            target = runs/name
            retained.copy_capture(case/'native', target)
            # The original retention helper predates the external Tcl adapter.
            for script in (case/'native').glob('executed-*.tcl'):
                shutil.copyfile(script, target/script.name)
            shutil.copyfile(case/'staging.json', target/'baseline-staging.json')
        for path in source.iterdir():
            if path.is_file() and path.suffix in ('.json', '.stdout', '.stderr'):
                shutil.copyfile(path, validation/path.name)
        shutil.copytree(source/'dependencies/setups', validation/'source-preparation')
        result = {'source_validation': str(source), 'raw_captures': check_raw(),
                  'scope': 'New deterministic diagnostic evidence; no earlier evidence regenerated'}
        (validation/'retention.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'retained_cases': 4, 'lossless': True}))
    elif args.seal:
        check_raw()
        entries = inventory()
        (HERE/'checksums.json').write_text(json.dumps({
            'classification': 'VERIFIED bounded synthetic diagnostic evidence',
            'files': len(entries), 'sha256': entries,
            'gzip': 'Lossless; mtime=0; each original raw digest retained separately'
        }, indent=2)+'\n')
        print(json.dumps({'files_sealed': len(entries)}))
    else:
        expected = json.loads((HERE/'checksums.json').read_text())
        actual = inventory()
        if actual != expected['sha256'] or len(actual) != expected['files']:
            raise ValueError('Phase 12 package inventory or checksum differs')
        check_raw()
        print(json.dumps({'files_verified': len(actual), 'raw_captures_verified': 4}))


if __name__ == '__main__':
    main()
