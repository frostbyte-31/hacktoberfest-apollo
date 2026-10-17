"""Checks over the retained Phase 8 trace (run from this directory: python3 test_p63_probe.py)."""
from pathlib import Path
import json, unittest
R = [json.loads(l) for l in (Path(__file__).resolve().parent / 'runs/p63.jsonl').read_text().splitlines()]
S = [r for r in R if r['ev'] == 'sample']

class P63Probe(unittest.TestCase):
    def test_keys_accepted(self):
        self.assertTrue(all(r['accepted'] > 0 for r in R if r['ev'] == 'input'))
    def test_p63_selected(self):
        self.assertEqual(S[-1]['MODREG'], 0o77)
    def test_imu_usable_before_selection(self):
        self.assertEqual(next(s for s in S if s['MODREG'] == 0o77)['IMODES33'] & 0o40, 0)
    def test_r02_refsmmat_alarm(self):
        self.assertEqual([S[-1]['FAILREG0'], S[-1]['FAILREG1']], [0o1520, 0o220])
    def test_refsmflg_absent(self):
        self.assertEqual(S[-1]['FLAGWRD3'] & 0o10000, 0)
    def test_thrust_counter_untouched(self):
        self.assertTrue(all(s['THRUST'] == 0o67777 for s in S))
    def test_no_thrust_drive_after_selection(self):
        self.assertFalse(any(r['ev'] == 'output' and r['channel'] == 0o14 and r['value'] & 0o10 and r['cycle'] > 3000000 for r in R))

if __name__ == '__main__': unittest.main()
