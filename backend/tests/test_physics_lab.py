"""Real retained Tcl propulsion under educational manual commands, no AGC claim."""
import math
import os
from pathlib import Path
import tempfile
import unittest

from backend import native_session
from backend.final_assets import runtime_manifest
from backend.physics_lab import (DT, MOON_RADIUS_M, PhysicsLab, PROPULSION,
                                  SCENARIOS, THRESHOLDS, touchdown)


class PhysicsLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        folder = root/'.build/physics-lab-tests'
        folder.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=folder)
        manifest = os.environ.get('PHYSICS_LAB_RUNTIME_MANIFEST') or runtime_manifest()
        cls.assets = native_session.prepare_assets(output=Path(cls.temp.name)/'assets',
                                                   runtime_manifest=manifest)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_initial_data_units_frames_and_synthetic_provenance(self):
        with PhysicsLab(self.assets) as lab:
            state = lab.snapshot()
            self.assertEqual(state['mode'], 'EDUCATIONAL_PHYSICS_LAB')
            self.assertEqual(state['status'], 'ready')
            self.assertEqual(state['spacecraft']['positionM'], [MOON_RADIUS_M+150,0,0])
            self.assertEqual(state['spacecraft']['velocityMps'], [-5,0,1])
            self.assertEqual(state['spacecraft']['horizontalVelocityMps'],1)
            self.assertEqual(state['frame']['downrange'],'+Z')
            self.assertIn('upstream_source_sha256',state['provenance'])
            self.assertTrue(any('No AGC' in text for text in state['assumptions']))

    def test_commands_validate_atomically_and_never_set_vehicle_state(self):
        with PhysicsLab(self.assets) as lab:
            initial=lab.snapshot()
            for throttle,pitch in ((True,0),(.5,False),(math.nan,0),(0,math.inf),(-.01,0),(1.01,0),(0,-1.01),(0,1.01)):
                with self.assertRaises(ValueError):lab.command(throttle,pitch)
                self.assertEqual(lab.snapshot(),initial)
            lab.command(.5,-.5)
            self.assertEqual(lab.snapshot()['spacecraft'],initial['spacecraft'])
            for ticks in (True,0,-1,1.5,1001):
                with self.assertRaises(ValueError):lab.step(ticks)
        with self.assertRaises(ValueError):lab.command(0,0)
        with self.assertRaises(ValueError):PhysicsLab(self.assets,'invented')

    def test_free_fall_gravity_is_not_specific_force(self):
        with PhysicsLab(self.assets) as lab:
            initial=lab.snapshot()['spacecraft']
            state=lab.step(100)
            expected_g=PROPULSION.MOON_MU_M3_S2/(MOON_RADIUS_M+150)**2
            self.assertAlmostEqual(state['spacecraft']['velocityMps'][0],-5-expected_g,delta=.002)
            self.assertAlmostEqual(state['spacecraft']['positionM'][0],initial['positionM'][0]-5-.5*expected_g,delta=.01)
            self.assertEqual(state['spacecraft']['specificForceMps2'],[0,0,0])
            self.assertEqual(state['spacecraft']['fuelKg'],500)
            self.assertEqual(state['engine']['thrustN'],0)
            self.assertEqual(state['tick'],100)
            self.assertEqual(state['simTimeSeconds'],1)

    def test_retained_engine_force_mass_flow_and_motion(self):
        with PhysicsLab(self.assets) as lab:
            lab.command(1,0)
            state=lab.step(1)
            self.assertEqual(state['engine']['thrustN'],45040)
            self.assertAlmostEqual(state['spacecraft']['specificForceMps2'][0],45040/8000,places=11)
            self.assertAlmostEqual(state['engine']['massFlowKgps'],45040/3050,places=11)
            self.assertAlmostEqual(state['spacecraft']['fuelKg'],500-45040/3050*DT,places=10)
            self.assertAlmostEqual(state['engine']['thrustVectorN'][0],45040,places=8)
            self.assertGreater(state['spacecraft']['verticalSpeedMps'],-5)

    def test_pitch_motor_rotates_actual_force_and_neutral_damps_rate(self):
        with PhysicsLab(self.assets) as lab:
            lab.command(.4,1)
            state=lab.step(100)
            self.assertGreater(state['spacecraft']['pitchDeg'],0)
            self.assertLess(state['engine']['thrustVectorN'][2],0)
            self.assertAlmostEqual(sum(x*x for x in state['spacecraft']['quaternionBodyToRef']),1,places=12)
            omega=state['spacecraft']['angularVelocityRadps'][1]
            lab.command(.4,0)
            self.assertLess(lab.step(100)['spacecraft']['angularVelocityRadps'][1],omega)

    def test_fuel_exhaustion_is_real_partial_burn_without_negative_fuel(self):
        with PhysicsLab(self.assets,'low-fuel') as lab:
            lab.command(1,0)
            state=lab.step(1000)
            self.assertEqual(state['status'],'fuel_exhausted')
            self.assertGreaterEqual(state['spacecraft']['fuelKg'],0)
            self.assertLessEqual(state['spacecraft']['fuelKg'],1e-8)
            self.assertGreater(state['spacecraft']['altitudeM'],0)
            self.assertEqual(state['engine']['enabled'],False)
            self.assertAlmostEqual(lab.debrief()['fuelUsedKg'],15,delta=1e-8)
            self.assertEqual(lab.step(1),state)
            with self.assertRaises(ValueError):lab.command(0,0)

    def test_ballistic_surface_contact_is_actual_crash_without_position_snap(self):
        with PhysicsLab(self.assets) as lab:
            while lab.status not in ('crashed','landed'):
                state=lab.step(1000)
            self.assertEqual(state['status'],'crashed')
            self.assertFalse(state['outcome']['success'])
            self.assertLess(state['spacecraft']['altitudeM'],0)
            self.assertGreater(abs(state['spacecraft']['verticalSpeedMps']),THRESHOLDS['verticalSpeedMps'])
            self.assertEqual(state['spacecraft']['fuelKg'],500)
            self.assertEqual(lab.debrief()['finalState'],state)

    def test_manual_braking_can_reach_a_measured_soft_contact(self):
        # Independent test pilot, not a production guidance controller: command
        # force for gentle 0.075 m/s² outward acceleration and observe contact.
        with PhysicsLab(self.assets) as lab:
            for _ in range(1800):
                current=lab.snapshot()['spacecraft']
                gravity=math.sqrt(sum(g*g for g in current['gravityMps2']))
                force=(gravity+.075)*current['massKg']
                lab.command((force-PROPULSION.MIN_THRUST_N)/(PROPULSION.MAX_THRUST_N-PROPULSION.MIN_THRUST_N),0)
                state=lab.step(10)
                if state['status'] in ('landed','crashed','fuel_exhausted','timed_out'):break
            self.assertEqual(state['status'],'landed')
            self.assertTrue(state['outcome']['success'])
            self.assertLessEqual(state['spacecraft']['altitudeM'],0)
            self.assertLessEqual(abs(state['spacecraft']['verticalSpeedMps']),2)
            self.assertGreater(lab.debrief()['fuelUsedKg'],0)

    def test_repeated_fixed_step_runs_are_identical(self):
        with PhysicsLab(self.assets) as a,PhysicsLab(self.assets) as b:
            for throttle,pitch,ticks in ((.2,.5,50),(.5,0,100),(0,-.5,100),(.8,0,100)):
                a.command(throttle,pitch);b.command(throttle,pitch)
                self.assertEqual(a.step(ticks),b.step(ticks))
            self.assertEqual(a.debrief(),b.debrief())

    def test_synthetic_outcome_limits_report_measured_failures(self):
        safe={'verticalSpeedMps':-1,'horizontalSpeedMps':.5,'pitchDeg':2,'downrangeM':10}
        self.assertTrue(touchdown(safe)['success'])
        for field,value in (('verticalSpeedMps',-3),('horizontalSpeedMps',2),('pitchDeg',9),('downrangeM',80)):
            result=touchdown({**safe,field:value})
            self.assertFalse(result['success']);self.assertTrue(result['reasons'])


if __name__=='__main__':unittest.main(verbosity=2)
