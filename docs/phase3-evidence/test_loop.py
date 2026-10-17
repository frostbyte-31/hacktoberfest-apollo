"""Concrete causal checks against captured, genuinely executed transcripts."""
import hashlib, json, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def load(name):
    return [json.loads(line) for line in (HERE/'runs'/f'{name}.stdout').read_text().splitlines()]
class LoopEvidence(unittest.TestCase):
    def test_sensor_reception(self):
        r=load('positive'); inputs=[x for x in r if x['ev']=='sensor']
        self.assertEqual(len(inputs),912)
        self.assertTrue(all(x['accepted']>0 and x['channel']==0o232 and x['operation']==0o21 for x in inputs))
        self.assertEqual(r[-1]['cdu'],[912,0,0])
    def test_actuator_changes_plant(self):
        r=load('positive'); plant=[x for x in r if x['ev']=='plant']
        self.assertEqual(sum(x['drive_pulses'] for x in plant),228)
        self.assertAlmostEqual(plant[-1]['angle_degrees'],228*0.043948,places=9)
        for x in plant:
            self.assertTrue(any(y['ev']=='output' and y['channel']==0o174 and y['cycle']==x['cycle'] and y['value']==x['drive_pulses'] for y in r))
        blocked=load('blocked')
        self.assertEqual(sum(x['ev']=='blocked' for x in blocked),10)
        self.assertEqual(blocked[-1]['position_counts'],[0,0,0])
    def test_return_measurement_and_agc_response(self):
        r=load('positive')
        first_plant=next(x for x in r if x['ev']=='plant')
        first_sensor=next(x for x in r if x['ev']=='sensor')
        first_changed=next(x for x in r if x['ev']=='sample' and x['cdu'][0]>0)
        self.assertLessEqual(first_plant['cycle'],first_sensor['cycle'])
        self.assertLess(first_sensor['cycle'],first_changed['cycle'])
        good=[x for x in r if x['ev']=='checkpoint' and x['z']==0o3636]
        self.assertEqual(len(good),1)
        self.assertEqual(good[0]['target'],[910,0,0])
        self.assertEqual(good[0]['cdu'],[912,0,0])
        self.assertEqual(r[-1]['failreg'],[0o1107,0,0])
    def test_disconnected_feedback_fails(self):
        for name in ['open','blocked']:
            r=load(name)
            self.assertEqual(r[-1]['cdu'],[0,0,0])
            self.assertEqual(r[-1]['failreg'],[0o1107,0o211,0])
            self.assertTrue(any(x['ev']=='checkpoint' and x['z']==0o3637 for x in r))
            self.assertFalse(any(x['ev']=='checkpoint' and x['z']==0o3636 for x in r))
        self.assertEqual(load('open')[-1]['position_counts'],[912,0,0])
    def test_negative_sign(self):
        r=load('negative')
        self.assertEqual(r[-1]['position_counts'],[-912,0,0])
        self.assertEqual(r[-1]['cdu'],[32768-912,0,0])
        self.assertTrue(all(x['operation']==0o23 for x in r if x['ev']=='sensor'))
        self.assertTrue(any(x['ev']=='checkpoint' and x['z']==0o3636 for x in r))
    def test_reproducible(self):
        self.assertEqual((HERE/'runs/positive.stdout').read_bytes(),(HERE/'runs/repeat.stdout').read_bytes())
    def test_prior_evidence_unchanged(self):
        hashes=json.loads((HERE/'prior_hashes.json').read_text())
        self.assertGreater(len(hashes),30)
        for name,digest in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
if __name__=='__main__': unittest.main()