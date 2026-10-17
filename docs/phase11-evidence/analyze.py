#!/usr/bin/env python3
"""Read-only checks of retained native PIPA/nav traces; supplies no AGC inputs."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROPE_SHA = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
MCT = Fraction(12, 1024000)
PIPA_COUNTERS = (0o37, 0o40, 0o41)
MASK = 0o77777
VELOCITY_LSB_M_S = Fraction(12800, 2**28)


def read_json(path):
    return json.loads(Path(path).read_text())


def signed(word):
    if type(word) is not int or not 0 <= word <= MASK:
        raise ValueError('Expected one original 15-bit word')
    return -(word ^ MASK) if word & 0o40000 else word


def dp(words):
    if len(words) != 2:
        raise ValueError('Expected two original DP words')
    return Fraction(signed(words[0])*16384 + signed(words[1]), 2**28)


def vector(words, scale, factor=1):
    if len(words) != 6:
        raise ValueError('Expected six-word original vector')
    return [float(dp(words[i:i+2])*2**scale*factor) for i in (0, 2, 4)]


def native_dir(path):
    path = Path(path)
    return path/'native' if (path/'native').is_dir() else path


def load_run(path):
    path = native_dir(path)
    trace = path/'trace.jsonl'
    data = trace.read_bytes() if trace.exists() else gzip.decompress((path/'trace.jsonl.gz').read_bytes())
    rows = [json.loads(line) for line in data.splitlines()]
    if not rows or rows[0].get('ev') != 'initial' or rows[-1].get('ev') != 'finish':
        raise ValueError('A complete initial/finish native trace is required')
    if any(r['ev'] in ('failure', 'wait_timeout') for r in rows):
        raise ValueError('Failed native experiment, not an accepted trace')
    if any(type(r.get('cycle')) is not int for r in rows) or any(a['cycle'] > b['cycle'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Native observations must have monotonic integer CPU cycles')
    mapping = read_json(path/'observer-map.json')
    indices = mapping['snapshot_addresses']
    if any(len(r['snapshot_words']) != len(indices) for r in rows if 'snapshot_words' in r):
        raise ValueError('Native observer width differs from its map')
    seal = read_json(path/'trace-sha256.json')
    digest = hashlib.sha256(data).hexdigest()
    if seal != {'sha256': digest, 'bytes': len(data)}:
        raise ValueError('Native raw trace checksum differs from capture manifest')
    return path, rows, mapping, digest, len(data)


def words(row, mapping, name, count=1):
    address = mapping['addresses'][name]
    indices = mapping['snapshot_addresses']
    return [row['snapshot_words'][indices.index(address+i)] for i in range(count)]


def one(rows, event):
    found = [r for r in rows if r['ev'] == event]
    if len(found) != 1:
        raise ValueError('Expected one '+event+' observation')
    return found[0]


def counter_next(word, operation):
    # Source contract: yaAGC CounterPINC/CounterMINC, signed-zero transitions.
    if operation == 0:
        value = 0 if word == 0o37777 else (word+1) & MASK
        return 1 if value == 0 and word != 0o37777 else value
    if operation == 2:
        value = MASK if word == 0o40000 else (word-1) & MASK
        return MASK-1 if value == MASK and word != 0o40000 else value
    raise ValueError('A PIPA pulse must be PINC or MINC')


def analyze_run(directory):
    path, rows, mapping, digest, byte_count = load_run(directory)
    start, plan, settled = (one(rows, name) for name in ('sensor_start', 'sensor_plan', 'settled'))
    review = one(rows, 'phase10_review')
    case = start['case']
    after = [r for r in rows if r['cycle'] >= start['cycle']]
    cp = [r for r in rows if r['ev'] == 'checkpoint']
    routines = Counter(r['routine'] for r in cp)
    interval = plan['interval']
    force = [sum(plan['ref_to_stable'][i][j]*plan['force_ref_m_s2'][j] for j in range(3)) for i in range(3)]
    inertial_specific_force = [a-g for a,g in zip(plan['total_acceleration_ref_m_s2'],plan['gravity_ref_m_s2'])]
    duration = float((plan['end_cycle']-plan['start_cycle'])*MCT)
    expected_dv = [f*duration for f in force]
    expected_counts = [math.trunc(value/.01) for value in expected_dv]
    # Pinned listing: KPIP1 = 33,2021 octal (bank27 decimal, offset17).
    # wasm.c:62–88 loads rope words big-endian then removes the parity bit;
    # physical banks >=4 retain the same file-bank number.
    rope = (ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()
    if hashlib.sha256(rope).hexdigest() != ROPE_SHA:
        raise ValueError('Original rope changed before independent arithmetic check')
    offset = 2*(27*1024+17)
    kpip1_words = [int.from_bytes(rope[offset+i:offset+i+2],'big') >> 1 for i in (0,2)]
    kpip1 = dp(kpip1_words)
    delivered = [r for r in after if r['ev'] == 'pipa_delivered']
    packets = [r for r in after if r['ev'] == 'input' and r['channel'] & 0x80]
    count_by_axis = [sum((1 if r['operation'] == 0 else -1) for r in delivered if r['axis'] == axis) for axis in 'XYZ']
    checks = {
        'unchanged_rope_and_no_flight_memory_writes': rows[0].get('rope_sha256') == ROPE_SHA and rows[0].get('original_ram_writes') == 0,
        'phase10_original_roots_and_review_preserved': routines['ROOTSTOR_RESULT'] == routines['QUADGUID'] == 9 and review['state']['modreg'] == 63 and review['state']['display']['VERB'] == '06' and review['state']['display']['NOUN'] == '61',
        'original_p51_alignment_matrix_remains_valid': review['state']['refsmflg'] and settled['state']['refsmflg'] and settled['state']['refsmmat'] == review['state']['refsmmat'],
        'original_p47_selected_and_navigation_scheduled': all(routines[n] for n in ('P47LM', 'STARTP47', 'PREREAD', 'READACCS', 'PIPASR', 'SERVICER', 'COPYCYCL', 'CALCN83', 'SERVEXIT')) and settled['state']['modreg'] == 47,
        'original_calcrvg_interpreter_dispatch_observed': routines['CALCRVG'] >= 5,
        'p47_uses_reference_navigation_route': all(words(r, mapping, 'FLAGWRD6')[0] & (1 << 7) == 0 for r in cp if r['routine'] == 'SERVICER'),
        'original_display_is_delta_velocity_n83': settled['state']['display']['PROG'] == '47' and settled['state']['display']['VERB'] == '16' and settled['state']['display']['NOUN'] == '83',
        'no_new_program_alarms': settled['state']['failreg'] == review['state']['failreg'] == [0o1520, 0, 0],
        'sensor_si_force_and_duration_match_independent_transform': abs(duration-6) < 1e-12 and all(abs(a-b) < 1e-12 for a,b in zip(force,interval['specific_force_stable_m_s2'])) and all(abs(a-b) < 1e-12 for a,b in zip(expected_dv, interval['delta_v_stable_m_s'])),
        'specific_force_subtracts_documented_nonzero_gravity': max(map(abs,plan['gravity_ref_m_s2'])) > 1 and all(abs(a-b) < 1e-12 for a,b in zip(inertial_specific_force,plan['force_ref_m_s2'])),
        'quantized_count_and_residual_match_physical_integral': expected_counts == interval['generated_counts'] and all(abs(dv-count*.01-residual) < 1e-12 and abs(residual) < .01 for dv,count,residual in zip(expected_dv,expected_counts,interval['remainder_m_s'])),
        'source_counter_addresses': [mapping['addresses'][n] for n in ('PIPAX','PIPAY','PIPAZ')] == list(PIPA_COUNTERS),
        'input_packets_match_recorded_hardware_events': [(r['cycle'],r['channel'],r['value']) for r in packets] == [(r['cycle'],0x80|r['counter'],r['operation']) for r in delivered] and all(r['accepted_bytes'] == 4 for r in packets),
        'source_operation_sign_and_axis_mapping': all(r['counter'] == PIPA_COUNTERS['XYZ'.index(r['axis'])] and r['operation'] in (0,2) for r in delivered),
        'disconnection_or_connection_observed': (not delivered and interval['suppressed_counts'] == expected_counts) if case == 'disconnected' else (count_by_axis == expected_counts and interval['suppressed_counts'] == [0,0,0]),
        'no_engine_on_commands_during_sensor_interval': all(not (r['value'] & (1 << 12)) for r in after if r['ev'] == 'output' and r['channel'] == 0o11),
        'only_dsky_and_source_pipa_hardware_inputs_after_review': all(r['channel'] in (0o15,0o237,0o240,0o241) for r in rows if r['ev'] == 'input' and r['cycle'] > review['cycle']) and any(r['ev'] == 'key_sequence' and r['text'] == 'V37E47E' for r in rows),
    }
    requested = [(r['cycle'],r['axis'],r['counter'],r['operation']) for r in interval['events']]
    actual = [(r['requested_cycle'],r['axis'],r['counter'],r['operation']) for r in delivered]
    checks['exact_requested_event_schedule_retained'] = actual == requested and all(r['cycle'] == r['requested_cycle'] for r in delivered)
    previous = {PIPA_COUNTERS[i]: start['navigation']['PIPA'+'XYZ'[i]][0] for i in range(3)}
    pending, hardware_responses, other_counter_changes = {}, [], []
    for row in after:
        if row['ev'] == 'input' and row['channel'] & 0x80:
            address = row['channel'] & 0x7f
            if address in pending:
                raise ValueError('More than one outstanding hardware pulse for the same counter')
            pending[address] = (row, previous[address])
        elif row['ev'] == 'transition' and row['address'] in previous:
            address, value = row['address'], row['value']
            if address in pending:
                pulse, before = pending.pop(address)
                expected = counter_next(before, pulse['value'])
                hardware_responses.append({'requested_cycle':pulse['cycle'], 'observed_cycle':row['cycle'], 'counter':address,
                    'before_octal':format(before,'05o'), 'after_octal':format(value,'05o'), 'operation':pulse['value'],
                    'correct': value == expected and row['cycle'] == pulse['cycle']+1})
            else:
                other_counter_changes.append({'cycle':row['cycle'],'counter':address,'value_octal':format(value,'05o')})
            previous[address] = value
    checks['every_pulse_has_genuine_next_cycle_counter_response'] = len(hardware_responses) == len(delivered) and not pending and all(r['correct'] for r in hardware_responses)
    raw_reads = [r for r in after if r['ev'] == 'checkpoint' and r['routine'] == 'SERVICER']
    consumed_counts = [sum(signed(words(r,mapping,'DELV',6)[2*i]) for r in raw_reads) for i in range(3)]
    checks['original_servicer_consumes_exact_delivered_counts'] = bool(raw_reads) and consumed_counts == count_by_axis and all(not any(signed(w) for w in words(r,mapping,'DELV',6)[1::2]) for r in raw_reads)
    checks['original_reader_resets_genuine_counters_to_signed_zero'] = all(signed(settled['navigation']['PIPA'+axis][0]) == 0 for axis in 'XYZ')
    nav = []
    for entry in (r for r in cp if r['routine'] == 'CALCN83' and r['cycle'] >= start['cycle']):
        exit_row = next((r for r in cp if r['routine'] == 'SERVEXIT' and r['cycle'] > entry['cycle']), None)
        if exit_row is None:
            continue  # A bounded horizon may stop during the final original job.
        before = vector(words(entry,mapping,'DELVCTL',6),7,100)
        delta = vector(words(entry,mapping,'DELVREF',6),7,100)
        accumulated = vector(words(exit_row,mapping,'DELVCTL',6),7,100)
        reader = next((r for r in reversed(raw_reads) if r['cycle'] < entry['cycle']), None)
        if reader is None:
            # The first in-flight job may have read just before sensor_start.
            reader = next((r for r in reversed(cp) if r['routine'] == 'SERVICER' and r['cycle'] < entry['cycle']), None)
        raw_counts = [signed(words(reader,mapping,'DELV',6)[2*i]) for i in range(3)]
        matrix = [2*dp(words(entry,mapping,'REFSMMAT',18)[i:i+2]) for i in range(0,18,2)]
        expected_delta = [float(sum(Fraction(raw_counts[i],16384)*matrix[i*3+j]*kpip1*12800 for i in range(3))) for j in range(3)]
        nav.append({'cycle':entry['cycle'], 'completed_cycle':exit_row['cycle'],
            'PIPTIME_cs':float(dp(words(entry,mapping,'PIPTIME',2))*2**28),
            'PGUIDE_cs':float(dp(words(entry,mapping,'PGUIDE',2))*2**28),
            'RN_m':vector(words(entry,mapping,'RN',6),29), 'VN_m_s':vector(words(entry,mapping,'VN',6),7,100),
            'DELVREF_m_s':delta, 'DELVCTL_before_m_s':before, 'DELVCTL_after_m_s':accumulated,
            'DELVIMU_m_s':vector(words(exit_row,mapping,'DELVIMU',6),7,100),
            'raw_consumed_counts':raw_counts, 'independent_rope_scaled_DELVREF_m_s':expected_delta,
            'original_transform_error_m_s':[a-b for a,b in zip(delta,expected_delta)],
            'original_accumulator_error_m_s':[c-a-b for a,b,c in zip(before,delta,accumulated)]})
    checks['original_calcn83_accumulates_reference_delta_v'] = bool(nav) and all(max(map(abs,r['original_accumulator_error_m_s'])) <= 2*12800/2**28 for r in nav)
    checks['original_read_period_is_two_seconds'] = bool(nav) and all(abs(r['PGUIDE_cs']-200) <= 1 for r in nav)
    checks['original_delta_v_transform_matches_rope_scaled_sensor_counts'] = bool(nav) and all(max(map(abs,r['original_transform_error_m_s'])) <= 2*float(VELOCITY_LSB_M_S) for r in nav)
    checks['navigation_rn_vn_copy_agrees_with_calculated_values'] = all(words(r,mapping,'RN',6) == words(r,mapping,'RN1',6) and words(r,mapping,'VN',6) == words(r,mapping,'VN1',6) for r in cp if r['routine'] == 'CALCN83' and r['cycle'] >= start['cycle'])
    checks['zero_bias_and_scale_error_are_observed_not_injected'] = not any(signed(w) for n in ('PIPASCF','PIPABIAS') for w in settled['navigation'][n])
    geometry = read_json(path/'configuration.json')['phase10']['synthetic_geometry']
    checks['navigation_state_stays_outside_lunar_reference_bound'] = bool(nav) and all(math.sqrt(sum(x*x for x in sample['RN_m'])) >= geometry['lunar_reference_radius_m'] for sample in nav)
    for name in ('preservation-before','preservation-after'):
        p = read_json(path/(name+'.json'))
        checks[name+'_all_prior_files_unchanged'] = bool(p['files_checked']) and not p['changed_or_missing']
    source = read_json(path/'source-integrity/after-execution.json')
    checks['pinned_original_source_files_unchanged'] = bool(source['files_checked']) and not source['changed_or_missing']
    original = read_json(path/'original-preservation-after.json')
    checks['original_baseline_integrity_guard_unchanged'] = original.get('ok') is True
    return {'case':case,'all_pass':all(checks.values()),'checks':checks,'raw_sha256':digest,'raw_bytes':byte_count,
            'checkpoint_counts':dict(routines), 'expected_specific_force_SM_m_s2':force,
            'independent_expected_delta_v_SM_m_s':expected_dv,'expected_quantized_counts':expected_counts,
            'delivered_signed_counts':count_by_axis,'original_consumed_signed_counts':consumed_counts,
            'native_counter_responses':hardware_responses,'other_counter_changes':other_counter_changes,
            'navigation_samples':nav,'start_navigation':start['navigation'],'settled_navigation':settled['navigation'],
            'final_state':settled['state'], 'source_ref_to_stable':plan['ref_to_stable'],
            'original_KPIP1':{'rope_address_octal':'33,2021','words_octal':[format(w,'05o') for w in kpip1_words],'fraction':float(kpip1),'nominal_decimal':.0128},
            'velocity_DP_LSB_m_s':float(VELOCITY_LSB_M_S),
            'observation_horizon_s':float((settled['cycle']-start['cycle'])*MCT),
            'synthetic_geometry':geometry}


def experiment(directory):
    directory = Path(directory)
    runs = {name:analyze_run(directory/name) for name in ('zero','positive','negative','disconnected','repeat')}
    zero = runs['zero']
    comparisons = {'positive_repeat_trace_byte_identical':runs['positive']['raw_sha256'] == runs['repeat']['raw_sha256']}
    diagnostics = {}
    zero_by_time = {r['PIPTIME_cs']:r for r in zero['navigation_samples']}
    for name in ('positive','negative','disconnected'):
        run = runs[name]
        matched = [(row,zero_by_time[row['PIPTIME_cs']]) for row in run['navigation_samples'] if row['PIPTIME_cs'] in zero_by_time]
        comparisons[name+'_has_matched_original_piptime_samples'] = len(matched) >= 3
        if not matched:
            continue
        measured, control = matched[-1]
        velocity = [a-b for a,b in zip(measured['VN_m_s'],control['VN_m_s'])]
        position = [a-b for a,b in zip(measured['RN_m'],control['RN_m'])]
        expected_stable = run['delivered_signed_counts']
        rotation = run['source_ref_to_stable']
        expected = [sum(rotation[i][j]*expected_stable[i]*.01 for i in range(3)) for j in range(3)]
        error = [a-b for a,b in zip(velocity,expected)]
        # For g=-mu*r/|r|^3, ||Dg|| <= 2mu/r_min^3. Use the declared
        # lunar reference radius as a conservative lower radius, and the
        # full .5*f*t^2 displacement bound throughout the bounded horizon.
        # Four velocity-DP LSB per original two-second sample additionally
        # allow the independently checked transform plus state arithmetic.
        geometry = run['synthetic_geometry']
        horizon = run['observation_horizon_s']
        force_magnitude = math.sqrt(sum(f*f for f in run['expected_specific_force_SM_m_s2']))
        displacement_bound = .5*force_magnitude*horizon*horizon
        gravity_bound = 2*geometry['mu_m3_s2']/geometry['lunar_reference_radius_m']**3*displacement_bound*horizon
        rounding_bound = 4*float(VELOCITY_LSB_M_S)*len(matched)
        velocity_tolerance = gravity_bound+rounding_bound
        diagnostics[name] = {'matched_PIPTIME_cs':measured['PIPTIME_cs'],'matched_samples':len(matched),
            'original_VN_difference_from_zero_m_s':velocity,'original_RN_difference_from_zero_m':position,
            'independent_expected_pipa_delta_v_REF_m_s':expected,'velocity_error_m_s':error,
            'tolerance_m_s':velocity_tolerance,'gravity_variation_bound_m_s':gravity_bound,'DP_rounding_allowance_m_s':rounding_bound,
            'tolerance_reason':'2*mu/r_min^3 times .5*|f|*t^2 displacement bound times bounded horizon, plus four velocity-DP LSB per original two-second sample; comparison uses actual integer pulse count, not unquantized force'}
        comparisons[name+'_original_velocity_matches_pipa_contribution'] = max(map(abs,error)) <= velocity_tolerance
        comparisons[name+'_original_position_response_is_causal'] = max(map(abs,position)) > 1 if name != 'disconnected' else position == [0,0,0]
        accumulated = vector(run['settled_navigation']['DELVCTL'],7,100)
        original_factor = run['original_KPIP1']['fraction']*12800/16384
        expected_rope = [sum(rotation[i][j]*expected_stable[i]*original_factor for i in range(3)) for j in range(3)]
        tolerance = 2*float(VELOCITY_LSB_M_S)*max(1,len(run['navigation_samples']))
        diagnostics[name].update(independent_rope_scaled_accumulator_REF_m_s=expected_rope,
                                  accumulated_rounding_tolerance_m_s=tolerance)
        comparisons[name+'_original_accumulator_matches_quantized_force'] = max(abs(a-b) for a,b in zip(accumulated,expected_rope)) <= tolerance
    comparisons['zero_specific_force_emits_no_pulses'] = zero['delivered_signed_counts'] == [0,0,0]
    comparisons['zero_specific_force_still_has_original_gravity_velocity_change'] = max(abs(a-b) for a,b in zip(vector(zero['start_navigation']['VN'],7,100),vector(zero['settled_navigation']['VN'],7,100))) > 1
    comparisons['positive_negative_velocity_responses_have_opposite_signs'] = bool(diagnostics.get('positive')) and bool(diagnostics.get('negative')) and diagnostics['positive']['original_VN_difference_from_zero_m_s'][0] > 0 and diagnostics['negative']['original_VN_difference_from_zero_m_s'][0] < 0
    comparisons['disconnected_matches_zero_navigation_words'] = all(runs['disconnected']['settled_navigation'][n] == zero['settled_navigation'][n] for n in ('RN','VN','PIPTIME','DELVCTL','DELVIMU'))
    return {'classification':'VERIFIED native PIPA navigation through Level 4' if all(r['all_pass'] for r in runs.values()) and all(comparisons.values()) else 'UNRESOLVED',
        'all_pass':all(r['all_pass'] for r in runs.values()) and all(comparisons.values()),'runs':runs,'comparisons':comparisons,'causal_diagnostics':diagnostics,
        'scope':'SYNTHETIC stationary aligned instrument, original P47 navigation; no ignition or powered descent; Level 5 guidance use NOT RUN'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite retained analysis')
    result = experiment(args.runs)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'all_pass':result['all_pass'],'failed_run_checks':{n:[k for k,v in r['checks'].items() if not v] for n,r in result['runs'].items()},'comparisons':result['comparisons']}))
    raise SystemExit(0 if result['all_pass'] else 1)
