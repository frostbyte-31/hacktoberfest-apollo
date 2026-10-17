#!/usr/bin/env python3
"""GPL-2.0-or-later. Native observational multi-axis AGC integration experiment."""
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
from common import ROOT, digest, load_module, write_json, verify_prior

M3 = load_module('phase7_retained_paced_orchestration', ROOT / 'docs/milestone3-evidence/feedback/run_validation.py')
PERIOD, CHUNK, END = M3.PERIOD, M3.CHUNK, M3.END
SIGNS, OPS = M3.SIGNS, M3.OPS
CASES = ('yaw', 'pitch', 'pitch_off', 'pitch_replay', 'combined', 'combined_off', 'combined_replay')
AXES = ('X', 'Y', 'Z')


def make_schedule(scenario):
    if scenario not in ('yaw', 'pitch', 'combined'):
        raise ValueError('Unsupported body-controller experiment')
    schedule = M3.make_schedule()
    if scenario == 'yaw':
        return schedule
    for row in schedule:
        if row[0] == 2500000:
            row[2] = 12286 if scenario == 'pitch' else 12278
        elif row[0] == 2500001 and scenario == 'pitch':
            row[1:] = [118, 20]
        elif row[0] == 2700000 and scenario == 'pitch':
            row[1:] = [118, 0]
    if scenario == 'combined':
        schedule.extend([[2500001, 118, 20], [2700000, 118, 0]])
    # Equal-timestamp normal packets are written before one CPU call, so the
    # original ringbuffer ChannelInput samples both RHC values without bias.
    return sorted(schedule)


class Engine:
    """Keep wire sequence IDs separate from observations of actual native bytes."""
    def __init__(self, library):
        self.lib = ctypes.CDLL(str(library))
        self.lib.p7_peek.restype = ctypes.c_uint32
        self.lib.p7_snapshot.argtypes = [ctypes.POINTER(ctypes.c_uint64)]
        self.lib.packet_write.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
        self.lib.step_chunk.restype = ctypes.c_uint32
        self.buffer = (ctypes.c_uint64 * 18)()
        self.lib.cpu_reset()
        raw = (ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()
        if digest(ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin') != M3.ROPE_SHA256:
            raise ValueError('Authentic retained rope hash differs')
        self.rope = (ctypes.c_ubyte * 73728).from_buffer_copy(raw)
        self.lib.set_fixed(self.rope)
        self.wire = collections.deque()
        self.serial = 0
        self.expected_cdu = [0, 0, 0]

    def snapshot(self):
        self.lib.p7_snapshot(self.buffer)
        values = list(self.buffer)
        return {'cycle': values[0], 'cdu': values[1:4], 'incoming': values[4], 'checker': values[5],
                'fifo': [{'entries': values[6 + 4*i], 'pending': values[7 + 4*i],
                          'head': values[8 + 4*i], 'deadline': values[9 + 4*i]} for i in range(3)]}

    def write(self, channel, value, request=None):
        status = self.lib.packet_write(channel, value)
        self.serial += 1
        row = {'wire_id': self.serial, 'channel': channel, 'value': value,
               'request_id': request['id'] if request else None,
               'axis': request['axis'] if request else None, 'accepted': status}
        if status > 0:
            self.wire.append(row)
        return row

    def step(self, count):
        before = self.snapshot()
        busy = before['incoming'] or any(f['pending'] for f in before['fifo'])
        if busy and count != 1:
            raise ValueError('Busy native transport must be observed per CPU call')
        prefix = []
        if count == 1:
            for index in range(before['incoming']):
                actual = self.lib.p7_peek(index)
                if actual == 0xffffffff:
                    raise ValueError('Malformed actual input ring packet')
                packet = {'mask': actual >> 31, 'channel': (actual >> 16) & 511, 'value': actual & 32767}
                prefix.append(packet)
                if not packet['mask'] and packet['channel'] & 128:
                    break
        used = self.lib.step_chunk(count)
        if used == 0xffffffff:
            raise ValueError('Native output observation overflow')
        after = self.snapshot()
        if after['cycle'] != before['cycle'] + count:
            raise ValueError('Actual engine clock differs from CPU-call count')
        if before['incoming'] - after['incoming'] != len(prefix):
            raise ValueError('Actual input consumption disagrees with parsed ring prefix')
        events = []
        counter_axis = None
        for actual in prefix:
            if not self.wire:
                raise ValueError('Actual native packet has no wire identity')
            expected = self.wire.popleft()
            if actual != {'mask': 0, 'channel': expected['channel'], 'value': expected['value']}:
                raise ValueError('Actual ring bytes differ from queued wire order/identity')
            event = {'ev': 'wire_consumption', 'cycle': after['cycle'], 'wire_id': expected['wire_id'],
                     'actual_packet': actual, 'request_id': expected['request_id'], 'axis': expected['axis']}
            events.append(event)
            if actual['channel'] & 128:
                axis = (actual['channel'] & 127) - 0o32
                if axis not in range(3) or actual['value'] not in SIGNS or expected['axis'] != axis:
                    raise ValueError('Unsupported actual counter packet or axis identity')
                if counter_axis is not None:
                    raise ValueError('Engine consumed two counter packets in one CPU call')
                counter_axis = axis
                prior, later = before['fifo'][axis], after['fifo'][axis]
                if prior['pending'] or later['pending'] != 1 or later['entries'] != 1 or later['head'] != actual['value']:
                    raise ValueError('Paced actual FIFO failed to enqueue signed/rate operation')
                events.append({'ev': 'enqueue', 'cycle': after['cycle'], 'axis': axis,
                    'request_id': expected['request_id'], 'wire_id': expected['wire_id'],
                    'code': later['head'], 'before': before, 'after': after})
        for axis in range(3):
            prior, later = before['fifo'][axis], after['fifo'][axis]
            if prior['pending'] == 1 and later['pending'] == 0:
                if counter_axis is not None:
                    raise ValueError('Counter packet input and FIFO service unexpectedly shared a CPU call')
                code = prior['head']
                if code not in SIGNS:
                    raise ValueError('Unknown actual FIFO application head')
                self.expected_cdu[axis] = (self.expected_cdu[axis] + SIGNS[code]) % 32768
                interval = 13 if code in (17, 19) else 213
                if later['deadline'] - prior['deadline'] != interval:
                    raise ValueError('Actual fresh-FIFO application rate mismatch')
                events.append({'ev': 'application', 'cycle': after['cycle'], 'axis': axis,
                               'code': code, 'before': before, 'after': after})
            elif axis != counter_axis and prior['pending'] != later['pending']:
                raise ValueError('Unaccounted native queue change')
            if later['entries'] > 1 or later['pending'] > 1:
                raise ValueError('Per-axis pacing capacity exceeded')
        if after['cdu'] != self.expected_cdu:
            raise ValueError('Native counters changed outside observed signed applications')
        outputs = []
        for index in range(used):
            word = self.lib.output_word(index)
            channel, value = (word >> 16) & 65535, word & 32767
            if channel in (5, 6) and value & ~255:
                raise ValueError('Unsupported jet-channel high bits')
            outputs.append((self.lib.output_cycle(index), channel, value))
        return before, after, events, outputs


def parse_response(response):
    if response.count('|') != 1:
        raise ValueError('Malformed phase7 model response: ' + response)
    raw, packets = response.strip().split('|')
    values = list(map(float, raw.split()))
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise ValueError('Non-finite or incomplete 3D telemetry')
    norm = sum(value * value for value in values[6:10])
    if abs(norm - 1) > 1e-9:
        raise ValueError('Orientation quaternion lost unit norm')
    if abs(values[5] if values[5] <= 180 else values[5] - 360) >= 80:
        raise ValueError('Unsupported middle-gimbal region')
    remainder = re.sub(r'\{(PCDU_FAST|MCDU_FAST|PCDU|MCDU) (\d+)\}', '', packets).strip()
    if remainder:
        raise ValueError('Unsupported sensor packet: ' + packets)
    parsed = []
    for name, address in re.findall(r'\{(PCDU_FAST|MCDU_FAST|PCDU|MCDU) (\d+)\}', packets):
        axis = int(address, 8) - 0o32
        if axis not in range(3):
            raise ValueError('Unsupported non-CDU sensor path')
        parsed.append((axis, OPS[name]))
    return {'omega': values[:3], 'gimbals': values[3:6], 'quaternion': values[6:10],
            'alpha_rad_s2': values[10:13], 'torque_Nm': values[13:16]}, parsed


def native_probe(library, output):
    engine = Engine(library)
    engine.step(200000)
    requests = [{'id': 1, 'axis': 0, 'code': 17}, {'id': 2, 'axis': 1, 'code': 19}, {'id': 3, 'axis': 2, 'code': 1}]
    with output.open('x') as stream:
        def emit(row): stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        emit({'ev': 'initial', 'classification': 'diagnostic_native_transport', 'state': engine.snapshot()})
        # Two legitimate normal input packets precede all three counters. The
        # first native call must consume both normals and exactly one counter.
        for channel, value in ((0o31, 0o67777), (0o167, 20)):
            emit({'ev': 'wire_delivery', **engine.write(channel, value)})
        for request in requests:
            emit({'ev': 'wire_delivery', **engine.write(128 | (0o32 + request['axis']), request['code'], request)})
        while engine.wire or any(f['pending'] for f in engine.snapshot()['fifo']):
            _, after, events, outputs = engine.step(1)
            if after['cycle'] > 201000:
                raise ValueError('Diagnostic native settlement timeout')
            for event in events:
                emit(event)
        settled = engine.snapshot()
        engine.step(1000)
        quiet = engine.snapshot()
        if quiet['cdu'] != [1, 32767, 1] or settled['cdu'] != quiet['cdu']:
            raise ValueError('Mixed-axis observed signed application failed')
        emit({'ev': 'summary', 'settled': settled, 'quiet': quiet, 'status': 'VERIFIED native transport only'})


def worker(args, output):
    scenario = args.case.split('_')[0]
    disconnected = args.case.endswith('_off')
    schedule = make_schedule(scenario)
    engine = Engine(args.library)
    log = output.open('x')
    stderr = output.with_suffix('.tcl.stderr').open('x')
    proc = subprocess.Popen([str(args.tcl), str(args.server), str(args.source), str(args.overlay)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    def emit(event, category, **values):
        log.write(json.dumps({'ev': event, 'category': category, **values}, separators=(',', ':'), allow_nan=False) + '\n')
    emit('initial', 'diagnostic', scenario=scenario, feedback_disconnected=disconnected,
         schedule=schedule, end=END, cycle_seconds=PERIOD, max_coupling_calls=CHUNK,
         initial_conditions='fresh CPU+model, zero physical rates, identity orientation, genuine delayed P00/V77 fixture',
         pacing='per CDU FIFO: one outstanding until actual application;214slow/14fast minimum delivery spacing',
         distinction='All3derivedgimbalsdelivered; validatedbodyinputaxesareyawandpitch; nofullthreeaxiscontrolclaim')
    queues = [collections.deque() for _ in range(3)]
    inflight = [None] * 3
    last_delivery = [None] * 3
    count_fields = ('generated', 'delivered', 'consumed', 'enqueued', 'applied', 'intentional_omissions')
    counts = [{key: 0 for key in count_fields} for _ in range(3)]
    tick = index = serial = 0
    jets = {5: 0, 6: 0}
    zero = 0
    next_coupling = CHUNK
    plant_cursor = 0
    frozen = checkpoint = False
    peak_omega = [0.0] * 3
    max_host = [0] * 3
    max_age = [0] * 3
    tail_applied = [0] * 3
    last_model = None
    def integrate(start, stop):
        nonlocal serial, last_model
        if stop <= start:
            return
        if proc.stdin is None or proc.stdout is None:
            raise ValueError('Missing model pipes')
        proc.stdin.write(f'{(stop - start) * PERIOD:.17g} {jets[5]} {jets[6]} {zero}\n')
        proc.stdin.flush()
        model, packets = parse_response(proc.stdout.readline())
        last_model = model
        for axis in range(3):
            peak_omega[axis] = max(peak_omega[axis], abs(model['omega'][axis]))
        emit('plant', 'simulated_vehicle', cycle=stop, interval_start=start,
             jets=[jets[5], jets[6]], zero=zero, **model)
        for axis, code in packets:
            serial += 1
            request = {'id': serial, 'axis': axis, 'counter': 0o32 + axis, 'code': code,
                       'origin': stop, 'available': tick}
            counts[axis]['generated'] += 1
            emit('generated', 'simulated_sensor', disconnected=disconnected, **request)
            if disconnected:
                counts[axis]['intentional_omissions'] += 1
            else:
                queues[axis].append(request)
                max_host[axis] = max(max_host[axis], len(queues[axis]))
    try:
        while True:
            if tick == END and not frozen:
                frozen = True
                emit('freeze', 'diagnostic', cycle=tick, state=engine.snapshot(),
                     host_pending=[len(q) for q in queues], inflight=inflight,
                     meaning='physical evolution/production frozen; genuine CPU tail only; noequilibriumclaim')
            if frozen and not any(queues) and not any(inflight):
                break
            if tick > END + 2000000:
                raise ValueError('Bounded three-FIFO diagnostic drain timeout')
            while not frozen and index < len(schedule) and schedule[index][0] == tick:
                _, channel, value = schedule[index]
                index += 1
                row = engine.write(channel, value)
                emit('input', 'diagnostic', cycle=tick, **row)
                if row['accepted'] <= 0:
                    raise ValueError('Genuine scheduled input rejected')
            for axis in range(3):
                if queues[axis] and inflight[axis] is None:
                    request = queues[axis][0]
                    spacing = 14 if request['code'] in (17, 19) else 214
                    if last_delivery[axis] is None or tick - last_delivery[axis] >= spacing:
                        request = queues[axis].popleft()
                        row = engine.write(128 | request['counter'], request['code'], request)
                        emit('delivery', 'diagnostic_sensor_transport', cycle=tick, request=request,
                             wire=row, host_pending=[len(q) for q in queues], tail=frozen)
                        if row['accepted'] <= 0:
                            raise ValueError('Paced multi-axis sensor ring rejection')
                        inflight[axis] = {**request, 'delivery': tick, 'wire_id': row['wire_id'], 'consumed': False}
                        last_delivery[axis] = tick
                        counts[axis]['delivered'] += 1
                        max_age[axis] = max(max_age[axis], tick - request['origin'])
            before = engine.snapshot()
            busy = before['incoming'] or any(inflight)
            step = 1 if busy else CHUNK
            if not frozen:
                step = min(step, END - tick, next_coupling - tick)
                if index < len(schedule):
                    step = min(step, schedule[index][0] - tick)
                if not checkpoint and tick < 2200000:
                    step = min(step, 2200000 - tick)
            for axis in range(3):
                if queues[axis] and inflight[axis] is None and last_delivery[axis] is not None:
                    spacing = 14 if queues[axis][0]['code'] in (17, 19) else 214
                    step = min(step, max(1, last_delivery[axis] + spacing - tick))
            before, after, events, outputs = engine.step(step)
            for event in events:
                axis = event.get('axis')
                kind = event.pop('ev')
                if kind == 'enqueue':
                    request = inflight[axis]
                    if request is None or request['id'] != event['request_id'] or request['consumed']:
                        raise ValueError('Actual enqueue request identity mismatch')
                    request['consumed'] = True
                    counts[axis]['consumed'] += 1
                    counts[axis]['enqueued'] += 1
                elif kind == 'application':
                    request = inflight[axis]
                    if request is None or not request['consumed'] or event['code'] != request['code']:
                        raise ValueError('Actual application lacks matching consumed request')
                    event.update(request_id=request['id'], delivery=request['delivery'], origin=request['origin'])
                    counts[axis]['applied'] += 1
                    tail_applied[axis] += frozen
                    inflight[axis] = None
                emit(kind, 'agc_diagnostic_readback' if kind == 'application' else 'diagnostic_sensor_transport', tail=frozen, **event)
            relevant = []
            for at, channel, value in outputs:
                emit('output', 'agc_output', cycle=at, channel=channel, value=value, tail=frozen)
                if channel in (5, 6, 10):
                    relevant.append((at, channel, value))
            tick += step
            if not frozen:
                for at, channel, value in relevant:
                    integrate(plant_cursor, at)
                    if channel in jets:
                        jets[channel] = value
                    else:
                        zero = int(bool(value & 16))
                    plant_cursor = at
                if tick == next_coupling or tick == END:
                    integrate(plant_cursor, tick)
                    plant_cursor = tick
                    next_coupling += CHUNK
                if tick == 2200000:
                    checkpoint = True
                    values = {'modreg': engine.lib.inspect_ram(0o1011),
                              'imodes30': engine.lib.inspect_ram(0o1302), 'imodes33': engine.lib.inspect_ram(0o1303),
                              'failreg': [engine.lib.inspect_ram(a) for a in (0o375, 0o376, 0o377)]}
                    emit('startup_checkpoint', 'agc_diagnostic_readback', cycle=tick, state=after, **values)
                    if values['modreg'] or any(values['failreg']) or (values['imodes30'] | values['imodes33']) & 0o40:
                        raise ValueError('Clean common IMU/DAP startup checkpoint failed')
        settled = engine.snapshot()
        emit('settled', 'diagnostic', state=settled, host_pending=[len(q) for q in queues], inflight=inflight)
        _, quiet, events, outputs = engine.step(1000)
        for at, channel, value in outputs:
            emit('output', 'agc_output', cycle=at, channel=channel, value=value, tail=True)
        if quiet['cdu'] != settled['cdu'] or quiet['incoming'] or any(f['pending'] for f in quiet['fifo']):
            raise ValueError('Quiet transport tail failed')
        for axis in range(3):
            if not disconnected and len({counts[axis][key] for key in ('generated', 'delivered', 'consumed', 'enqueued', 'applied')}) != 1:
                raise ValueError('Unaccounted per-axis sensor loss')
        if not checkpoint:
            raise ValueError('No observed startup checkpoint')
        emit('summary', 'diagnostic', scenario=scenario, feedback_disconnected=disconnected,
             counts=counts, settled=settled, quiet=quiet, final_model=last_model,
             peak_abs_omega_deg_s=peak_omega, max_host_queue=max_host, max_origin_to_delivery_calls=max_age,
             tail_applied=tail_applied, state_writes=0)
    finally:
        if proc.stdin:
            proc.stdin.close()
        code = proc.wait(timeout=30)
        stderr.close()
        log.close()
        if code:
            raise ValueError('Phase7 Tcl model failed: ' + str(code))


def run_command(argv, label, output, commands):
    argv = list(map(str, argv))
    row = {'argv': argv, 'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit': 'RUNNING'}
    commands.append(row)
    write_json(output / 'commands.json', commands)
    with (output / (label + '.stdout')).open('x') as stdout, (output / (label + '.stderr')).open('x') as stderr:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        row['pid'] = process.pid
        write_json(output / 'commands.json', commands)
        try:
            row['exit'] = process.wait(timeout=240)
        except BaseException as error:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            row['exit'], row['interruption'] = process.returncode, type(error).__name__
            raise
        finally:
            row['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            write_json(output / 'commands.json', commands)
    if row['exit'] != 0:
        raise RuntimeError(label + ' failed; inspect actual stderr')


def build(source, output, cc):
    engine = source / 'yaAGC'
    compiler = shutil.which(cc)
    if compiler is None:
        raise ValueError('C compiler unavailable')
    files = ('wasm.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c')
    return [compiler, '-shared', '-fPIC', '-O2', '-I' + str(engine),
            '-I' + str(ROOT / 'docs/milestone2-evidence/cdu'), HERE / 'inspect_axes.c',
            ROOT / 'docs/phase5-evidence/plant_bridge.c', *[engine / name for name in files], '-lm', '-o', output / 'engine.so']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tcl', type=Path)
    parser.add_argument('--runtime-manifest', type=Path)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--case', choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument('--library', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--server', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--overlay', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--native-probe', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--native-only', action='store_true', help='Build and verify mixed-axis native transport without Tcl/vehicle')
    args = parser.parse_args()
    output = M3.destination(args.output)
    if args.native_probe:
        native_probe(args.library, output)
        return
    if args.case:
        worker(args, output)
        return
    output.mkdir(parents=True)
    prior = verify_prior()
    write_json(output / 'preservation-before.json', prior)
    if not prior['ok']:
        raise ValueError('Retained evidence changed')
    source = args.source.resolve()
    expected = json.loads((ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
    for name, wanted in expected.items():
        if digest(source / name) != wanted:
            raise ValueError('Pinned source differs: ' + name)
    for path in HERE.glob('*.py'):
        shutil.copyfile(path, output / ('executed-' + path.name))
    shutil.copyfile(HERE / 'inspect_axes.c', output / 'executed-inspect_axes.c')
    commands = []
    run_command([shutil.which(args.cc), '--version'], 'compiler-version', output, commands)
    run_command([sys.executable, '--version'], 'python-version', output, commands)
    run_command(build(source, output, args.cc), 'build', output, commands)
    run_command([sys.executable, Path(__file__), '--source', source, '--native-probe', '--library', output / 'engine.so',
                 '--output', output / 'native-probe.jsonl'], 'native-probe', output, commands)
    write_json(output / 'inputs_source_hashes.json', {'upstream_revision': 'f577e3fd917866c59334e6cdd32504f09df76f60',
        'source_sha256': expected, 'binary_sha256': digest(output / 'engine.so'),
        'participating_sha256': {str(path.relative_to(ROOT)): digest(path) for path in [Path(__file__), HERE / 'inspect_axes.c',
            ROOT / 'docs/milestone2-evidence/cdu/inspect_bridge.c', ROOT / 'docs/phase5-evidence/plant_bridge.c']}})
    if args.native_only:
        write_json(output / 'summary.json', {'status': 'VERIFIED DIAGNOSTIC ONLY', 'capability': 'A retained prior; no new vehicle execution',
            'scope': 'Native parsed mixed-input/all3FIFO observation, not attitude-control capability'})
        return
    raise RuntimeError('Full vehicle runner awaiting source-locked physics adapter; native evidence retained, no multi-axis claim')


if __name__ == '__main__':
    main()
