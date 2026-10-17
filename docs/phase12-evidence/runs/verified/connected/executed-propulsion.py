#!/usr/bin/env python3
"""Bounded DPS actuator and translation adapter; no guidance or navigation code.

Original upstream dynamic_simulation owns F/m and fuel mass flow. Phase7's
quaternion matrix owns orientation conversion. Modern code supplies only the
missing DECA counter decoder and transparent 3D translational integration.
The fixed attitude and ideal instantaneous engine response are SYNTHETIC
approximations, not validated flight hardware transients. No AGC RAM is read
or written by this module. The caller must provide authentic packets separately.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINE_ON, ENGINE_OFF = 0o10000, 0o20000
THRUST_COUNTER_CHANNEL = 0x80 | 0o55
POUT, MOUT, ZOUT = 0o15, 0o16, 0o17
PULSES_PER_NEWTON = 0.0797959872
MIN_THRUST_N = 4560.0
MAX_THRUST_N = 45040.0
DECA_MAX_COUNTS = 3428
EXHAUST_VELOCITY_M_S = 3050.0
MOON_MU_M3_S2 = 4.902778e12
MODEL = 'Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl'
INITIALIZATION = 'Contributed/LM_Simulator/lm_simulator.tcl'


def _finite(value):
    if isinstance(value, bool):
        raise ValueError('a finite numerical physical quantity is required')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('a finite numerical physical quantity is required')
    return number


def _vector(values, width=3):
    if len(values) != width:
        raise ValueError('incorrect physical vector width')
    return tuple(_finite(value) for value in values)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class DpsReceiver:
    """External DECA accumulator, driven only by supplied output packet events.

    Disarming physically zeros the automatic counter. Engine OFF while armed
    stops thrust but leaves that counter intact until genuine decrement pulses
    arrive. The 3428-count accumulator limit comes from R567 control data;
    physical min/max and 3050m/s exhaust velocity are pinned LM-simulator
    parameters, not asserted Apollo11 flight calibration. The nominal software
    pulse/N conversion is an explicit plant approximation. The manual lever is
    fixed at its minimum. Manual throttle modulation is outside this fixture.
    """
    armed: bool = False
    autothrottle: bool = True
    automatic_count: int = 0
    requested_engine_on: bool = False

    def __post_init__(self):
        if type(self.armed) is not bool or type(self.autothrottle) is not bool:
            raise ValueError('hardware switches must be boolean')
        if (type(self.automatic_count) is not int
                or not 0 <= self.automatic_count <= DECA_MAX_COUNTS):
            raise ValueError('invalid DECA accumulator')
        if type(self.requested_engine_on) is not bool:
            raise ValueError('engine request must be boolean')
        if not self.armed:
            self.automatic_count = 0

    def set_hardware(self, *, armed=None, autothrottle=None):
        for value in (armed, autothrottle):
            if value is not None and type(value) is not bool:
                raise ValueError('hardware switches must be boolean')
        if armed is not None:
            self.armed = armed
        if autothrottle is not None:
            self.autothrottle = autothrottle
        if not self.armed:
            self.automatic_count = 0

    def consume(self, channel, value):
        if type(channel) is not int or type(value) is not int or not 0 <= value <= 0o77777:
            raise ValueError('invalid AGC output packet')
        if channel == 0o11:
            if value & ENGINE_ON and value & ENGINE_OFF:
                raise ValueError('conflicting engine ON/OFF output')
            if value & ENGINE_OFF:
                self.requested_engine_on = False
            elif value & ENGINE_ON:
                self.requested_engine_on = True
        elif channel == THRUST_COUNTER_CHANNEL:
            if value not in (POUT, MOUT, ZOUT):
                raise ValueError('unsupported THRUST counter output')
            if self.armed and self.autothrottle:
                change = 1 if value == POUT else -1 if value == MOUT else 0
                self.automatic_count = max(0, min(DECA_MAX_COUNTS,
                                                   self.automatic_count + change))
        # Other genuine output channels have no DPS effect.
        return self.snapshot()

    @property
    def enabled(self):
        return self.armed and self.requested_engine_on

    @property
    def commanded_thrust_n(self):
        count = self.automatic_count if self.autothrottle else 0
        return min(MAX_THRUST_N, MIN_THRUST_N + count / PULSES_PER_NEWTON)

    def snapshot(self):
        return {'armed': self.armed, 'autothrottle': self.autothrottle,
                'requested_engine_on': self.requested_engine_on,
                'enabled': self.enabled, 'automatic_count': self.automatic_count,
                'commanded_thrust_n': self.commanded_thrust_n}


class LegacyEngine:
    """Owns a persistent verified Tcl subprocess executing the original plant."""
    def __init__(self, *, source, tcl, mass_kg=15000.0, fuel_kg=8355.0,
                 ascent_mass_kg=4670.0, runtime_manifest=None):
        self.source, self.tcl = Path(source).resolve(), Path(tcl).resolve()
        mass, fuel, ascent = map(_finite, (mass_kg, fuel_kg, ascent_mass_kg))
        if mass <= ascent or ascent <= 0 or not 0 <= fuel < mass - ascent:
            raise ValueError('inconsistent dry/ascent/propellant mass')
        expected = json.loads((ROOT/'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
        self.source_hashes = {}
        for name in (MODEL, INITIALIZATION):
            actual = _digest(self.source / name)
            if actual != expected[name]:
                raise ValueError('pinned original plant source mismatch: ' + name)
            self.source_hashes[name] = actual
        manifest = (Path(runtime_manifest) if runtime_manifest is not None
                    else self.tcl.parents[2] / 'runtime-manifest.json')
        spec = importlib.util.spec_from_file_location('phase12_runtime', ROOT/'tools/reproducibility/bootstrap_runtime.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        runtime = module.validate_runtime(manifest)
        if Path(runtime['executable']).resolve() != self.tcl:
            raise ValueError('Tcl executable differs from verified runtime manifest')
        phase7 = ROOT/'docs/phase7-evidence/physics/orientation.tcl'
        self.provenance = {'upstream_source_sha256': self.source_hashes,
                           'phase7_orientation_sha256': _digest(phase7),
                           'adapter_sha256': _digest(HERE/'legacy_engine.tcl'),
                           'tcl_executable_sha256': _digest(self.tcl),
                           'engine_response': 'ASSUMED instantaneous upstream model',
                           'force_scale': 'ASSUMED nominal guidance pulse/N applied to physical plant',
                           'exhaust_velocity_m_s': EXHAUST_VELOCITY_M_S,
                           'max_interval_s': 0.010001}
        self.process = subprocess.Popen(
            [str(self.tcl), str(HERE/'legacy_engine.tcl'), str(self.source), str(phase7),
             repr(mass), repr(fuel), repr(ascent)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        if self.process.stdout.readline().strip() != 'READY':
            self.close()
            raise RuntimeError('headless original plant did not initialize')
        self.mass_kg, self.fuel_kg = mass, fuel

    def step(self, dt, *, enabled, thrust_n, quaternion_body_to_ref=(1, 0, 0, 0)):
        dt, thrust = map(_finite, (dt, thrust_n))
        q = _vector(quaternion_body_to_ref, 4)
        if type(enabled) is not bool:
            raise ValueError('engine enable must be boolean')
        if not 0 < dt <= 0.010001 or not 0 <= thrust <= MAX_THRUST_N:
            raise ValueError('outside bounded engine interval or force range')
        if abs(sum(x*x for x in q) - 1) > 1e-9:
            raise ValueError('body-to-reference quaternion must be unit length')
        if enabled and thrust*dt/EXHAUST_VELOCITY_M_S > self.fuel_kg:
            raise ValueError('fuel-exhaustion transient is outside bounded fixture')
        line = ' '.join(map(str, (dt, int(enabled), thrust, *q))) + '\n'
        try:
            self.process.stdin.write(line)
            self.process.stdin.flush()
            result = self.process.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError('original plant transport failed') from exc
        if not result:
            error = self.process.stderr.read()
            raise RuntimeError('original plant stopped: ' + error)
        values = [float(x) for x in result.split()]
        if len(values) != 19 or not all(math.isfinite(x) for x in values):
            raise RuntimeError('invalid original plant response')
        self.mass_kg, self.fuel_kg = values[1], values[3]
        return {'mass_before_kg': values[0], 'mass_kg': values[1],
                'fuel_before_kg': values[2], 'fuel_kg': values[3],
                'acceleration_body_x_m_s2': values[4], 'mass_flow_kg_s': values[5],
                'engine_enabled': bool(values[6]), 'delta_v_body_m_s': values[7:10],
                'rotation_body_to_ref': [values[10:13], values[13:16], values[16:19]],
                'delivered_thrust_n': thrust if values[6] else 0.0}

    def close(self):
        process = getattr(self, 'process', None)
        if process is None:
            return
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=3)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        self.process = None

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


def gravity(position_ref_m, mu_m3_s2=MOON_MU_M3_S2):
    position, mu = _vector(position_ref_m), _finite(mu_m3_s2)
    norm = math.sqrt(sum(x*x for x in position))
    if norm <= 1 or mu < 0:
        raise ValueError('invalid central-gravity state')
    return tuple(-mu*x/norm**3 for x in position)


class PropulsionPlant:
    """Existing engine plus fixed-attitude 3D velocity-Verlet translation.

    Origin: lunar center. Position m, velocity m/s and acceleration m/s² are in
    the same inertial reference frame as the supplied fixed body quaternion.
    Gravity is central and evaluated at both interval endpoints. Specific
    force is the existing engine's body delta-v divided by dt, rotated with
    the reused Phase7 matrix. Preburn mass is frozen within each <=10ms step,
    exactly as upstream dynamic_simulation. No fictitious landing is modeled.
    """
    def __init__(self, *, source, tcl, position_ref_m, velocity_ref_m_s,
                 quaternion_body_to_ref=(1, 0, 0, 0), mass_kg=15000.0,
                 fuel_kg=8355.0, connected=True, mu_m3_s2=MOON_MU_M3_S2,
                 runtime_manifest=None):
        self.position_ref_m = _vector(position_ref_m)
        self.velocity_ref_m_s = _vector(velocity_ref_m_s)
        self.quaternion_body_to_ref = _vector(quaternion_body_to_ref, 4)
        if abs(sum(x*x for x in self.quaternion_body_to_ref)-1) > 1e-9:
            raise ValueError('body-to-reference quaternion must be unit length')
        if type(connected) is not bool:
            raise ValueError('physical engine connection must be boolean')
        self.mu_m3_s2 = _finite(mu_m3_s2)
        gravity(self.position_ref_m, self.mu_m3_s2)
        self.connected, self.time_s = connected, 0.0
        self.engine = LegacyEngine(source=source, tcl=tcl, mass_kg=mass_kg,
                                   fuel_kg=fuel_kg, runtime_manifest=runtime_manifest)

    def step(self, dt, *, enabled, thrust_n):
        dt, commanded = _finite(dt), _finite(thrust_n)
        if type(enabled) is not bool:
            raise ValueError('engine enable must be boolean')
        engine = self.engine.step(dt, enabled=enabled and self.connected,
                                  thrust_n=commanded,
                                  quaternion_body_to_ref=self.quaternion_body_to_ref)
        matrix, body_dv = engine['rotation_body_to_ref'], engine['delta_v_body_m_s']
        specific = tuple(sum(matrix[i][j]*body_dv[j]/dt for j in range(3)) for i in range(3))
        initial_r, initial_v = self.position_ref_m, self.velocity_ref_m_s
        g0 = gravity(initial_r, self.mu_m3_s2)
        next_r = tuple(initial_r[i]+initial_v[i]*dt+0.5*(g0[i]+specific[i])*dt*dt
                       for i in range(3))
        g1 = gravity(next_r, self.mu_m3_s2)
        next_v = tuple(initial_v[i]+0.5*(g0[i]+g1[i])*dt+specific[i]*dt for i in range(3))
        self.position_ref_m, self.velocity_ref_m_s = next_r, next_v
        self.time_s += dt
        return {**engine, 'time_s': self.time_s, 'physical_engine_connected': self.connected,
                'commanded_thrust_n': commanded, 'requested_engine_enabled': enabled,
                'position_before_ref_m': list(initial_r), 'velocity_before_ref_m_s': list(initial_v),
                'position_ref_m': list(next_r), 'velocity_ref_m_s': list(next_v),
                'quaternion_body_to_ref': list(self.quaternion_body_to_ref),
                'angular_velocity_body_rad_s': [0.0, 0.0, 0.0],
                'specific_force_ref_m_s2': list(specific), 'gravity_ref_m_s2': list(g0),
                'total_acceleration_ref_m_s2': [g0[i]+specific[i] for i in range(3)],
                'thrust_vector_ref_n': [specific[i]*engine['mass_before_kg'] for i in range(3)],
                'delta_v_specific_ref_m_s': [x*dt for x in specific]}

    def close(self):
        self.engine.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
