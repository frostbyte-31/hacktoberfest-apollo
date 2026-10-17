#!/usr/bin/env python3
"""Capture focused Phase8/9 regressions, Phase10 native evidence and math tests."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=HERE/'runs/final-validation')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    record = {'runs': str(args.runs.resolve()), 'commands': []}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PHASE10_RUNS=str(args.runs.resolve()))
    failed = False
    for name, path in [('phase8', ROOT/'docs/phase8-evidence'), ('phase9', ROOT/'docs/phase9-evidence'),
                       ('phase10-native', HERE), ('phase10-math', HERE/'math')]:
        command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(path), '-p', 'test_*.py', '-v']
        row = {'name': name, 'argv': command, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        with (args.output/(name+'.stdout')).open('w') as out, (args.output/(name+'.stderr')).open('w') as err:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=out, stderr=err)
        row.update(exit=result.returncode, ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        record['commands'].append(row)
        (args.output/'commands.json').write_text(json.dumps(record, indent=2)+'\n')
        print(name+' exit'+str(result.returncode), flush=True)
        failed |= result.returncode != 0
    raise SystemExit(1 if failed else 0)
