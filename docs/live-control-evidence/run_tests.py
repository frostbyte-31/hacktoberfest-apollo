#!/usr/bin/env python3
"""Record strict adapter-unit and actual captured-trace test outcomes."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

sys.dont_write_bytecode = True
from live_common import HERE, ROOT, digest, new_output, verify_prior, write_json

SUITES = {'native-unit': (ROOT / 'backend/tests', 'test_native.py'),
          'live-traces': (HERE, 'test_evidence.py')}


def child(name, result_path):
    directory, pattern = SUITES[name]
    suite = unittest.defaultTestLoader.discover(str(directory), pattern=pattern)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    counts = {'tests_run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'skipped': len(result.skipped),
              'expected_failures': len(result.expectedFailures),
              'unexpected_successes': len(result.unexpectedSuccesses)}
    strict = result.testsRun > 0 and result.wasSuccessful() and not any(
        counts[key] for key in counts if key != 'tests_run')
    write_json(result_path, {'suite': name, **counts, 'strict_success': strict})
    return 0 if strict else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--evidence', type=Path, default=HERE / 'runs/2026-10-17-verified/validation')
    parser.add_argument('--child', choices=list(SUITES), help=argparse.SUPPRESS)
    parser.add_argument('--result', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return child(args.child, args.result)
    output = new_output(args.output or ROOT / '.build/live-control/tests' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]))
    before = verify_prior()
    write_json(output / 'preservation-before.json', before)
    if not before['ok']:
        raise ValueError('Prior evidence changed')
    paths = [Path(__file__), HERE / 'test_evidence.py', HERE / 'analyze.py', HERE / 'live_common.py',
             ROOT / 'backend/tests/test_native.py', ROOT / 'backend/native_session.py']
    write_json(output / 'executed-code-hashes.json', {str(p.relative_to(ROOT)): digest(p) for p in paths})
    commands, total, success = [], 0, True
    environment = dict(os.environ, APOLLO_LIVE_EVIDENCE=str(args.evidence.resolve()))
    for name in SUITES:
        argv = [sys.executable, '-B', Path(__file__), '--child', name, '--result', output / (name+'.result.json')]
        argv = list(map(str, argv))
        record = {'argv': argv, 'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'evidence': environment['APOLLO_LIVE_EVIDENCE'], 'exit': 'RUNNING'}
        commands.append(record)
        write_json(output / 'commands.json', commands)
        with (output / (name+'.stdout')).open('x') as stdout, (output / (name+'.stderr')).open('x') as stderr:
            process = subprocess.Popen(argv, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
            record['pid'] = process.pid
            write_json(output / 'commands.json', commands)
            record['exit'] = process.wait(timeout=120)
        record['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(output / 'commands.json', commands)
        result_file = output / (name+'.result.json')
        result = json.loads(result_file.read_text()) if result_file.exists() else {}
        total += result.get('tests_run', 0)
        success = success and record['exit'] == 0 and result.get('strict_success', False)
    after = verify_prior()
    write_json(output / 'preservation-after.json', after)
    success = success and after['ok']
    write_json(output / 'completion.json', {'strict_success': success, 'tests_run': total,
        'scope': 'Native adapter unit rejection checks and captured authentic native traces; fresh execution is the separate run_validation command',
        'prior_files_preserved': after['files_checked']})
    print('Live control tests: ' + str(output))
    print(str(total) + ' tests; strict_success=' + str(success))
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
