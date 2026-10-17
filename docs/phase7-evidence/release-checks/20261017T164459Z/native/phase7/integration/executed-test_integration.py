"""GPL-2.0-or-later. Actual captured control evidence and fresh native transport.

No locked Tcl cache/download is required: make check separately runs all coupled
experiments. These tests rebuild the observer against retained unchanged source.
"""
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('phase7_integration_tests', HERE / 'run_validation.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CAPTURE = HERE / 'runs/integration-attempt-02'


class NativeWireAndFifos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = runner.ROOT / '.build/phase7'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='integration-native-test-', dir=scratch)
        cls.work = Path(cls.temporary.name)
        common = runner.load_module('phase7_test_build_helpers', runner.ROOT / 'docs/phase7-evidence/common.py')
        expected = json.loads((runner.ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
        source = cls.work / 'source'
        common.retained.extract_source(runner.ROOT / 'docs/phase6-evidence/corresponding-source.tar.gz', source, expected)
        output = cls.work / 'run'
        result = subprocess.run([sys.executable, HERE / 'run_validation.py', '--source', source, '--output', output,
                                 '--native-only'], cwd=runner.ROOT, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError('Fresh native observer failed:\n' + result.stdout + result.stderr)
        cls.rows = [json.loads(line) for line in (output / 'native-probe.jsonl').read_text().splitlines()]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_actual_native_bytes_preserve_mixed_normal_and_three_counter_order(self):
        consumed = [r for r in self.rows if r['ev'] == 'wire_consumption']
        self.assertEqual([r['actual_packet']['channel'] for r in consumed], [0o31, 0o167, 128 | 0o32, 128 | 0o33, 128 | 0o34])
        self.assertEqual([r['actual_packet']['value'] for r in consumed], [0o67777, 20, 17, 19, 1])
        self.assertEqual([r['cycle'] for r in consumed], [200001, 200001, 200001, 200002, 200003])
        self.assertEqual([r['wire_id'] for r in consumed], [1, 2, 3, 4, 5])

    def test_actual_three_fifo_heads_modular_counts_and_quiet_settlement(self):
        applications = [r for r in self.rows if r['ev'] == 'application']
        self.assertEqual([(r['axis'], r['code']) for r in applications], [(0, 17), (1, 19), (2, 1)])
        self.assertEqual(self.rows[-1]['quiet']['cdu'], [1, 32767, 1])
        self.assertEqual(self.rows[-1]['quiet']['cycle'] - self.rows[-1]['settled']['cycle'], 1000)
        self.assertTrue(all(not fifo['pending'] for fifo in self.rows[-1]['quiet']['fifo']))


class CapturedMultiAxisControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {}
        hashes = json.loads((CAPTURE / 'raw-trace-hashes.json').read_text())
        for case in runner.CASES:
            with gzip.open(CAPTURE / (case + '.jsonl.gz'), 'rb') as stream:
                raw = stream.read()
            if hashlib.sha256(raw).hexdigest() != hashes[case + '.jsonl']:
                raise AssertionError('Captured raw trace hash mismatch')
            cls.rows[case] = [json.loads(line) for line in raw.splitlines()]
        with gzip.open(CAPTURE / 'yaw_baseline.jsonl.gz', 'rt') as stream:
            cls.baseline = [json.loads(line) for line in stream]

    def altered(self, event, change, case='combined'):
        rows = list(self.rows[case])
        index = next(i for i, row in enumerate(rows) if row['ev'] == event)
        rows[index] = copy.deepcopy(rows[index])
        change(rows[index])
        return rows

    def test_all_captured_cases_reconcile_actual_native_boundaries(self):
        for case, rows in self.rows.items():
            with self.subTest(case=case):
                runner.validate_rows(rows)

    def test_original_yaw_and_new_quaternion_yaw_preserve_baseline(self):
        expected = json.loads((runner.ROOT / 'docs/milestone3-evidence/feedback/runs/attempt-03/raw-trace-hashes.json').read_text())
        hashes = json.loads((CAPTURE / 'raw-trace-hashes.json').read_text())
        self.assertEqual(hashes['yaw_baseline.jsonl'], expected['corrected_negative.jsonl'])
        comparison = runner.yaw_compatibility(self.baseline, self.rows['yaw'])
        self.assertTrue(comparison['passed'])
        self.assertTrue(comparison['timed_jets_exact'])
        self.assertTrue(comparison['actual_cdu_applications_exact'])

    def test_pitch_and_simultaneous_replays_are_exact(self):
        self.assertEqual(self.rows['pitch'], self.rows['pitch_replay'])
        self.assertEqual(self.rows['combined'], self.rows['combined_replay'])

    def test_independent_pitch_uses_original_qr_jets_and_actual_cdus(self):
        rows = self.rows['pitch']
        self.assertTrue(any(r['ev'] == 'output' and r['channel'] == 5 and r['value'] for r in rows))
        self.assertGreater(rows[-1]['counts'][1]['applied'], 0)
        self.assertGreater(rows[-1]['peak_abs_omega_deg_s'][1], .1)
        self.assertTrue(any(r['ev'] == 'application' and r['axis'] == 1 for r in rows))

    def test_simultaneous_actual_pq_torque_rates_and_orientation_overlap(self):
        self.assertTrue(any(r['ev'] == 'plant' and abs(r['torque_Nm'][0]) > .1 and abs(r['torque_Nm'][1]) > .1
                            and abs(r['omega'][0]) > .01 and abs(r['omega'][1]) > .01
                            and abs(r['quaternion'][1]) > 1e-9 and abs(r['quaternion'][2]) > 1e-9
                            for r in self.rows['combined']))

    def test_all_derived_gimbal_paths_retained_without_claiming_third_axis_control(self):
        self.assertTrue(all(c['applied'] > 0 for c in self.rows['combined'][-1]['counts']))
        self.assertFalse(any(row[1] == 0o170 for row in self.rows['combined'][0]['schedule']))
        self.assertTrue(any(r['ev'] == 'application' and r['axis'] == 2 for r in self.rows['combined']))

    def test_disconnected_controls_change_actual_timed_commands_keep_zero_cdus(self):
        for case in ('pitch', 'combined'):
            with self.subTest(case=case):
                def commands(rows):
                    return [(r['cycle'], r['channel'], r['value']) for r in rows if r['ev'] == 'output' and r['channel'] in (5, 6)]
                self.assertNotEqual(commands(self.rows[case]), commands(self.rows[case + '_off']))
                self.assertEqual(self.rows[case + '_off'][-1]['quiet']['cdu'], [0, 0, 0])
                self.assertGreater(sum(r['generated'] for r in self.rows[case + '_off'][-1]['counts']), 0)

    def test_combined_horizon_declared_before_execution_and_guard_active(self):
        for case in ('combined', 'combined_off', 'combined_replay'):
            self.assertEqual(self.rows[case][0]['end'], 3200000)
            self.assertTrue(all(abs((r['gimbals'][2] + 180) % 360 - 180) < 80 for r in self.rows[case] if r['ev'] == 'plant'))

    def test_final_actual_cdu_angles_match_quaternion_derived_gimbals_within_quantum(self):
        for case in ('yaw', 'pitch', 'combined'):
            with self.subTest(case=case):
                final = self.rows[case][-1]
                angles = runner.quaternion_gimbals(final['final_model']['quaternion'])
                errors = [abs((count * 360 / 32768 - angle + 180) % 360 - 180) for count, angle in zip(final['quiet']['cdu'], angles)]
                self.assertLessEqual(max(errors), 360 / 32768 + 1e-8)

    def test_pc_bank_flags_and_real_inertia_telemetry_exist(self):
        samples = [r for r in self.rows['combined'] if r['ev'] == 'execution_sample']
        self.assertGreater(len({r['registers']['z'] for r in samples}), 1)
        self.assertTrue(all(set(('z', 'eb', 'fb', 'bb', 'modreg', 'imodes30', 'imodes33', 'failreg', 'dapbools')) <= set(r['registers']) for r in samples))
        models = [r for r in self.rows['combined'] if r['ev'] == 'plant']
        self.assertTrue(all(min(r['inertia_before_kgm2']) > 0 for r in models))
        self.assertTrue(all(r['fuel_after_kg'] <= r['fuel_before_kg'] for r in models))

    def test_reject_swapped_native_packet_axis(self):
        rows = self.altered('wire_consumption', lambda r: r['actual_packet'].__setitem__('channel', 999))
        with self.assertRaisesRegex(ValueError, 'native ring order/bytes'):
            runner.validate_rows(rows)

    def test_reject_wrong_actual_fifo_head(self):
        rows = self.altered('application', lambda r: r['before']['fifo'][r['axis']].__setitem__('head', 17 if r['code'] != 17 else 19))
        with self.assertRaisesRegex(ValueError, 'application order/head'):
            runner.validate_rows(rows)

    def test_reject_wrong_actual_counter_delta(self):
        rows = self.altered('application', lambda r: r['after']['cdu'].__setitem__(r['axis'], r['before']['cdu'][r['axis']]))
        with self.assertRaisesRegex(ValueError, 'modular counter'):
            runner.validate_rows(rows)

    def test_reject_missing_observed_application_despite_summary(self):
        rows = list(self.rows['combined'])
        rows.remove(next(r for r in rows if r['ev'] == 'application'))
        with self.assertRaises(ValueError):
            runner.validate_rows(rows)

    def test_reject_false_summary_and_settlement(self):
        rows = self.altered('summary', lambda r: r['counts'][0].__setitem__('applied', 999999))
        with self.assertRaisesRegex(ValueError, 'Summary count'):
            runner.validate_rows(rows)
        rows = self.altered('summary', lambda r: r['quiet']['fifo'][1].__setitem__('pending', 1))
        with self.assertRaisesRegex(ValueError, 'unsettled'):
            runner.validate_rows(rows)

    def test_reject_swapped_final_orientation_interface(self):
        rows = self.altered('summary', lambda r: r['final_model'].__setitem__('quaternion', [1, 0, 0, 0]))
        with self.assertRaisesRegex(ValueError, 'quaternion-derived gimbals'):
            runner.validate_rows(rows)

    def test_reject_sensor_data_mislabeled_as_authentic_output(self):
        rows = self.altered('generated', lambda r: r.__setitem__('category', 'agc_output'))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            runner.validate_rows(rows)

    def test_actual_error_needles_are_not_coarse_platform_motion(self):
        latch = active = inactive = 0
        for row in self.rows['combined']:
            if row['ev'] == 'output':
                if row['channel'] == 0o12:
                    latch = row['value']
                elif row['channel'] in (0o174, 0o175, 0o176) and row['value']:
                    active += bool(latch & 8)
                    inactive += not bool(latch & 8)
        self.assertEqual(active, 0)
        self.assertGreater(inactive, 0)

    def test_reject_active_unsupported_alignment_without_discarding_raw_packet(self):
        rows = list(self.rows['combined'])
        first = next(i for i, r in enumerate(rows) if r['ev'] == 'output' and r['channel'] in (0o174, 0o175, 0o176) and r['value'])
        rows.insert(first, {'ev': 'output', 'category': 'agc_output', 'channel': 0o12, 'value': 8, 'cycle': rows[first]['cycle'], 'tail': False})
        with self.assertRaisesRegex(ValueError, 'active coarse-alignment'):
            runner.validate_rows(rows)

    def test_reject_unsupported_sensor_path_and_nonunit_orientation(self):
        extra = '1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 0 0'
        with self.assertRaisesRegex(ValueError, 'non-CDU'):
            runner.parse_response('0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0|{PCDU 37}|' + extra)
        with self.assertRaisesRegex(ValueError, 'unit norm'):
            runner.parse_response('0 0 0 0 0 0 2 0 0 0 0 0 0 0 0 0||' + extra)

    def test_same_call_analog_vector_schedule_is_source_justified(self):
        schedule = runner.make_schedule('combined')
        self.assertIn([2500000, 0o31, 12278], schedule)
        analog = [row[1:] for row in schedule if row[0] == 2500001]
        self.assertEqual(analog, [[0o166, 20], [0o167, 32747]])
        self.assertEqual([row[1:] for row in schedule if row[0] == 2700000], [[0o166, 0], [0o167, 0]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
