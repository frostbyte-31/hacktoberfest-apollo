#!/usr/bin/env python3
"""GPL-2.0-or-later. Bounded paced yaw feedback using retained engine/model.

The modern orchestration adds observable, conservatively paced sensor transport.
Physics and flight execution are reused, not independently reimplemented.
"""
import argparse
import collections
import ctypes
import datetime
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ROOT, digest, load_module, retained, verify_prior, write_json

PHASE5 = ROOT / 'docs/phase5-evidence'
M2CDU = ROOT / 'docs/milestone2-evidence/cdu'
PERIOD = 12 / 1024000
CHUNK = 853
END = 4000000
ROPE_SHA256 = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
OPS = {'PCDU': 1, 'MCDU': 3, 'PCDU_FAST': 17, 'MCDU_FAST': 19}
SIGNS = {1: 1, 3: -1, 17: 1, 19: -1}
CASES = ('original_negative', 'corrected_negative', 'corrected_feedback_off', 'corrected_repeat')


def destination(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Output must not be a symlink')
    output = path.resolve()
    if output.exists():
        raise ValueError('Output already exists')
    if output == ROOT or ROOT in output.parents:
        if ROOT / '.build' not in output.parents:
            raise ValueError('Use new .build or external scratch; retained evidence is immutable')
    return output


def make_schedule():
    # Reuse exact retained fixtures, shifting complete key sequences only.
    original = [list(map(int, line.split())) for line in (PHASE5 / 'operate_inputs.txt').read_text().splitlines()[1:]]
    result = []
    for tick, channel, value in original:
        if 1000000 <= tick <= 1127998:
            tick += 600000  # Complete V37E00E after observed ISSUP/STARTDAP.
        elif 1600000 <= tick <= 1663999:
            tick += 400000  # Complete V77E, no overlap with delayed V37.
        if tick == 2500000:
            value = 12279  # Active-low negative yaw discrete; source retained Phase4.
        elif tick == 2500001:
            value = 32747  # One's-complement -20 at fictitious RHC input0167.
        result.append([tick, channel, value])
    result.sort()
    if len({row[0] for row in result}) != len(result):
        raise ValueError('Input schedules collide')
    return result


def state(lib):
    return {'cycle': lib.diag_cycle(), 'cdu': [lib.diag_cdu(i) for i in range(3)],
            'entries': lib.diag_entries(), 'pending': lib.diag_pending(),
            'head_code': lib.diag_head_code(), 'incoming': lib.diag_incoming(),
            'deadline': lib.diag_deadline(), 'checker': lib.diag_checker()}


def checked_plant_response(response):
    if '|' not in response:
        raise ValueError('Plant failed: ' + response)
    raw_state, packets = response.strip().split('|')
    values = list(map(float, raw_state.split()))
    if len(values) != 6 or not all(math.isfinite(x) for x in values):
        raise ValueError('Malformed/non-finite plant response')
    if any(values[index] != 0 for index in (1, 2, 4, 5)):
        raise ValueError('Unsupported cross-axis plant motion')
    parsed = []
    # Reject unparsed output, rather than silently skipping unsupported sensors.
    remainder = re.sub(r'\{(PCDU_FAST|MCDU_FAST|PCDU|MCDU) (\d+)\}', '', packets).strip()
    if remainder:
        raise ValueError('Unsupported model sensor packet: ' + packets)
    for op, address in re.findall(r'\{(PCDU_FAST|MCDU_FAST|PCDU|MCDU) (\d+)\}', packets):
        if int(address, 8) != 0o32:
            raise ValueError('Unsupported cross-axis CDU sensor')
        parsed.append(OPS[op])
    return values, parsed


def check_jet(channel, value):
    if channel == 5 and value:
        raise ValueError('Unsupported channel005 jet axis')
    if channel == 6 and value & ~0xff:
        raise ValueError('Unsupported channel006 jet bits')


def worker(args, output):
    lib = ctypes.CDLL(str(args.library))
    for symbol in ('diag_cycle', 'diag_deadline'):
        getattr(lib, symbol).restype = ctypes.c_uint64
    lib.packet_write.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
    lib.step_chunk.restype = ctypes.c_uint
    lib.cpu_reset()
    rope = (ctypes.c_ubyte * 73728).from_buffer_copy((ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes())
    lib.set_fixed(rope)
    disconnected = args.case == 'corrected_feedback_off'
    selector = 'original' if args.case == 'original_negative' else 'corrected'
    server = args.server
    log = output.open('x')
    stderr = output.with_suffix('.tcl.stderr').open('x')
    proc = subprocess.Popen([str(args.tcl), str(server), str(args.source)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    schedule = make_schedule()
    def emit(event, category, **row):
        log.write(json.dumps({'ev': event, 'category': category, **row}, separators=(',', ':'), allow_nan=False) + '\n')
    emit('initial', 'diagnostic', selector=selector, feedback_disconnected=disconnected,
         end=END, cycle_seconds=PERIOD, max_coupling_calls=CHUNK, schedule=schedule,
         model='retained active LM-7 defaults; zero rates/gimbals; no flight RAM writes',
         pacing='one outstanding CDU X request until actual application; minimum delivery spacing214slow/14fast CPUcalls',
         drain='at fixed end freeze plant/production, run real CPU and paced queued sensors to empty, then1000quiet calls')
    tick = index = serial = 0
    jets = {5: 0, 6: 0}
    zero = 0
    queue = collections.deque()
    inflight = None
    last_delivery = None
    expected_cdu = 0
    counters = dict(generated=0, delivered=0, consumed=0, enqueued=0, applied=0,
                    ringbuffer_rejects=0, silent_fifo_drops=0, intentionally_disconnected=0)
    peak = max_host = max_age = max_fifo = max_pending = 0
    last_model = [0.0] * 6
    fast_negative = slow_negative_high = 0
    checkpoint = False
    frozen = False
    def integrate(start, stop):
        nonlocal serial, peak, max_host, last_model, fast_negative, slow_negative_high
        if stop <= start:
            return
        if proc.stdin is None or proc.stdout is None:
            raise RuntimeError('Plant pipes unavailable')
        proc.stdin.write(f'{(stop - start) * PERIOD:.17g} {jets[5]} {jets[6]} {zero} 0\n')
        proc.stdin.flush()
        model, codes = checked_plant_response(proc.stdout.readline())
        last_model = model
        peak = max(peak, abs(model[0]))
        emit('plant', 'simulated_vehicle', cycle=stop, interval_start=start, omega=model[:3],
             gimbals=model[3:], jets=[jets[5], jets[6]], zero=zero)
        for code in codes:
            serial += 1
            counters['generated'] += 1
            fast_negative += code == 19
            slow_negative_high += code == 3 and model[0] <= -4
            request = {'id': serial, 'code': code, 'origin': stop, 'available': tick,
                       'model_yaw_deg_s': model[0]}
            emit('generated', 'simulated_sensor', **request, disconnected=disconnected)
            if disconnected:
                counters['intentionally_disconnected'] += 1
            else:
                queue.append(request)
                max_host = max(max_host, len(queue))
    try:
        while True:
            if tick == END and not frozen:
                frozen = True
                emit('freeze', 'diagnostic', cycle=tick, state=state(lib), host_pending=len(queue),
                     inflight=inflight, model_state=last_model,
                     meaning='Plant evolution and new sensor production stop; subsequent tail is transport diagnostic, not equilibrium')
            if frozen and not queue and inflight is None:
                break
            if tick > END + 2000000:
                raise RuntimeError('Bounded transport drain timeout')
            while not frozen and index < len(schedule) and schedule[index][0] == tick:
                _, channel, value = schedule[index]
                index += 1
                accepted = lib.packet_write(channel, value)
                emit('input', 'diagnostic', cycle=tick, channel=channel, value=value, accepted=accepted)
                if accepted <= 0:
                    raise RuntimeError('Scheduled input rejected')
            if queue and inflight is None:
                request = queue[0]
                spacing = 14 if request['code'] in (17, 19) else 214
                if last_delivery is None or tick - last_delivery >= spacing:
                    request = queue.popleft()
                    accepted = lib.packet_write(128 | 0o32, request['code'])
                    emit('delivery', 'diagnostic_sensor_transport', cycle=tick, request=request,
                         accepted=accepted, host_pending=len(queue), tail=frozen)
                    if accepted <= 0:
                        counters['ringbuffer_rejects'] += 1
                        raise RuntimeError('Paced sensor ringbuffer rejection')
                    counters['delivered'] += 1
                    inflight = {**request, 'delivery': tick, 'consumed': False}
                    last_delivery = tick
                    max_age = max(max_age, tick - request['origin'])
            before = state(lib)
            count = 1 if inflight else CHUNK
            if not frozen:
                count = min(count, END - tick)
                if index < len(schedule):
                    count = min(count, schedule[index][0] - tick)
                if not checkpoint and tick < 2200000:
                    count = min(count, 2200000 - tick)
            if queue and inflight is None and last_delivery is not None:
                spacing = 14 if queue[0]['code'] in (17, 19) else 214
                count = min(count, max(1, last_delivery + spacing - tick))
            used = lib.step_chunk(count)
            if used == 0xffffffff:
                raise RuntimeError('Native output trace overflow')
            after = state(lib)
            if after['cycle'] != tick + count:
                raise RuntimeError('Wrapper CPU call and actual engine clock differ')
            if after['cdu'][1:] != [0, 0]:
                raise RuntimeError('Unsupported cross-axis CDU state')
            max_fifo = max(max_fifo, after['entries'])
            max_pending = max(max_pending, after['pending'])
            if inflight is not None:
                if not inflight['consumed'] and after['incoming'] < before['incoming']:
                    counters['consumed'] += 1
                    inflight['consumed'] = True
                    enqueued = after['pending'] == before['pending'] + 1
                    emit('consumption', 'diagnostic_sensor_transport', cycle=after['cycle'], request_id=inflight['id'],
                         code=inflight['code'], enqueued=enqueued, before=before, after=after, tail=frozen)
                    if not enqueued or after['head_code'] != inflight['code']:
                        counters['silent_fifo_drops'] += 1
                        raise RuntimeError('Actual FIFO did not enqueue paced signed/rate operation')
                    counters['enqueued'] += 1
                elif before['pending'] == 1 and after['pending'] == 0:
                    code = before['head_code']
                    if code != inflight['code'] or not inflight['consumed']:
                        raise RuntimeError('Actual FIFO application order/sign/rate mismatch')
                    expected_cdu = (expected_cdu + SIGNS[code]) % 32768
                    counters['applied'] += 1
                    emit('application', 'agc_diagnostic_readback', cycle=after['cycle'], code=code,
                         request_id=inflight['id'], delivery=inflight['delivery'], origin=inflight['origin'],
                         before=before, after=after, tail=frozen)
                    inflight = None
            if after['cdu'][0] != expected_cdu:
                raise RuntimeError('Actual counter delta is not accounted for by applied operations')
            outputs = []
            for i in range(used):
                word, at = lib.output_word(i), lib.output_cycle(i)
                channel, value = (word >> 16) & 65535, word & 32767
                check_jet(channel, value)
                emit('output', 'agc_output', cycle=at, channel=channel, value=value, tail=frozen)
                if channel in (5, 6, 10):
                    outputs.append((at, channel, value))
            prior_tick = tick
            tick += count
            if not frozen:
                cursor = prior_tick
                for at, channel, value in outputs + [(tick, -1, 0)]:
                    integrate(cursor, at)
                    if channel in jets:
                        jets[channel] = value
                    elif channel == 10:
                        zero = int(bool(value & 16))
                    cursor = at
                if tick == 2200000:
                    checkpoint = True
                    mode = lib.inspect_ram(0o1011)
                    imodes33 = lib.inspect_ram(0o1303)
                    emit('startup_checkpoint', 'agc_diagnostic_readback', cycle=tick, modreg=mode,
                         imodes33=imodes33, failreg=[lib.inspect_ram(a) for a in (0o375, 0o376, 0o377)],
                         state=after, v77='Complete key sequence delivered after P00 selection; no claim that its clear changed a previously set bit')
                    if mode != 0 or imodes33 & 0o40:
                        raise RuntimeError('Delayed P00/readiness checkpoint not established')
        settled = state(lib)
        emit('settled', 'diagnostic', cycle=tick, state=settled, host_pending=len(queue), inflight=inflight)
        # Continue logging genuine actuator output during the frozen diagnostic tail.
        used = lib.step_chunk(1000)
        for i in range(used):
            word = lib.output_word(i)
            channel, value = (word >> 16) & 65535, word & 32767
            check_jet(channel, value)
            emit('output', 'agc_output', cycle=lib.output_cycle(i), channel=channel, value=value, tail=True)
        quiet = state(lib)
        if quiet['cdu'] != settled['cdu'] or quiet['entries'] or quiet['pending'] or quiet['incoming']:
            raise RuntimeError('Counter/queues changed during1000-call quiet tail')
        if not counters['generated'] or not checkpoint:
            raise RuntimeError('No real model sensor motion/checkpoint')
        if not disconnected and len({counters[k] for k in ('generated', 'delivered', 'consumed', 'enqueued', 'applied')}) != 1:
            raise RuntimeError('Unaccounted sensor transport loss')
        emit('summary', 'diagnostic', selector=selector, feedback_disconnected=disconnected,
             counts=counters, peak_abs_yaw_deg_s=peak, max_host_queue=max_host,
             max_origin_to_delivery_calls=max_age, max_fifo_entries=max_fifo, max_fifo_pending=max_pending,
             generated_negative_fast=fast_negative, generated_slow_negative_at_high_rate=slow_negative_high,
             final_model=last_model, settled=settled, quiet=quiet, freeze_cycle=END,
             expected_modular_cdu=expected_cdu, state_writes=0)
    finally:
        if proc.stdin:
            proc.stdin.close()
        code = proc.wait(timeout=30)
        stderr.close()
        log.close()
        if code:
            raise RuntimeError('Tcl model exit ' + str(code))


def load_trace(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows or rows[0].get('ev') != 'initial' or rows[-1].get('ev') != 'summary':
        raise ValueError('Incomplete feedback trace')
    for row in rows:
        for key in ('omega', 'gimbals'):
            if key in row:
                if not all(math.isfinite(x) for x in row[key]) or row[key][1:] != [0.0, 0.0]:
                    raise ValueError('Non-finite or unsupported plant axis')
        if row['ev'] == 'output':
            check_jet(row['channel'], row['value'])
    return rows


def analyze(path):
    rows = load_trace(path)
    summary = {key: value for key, value in rows[-1].items() if key not in ('ev', 'category')}
    summary['raw_sha256'] = digest(path)
    summary['nonzero_rcs_words_octal'] = dict(collections.Counter(f'{r["value"]:05o}' for r in rows
         if r['ev'] == 'output' and r['channel'] == 6 and r['value'] and not r['tail']))
    summary['applied_codes'] = dict(collections.Counter(str(r['code']) for r in rows if r['ev'] == 'application'))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--tcl', required=True, type=Path)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--case', choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument('--library', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--server', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = destination(args.output)
    if args.case:
        worker(args, output)
        return
    output.mkdir(parents=True)
    preservation = verify_prior()
    write_json(output / 'preservation-before.json', preservation)
    if not preservation['ok']:
        raise RuntimeError('Earlier evidence differs')
    source = args.source.resolve()
    expected = json.loads((ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
    for relative, wanted in expected.items():
        if digest(source / relative) != wanted:
            raise RuntimeError('Pinned source mismatch: ' + relative)
    if digest(ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin') != ROPE_SHA256:
        raise RuntimeError('Authentic rope hash differs')
    for path in sorted(HERE.glob('*.py')):
        shutil.copyfile(path, output / ('executed-' + path.name))
    shutil.copyfile(PHASE5 / 'plant_server.tcl', output / 'executed-retained-plant_server.tcl')
    adapter = load_module('milestone3_selector_for_feedback', HERE.parent / 'model/fix_selector.py')
    corrected_module = output / 'corrected_imu.tcl'
    write_json(output / 'selector-audit.json', adapter.apply_selector(source, corrected_module))
    original_server = (PHASE5 / 'plant_server.tcl').read_text()
    marker = 'while {[gets stdin line] >= 0} {'
    if original_server.count(marker) != 1:
        raise ValueError('Retained plant server entry changed')
    corrected_server = output / 'corrected_server.tcl'
    corrected_server.write_text(original_server.replace(marker, f'source {{{corrected_module}}}\n' + marker, 1))
    engine = source / 'yaAGC'
    others = ['wasm.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c']
    commands = []
    compiler = shutil.which(args.cc)
    if compiler is None:
        raise RuntimeError('Missing C compiler')
    def run(argv, label):
        retained.run_command(argv, label, output, commands, timeout=240)
    run([compiler, '--version'], 'compiler-version')
    run([sys.executable, '--version'], 'python-version')
    library = output / 'engine.so'
    run([compiler, '-shared', '-fPIC', '-O2', '-I' + str(engine), M2CDU / 'inspect_bridge.c',
         PHASE5 / 'plant_bridge.c', *[engine / name for name in others], '-lm', '-o', library], 'build')
    write_json(output / 'inputs_source_hashes.json', {'source': expected,
        'participating': {str(path.relative_to(ROOT)): digest(path) for path in
        [Path(__file__), M2CDU / 'inspect_bridge.c', PHASE5 / 'plant_bridge.c', PHASE5 / 'plant_server.tcl',
         HERE.parent / 'model/fix_selector.py', ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin']},
        'binary_sha256': digest(library), 'tcl_executable_sha256': digest(args.tcl.resolve())})
    summaries = {}
    for case in CASES:
        server = PHASE5 / 'plant_server.tcl' if case == 'original_negative' else corrected_server
        run([sys.executable, Path(__file__), '--source', source, '--tcl', args.tcl.resolve(), '--output',
             output / (case + '.jsonl'), '--case', case, '--library', library, '--server', server], case)
        summaries[case] = analyze(output / (case + '.jsonl'))
    replay_equal = (output / 'corrected_negative.jsonl').read_bytes() == (output / 'corrected_repeat.jsonl').read_bytes()
    checks = {'exact_corrected_replay': replay_equal,
              'natural_negative_high_rate_observed': summaries['corrected_negative']['peak_abs_yaw_deg_s'] > 4
                   and summaries['corrected_negative']['generated_negative_fast'] > 0,
              'original_selector_slow_at_negative_high_rate': summaries['original_negative']['generated_slow_negative_at_high_rate'] > 0,
              'original_no_negative_fast': summaries['original_negative']['generated_negative_fast'] == 0,
              'feedback_changes_rcs': summaries['corrected_negative']['nonzero_rcs_words_octal'] != summaries['corrected_feedback_off']['nonzero_rcs_words_octal'],
              'disconnected_no_delivery': summaries['corrected_feedback_off']['counts']['delivered'] == 0,
              'disconnected_counter_zero': summaries['corrected_feedback_off']['quiet']['cdu'] == [0, 0, 0],
              'all_connected_settled_without_loss': all(summaries[case]['counts']['generated'] == summaries[case]['counts']['applied']
                    and summaries[case]['counts']['ringbuffer_rejects'] == 0 and summaries[case]['counts']['silent_fifo_drops'] == 0
                    for case in CASES if case != 'corrected_feedback_off')}
    write_json(output / 'summary.json', {'cases': summaries, 'checks': checks,
               'scope': 'Synthetic single-axis negative yaw, modern sensor-selector correction; no general-axis or landing claim'})
    write_json(output / 'preservation-after.json', verify_prior())
    if not all(checks.values()):
        raise RuntimeError('Feedback validation failed; retained actual measurements in summary.json')
    print(json.dumps({'checks': checks, 'cases': {name: {'counts': row['counts'], 'peak_abs_yaw_deg_s': row['peak_abs_yaw_deg_s'],
        'generated_negative_fast': row['generated_negative_fast'], 'max_host_queue': row['max_host_queue'],
        'max_origin_to_delivery_calls': row['max_origin_to_delivery_calls']} for name, row in summaries.items()}}, indent=2))


if __name__ == '__main__':
    main()
