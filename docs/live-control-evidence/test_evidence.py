"""Reconcile genuine retained live runs; altered copies are rejection controls."""
import copy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest

from analyze import analyze_directory, analyze_trace, load_trace, QUANTUM
from live_common import HERE, ROOT, digest, verify_prior


class LiveEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = Path(os.environ.get('APOLLO_LIVE_EVIDENCE',
            HERE / 'runs/2026-10-17-verified/validation'))
        cls.result = analyze_directory(cls.evidence)
        cls.raw = {}
        cls.rows = {}
        for name in cls.result['cases']:
            path = cls.evidence / name / 'trace.jsonl'
            if not path.exists():
                path = path.with_suffix('.jsonl.gz')
            cls.raw[name], cls.rows[name] = load_trace(path)

    def test_all_signed_cases_are_actual_original_execution(self):
        self.assertEqual(set(self.result['cases']),
            {'yaw_plus', 'yaw_minus', 'pitch_plus', 'pitch_minus', 'combined', 'combined_replay'})
        for name, result in self.result['cases'].items():
            self.assertEqual(result['status'], 'VERIFIED', name)
            provenance = self.rows[name][0]['provenance']
            self.assertEqual(provenance['upstream_revision'], 'f577e3fd917866c59334e6cdd32504f09df76f60')
            rope = next(value for path, value in provenance['inputs_sha256'].items() if path.endswith('/MAIN.agc.bin'))
            self.assertEqual(rope, '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e')

    def test_actual_native_counter_queues_settle_without_loss(self):
        for result in self.result['cases'].values():
            for axis in result['counts']:
                self.assertEqual(len(set(axis.values())), 1)
            self.assertEqual(result['quiet_cycle']-result['settled_cycle'], 1000)
            self.assertLessEqual(max(result['settled_cdu_quaternion_residual_deg']), QUANTUM+1e-8)

    def test_original_gated_reads_observe_both_signs_and_neutral(self):
        for name, rows in self.rows.items():
            command = self.result['cases'][name]['command']
            gates = [r for r in rows if r['ev'] == 'rhc_gate_observation']
            for source, target in [('yaw_port0167', 'rhc_yaw_counter0043'),
                                   ('pitch_port0166', 'rhc_pitch_counter0042')]:
                if command[source]:
                    self.assertTrue(any(command['cycle'] < r['cycle'] < command['neutral_at'] and
                        r[target] == command[source] for r in gates), (name, source))
                self.assertTrue(any(command['neutral_at'] < r['cycle'] < 3200000 and r[target] == 0
                    for r in gates), (name, target))

    def test_cycle_identical_combined_replay_has_identical_complete_raw_bytes(self):
        self.assertTrue(self.result['combined_replay_byte_identical'])
        self.assertEqual(self.raw['combined'], self.raw['combined_replay'])

    def test_positive_and_negative_commands_have_signed_body_response(self):
        for name in ['yaw_plus', 'yaw_minus', 'pitch_plus', 'pitch_minus']:
            values = self.result['cases'][name]['max_signed_body_response_during_hold_deg_s']
            self.assertGreater(values[0 if name.startswith('yaw') else 1], .05, name)

    def test_all_prior_evidence_is_still_byte_identical(self):
        result = verify_prior()
        self.assertTrue(result['ok'], result['changed_or_missing'])
        self.assertEqual(result['files_checked'], 2572)

    def check_alteration_rejected(self, alter, message):
        rows = copy.deepcopy(self.rows['combined'])
        alter(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'deliberately-altered-copy.jsonl'
            path.write_text(''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, message):
                analyze_trace(path, -1, 1)

    def test_altered_actual_wire_packet_is_rejected(self):
        def alter(rows):
            row = next(r for r in rows if r['ev'] == 'wire_consumption')
            row['actual_packet']['value'] ^= 1
        self.check_alteration_rejected(alter, 'Actual parsed native ring packet')

    def test_altered_native_application_is_rejected(self):
        def alter(rows):
            row = next(r for r in rows if r['ev'] == 'application')
            row['after']['cdu'][row['axis']] = (row['after']['cdu'][row['axis']]+1) % 32768
        self.check_alteration_rejected(alter, 'Actual applied native counter delta')

    def test_missing_automatic_neutral_is_rejected(self):
        def alter(rows):
            rows[:] = [r for r in rows if not (r['ev'] == 'neutral' and
                r['origin'] == 'automatic bounded pulse neutral')]
        self.check_alteration_rejected(alter, 'Automatic authentic neutral input')


if __name__ == '__main__':
    unittest.main()
