#!/usr/bin/env python3
"""Fresh pinned native PIPA controls, replay, and unchanged Phase 10 regression.

Requires Python, Git, a C compiler and make. The original preparer downloads
the pinned source unless --archive supplies its hash-verified archive. Every
case revalidates that source, listing, symbols and rope; no saved cores or
retained execution outputs substitute for fresh execution.
"""
import argparse
import datetime
import hashlib
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
PHASE10_TRACE_SHA = '6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2'


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Fresh directory below .build/phase11')
    parser.add_argument('--archive', type=Path, help='Optional pinned Virtual AGC archive')
    args = parser.parse_args()
    output = (args.output or ROOT/'.build/phase11'/('validation-'+uuid.uuid4().hex[:12])).resolve()
    if (ROOT/'.build/phase11').resolve() not in output.parents:
        raise ValueError('Output must be a fresh directory below .build/phase11')
    output.mkdir(parents=True, exist_ok=False)
    runs = output/'runs'
    runs.mkdir()
    commands = []
    sources = [HERE/name for name in ('validate.py', 'run_pipa.py', 'pipa_bridge.c',
                                     'pipa_sensor.py', 'analyze.py', 'test_sensor.py', 'test_native.py')]
    frozen = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    save(output/'code-before.json', frozen)
    # Do not capture arbitrary environment variables: they may contain secrets.
    save(output/'environment.json', {'utc': utc(), 'python': sys.version,
         'executable': sys.executable, 'platform': platform.platform(),
         'environment': {key: os.environ[key] for key in ('PATH', 'CC', 'MAKE', 'SOURCE_DATE_EPOCH') if key in os.environ},
         'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
         'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()})

    def run(name, argv, *, cwd=ROOT, env=None):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
               'started_utc': utc(), 'environment_overrides': env or {}}
        commands.append(row)
        save(output/'commands.json', commands)
        print(name+' started', flush=True)
        with (output/(name+'.stdout')).open('w') as out, (output/(name+'.stderr')).open('w') as err:
            process = subprocess.Popen(row['argv'], cwd=cwd, stdout=out, stderr=err,
                                       env=dict(os.environ, **(env or {})))
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
        command = [sys.executable, '-B', HERE/'run_pipa.py', '--case', 'zero', '--output', runs/'zero']
        if args.archive:
            command += ['--archive', args.archive.resolve()]
        run('zero', command)
        setup = runs/'zero/native/setup-used.json'
        for name in ('positive', 'negative', 'disconnected', 'repeat'):
            run(name, [sys.executable, '-B', HERE/'run_pipa.py', '--case', 'positive' if name == 'repeat' else name,
                       '--setup', setup, '--output', runs/name])
        run('analysis', [sys.executable, '-B', HERE/'analyze.py', '--runs', runs, '--output', output/'analysis.json'])
        baseline = runs/'zero/baseline'
        phase10 = baseline/'docs/phase10-evidence'
        run('phase10-baseline', [sys.executable, '-B', phase10/'run_mission.py', '--setup', setup,
                                '--config', phase10/'configs/mission-15km.json', '--output', output/'phase10-baseline'], cwd=baseline)
        code = ('import importlib.util,json,sys; from pathlib import Path; '
                'p=Path(sys.argv[1]); s=importlib.util.spec_from_file_location("original_phase10_analysis",p); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                'r=m.analyze_run(Path(sys.argv[2])); '
                'Path(sys.argv[3]).write_text(json.dumps(r,indent=2,allow_nan=False)+"\\n"); '
                'print(json.dumps({"all_pass":r["all_pass"],"raw_sha256":r["raw_sha256"]})); '
                'sys.exit(0 if r["all_pass"] else 1)')
        run('phase10-analysis', [sys.executable, '-B', '-c', code, phase10/'analyze.py',
                                output/'phase10-baseline', output/'phase10-analysis.json'], cwd=baseline)
        actual = sha(output/'phase10-baseline/trace.jsonl')
        save(output/'phase10-regression.json', {'expected_raw_sha256': PHASE10_TRACE_SHA,
             'actual_raw_sha256': actual, 'byte_identical': actual == PHASE10_TRACE_SHA})
        if actual != PHASE10_TRACE_SHA:
            raise ValueError('Unchanged Phase 10 trace differs from its retained canonical raw bytes')
        for name in ('sensor', 'native'):
            run(name+'-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', HERE,
                '-p', 'test_'+name+'.py', '-v'], env={'PHASE11_RUNS': str(runs)})
        changed = [name for name, expected in frozen.items() if sha(ROOT/name) != expected]
        save(output/'code-after.json', {'files_checked': len(frozen), 'changed_or_missing': changed})
        if changed:
            raise ValueError('Experiment code changed during validation: '+repr(changed))
        counts = {}
        for name in ('sensor', 'native'):
            text = (output/(name+'-tests.stderr')).read_text()
            match = re.search(r'Ran (\d+) tests? in ', text)
            if not match or not re.search(r'^OK\s*$', text, re.M):
                raise ValueError('Unable to verify actual unittest summary for '+name)
            counts[name] = {'passed': int(match.group(1)), 'failed': 0, 'errored': 0, 'skipped': 0}
        save(output/'completion.json', {'classification': 'VERIFIED native PIPA navigation through Level 4',
             'native_cases': ['zero', 'positive', 'negative', 'disconnected', 'positive repeat'],
             'phase10_canonical_raw_trace_identical': True, 'test_results': counts,
             'scope': 'Synthetic stationary instrument and original P47; Level 5 guidance use, ignition and powered descent NOT RUN'})
        print(json.dumps({'all_pass': True, 'output': str(output), 'test_results': counts}), flush=True)
    except BaseException as error:
        save(output/'failure.json', {'error': repr(error), 'utc': utc()})
        raise


if __name__ == '__main__':
    main()
