"""GPL-2.0-or-later. Assertions over actual retained native Phase 8 evidence."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=HERE/'runs/attempt-03'

def raw(directory,name):
    path=directory/name
    return path.read_bytes() if path.exists() else gzip.decompress(path.with_name(path.name+'.gz').read_bytes())

def trace(name):
    return [json.loads(line) for line in raw(RUN,name).splitlines()]

class FeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p63=trace('p63.stdout');cls.baseline=trace('baseline.stdout')
        cls.states=[r for r in cls.p63 if r['ev'] in ('sample','state')]
        cls.checkpoints=[r for r in cls.p63 if r['ev']=='before']

    def test_all_prior_tracked_documentation_preserved(self):
        hashes=json.loads((HERE/'prior_hashes.json').read_text())
        self.assertEqual(len(hashes),3268)
        for name,expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)

    def test_lossless_packaging_all_attempts(self):
        for directory in sorted((HERE/'runs').iterdir()):
            manifest=json.loads((directory/'retention.json').read_text())
            for name,record in manifest['files'].items():
                retained=(directory/record['retained_name']).read_bytes()
                self.assertEqual(hashlib.sha256(retained).hexdigest(),record['retained_sha256'],name)
                unpacked=gzip.decompress(retained) if record['retained_name'].endswith('.gz') else retained
                self.assertEqual(hashlib.sha256(unpacked).hexdigest(),record['raw_sha256'],name)
                self.assertEqual(len(unpacked),record['raw_bytes'],name)

    def test_unmodified_phase5_baseline_reproduced(self):
        self.assertEqual(raw(RUN,'phase5-operate.stdout'),(ROOT/'docs/phase5-evidence/runs/operate.stdout').read_bytes())
        self.assertEqual(raw(RUN,'baseline.inputs.txt'),(ROOT/'docs/phase5-evidence/operate_inputs.txt').read_bytes())
        self.assertEqual([r for r in self.baseline if r.get('cycle',0)<2200000],
                         [r for r in self.p63 if r.get('cycle',0)<2200000])

    def test_only_added_stimuli_are_normal_v37e63e_keys(self):
        take=lambda rows:[(r['cycle'],r['channel'],r['value']) for r in rows if r['ev']=='input']
        added=[(2200000+i*21333,0o15,key) for i,key in enumerate((17,3,7,28,6,3,28))]
        self.assertEqual(take(self.p63),sorted(take(self.baseline)+added))
        self.assertTrue(all(r['accepted']>0 for r in self.p63 if r['ev']=='input'))
        self.assertTrue(all(not ch&128 for _,ch,_ in take(self.p63)))
        self.assertEqual(self.p63[0]['ram_writes'],0)

    def test_p63_selected_but_refsm_readiness_rejected(self):
        entries=[r for r in self.checkpoints if r['bank']==0o32 and r['z']==0o2776]
        checks=[r for r in self.checkpoints if r['bank']==4 and r['z']==0o3254]
        self.assertEqual(entries[0]['cycle'],2334707)
        self.assertTrue(checks)
        self.assertTrue(all(not r['flagword3']&0o10000 for r in checks))
        alarms=[r for r in self.checkpoints if r['bank']==4 and r['z']==0o3266]
        self.assertTrue(alarms)
        self.assertTrue(all(r['a']==0o220 for r in alarms))
        self.assertFalse(any(r['bank']==4 and r['z']==0o3270 for r in self.checkpoints))
        self.assertFalse(any(r['bank']==0o32 and r['z']==0o3002 for r in self.checkpoints))

    def test_alarm_history_is_not_erased(self):
        self.assertTrue(any(r['failreg']==[0o1107,0,0] for r in self.states))
        self.assertTrue(any(r['cycle']>490664 and r['failreg']==[0,0,0] for r in self.states))
        self.assertTrue(any(r['failreg']==[0o1520,0,0] for r in self.states))
        self.assertEqual(self.states[-1]['failreg'],[0o1520,0o220,0])
        self.assertEqual(self.states[-1]['modreg'],63)

    def test_throttle_signal_is_the_observed_engine_off_reset(self):
        stores=[r for r in self.checkpoints if r['bank']==0o36 and r['z']==0o3601 and r['cycle']>2200000]
        self.assertTrue(stores)
        # The accumulator is a sign-extended 16-bit central; THRUST stores SP15.
        self.assertTrue(all(r['a']==0o167777 and r['a']&0o77777==0o67777 for r in stores))
        change=next(r for r in self.states if r['cycle']>2200000 and r['thrust']==0o67777)
        signal=next(r for r in self.p63 if r['ev']=='output' and r['channel']==0o14
                    and r['cycle']>2200000 and r['value']&8)
        entry=next(r for r in self.checkpoints if r['bank']==0o32 and r['z']==0o2776)
        self.assertEqual((change['cycle'],signal['cycle']),(2331816,2331821))
        self.assertEqual(signal['value'],0o70010)
        self.assertLess(signal['cycle'],entry['cycle'])
        self.assertFalse(any(r['bank']==0o31 and r['z'] in (0o2216,0o2312) for r in self.checkpoints))

    def test_no_engine_on_output_after_request(self):
        self.assertFalse(any(r['ev']=='output' and r['channel']==0o11 and r['cycle']>=2200000
                             and r['value']&0o10000 for r in self.p63))
        self.assertFalse(self.p63[0]['vehicle_model'])

    def test_exact_replay_and_actual_execution_exit_codes(self):
        self.assertEqual(raw(RUN,'p63.stdout'),raw(RUN,'repeat.stdout'))
        commands=json.loads((RUN/'commands.json').read_text())
        self.assertEqual(len(commands),7)
        self.assertTrue(all(r['exit']==0 for r in commands))
        validation=json.loads((RUN/'validation.json').read_text())
        self.assertEqual(len(validation['checks']),15)
        self.assertTrue(validation['all_pass'])
        self.assertTrue(all(validation['checks'].values()))

    def test_development_driver_mistakes_are_preserved(self):
        first=json.loads((HERE/'runs/attempt-01/validation.json').read_text())
        second=json.loads((HERE/'runs/attempt-02/validation.json').read_text())
        self.assertFalse(first['all_pass']);self.assertFalse(second['all_pass'])
        self.assertFalse(first['checks']['only_added_input_is_v37e63e'])
        self.assertFalse(second['checks']['throttle_reset_is_engine_off_before_p63'])
        self.assertTrue(all(r['exit']==0 for r in json.loads((HERE/'runs/attempt-01/commands.json').read_text())))

if __name__=='__main__':unittest.main()
