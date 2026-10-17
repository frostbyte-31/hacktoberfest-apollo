#!/usr/bin/env python3
"""Evidence/causality tests involving actual original Luminary native execution."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('phase10_actual_analysis', HERE/'analyze.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
RUNS = Path(os.environ.get('PHASE10_RUNS', str(HERE/'runs/final-validation')))


class MissionEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = analysis.experiment(RUNS, RUNS/'phase9-baseline/analysis.json')
        cls.independent = json.loads((RUNS/'final-independent-math.json').read_text())

    def test_original_rope_is_unchanged(self):
        import hashlib
        self.assertEqual(hashlib.sha256((ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()).hexdigest(), analysis.p9.ROPE_SHA)

    def test_phase9_remains_exact_reproducible_negative_control(self):
        self.assertTrue(self.result['comparisons']['phase9_negative_baseline_reproduced_without_changes'])

    def test_p51_p27_and_r02_use_actual_original_paths(self):
        self.assertTrue(self.result['run']['all_pass'], self.result['run']['checks'])

    def test_source_supported_mission_input_values_reach_permanent_state(self):
        for name in ('run', 'repeat', 'altitude_variant'):
            checks = self.result[name]['checks']
            self.assertTrue(checks['all_configured_inputs_have_real_p27_transactions'])
            self.assertTrue(checks['state_update_original_intwake_clears_identifier_and_populates_permanent_state'])

    def test_lunar_state_is_coherent_circular_and_bound(self):
        for name, altitude in [('run', 15000), ('altitude_variant', 16000)]:
            diag = self.result[name]['input_state_independent_diagnostics']
            self.assertAlmostEqual(diag['altitude_above_reference_m'], altitude, delta=1)
            self.assertLess(abs(diag['radial_velocity_m_s']), .001)
            self.assertAlmostEqual(diag['speed_m_s'], diag['circular_speed_at_radius_m_s'], delta=.001)

    def test_actual_coefficients_are_nonzero_and_source_formula_agrees(self):
        records = self.result['run']['polynomial_entries']
        self.assertGreater(len(records), 0)
        for record in records:
            self.assertFalse(record['observed']['degenerate_all_zero'])
            self.assertTrue(record['observed']['derivative_coefficient_abs_lt_one'])
            self.assertLessEqual(max(map(abs, record['independent_formula_error_DP_LSB'])), 2)

    def test_each_actual_root_has_good_original_continuation(self):
        for record in self.result['run']['returned_roots']:
            self.assertTrue(record['actual_normal_return_and_original_TTF_store'])
            self.assertIn(record['iterations'], range(1, 9))
            self.assertTrue(record['residual_within_original_step_tolerance_plus_32_DP_LSB'])

    def test_refsm_and_guidance_matrices_are_proper_rotations(self):
        for record in self.independent['passes']:
            for name in ('REFSMMAT', 'CG'):
                self.assertLess(record[name]['max_orthogonality_error'], 1e-6)
                self.assertAlmostEqual(record[name]['determinant'], 1, delta=1e-6)

    def test_actual_position_and_guidance_transform_consistency(self):
        for record in self.independent['passes']:
            diag = record['INDEPENDENT_VALIDATION']
            self.assertLess(diag['LAND_current_epoch_error_norm_m'], 2)
            self.assertLess(max(map(abs, diag['R_minus_REFSM_transformed_RATT1_m'])), 1)
            self.assertLess(max(map(abs, diag['RGU_minus_CG_R_minus_LAND_m'])), 1)
            self.assertLess(max(map(abs, diag['VGU_minus_CG_surface_velocity_m_s'])), .01)

    def test_original_ignition_time_is_future_and_stops_at_crew_review(self):
        run = self.result['run']
        self.assertGreater(len(run['ignition_solution']), 0)
        self.assertGreater(run['ignition_solution'][0]['TIG_cs'], run['ignition_solution'][0]['TIME2_cs'])
        self.assertEqual(run['final_state']['display']['NOUN'], '61')
        self.assertEqual(run['final_state']['failreg'], [0o1520, 0, 0])

    def test_exact_native_replay_and_causal_altitude_change(self):
        self.assertTrue(self.result['comparisons']['full_repeat_native_trace_byte_identical'])
        self.assertTrue(self.result['comparisons']['coherent_altitude_change_changes_original_coefficients_and_root'])

    def test_missing_site_reaches_genuine_failed_root_path(self):
        self.assertTrue(self.result['missing_site_control']['all_pass'])
        self.assertTrue(self.result['comparisons']['missing_landing_site_changes_actual_root_behavior'])

    def test_all_prior_tracked_inputs_preserved(self):
        spec = importlib.util.spec_from_file_location('p10_preservation', HERE/'run_mission.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.preserve()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['files_checked'], 4098)

    def test_corrupted_telemetry_does_not_validate(self):
        run = analysis.p9.load_run(RUNS/'final')
        row = next(r for r in run['rows'] if r['ev'] == 'checkpoint' and r['routine'] == 'ROOTPSRS')
        idx = run['mapping']['snapshot_addresses'].index(run['mapping']['addresses']['TABLTTF'])
        row['snapshot_words'][idx] ^= 0o1000
        with tempfile.TemporaryDirectory(prefix='phase10-tamper-') as folder:
            path = Path(folder)
            for name in ('observer-map.json', 'configuration.json'):
                (path/name).write_bytes((RUNS/'final'/name).read_bytes())
            (path/'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in run['rows'])+'\n')
            result = analysis.analyze_run(path)
            self.assertFalse(result['all_pass'])
            self.assertFalse(result['checks']['original_coefficients_match_independent_operand_formulas_within_2_DP_LSB'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
