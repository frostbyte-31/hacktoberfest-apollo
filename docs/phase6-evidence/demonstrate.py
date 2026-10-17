#!/usr/bin/env python3
"""GPL-2.0-or-later. Inspection/launch layer over unchanged Phase 5 integration."""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import json
import math
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'docs/phase5-evidence'
PIN = 'f577e3fd917866c59334e6cdd32504f09df76f60'
CATEGORIES = {'initial': 'diagnostic', 'input': 'diagnostic', 'output': 'agc_output',
              'plant': 'simulated_vehicle', 'sensor': 'simulated_sensor', 'sample': 'agc_diagnostic_readback'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')

def load_trace(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows or rows[0].get('ev') != 'initial':
        raise ValueError('Missing initial record')
    for row in rows:
        if row.get('ev') not in CATEGORIES:
            raise ValueError('Unknown event')
        def finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError('Non-finite trace value')
            if isinstance(value, list):
                for item in value: finite(item)
            if isinstance(value, dict):
                for item in value.values(): finite(item)
        finite(row)
    samples = [r for r in rows if r['ev'] == 'sample']
    if not samples or samples[-1]['cycle'] != rows[0]['cycles']:
        raise ValueError('Incomplete trace')
    return rows

def inspect_trace(path, output, name):
    rows = load_trace(path)
    plants = [r for r in rows if r['ev'] == 'plant']
    sensors = [r for r in rows if r['ev'] == 'sensor']
    samples = [r for r in rows if r['ev'] == 'sample']
    jets = [r for r in rows if r['ev'] == 'output' and r['channel'] in (5, 6)]
    if not plants: raise ValueError('Missing vehicle state')
    if any(r['accepted'] <= 0 for r in rows if r['ev'] == 'input'):
        raise ValueError('Rejected scheduled input')
    if any(r['delivered'] and r['accepted'] <= 0 for r in sensors):
        raise ValueError('Rejected feedback')
    if any(r['channel'] == 5 and r['value'] for r in jets):
        raise ValueError('Unsupported jet axis')
    if any(r['counter'] != 0o32 for r in sensors):
        raise ValueError('Unsupported sensor axis')
    if any(any(r[k][i] != 0 for k in ('omega', 'gimbals') for i in (1, 2)) for r in plants):
        raise ValueError('Unsupported vehicle axis')
    def first(predicate):
        return next(({'raw_line': i + 1, 'record': r} for i, r in enumerate(rows) if predicate(r)), None)
    selected = {
        'controller_input': first(lambda r: r['ev'] == 'input' and r['cycle'] == 2500000),
        'first_nonzero_rcs': first(lambda r: r['ev'] == 'output' and r['channel'] == 6 and r['value'] != 0),
        'first_motion': first(lambda r: r['ev'] == 'plant' and r['omega'][0] != 0),
        'first_sensor_request': first(lambda r: r['ev'] == 'sensor'),
        'first_cdu_readback': first(lambda r: r['ev'] == 'sample' and r['cdu'][0] != 0),
        'first_opposite_jet_word': first(lambda r: r['ev'] == 'output' and r['channel'] == 6 and r['value'] == 0o252),
    }
    summary = {'status': 'VERIFIED', 'run': name, 'raw_sha256': digest(path),
        'initial': rows[0], 'selected_observations': selected,
        'rcs_nonzero_word_counts_octal': dict(collections.Counter(f'{r["channel"]:03o}:{r["value"]:05o}' for r in jets if r['value'])),
        'generated_sensor_requests': len(sensors), 'delivered_sensor_requests': sum(r['delivered'] for r in sensors),
        'accepted_sensor_requests': sum(r['delivered'] and r['accepted'] > 0 for r in sensors),
        'peak_abs_yaw_deg_s': max(abs(r['omega'][0]) for r in plants),
        'final_model': plants[-1], 'final_agc_readback': samples[-1],
        'link_limit': 'Selected observations establish chronology, not an instruction-level cause for each jet. Cross-run intervention establishes feedback dependence.'}
    write_json(output / f'{name}.summary.json', summary)
    with (output / f'{name}.categorized.jsonl').open('w') as stream:
        for i, row in enumerate(rows):
            record = {'schema': 1, 'run': name, 'raw_line': i + 1,
                      'category': CATEGORIES[row['ev']], 'observation': row}
            if 'cycle' in row:
                record['convention_time_s'] = row['cycle'] * rows[0]['cycle_seconds']
            if row['ev'] == 'sensor':
                record['delivery_cycle'] = row['cycle']
                record['model_interval_end_cycle'] = row['origin_interval_end']
            stream.write(json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n')
    return summary, [(r['cycle'], r['channel'], r['value']) for r in jets]

def summarize(output):
    summaries, jets = {}, {}
    for name in ('closed', 'feedback_off', 'repeat'):
        summaries[name], jets[name] = inspect_trace(output / f'{name}.jsonl', output, name)
    closed, off = summaries['closed'], summaries['feedback_off']
    checks = {
        'fresh_replay_byte_identical': (output / 'closed.jsonl').read_bytes() == (output / 'repeat.jsonl').read_bytes(),
        'feedback_changes_agc_rcs_transcript': jets['closed'] != jets['feedback_off'],
        'connected_has_opposite_word_disconnected_does_not': closed['selected_observations']['first_opposite_jet_word'] is not None and off['selected_observations']['first_opposite_jet_word'] is None,
        'connected_readback_nonzero': closed['final_agc_readback']['cdu'][0] != 0,
        'disconnected_readback_zero': off['final_agc_readback']['cdu'] == [0, 0, 0],
        'disconnected_generated_but_delivered_none': off['generated_sensor_requests'] > 0 and off['delivered_sensor_requests'] == 0,
        'connected_all_requests_accepted': closed['generated_sensor_requests'] > 0 and closed['generated_sensor_requests'] == closed['accepted_sensor_requests'],
    }
    write_json(output / 'validation.json', checks)
    if not all(checks.values()): raise ValueError('Demonstration validation failed')
    text = ['# Recorded demonstration summary', '', '**VERIFIED — native single-axis feedback demonstration; not a landing.**', '',
            '| Run | Model peak yaw °/s | Model final X ° | AGC CDU X | Sensor generated / delivered |',
            '|---|---:|---:|---:|---:|']
    for name, s in summaries.items():
        text.append(f'| {name} | {s["peak_abs_yaw_deg_s"]:.6f} | {s["final_model"]["gimbals"][0]:.6f} | {s["final_agc_readback"]["cdu"][0]} | {s["generated_sensor_requests"]} / {s["delivered_sensor_requests"]} |')
    text += ['', '## Connected event trace (decimal CPU-call indices; octal channel words)', '']
    for label, item in closed['selected_observations'].items():
        if item:
            row = item['record']
            text.append(f'- {label}: call {row["cycle"]}, raw line {item["raw_line"]}: `{json.dumps(row)}`')
    text += ['', 'Actual channel006 word00125 selects positive-yaw jets in this model; word00252 selects opposing jets. The latter occurs in the connected run and not the feedback-disconnected run.',
             '', 'Categorized traces separate AGC outputs, simulated vehicle, simulated sensors and diagnostic readbacks. Sensor delivery and model-origin timestamps are distinct; rows are not globally time-sorted.',
             '', '**ASSUMED:** synthetic LM-7 dynamics, zero initial rates/gimbals, operate-only hardware fixture. Semi-implicit integration; at most853 CPU calls per coupling chunk; sensor delivery at chunk end; counter queues not drained.',
             '', '**NOT RUN:** historical calibration, complete IMU alignment/REFSMMAT, clean mission initialization, cold-start01107 isolation, general three-axis control, coupled WASM, throttle/radar, powered descent, landing, UI, multiplayer or AI crew.',
             '', 'Readiness instruction proof is retained in Phase5, not rerun here. The schedule retains V36E, prematurely requested V37E00E (01520; not P00), and V77E. This is not alarm-free mission readiness.']
    (output / 'SUMMARY.md').write_text('\n'.join(text) + '\n')
    print('\n'.join(text))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists(): parser.error('Output must not exist; choose a new scratch directory')
    if output == ROOT or ROOT in output.parents and not (HERE in output.parents):
        parser.error('Use scratch or the Phase6 evidence directory, never earlier project evidence')
    output.mkdir(parents=True)
    commands = []
    def run(cmd, label):
        cmd = [str(x) for x in cmd]
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with (output / f'{label}.stdout').open('w') as stdout, (output / f'{label}.stderr').open('w') as stderr:
                result = subprocess.run(cmd, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=180)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 'TIMEOUT'
        commands.append({'argv': cmd, 'cwd': str(ROOT), 'start_utc': start,
                         'end_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit': code})
        write_json(output / 'commands.json', commands)
        if code != 0: raise RuntimeError(f'{label} failed: {code}; see preserved stderr')
    try:
        for tool in ('gcc', 'nix'):
            if shutil.which(tool) is None: raise RuntimeError(f'Missing {tool}; install before launching')
        expected = json.loads((PRIOR / 'loop-runs/inputs_source_hashes.json').read_text())
        hashes = {}
        for old_path, wanted in expected.items():
            if old_path.startswith('/tmp/apollo/va/'):
                path = source / old_path.removeprefix('/tmp/apollo/va/')
            else:
                path = ROOT / old_path.removeprefix('/dev-server/')
            if not path.is_file() or digest(path) != wanted:
                raise RuntimeError(f'Pinned input mismatch: {path}')
            hashes[str(path)] = wanted
        # Pin included headers too, not just compilation units (new Phase6 baseline).
        for path in sorted((source / 'yaAGC').glob('*.h')):
            hashes[str(path)] = digest(path)
        write_json(output / 'inputs_source_hashes.json', {'revision': PIN, 'sha256': hashes})
        write_json(output / 'initial_conditions.json', {'schedule': (PRIOR / 'operate_inputs.txt').read_text(),
            'reset': 'Fresh cpu_reset and fresh Tcl plant per run; no restored memory',
            'model': 'Unchanged active upstream LM-7 defaults, stationary zero gimbals',
            'correction': 'Channel030 IMU OPERATE active-low; software clears readiness itself',
            'modes': ['closed', 'feedback_off', 'closed replay'], 'ram_writes': 0})
        run([sys.executable, '--version'], 'python_version')
        run(['gcc', '--version'], 'gcc_version')
        run(['nix', '--version'], 'nix_version')
        tcl = output / 'tcl_version.tcl'
        tcl.write_text('puts [info patchlevel]\nif {[package vcompare [info patchlevel] 8.6] < 0} {exit 1}\n')
        run(['nix', 'shell', 'nixpkgs#tcl', '-c', 'tclsh', tcl], 'tcl_version')
        engine = source / 'yaAGC'
        files = [engine / f for f in ('wasm.c', 'agc_engine.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c')]
        run(['gcc', '-shared', '-fPIC', '-O2', '-I' + str(engine), PRIOR / 'plant_bridge.c', *files, '-lm', '-o', output / 'engine.so'], 'build')
        write_json(output / 'binary_hashes.json', {'engine.so': digest(output / 'engine.so')})
        for name in ('closed', 'feedback_off', 'repeat'):
            run([sys.executable, PRIOR / 'run_loop.py', source, output / 'engine.so', output / f'{name}.jsonl', 'closed' if name == 'repeat' else name], name)
        summarize(output)
        write_json(output / 'completion.json', {'status': 'VERIFIED', 'integration': 'unchanged Phase5', 'runs': 3})
    except Exception as error:
        write_json(output / 'failure.json', {'status': 'NOT RUN or incomplete; inspect commands', 'error': str(error)})
        raise

if __name__ == '__main__': main()