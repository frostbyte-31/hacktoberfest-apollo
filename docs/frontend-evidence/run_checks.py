#!/usr/bin/env python3
"""Capture frontend contract tests and unchanged backend regressions in a new folder."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node', default='node')
    p.add_argument('--tsc', type=Path, default=ROOT / 'frontend/node_modules/typescript/lib/tsc.js')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if ROOT / '.build' not in output.parents or output.exists():
        raise ValueError('Use a new output directory under this checkout .build')
    output.mkdir(parents=True)
    commands = [
        ('preservation-before', [sys.executable, '-B', str(HERE / 'check_integrity.py')]),
        ('typecheck', [args.node, str(args.tsc.resolve()), '-p', 'frontend/tsconfig.json']),
        ('presentation', [args.node, '--test', *[str(path.relative_to(ROOT)) for path in sorted((ROOT / 'frontend/tests').glob('*.test.mjs'))]]),
        ('backend', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'backend/tests', '-v']),
        ('recorded-attitude', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'frontend/tests', '-p', 'test_replay.py', '-v']),
        ('recorded-guidance', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'frontend/tests', '-p', 'test_guidance_data.py', '-v']),
        ('launcher', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/demo/tests', '-v']),
        ('live-evidence', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'docs/live-control-evidence', '-p', 'test_*.py', '-v']),
        ('export-verification', [sys.executable, '-B', 'tools/demo/demo.py', 'verify']),
        ('preservation-after', [sys.executable, '-B', str(HERE / 'check_integrity.py')]),
    ]
    record = {'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'python': sys.version, 'platform': platform.platform(), 'commands': [],
              'interpretation': 'Frontend/API/data checks do not prove powered descent or new AGC execution. Historical missing-log checks were not rerun by this focused suite.'}
    paths = [path for folder in ('frontend', 'backend') for path in (ROOT / folder).rglob('*')
             if path.is_file() and '__pycache__' not in path.parts and 'node_modules' not in path.parts]
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    record['source_sha256'] = hashes
    failed = False
    for name, command in commands:
        row = {'name': name, 'argv': command, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        print('Running ' + name, flush=True)
        with (output / (name + '.stdout')).open('w') as stdout, (output / (name + '.stderr')).open('w') as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        row.update(exit=result.returncode, ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        record['commands'].append(row)
        save(output / 'record.json', record)
        print('{}: exit {}'.format(name, result.returncode), flush=True)
        failed |= result.returncode != 0
    changed = [name for name, expected in hashes.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    record.update(passed=not failed and not changed, changed_during_checks=changed)
    save(output / 'record.json', record)
    return 0 if record['passed'] else 1
if __name__ == '__main__':
    raise SystemExit(main())
