#!/usr/bin/env python3
"""Read-only comparison and compact retention of a fresh Phase12 release run.

The new raw traces remain in the requested build directory.  They are compared
byte for byte against decompressed, checksum-sealed original traces; no original
artifact is rewritten or regenerated.
"""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root, run = args.checkout.resolve(), args.run.resolve()
    destination = Path(__file__).resolve().parent
    if root not in run.parents or run.name != 'final-integration-release':
        raise ValueError('Expected a fresh release run in the clean source checkout')
    completion = json.loads((run/'completion.json').read_text())
    if completion.get('all_native_and_causal_checks_pass') is not True:
        raise ValueError('Fresh native validator did not complete successfully')

    seals = {}
    for name in ('phase10-evidence', 'phase11-evidence', 'phase12-evidence',
                 'phase12-release-evidence'):
        manifest = root/'docs'/name/'checksums.json'
        expected = json.loads(manifest.read_text())['sha256']
        changed = [name for name, digest in expected.items()
                   if not (root/name).is_file() or sha(root/name) != digest]
        seals[name] = {'files_checked': len(expected),
                       'seal_sha256': sha(manifest),
                       'changed_or_missing': changed}
        if changed:
            raise ValueError('Original evidence changed: '+repr(changed))

    comparisons = {}
    for name in ('sink', 'connected', 'no-feedback', 'repeat'):
        retained = root/'docs/phase12-evidence/runs/verified'/name/'trace.jsonl.gz'
        fresh = run/'runs'/name/'native/trace.jsonl'
        raw_a, raw_b = hashlib.sha256(), hashlib.sha256()
        length, blocks, equal = 0, 0, True
        with gzip.open(retained, 'rb') as old, fresh.open('rb') as new:
            while True:
                a, b = old.read(1024*1024), new.read(1024*1024)
                if not a and not b:
                    break
                raw_a.update(a)
                raw_b.update(b)
                equal = equal and a == b
                length += len(b)
                blocks += 1
        comparisons[name] = {'retained_gzip': str(retained), 'fresh_raw': str(fresh),
            'retained_raw_sha256': raw_a.hexdigest(),
            'fresh_raw_sha256': raw_b.hexdigest(), 'fresh_bytes': length,
            'blocks_compared': blocks, 'byte_for_byte_equal': equal}
        if not equal or raw_a.digest() != raw_b.digest():
            raise ValueError('Fresh native trace differs: '+name)

    prior = json.loads((root/'docs/phase12-evidence/prior_hashes.json').read_text())['sha256']
    changed = [name for name, digest in prior.items()
               if not (root/name).is_file() or sha(root/name) != digest]
    if changed:
        raise ValueError('Prior source/evidence changed: '+repr(changed))

    original_frontend = json.loads((root/'docs/phase12-evidence/frontend-before.json').read_text())
    frontend_root = Path(original_frontend['root'])
    frontend_paths = set(filter(None, subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=frontend_root).decode().split('\0')))
    frontend_changed = [name for name, digest in original_frontend['sha256'].items()
                        if not (frontend_root/name).is_file() or sha(frontend_root/name) != digest]
    frontend = {'root': str(frontend_root),
        'files_checked': len(original_frontend['sha256']),
        'changed_or_missing': frontend_changed,
        'inventory_added': sorted(frontend_paths-set(original_frontend['sha256'])),
        'inventory_removed': sorted(set(original_frontend['sha256'])-frontend_paths),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=frontend_root, text=True).strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=frontend_root, text=True).strip(),
        'status': subprocess.check_output(['git', 'status', '--short'], cwd=frontend_root, text=True)}
    frontend['unchanged'] = (not frontend_changed and not frontend['inventory_added']
        and not frontend['inventory_removed']
        and all(frontend[name] == original_frontend[name] for name in ('branch', 'head', 'status')))
    if not frontend['unchanged']:
        raise ValueError('The protected frontend worktree changed')

    for path in sorted(run.iterdir()):
        if path.is_file() and path.suffix in ('.json', '.stdout', '.stderr'):
            shutil.copyfile(path, destination/path.name)
    for case in ('sink', 'connected', 'no-feedback', 'repeat'):
        source = run/'runs'/case/'native'
        target = destination/'native-metadata'/case
        target.mkdir(parents=True, exist_ok=False)
        for path in sorted(source.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.stdout', '.stderr'):
                shutil.copyfile(path, target/path.name)
        integrity = source/'source-integrity'
        if integrity.is_dir():
            shutil.copytree(integrity, target/'source-integrity')
    setup_candidates = list((run/'dependencies/setups').glob('*/setup.json'))
    if len(setup_candidates) != 1:
        raise ValueError('Ambiguous original source preparation')
    setup = json.loads(setup_candidates[0].read_text())
    save(destination/'trace-comparison.json', comparisons)
    summary = {
        'classification': 'VERIFIED bounded synthetic original-software DPS/PIPA release gate',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_checkout': str(root), 'raw_output': str(run),
        'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip(),
        'source_working_tree': subprocess.check_output(['git', 'status', '--short'], cwd=root, text=True),
        'original_evidence_seals': seals,
        'prior_files': {'files_checked': len(prior), 'changed_or_missing': changed},
        'protected_frontend': frontend,
        'fresh_trace_comparisons': comparisons,
        'fresh_test_results': completion['test_results'],
        'total_passed': sum(row['passed'] for row in completion['test_results'].values()),
        'all_four_traces_equal': all(row['byte_for_byte_equal'] for row in comparisons.values()),
        'original_setup': setup,
        'limitations': [
            'Bounded synthetic fixed-attitude scenario; not calibrated historical descent.',
            'The original flight computer controls the documented engine/PIPA experiment; this is not a complete landing.',
            'Raw fresh streams remain in the build output; matching immutable retained compressed streams supply the same bytes.'
        ]}
    save(destination/'release-gate.json', summary)
    print(json.dumps({'passed': summary['total_passed'],
                      'all_four_traces_equal': summary['all_four_traces_equal'],
                      'prior_files_unchanged': len(prior),
                      'source_working_tree': summary['source_working_tree']}, indent=2))


if __name__ == '__main__':
    main()
