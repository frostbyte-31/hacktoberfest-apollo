"""GPL-2.0-or-later. Reconcile actual feedback captures and reject corrupt evidence.

No Tcl download/cache is required here. Full fresh coupled execution is the
run_validation provider; native FIFO behavior is also rebuilt by milestone2 tests.
"""
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('milestone3_feedback_tests_runner', HERE / 'run_validation.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CAPTURE = HERE / 'runs/attempt-03'


class PacedSingleAxisFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {}
        cls.hashes = json.loads((CAPTURE / 'raw-trace-hashes.json').read_text())
        for case in runner.CASES:
            with gzip.open(CAPTURE / (case + '.jsonl.gz'), 'rb') as stream:
                raw = stream.read()
            if hashlib.sha256(raw).hexdigest() != cls.hashes[case + '.jsonl']:
                raise AssertionError('Captured raw trace hash mismatch')
            cls.rows[case] = [json.loads(line) for line in raw.splitlines()]

    def altered(self, event, change, case='corrected_negative'):
        rows = copy.deepcopy(self.rows[case])
        change(next(row for row in rows if row['ev'] == event))
        return rows

    def test_all_five_captures_reconcile_without_tcl(self):
        for case, rows in self.rows.items():
            with self.subTest(case=case):
                runner.validate_rows(rows)

    def test_corrected_replay_raw_bytes_match(self):
        self.assertEqual(self.hashes['corrected_negative.jsonl'], self.hashes['corrected_repeat.jsonl'])

    def test_clean_delayed_schedule_has_no_collisions_and_preserves_negative_rhc(self):
        schedule = runner.make_schedule()
        self.assertEqual(len(schedule), len({row[0] for row in schedule}))
        self.assertIn([1600000, 13, 17], schedule)
        self.assertIn([1727998, 13, 28], schedule)
        self.assertIn([2000000, 13, 17], schedule)
        self.assertIn([2063999, 13, 28], schedule)
        self.assertIn([2500000, 25, 12279], schedule)
        self.assertIn([2500001, 119, 32747], schedule)

    def test_original_and_corrected_use_identical_declared_physical_inputs(self):
        original, corrected = self.rows['original_negative'][0], self.rows['corrected_negative'][0]
        for key in original:
            if key != 'selector':
                self.assertEqual(original[key], corrected[key])
        for rows in self.rows.values():
            checkpoint = next(r for r in rows if r['ev'] == 'startup_checkpoint')
            self.assertEqual(checkpoint['modreg'], 0)
            self.assertEqual(checkpoint['failreg'], [0, 0, 0])
            self.assertEqual((checkpoint['imodes30'] | checkpoint['imodes33']) & 0o40, 0)

    def test_negative_high_rate_exercises_correction_without_forced_state(self):
        original, corrected = self.rows['original_negative'][-1], self.rows['corrected_negative'][-1]
        self.assertGreater(original['generated_slow_negative_at_high_rate'], 0)
        self.assertEqual(original['generated_negative_fast'], 0)
        self.assertGreater(corrected['generated_negative_fast'], 0)
        self.assertEqual(corrected['generated_slow_negative_at_high_rate'], 0)
        self.assertGreater(corrected['peak_abs_yaw_deg_s'], 4)
        self.assertEqual(corrected['state_writes'], 0)

    def test_actual_signed_fast_head_and_modular_transition_are_visible(self):
        applied = [r for r in self.rows['corrected_negative'] if r['ev'] == 'application' and r['code'] == 19]
        self.assertTrue(applied)
        for row in applied:
            self.assertEqual(row['before']['head_code'], 19)
            self.assertEqual(row['after']['cdu'][0], (row['before']['cdu'][0] - 1) % 32768)
            self.assertEqual(row['after']['deadline'] - row['before']['deadline'], 13)

    def test_feedback_changes_timed_genuine_jets_while_rhc_is_held(self):
        def held_jets(rows):
            return [(r['cycle'], r['value']) for r in rows if r['ev'] == 'output' and r['channel'] == 6
                    and 2500000 < r['cycle'] < 2700000]
        connected = held_jets(self.rows['corrected_negative'])
        disconnected = held_jets(self.rows['corrected_feedback_off'])
        self.assertNotEqual(connected, disconnected)
        self.assertTrue(any(value not in (0, 170) for _, value in connected))
        self.assertTrue(all(value in (0, 170) for _, value in disconnected))

    def test_disconnected_retains_model_motion_and_actual_zero_cdu(self):
        summary = self.rows['corrected_feedback_off'][-1]
        self.assertGreater(summary['counts']['generated'], 0)
        self.assertEqual(summary['counts']['delivered'], 0)
        self.assertEqual(summary['quiet']['cdu'], [0, 0, 0])
        self.assertGreater(abs(summary['final_model'][0]), 10)
        self.assertLess(abs(self.rows['corrected_negative'][-1]['final_model'][0]), 1)

    def test_short_cutoff_observes_real_nonempty_drain_then_quiet_cpu(self):
        rows = self.rows['corrected_drain']
        freeze = next(r for r in rows if r['ev'] == 'freeze')
        summary = rows[-1]
        self.assertEqual(freeze['cycle'], 2650000)
        self.assertGreater(freeze['host_pending'] + freeze['state']['pending'] + freeze['state']['incoming'], 0)
        self.assertGreater(summary['tail_applied'], 0)
        self.assertGreater(summary['settlement_tail_cpu_calls'], 0)
        self.assertEqual(summary['quiet']['cycle'] - summary['settled']['cycle'], 1000)
        self.assertFalse(any(r['ev'] == 'plant' and r['cycle'] > freeze['cycle'] for r in rows))

    def test_summary_counts_cannot_replace_actual_applications(self):
        rows = self.altered('summary', lambda r: r['counts'].__setitem__('applied', r['counts']['applied'] + 1))
        with self.assertRaisesRegex(ValueError, 'Summary count'):
            runner.validate_rows(rows)

    def test_reject_missing_application_despite_summary_claim(self):
        rows = copy.deepcopy(self.rows['corrected_negative'])
        rows.remove(next(r for r in rows if r['ev'] == 'application'))
        with self.assertRaises(ValueError):
            runner.validate_rows(rows)

    def test_reject_wrong_actual_fifo_head_rate(self):
        rows = self.altered('application', lambda r: r['before'].__setitem__('head_code', 17))
        with self.assertRaisesRegex(ValueError, 'FIFO head/order'):
            runner.validate_rows(rows)

    def test_reject_wrong_actual_counter_delta(self):
        rows = self.altered('application', lambda r: r['after']['cdu'].__setitem__(0, r['before']['cdu'][0]))
        with self.assertRaisesRegex(ValueError, 'counter delta'):
            runner.validate_rows(rows)

    def test_reject_wrong_applied_deadline_rate(self):
        rows = self.altered('application', lambda r: r['after'].__setitem__('deadline', r['before']['deadline'] + 999))
        with self.assertRaisesRegex(ValueError, 'deadline increment'):
            runner.validate_rows(rows)

    def test_reject_fake_queue_settlement(self):
        rows = self.altered('settled', lambda r: r['state'].__setitem__('pending', 1))
        with self.assertRaisesRegex(ValueError, 'settlement retains'):
            runner.validate_rows(rows)

    def test_reject_clean_start_claim_with_recorded_alarm(self):
        rows = self.altered('startup_checkpoint', lambda r: r['failreg'].__setitem__(0, 0o1107))
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            runner.validate_rows(rows)

    def test_reject_generated_data_mislabeled_as_agc_output(self):
        rows = self.altered('generated', lambda r: r.__setitem__('category', 'agc_output'))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            runner.validate_rows(rows)

    def test_reject_unbounded_availability_delay(self):
        rows = self.altered('generated', lambda r: r.__setitem__('available', r['origin'] + runner.CHUNK + 1))
        with self.assertRaisesRegex(ValueError, 'availability latency'):
            runner.validate_rows(rows)

    def test_reject_cross_axis_packets_motion_words_and_nonfinite_data(self):
        for response in ['0 1 0 0 0 0|', '0 0 0 0 0 0|{PCDU 33}', 'nan 0 0 0 0 0|', '0 0 0 0 0 0|{BOGUS 32}']:
            with self.subTest(response=response), self.assertRaises(ValueError):
                runner.checked_plant_response(response)
        for channel, value in [(5, 1), (6, 256)]:
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                runner.check_jet(channel, value)
        for value in range(256):
            runner.check_jet(6, value)

    def test_output_guard_refuses_existing_retained_and_symlink_destinations(self):
        with self.assertRaises(ValueError):
            runner.destination(HERE / 'test_feedback.py')
        with self.assertRaises(ValueError):
            runner.destination(HERE / 'must-not-be-created.jsonl')
        scratch = runner.ROOT / '.build/milestone3'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            alias = Path(temporary) / 'alias'
            alias.symlink_to(HERE, target_is_directory=True)
            with self.assertRaises(ValueError):
                runner.destination(alias / 'must-not-be-created.jsonl')


if __name__ == '__main__':
    unittest.main(verbosity=2)
