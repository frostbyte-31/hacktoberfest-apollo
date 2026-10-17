#!/usr/bin/env python3
"""GPL-2.0-or-later. Native, single-axis diagnostic CDU transport validation.

Each workload uses a new process, genuine Luminary099, the unchanged retained
yaAGC ringbuffer backend and read-only inspectors. This is not a vehicle test.
"""
import argparse
import collections
import ctypes
import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROPE_SHA256 = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
CASES = {
    'positive_slow': [[1] * 12],
    'negative_slow': [[3] * 12],
    'positive_fast': [[17] * 24],
    'negative_fast': [[19] * 24],
    'mixed': [[1] * 4 + [3] * 3 + [17] * 8 + [19] * 7],
    'alternating_supported': [[1, 3, 17, 19] * 16],
    'signed_wrap': [[3], [1]],
    'fifo_capacity_control': [[1, 3] * 64 + [1]],
    'ringbuffer_capacity_control': [[17] * 1025],
}
SIGNS = {1: 1, 3: -1, 17: 1, 19: -1}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def validate_output(path):
    """Allow a new scratch destination; never replace retained evidence."""
    if path.is_symlink():
        raise ValueError('Output must not be a symlink')
    output = path.resolve()
    if output.exists():
        raise ValueError('Output already exists; use a new scratch destination')
    if ROOT in output.parents and ROOT / '.build' not in output.parents:
        raise ValueError('Run into .build or external scratch; retained evidence stays immutable')
    return output


def snapshot(lib):
    return {'cycle': lib.diag_cycle(), 'cdu': [lib.diag_cdu(i) for i in range(3)],
            'fifo_entries': lib.diag_entries(), 'fifo_pending': lib.diag_pending(),
            'fifo_head_code': lib.diag_head_code(),
            'incoming': lib.diag_incoming(), 'next_update': lib.diag_deadline(),
            'checker': lib.diag_checker()}


def workload(name, library, output):
    """Internal worker; fresh process avoids upstream static FIFO reset ambiguity."""
    lib = ctypes.CDLL(str(library))
    for symbol in ('diag_cycle', 'diag_deadline'):
        getattr(lib, symbol).restype = ctypes.c_uint64
    lib.packet_write.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
    lib.cpu_reset()
    rope_path = ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin'
    rope = (ctypes.c_ubyte * 73728).from_buffer_copy(rope_path.read_bytes())
    lib.set_fixed(rope)
    lib.diag_step(200000)
    initial = snapshot(lib)
    if initial['cdu'] != [0, 0, 0] or initial['fifo_pending'] or initial['incoming']:
        raise RuntimeError('Diagnostic initial conditions are not idle zero-CDU')
    trace = output.open('x')
    def emit(event, **values):
        trace.write(json.dumps({'ev': event, **values}, separators=(',', ':'), allow_nan=False) + '\n')
    emit('initial', case=name, classification='diagnostic_transport_not_vehicle_or_flight_output',
         state=initial, phases=CASES[name], counter_octal='032', ram_writes=0,
         initialization='fresh cpu_reset, authentic rope, 200000 cpu calls, no hardware input fixture',
         exact_clock_hz={'numerator': 1024000, 'denominator': 12},
         wrapper_cycle_seconds=0.00001172)
    requests = accepted = consumed = enqueued = dropped = applied = rejected = expected_delta = 0
    max_entries = max_pending = 0
    for phase, codes in enumerate(CASES[name]):
        incoming_codes = collections.deque()
        fifo_codes = collections.deque()
        for code in codes:
            before = snapshot(lib)
            status = lib.packet_write(128 | 0o32, code)
            requests += 1
            accepted += status > 0
            rejected += status == 0
            if status < 0:
                raise RuntimeError('Malformed packet')
            if status > 0:
                incoming_codes.append(code)
            emit('delivery', phase=phase, code=code, packet_write_result=status,
                 state=snapshot(lib), delivery_cycle=before['cycle'])
        before = snapshot(lib)
        # No elapsed host time enters this loop. Counter input costs one call;
        # FIFO service is observed separately on subsequent real CPU calls.
        while before['incoming'] or before['fifo_pending']:
            if before['cycle'] - initial['cycle'] > 1000000:
                raise RuntimeError('Bounded queue settlement timeout')
            lib.diag_step(1)
            after = snapshot(lib)
            if after['cdu'][1:] != [0, 0]:
                raise RuntimeError('Unsupported cross-axis counter motion')
            max_entries = max(max_entries, after['fifo_entries'])
            max_pending = max(max_pending, after['fifo_pending'])
            if after['incoming'] == before['incoming'] - 1:
                code = incoming_codes.popleft()
                consumed += 1
                queued = after['fifo_pending'] == before['fifo_pending'] + 1
                if queued:
                    fifo_codes.append(code)
                    enqueued += 1
                    expected_delta += SIGNS[code]
                elif after['fifo_pending'] == before['fifo_pending']:
                    dropped += 1
                else:
                    raise RuntimeError('Unexpected FIFO enqueue transition')
                if after['cdu'] != before['cdu']:
                    raise RuntimeError('Packet consumption unexpectedly applied counter')
                emit('consumption', phase=phase, code=code, fifo_enqueued=queued, before=before, after=after)
            elif after['fifo_pending'] == before['fifo_pending'] - 1:
                expected_code = fifo_codes.popleft()
                code = before['fifo_head_code']
                if code != expected_code:
                    raise RuntimeError('Actual FIFO head sign/rate disagrees with requested operation order')
                if after['cdu'][0] != (before['cdu'][0] + SIGNS[code]) % 32768:
                    raise RuntimeError('Applied operation has wrong modular counter delta')
                applied += 1
                emit('application', phase=phase, code=code, expected_code=expected_code, before=before, after=after)
            elif (after['incoming'], after['fifo_pending'], after['cdu']) != (before['incoming'], before['fifo_pending'], before['cdu']):
                raise RuntimeError('Unaccounted memory/queue change')
            before = after
        if incoming_codes or fifo_codes:
            raise RuntimeError('Queue observer failed to account for pulses')
        settled = snapshot(lib)
        lib.diag_step(1000)
        quiet = snapshot(lib)
        if quiet['cdu'] != settled['cdu'] or quiet['incoming'] or quiet['fifo_pending']:
            raise RuntimeError('Counter changed during 1000-call post-settlement observation')
        emit('settled', phase=phase, state=settled, after_1000_idle_calls=quiet)
    final = snapshot(lib)
    summary = {'case': name, 'classification': 'diagnostic_transport', 'requests': requests,
               'packet_accepted': accepted, 'ringbuffer_rejected': rejected,
               'consumed': consumed, 'fifo_enqueued': enqueued, 'fifo_dropped': dropped,
               'applied': applied, 'max_fifo_entries': max_entries, 'max_fifo_pending': max_pending,
               'expected_modular_cdu': expected_delta % 32768, 'final_state': final,
               'all_accounted': requests == accepted + rejected and accepted == enqueued + dropped
                                and enqueued == applied and final['cdu'][0] == expected_delta % 32768}
    if not summary['all_accounted']:
        raise RuntimeError('Unaccounted transport loss')
    if name == 'fifo_capacity_control':
        if (dropped, max_entries, accepted, applied) != (1, 128, 129, 128):
            raise RuntimeError('FIFO negative control did not expose expected one silent drop')
    elif dropped:
        raise RuntimeError('Supported workload lost CDU operations')
    if name == 'ringbuffer_capacity_control':
        if (rejected, accepted, max_entries) != (2, 1023, 1):
            raise RuntimeError('Ringbuffer bounded negative control disagrees with source')
    elif rejected:
        raise RuntimeError('Supported workload rejected input')
    emit('summary', **summary)
    trace.close()


def analyze(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    summary = rows[-1]
    if summary.get('ev') != 'summary' or not summary['all_accounted']:
        raise ValueError('Incomplete trace')
    applications = [r for r in rows if r['ev'] == 'application']
    consumptions = [r for r in rows if r['ev'] == 'consumption']
    applications_by_code = collections.Counter(r['code'] for r in applications)
    intervals = collections.Counter(b['after']['cycle'] - a['after']['cycle']
                                    for a, b in zip(applications, applications[1:]))
    summary = {k: v for k, v in summary.items() if k != 'ev'}
    summary.update({'raw_sha256': digest(path), 'application_codes': dict(applications_by_code),
                    'application_interval_cpu_calls': dict(sorted(intervals.items())),
                    'first_consumption_cycle': consumptions[0]['after']['cycle'],
                    'first_application_cycle': applications[0]['after']['cycle'],
                    'last_application_cycle': applications[-1]['after']['cycle'],
                    'last_consumption_cycle': consumptions[-1]['after']['cycle']})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--case', choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument('--library', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        output = validate_output(args.output)
    except ValueError as error:
        parser.error(str(error))
    if args.case:
        workload(args.case, args.library, output)
        return
    if args.source is None:
        parser.error('--source is required')
    output.mkdir(parents=True)
    source = args.source.resolve()
    expected = json.loads((ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
    for relative, wanted in expected.items():
        if digest(source / relative) != wanted:
            raise RuntimeError('Pinned source differs: ' + relative)
    if digest(ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin') != ROPE_SHA256:
        raise RuntimeError('Pinned Luminary099 rope differs')
    write_json(output / 'inputs.json', {'upstream_revision': 'f577e3fd917866c59334e6cdd32504f09df76f60',
               'source_sha256': expected,
               'harness_sha256': {p.name: digest(p) for p in (HERE / 'inspect_bridge.c', Path(__file__))},
               'rope_sha256': digest(ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin')})
    commands = []
    def run(argv, label):
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (output / (label + '.stdout')).open('w') as out, (output / (label + '.stderr')).open('w') as err:
            result = subprocess.run([str(x) for x in argv], cwd=ROOT, stdout=out, stderr=err, timeout=120)
        commands.append({'argv': [str(x) for x in argv], 'cwd': str(ROOT), 'start_utc': start,
                         'end_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit': result.returncode})
        write_json(output / 'commands.json', commands)
        if result.returncode:
            raise RuntimeError('Command failed: ' + label)
    compiler = shutil.which(args.cc)
    if compiler is None:
        raise RuntimeError('C compiler unavailable')
    run([compiler, '--version'], 'compiler-version')
    run([sys.executable, '--version'], 'python-version')
    engine = source / 'yaAGC'
    others = ['wasm.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c']
    library = output / 'engine.so'
    run([compiler, '-shared', '-fPIC', '-O2', '-I' + str(engine), HERE / 'inspect_bridge.c',
         *[engine / name for name in others], '-lm', '-o', library], 'build')
    summaries = {}
    for name in CASES:
        for suffix in ('', '-replay'):
            run([sys.executable, Path(__file__), '--case', name, '--library', library,
                 '--output', output / (name + suffix + '.jsonl')], name + suffix)
        first, replay = output / (name + '.jsonl'), output / (name + '-replay.jsonl')
        if first.read_bytes() != replay.read_bytes():
            raise RuntimeError('Replay differs: ' + name)
        summaries[name] = analyze(first)
        summaries[name]['replay_byte_identical'] = True
    write_json(output / 'summary.json', {'status': 'VERIFIED', 'cases': summaries,
               'binary_sha256': digest(library), 'platform': platform.platform(),
               'clock': '1024000/12 CPU calls/second; wrapper 11.72us is an approximation',
               'scope': 'single-axis synthetic counter-transport diagnostics; no vehicle, mission startup or flight-control inference'})
    print(json.dumps({name: {k: s[k] for k in ('applied', 'fifo_dropped', 'ringbuffer_rejected', 'max_fifo_entries', 'final_state')}
                      for name, s in summaries.items()}, indent=2))


if __name__ == '__main__':
    main()
