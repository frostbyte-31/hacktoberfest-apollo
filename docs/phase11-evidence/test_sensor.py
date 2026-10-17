#!/usr/bin/env python3
"""Modern ideal-sensor unit tests. These do not establish AGC navigation success."""
from fractions import Fraction
import json
import unittest

from pipa_sensor import (DELTA_V_PER_PULSE_M_S, MCT_SECONDS, PIPA_COUNTERS,
                         PINC, MINC, PipaSensor)


class SensorTests(unittest.TestCase):
    def sample(self, sensor, end, force, *, gravity=(0, 0, 0), connected=True):
        total = tuple(Fraction(str(f)) + Fraction(str(g)) for f, g in zip(force, gravity))
        return sensor.sample(end, total_acceleration_m_s2=total,
                             gravity_m_s2=gravity, connected=connected)

    def test_source_mappings_and_nominal_scale(self):
        self.assertEqual(PIPA_COUNTERS, (0o37, 0o40, 0o41))
        self.assertEqual((PINC, MINC), (0, 2))
        self.assertEqual(Fraction('0.0512') * 32 * 100 / 16384, DELTA_V_PER_PULSE_M_S)
        self.assertEqual(MCT_SECONDS, Fraction(12, 1024000))

    def test_free_fall_acceleration_is_not_specific_force(self):
        result = self.sample(PipaSensor(), 256000, (0, 0, 0), gravity=(-1.62, 0, 0))
        self.assertEqual(result.specific_force_stable_m_s2, (0, 0, 0))
        self.assertEqual(result.delta_v_stable_m_s, (0, 0, 0))
        self.assertEqual(result.generated_counts, (0, 0, 0))
        self.assertEqual(result.events, ())

    def test_positive_pulses_and_exact_threshold_times(self):
        # 1/3 m/s**2 for exactly 3 seconds = 1 m/s = 100 pulses.
        result = self.sample(PipaSensor(start_cycle=17), 256017, (Fraction(1, 3), 0, 0))
        self.assertEqual(result.delta_v_stable_m_s, (1, 0, 0))
        self.assertEqual(result.generated_counts, (100, 0, 0))
        self.assertEqual(len(result.events), 100)
        self.assertEqual(result.events[0].cycle, 2577)
        self.assertEqual(result.events[-1].cycle, 256017)
        self.assertTrue(all(event.operation == PINC and event.counter == 0o37
                            and event.channel == 0o237 for event in result.events))
        self.assertEqual(result.remainder_m_s, (0, 0, 0))

    def test_negative_pulses_are_minc_not_mcdu(self):
        result = self.sample(PipaSensor(), 256000, (0, Fraction(-1, 3), 0))
        self.assertEqual(result.generated_counts, (0, -100, 0))
        self.assertTrue(all(event.operation == MINC and event.counter == 0o40
                            and event.channel == 0o240 for event in result.events))

    def test_frame_rotation_and_axis_sign(self):
        # Proper +90-degree inertial->stable rotation about Z: +I_X -> +SM_Y.
        sensor = PipaSensor(inertial_to_stable=((0, -1, 0), (1, 0, 0), (0, 0, 1)))
        result = self.sample(sensor, 256000, (Fraction(1, 3), 0, 0))
        self.assertEqual(result.specific_force_stable_m_s2, (0, Fraction(1, 3), 0))
        self.assertEqual(result.generated_counts, (0, 100, 0))

    def test_fractional_pulses_accumulate_across_samples(self):
        sensor = PipaSensor()
        first = self.sample(sensor, 2560, (Fraction(1, 6), 0, 0))
        second = self.sample(sensor, 5120, (Fraction(1, 6), 0, 0))
        self.assertEqual(first.events, ())
        self.assertEqual(first.remainder_m_s[0], Fraction(1, 200))
        self.assertEqual(len(second.events), 1)
        self.assertEqual(second.events[0].cycle, 5120)

    def test_signed_remainder_cancels_before_reversing(self):
        sensor = PipaSensor()
        self.sample(sensor, 2560, (Fraction(1, 6), 0, 0))
        result = self.sample(sensor, 10240, (Fraction(-1, 6), 0, 0))
        self.assertEqual(result.generated_counts, (-1, 0, 0))
        self.assertEqual(result.events[0].cycle, 10240)
        self.assertEqual(result.remainder_m_s, (0, 0, 0))

    def test_disconnection_drops_inputs_without_replaying_on_reconnect(self):
        sensor = PipaSensor()
        disconnected = self.sample(sensor, 256000, (Fraction(1, 3), 0, 0), connected=False)
        self.assertEqual(disconnected.events, ())
        self.assertEqual(disconnected.generated_counts, (100, 0, 0))
        self.assertEqual(disconnected.suppressed_counts, (100, 0, 0))
        reconnected = self.sample(sensor, 258560, (Fraction(1, 3), 0, 0))
        self.assertEqual(reconnected.generated_counts, (1, 0, 0))
        self.assertEqual(len(reconnected.events), 1)

    def test_chunking_does_not_change_pulse_schedule(self):
        whole_sensor, split_sensor = PipaSensor(), PipaSensor()
        whole = self.sample(whole_sensor, 256000, ('0.013', '-0.021', '0.004'))
        events = []
        for end in (1, 120, 990, 3000, 15000, 100000, 256000):
            events.extend(self.sample(split_sensor, end, ('0.013', '-0.021', '0.004')).events)
        self.assertEqual(tuple(events), whole.events)
        self.assertEqual(split_sensor.remainder, whole_sensor.remainder)

    def test_multiple_axes_have_stable_order(self):
        result = self.sample(PipaSensor(), 2560, (Fraction(1, 3),) * 3)
        self.assertEqual([event.axis for event in result.events], ['X', 'Y', 'Z'])
        self.assertEqual([event.cycle for event in result.events], [2560] * 3)

    def test_rounds_crossing_up_to_integer_cycle(self):
        result = self.sample(PipaSensor(), 3000, (Fraction(1, 7), 0, 0))
        # At 1/7 m/s**2 one threshold needs 17920/3 MCT: not reached yet.
        self.assertEqual(result.events, ())
        result = self.sample(PipaSensor(), 6000, (Fraction(1, 7), 0, 0))
        self.assertEqual(result.events[0].cycle, 5974)

    def test_repeated_run_serializes_identically(self):
        a = self.sample(PipaSensor(), 256000, ('0.013', '-0.021', '0.004')).as_dict()
        b = self.sample(PipaSensor(), 256000, ('0.013', '-0.021', '0.004')).as_dict()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_rejects_invalid_vectors_frames_and_time(self):
        for matrix in (((1, 0, 0), (0, 2, 0), (0, 0, 1)),
                       ((1, 0, 0), (0, 1, 0), (0, 0, -1)), ((1, 0),) * 3):
            with self.assertRaises(ValueError):
                PipaSensor(inertial_to_stable=matrix)
        for force in ((float('nan'), 0, 0), (float('inf'), 0, 0), (True, 0, 0), (0, 0)):
            with self.assertRaises((ValueError, TypeError)):
                PipaSensor().sample(10, total_acceleration_m_s2=force, gravity_m_s2=(0, 0, 0))
        sensor = PipaSensor(start_cycle=10)
        with self.assertRaises(ValueError):
            self.sample(sensor, 9, (0, 0, 0))
        with self.assertRaises(ValueError):
            self.sample(PipaSensor(), 100, (1000, 0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
