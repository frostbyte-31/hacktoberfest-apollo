"""Concrete evidence checks; run with python3 -m unittest discover here."""
import unittest,json
from pathlib import Path
P=Path(__file__).parent
class ValidationTests(unittest.TestCase):
    def test_identical_initial_conditions_and_outputs(self):
        for scenario,cycles in [('clock',2300000),('p63',2600000)]:
            native=(P/f'41_native_{scenario}.jsonl').read_bytes()
            self.assertEqual(native,(P/f'42_wasm_{scenario}.jsonl').read_bytes())
            self.assertEqual(native,(P/f'44_browser_{scenario}.jsonl').read_bytes())
            self.assertEqual(json.loads(native.splitlines()[-1])['cycle'],cycles)
    def test_p63_readiness_failure_not_descent(self):
        records=[json.loads(l) for l in (P/'41_native_p63.jsonl').read_text().splitlines()]
        checkpoints=[r for r in records if r['ev']=='checkpoint']
        self.assertTrue(any(r['bank']==0o32 and r['z']==0o2776 for r in checkpoints))
        self.assertTrue(any(r['bank']==4 and r['z']==0o3267 for r in checkpoints))
        self.assertFalse(any(r['bank']==0o14 and r['z']==0o3135 for r in checkpoints))
        self.assertIn('FAILREG=1107,210,0',(P/'47_p63_final_memory.txt').read_text())
if __name__=='__main__':unittest.main()