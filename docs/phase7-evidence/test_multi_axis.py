"""Checks over retained Phase 7 raw traces (run: python3 -m unittest docs/phase7-evidence/test_multi_axis.py)."""
from pathlib import Path
import json, hashlib, unittest
RUN = Path(__file__).resolve().parent / 'runs'

def rows(m): return [json.loads(l) for l in (RUN / f'{m}.jsonl').read_text().splitlines()]
def plants(m): return [r for r in rows(m) if r['ev'] == 'plant']
def final_cdu(m): return [r for r in rows(m) if r['ev'] == 'sample'][-1]['cdu']
def jets(m): return [(r['cycle'], r['channel'], r['value']) for r in rows(m) if r['ev'] == 'output' and r['channel'] in (5, 6)]

class MultiAxis(unittest.TestCase):
    def test_single_axis_baseline_unchanged(self):
        self.assertEqual(hashlib.sha256((RUN / 'yaw_baseline.jsonl').read_bytes()).hexdigest(),
                         '9708a22c8066d2d829e756b5f3a865f0ab68a7ff5c27dae05403174944fdad99')
    def test_first_agc_channel005_word(self):
        first = next(r for r in rows('closed') if r['ev'] == 'output' and r['channel'] == 5 and r['value'])
        self.assertEqual((first['cycle'], first['value']), (2509765, 0o22))
    def test_no_channel006_in_pitch_run(self):
        self.assertFalse(any(v for _, c, v in jets('closed') if c == 6))
    def test_pitch_response_and_no_yaw(self):
        p = plants('closed')
        self.assertGreater(max(abs(r['omega'][1]) for r in p), 4.0)
        self.assertEqual(max(abs(r['omega'][0]) for r in p), 0)
    def test_roll_cross_axis_small(self):
        self.assertLess(max(abs(r['omega'][2]) for r in plants('closed')), 0.02)
    def test_connected_cdu_readback(self):
        self.assertEqual(final_cdu('closed'), [0, 1713, 32761])
    def test_disconnected_readback_zero_and_jets_differ(self):
        self.assertEqual(final_cdu('feedback_off'), [0, 0, 0])
        self.assertNotEqual(jets('closed'), jets('feedback_off'))
    def test_disconnected_larger_rate(self):
        self.assertGreater(max(abs(r['omega'][1]) for r in plants('feedback_off')), 11)
    def test_negative_reverses(self):
        pk = lambda m: max(plants(m), key=lambda r: abs(r['omega'][1]))['omega'][1]
        self.assertLess(pk('closed') * pk('negative'), 0)
    def test_replay_identical(self):
        self.assertEqual((RUN / 'closed.jsonl').read_bytes(), (RUN / 'repeat.jsonl').read_bytes())

if __name__ == '__main__': unittest.main()
