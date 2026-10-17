"""GPL-2.0-or-later. Real native CDU tests using only the retained source bundle."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('milestone2_cdu_runner', HERE / 'run_validation.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class NativeCduTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = ROOT / '.build/milestone2-cdu'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='native-tests-', dir=scratch)
        cls.work = Path(cls.temporary.name)
        source = cls.work / 'source'
        expected = json.loads((ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
        with tarfile.open(ROOT / 'docs/phase6-evidence/corresponding-source.tar.gz', 'r:gz') as archive:
            members = archive.getmembers()
            if len(members) != len(expected) or {m.name for m in members} != set(expected):
                raise AssertionError('Source archive inventory differs')
            for member in members:
                path = Path(member.name)
                if not member.isfile() or path.is_absolute() or '..' in path.parts:
                    raise AssertionError('Unsafe retained source member')
                data = archive.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != expected[member.name]:
                    raise AssertionError('Retained source member hash differs')
                target = source / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        cls.output = cls.work / 'run'
        result = subprocess.run([sys.executable, HERE / 'run_validation.py', '--source', source,
                                 '--output', cls.output], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError('Native validation failed:\n' + result.stdout + result.stderr)
        cls.summary = json.loads((cls.output / 'summary.json').read_text())['cases']
        cls.traces = {name: [json.loads(line) for line in (cls.output / (name + '.jsonl')).read_text().splitlines()]
                      for name in runner.CASES}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_all_workloads_replay_exactly(self):
        for name in runner.CASES:
            with self.subTest(case=name):
                self.assertEqual((self.output / (name + '.jsonl')).read_bytes(),
                                 (self.output / (name + '-replay.jsonl')).read_bytes())

    def test_each_supported_packet_is_enqueued_and_applied(self):
        for name, summary in self.summary.items():
            if name.endswith('_control'):
                continue
            with self.subTest(case=name):
                self.assertEqual(summary['requests'], summary['packet_accepted'])
                self.assertEqual(summary['packet_accepted'], summary['fifo_enqueued'])
                self.assertEqual(summary['fifo_enqueued'], summary['applied'])
                self.assertEqual(summary['fifo_dropped'], 0)
                self.assertTrue(summary['all_accounted'])

    def test_pure_signed_slow_counts_and_symmetric_application_times(self):
        positive = [r for r in self.traces['positive_slow'] if r['ev'] == 'application']
        negative = [r for r in self.traces['negative_slow'] if r['ev'] == 'application']
        self.assertEqual([r['after']['cycle'] for r in positive], [r['after']['cycle'] for r in negative])
        self.assertEqual([r['after']['cdu'][0] for r in positive], list(range(1, 13)))
        self.assertEqual([r['after']['cdu'][0] for r in negative], [(32768 - i) for i in range(1, 13)])

    def test_pure_signed_fast_counts_and_symmetric_application_times(self):
        positive = [r for r in self.traces['positive_fast'] if r['ev'] == 'application']
        negative = [r for r in self.traces['negative_fast'] if r['ev'] == 'application']
        self.assertEqual([r['after']['cycle'] for r in positive], [r['after']['cycle'] for r in negative])
        self.assertEqual([r['after']['cdu'][0] for r in positive], list(range(1, 25)))
        self.assertEqual([r['after']['cdu'][0] for r in negative], [(32768 - i) for i in range(1, 25)])

    def test_deadline_cadence_uses_exact_clock_and_not_rounded_wrapper(self):
        for name, intervals, sum_three, rate in [('positive_slow', {213, 214}, 640, 400),
                                               ('positive_fast', {13, 14}, 40, 6400)]:
            with self.subTest(case=name):
                applied = [r for r in self.traces[name] if r['ev'] == 'application']
                steps = [r['after']['next_update'] - r['before']['next_update'] for r in applied]
                self.assertEqual(set(steps), intervals)
                for index in range(0, len(steps) - 2, 3):
                    self.assertEqual(sum(steps[index:index + 3]), sum_three)
                self.assertEqual((1024000 / 12) * 3 / sum_three, rate)
                first = next(r for r in self.traces[name] if r['ev'] == 'consumption')
                self.assertEqual(first['after']['next_update'] - first['after']['cycle'], min(intervals))

    def test_packet_consumption_and_actual_application_are_separate(self):
        for name, rows in self.traces.items():
            with self.subTest(case=name):
                for row in rows:
                    if row['ev'] == 'consumption':
                        self.assertEqual(row['before']['cdu'], row['after']['cdu'])
                first_delivery = next(r for r in rows if r['ev'] == 'delivery')
                first_application = next(r for r in rows if r['ev'] == 'application')
                self.assertGreater(first_application['after']['cycle'], first_delivery['delivery_cycle'])

    def test_backlog_can_catch_up_faster_than_nominal_deadline_spacing(self):
        # Counter-input calls postpone service without moving the original
        # deadline. This prevents treating nominal6400Hz as a hard per-event cap.
        rows = [r for r in self.traces['positive_fast'] if r['ev'] == 'application']
        intervals = [b['after']['cycle'] - a['after']['cycle'] for a, b in zip(rows, rows[1:])]
        self.assertTrue(any(interval < 13 for interval in intervals))
        self.assertGreater(rows[0]['after']['cycle'], rows[0]['before']['next_update'])

    def test_mixed_runs_preserve_order_and_signed_net_count(self):
        for name in ('mixed', 'alternating_supported'):
            with self.subTest(case=name):
                applications = [r for r in self.traces[name] if r['ev'] == 'application']
                operations = [r['before']['fifo_head_code'] for r in applications]
                expected = runner.CASES[name][0]
                self.assertEqual(operations, expected)
                for index, (row, expected_code) in enumerate(zip(applications, expected)):
                    # Read-only C getter decodes the actual upstream FIFO head;
                    # independently inspect its effect on the real deadline.
                    self.assertEqual(row['code'], row['before']['fifo_head_code'])
                    self.assertEqual(row['code'], expected_code)
                    short_interval = 13 if expected_code in (17, 19) else 213
                    self.assertEqual(row['after']['next_update'] - row['before']['next_update'],
                                     short_interval + (index % 3 == 1))
                    self.assertEqual((row['after']['cdu'][0] - row['before']['cdu'][0]) % 32768,
                                     runner.SIGNS[expected_code] % 32768)
                self.assertEqual(self.summary[name]['final_state']['cdu'][0],
                                 sum(runner.SIGNS[code] for code in operations) % 32768)
        self.assertEqual(self.summary['mixed']['max_fifo_entries'], 4)
        self.assertEqual(self.summary['alternating_supported']['max_fifo_entries'], 64)

    def test_signed_wrap_uses_packets_without_counter_initialization_writes(self):
        applications = [r for r in self.traces['signed_wrap'] if r['ev'] == 'application']
        self.assertEqual([(r['before']['cdu'][0], r['after']['cdu'][0]) for r in applications],
                         [(0, 32767), (32767, 0)])
        self.assertEqual([r['code'] for r in applications], [3, 1])
        self.assertEqual(self.traces['signed_wrap'][0]['ram_writes'], 0)

    def test_fifo_capacity_control_detects_silent_loss_despite_packet_acceptance(self):
        summary = self.summary['fifo_capacity_control']
        self.assertEqual((summary['requests'], summary['packet_accepted'], summary['applied']), (129, 129, 128))
        self.assertEqual((summary['fifo_dropped'], summary['max_fifo_entries']), (1, 128))
        dropped = [r for r in self.traces['fifo_capacity_control']
                   if r['ev'] == 'consumption' and not r['fifo_enqueued']]
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]['after']['fifo_entries'], 128)

    def test_ringbuffer_capacity_control_and_same_run_coalescing(self):
        summary = self.summary['ringbuffer_capacity_control']
        self.assertEqual((summary['requests'], summary['packet_accepted'], summary['ringbuffer_rejected']),
                         (1025, 1023, 2))
        self.assertEqual((summary['fifo_dropped'], summary['applied']), (0, 1023))
        self.assertEqual((summary['max_fifo_entries'], summary['max_fifo_pending']), (1, 1023))

    def test_queue_settlement_and_quiet_observation_are_bounded(self):
        for name, rows in self.traces.items():
            with self.subTest(case=name):
                settlements = [r for r in rows if r['ev'] == 'settled']
                self.assertEqual(len(settlements), len(runner.CASES[name]))
                for row in settlements:
                    self.assertEqual((row['state']['incoming'], row['state']['fifo_pending'], row['state']['fifo_entries']),
                                     (0, 0, 0))
                    self.assertEqual(row['after_1000_idle_calls']['cycle'] - row['state']['cycle'], 1000)
                    self.assertEqual(row['state']['cdu'], row['after_1000_idle_calls']['cdu'])
                self.assertLess(rows[-1]['final_state']['cycle'] - rows[0]['state']['cycle'], 1000000)

    def test_other_axes_remain_zero(self):
        for name, rows in self.traces.items():
            with self.subTest(case=name):
                for row in rows:
                    for key in ('state', 'before', 'after', 'after_1000_idle_calls', 'final_state'):
                        if key in row:
                            self.assertEqual(row[key]['cdu'][1:], [0, 0])

    def test_worker_rejects_existing_output_without_writing(self):
        target = self.work / 'existing-trace.jsonl'
        sentinel = b'retained existing evidence\n'
        target.write_bytes(sentinel)
        result = subprocess.run([sys.executable, HERE / 'run_validation.py', '--case', 'positive_slow',
                                 '--library', '/deliberately/missing/library.so', '--output', target],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Output already exists', result.stderr)
        self.assertEqual(target.read_bytes(), sentinel)

    def test_worker_rejects_new_retained_evidence_path_before_loading_engine(self):
        target = HERE / 'forbidden-worker-output.jsonl'
        self.assertFalse(target.exists())
        result = subprocess.run([sys.executable, HERE / 'run_validation.py', '--case', 'positive_slow',
                                 '--library', '/deliberately/missing/library.so', '--output', target],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('retained evidence stays immutable', result.stderr)
        self.assertFalse(target.exists())

    def test_worker_rejects_build_symlink_escape_into_retained_evidence(self):
        alias = self.work / 'evidence-alias'
        alias.symlink_to(HERE, target_is_directory=True)
        target = alias / 'forbidden-symlink-worker-output.jsonl'
        result = subprocess.run([sys.executable, HERE / 'run_validation.py', '--case', 'positive_slow',
                                 '--library', '/deliberately/missing/library.so', '--output', target],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('retained evidence stays immutable', result.stderr)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
