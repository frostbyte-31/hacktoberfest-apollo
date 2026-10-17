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
    def test_thrust_counter_written_once_at_v37(self):
        changes = [(s['cycle'], s['THRUST']) for a, s in zip(S, S[1:]) if a['THRUST'] != s['THRUST']]
        self.assertEqual(changes, [(491517, 0o77777), (3130557, 0o67777)])
    def test_channel014_bit4_drive_at_v37(self):
        drives = [(r['cycle'], r['value']) for r in R if r['ev'] == 'output' and r['channel'] == 0o14 and r['value'] & 0o10]
        self.assertEqual(drives, [(495, 0o10), (3129803, 0o70010)])

if __name__ == '__main__': unittest.main()
