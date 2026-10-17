"""Concrete retained-execution checks; no claim of a completed spacecraft loop."""
import hashlib,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def records(name):return [json.loads(x) for x in (HERE/'runs'/f'{name}.stdout').read_text().splitlines()]
class ControlEvidence(unittest.TestCase):
 def test_prior_evidence_preserved(self):
  hashes=json.loads((HERE/'prior_hashes.json').read_text());self.assertEqual(len(hashes),78)
  for name,digest in hashes.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
 def test_phase3_not_a_thruster_experiment(self):
  for name in ['positive','repeat','open','blocked','negative']:
   r=[json.loads(x) for x in (ROOT/'docs/phase3-evidence/runs'/f'{name}.stdout').read_text().splitlines()]
   rcs=[x for x in r if x['ev']=='output' and x['channel'] in (5,6)]
   self.assertGreater(len(rcs),0);self.assertEqual(sum(x['value']!=0 for x in rcs),0)
 def test_probe_inputs_received(self):
  r=records('probe');inputs=[x for x in r if x['ev']=='input']
  self.assertEqual(len(inputs),21);self.assertTrue(all(x['accepted']>0 for x in inputs))
  self.assertEqual(r[0]['ram_writes'],0);self.assertEqual(r[-1]['modreg'],0)
  self.assertTrue(any(x['channel']==0o167 and x['value']==20 for x in inputs))
 def test_source_readiness_blocks_actuation(self):
  r=records('probe');check=[x for x in r if x['ev']=='checkpoint']
  self.assertEqual(sum(x['z']==0o2046 for x in check),0)
  self.assertEqual(sum(x['z']==0o2163 for x in check),469)
  c=next(x for x in check if x['z']==0o2000 and x['cycle']>2700001)
  self.assertEqual(c['chan31']&0o30000,0o20000)
  self.assertEqual(c['chan30']&0o1000,0)
  self.assertEqual(c['imodes33']&0o40,0o40)
  self.assertEqual(c['dapbools']&4,4)
  rcs=[x for x in r if x['ev']=='output' and x['channel'] in (5,6)]
  self.assertEqual(len(rcs),942);self.assertTrue(all(x['value']==0 for x in rcs))
 def test_replay(self):
  self.assertEqual((HERE/'runs/probe.stdout').read_bytes(),(HERE/'runs/repeat.stdout').read_bytes())
 def test_component_yaw_sign_and_sensor(self):
  rows=(HERE/'runs/component.stdout').read_text().splitlines();self.assertEqual(len(rows),3)
  parsed={}
  for line in rows:
   values={t.split('=',1)[0]:t.split('=',1)[1] for t in line.split() if '=' in t};parsed[values['MODE']]=values
  self.assertAlmostEqual(float(parsed['positive']['OMEGA_YAW']),0.49312402726613486,places=12)
  self.assertAlmostEqual(float(parsed['negative']['OMEGA_YAW']),-0.49312402726613486,places=12)
  self.assertEqual(int(parsed['positive']['PACKETS']),4);self.assertEqual(parsed['positive']['FIRST'],'PCDU')
  self.assertEqual(int(parsed['negative']['PACKETS']),4);self.assertEqual(parsed['negative']['FIRST'],'MCDU')
  self.assertEqual(float(parsed['blocked']['OMEGA_YAW']),0);self.assertEqual(int(parsed['blocked']['PACKETS']),0)
if __name__=='__main__':unittest.main()