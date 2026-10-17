"""Diagnostic arithmetic tests; these do not execute Luminary."""
from fractions import Fraction
import importlib.util
from pathlib import Path
import json
import unittest

HERE = Path(__file__).resolve().parent
DOCS = HERE.parents[1]
spec = importlib.util.spec_from_file_location('phase10_math', HERE/'diagnostics.py')
math_checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math_checks)


class ArithmeticTests(unittest.TestCase):
    def test_both_ones_complement_zeros(self):
        self.assertEqual(math_checks.signed_sp(0), 0)
        self.assertEqual(math_checks.signed_sp(0o77777), 0)
        self.assertEqual(math_checks.dp_fraction([0o77777, 0]), 0)

    def test_dp_mixed_sign_and_signed_zero_low_word(self):
        self.assertEqual(math_checks.dp_fraction([0o20000, 0o77777]), Fraction(1, 2))
        self.assertEqual(math_checks.dp_count([1, 0o77776]), 16383)
        self.assertEqual(math_checks.dp_count([0o77776, 1]), -16383)
        self.assertEqual(math_checks.dp_count([0, 0o77776]), -1)

    def test_reject_non_word_inputs(self):
        for word in (-1, 0o100000, True, 1.2):
            with self.assertRaises(ValueError):
                math_checks.signed_sp(word)

    def test_explicit_si_scaling(self):
        self.assertEqual(math_checks.physical_dp([0o20000, 0], 29), 2**28)
        self.assertEqual(math_checks.physical_dp([0o20000, 0], 7, 100), 6400)

    def test_canonical_encoding_quantization_and_sign(self):
        self.assertEqual(math_checks.encode_fraction(Fraction(-1, 2)), [0o57777, 0o77777])
        self.assertEqual(math_checks.encode_fraction(Fraction(1, 2)), [0o20000, 0])
        words = math_checks.encode_physical(1738090.2, 27)
        self.assertAlmostEqual(math_checks.physical_dp(words, 27), 1738090.2, delta=.25)
        with self.assertRaises(ValueError):
            math_checks.encode_fraction(1)

    def test_si_state_consistency(self):
        # Synthetic circular orbit, not mission data or a propagated solution.
        radius, mu = 1753090, 4.902778e12
        speed = (mu/radius)**.5
        report = math_checks.state_diagnostics([radius, 0, 0], [0, 0, speed], [1738090, 0, 0], mu, 1738090)
        self.assertEqual(report['altitude_above_reference_m'], 15000)
        self.assertEqual(report['radial_velocity_m_s'], 0)
        self.assertEqual(report['site_central_angle_rad'], 0)
        self.assertAlmostEqual(report['speed_m_s'], report['circular_speed_at_radius_m_s'])
        self.assertTrue(report['bound_two_body_energy'])

    def test_retained_synthetic_candidate_is_coherent(self):
        candidate = json.loads((HERE/'synthetic-candidate-t120.json').read_text())
        self.assertEqual(candidate['rope_sha256'], '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e')
        inputs = candidate['input_candidates']
        # These are INITIALIZED MISSION INPUTS, not AGC-computed outputs.
        report = math_checks.state_diagnostics(
            inputs['RRECTLEM']['encoded_si_readback'], inputs['VRECTLEM']['encoded_si_readback'],
            [candidate['lunar_reference_radius_m'], 0, 0], candidate['mu_m3_s2'], candidate['lunar_reference_radius_m'])
        self.assertAlmostEqual(report['altitude_above_reference_m'], 15000, delta=.5)
        self.assertAlmostEqual(report['speed_m_s'], report['circular_speed_at_radius_m_s'], delta=.001)
        self.assertAlmostEqual(report['radial_velocity_m_s'], 0, delta=.001)
        self.assertAlmostEqual(candidate['TLAND_cs']-candidate['state_epoch_cs'], 66440)
        m = candidate['independent_physical_moon_matrix_at_TLAND']
        site = inputs['RLS']['encoded_si_readback']
        transformed = [sum(m[j][i]*site[j] for j in range(3)) for i in range(3)]
        self.assertAlmostEqual(transformed[0], candidate['lunar_reference_radius_m'], delta=.5)
        self.assertAlmostEqual(transformed[1], 0, delta=.5)
        self.assertAlmostEqual(transformed[2], 0, delta=.5)

    def test_causal_altitude_variant_preserves_frame_epoch(self):
        base = json.loads((HERE/'synthetic-candidate-t120.json').read_text())
        changed = json.loads((HERE/'synthetic-candidate-t120-alt16km.json').read_text())
        for key in ('rope_sha256', 'mu_m3_s2', 'lunar_reference_radius_m', 'state_epoch_cs', 'TLAND_cs'):
            self.assertEqual(base[key], changed[key])
        self.assertEqual(base['input_candidates']['RLS'], changed['input_candidates']['RLS'])
        self.assertAlmostEqual(changed['diagnostics']['radius_m']-base['diagnostics']['radius_m'], 1000)
        self.assertLess(changed['diagnostics']['circular_speed_at_radius_m_s'], base['diagnostics']['circular_speed_at_radius_m_s'])

    def test_earlier_downrange_candidates_preserve_circular_state(self):
        for suffix, altitude in (('', 15000), ('-alt16km', 16000)):
            candidate = json.loads((HERE/('synthetic-candidate-t120-angle040'+suffix+'.json')).read_text())
            inputs = candidate['input_candidates']
            report = math_checks.state_diagnostics(
                inputs['RRECTLEM']['encoded_si_readback'], inputs['VRECTLEM']['encoded_si_readback'],
                [candidate['lunar_reference_radius_m'], 0, 0], candidate['mu_m3_s2'], candidate['lunar_reference_radius_m'])
            self.assertAlmostEqual(report['altitude_above_reference_m'], altitude, delta=.5)
            self.assertAlmostEqual(report['speed_m_s'], report['circular_speed_at_radius_m_s'], delta=.001)
            self.assertAlmostEqual(report['radial_velocity_m_s'], 0, delta=.001)
            self.assertAlmostEqual(report['site_central_angle_rad'], .4, delta=1e-6)
            self.assertAlmostEqual(report['surface_arc_distance_m'], 695236, delta=.5)

    def test_half_unit_identity_matrix(self):
        words = sum(([0o20000, 0] if i == j else [0, 0]
                     for i in range(3) for j in range(3)), [])
        report = math_checks.matrix_diagnostics(words)
        self.assertEqual(report['determinant'], 1)
        self.assertEqual(report['max_orthogonality_error'], 0)

    def test_retained_phase9_actual_matrix(self):
        report = math_checks.phase9_report(DOCS/'phase9-evidence/runs/final/trace.jsonl.gz')
        self.assertTrue(report['agc_set_refsmflg'])
        self.assertLess(report['matrix']['max_orthogonality_error'], 1e-7)
        self.assertAlmostEqual(report['matrix']['determinant'], 1, delta=1e-7)
        self.assertLess(report['matrix']['max_identity_difference'], 3e-5)

    def test_zero_coefficients_are_degenerate(self):
        report = math_checks.coefficient_diagnostics([0]*8, [0, 0])
        self.assertTrue(report['degenerate_all_zero'])
        self.assertEqual(report['residual_fraction'], 0)
        self.assertEqual(report['derivative_fraction'], 0)
        self.assertIsNone(report['diagnostic_newton_correction_fraction'])

    def test_root_diagnostic_never_solves_or_changes_root(self):
        # A0=-1/4, A1=+1/2 and the observed x=+1/2 give zero residual.
        report = math_checks.coefficient_diagnostics([0o67777, 0o77777, 0o20000, 0, 0, 0, 0, 0], [0o20000, 0])
        self.assertEqual(report['residual_fraction'], 0)
        self.assertEqual(report['signed_time_to_go_seconds'], 655.36)
        self.assertTrue(report['derivative_coefficient_abs_lt_one'])

    def test_coefficient_operations_follow_source(self):
        self.assertEqual(math_checks.expected_coefficient_fractions(
            Fraction(1, 2), Fraction(1, 4), Fraction(1, 8),
            Fraction(-1, 16), Fraction(1, 32), Fraction(1, 64)),
            [Fraction(3, 32), Fraction(1, 32), Fraction(1, 32), Fraction(1, 64)])


if __name__ == '__main__':
    unittest.main()
