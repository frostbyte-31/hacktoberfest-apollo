#!/usr/bin/env python3
"""Run strict Phase 7 physics and authentic-integration tests in fresh processes."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
from common import ROOT, HERE, retained, load_module, write_json, verify_prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--_child', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._child is not None:
        if args.output is None:
            parser.error('Child requires output')
        recorder = load_module('phase7_retained_test_recorder', ROOT / 'docs/milestone2-evidence/run_tests.py')
        return recorder.child(args._child, retained.validate_output(args.output))
    proposed = args.output or ROOT / '.build/phase7/tests' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    output = retained.validate_output(proposed)
    output.mkdir(parents=True)
    commands = []
    try:
        before = verify_prior()
        write_json(output / 'preservation-before.json', before)
        if not before['ok']:
            raise ValueError('Prior evidence changed; refusing tests')
        reports = {}
        for name in ('physics', 'integration'):
            result = output / (name + '.json')
            retained.run_command([sys.executable, '-B', Path(__file__), '--_child', HERE / name,
                                  '--output', result], name, output, commands, timeout=300)
            reports[name] = json.loads(result.read_text())
            if not reports[name]['passed'] or reports[name]['tests_run'] <= 0:
                raise ValueError('Rejected test outcomes: ' + name)
        after = verify_prior()
        write_json(output / 'preservation-after.json', after)
        if not after['ok']:
            raise ValueError('Prior evidence changed during tests')
        summary = {'status': 'VERIFIED', 'tests_run': sum(r['tests_run'] for r in reports.values()),
                   'passed': True, 'groups': reports, 'prior_files_preserved': after['files_checked']}
        write_json(output / 'results.json', summary)
        print(json.dumps({'tests_run': summary['tests_run'], 'passed': True, 'records': str(output)}))
        return 0
    except Exception as error:
        write_json(output / 'failure.json', {'status': 'FAILED or incomplete', 'error': str(error)})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
