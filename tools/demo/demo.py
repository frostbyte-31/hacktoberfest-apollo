#!/usr/bin/env python3
"""Verify/launch recorded guidance, or reproduce the frozen native experiment.

The replay needs only Python 3.8+ and retained repository files. Native
reproduction additionally needs Git, a C compiler, make, and the pinned
Virtual AGC archive (downloaded by the unchanged Phase 9 preparer if absent).
No native command changes the current application's or historical evidence's
files: the original experiment runs in a verified, isolated baseline copy.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = '6859637ae8dcb1041db3944489d0f909ed58429f'
P10_MANIFEST = 'docs/phase10-evidence/checksums.json'
P10_MANIFEST_SHA = '10b77abb67914dd6e0f4a13afb967b67f8e96b161217b63f9b0706f9a78fa7cc'
ROPE = 'docs/phase1-evidence/artifacts/MAIN.agc.bin'
ROPE_SHA = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
# Reproducible build metadata for yaYUL's __DATE__ banner. This is the
# retained assembler's build date, not a mission time or Apollo input.
SOURCE_DATE_EPOCH = '1792195200'  # 2026-10-17 00:00:00 UTC
LISTING_SHA = 'd5547c4db630c444004be99556a34e612954eed0b3f27bac4bbe318ad8fbc108'
SYMBOL_SHA = '16ee199168beb4105f94bf8c0e61ccc2429914e73c1f6d731b1f214b81eeb40b'
ARCHIVE_NAME = 'virtualagc-f577e3fd.tar.gz'
CANONICAL = 'docs/phase10-evidence/runs/final-validation'
TRACE_SHA = {
    'final': '6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2',
    'repeat': '6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2',
    'altitude-16km': '34540f19cf0b19284d2d15add4043da854a528625e31a84af30aee4660259eb4',
    'missing-site': '432f74373968b1040c35b5dd3e7e1365c8aa13561e75d07b1d4e0ced02355bc9',
}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def relative_file(root, name):
    """Resolve manifest files without accepting aliases or filesystem escapes."""
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Unsafe manifest path: ' + name)
    path = root.joinpath(*relative.parts)
    if not path.is_file() or any(parent.is_symlink() for parent in [path] + list(path.parents) if parent != root.parent):
        raise ValueError('Required regular file missing or symlinked: ' + name)
    if root.resolve() not in path.resolve().parents:
        raise ValueError('File escapes repository: ' + name)
    return path


def verify_hashes(root, entries):
    mismatches = []
    for name, expected in entries.items():
        try:
            actual = digest(relative_file(root, name))
        except (ValueError, OSError) as error:
            mismatches.append({'path': name, 'error': str(error)})
            continue
        if actual != expected:
            mismatches.append({'path': name, 'expected': expected, 'actual': actual})
    if mismatches:
        raise ValueError('Integrity mismatch: ' + json.dumps(mismatches, sort_keys=True))
    return len(entries)


def verify_artifacts(root=ROOT):
    """Verify sealed Phase 10 files, rope and raw canonical replay bytes.

    This deliberately does not claim the new application is the old frozen
    application. Full original 4098-file checks run unchanged in the isolated
    baseline during native reproduction.
    """
    root = root.resolve()
    verify_hashes(root, {P10_MANIFEST: P10_MANIFEST_SHA, ROPE: ROPE_SHA})
    manifest = json.loads((root / P10_MANIFEST).read_text())
    if manifest.get('base_revision') != BASE_REVISION:
        raise ValueError('Unexpected Phase 10 baseline revision')
    checked = verify_hashes(root, manifest['sha256'])
    traces = {}
    for scenario, expected in TRACE_SHA.items():
        path = relative_file(root, CANONICAL + '/' + scenario + '/trace.jsonl.gz')
        result = hashlib.sha256()
        with gzip.open(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                result.update(block)
        actual = result.hexdigest()
        if actual != expected:
            raise ValueError('Canonical raw trace mismatch: ' + scenario)
        traces[scenario] = actual
    return {'verified': True, 'phase10_sealed_files': checked,
            'phase10_manifest_sha256': P10_MANIFEST_SHA,
            'rope_sha256': ROPE_SHA, 'canonical_raw_trace_sha256': traces,
            'mode': 'RECORDED AUTHENTIC EXECUTION REPLAY',
            'synthetic_scenario': True, 'powered_descent': 'NOT RUN'}


def record(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def run_logged(argv, cwd, directory, name, environment=None):
    row = {'argv': list(map(str, argv)), 'cwd': str(cwd),
           'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if environment:
        row['environment_overrides'] = dict(environment)
    record(directory / (name + '.command.json'), row)
    with (directory / (name + '.stdout')).open('w') as out, (directory / (name + '.stderr')).open('w') as err:
        result = subprocess.run(row['argv'], cwd=str(cwd), stdout=out, stderr=err,
                                env=dict(os.environ, **environment) if environment else None)
    row['exit'] = result.returncode
    row['ended_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record(directory / (name + '.command.json'), row)
    print('{}: exit {}'.format(name, result.returncode), flush=True)
    if result.returncode:
        raise RuntimeError('Failed {}; diagnostics: {}'.format(name, directory))
    return directory / (name + '.stdout')


def extract_baseline(archive, destination):
    """Extract regular Git archive files into a new directory, never over files."""
    with tarfile.open(archive, 'r:') as source:
        for member in source.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe Git archive member: ' + member.name)
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            else:
                raise ValueError('Unsupported Git archive member: ' + member.name)


def stage_baseline(root, work):
    """Keep original preservation guards meaningful while allowing the new UI."""
    root, work = root.resolve(), work.resolve()
    verified = verify_artifacts(root)
    work.mkdir(parents=True, exist_ok=False)
    snapshot = work / 'baseline'
    snapshot.mkdir()
    archive = work / 'baseline.git.tar'
    run_logged(['git', 'archive', '--format=tar', '--output', str(archive), BASE_REVISION],
               root, work, 'git-archive')
    extract_baseline(archive, snapshot)
    prior_path = root / 'docs/phase10-evidence/prior_hashes.json'
    prior = json.loads(prior_path.read_text())
    if prior.get('source_revision') != BASE_REVISION or len(prior['sha256']) != 4098:
        raise ValueError('Unexpected original preservation inventory')
    original_count = verify_hashes(snapshot, prior['sha256'])
    manifest = json.loads((root / P10_MANIFEST).read_text())
    entries = dict(manifest['sha256'])
    entries[P10_MANIFEST] = P10_MANIFEST_SHA
    for name in entries:
        if name != 'docs/PHASE10_MISSION_INITIALIZATION.md' and not name.startswith('docs/phase10-evidence/'):
            raise ValueError('Unexpected Phase 10 artifact scope: ' + name)
        source = relative_file(root, name)
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    verify_hashes(snapshot, entries)
    summary = {'verified': True, 'baseline_revision': BASE_REVISION,
               'original_tracked_files_checked': original_count,
               'copied_phase10_files_checked': len(entries),
               'baseline': str(snapshot), 'current_application_copied': False,
               'preservation_guards_modified': False, 'artifacts': verified}
    record(work / 'staging.json', summary)
    return snapshot


def reproduce(root, work, archive=None):
    snapshot = stage_baseline(root, work)
    try:
        prepare = [sys.executable, '-B', str(snapshot / 'docs/phase9-evidence/prepare.py'),
                   '--cache', str(snapshot / '.build/phase10_5/dependencies')]
        supplied = archive.resolve() if archive else root / '.build/phase89' / ARCHIVE_NAME
        if archive or supplied.is_file():
            prepare += ['--archive', str(supplied)]
        # Preserve the original exact listing/symbol guards. The upstream
        # assembler prints its compile date; a later build day otherwise
        # changes only that banner and its dependent listing hash. The
        # standard compiler build-epoch input makes the unchanged build
        # reproducible without rewriting any listing or symbol file.
        output = run_logged(prepare, snapshot, work, 'prepare',
                            {'SOURCE_DATE_EPOCH': SOURCE_DATE_EPOCH})
        setup = json.loads(output.read_text())
        setup_path = Path(setup['setupFile'])
        if not setup.get('verified') or snapshot not in setup_path.resolve().parents:
            raise ValueError('Unverified or external setup returned by original preparer')
        if digest(Path(setup['listing'])) != LISTING_SHA or digest(Path(setup['symbols'])) != SYMBOL_SHA:
            raise ValueError('Compiler did not reproduce original assembler listing/observer metadata; '
                             'SOURCE_DATE_EPOCH support is required. Original guards remain intact.')
        validation = snapshot / '.build/phase10_5/native-validation'
        run_logged([sys.executable, '-B', str(snapshot / 'docs/phase10-evidence/validate.py'),
                    '--setup', str(setup_path), '--output', str(validation)], snapshot, work, 'native-validation')
        actual = json.loads((validation / 'analysis.json').read_text())
        analysis_keys = {'final': 'run', 'repeat': 'repeat', 'altitude-16km': 'altitude_variant',
                         'missing-site': 'missing_site_control'}
        matches = {name: actual[key]['raw_sha256'] == expected
                   for name, expected in TRACE_SHA.items() for key in [analysis_keys[name]]}
        if not actual['all_pass'] or not all(matches.values()):
            raise ValueError('Fresh original execution differs from canonical Phase 10 evidence')
        tests = snapshot / '.build/phase10_5/focused-tests'
        run_logged([sys.executable, '-B', str(snapshot / 'docs/phase10-evidence/run_tests.py'),
                    '--runs', str(validation), '--output', str(tests)], snapshot, work, 'focused-tests')
        result = {'verified': True, 'mode': 'LIVE AUTHENTIC NATIVE REPRODUCTION (separate from UI replay)',
                  'baseline_revision': BASE_REVISION, 'snapshot': str(snapshot),
                  'assembler_build_environment': {'SOURCE_DATE_EPOCH': SOURCE_DATE_EPOCH},
                  'analysis': str(validation / 'analysis.json'), 'tests': str(tests),
                  'canonical_trace_matches': matches, 'powered_descent': 'NOT RUN',
                  'current_original_artifacts_after': verify_artifacts(root)}
        record(work / 'completion.json', result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    except BaseException as error:
        record(work / 'failure.json', {'error': repr(error), 'evidence': str(work)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verify', help='Offline hash/data verification; no compiler, downloads or writes')
    launch = sub.add_parser('launch', help='Verify and launch recorded guidance on loopback')
    launch.add_argument('--port', type=int, default=4173)
    native = sub.add_parser('reproduce', help='Fresh original native experiment in isolated baseline')
    native.add_argument('--archive', type=Path, help='Offline pinned upstream tar.gz; mandatory checksum still applies')
    native.add_argument('--output', type=Path, help='New output directory under .build/phase10_5')
    args = parser.parse_args()
    if args.command == 'reproduce':
        work = (args.output or ROOT / '.build/phase10_5/reproduction' / uuid.uuid4().hex[:12]).resolve()
        allowed = ROOT / '.build/phase10_5'
        if allowed not in work.parents:
            raise ValueError('Reproduction output must be a new directory under .build/phase10_5')
        reproduce(ROOT, work, args.archive)
    else:
        verified = verify_artifacts()
        exporter = [sys.executable, '-B', str(ROOT / 'frontend/tools/export_guidance.py')]
        if args.command == 'verify':
            subprocess.run(exporter + ['--check'], cwd=str(ROOT), check=True)
            print(json.dumps(verified, indent=2, sort_keys=True))
        else:
            if not 0 <= args.port <= 65535:
                parser.error('--port must be in 0..65535')
            subprocess.run(exporter, cwd=str(ROOT), check=True)
            print('RECORDED AUTHENTIC EXECUTION REPLAY · SYNTHETIC · powered descent NOT RUN', flush=True)
            print('Open http://127.0.0.1:{}/guidance.html'.format(args.port), flush=True)
            subprocess.run([sys.executable, '-B', str(ROOT / 'frontend/serve.py'), '--replay-only',
                            '--port', str(args.port)], cwd=str(ROOT), check=True)


if __name__ == '__main__':
    main()
