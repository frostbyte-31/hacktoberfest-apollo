"""Server-owned Level C landing laboratory, explicitly independent of the AGC.

Translation, engine acceleration/fuel flow and quaternion-to-force conversion
reuse the unchanged Phase 12 PropulsionPlant / LegacyEngine and Phase 7 matrix.
The sole new actuator is an explicitly synthetic, single-axis pitch motor.
No original Apollo instructions, navigation words or hardware outputs are used
or synthesized by this educational mode.
"""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'apollo_final_educational_propulsion', ROOT/'docs/phase12-evidence/propulsion.py')
PROPULSION = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = PROPULSION
_SPEC.loader.exec_module(PROPULSION)

DT = .01
MOON_RADIUS_M = 1738090.0
PITCH_INERTIA_KG_M2 = 12000.0
PITCH_TORQUE_NM = 2400.0
PITCH_DAMPING_PER_S = 2.0
TERMINAL = frozenset(('landed', 'crashed', 'fuel_exhausted', 'lost', 'timed_out'))
THRESHOLDS = {'verticalSpeedMps': 2.0, 'horizontalSpeedMps': 1.5,
              'pitchDeg': 8.0, 'landingSiteDistanceM': 75.0,
              'lossOfControlPitchDeg': 70.0, 'timeLimitSeconds': 180.0}
SCENARIOS = {
    'training': {'id': 'training', 'title': 'Final approach', 'altitudeM': 150.0,
                 'verticalSpeedMps': -5.0, 'horizontalSpeedMps': 1.0,
                 'massKg': 8000.0, 'fuelKg': 500.0},
    'braking': {'id': 'braking', 'title': 'Brake before touchdown', 'altitudeM': 300.0,
                'verticalSpeedMps': -15.0, 'horizontalSpeedMps': 3.0,
                'massKg': 8000.0, 'fuelKg': 500.0},
    'low-fuel': {'id': 'low-fuel', 'title': 'Limited propellant', 'altitudeM': 150.0,
                 'verticalSpeedMps': -5.0, 'horizontalSpeedMps': 1.0,
                 'massKg': 8000.0, 'fuelKg': 15.0},
}


def _number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(name+' must be finite and between '+str(low)+' and '+str(high))
    return float(value)


def _geometry(position, velocity):
    radius = math.sqrt(sum(x*x for x in position))
    unit = [x/radius for x in position]
    vertical = sum(v*u for v,u in zip(velocity, unit))
    horizontal = math.sqrt(max(0.0, sum(v*v for v in velocity)-vertical*vertical))
    plane_radius = math.hypot(position[0], position[2])
    signed_horizontal = (-position[2]*velocity[0]+position[0]*velocity[2])/plane_radius
    return {'altitudeM': radius-MOON_RADIUS_M, 'verticalSpeedMps': vertical,
            'horizontalSpeedMps': horizontal, 'horizontalVelocityMps': signed_horizontal,
            'downrangeM': MOON_RADIUS_M*math.atan2(position[2], position[0])}


def touchdown(measured):
    """Synthetic teaching thresholds, never claimed as Apollo flight limits."""
    reasons = []
    if abs(measured['verticalSpeedMps']) > THRESHOLDS['verticalSpeedMps']:
        reasons.append('vertical impact speed exceeds the synthetic 2 m/s limit')
    if measured['horizontalSpeedMps'] > THRESHOLDS['horizontalSpeedMps']:
        reasons.append('horizontal impact speed exceeds the synthetic 1.5 m/s limit')
    if abs(measured['pitchDeg']) > THRESHOLDS['pitchDeg']:
        reasons.append('tilt exceeds the synthetic 8 degree limit')
    if abs(measured['downrangeM']) > THRESHOLDS['landingSiteDistanceM']:
        reasons.append('contact is outside the synthetic 75 m landing-site limit')
    return {'success': not reasons, 'reasons': reasons or ['contact meets the synthetic teaching limits'],
            'measured': deepcopy(measured), 'thresholds': deepcopy(THRESHOLDS)}


class PhysicsLab:
    """Fixed 10 ms physics ticks; the caller owns pacing, permission and audit.

    Coordinates: Moon-centered inertial REF, initial local up +X, downrange +Z.
    Engine thrust is body +X. Positive right-handed pitch is about body +Y,
    turning thrust towards -Z. The pitch motor has fixed synthetic inertia,
    applied torque and viscous damping; it is not Apollo RCS or AGC guidance.
    Quaternion rotation and translational integration remain in the existing
    Phase 12 plant. Attitude is held at its integrated endpoint within each
    <=10 ms interval, matching the existing bounded orientation cadence.
    """
    def __init__(self, assets, scenario='training'):
        if not isinstance(scenario, str) or scenario not in SCENARIOS:
            raise ValueError('Unknown educational scenario')
        initial = deepcopy(SCENARIOS[scenario])
        self.scenario = scenario
        self.initial = initial
        self.tick = 0
        self.status = 'ready'
        self.controls = {'throttle': 0.0, 'pitch': 0.0}
        self.angle = self.omega = self.torque = 0.0
        self.outcome = None
        self.closed = False
        self.command_count = 0
        self.maximum_altitude = self.minimum_altitude = initial['altitudeM']
        self.maximum_speed = math.hypot(initial['verticalSpeedMps'], initial['horizontalSpeedMps'])
        self.last_average_thrust = 0.0
        manifest = assets.get('runtime_manifest') or assets.get('provenance', {}).get('runtime_manifest')
        self.plant = PROPULSION.PropulsionPlant(
            source=assets['source'], tcl=assets['tcl'], runtime_manifest=manifest,
            position_ref_m=(MOON_RADIUS_M+initial['altitudeM'], 0.0, 0.0),
            velocity_ref_m_s=(initial['verticalSpeedMps'], 0.0, initial['horizontalSpeedMps']),
            mass_kg=initial['massKg'], fuel_kg=initial['fuelKg'])
        self.provenance = deepcopy(self.plant.engine.provenance)
        self.last = None

    def command(self, throttle, pitch):
        # Validate both fields before changing either authoritative control.
        throttle = _number(throttle, 0.0, 1.0, 'throttle')
        pitch = _number(pitch, -1.0, 1.0, 'pitch')
        if self.closed or self.status in TERMINAL:
            raise ValueError('The educational flight has ended; restart before commanding')
        self.controls = {'throttle': throttle, 'pitch': pitch}
        self.command_count += 1
        return {'accepted': True, 'tick': self.tick, 'controls': deepcopy(self.controls),
                'source': 'manual educational actuator commands; not AGC output'}

    def _interval(self):
        self.torque = PITCH_TORQUE_NM*self.controls['pitch']-PITCH_INERTIA_KG_M2*PITCH_DAMPING_PER_S*self.omega
        next_omega = self.omega+self.torque/PITCH_INERTIA_KG_M2*DT
        self.angle += .5*(self.omega+next_omega)*DT
        self.omega = next_omega
        # Exact representation of the integrated single-axis pitch; existing
        # Phase7 Tcl matrix performs the actual body-to-REF force conversion.
        self.plant.quaternion_body_to_ref = (math.cos(self.angle/2), 0.0, math.sin(self.angle/2), 0.0)
        setting = self.controls['throttle']
        force = 0.0 if setting == 0 else PROPULSION.MIN_THRUST_N+setting*(PROPULSION.MAX_THRUST_N-PROPULSION.MIN_THRUST_N)
        fuel = self.plant.engine.fuel_kg
        burn_dt = DT if force > 0 else 0.0
        if force > 0 and force*DT/PROPULSION.EXHAUST_VELOCITY_M_S > fuel:
            # Avoid crossing the retained engine's genuine negative-fuel guard.
            # A negligible roundoff reserve is disclosed, not silently burned.
            burn_dt = max(0.0, fuel*PROPULSION.EXHAUST_VELOCITY_M_S/force*(1-1e-12))
        if burn_dt > 1e-12:
            self.last = self.plant.step(burn_dt, enabled=True, thrust_n=force)
        remaining = DT-burn_dt
        if remaining > 1e-12:
            self.last = self.plant.step(remaining, enabled=False, thrust_n=0.0)
        self.last_average_thrust = force*burn_dt/DT
        self.tick += 1
        current = self._measure()
        self.maximum_altitude = max(self.maximum_altitude, current['altitudeM'])
        self.minimum_altitude = min(self.minimum_altitude, current['altitudeM'])
        self.maximum_speed = max(self.maximum_speed, math.sqrt(sum(v*v for v in self.plant.velocity_ref_m_s)))
        if current['altitudeM'] <= 0:
            self.outcome = touchdown(current)
            self.status = 'landed' if self.outcome['success'] else 'crashed'
        elif self.plant.engine.fuel_kg <= 1e-8:
            self._finish('fuel_exhausted', 'usable propellant exhausted before surface contact', current)
        elif abs(current['pitchDeg']) > THRESHOLDS['lossOfControlPitchDeg']:
            self._finish('lost', 'tilt exceeded the synthetic 70 degree control boundary', current)
        elif self.tick*DT >= THRESHOLDS['timeLimitSeconds']:
            self._finish('timed_out', 'the bounded educational flight reached its time limit', current)

    def _finish(self, status, reason, current):
        self.status = status
        self.outcome = {'success': False, 'reasons': [reason], 'measured': deepcopy(current),
                        'thresholds': deepcopy(THRESHOLDS)}

    def step(self, ticks=10):
        if type(ticks) is not int or not 1 <= ticks <= 1000:
            raise ValueError('ticks must be an integer from 1 to 1000')
        if self.closed:
            raise ValueError('Educational laboratory is closed')
        if self.status not in TERMINAL:
            self.status = 'running'
            for _ in range(ticks):
                self._interval()
                if self.status in TERMINAL:
                    break
        return self.snapshot()

    def _measure(self):
        return {**_geometry(self.plant.position_ref_m, self.plant.velocity_ref_m_s),
                'pitchDeg': math.degrees(self.angle+math.atan2(self.plant.position_ref_m[2],self.plant.position_ref_m[0])),
                'fuelKg': self.plant.engine.fuel_kg,
                'massKg': self.plant.engine.mass_kg}

    def snapshot(self):
        current = self._measure()
        gravity = list(PROPULSION.gravity(self.plant.position_ref_m))
        terminal = self.status in TERMINAL
        thrust = self.last['delivered_thrust_n'] if self.last and not terminal else 0.0
        specific = self.last['specific_force_ref_m_s2'] if self.last and not terminal else [0.0]*3
        acceleration = [g+f for g,f in zip(gravity, specific)]
        q = list(self.plant.quaternion_body_to_ref)
        return {'mode': 'EDUCATIONAL_PHYSICS_LAB', 'source': 'live server simulation; manual modern actuators',
            'status': self.status, 'tick': self.tick, 'simTimeSeconds': self.tick*DT,
            'scenario': self.scenario, 'controls': deepcopy(self.controls),
            'spacecraft': {**current, 'positionM': list(self.plant.position_ref_m),
                'velocityMps': list(self.plant.velocity_ref_m_s), 'accelerationMps2': acceleration,
                'specificForceMps2': list(specific), 'gravityMps2': gravity,
                'quaternionBodyToRef': q, 'angularVelocityRadps': [0.0, self.omega, 0.0]},
            'engine': {'enabled': thrust > 0, 'throttle': self.controls['throttle'], 'thrustN': thrust,
                'massFlowKgps': thrust/PROPULSION.EXHAUST_VELOCITY_M_S,
                'thrustVectorN': list(self.last['thrust_vector_ref_n']) if self.last and not terminal else [0.0]*3,
                'lastStepAverageThrustN': self.last_average_thrust},
            'outcome': deepcopy(self.outcome), 'thresholds': deepcopy(THRESHOLDS),
            'units': {'position': 'm', 'velocity': 'm/s', 'acceleration': 'm/s²', 'mass': 'kg',
                'time': 's', 'thrust': 'N', 'angularVelocity': 'rad/s', 'pitch': 'degree'},
            'frame': {'name': 'Moon-centered inertial REF', 'origin': 'Moon center',
                'initialUp': '+X', 'downrange': '+Z', 'thrustBodyAxis': '+X',
                'positivePitch': 'right-handed about body +Y; thrust turns toward REF -Z'},
            'provenance': deepcopy(self.provenance),
            'assumptions': ['SYNTHETIC educational scenario, not Apollo 11 flight data.',
                'No AGC guidance, PIPA delivery or RCS commands drive this mode.',
                'Existing central lunar gravity and velocity-Verlet translation; fixed 10 ms ticks.',
                'Existing ideal instantaneous engine; thrust min/max and exhaust velocity are model parameters.',
                'Synthetic pitch motor: I=12000 kg·m², commanded torque=±2400 N·m, damping=2/s.',
                'Pitch actuator propellant and changing rotational inertia are not modeled.',
                'Surface outcome uses actual integrated endpoint; no position or velocity snapping.',
                'Terminal physics freezes; engine telemetry then reports OFF.',
                'Fuel exhaustion leaves at most 1e-8 kg numerical reserve.']}

    def debrief(self):
        return {'mode': 'EDUCATIONAL_PHYSICS_LAB', 'status': self.status,
            'simTimeSeconds': self.tick*DT, 'outcome': deepcopy(self.outcome),
            'fuelUsedKg': self.initial['fuelKg']-self.plant.engine.fuel_kg,
            'maximumAltitudeM': self.maximum_altitude, 'minimumAltitudeM': self.minimum_altitude,
            'maximumSpeedMps': self.maximum_speed, 'commandsApplied': self.command_count,
            'finalState': self.snapshot(),
            'lessons': ['Thrust changes acceleration; existing velocity takes time to brake.',
                'Tilting redirects thrust and can trade vertical braking for horizontal motion.',
                'Free fall has gravity acceleration and zero ideal accelerometer specific force.',
                'These manual physics results are separate from original Luminary guidance.']}

    def close(self):
        if not self.closed:
            self.plant.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
