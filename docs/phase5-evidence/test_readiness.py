"""Concrete evidence assertions; these do not validate historical mission accuracy."""
from pathlib import Path
import unittest, json, hashlib
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def read(path): return [json.loads(l) for l in path.read_text().splitlines()]

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gates = {n: read(HERE / 'runs' / (n + '.stdout')) for n in ['baseline', 'operate', 'off']}
        cls.loops = {n: read(HERE / 'loop-runs' / (n + '.jsonl')) for n in ['closed', 'feedback_off', 'blocked', 'negative']}

    def test_prior_evidence_unchanged(self):
        hashes = json.loads((HERE / 'prior_hashes.json').read_text())
        self.assertEqual(len(hashes), 109)
        for p, h in hashes.items(): self.assertEqual(hashlib.sha256((ROOT / p).read_bytes()).hexdigest(), h, p)

    def test_baseline_reproduces_original_failure(self):
        rows = self.gates['baseline']
        self.assertEqual(sum(r['ev'] == 'checkpoint' and r['bank'] == 0o16 and r['z'] == 0o2163 for r in rows), 469)
        self.assertEqual(sum(r['ev'] == 'checkpoint' and r['bank'] == 0o16 and r['z'] == 0o2046 for r in rows), 0)
        self.assertFalse(any(r['ev'] == 'output' and r['channel'] in (5, 6) and r['value'] for r in rows))
        prior = read(ROOT / 'docs/phase4-evidence/runs/probe.stdout')
        keep = lambda data: [r for r in data if r['ev'] in ('initial', 'input', 'output', 'sample')]
        self.assertEqual(keep(rows), keep(prior))

    def test_correction_changes_only_operate_bit(self):
        a = (HERE / 'baseline_inputs.txt').read_text().splitlines()
        b = (HERE / 'operate_inputs.txt').read_text().splitlines()
        changes = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual(changes, [('100001 24 15871', '100001 24 15615')])
        self.assertEqual(15871 ^ 15615, 1 << 8)

    def test_original_issup_clears_the_gate(self):
        before = [r for r in self.gates['operate'] if r['ev'] == 'before']
        a = next(r for r in before if r['cycle'] == 1480208)
        b = next(r for r in before if r['cycle'] == 1480209)
        self.assertEqual((a['bank'], a['z'], a['imodes33']), (6, 0o2326, 0o36040))
        self.assertEqual((b['bank'], b['z'], b['imodes33']), (6, 0o2327, 0o36000))
        self.assertTrue(any(r['ev'] == 'checkpoint' and r['bank'] == 0o16 and r['z'] == 0o2046 for r in self.gates['operate']))

    def test_imu_off_restores_rejection(self):
        rows = self.gates['off']
        final = [r for r in rows if r['ev'] == 'sample'][-1]
        self.assertTrue(final['imodes33'] & 32)
        self.assertFalse(any(r['ev'] == 'output' and r['channel'] in (5, 6) and r['value'] for r in rows))

    def test_actual_jets_move_vehicle_and_read_back(self):
        data = self.loops['closed']
        self.assertTrue(any(r['ev'] == 'output' and r['channel'] == 6 and r['value'] == 0o125 for r in data))
        self.assertTrue(any(r['ev'] == 'plant' and r['omega'][0] > 0.1 for r in data))
        self.assertTrue(any(r['ev'] == 'sensor' and r['counter'] == 0o32 and r['delivered'] and r['accepted'] > 0 for r in data))
        self.assertTrue(any(r['ev'] == 'sample' and r['cdu'][0] > 0 for r in data))

    def test_feedback_changes_original_commands(self):
        def jets(data): return [(r['cycle'], r['channel'], r['value']) for r in data if r['ev'] == 'output' and r['channel'] in (5, 6)]
        self.assertNotEqual(jets(self.loops['closed']), jets(self.loops['feedback_off']))
        self.assertTrue(any(r['ev'] == 'output' and r['channel'] == 6 and r['value'] == 0o252 for r in self.loops['closed']))
        self.assertFalse(any(r['ev'] == 'output' and r['channel'] == 6 and r['value'] == 0o252 for r in self.loops['feedback_off']))

    def test_actuator_disconnect_removes_motion(self):
        data = self.loops['blocked']
        self.assertTrue(any(r['ev'] == 'output' and r['channel'] == 6 and r['value'] for r in data))
        self.assertEqual(max(abs(v) for r in data if r['ev'] == 'plant' for v in r['omega']), 0)
        self.assertEqual(sum(r['ev'] == 'sensor' for r in data), 0)

    def test_sensor_disconnect_removes_readback(self):
        data = self.loops['feedback_off']
        self.assertTrue(any(r['ev'] == 'sensor' for r in data))
        self.assertFalse(any(r['ev'] == 'sensor' and r['delivered'] for r in data))
        self.assertFalse(any(r['ev'] == 'sample' and any(r['cdu']) for r in data))
        self.assertGreater(max(abs(r['omega'][0]) for r in data if r['ev'] == 'plant'), 10)

    def test_opposite_input_reverses_initial_response(self):
        def first(data): return next(r['value'] for r in data if r['ev'] == 'output' and r['channel'] == 6 and r['value'])
        self.assertEqual(first(self.loops['closed']), 0o125)
        self.assertEqual(first(self.loops['negative']), 0o252)
        self.assertTrue(any(r['ev'] == 'plant' and r['omega'][0] < -0.1 for r in self.loops['negative']))

    def test_fixture_stays_single_axis(self):
        for data in self.loops.values():
            self.assertFalse(any(r['ev'] == 'output' and r['channel'] == 5 and r['value'] for r in data))
            self.assertFalse(any(r['ev'] == 'sensor' and r['counter'] != 0o32 for r in data))
            self.assertFalse(any(r['ev'] == 'plant' and (r['omega'][1] != 0 or r['omega'][2] != 0) for r in data))

    def test_exact_replays(self):
        self.assertEqual((HERE / 'runs/operate.stdout').read_bytes(), (HERE / 'runs/repeat.stdout').read_bytes())
        self.assertEqual((HERE / 'loop-runs/closed.jsonl').read_bytes(), (HERE / 'loop-runs/repeat.jsonl').read_bytes())

if __name__ == '__main__': unittest.main()