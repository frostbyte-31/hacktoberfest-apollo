"""Strict reconciliation of raw live native observations, not replay telemetry."""
from collections import Counter, deque
import gzip
import hashlib
import json
import math
from pathlib import Path

from live_common import digest

SIGNS = {1: 1, 3: -1, 17: 1, 19: -1}
QUANTUM = 360 / 32768
KINDS = {'initial', 'input', 'pilot_command', 'neutral', 'generated', 'delivery',
         'wire_consumption', 'enqueue', 'application', 'output', 'plant',
         'execution_sample', 'actuator_decode', 'startup_checkpoint',
         'rhc_gate_observation', 'instrument_output', 'freeze', 'settled', 'summary'}


def load_trace(path):
    path = Path(path)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return raw, [json.loads(line) for line in raw.splitlines()]


def quaternion_gimbals(q):
    """Independent matrix decomposition of scalar-first body-to-stable q."""
    w, x, y, z = q
    c21 = 2 * (x*y + w*z)
    c22 = 1 - 2 * (x*x + z*z)
    c23 = 2 * (y*z - w*x)
    c31 = 2 * (x*z - w*y)
    c11 = 1 - 2 * (y*y + z*z)
    return [math.degrees(math.atan2(-c23, c22)) % 360,
            math.degrees(math.atan2(-c31, c11)) % 360,
            math.degrees(math.asin(max(-1, min(1, c21)))) % 360]


def wrapped_difference(a, b):
    return abs((a-b+180) % 360-180)


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Non-finite recorded value')
    if isinstance(value, list):
        for item in value:
            finite(item)
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)


def analyze_trace(path, yaw, pitch):
    raw, rows = load_trace(path)
    if not rows or rows[0].get('ev') != 'initial' or rows[-1].get('ev') != 'summary':
        raise ValueError('Incomplete actual live trace')
    if any(row.get('ev') not in KINDS for row in rows):
        raise ValueError('Unknown or failed live observation')
    finite(rows)
    summary = rows[-1]
    if summary.get('status') != 'VERIFIED bounded live session' or summary.get('state_writes') != 0:
        raise ValueError('Live session did not report verified unchanged flight-memory behavior')
    checkpoints = [r for r in rows if r['ev'] == 'startup_checkpoint']
    if len(checkpoints) != 1:
        raise ValueError('Missing unique actual startup checkpoint')
    ready = checkpoints[0]
    regs = ready['registers']
    if (ready['cycle'] != 2200000 or regs['modreg'] or any(regs['failreg']) or
            (regs['imodes30'] | regs['imodes33']) & 0o40 or not regs['dapbools'] & 4):
        raise ValueError('Original readiness conditions were not observed')
    commands = [r for r in rows if r['ev'] == 'pilot_command']
    if len(commands) != 1:
        raise ValueError('Expected exactly one documented pilot command')
    command = commands[0]
    expected_word = 12287 - {-1: 8, 0: 0, 1: 4}[yaw] - {-1: 2, 0: 0, 1: 1}[pitch]
    encode = lambda sign: 20 if sign > 0 else 32747 if sign < 0 else 0
    if (command['cycle'], command['yaw'], command['pitch'], command['channel031'],
            command['yaw_port0167'], command['pitch_port0166']) != (
            2500000, yaw, pitch, expected_word, encode(yaw), encode(pitch)):
        raise ValueError('Authentic signed RHC input differs from the predeclared experiment')
    if command['neutral_at'] != 2585333:
        raise ValueError('Pilot command lease differs from the predeclared bound')
    neutral = [r for r in rows if r['ev'] == 'neutral']
    auto = [r for r in neutral if r['origin'] == 'automatic bounded pulse neutral']
    if len(auto) != 1 or auto[0]['cycle'] != command['neutral_at']:
        raise ValueError('Automatic authentic neutral input was not made at its exact deadline')
    for r in neutral:
        if any(r[key] for key in ('yaw', 'pitch', 'yaw_port0167', 'pitch_port0166')) or r['channel031'] != 28671:
            raise ValueError('Neutral event is not source-supported neutral RHC input')

    generated, delivered, consumed, enqueued, applied = {}, {}, {}, {}, {}
    wire = deque()
    outstanding = [None] * 3
    last_delivery = [None] * 3
    expected_cdu = [0, 0, 0]
    counted = [Counter() for _ in range(3)]
    outputs, plants, gate_reads = [], [], []
    for r in rows:
        kind = r['ev']
        if kind == 'input':
            if r['accepted'] <= 0 or r['request_id'] is not None or r['axis'] is not None:
                raise ValueError('Rejected or mislabeled normal input')
            wire.append({k: r[k] for k in ('wire_id', 'channel', 'value', 'request_id', 'axis')})
        elif kind == 'generated':
            identity, axis, code = r['id'], r['axis'], r['code']
            if identity in generated or axis not in range(3) or code not in SIGNS or r['counter'] != 0o32+axis:
                raise ValueError('Invalid generated sensor operation')
            if not 0 <= r['available']-r['origin'] <= 853:
                raise ValueError('Sensor availability exceeds original coupling bound')
            generated[identity] = r
            counted[axis]['generated'] += 1
        elif kind == 'delivery':
            request, w = r['request'], r['wire']
            identity, axis = request['id'], request['axis']
            if identity not in generated or identity in delivered or outstanding[axis] is not None:
                raise ValueError('Overlapping or unaccounted sensor delivery')
            if any(request[k] != generated[identity][k] for k in ('axis', 'counter', 'code', 'origin', 'available')):
                raise ValueError('Delivered request differs from generated sensor operation')
            if w['accepted'] <= 0 or (w['channel'], w['value']) != (128 | request['counter'], request['code']):
                raise ValueError('Actual sensor wire bytes differ from generated operation')
            spacing = 14 if request['code'] in (17, 19) else 214
            if r['cycle'] < request['available'] or (last_delivery[axis] is not None and r['cycle']-last_delivery[axis] < spacing):
                raise ValueError('Actual per-axis delivery pacing violated')
            last_delivery[axis] = r['cycle']
            outstanding[axis] = identity
            delivered[identity] = r
            counted[axis]['delivered'] += 1
            wire.append({k: w[k] for k in ('wire_id', 'channel', 'value', 'request_id', 'axis')})
        elif kind == 'wire_consumption':
            if not wire:
                raise ValueError('Actual consumed packet has no matching delivered identity')
            w = wire.popleft()
            if r['wire_id'] != w['wire_id'] or r['actual_packet'] != {'mask': 0, 'channel': w['channel'], 'value': w['value']}:
                raise ValueError('Actual parsed native ring packet/order differs from delivered bytes')
            if w['request_id'] is not None:
                consumed[w['request_id']] = r
                counted[w['axis']]['consumed'] += 1
        elif kind == 'enqueue':
            identity, axis = r['request_id'], r['axis']
            if outstanding[axis] != identity or identity not in consumed or identity in enqueued:
                raise ValueError('Native FIFO enqueue lacks a consumed request')
            before, after = r['before']['fifo'][axis], r['after']['fifo'][axis]
            if before['pending'] or after['pending'] != 1 or after['entries'] != 1 or after['head'] != generated[identity]['code']:
                raise ValueError('Actual FIFO head/sign/rate does not match the generated request')
            enqueued[identity] = r
            counted[axis]['enqueued'] += 1
        elif kind == 'application':
            identity, axis = r['request_id'], r['axis']
            if outstanding[axis] != identity or identity not in enqueued or identity in applied:
                raise ValueError('Native application lacks the matching actual FIFO enqueue')
            before, after = r['before'], r['after']
            code = generated[identity]['code']
            if before['cdu'] != expected_cdu or before['fifo'][axis]['head'] != code or r['code'] != code:
                raise ValueError('Actual application sign/counter predecessor mismatch')
            expected_cdu[axis] = (expected_cdu[axis]+SIGNS[code]) % 32768
            if after['cdu'] != expected_cdu or after['fifo'][axis]['pending']:
                raise ValueError('Actual applied native counter delta differs from the signed sensor operation')
            if after['fifo'][axis]['deadline']-before['fifo'][axis]['deadline'] != (13 if code in (17, 19) else 213):
                raise ValueError('Actual native FIFO rate deadline mismatch')
            outstanding[axis] = None
            applied[identity] = r
            counted[axis]['applied'] += 1
        elif kind == 'output':
            if r['category'] != 'agc_output':
                raise ValueError('An output lacks authentic AGC provenance')
            if r['channel'] in (5, 6):
                if not 0 <= r['value'] <= 255:
                    raise ValueError('Unsupported actual RCS bits')
                outputs.append(r)
        elif kind == 'plant':
            if abs(sum(v*v for v in r['quaternion'])-1) > 1e-9:
                raise ValueError('Actual modeled quaternion is not normalized')
            if any(wrapped_difference(a, b) > 1e-8 for a, b in zip(quaternion_gimbals(r['quaternion']), r['gimbals'])):
                raise ValueError('Reported model gimbals differ from its authoritative quaternion')
            plants.append(r)
        elif kind == 'rhc_gate_observation':
            if r['channel013'] & 0o600 != 0o600 or r['readback_cycle'] < r['cycle']:
                raise ValueError('RHC readback lacks the actual original gated-read output')
            gate_reads.append(r)
        elif kind == 'instrument_output' and r.get('unsupported'):
            raise ValueError('Unsupported active instrument actuation was produced')
    if wire or any(v is not None for v in outstanding):
        raise ValueError('Trace leaves actual delivered input or sensor operations outstanding')
    if set(generated) != set(delivered) or set(generated) != set(consumed) or set(generated) != set(enqueued) or set(generated) != set(applied):
        raise ValueError('Generated, actual delivered/consumed/enqueued/applied sensor identities differ')
    for axis in range(3):
        actual = {key: counted[axis][key] for key in ('generated', 'delivered', 'consumed', 'enqueued', 'applied')}
        if actual != summary['counts'][axis] or len(set(actual.values())) != 1:
            raise ValueError('Claimed per-axis counts differ from raw actual observations')
    settled, quiet = summary['settled'], summary['quiet']
    if settled['cdu'] != expected_cdu or quiet['cdu'] != expected_cdu or quiet['cycle']-settled['cycle'] != 1000:
        raise ValueError('Native counter state or quiet-tail duration mismatch')
    if any(state['incoming'] or any(f['entries'] or f['pending'] for f in state['fifo']) for state in (settled, quiet)):
        raise ValueError('Actual input ring or native CDU FIFOs remain nonempty')
    angles = quaternion_gimbals(summary['final_model']['quaternion'])
    residual = [wrapped_difference(count*QUANTUM, angle) for count, angle in zip(quiet['cdu'], angles)]
    if max(residual) > QUANTUM+1e-8:
        raise ValueError('Settled actual CDU readings disagree with quaternion-derived gimbals')
    freezes = [r for r in rows if r['ev'] == 'freeze']
    if len(freezes) != 1 or freezes[0]['cycle'] != 3200000:
        raise ValueError('Physical production did not stop at the predeclared horizon')
    active_plants = [r for r in plants if command['cycle'] <= r['cycle'] < command['neutral_at']]
    if not active_plants:
        raise ValueError('No actual modeled response during the commanded interval')
    active_gate = [r for r in gate_reads if command['cycle'] < r['cycle'] < command['neutral_at']]
    signed_response = []
    for axis, sign, channel, field in ((0, yaw, 6, 'rhc_yaw_counter0043'), (1, pitch, 5, 'rhc_pitch_counter0042')):
        if not sign:
            signed_response.append(None)
            continue
        if not any(r['channel'] == channel and r['value'] and command['cycle'] < r['cycle'] < command['neutral_at'] for r in outputs):
            raise ValueError('No actual original RCS output on the commanded control path')
        projected = max(sign*r['omega'][axis] for r in active_plants)
        if projected <= .05 or not counted[axis]['applied']:
            raise ValueError('Signed body response or actual corresponding CDU feedback was not observed')
        if not any(r[field] == encode(sign) for r in active_gate):
            raise ValueError('Original gated RHC counter copy was not observed with the commanded signed count')
        signed_response.append(projected)
    return {'status': 'VERIFIED', 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
            'rows': len(rows), 'counts': summary['counts'], 'final_cdu': quiet['cdu'],
            'final_model': summary['final_model'], 'settled_cycle': settled['cycle'], 'quiet_cycle': quiet['cycle'],
            'max_signed_body_response_during_hold_deg_s': signed_response,
            'settled_cdu_quaternion_residual_deg': residual,
            'actual_rcs_packet_count': len(outputs), 'actual_rhc_gate_observations': len(gate_reads),
            'command': command, 'automatic_neutral': auto[0]}


def analyze_directory(path, require_full=True):
    from run_validation import CASES
    path = Path(path)
    found = [name for name in CASES if (path / name / 'trace.jsonl').exists() or (path / name / 'trace.jsonl.gz').exists()]
    if not found or require_full and found != list(CASES):
        raise ValueError('Missing expected fresh live cases')
    cases = {}
    for name in found:
        trace = path / name / 'trace.jsonl'
        if not trace.exists():
            trace = trace.with_suffix('.jsonl.gz')
        cases[name] = analyze_trace(trace, *CASES[name])
    if require_full:
        identical = cases['combined']['raw_sha256'] == cases['combined_replay']['raw_sha256']
        if not identical:
            raise ValueError('Identical cycle-scheduled live commands did not reproduce complete raw bytes')
    else:
        identical = None
    return {'status': 'VERIFIED', 'cases': cases, 'combined_replay_byte_identical': identical,
            'limits': 'Bounded live input and feedback; no new disconnected experiment, full three-axis or descent claim'}
