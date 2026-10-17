#!/usr/bin/env python3
"""Read-only, streaming verification of native DPS/physics/PIPA captures.

Modern calculations here validate retained observations. They never provide
guidance, navigation words, hardware packets or state to the executing AGC.
"""
import argparse
from collections import Counter, defaultdict, deque
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROPE_SHA = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
MCT = Fraction(12, 1024000)
MASK = 0o77777
COUNTERS = (0o37, 0o40, 0o41)
VEL_LSB = 12800 / 2**28
POSITION_LSB = 2**24 / 2**28
MU = 4.902778e12


def read_json(path):
    return json.loads(Path(path).read_text())


def signed(word):
    if type(word) is not int or not 0 <= word <= MASK:
        raise ValueError('Expected a genuine 15-bit AGC word')
    return -(word ^ MASK) if word & 0o40000 else word


def dp(words):
    if len(words) != 2:
        raise ValueError('Expected an original two-word fixed-point quantity')
    return Fraction(signed(words[0])*16384 + signed(words[1]), 2**28)


def vector(words, scale, factor=1):
    if len(words) != 6:
        raise ValueError('Expected an original six-word vector')
    return [float(dp(words[i:i+2])*2**scale*factor) for i in (0, 2, 4)]


def maximum(values):
    return max(map(abs, values), default=0.0)


def native_dir(path):
    path = Path(path)
    return path/'native' if (path/'native').is_dir() else path


def words(row, mapping, name, count=1):
    address = mapping['addresses'][name]
    lookup = mapping['_lookup']
    return [row['snapshot_words'][lookup[address+i]] for i in range(count)]


def counter_next(word, operation):
    if operation == 0:
        value = 0 if word == 0o37777 else (word+1) & MASK
        return 1 if value == 0 and word != 0o37777 else value
    if operation == 2:
        value = MASK if word == 0o40000 else (word-1) & MASK
        return MASK-1 if value == MASK and word != 0o40000 else value
    raise ValueError('PIPA inputs must be genuine PINC or MINC requests')


def rope_scale():
    rope = (ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()
    if hashlib.sha256(rope).hexdigest() != ROPE_SHA:
        raise ValueError('Original Luminary rope differs from validated binary')
    # Pinned assembled KPIP2 = 33,2023, immediately after KPIP1 = 33,2021.
    # wasm.c loads big-endian rope words and removes the parity bit.
    offset = 2*(0o33*1024 + 0o23)
    pair = [int.from_bytes(rope[offset+i:offset+i+2], 'big') >> 1 for i in (0, 2)]
    return pair, dp(pair)


def analyze_run(directory):
    path = native_dir(directory)
    mapping = read_json(path/'observer-map.json')
    mapping['_lookup'] = {a:i for i,a in enumerate(mapping['snapshot_addresses'])}
    kpip_words, kpip2 = rope_scale()
    cp, stages, nav, guidance, outputs = Counter(), {}, [], [], []
    stage_physics, stage_external_counts = {}, {}
    dinc, counter_outputs, drive_outputs = [], [], []
    counters = {address:0 for address in COUNTERS}
    pending = defaultdict(deque)
    pulses, consumed, generated = [0]*3, [0]*3, [0]*3
    counter_errors, counter_latency, unmatched_counter_changes = [], [], 0
    thrust_word, throttle_errors, throttle_latency = 0, [], []
    thrust_loads, last_counter_output_cycle, last_counter_output_value = [], None, None
    hardware_clears, hardware_clear_errors = 0, []
    automatic_count, armed, automatic, engine_on = 0, False, True, False
    throttle_pending = deque()
    physics_errors = defaultdict(float)
    native_math_errors = defaultdict(float)
    first, finish, init, final_plant = None, None, None, None
    last_cycle, last_time, raw_bytes = -1, None, 0
    digest = hashlib.sha256()
    event_counts = Counter()
    plant_rows, pipa_rows, accepted_pipa = 0, 0, 0
    physical_impulse = [0.0]*3
    sensor_impulse, previous_residual = [0.0]*3, [0.0]*3
    pipa_schedule, measurements = [], []
    max_delay, max_model_dt, first_thrust_cycle = 0, 0.0, None
    first_engine_on, first_flatout = None, None
    latest_mun, previous_plant, receiver_state = None, None, None
    physical_enabled_intervals, mass_after_engine_off = 0, None
    monotonic, observer_width, source_inputs = True, True, True
    trace = path/'trace.jsonl'
    stream = trace.open('rb') if trace.exists() else gzip.open(path/'trace.jsonl.gz', 'rb')
    with stream:
        for line in stream:
            digest.update(line); raw_bytes += len(line)
            row = json.loads(line)
            event, cycle = row['ev'], row['cycle']
            if type(cycle) is not int:
                raise ValueError('Native CPU cycle must be an integer')
            monotonic &= cycle >= last_cycle
            last_cycle = cycle
            event_counts[event] += 1
            if first is None:
                first = row
            if event in ('failure', 'wait_timeout'):
                raise ValueError('Failed native execution cannot be accepted: '+str(row))
            if 'snapshot_words' in row:
                observer_width &= len(row['snapshot_words']) == len(mapping['snapshot_addresses'])
            if event == 'stage':
                stages[row['name']] = row
                if previous_plant is not None:
                    stage_physics[row['name']] = previous_plant
                if row['name'] == 'crew-switches-set':
                    armed = not row['channels'][str(0o30)] & 4
                    automatic = not row['channels'][str(0o30)] & 0o20
                if row['name'] == 'crew-disarmed':
                    armed = not row['channels'][str(0o30)] & 4
                    if not armed:
                        automatic_count = 0
                stage_external_counts[row['name']] = automatic_count
            elif event == 'plant_initialization':
                init = row
                previous_plant = row['telemetry']
                last_time = previous_plant['time_s']
            elif event == 'finish':
                finish = row
            elif event == 'hardware_latch_clear':
                hardware_clears += 1
                if (row['channel']!=0o14 or row['before']&0o10==0
                        or row['after']!=row['before']&(MASK ^ 0o10)
                        or last_counter_output_cycle!=cycle or last_counter_output_value!=0o17):
                    hardware_clear_errors.append(cycle)
            elif event == 'input':
                channel, value = row['channel'], row['value']
                source_inputs &= channel in (0o15,0o16,0o30,0o31,0o32,0o33,0o255,0o237,0o240,0o241)
                if channel == 0o255:
                    dinc.append((cycle,value,row['accepted_bytes']))
                    throttle_pending.append(cycle)
                elif channel & 0x80 and channel & 0x7f in COUNTERS:
                    axis = COUNTERS.index(channel & 0x7f)
                    pending[channel & 0x7f].append((cycle,value))
                    pulses[axis] += 1 if value == 0 else -1
                    accepted_pipa += row['accepted_bytes'] == 4
                    pipa_schedule.append((cycle,'XYZ'[axis],channel & 0x7f,value))
            elif event == 'output':
                channel, value = row['channel'], row['value']
                if channel == 0o11:
                    if value & 0o10000 and first_engine_on is None:
                        first_engine_on = {k:row[k] for k in ('cycle','pre_bank','pre_z','value')}
                    if value & 0o10000 and value & 0o20000:
                        throttle_errors.append('conflicting engine ON/OFF')
                    if value & 0o20000:
                        engine_on = False
                    elif value & 0o10000:
                        engine_on = True
                    if not outputs or outputs[-1][1:] != (channel,value & 0o30000):
                        outputs.append((cycle,channel,value & 0o30000))
                elif channel == 0o255:
                    counter_outputs.append((cycle,value))
                    last_counter_output_cycle = cycle
                    last_counter_output_value = value
                    if not throttle_pending:
                        throttle_errors.append('counter output without external DINC')
                    else:
                        request_cycle = throttle_pending.popleft()
                        throttle_latency.append(cycle-request_cycle)
                    expected = 0o15 if signed(thrust_word)>0 else 0o16 if signed(thrust_word)<0 else 0o17
                    if value != expected:
                        throttle_errors.append('DINC output disagrees with original counter sign')
                    if armed and automatic:
                        automatic_count = max(0,min(3428,automatic_count+(1 if value==0o15 else -1 if value==0o16 else 0)))
                elif channel == 0o14:
                    drive_outputs.append((cycle,value,row['pre_bank'],row['pre_z']))
            elif event == 'transition':
                address, value = row['address'], row['value']
                if address == mapping['addresses']['THRUST']:
                    thrust_word = value
                    if cycle != last_counter_output_cycle:
                        thrust_loads.append((cycle,value,row['pre_bank'],row['pre_z']))
                if address in counters:
                    if pending[address]:
                        requested, operation = pending[address].popleft()
                        if value != counter_next(counters[address],operation):
                            counter_errors.append((cycle,address,counters[address],value,operation))
                        counter_latency.append(cycle-requested)
                    else:
                        unmatched_counter_changes += 1
                    counters[address] = value
            elif event == 'pipa_measurement':
                pipa_rows += 1
                max_delay = max(max_delay,row['coupling_delay_mct'])
                measurements.append((cycle,row['axis'],row['counter'],row['operation']))
                if cycle-row['requested_cycle'] != row['coupling_delay_mct'] or not 0 <= row['coupling_delay_mct'] <= 426:
                    counter_errors.append(('sensor coupling',cycle))
            elif event == 'checkpoint':
                routine = row['routine']; cp[routine] += 1
                if routine == 'FLATOUT' and first_flatout is None:
                    first_flatout = cycle
                if routine == 'SERVICER' and init and cycle >= init['cycle']:
                    raw = words(row,mapping,'DELV',6)
                    for i in range(3):
                        consumed[i] += signed(raw[2*i])
                    if any(signed(w) for w in raw[1::2]):
                        counter_errors.append(('raw PIPA low word not zero',cycle))
                if routine == 'MUNRVG':
                    latest_mun = row
                if routine == 'MUNRETRN' and latest_mun and 'R1S' in mapping['addresses']:
                    entry = latest_mun
                    counts = [signed(w) for w in words(entry,mapping,'DELV',6)[::2]]
                    velocity = vector(words(entry,mapping,'V',6),7,100)
                    position = vector(words(entry,mapping,'R',6),24)
                    old_g = vector(words(entry,mapping,'GDT/2',6),7,100)
                    new_g = vector(words(row,mapping,'GDT1/2',6),7,100)
                    computed_v = vector(words(row,mapping,'V1S',6),7,100)
                    computed_r = vector(words(row,mapping,'R1S',6),24)
                    period = float(dp(words(entry,mapping,'PGUIDE',2))*2**28/100)
                    delta = [float(Fraction(n,16384)*kpip2*25600) for n in counts]
                    ve = [actual-(v+dv+g0+g1) for actual,v,dv,g0,g1 in zip(computed_v,velocity,delta,old_g,new_g)]
                    re = [actual-(r+(v+.5*dv+g0)*period) for actual,r,v,dv,g0 in zip(computed_r,position,velocity,delta,old_g)]
                    native_math_errors['velocity_m_s'] = max(native_math_errors['velocity_m_s'],maximum(ve))
                    native_math_errors['position_m'] = max(native_math_errors['position_m'],maximum(re))
                    nav.append({'cycle':cycle,'entry_cycle':entry['cycle'],
                        'PIPTIME_cs':float(dp(words(entry,mapping,'PIPTIME',2))*2**28),
                        'period_s':period,'consumed_counts':counts,'pulse_delta_v_stable_m_s':delta,
                        'R_before_stable_m':position,'V_before_stable_m_s':velocity,
                        'R_computed_stable_m':computed_r,'V_computed_stable_m_s':computed_v,
                        'old_half_gravity_delta_v_m_s':old_g,'new_half_gravity_delta_v_m_s':new_g,
                        'velocity_arithmetic_error_m_s':ve,'position_arithmetic_error_m':re})
                    latest_mun = None
                if routine in ('COPYCYCL','LUNLAND','THROTTLE','GDUMP1','ROOTPSRS','ROOTSTOR_RESULT','QUADGUID'):
                    guidance.append({'cycle':cycle,'routine':routine,
                        'PIPTIME_cs':float(dp(words(row,mapping,'PIPTIME',2))*2**28),
                        'R_stable_m':vector(words(row,mapping,'R',6),24),
                        'V_stable_m_s':vector(words(row,mapping,'V',6),7,100),
                        'STEERSW':bool(words(row,mapping,'FLAGWRD2')[0]&0o2000),
                        'ABDELV_counts':words(row,mapping,'ABDELV')[0],
                        'FC':words(row,mapping,'FC',2),'FP':words(row,mapping,'FP',2),
                        'RGU':words(row,mapping,'RGU',6),'VGU':words(row,mapping,'VGU',6),
                        'TTF':words(row,mapping,'TTF/8',2),'TABLTTF':words(row,mapping,'TABLTTF',10)})
            elif event == 'plant':
                plant_rows += 1
                value, interval = row['telemetry'], row['sensor_interval']
                if init is None:
                    raise ValueError('Plant observation lacks an explicit initialization')
                dt = float((interval['end_cycle']-interval['start_cycle'])*MCT)
                max_model_dt = max(max_model_dt,dt)
                if not 0 < dt <= .010001:
                    raise ValueError('Plant interval exceeds documented bounded stepping')
                physics_errors['clock_s'] = max(physics_errors['clock_s'],abs(value['time_s']-last_time-dt))
                force, mass = value['delivered_thrust_n'],value['mass_before_kg']
                expected_command = min(45040.0,4560.0+(automatic_count if automatic else 0)/.0797959872)
                expected_force = expected_command if armed and engine_on and case_connected(init) else 0.0
                physics_errors['authentic_command_to_thrust_n'] = max(physics_errors['authentic_command_to_thrust_n'],abs(force-expected_force))
                expected_flow = force/3050
                physics_errors['mass_flow_kg_s'] = max(physics_errors['mass_flow_kg_s'],abs(value['mass_flow_kg_s']-expected_flow))
                physics_errors['mass_step_kg'] = max(physics_errors['mass_step_kg'],abs(value['mass_kg']-(mass-expected_flow*dt)))
                physics_errors['fuel_step_kg'] = max(physics_errors['fuel_step_kg'],abs(value['fuel_kg']-(value['fuel_before_kg']-expected_flow*dt)))
                physics_errors['force_over_mass_m_s2'] = max(physics_errors['force_over_mass_m_s2'],abs(value['acceleration_body_x_m_s2']-force/mass))
                q = value['quaternion_body_to_ref']; w,x,y,z = q
                direction = [1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y)]
                specific = value['specific_force_ref_m_s2']
                physics_errors['quaternion_norm'] = max(physics_errors['quaternion_norm'],abs(sum(t*t for t in q)-1))
                physics_errors['thrust_frame_m_s2'] = max(physics_errors['thrust_frame_m_s2'],maximum(f-direction[i]*force/mass for i,f in enumerate(specific)))
                radius = math.sqrt(sum(x*x for x in value['position_before_ref_m']))
                expected_g = [-MU*x/radius**3 for x in value['position_before_ref_m']]
                physics_errors['gravity_m_s2'] = max(physics_errors['gravity_m_s2'],maximum(a-b for a,b in zip(expected_g,value['gravity_ref_m_s2'])))
                physics_errors['specific_force_m_s2'] = max(physics_errors['specific_force_m_s2'],maximum(a-g-f for a,g,f in zip(value['total_acceleration_ref_m_s2'],value['gravity_ref_m_s2'],specific)))
                expected_r = [r+v*dt+.5*(g+f)*dt*dt for r,v,g,f in zip(value['position_before_ref_m'],value['velocity_before_ref_m_s'],expected_g,specific)]
                radius1 = math.sqrt(sum(x*x for x in value['position_ref_m']))
                next_g = [-MU*x/radius1**3 for x in value['position_ref_m']]
                expected_v = [v+.5*(g+h)*dt+f*dt for v,g,h,f in zip(value['velocity_before_ref_m_s'],expected_g,next_g,specific)]
                physics_errors['position_step_m'] = max(physics_errors['position_step_m'],maximum(a-b for a,b in zip(expected_r,value['position_ref_m'])))
                physics_errors['velocity_step_m_s'] = max(physics_errors['velocity_step_m_s'],maximum(a-b for a,b in zip(expected_v,value['velocity_ref_m_s'])))
                physics_errors['state_continuity_m'] = max(physics_errors['state_continuity_m'],maximum(a-b for a,b in zip(value['position_before_ref_m'],previous_plant['position_ref_m'])))
                rotation = init['refs_to_stable']
                sm = [sum(rotation[i][j]*specific[j] for j in range(3)) for i in range(3)]
                physics_errors['sensor_transform_m_s2'] = max(physics_errors['sensor_transform_m_s2'],maximum(a-b for a,b in zip(sm,interval['specific_force_stable_m_s2'])))
                for i in range(3):
                    physical_impulse[i] += specific[i]*dt
                    sensor_impulse[i] += interval['delta_v_stable_m_s'][i]
                    generated[i] += interval['generated_counts'][i]
                    error = previous_residual[i]+interval['delta_v_stable_m_s'][i]-.01*interval['generated_counts'][i]-interval['remainder_m_s'][i]
                    physics_errors['quantization_residual_m_s'] = max(physics_errors['quantization_residual_m_s'],abs(error))
                    previous_residual[i] = interval['remainder_m_s'][i]
                if force > 0:
                    physical_enabled_intervals += 1
                    if first_thrust_cycle is None:
                        first_thrust_cycle = cycle
                elif first_thrust_cycle is not None and mass_after_engine_off is None:
                    mass_after_engine_off = value['mass_kg']
                last_time, previous_plant, final_plant = value['time_s'],value,value
    if first is None or first.get('ev') != 'initial' or finish is None:
        raise ValueError('A complete initial/finish native capture is required')
    seal = read_json(path/'trace-sha256.json')
    digest_hex = digest.hexdigest()
    if seal != {'sha256':digest_hex,'bytes':raw_bytes}:
        raise ValueError('Raw trace checksum does not match retained capture manifest')
    if init is None or final_plant is None:
        raise ValueError('Phase12 causal experiments require the explicit plant and sink model')
    case = init['case']
    counter_balance = [pulses[i]-consumed[i]-signed(finish['observed_words']['PIPA'+'XYZ'[i]][0]) for i in range(3)]
    review = stages['phase10-V06N61']
    mass_load = stages['original-mass-load-complete']
    engine_request = stages['original-engine-enable-request']
    ignition = mapping['checkpoints']['IGNITION']
    positive_after_flatout = [r for r in counter_outputs if r[0]>=first_flatout and r[1]==0o15]
    first_throttle_after_flatout = next((r['cycle'] for r in guidance if r['routine']=='THROTTLE' and r['cycle']>first_flatout),last_cycle+1)
    uninterrupted_flatout = [r for r in positive_after_flatout if r[0]<first_throttle_after_flatout]
    flatout_indices = [i for i,(cycle,value) in enumerate(counter_outputs) if first_flatout<=cycle<first_throttle_after_flatout and value==0o15]
    flatout_requests = [dinc[i][0] for i in flatout_indices]
    clock_phase_error = max((abs((cycle-flatout_requests[0])-i*80/3) for i,cycle in enumerate(flatout_requests)),default=math.inf)
    final_off = next((cycle for cycle,ch,value in reversed(outputs) if value==0o20000),None)
    reset_load = next(((cycle,value) for cycle,value,bank,z in reversed(thrust_loads) if final_off is not None and cycle>final_off and value==MASK-4096),None)
    cancellation = next((r for r in drive_outputs if reset_load and r[0]>reset_load[0] and not r[1]&0o10),None)
    reset_pulses = [r for r in counter_outputs if reset_load and cancellation and reset_load[0]<r[0]<=cancellation[0] and r[1]==0o16]
    reset_remaining = signed(reset_load[1])+len(reset_pulses) if reset_load else None
    shutdown_name='original-shutdown-reset-requested'
    reset_before_on = any(c < first_engine_on['cycle'] and value==0o20000 for c,ch,value in outputs)
    physics_limits = {'clock_s':1e-10,'mass_flow_kg_s':1e-10,'mass_step_kg':1e-8,'fuel_step_kg':1e-8,
        'force_over_mass_m_s2':1e-10,'quaternion_norm':1e-10,'thrust_frame_m_s2':1e-10,
        'gravity_m_s2':1e-12,'specific_force_m_s2':1e-12,'position_step_m':1e-8,
        'velocity_step_m_s':1e-9,'state_continuity_m':1e-8,'sensor_transform_m_s2':1e-10,
        'quantization_residual_m_s':1e-12,'authentic_command_to_thrust_n':1e-8}
    checks = {
        'raw_capture_complete_monotonic_and_observer_map_matches':monotonic and observer_width,
        'original_rope_no_flight_memory_writes':first.get('rope_sha256')==ROPE_SHA and first.get('original_ram_writes')==0,
        'only_documented_hardware_input_channels':source_inputs,
        'original_p51_reference_readiness_and_p63_review':review['state']['refsmflg'] and review['state']['modreg']==63 and review['state']['display']['VERB']=='06' and review['state']['display']['NOUN']=='61' and cp['P63_AFTER_R02']>0,
        'original_dsky_v48_mass_load':abs(float(dp(mass_load['observed_words']['MASS'])*2**16)-15000)<1e-8 and mass_load['observed_words']['LEMMASS']==[3750],
        'original_crew_and_preignition_continuation':all(cp[n]>0 for n in ('ASTNRETN','R51P63','R60LEM','P63SPOT4','BURNBABY','P40AUTO','MIDTOAV1','PREREAD')) and stages['R51-checklist']['state']['display']['R1']=='00014',
        'original_v99_crew_request_is_separate_from_engine_on':engine_request['state']['display']['VERB']=='99' and engine_request['state']['display']['NOUN']=='62' and engine_request['cycle']<first_engine_on['cycle'],
        'original_ignition_instruction_emits_engine_on':cp['IGNITION']==1 and first_engine_on['pre_bank']==ignition[0] and ignition[1]<=first_engine_on['pre_z']<ignition[1]+32,
        'engine_off_reset_observed_before_ignition':reset_before_on and cp['ENGINOF3']>0,
        'original_p63_zoom_and_flatout_execute':cp['P63ZOOM']==cp['FLATOUT']==1 and first_engine_on['cycle']<first_flatout,
        'genuine_dinc_drives_counter_outputs':bool(dinc) and len(dinc)==len(counter_outputs) and not throttle_pending and not throttle_errors and all(value==4 and accepted==4 for cycle,value,accepted in dinc) and all(1<=latency<=8 for latency in throttle_latency),
        'hardware_drive_latch_clear_requires_genuine_zout':hardware_clears==sum(value==0o17 for cycle,value in counter_outputs)>0 and not hardware_clear_errors,
        'flatout_original_counter_load_is_4096':any(first_flatout<=cycle<=first_flatout+100 and value==4096 for cycle,value,bank,z in thrust_loads),
        'flatout_sink_emits_4096_uninterrupted_positive_pulses':len(uninterrupted_flatout)==4096 if case!='connected' else len(uninterrupted_flatout)>0,
        'external_thrust_clock_has_source_3200_hz_phase':clock_phase_error<=1.000001,
        'source_pipa_addresses_and_sign_operations':[mapping['addresses'][n] for n in ('PIPAX','PIPAY','PIPAZ')]==list(COUNTERS) and all(r[2]==COUNTERS['XYZ'.index(r[1])] and r[3] in (0,2) for r in measurements),
        'bounded_sensor_coupling_and_real_packet_acceptance':max_delay<=426 and accepted_pipa==sum(abs(x) for x in pulses) and not counter_errors and all(1<=x<=8 for x in counter_latency),
        'physical_sensor_count_and_delivery_match':pipa_schedule==measurements if case=='connected' else not pipa_schedule,
        'original_navigation_consumes_delivered_counts':not any(counter_balance) and all(not q for q in pending.values()) and cp['MUNRVG']>0 and cp['SERVICER']>0,
        'original_munrvg_math_matches_independent_pulse_and_gravity_arithmetic':bool(nav) and native_math_errors['velocity_m_s']<=8*VEL_LSB and native_math_errors['position_m']<=4*POSITION_LSB,
        'original_munrvg_period_remains_two_seconds':bool(nav) and all(abs(n['period_s']-2)<.010001 for n in nav),
        'physical_engine_model_observations_present':plant_rows>0 and max_model_dt<=.010001,
        'physical_units_frame_gravity_integration_and_mass_flow':all(physics_errors[k]<=limit for k,limit in physics_limits.items()),
        'zero_force_before_authentic_ignition':first_thrust_cycle is None if case=='sink' else first_thrust_cycle>first_engine_on['cycle'],
        'disconnected_engine_or_connected_physical_motion':(physical_enabled_intervals==0 and final_plant['mass_kg']==init['initial_mass_kg']) if case=='sink' else (physical_enabled_intervals>0 and final_plant['mass_kg']<init['initial_mass_kg']),
        'bounded_p63_horizon_followed_by_original_p00_shutdown':stages['bounded-post-enable-horizon']['state']['modreg']==63 and finish['state']['modreg']==0,
        'original_engine_off_cancels_reset_without_fabricated_counter_settlement':not engine_on and reset_load is not None and cancellation is not None and 0<len(reset_pulses)<4096 and signed(finish['observed_words']['THRUST'][0])==reset_remaining and not any(cycle>cancellation[0] for cycle,value in counter_outputs) and stages[shutdown_name]['channels'][str(0o11)]&0o20000!=0,
        'crew_disarm_is_separate_from_original_software_reset':not armed and automatic_count==0 and 'crew-disarmed' in stages and stages['crew-disarmed']['channels'][str(0o30)]&4!=0 and stage_external_counts[shutdown_name]>0,
        'physical_engine_off_stops_force_and_propellant_flow':final_plant['delivered_thrust_n']==final_plant['mass_flow_kg_s']==0 and (case=='sink' or mass_after_engine_off is not None and abs(final_plant['mass_kg']-mass_after_engine_off)<1e-8),
    }
    for filename in ('preservation-before','preservation-after'):
        saved=read_json(path/(filename+'.json'))
        checks[filename+'_all_prior_files_unchanged']=bool(saved['files_checked']) and not saved['changed_or_missing']
    source=read_json(path/'source-integrity/after-execution.json')
    checks['original_pinned_source_unchanged']=bool(source['files_checked']) and not source['changed_or_missing']
    checks['original_phase10_baseline_guard_unchanged']=read_json(path/'original-preservation-after.json')['ok'] is True
    return {'case':case,'all_pass':all(checks.values()),'checks':checks,'raw_sha256':digest_hex,'raw_bytes':raw_bytes,
        'event_counts':dict(event_counts),'checkpoint_counts':dict(cp),'first_engine_on':first_engine_on,
        'first_flatout_cycle':first_flatout,'engine_command_transitions':outputs,
        'counter_clock':{'DINC_events':len(dinc),'counter_outputs':dict(Counter(v for c,v in counter_outputs)),
            'maximum_delivery_delay_mct':max(throttle_latency,default=0),'errors':throttle_errors,
            'hardware_drive_latch_clears':hardware_clears,'hardware_latch_clear_errors':hardware_clear_errors,
            'positive_outputs_after_flatout':len(positive_after_flatout),
            'positive_flatout_pulses_before_next_original_throttle':len(uninterrupted_flatout),
            'first_flatout_counter_clock_max_phase_error_mct':clock_phase_error,
            'flatout_uninterrupted_train_duration_s':float((uninterrupted_flatout[-1][0]-uninterrupted_flatout[0][0])*MCT) if uninterrupted_flatout else None,
            'original_counter_loads':thrust_loads,'final_external_automatic_count':automatic_count,
            'software_shutdown_reset':{'load':reset_load,'drive_cancellation':cancellation,
                'negative_pulses_before_cancellation':len(reset_pulses),'original_counter_remaining':reset_remaining,
                'external_accumulator_after_software_stop':stage_external_counts.get(shutdown_name),
                'external_accumulator_after_crew_disarm':stage_external_counts.get('crew-disarmed'),
                'classification':'Original P00 cancels a partially delivered reset; a later physical crew disarm separately clears the external accumulator.'}},
        'physical':{'initialization':init,'final':final_plant,'rows':plant_rows,'max_interval_s':max_model_dt,
            'bounded_horizon':stage_physics.get('bounded-post-enable-horizon'),
            'bounded_horizon_cycle':stages['bounded-post-enable-horizon']['cycle'],
            'first_thrust_cycle':first_thrust_cycle,'physical_specific_impulse_REF_m_s':physical_impulse,
            'max_independent_validation_errors':dict(physics_errors),'validation_tolerances':physics_limits},
        'sensor':{'generated_counts':generated,'delivered_counts':pulses,'consumed_counts':consumed,
            'ending_counter_counts':[signed(finish['observed_words']['PIPA'+axis][0]) for axis in 'XYZ'],
            'counter_balance_error':counter_balance,'counter_errors':counter_errors,
            'maximum_counter_delivery_delay_mct':max(counter_latency,default=0),'maximum_coupling_delay_mct':max_delay,
            'specific_impulse_stable_m_s':sensor_impulse,'ending_quantization_remainder_m_s':previous_residual},
        'navigation_samples':nav,'guidance_samples':guidance,'native_math_max_errors':dict(native_math_errors),
        'original_KPIP2':{'rope_address_octal':'33,2023','words_octal':[format(w,'05o') for w in kpip_words],'fraction':float(kpip2)},
        'final_state':finish['state'],'final_observed_words':finish['observed_words'],
        'classification':'Physical plant and sensor/native navigation are tested separately; closed-loop guidance requires causal comparisons.'}


def case_connected(initialization):
    return initialization['telemetry']['physical_engine_connected']


def experiment(directory):
    directory=Path(directory)
    runs={name:analyze_run(directory/name) for name in ('sink','connected','no-feedback','repeat')}
    a,b,c=runs['connected'],runs['sink'],runs['no-feedback']
    checks={'connected_repeat_trace_byte_identical':a['raw_sha256']==runs['repeat']['raw_sha256'],
        'same_authentic_ignition_cycle':len({r['first_engine_on']['cycle'] for r in runs.values()})==1,
        'engine_connection_causes_physical_velocity_position_and_fuel_change':a['physical']['bounded_horizon_cycle']==b['physical']['bounded_horizon_cycle'] and maximum(x-y for x,y in zip(a['physical']['bounded_horizon']['velocity_ref_m_s'],b['physical']['bounded_horizon']['velocity_ref_m_s']))>1 and maximum(x-y for x,y in zip(a['physical']['bounded_horizon']['position_ref_m'],b['physical']['bounded_horizon']['position_ref_m']))>1 and a['physical']['bounded_horizon']['mass_kg']<b['physical']['bounded_horizon']['mass_kg'],
        'only_connected_feedback_delivers_pipa_hardware':sum(abs(n) for n in a['sensor']['delivered_counts'])>0 and not any(c['sensor']['delivered_counts']) and not any(b['sensor']['generated_counts']),
        'engine_derived_feedback_reaches_original_navigation':sum(abs(n) for n in a['sensor']['consumed_counts'])>0 and not any(c['sensor']['consumed_counts']) and not any(b['sensor']['consumed_counts']),
        'disconnected_feedback_preserves_sink_original_navigation':c['final_observed_words']['R']==b['final_observed_words']['R'] and c['final_observed_words']['V']==b['final_observed_words']['V'],
        'feedback_changes_original_navigation_words':a['final_observed_words']['R']!=c['final_observed_words']['R'] and a['final_observed_words']['V']!=c['final_observed_words']['V'],
        'feedback_changes_original_control_execution':a['checkpoint_counts'].get('THROTTLE',0)>0 and b['checkpoint_counts'].get('THROTTLE',0)==c['checkpoint_counts'].get('THROTTLE',0)==0,
        'feedback_changes_authentic_throttle_counter_output':a['counter_clock']['counter_outputs']!=c['counter_clock']['counter_outputs'],
    }
    diagnostics={}
    for control in ('sink','no-feedback'):
        other=runs[control]
        match={n['PIPTIME_cs']:n for n in other['navigation_samples']}
        pairs=[(n,match[n['PIPTIME_cs']]) for n in a['navigation_samples'] if n['PIPTIME_cs'] in match]
        checks['matched_original_navigation_epochs_'+control]=len(pairs)>=3
        if pairs:
            measured,baseline=pairs[-1]
            pulse_difference=[sum(p['pulse_delta_v_stable_m_s'][i]-q['pulse_delta_v_stable_m_s'][i] for p,q in pairs) for i in range(3)]
            gravity_difference=[sum(p['old_half_gravity_delta_v_m_s'][i]+p['new_half_gravity_delta_v_m_s'][i]-q['old_half_gravity_delta_v_m_s'][i]-q['new_half_gravity_delta_v_m_s'][i] for p,q in pairs) for i in range(3)]
            actual_delta=[x-y for x,y in zip(measured['V_computed_stable_m_s'],baseline['V_computed_stable_m_s'])]
            first_a,first_b=pairs[0]
            initial_difference=[x-y for x,y in zip(first_a['V_before_stable_m_s'],first_b['V_before_stable_m_s'])]
            error=[actual_delta[i]-initial_difference[i]-pulse_difference[i]-gravity_difference[i] for i in range(3)]
            tolerance=16*VEL_LSB*len(pairs)
            checks['independent_original_velocity_difference_budget_'+control]=maximum(error)<=tolerance
            diagnostics[control]={'PIPTIME_cs':measured['PIPTIME_cs'],'matched_samples':len(pairs),
                'original_velocity_difference_stable_m_s':actual_delta,
                'original_position_difference_stable_m':[x-y for x,y in zip(measured['R_computed_stable_m'],baseline['R_computed_stable_m'])],
                'quantized_pulse_contribution_stable_m_s':pulse_difference,
                'original_gravity_contribution_difference_m_s':gravity_difference,
                'independent_velocity_budget_error_m_s':error,'velocity_DP_tolerance_m_s':tolerance,
                'tolerance_reason':'Sixteen velocity DP LSB per paired original two-second navigation cycle; gravity contributions are separately observed original values, not fabricated sensor acceleration.'}
    return {'all_pass':all(r['all_pass'] for r in runs.values()) and all(checks.values()),'runs':runs,
        'comparisons':checks,'causal_navigation_comparisons':diagnostics,
        'scope':'Bounded SYNTHETIC P63 engine/physical sensor/navigation experiment, not a landing.',
        'guidance_level':'Causal original throttle response verified only when feedback_changes_original_control_execution and feedback_changes_authentic_throttle_counter_output both pass.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=experiment(args.runs)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'all_pass':result['all_pass'],'runs':{k:v['all_pass'] for k,v in result['runs'].items()},'comparisons':result['comparisons']}))
    raise SystemExit(0 if result['all_pass'] else 1)


if __name__=='__main__':
    main()
