"""Native original-Comanche alignment and external instrument causal controls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest

from backend.cmc_alignment import (CATALOG, SEPARATION, STARS, CmcAlignmentProcess,
                                    prepare_alignment_assets, _los)
from backend.cmc_native import ROPE_SHA256, PERIOD

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'docs/earth-departure-evidence/experiments/run_validation.py'


class OriginalCmcAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='apollo-cmc-alignment-')
        cls.base=Path(cls.tmp.name)
        cls.assets=prepare_alignment_assets(cls.base/'assets')
        cls.spec=cls.base/'assets.json'
        cls.spec.write_text(json.dumps(cls.assets))
        cls.runs={}
        for mode in ('connected','repeat','feedback-off','mark-irq-off','imu-off',
                     'bad-sighting','no-torque-approval','ui-quantized'):
            folder=cls.base/mode
            process=subprocess.run([sys.executable,'-B',str(RUNNER),'--out',str(folder),
                '--mode',mode,'--assets',str(cls.spec)],cwd=ROOT,capture_output=True,text=True,timeout=30)
            if process.returncode:
                raise AssertionError(process.stderr or process.stdout)
            cls.runs[mode]=json.loads((folder/'summary.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_fixed_catalog_geometry_preserves_original_star_separation(self):
        a,b=[_los(s['shaftDeg'],s['trunnionDeg'])for s in STARS]
        measured=math.degrees(math.acos(sum(x*y for x,y in zip(a,b))))
        self.assertAlmostEqual(measured,SEPARATION,places=9)
        self.assertAlmostEqual(SEPARATION,61.04741080287203,places=9)
        self.assertEqual([s['code']for s in STARS],['30','37'])

    def test_boot_reference_is_computed_by_original_p51_and_not_p52_success(self):
        frames=json.loads((self.base/'connected/frames.json').read_text())
        initial=frames[0]['computer']
        self.assertEqual(initial['dsky']['PROG'],'00')
        instruments=initial['instruments']
        self.assertTrue(instruments['alignment']['referenceInitialized'])
        self.assertFalse(instruments['alignment']['p52Complete'])
        self.assertEqual([m['program']for m in instruments['marks']],['51','51'])
        self.assertTrue(any(instruments['referenceMatrixWords']))
        matrix=instruments['referenceMatrix']['values']
        for row in matrix:self.assertAlmostEqual(sum(v*v for v in row),1,places=6)
        # Independently compare the original computed inertial-to-SM matrix
        # against the physical catalog sight directions and original NB tilt.
        for star,vector in zip(STARS,CATALOG):
            raw=_los(star['shaftDeg'],star['trunnionDeg'])
            physical=[.8431756920*raw[0]+.5376381241*raw[2],raw[1],
                      -.5376381241*raw[0]+.8431756920*raw[2]]
            computed=[sum(row[k]*vector[k]for k in range(3))for row in matrix]
            error=math.degrees(math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(physical,computed))))))
            self.assertLess(error,.05)
        self.assertEqual(instruments['checkpoints'][0]['kind'],'p51-star-fit')
        self.assertLessEqual(int(instruments['checkpoints'][0]['dsky']['R1']),5)

    def test_original_p52_optical_fit_torques_feedback_and_completion(self):
        summary=self.runs['connected'];alignment=summary['alignment']
        self.assertTrue(alignment['p52Complete'])
        self.assertEqual(alignment['p52Marks'],2)
        self.assertTrue(alignment['torqueApproved'])
        self.assertEqual(alignment['torqueOutputCount'],3)
        self.assertGreater(alignment['gyroSensorFeedbackOperations'],0)
        self.assertEqual(summary['finalDsky']['PROG'],'00')
        self.assertEqual(summary['encoderReadback']['CDUY'],1)
        self.assertEqual(summary['encoderReadback']['CDUZ'],32767)
        self.assertEqual([p['axis']for p in summary['gyroOutputs']],['Y','Z','X'])
        self.assertTrue(all(p['channel']==0o177 for p in summary['gyroOutputs']))
        self.assertIn('p52-star-fit',[p['kind']for p in summary['checkpoints']])
        self.assertIn('p52-completion-display',[p['kind']for p in summary['checkpoints']])

    def test_feedback_disconnected_does_not_certify_alignment(self):
        summary=self.runs['feedback-off']
        self.assertEqual(summary['alignment']['torqueOutputCount'],3)
        self.assertFalse(summary['alignment']['p52Complete'])
        self.assertEqual(summary['alignment']['gyroSensorFeedbackOperations'],0)
        self.assertEqual([summary['encoderReadback'][k]for k in ('CDUX','CDUY','CDUZ')],[0,0,0])

    def test_mark_packet_without_hardware_edge_leaves_original_waiting(self):
        summary=self.runs['mark-irq-off']
        self.assertEqual(summary['finalDsky']['PROG'],'52')
        self.assertEqual(summary['finalDsky']['VERB'],'51')
        self.assertFalse(summary['alignment']['p52Complete'])
        self.assertEqual(summary['alignment']['torqueOutputCount'],0)

    def test_imu_off_remains_an_original_00210_alarm(self):
        summary=self.runs['imu-off']
        self.assertEqual(summary['finalDsky']['R1'],'00210')
        self.assertFalse(summary['alignment']['referenceInitialized'])
        self.assertFalse(summary['alignment']['p52Complete'])

    def test_original_n93_requires_operator_approval(self):
        summary=self.runs['no-torque-approval']
        self.assertEqual((summary['finalDsky']['VERB'],summary['finalDsky']['NOUN']),('06','93'))
        self.assertFalse(summary['alignment']['torqueApproved'])
        self.assertEqual(summary['alignment']['torqueOutputCount'],0)
        self.assertFalse(summary['alignment']['p52Complete'])

    def test_bad_optical_sighting_is_not_a_success_certificate(self):
        summary=self.runs['bad-sighting']
        fit=next(p for p in summary['checkpoints']if p['kind']=='p52-star-fit')
        self.assertGreater(int(fit['dsky']['R1']),5)
        self.assertFalse(summary['alignment']['p52Complete'])

    def test_fresh_native_replay_is_byte_identical(self):
        self.assertEqual(self.runs['connected']['traceSha256'],self.runs['repeat']['traceSha256'])
        self.assertEqual((self.base/'connected/trace.jsonl').read_bytes(),
                         (self.base/'repeat/trace.jsonl').read_bytes())

    def test_practical_104_point_4_degree_controller_target_completes(self):
        self.assertTrue(self.runs['ui-quantized']['alignment']['p52Complete'])

    def test_source_identity_clock_and_scope_remain_explicit(self):
        frames=json.loads((self.base/'connected/frames.json').read_text())
        for frame in frames:
            computer=frame['computer']
            self.assertEqual(computer['provenance']['ropeSha256'],ROPE_SHA256)
            self.assertIs(computer['provenance']['hostFlightMemoryWrites'],False)
            self.assertIsNone(computer['flightState'])
            self.assertIs(computer['historicalCheckpointLoaded'],False)
            self.assertAlmostEqual(computer['cpuSeconds'],computer['cycle']*PERIOD,places=9)

    def test_invalid_instrument_requests_do_not_advance_original_clock(self):
        computer=CmcAlignmentProcess(self.assets,self.base/'invalid')
        try:
            before=computer.boot()
            requests=[('power_imu',1),('optics_mode','CMC'),('optics_mode','FAKE'),
                ('optics_slew',{'shaft':float('nan'),'trunnion':0,'rate':'HIGH','seconds':1}),
                ('optics_slew',{'shaft':1,'trunnion':0,'rate':'HIGH','seconds':2}),
                ('mark','ENTER'),('teleport',{'target':'moon'})]
            for action,value in requests:
                with self.subTest(action=action,value=value):
                    with self.assertRaises(ValueError):computer.instrument(action,value)
                    self.assertEqual(computer.advance(0)['cycle'],before['cycle'])
        finally:computer.close()

    def test_zero_switch_uses_original_counter_zeroing_and_manual_returns(self):
        computer=CmcAlignmentProcess(self.assets,self.base/'zero')
        try:
            computer.boot()
            zero=computer.instrument('optics_mode','ZERO')['computer']
            self.assertEqual(zero['instruments']['encoderReadback']['CDUS'],0)
            self.assertEqual(zero['instruments']['encoderReadback']['CDUT'],25568)
            self.assertEqual(zero['instruments']['trunnionDeg'],0)
            computer.instrument('optics_mode','MANUAL')
            jog=computer.instrument('optics_slew',{'shaft':1,'trunnion':1,'rate':'HIGH','seconds':.1})['computer']
            self.assertAlmostEqual(jog['instruments']['shaftDeg'],2)
            self.assertAlmostEqual(jog['instruments']['trunnionDeg'],1)
        finally:computer.close()

    def test_controller_motion_takes_reported_cpu_time(self):
        computer=CmcAlignmentProcess(self.assets,self.base/'timing')
        try:
            before=computer.boot()
            after=computer.instrument('optics_slew',{'shaft':1,'trunnion':0,'rate':'HIGH','seconds':1})['computer']
            self.assertAlmostEqual(after['cpuSeconds']-before['cpuSeconds'],1,places=5)
            self.assertAlmostEqual(after['instruments']['shaftDeg'],20)
        finally:computer.close()


if __name__=='__main__':unittest.main()
