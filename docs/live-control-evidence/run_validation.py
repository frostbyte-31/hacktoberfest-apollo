#!/usr/bin/env python3
"""Run fresh signed yaw/pitch live-session experiments, never replay inputs."""
import argparse
import datetime
import importlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
from live_common import ROOT, HERE, digest, new_output, verify_prior, write_json

sys.path.insert(0, str(ROOT))

# Declared before the first experiment: authentic inputs are made at the same
# call boundaries in fresh sessions. Repeat equivalence covers complete traces.
CASES = {
    'yaw_plus': (1, 0),
    'yaw_minus': (-1, 0),
    'pitch_plus': (0, 1),
    'pitch_minus': (0, -1),
    'combined': (-1, 1),
    'combined_replay': (-1, 1),
}
CONTROL_CYCLE = 2500000
HOLD_CYCLES = 85333
END_CYCLE = 3200000


def run_case(native, assets, destination, yaw, pitch):
    session = native.NativeSession(assets, output=destination)
    # NativeSession itself reserves the fresh output directory on start. The
    # call journal is created after start so it cannot obstruct that guard.
    actions = []

    def record(method, *args, **kwargs):
        entry = {'method': method, 'args': list(args), 'kwargs': kwargs,
                 'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        actions.append(entry)
        if destination.exists():
            write_json(destination / 'api-actions.json', actions)
        try:
            entry['result'] = json.loads(json.dumps(getattr(session, method)(*args, **kwargs), allow_nan=False))
            return entry['result']
        finally:
            entry['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if destination.exists():
                write_json(destination / 'api-actions.json', actions)

    try:
        startup = record('start')
        if not startup['ready']:
            raise ValueError('Actual original startup did not establish readiness')
        record('advance_to', CONTROL_CYCLE)
        command = record('command', yaw=yaw, pitch=pitch, duration_cycles=HOLD_CYCLES)
        record('advance_to', CONTROL_CYCLE + HOLD_CYCLES + 1)
        endpoint = record('advance_to', END_CYCLE)
        summary = record('stop', 'deterministic_validation')
        write_json(destination / 'validation-call-results.json', {
            'startup': startup, 'command': command, 'endpoint': endpoint, 'summary': summary})
    except BaseException as error:
        try:
            record('stop', 'validation_failure')
        except BaseException as stop_error:
            write_json(destination / 'stop-failure.json', {'error': repr(stop_error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', choices=list(CASES))
    args = parser.parse_args()
    proposed = args.output or ROOT / '.build/live-control/validation' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    output = new_output(proposed)
    try:
        before = verify_prior()
        write_json(output / 'preservation-before.json', before)
        if not before['ok']:
            raise ValueError('Existing evidence changed; refusing new experiments')
        write_json(output / 'environment.json', {
            'argv': sys.argv, 'cwd': str(Path.cwd()), 'python': sys.version,
            'platform': platform.platform(),
            'repository_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'classification': 'Fresh native original Luminary execution with simulated modern rotational dynamics',
            'scope': 'Bounded user-controller signed yaw/pitch; no descent, replacement guidance or flight telemetry'})
        native = importlib.import_module('backend.native_session')
        assets = native.prepare_assets(output / 'assets')
        write_json(output / 'experiment-plan.json', {
            'cases': CASES, 'control_cycle': CONTROL_CYCLE, 'hold_cycles': HOLD_CYCLES,
            'end_cycle': END_CYCLE, 'cycle_seconds': 12 / 1024000,
            'repeat_criterion': 'Identical complete raw traces for combined and combined_replay',
            'neutralization': 'NativeSession bounded command expires through actual normal RHC inputs',
            'settlement': 'Explicit physics freeze, real FIFO drain, then 1000 quiet CPU calls'})
        paths = [HERE / 'run_validation.py', HERE / 'analyze.py', HERE / 'live_common.py', HERE / 'prior_hashes.json',
                 Path(native.__file__).resolve()]
        write_json(output / 'executed-code-hashes.json', {str(p.relative_to(ROOT)): digest(p) for p in paths})
        snapshot = output / 'executed-code'
        for path in paths:
            target = snapshot / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        selected = {args.case: CASES[args.case]} if args.case else CASES
        for name, (yaw, pitch) in selected.items():
            run_case(native, assets, output / name, yaw, pitch)
        from analyze import analyze_directory
        results = analyze_directory(output, require_full=not args.case)
        write_json(output / 'analysis.json', results)
        after = verify_prior()
        write_json(output / 'preservation-after.json', after)
        if not after['ok']:
            raise ValueError('Existing evidence changed during experiment')
        write_json(output / 'completion.json', {
            'status': 'VERIFIED', 'cases': list(selected),
            'prior_files_preserved': after['files_checked'],
            'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print('Live control validation: ' + str(output))
    except BaseException as error:
        write_json(output / 'failure.json', {
            'status': 'FAILED or incomplete', 'error': repr(error),
            'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise


if __name__ == '__main__':
    main()
