"""Read actual startup captures; these assertions do not establish descent readiness."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
RUN = Path(os.environ.get('APOLLO_STARTUP_RUN_DIR',HERE/'runs/verified'))
spec = importlib.util.spec_from_file_location('milestone2_startup_runner',HERE/'run_validation.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((RUN/'summary.json').read_text())
        cls.rows = {n:runner.read_trace(RUN/(n+'.stdout')) for n in cls.summary}

    def test_original_sources_have_pinned_provenance(self):
        manifest=json.loads((HERE/'source/manifest.json').read_text())
        self.assertEqual(manifest['upstream_revision'],runner.REVISION)
        self.assertEqual(len(manifest['files']),3)
        for name,row in manifest['files'].items():
            self.assertIn('/'+runner.REVISION+'/',row['url'])
            self.assertEqual(runner.digest(HERE/'source'/name),row['sha256'])

    def test_addresses_agree_with_rope_and_erasable_source(self):
        mapping=runner.resolve_addresses(ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin')
        self.assertEqual(mapping,json.loads((RUN/'resolved_addresses.json').read_text()))

    def test_cold_boot_takes_zero_pair_failure_path(self):
        rows=self.rows['delayed']
        check=next(r for r in rows if r['ev']=='before' and r['bank']==5 and r['z']==0o3005)
        self.assertEqual((check['a'],check['mpac5'],check['phase_pairs']),(0,5,[0]*12))
        self.assertEqual(self.summary['delayed']['ptbad_cycles'],[526])
        self.assertEqual(self.summary['delayed']['failreg_changes'][1],{'cycle':553,'failreg':[0o1107,0,0]})

    def test_original_fresh_start_clears_alarm_and_stays_clear(self):
        rows=self.rows['delayed']
        clean=next(r['cycle'] for r in rows if r['ev']=='state' and r['cycle']>490664 and not any(r['failreg']))
        self.assertEqual(clean,491361)
        self.assertTrue(all(r['failreg']==[0,0,0] for r in rows if r['ev'] in ('state','sample') and r['cycle']>=clean))

    def test_ready_observed_before_first_delayed_v37_key(self):
        rows=self.rows['delayed']
        ready=next(r for r in rows if r['ev']=='before' and r['bank']==6 and r['z']==0o2327 and not r['imodes33']&32)
        self.assertFalse(ready['imodes30']&32)
        self.assertEqual(ready['cycle'],1480208)
        self.assertLess(ready['cycle'],1600000)
        self.assertLess(self.summary['delayed']['first_startdap'],1600000)

    def test_late_v37_enters_p00_with_no_recorded_alarms(self):
        summary=self.summary['delayed']
        self.assertIsNone(summary['first_cantroo'])
        self.assertEqual(summary['first_modreg_p00_after_startup'],1729504)
        self.assertEqual(summary['last_state']['modreg'],0)
        self.assertEqual(summary['last_state']['failreg'],[0,0,0])

    def test_legacy_and_premature_keys_hit_original_rejection(self):
        for name in ('legacy','v37_before_ready'):
            summary=self.summary[name]
            self.assertIsNotNone(summary['first_cantroo'])
            self.assertEqual(summary['last_state']['modreg'],0o77777)
            self.assertEqual(summary['last_state']['failreg'],[0o1520,0,0])
            gate=next(r for r in self.rows[name] if r['ev']=='before' and r['bank']==4 and r['z']==0o2045)
            self.assertEqual(gate['a'],32)

    def test_after_ready_control_accepts_p00(self):
        summary=self.summary['v37_after_ready']
        self.assertIsNone(summary['first_cantroo'])
        self.assertEqual(summary['last_state']['modreg'],0)
        self.assertEqual(summary['last_state']['failreg'],[0,0,0])

    def test_imu_off_p00_is_not_dap_readiness(self):
        summary=self.summary['imu_off']
        self.assertEqual(summary['last_state']['modreg'],0)
        self.assertIsNone(summary['first_startdap'])
        self.assertIsNone(summary['first_issup_clear'])
        self.assertTrue(summary['last_state']['imodes33']&32)

    def test_no_v36_does_not_clear_expected_cold_alarm(self):
        summary=self.summary['without_v36']
        self.assertEqual(summary['last_state']['modreg'],0)
        self.assertEqual(summary['last_state']['failreg'],[0o1107,0,0])
        self.assertFalse(any(r['ev']=='input' and 426665<=r['cycle']<=490664 for r in self.rows['without_v36']))

    def test_exact_replay_and_raw_hashes(self):
        self.assertEqual((RUN/'delayed.stdout').read_bytes(),(RUN/'repeat.stdout').read_bytes())
        for name,summary in self.summary.items():
            self.assertEqual(runner.digest(RUN/(name+'.stdout')),summary['raw_sha256'])

    def test_no_counter_or_vehicle_stimulus(self):
        for name,rows in self.rows.items():
            self.assertEqual(rows[0]['ram_writes'],0)
            self.assertFalse(rows[0]['vehicle_model'])
            self.assertEqual(rows[0]['counter_packets'],0)
            self.assertEqual(self.summary[name]['nonzero_jet_words'],0)
            self.assertTrue(all(r['cdu']==[0,0,0] for r in rows if r['ev'] in ('sample','state')))
            self.assertTrue(all(r['channel'] in (13,24,25) for r in rows if r['ev']=='input'))

    def test_command_records_are_completed_and_timestamped(self):
        commands=json.loads((RUN/'commands.json').read_text())
        self.assertEqual(len(commands),9)
        for row in commands:
            self.assertEqual(row['exit'],0)
            self.assertTrue(row['start_utc']<=row['end_utc'])
        self.assertTrue(json.loads((RUN/'validation.json').read_text())['all_pass'])

if __name__=='__main__':
    unittest.main()
