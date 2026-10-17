"""GPL-2.0-or-later. Concrete demonstration evidence and fail-closed inspection tests."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('apollo_demonstration', HERE / 'demonstrate.py')
if spec is None or spec.loader is None: raise RuntimeError('Cannot load demonstration')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

class DemonstrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run = HERE / 'demo-run'
        cls.closed = demo.load_trace(cls.run / 'closed.jsonl')
        cls.off = demo.load_trace(cls.run / 'feedback_off.jsonl')

    def test_prior_evidence_preserved(self):
        hashes = json.loads((HERE / 'prior_hashes.json').read_text())
        self.assertEqual(len(hashes), 177)
        for path, expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)

    def test_fresh_replay_exact(self):
        self.assertEqual((self.run / 'closed.jsonl').read_bytes(), (self.run / 'repeat.jsonl').read_bytes())

    def test_original_jets_follow_controller_input(self):
        first = next(r for r in self.closed if r['ev'] == 'output' and r['channel'] == 6 and r['value'])
        self.assertEqual((first['cycle'], first['value']), (2509125, 0o125))
        self.assertGreater(first['cycle'], 2500000)

    def test_changed_measurements_change_original_commands(self):
        jets = lambda data: [(r['cycle'], r['channel'], r['value']) for r in data if r['ev'] == 'output' and r['channel'] in (5, 6)]
        self.assertNotEqual(jets(self.closed), jets(self.off))
        braking = lambda data: [r for r in data if r['ev'] == 'output' and r['channel'] == 6 and r['value'] == 0o252]
        self.assertEqual(len(braking(self.closed)), 7)
        self.assertEqual(len(braking(self.off)), 0)

    def test_sensor_disconnect_removes_readback_not_motion(self):
        sensors = [r for r in self.off if r['ev'] == 'sensor']
        self.assertEqual(len(sensors), 16173)
        self.assertEqual(sum(r['delivered'] for r in sensors), 0)
        self.assertTrue(all(r['cdu'] == [0, 0, 0] for r in self.off if r['ev'] == 'sample'))
        self.assertGreater(max(abs(r['omega'][0]) for r in self.off if r['ev'] == 'plant'), 10)

    def test_actual_sensor_acceptance_and_counter_application_distinct(self):
        sensors = [r for r in self.closed if r['ev'] == 'sensor']
        self.assertEqual(len(sensors), 1539)
        self.assertTrue(all(r['delivered'] and r['accepted'] > 0 for r in sensors))
        self.assertEqual([r for r in self.closed if r['ev'] == 'sample'][-1]['cdu'], [1533, 0, 0])

    def test_delivery_timestamp_preserved_separately(self):
        sensors = [r for r in self.closed if r['ev'] == 'sensor']
        self.assertTrue(all(0 <= r['cycle'] - r['origin_interval_end'] <= 853 for r in sensors))
        self.assertTrue(any(r['cycle'] > r['origin_interval_end'] for r in sensors))

    def test_inspection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            demo.inspect_trace(self.run / 'closed.jsonl', output, 'closed')
            self.assertEqual((output / 'closed.summary.json').read_bytes(), (self.run / 'closed.summary.json').read_bytes())
            self.assertEqual((output / 'closed.categorized.jsonl').read_bytes(), (self.run / 'closed.categorized.jsonl').read_bytes())

    def test_truncated_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.jsonl'
            path.write_text(json.dumps(self.closed[0]) + '\n')
            with self.assertRaisesRegex(ValueError, 'Incomplete'): demo.load_trace(path)

    def test_nonfinite_state_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in [self.closed[0], {'ev': 'plant', 'omega': [float('nan')]}, self.closed[-1]]) + '\n')
            with self.assertRaisesRegex(ValueError, 'Non-finite'): demo.load_trace(path)

    def test_compiler_and_runs_exit_zero(self):
        commands = json.loads((self.run / 'commands.json').read_text())
        self.assertEqual(len(commands), 8)
        self.assertTrue(all(r['exit'] == 0 for r in commands))

if __name__ == '__main__': unittest.main()