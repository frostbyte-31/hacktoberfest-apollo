"""Read-only Phase 12 recording export; never executes or controls an AGC.

The original evidence seal and all four decompressed raw fingerprints are
verified before selecting actual physical observations from three native cases.
Frames hold recorded samples. Derived local projections are modern diagnostics,
not AGC navigation or a new spacecraft dynamics implementation.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'docs/phase12-evidence'
MCT = Fraction(12, 1024000)
MAX_SAMPLE_CYCLES = int(Fraction(1, 4)/MCT)
CASES = ('sink', 'connected', 'no-feedback')
TITLES = {'sink': 'Engine disconnected',
          'connected': 'Engine and PIPA feedback connected',
          'no-feedback': 'Engine connected, PIPA feedback disconnected'}
LIMITATIONS = [
    'VERIFIED RECORDED AUTHENTIC AGC EXPERIMENT; playback is not live execution.',
    'SYNTHETIC fixed-attitude fixture, not historical Apollo 11 flight data.',
    'Original Luminary commands drive a simplified physical engine and navigation feedback.',
    'RCS is disconnected; the crew accepted an attitude review without an achieved burn maneuver.',
    'Engine response is instantaneous; inherited LM-7 parameters and nominal DECA gain are approximations.',
    'Zero LOWCRIT/HIGHCRIT padloads and saturated thrust do not establish a calibrated throttle policy.',
    'The recorded initial thrust is not established retrograde braking; no complete descent or landing is demonstrated.',
    'Physical REF state and original stable-member navigation/PIPTIME are separate measurements.',
    'Only actual observations are shown, held between samples without interpolation or extrapolation.',
]
STAGES = {
    'R51-checklist': 'Original R51 crew checklist',
    'R60-crew-attitude-review': 'Original R60 attitude review',
    'after-attitude-review': 'Crew accepted attitude review; fixture remains fixed',
    'crew-switches-set': 'Documented external crew switches set',
    'crew-switch-checklist': 'Original crew switch checklist',
    'preignition-wait': 'Original preignition countdown',
    'original-engine-enable-request': 'Original V99N62 crew ignition request',
    'bounded-post-enable-horizon': 'Bounded P63 experiment horizon',
    'original-shutdown-reset-requested': 'Original P00 shutdown; reset may remain incomplete',
    'crew-disarmed': 'Separate crew DISARM resets external DECA',
}
ROUTINES = {'IGNITION': 'Original IGNITION entry',
            'FLATOUT': 'Original FLATOUT entry',
            'THROTTLE': 'Original guidance THROTTLE entry',
            'MUNRVG': 'Original lunar navigation reads the measured increment',
            'LUNLAND': 'Original lunar landing guidance entry'}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def verify_trace(path, expected):
    """Verify original raw bytes, independently of the compressed file hash."""
    result, count = hashlib.sha256(), 0
    with gzip.open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
            count += len(block)
    observed = {'sha256': result.hexdigest(), 'bytes': count}
    if observed != expected:
        raise ValueError('Retained raw trace differs: '+str(path))
    return observed


def verify_evidence(root=ROOT):
    root = Path(root).resolve()
    package = root/PACKAGE
    seal_path = package/'checksums.json'
    seal = read_json(seal_path)
    paths = [root/'docs/PHASE12_DESCENT_PROPULSION.md']
    paths.extend(path for path in sorted(package.rglob('*'))
                 if path.is_file() and path != seal_path and '__pycache__' not in path.parts)
    observed = {str(path.relative_to(root)): digest(path) for path in paths}
    if observed != seal['sha256'] or len(observed) != seal['files']:
        raise ValueError('Original Phase 12 evidence seal differs')
    raw = {}
    for case in (*CASES, 'repeat'):
        source = package/'runs/verified'/case
        raw[case] = verify_trace(source/'trace.jsonl.gz', read_json(source/'trace-sha256.json'))
    if raw['connected'] != raw['repeat']:
        raise ValueError('Original connected repeat is not byte-identical')
    config_path = 'docs/phase10-evidence/configs/mission-15km.json'
    expected_config = read_json(package/'prior_hashes.json')['sha256'][config_path]
    if digest(root/config_path) != expected_config:
        raise ValueError('Original mission geometry changed')
    analysis = read_json(package/'validation/analysis.json')
    if analysis.get('all_pass') is not True:
        raise ValueError('Original native analysis did not pass')
    for case, value in raw.items():
        if analysis['runs'][case]['raw_sha256'] != value['sha256']:
            raise ValueError('Analysis does not identify retained raw capture')
    return {'sealSha256': digest(seal_path), 'filesVerified': len(observed),
            'rawTraces': raw, 'connectedRepeatByteIdentical': True,
            'geometryPath': config_path, 'geometrySha256': expected_config}


def _vector(value, length=3):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError('Recorded vector has an invalid width')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError('Recorded vector must contain finite numbers')
    return list(value)


def project_physics(telemetry, radius_m, origin_angle):
    """Independent display projections of recorded state, not propagation."""
    position = _vector(telemetry['position_ref_m'])
    velocity = _vector(telemetry['velocity_ref_m_s'])
    radius = math.sqrt(sum(x*x for x in position))
    plane_radius = math.hypot(position[0], position[2])
    if radius <= 1 or plane_radius <= 1:
        raise ValueError('Recorded position cannot define this local projection')
    up = [x/radius for x in position]
    tangent = [-position[2]/plane_radius, 0.0, position[0]/plane_radius]
    vertical = sum(v*u for v, u in zip(velocity, up))
    horizontal = math.sqrt(max(0.0, sum(v*v for v in velocity)-vertical*vertical))
    matrix = [_vector(row) for row in telemetry['rotation_body_to_ref']]
    body_x = [matrix[i][0] for i in range(3)]
    # Same right-handed +body-Y convention as the educational lab: positive
    # pitch turns body +X towards negative local downrange. This is a derived
    # XZ projection; no orientation or sensor measurement is changed.
    pitch = math.degrees(math.atan2(-sum(a*b for a, b in zip(body_x, tangent)),
                                   sum(a*b for a, b in zip(body_x, up))))
    return {
        'simTimeSeconds': telemetry['time_s'],
        'spacecraft': {
            'positionM': position, 'velocityMps': velocity,
            'accelerationMps2': _vector(telemetry['total_acceleration_ref_m_s2']),
            'specificForceMps2': _vector(telemetry['specific_force_ref_m_s2']),
            'gravityMps2': _vector(telemetry['gravity_ref_m_s2']),
            'quaternionBodyToRef': _vector(telemetry['quaternion_body_to_ref'], 4),
            'angularVelocityRadps': _vector(telemetry['angular_velocity_body_rad_s']),
            'massKg': telemetry['mass_kg'], 'fuelKg': telemetry['fuel_kg'],
            'altitudeM': radius-radius_m, 'verticalSpeedMps': vertical,
            'horizontalSpeedMps': horizontal,
            'horizontalVelocityMps': sum(v*t for v, t in zip(velocity, tangent)),
            'downrangeM': radius_m*(math.atan2(position[2], position[0])-origin_angle),
            'pitchDeg': pitch,
        },
        'engine': {
            'enabled': telemetry['engine_enabled'], 'throttle': None,
            'commandedEnabled': telemetry['requested_engine_enabled'],
            'thrustN': telemetry['delivered_thrust_n'],
            'commandedThrustN': telemetry['commanded_thrust_n'],
            'massFlowKgps': telemetry['mass_flow_kg_s'],
            'thrustVectorN': _vector(telemetry['thrust_vector_ref_n']),
        },
        'assumptions': LIMITATIONS[1:8], 'outcome': None,
    }


def _source(line, cycle, fingerprint):
    return {'rawLine': line, 'cycle': cycle, 'traceSha256': fingerprint}


def _case(root, case, fingerprint, radius_m, result):
    path = root/PACKAGE/'runs/verified'/case
    mapping = read_json(path/'observer-map.json')
    program_index = mapping['snapshot_addresses'].index(mapping['addresses']['MODREG'])
    frames, events = [], []
    t0 = origin_angle = None
    dsky = dsky_source = program = program_source = None
    pending = None
    previous_cycle = -1
    last_engine_command = None
    physical_enabled = False

    def event(row, source, title, kind):
        if t0 is None or row['cycle'] < t0:
            return
        events.append({'id': case+'-'+str(source['rawLine'])+'-'+kind,
                       't': float((row['cycle']-t0)*MCT), 'cycle': row['cycle'],
                       'title': title, 'type': kind, 'source': source})

    with gzip.open(path/'trace.jsonl.gz', 'rt') as stream:
        for line, text in enumerate(stream, 1):
            row = json.loads(text)
            cycle = row['cycle']
            if type(cycle) is not int or cycle < previous_cycle:
                raise ValueError('Original capture is not monotonic')
            previous_cycle = cycle
            source = _source(line, cycle, fingerprint)
            if row['ev'] == 'output':
                if row['channel'] == 0o10:
                    dsky, dsky_source = row['display'], source
                elif row['channel'] == 0o11:
                    command = 'on' if row['value'] & 0o10000 else 'off' if row['value'] & 0o20000 else None
                    if command and command != last_engine_command:
                        event(row, source, 'Original ENGINE '+command.upper()+' output', 'engine-command')
                    if command:
                        last_engine_command = command
            elif row['ev'] == 'checkpoint':
                program, program_source = row['snapshot_words'][program_index], source
                if row['routine'] in ROUTINES:
                    event(row, source, ROUTINES[row['routine']], 'navigation' if row['routine']=='MUNRVG' else 'guidance')
            elif row['ev'] == 'stage':
                if row['name'] in STAGES:
                    event(row, source, STAGES[row['name']], 'crew' if 'crew' in row['name'] or 'R51' in row['name'] or 'R60' in row['name'] else 'mission')
            if row['ev'] not in ('plant_initialization', 'plant'):
                continue
            telemetry = row['telemetry']
            if t0 is None:
                if row['ev'] != 'plant_initialization':
                    raise ValueError('No recorded physical initialization')
                t0 = cycle
                origin_angle = math.atan2(telemetry['position_ref_m'][2], telemetry['position_ref_m'][0])
                event(row, source, 'Synthetic physical fixture initialized', 'physics')
            physics = project_physics(telemetry, radius_m, origin_angle)
            frame = {'t': float((cycle-t0)*MCT), 'cycle': cycle, 'source': source,
                     'physics': physics,
                     'agc': {'dsky': deepcopy(dsky), 'program': program,
                             'sourceCycle': None if dsky_source is None else dsky_source['cycle'],
                             'dskySource': deepcopy(dsky_source), 'programSource': deepcopy(program_source)}}
            changed = bool(telemetry['engine_enabled']) != physical_enabled
            if changed:
                event(row, source, 'Synthetic plant thrust '+('begins' if telemetry['engine_enabled'] else 'stops'), 'physics')
            physical_enabled = bool(telemetry['engine_enabled'])
            # Keep the last genuine observation before a 250 ms gap would be
            # exceeded. Mandatory physical on/off frames remain genuine too.
            if frames and cycle-frames[-1]['cycle'] > MAX_SAMPLE_CYCLES:
                if pending is None or pending['cycle'] <= frames[-1]['cycle']:
                    raise ValueError('Raw physical sampling exceeds display hold bound')
                frames.append(pending)
            if not frames or changed:
                if not frames or frame['cycle'] != frames[-1]['cycle']:
                    frames.append(frame)
            pending = frame
    if pending is None:
        raise ValueError('Capture has no physical observations')
    if frames[-1]['cycle'] != pending['cycle']:
        frames.append(pending)
    if any(b['cycle']-a['cycle'] > MAX_SAMPLE_CYCLES for a, b in zip(frames, frames[1:])):
        raise ValueError('Recorded sample gap exceeds 250 ms')
    navigation = result['navigation_samples'][-1] if result['navigation_samples'] else None
    return {
        'id': case, 'title': TITLES[case], 'traceSha256': fingerprint,
        'durationSeconds': frames[-1]['t'], 'frames': frames, 'events': events,
        'source': {'tracePath': str((path/'trace.jsonl.gz').relative_to(root)),
                   'traceSha256': fingerprint, 't0Cycle': t0,
                   'physicalSimulationEpoch': 'Raw time_s is elapsed model propagation from initialized mission-state epoch; replay t starts at physical fixture activation.',
                   'sampling': 'Actual physical observations, held; at most 0.25 s apart, no interpolation.',
                   'coordinateFrame': 'Moon-centered basic REF; original MUNRVG navigation uses stable-member coordinates.',
                   'lunarRadiusM': radius_m, 'initialProjectionAngleRad': origin_angle},
        'result': {
            'originalChecksPass': result['all_pass'],
            'engineConnected': case != 'sink', 'pipaFeedbackConnected': case == 'connected',
            'originalEngineOnCycle': result['first_engine_on']['cycle'],
            'originalThrottleCalls': result['checkpoint_counts'].get('THROTTLE', 0),
            'originalLunarNavigationPasses': result['checkpoint_counts'].get('MUNRVG', 0),
            'sensor': deepcopy(result['sensor']),
            'navigation': {'coordinateFrame': 'IMU stable member', 'timeReference': 'Original PIPTIME, centiseconds',
                           'lastOriginalSample': deepcopy(navigation),
                           'sourceNote': 'AGC-computed navigation, separate from recorded physical REF state.'},
            'finalMassKg': result['physical']['final']['mass_kg'],
            'finalFuelKg': result['physical']['final']['fuel_kg'],
            'finalAlarmsOctal': [format(word, '05o') for word in result['final_state']['failreg'] if word],
            'landing': 'NOT RUN', 'calibratedDescent': 'UNRESOLVED',
        },
    }


def build_recording(root=ROOT):
    root = Path(root).resolve()
    verified = verify_evidence(root)
    geometry = read_json(root/verified['geometryPath'])['synthetic_geometry']
    analysis = read_json(root/PACKAGE/'validation/analysis.json')
    cases = [_case(root, case, verified['rawTraces'][case]['sha256'],
                   geometry['lunar_reference_radius_m'], analysis['runs'][case]) for case in CASES]
    return {'schemaVersion': 1, 'mode': 'RECORDED_AUTHENTIC_AGC_EXPERIMENT',
            'title': 'Original Luminary: bounded propulsion and inertial feedback',
            'limitations': LIMITATIONS, 'cases': cases,
            'units': {'position': 'm', 'velocity': 'm/s', 'acceleration': 'm/s²',
                      'time': 's', 'thrust': 'N', 'mass': 'kg', 'angularVelocity': 'rad/s', 'pitch': 'degree'},
            'projection': {'kind': 'INDEPENDENT_PROJECTION', 'plane': 'basic REF XZ',
                           'altitude': '|r| minus documented lunar reference radius',
                           'verticalSpeed': 'v dot r/|r|',
                           'downrange': 'reference radius times change in atan2(z,x), relative to first physical sample',
                           'positivePitch': 'right-handed body +Y tilt from local radial up; thrust turns toward negative local XZ tangent',
                           'caution': 'Local projections do not establish a historical trajectory or achieved burn attitude.'},
            'provenance': {**verified, 'sourcePackage': PACKAGE+'/checksums.json',
                           'analysisPath': PACKAGE+'/validation/analysis.json',
                           'analysisSha256': digest(root/PACKAGE/'validation/analysis.json'),
                           'originalVirtualAgcRevision': read_json(root/PACKAGE/'mapping.json')['virtualagc_revision'],
                           'clockSecondsPerMct': float(MCT)},
            'capabilities': {'liveExecution': False, 'replay': True, 'arbitraryCommands': False,
                             'completeDescent': False, 'landing': False,
                             'causalNavigationAndOriginalThrottle': analysis['comparisons']['feedback_changes_original_control_execution']}}


def serialize(recording):
    # Match the existing generated frontend recordings: compact JSON avoids
    # shipping indentation on every repeated sample over the local demo server.
    return json.dumps(recording, separators=(',', ':'), allow_nan=False)+'\n'


DERIVED_PROJECTION_FIELDS = frozenset(('altitudeM', 'verticalSpeedMps',
    'horizontalSpeedMps', 'horizontalVelocityMps', 'downrangeM', 'pitchDeg'))
PROJECTION_ULP_LIMIT = 8


def verify_export(text, expected):
    """Compare to a fresh sealed-source export, allowing only display-math ULPs.

    Host libm implementations can differ in their last bits. This allowance
    applies only to six named projections computed by ``project_physics``.
    Recorded vectors, engine/AGC observations, source hashes, sample order and
    all other values must agree exactly, including the sign of a recorded zero.
    The returned flag distinguishes equivalent observations from identical bytes.
    """
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate propulsion export field')
            result[key] = value
        return result

    actual = json.loads(text, object_pairs_hook=unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite export value')))
    differences = 0

    def compare(left, right, path=()):
        nonlocal differences
        def fail():
            raise ValueError('Propulsion export differs from sealed source at '+
                             '/'.join(str(part) for part in path))
        if type(left) is not type(right):
            fail()
        if isinstance(right, dict):
            if left.keys() != right.keys():
                fail()
            for key in right:
                compare(left[key], right[key], (*path, key))
        elif isinstance(right, list):
            if len(left) != len(right):
                fail()
            for index, (a, b) in enumerate(zip(left, right)):
                compare(a, b, (*path, index))
        elif type(right) is float:
            if not math.isfinite(left) or not math.isfinite(right):
                fail()
            if left.hex() == right.hex():
                return
            derived = (len(path) == 7 and path[0] == 'cases'
                       and type(path[1]) is int and path[2] == 'frames'
                       and type(path[3]) is int and path[4:6] == ('physics', 'spacecraft')
                       and path[6] in DERIVED_PROJECTION_FIELDS)
            limit = PROJECTION_ULP_LIMIT * max(math.ulp(left), math.ulp(right))
            if not derived or abs(left-right) > limit:
                fail()
            differences += 1
        elif left != right:
            fail()

    compare(actual, expected)
    return {'byteIdentical': text == serialize(expected),
            'recordedObservationsExact': True,
            'derivedProjectionUlpLimit': PROJECTION_ULP_LIMIT,
            'derivedProjectionDifferences': differences}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'frontend/dist/data/propulsion-lab.json')
    parser.add_argument('--check', action='store_true', help='Verify existing export; never write it')
    args = parser.parse_args()
    output = args.output.resolve()
    text = serialize(build_recording())
    verification = None
    if args.check:
        verification = verify_export(output.read_text(), json.loads(text))
    else:
        if ROOT/'docs' == output or ROOT/'docs' in output.parents:
            raise ValueError('Exporter cannot write retained evidence')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    print(json.dumps({'verified': True, 'mode': 'RECORDED_AUTHENTIC_AGC_EXPERIMENT',
                      'cases': len(CASES), 'output': str(output), 'sha256': digest(output),
                      'verification': verification}))


if __name__ == '__main__':
    main()
