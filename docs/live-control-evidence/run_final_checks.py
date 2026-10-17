#!/usr/bin/env python3
"""Capture regression output without replacing earlier evidence or hiding gaps."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
from live_common import ROOT, digest, verify_prior, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default='node')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--contracts-only', action='store_true', help='Rerun local API/presentation checks after a restricted loopback bind; leave the earlier full regression result intact.')
    args = parser.parse_args()
    folder = args.output or ROOT / '.build/live-control/final-checks' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    commands = [
        ['make', 'test-live', 'NODE=' + args.node],
        [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'docs/live-control-evidence', '-p', 'test_*.py', '-v'],
    ]
    if not args.contracts_only:
        commands.insert(0, ['make', 'check'])
    before = verify_prior()
    write_json(folder / 'preservation-before.json', before)
    if not before['ok']:
        raise ValueError('Earlier evidence has changed')
    sources = [p for base in ('backend', 'frontend') for p in (ROOT / base).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts]
    sources += [ROOT / 'Makefile', ROOT / 'README.md', Path(__file__)]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in sorted(sources)}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    record = {'argv': sys.argv, 'platform': platform.platform(), 'python': sys.version,
              'node': subprocess.run([args.node, '--version'], capture_output=True, text=True).stdout.strip(),
              'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_sha256': hashes, 'commands': []}
    write_json(folder / 'record.json', record)
    failed = False
    for i, command in enumerate(commands, 1):
        name = '{:02d}'.format(i)
        row = {'command': command, 'cwd': str(ROOT), 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        print('Running ' + ' '.join(command), flush=True)
        with (folder / (name + '.stdout')).open('w') as out, (folder / (name + '.stderr')).open('w') as err:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=out, stderr=err)
        row.update(returncode=result.returncode, ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        record['commands'].append(row)
        write_json(folder / 'record.json', record)
        failed |= result.returncode != 0
        print('Exit {}: {}'.format(result.returncode, folder / name), flush=True)
    after = verify_prior()
    write_json(folder / 'preservation-after.json', after)
    changed = [path for path, sha in hashes.items() if digest(ROOT / path) != sha]
    record.update(passed=not failed and after['ok'] and not changed, changed_during_checks=changed,
                  interpretation='make check preserves three classified historical missing-log errors; inspect its per-suite results. Exit zero is not a claim that those tests passed.')
    write_json(folder / 'record.json', record)
    print(json.dumps({'output': str(folder), 'passed': record['passed']}), flush=True)
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
