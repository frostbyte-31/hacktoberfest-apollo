#!/usr/bin/env python3
"""Ideal, bounded PIPA measurement adapter; no spacecraft/navigation integration.

VERIFIED mappings in Virtual AGC f577e3fd917866c59334e6cdd32504f09df76f60:
  Luminary099/ERASABLE_ASSIGNMENTS.agc:134-136: PIPAX/Y/Z = 037/040/041.
  yaAGC/ringbuffer_api.c:130-135: channel bit 0x80 selects counter operations.
  yaAGC/agc_engine.c:1570-1602: operation 0=PINC; operation 2=MINC.
  Luminary099/SERVICER.agc:199-204: ABDELV counts are cm/s; KPIP converts
    count/2**14 to (m/cs)/2**5. CONTROLLED_CONSTANTS.agc:178 gives .0512:
    .0512 * 2**5 * 100 / 2**14 = .01 m/s per nominal LM PIPA pulse.
  yaAGC/agc_engine.c:1863: one MCT is 12/1024000 seconds.

ASSUMED ideal sensor: no bias, scale error, saturation, noise, or vibration.
Inputs are piecewise constant inertial vectors in m/s**2. A caller supplies a
proper inertial-to-stable-member rotation, f_SM = C_SM_I (a_I - g_I). Identity
means a deliberately aligned diagnostic fixture, not a calibrated Apollo IMU.
No body attitude or gravity model is inferred here. No AGC memory is accessed.

An event is requested on the first integer MCT boundary at/after a signed
0.01 m/s threshold crossing. The signed fractional remainder is retained.
Different axes may request the same MCT; transport must record actual service
cycles if it serializes them. Disconnection drops events while measurement
continues, so reconnection does not replay missed pulses. Host clock is unused.
"""
from dataclasses import dataclass
from fractions import Fraction
import math


PIPA_COUNTERS = (0o37, 0o40, 0o41)
PINC, MINC = 0, 2
DELTA_V_PER_PULSE_M_S = Fraction(1, 100)
MCT_SECONDS = Fraction(12, 1024000)
IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _number(value):
    """Interpret external decimal values without binary-float accumulation."""
    if isinstance(value, bool):
        raise ValueError('boolean is not a physical quantity')
    try:
        return value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError('physical quantities must be finite numbers') from exc


def _vector(values):
    if len(values) != 3:
        raise ValueError('a three-component vector is required')
    return tuple(_number(value) for value in values)


def rotation(values):
    """Validate a proper rotation; reject scale/shear/reflection frame mistakes."""
    if len(values) != 3:
        raise ValueError('a 3x3 inertial-to-stable-member rotation is required')
    matrix = tuple(_vector(row) for row in values)
    for i in range(3):
        for j in range(3):
            dot = sum(matrix[i][k] * matrix[j][k] for k in range(3))
            if abs(float(dot) - (1 if i == j else 0)) > 1e-6:
                raise ValueError('inertial-to-stable-member matrix is not orthogonal')
    a, b, c = matrix
    determinant = (a[0] * (b[1]*c[2] - b[2]*c[1])
                   - a[1] * (b[0]*c[2] - b[2]*c[0])
                   + a[2] * (b[0]*c[1] - b[1]*c[0]))
    if abs(float(determinant) - 1) > 1e-6:
        raise ValueError('inertial-to-stable-member matrix is not a proper rotation')
    return matrix


@dataclass(frozen=True)
class CounterEvent:
    """One hardware operation request, not an AGC input-channel value write."""
    cycle: int
    axis: str
    counter: int
    operation: int

    @property
    def channel(self):
        return 0x80 | self.counter

    @property
    def sign(self):
        return 1 if self.operation == PINC else -1

    def as_dict(self):
        return {'cycle': self.cycle, 'axis': self.axis,
                'counter': self.counter, 'channel': self.channel,
                'operation': self.operation, 'sign': self.sign}


@dataclass(frozen=True)
class SensorInterval:
    start_cycle: int
    end_cycle: int
    specific_force_stable_m_s2: tuple
    delta_v_stable_m_s: tuple
    remainder_m_s: tuple
    generated_counts: tuple
    suppressed_counts: tuple
    events: tuple

    def as_dict(self):
        return {
            'start_cycle': self.start_cycle, 'end_cycle': self.end_cycle,
            'specific_force_stable_m_s2': [float(x) for x in self.specific_force_stable_m_s2],
            'delta_v_stable_m_s': [float(x) for x in self.delta_v_stable_m_s],
            'remainder_m_s': [float(x) for x in self.remainder_m_s],
            'generated_counts': list(self.generated_counts),
            'suppressed_counts': list(self.suppressed_counts),
            'events': [event.as_dict() for event in self.events],
        }

    def to_dict(self):
        return self.as_dict()


class PipaSensor:
    """Piecewise-constant ideal sensor; cycles refer to emulator cpu_step calls."""
    def __init__(self, *, start_cycle=0, inertial_to_stable=IDENTITY):
        if isinstance(start_cycle, bool) or not isinstance(start_cycle, int) or start_cycle < 0:
            raise ValueError('start_cycle must be a nonnegative integer')
        self.cycle = start_cycle
        self.inertial_to_stable = rotation(inertial_to_stable)
        self.remainder = (Fraction(0),) * 3

    def sample(self, end_cycle, *, total_acceleration_m_s2, gravity_m_s2, connected=True):
        if isinstance(end_cycle, bool) or not isinstance(end_cycle, int) or end_cycle < self.cycle:
            raise ValueError('end_cycle must be an integer at/after the current cycle')
        if not isinstance(connected, bool):
            raise ValueError('connected must be boolean')
        acceleration, gravity = _vector(total_acceleration_m_s2), _vector(gravity_m_s2)
        inertial_force = tuple(a-g for a, g in zip(acceleration, gravity))
        force = tuple(sum(row[k] * inertial_force[k] for k in range(3))
                      for row in self.inertial_to_stable)
        per_cycle = tuple(value * MCT_SECONDS for value in force)
        if any(abs(value) > DELTA_V_PER_PULSE_M_S for value in per_cycle):
            raise ValueError('fixture cannot represent more than one pulse per axis per MCT')
        count = end_cycle - self.cycle
        delta_v = tuple(value * count for value in per_cycle)
        residual, generated, events = [], [], []
        for axis, (old, increment) in enumerate(zip(self.remainder, per_cycle)):
            signed_count = 0
            if increment:
                sign = 1 if increment > 0 else -1
                threshold = sign * DELTA_V_PER_PULSE_M_S
                crossing = (threshold - old) / increment
                period = DELTA_V_PER_PULSE_M_S / abs(increment)
                # Each crossing is calculated from the exact integrated signal.
                while crossing <= count:
                    tick = math.ceil(crossing)
                    events.append(CounterEvent(self.cycle + tick, 'XYZ'[axis],
                                               PIPA_COUNTERS[axis], PINC if sign > 0 else MINC))
                    signed_count += sign
                    crossing += period
            residual.append(old + delta_v[axis] - signed_count * DELTA_V_PER_PULSE_M_S)
            generated.append(signed_count)
        events.sort(key=lambda event: (event.cycle, event.axis))
        result = SensorInterval(self.cycle, end_cycle, force, delta_v, tuple(residual),
                                tuple(generated), (0, 0, 0) if connected else tuple(generated),
                                tuple(events) if connected else ())
        self.cycle, self.remainder = end_cycle, tuple(residual)
        return result
