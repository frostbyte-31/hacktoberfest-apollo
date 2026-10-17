#!/usr/bin/env python3
"""Focused modern-model tests; these do NOT prove authentic AGC execution.

Run with --source <verified VirtualAGC root> --tcl <verified Tcl executable>.
The same files are hash-verified by LegacyEngine before the original procedure
is executed. No environment-specific paths or network downloads are required.
"""
import argparse
from pathlib import Path
import json
import math
import sys
import tempfile
import unittest

from propulsion import (DpsReceiver, LegacyEngine, PropulsionPlant, gravity,
    ENGINE_ON, ENGINE_OFF, THRUST_COUNTER_CHANNEL, POUT, MOUT, ZOUT,
    MAX_THRUST_N, MIN_THRUST_N, DECA_MAX_COUNTS, PULSES_PER_NEWTON,
    EXHAUST_VELOCITY_M_S, MOON_MU_M3_S2, ROOT, MODEL, INITIALIZATION)

SOURCE = TCL = MANIFEST = None


class ReceiverTests(unittest.TestCase):
    def test_engine_requires_both_arm_and_on(self):
        receiver = DpsReceiver()
        receiver.consume(0o11, ENGINE_ON)
        self.assertFalse(receiver.enabled)
        receiver.set_hardware(armed=True)
        self.assertTrue(receiver.enabled)
        receiver.consume(0o11, ENGINE_OFF)
        self.assertFalse(receiver.enabled)

    def test_positive_negative_and_zero_pulses(self):
        receiver = DpsReceiver(armed=True)
        for _ in range(123):
            receiver.consume(THRUST_COUNTER_CHANNEL, POUT)
        self.assertEqual(receiver.automatic_count, 123)
        self.assertAlmostEqual(receiver.commanded_thrust_n,
                               MIN_THRUST_N+123/PULSES_PER_NEWTON)
        receiver.consume(THRUST_COUNTER_CHANNEL, ZOUT)
        self.assertEqual(receiver.automatic_count, 123)
        for _ in range(23):
            receiver.consume(THRUST_COUNTER_CHANNEL, MOUT)
        self.assertEqual(receiver.automatic_count, 100)

    def test_hardware_counter_and_mechanical_force_stop_are_distinct(self):
        receiver = DpsReceiver(armed=True)
        for _ in range(4096):
            receiver.consume(THRUST_COUNTER_CHANNEL, POUT)
        self.assertEqual(receiver.automatic_count, DECA_MAX_COUNTS)
        self.assertEqual(receiver.commanded_thrust_n, MAX_THRUST_N)
        receiver.consume(THRUST_COUNTER_CHANNEL, MOUT)
        self.assertEqual(receiver.automatic_count, DECA_MAX_COUNTS-1)
        self.assertEqual(receiver.commanded_thrust_n, MAX_THRUST_N)

    def test_engine_off_reset_requires_actual_decrement_pulses(self):
        receiver = DpsReceiver(armed=True, automatic_count=2000, requested_engine_on=True)
        receiver.consume(0o11, ENGINE_OFF)
        self.assertFalse(receiver.enabled)
        self.assertEqual(receiver.automatic_count, 2000)
        for _ in range(4096):
            receiver.consume(THRUST_COUNTER_CHANNEL, MOUT)
        self.assertEqual(receiver.automatic_count, 0)
        self.assertEqual(receiver.commanded_thrust_n, MIN_THRUST_N)

    def test_disarming_resets_physical_automatic_counter(self):
        receiver = DpsReceiver(armed=True, automatic_count=100, requested_engine_on=True)
        receiver.set_hardware(armed=False)
        self.assertFalse(receiver.enabled)
        self.assertEqual(receiver.automatic_count, 0)
        receiver.consume(THRUST_COUNTER_CHANNEL, POUT)
        self.assertEqual(receiver.automatic_count, 0)

    def test_manual_minimum_is_separate_from_automatic_offset(self):
        receiver = DpsReceiver(armed=True, automatic_count=100)
        receiver.set_hardware(autothrottle=False)
        self.assertEqual(receiver.commanded_thrust_n, MIN_THRUST_N)
        receiver.consume(THRUST_COUNTER_CHANNEL, POUT)
        self.assertEqual(receiver.automatic_count, 100)

    def test_unrelated_dsky_bits_do_not_turn_engine_on(self):
        receiver = DpsReceiver(armed=True)
        receiver.consume(0o11, 0o7777)
        receiver.consume(0o14, 0o10)
        self.assertFalse(receiver.enabled)
        self.assertEqual(receiver.automatic_count, 0)

    def test_conflicting_and_malformed_commands_are_rejected(self):
        receiver = DpsReceiver(armed=True)
        for channel, value in ((0o11,ENGINE_ON|ENGINE_OFF),
                               (THRUST_COUNTER_CHANNEL, 2),
                               (0o11, -1), (True, 0), (0o11, True)):
            with self.assertRaises(ValueError):
                receiver.consume(channel, value)
        with self.assertRaises(ValueError):
            receiver.set_hardware(armed=1)


class PhysicalModelTests(unittest.TestCase):
    def plant(self, **kwargs):
        options = dict(source=SOURCE, tcl=TCL, runtime_manifest=MANIFEST,
                       position_ref_m=(1753090, 0, 0), velocity_ref_m_s=(0, 0, 0))
        options.update(kwargs)
        return PropulsionPlant(**options)

    def test_original_plant_force_mass_and_fuel_units(self):
        with self.plant(mu_m3_s2=0) as plant:
            observation = plant.step(.01, enabled=True, thrust_n=MAX_THRUST_N)
        self.assertAlmostEqual(observation['acceleration_body_x_m_s2'], MAX_THRUST_N/15000)
        self.assertAlmostEqual(observation['mass_flow_kg_s'], MAX_THRUST_N/3050)
        self.assertAlmostEqual(observation['mass_kg'],15000-MAX_THRUST_N*.01/3050)
        self.assertAlmostEqual(observation['fuel_kg'],8355-MAX_THRUST_N*.01/3050)
        self.assertAlmostEqual(observation['delta_v_body_m_s'][0], MAX_THRUST_N*.01/15000)
        self.assertEqual(observation['delta_v_body_m_s'][1:], [0,0])

    def test_zero_specific_force_free_fall_changes_inertial_velocity(self):
        with self.plant() as plant:
            observation = plant.step(.01, enabled=False, thrust_n=0)
        self.assertEqual(observation['specific_force_ref_m_s2'], [0,0,0])
        self.assertLess(observation['velocity_ref_m_s'][0], 0)
        self.assertEqual(observation['mass_kg'], 15000)
        self.assertEqual(observation['fuel_kg'], 8355)
        self.assertEqual(observation['mass_flow_kg_s'], 0)

    def test_engine_disconnected_is_a_physical_negative_control(self):
        with self.plant(connected=False) as disconnected, self.plant() as zero:
            for _ in range(100):
                blocked = disconnected.step(.01, enabled=True, thrust_n=MAX_THRUST_N)
                free = zero.step(.01, enabled=False, thrust_n=0)
        for key in ('position_ref_m','velocity_ref_m_s','specific_force_ref_m_s2',
                    'mass_kg','fuel_kg'):
            self.assertEqual(blocked[key], free[key])
        self.assertEqual(blocked['delivered_thrust_n'], 0)
        self.assertEqual(blocked['commanded_thrust_n'], MAX_THRUST_N)

    def test_rotated_body_thrust_uses_phase7_quaternion_matrix(self):
        half = math.sqrt(.5)
        with self.plant(mu_m3_s2=0, quaternion_body_to_ref=(half,0,half,0)) as plant:
            observation = plant.step(.01,enabled=True,thrust_n=15000)
        self.assertAlmostEqual(observation['specific_force_ref_m_s2'][0],0,places=12)
        self.assertAlmostEqual(observation['specific_force_ref_m_s2'][1],0,places=12)
        self.assertAlmostEqual(observation['specific_force_ref_m_s2'][2],-1,places=12)
        self.assertAlmostEqual(observation['velocity_ref_m_s'][2],-.01,places=12)
        self.assertAlmostEqual(observation['position_ref_m'][2],-.00005,places=12)

    def test_acceleration_direction_is_not_velocity_direction(self):
        with self.plant(mu_m3_s2=0,velocity_ref_m_s=(-100,0,0)) as plant:
            observation = plant.step(.01,enabled=True,thrust_n=15000)
        self.assertGreater(observation['total_acceleration_ref_m_s2'][0],0)
        self.assertLess(observation['velocity_ref_m_s'][0],0)
        self.assertLess(observation['position_ref_m'][0],1753090)

    def test_ballistic_translation_matches_analytic_motion(self):
        initial_r=(1753090,10,20)
        initial_v=(4,-3,2)
        with self.plant(mu_m3_s2=0,position_ref_m=initial_r,velocity_ref_m_s=initial_v) as plant:
            for _ in range(100):
                observation=plant.step(.01,enabled=False,thrust_n=0)
        for i in range(3):
            self.assertAlmostEqual(observation['position_ref_m'][i],initial_r[i]+initial_v[i],places=7)
            self.assertEqual(observation['velocity_ref_m_s'][i],initial_v[i])

    def test_first_step_acceleration_matches_analytic_position(self):
        with self.plant(mu_m3_s2=0) as plant:
            observation=plant.step(.01,enabled=True,thrust_n=15000)
        self.assertAlmostEqual(observation['position_ref_m'][0],1753090+.5*.01**2,places=8)
        self.assertAlmostEqual(observation['velocity_ref_m_s'][0],.01,places=12)

    def test_mass_freezing_converges_toward_independent_rocket_equation(self):
        errors=[]
        for step in (.01,.005):
            with self.plant(mu_m3_s2=0) as plant:
                for _ in range(round(2/step)):
                    observation=plant.step(step,enabled=True,thrust_n=MAX_THRUST_N)
            expected=3050*math.log(15000/observation['mass_kg'])
            error=expected-observation['velocity_ref_m_s'][0]
            self.assertGreater(error,0)
            self.assertLess(error,0.00004)
            errors.append(error)
        self.assertLess(errors[1],errors[0]*.501)

    def test_central_gravity_direction_and_magnitude(self):
        r=(1000000,2000000,-3000000)
        g=gravity(r)
        magnitude=math.sqrt(sum(x*x for x in g))
        radius=math.sqrt(sum(x*x for x in r))
        self.assertAlmostEqual(magnitude,MOON_MU_M3_S2/radius**2)
        self.assertLess(sum(g[i]*r[i] for i in range(3)),0)
        self.assertAlmostEqual(g[0]*r[1]-g[1]*r[0],0)

    def test_velocity_verlet_preserves_circular_orbit_energy(self):
        radius=1753090
        speed=math.sqrt(MOON_MU_M3_S2/radius)
        initial_energy=-MOON_MU_M3_S2/(2*radius)
        with self.plant(velocity_ref_m_s=(0,0,speed)) as plant:
            for _ in range(1000):
                observation=plant.step(.01,enabled=False,thrust_n=0)
        radius_end=math.sqrt(sum(x*x for x in observation['position_ref_m']))
        energy=sum(x*x for x in observation['velocity_ref_m_s'])/2-MOON_MU_M3_S2/radius_end
        self.assertLess(abs((energy-initial_energy)/initial_energy),1e-11)

    def test_identical_runs_have_identical_modern_physics_trace(self):
        traces=[]
        for _ in range(2):
            with self.plant() as plant:
                trace=[plant.step(.01,enabled=i>=5,thrust_n=10000) for i in range(20)]
                traces.append(json.dumps(trace,sort_keys=True))
        self.assertEqual(traces[0],traces[1])

    def test_invalid_frames_and_unbounded_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            self.plant(quaternion_body_to_ref=(1,1,0,0))
        with self.plant() as plant:
            for dt,force in ((0,0),(-.01,0),(.1,0),(.01,-1),(.01,MAX_THRUST_N+1),(.01,float('nan'))):
                with self.assertRaises(ValueError):
                    plant.step(dt,enabled=True,thrust_n=force)
        with self.assertRaises(ValueError):
            gravity((0,0,0))

    def test_fuel_exhaustion_is_rejected_not_silently_integrated(self):
        with self.plant(fuel_kg=.001) as plant:
            with self.assertRaisesRegex(ValueError,'Fuel|fuel'):
                plant.step(.01,enabled=True,thrust_n=MAX_THRUST_N)

    def test_original_source_integrity_guard_rejects_changed_model(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)
            (source/Path(MODEL).parent).mkdir(parents=True)
            (source/MODEL).write_text('proc dynamic_simulation {} {}\n')
            with self.assertRaisesRegex(ValueError,'source mismatch'):
                LegacyEngine(source=source,tcl=TCL)

    def test_phase11_sensor_sees_force_not_gravity(self):
        sys.path.insert(0,str(ROOT/'docs/phase11-evidence'))
        from pipa_sensor import PipaSensor, MCT_SECONDS
        cycles=800 # 0.009375 seconds, exact AGC MCT timing.
        dt=float(cycles*MCT_SECONDS)
        with self.plant() as plant:
            observation=plant.step(dt,enabled=True,thrust_n=32768)
        sensor=PipaSensor()
        interval=sensor.sample(cycles,total_acceleration_m_s2=observation['total_acceleration_ref_m_s2'],
                               gravity_m_s2=observation['gravity_ref_m_s2'])
        # 32768/15000 * .009375 = .02048 m/s; avoid an exact threshold
        # where upstream binary floating point may put .02 just below two pulses.
        self.assertEqual(interval.generated_counts,(2,0,0))
        self.assertAlmostEqual(float(interval.delta_v_stable_m_s[0]),.02048,places=12)
        free=PipaSensor().sample(cycles,total_acceleration_m_s2=observation['gravity_ref_m_s2'],
                                gravity_m_s2=observation['gravity_ref_m_s2'])
        self.assertEqual(free.events,())


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--tcl',type=Path,required=True)
    parser.add_argument('--runtime-manifest',type=Path)
    args,other=parser.parse_known_args()
    SOURCE,TCL,MANIFEST=args.source,args.tcl,args.runtime_manifest
    unittest.main(argv=[sys.argv[0],*other])
