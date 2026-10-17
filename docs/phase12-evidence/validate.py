#!/usr/bin/env python3
"""Fresh native DPS/PIPA controls using source-verified original flight software.

No retained trace or saved core substitutes for execution. Requires Python, Git,
a C compiler and make; the optional archive and runtime manifest support offline
reuse after the unchanged original source/runtime checks validate them.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_DATE_EPOCH = '1792195200'


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def preserve():
    expected = json.loads((HERE/'prior_hashes.json').read_text())['sha256']
    changed = [name for name, digest in expected.items()
               if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
    if changed:
        raise ValueError('Earlier files changed: '+repr(changed))
    return {'files_checked': len(expected), 'changed_or_missing': changed}


def unittest_counts(path):
    text = path.read_text()
    found = re.search(r'Ran (\d+) tests? in ', text)
    if not found or not re.search(r'^OK\s*$', text, re.M):
        raise ValueError('No successful complete unittest summary: '+str(path))
    return {'passed': int(found.group(1)), 'failed': 0, 'errored': 0, 'skipped': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Fresh directory below .build/phase12')
    parser.add_argument('--archive', type=Path, help='Optional exact pinned Virtual AGC archive')
    parser.add_argument('--runtime-manifest', type=Path, help='Existing locked Tcl manifest; revalidated')
    args = parser.parse_args()
    output = (args.output or ROOT/'.build/phase12'/('validation-'+uuid.uuid4().hex[:12])).resolve()
    # Keep the boundary lexical: a .build symlink must not authorize old evidence.
    if ROOT/'.build/phase12' not in output.parents:
        raise ValueError('Output must be fresh and below .build/phase12')
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    sources = sorted(path for path in HERE.iterdir()
                     if path.is_file() and (path.suffix in ('.py', '.c', '.tcl') or path.name == 'mapping.json'))
    frozen = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    save(output/'code-before.json', frozen)
    save(output/'environment.json', {'utc': utc(), 'python': sys.version,
         'executable': sys.executable, 'platform': platform.platform(),
         'environment': {key: os.environ[key] for key in ('PATH', 'CC', 'MAKE', 'SOURCE_DATE_EPOCH') if key in os.environ},
         'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
         'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
         'scope': 'SYNTHETIC bounded DPS/PIPA experiment, unchanged original Luminary; no full landing'})

    def run(name, argv, *, env=None):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(ROOT),
               'started_utc': utc(), 'environment_overrides': env or {}}
        commands.append(row)
        save(output/'commands.json', commands)
        print(name+' started', flush=True)
        with (output/(name+'.stdout')).open('w') as stdout, (output/(name+'.stderr')).open('w') as stderr:
            process = subprocess.Popen(row['argv'], cwd=ROOT, stdout=stdout, stderr=stderr,
                                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **(env or {})))
            while True:
                try:
                    code = process.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    print(name+' running', flush=True)
        row.update(exit=code, ended_utc=utc())
        save(output/'commands.json', commands)
        print(name+' exit '+str(code), flush=True)
        if code:
            raise RuntimeError('Failed '+name+'; complete stdout/stderr retained')

    try:
        save(output/'preservation-before.json', preserve())
        command = [sys.executable, '-B', ROOT/'docs/phase9-evidence/prepare.py', '--cache', output/'dependencies']
        if args.archive:
            command += ['--archive', args.archive.resolve()]
        run('prepare', command, env={'SOURCE_DATE_EPOCH': SOURCE_DATE_EPOCH})
        setups = sorted((output/'dependencies/setups').glob('*/setup.json'))
        if len(setups) != 1:
            raise ValueError('Ambiguous original verified setup')
        setup = setups[0]
        retained = load('phase12_original_extraction', ROOT/'docs/milestone1-evidence/reproduce.py')
        manifest_path = ROOT/'docs/phase6-evidence/corresponding-source-hashes.json'
        expected = json.loads(manifest_path.read_text())
        if len(expected) != 24:
            raise ValueError('Unexpected original plant-source inventory')
        bundle = ROOT/'docs/phase6-evidence/corresponding-source.tar.gz'
        plant = output/'plant-source'
        # Original extractor checks exact inventory, regular files only, safe
        # relative paths and every hash before writing any source bytes.
        retained.extract_source(bundle, plant, expected)
        save(output/'plant-source-verification.json', {'archive_sha256': sha(bundle),
             'manifest_sha256': sha(manifest_path), 'files_checked': len(expected),
             'sha256': {name: sha(plant/name) for name in sorted(expected)}, 'changed_or_missing': []})
        bootstrap = load('phase12_original_runtime', ROOT/'tools/reproducibility/bootstrap_runtime.py')
        runtime_manifest = args.runtime_manifest.resolve() if args.runtime_manifest else ROOT/'.build/reproducibility/runtime-manifest.json'
        runtime = None
        if runtime_manifest.exists():
            try:
                runtime = bootstrap.validate_runtime(runtime_manifest)
            except (OSError, ValueError, RuntimeError) as error:
                save(output/'existing-runtime-rejected.json', {'manifest': str(runtime_manifest), 'error': repr(error)})
                if args.runtime_manifest:
                    raise
        elif args.runtime_manifest:
            raise ValueError('Requested runtime manifest does not exist')
        if runtime is None:
            cache = output/'runtime-dependencies'
            run('runtime-bootstrap', [sys.executable, '-B', ROOT/'tools/reproducibility/bootstrap_runtime.py', '--cache-dir', cache])
            runtime_manifest = cache/'runtime-manifest.json'
            runtime = bootstrap.validate_runtime(runtime_manifest)
        save(output/'runtime-verification.json', {'manifest_path': str(runtime_manifest),
             'manifest_sha256': sha(runtime_manifest), 'runtime': runtime})
        runs = output/'runs'
        runs.mkdir()
        for name, case in (('sink', 'sink'), ('connected', 'connected'),
                           ('no-feedback', 'no-feedback'), ('repeat', 'connected')):
            run(name, [sys.executable, '-B', HERE/'run_engine.py', '--setup', setup,
                '--plant-source', plant, '--tcl', runtime['executable'],
                '--runtime-manifest', runtime_manifest, '--case', case, '--output', runs/name])
        run('analysis', [sys.executable, '-B', HERE/'analyze.py', '--runs', runs, '--output', output/'analysis.json'])
        run('native-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', HERE,
            '-p', 'test_native.py', '-v'], env={'PHASE12_RUNS': str(runs)})
        run('model-tests', [sys.executable, '-B', HERE/'test_propulsion.py', '--source', plant,
            '--tcl', runtime['executable'], '--runtime-manifest', runtime_manifest, '-v'])
        after = preserve()
        save(output/'preservation-after.json', after)
        changed = [name for name, digest in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
        save(output/'code-after.json', {'files_checked': len(frozen), 'changed_or_missing': changed})
        if changed:
            raise ValueError('Experiment source changed during validation: '+repr(changed))
        counts = {name: unittest_counts(output/(name+'-tests.stderr')) for name in ('native', 'model')}
        analysis = json.loads((output/'analysis.json').read_text())
        if analysis.get('all_pass') is not True:
            raise ValueError('Native analysis did not verify all checks')
        save(output/'completion.json', {'classification': analysis.get('classification', 'See original analysis'),
             'native_cases': ['sink', 'connected', 'no-feedback', 'connected repeat'],
             'test_results': counts, 'all_native_and_causal_checks_pass': True,
             'prior_files_preserved': after['files_checked'],
             'scope': 'Bounded SYNTHETIC fixture; consult analysis for actually demonstrated feedback level; no landing claim'})
        print(json.dumps({'all_pass': True, 'output': str(output), 'test_results': counts}), flush=True)
    except BaseException as error:
        save(output/'failure.json', {'error': repr(error), 'utc': utc()})
        raise


if __name__ == '__main__':
    main()
