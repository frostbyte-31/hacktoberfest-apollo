#!/usr/bin/env python3
"""Assertions against real native runs, distinct from modern sensor unit tests."""
import os
from pathlib import Path
import unittest

import analyze


class NativePipaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Retained native captures work without a build cache. A fresh validator
        # supplies PHASE11_RUNS; missing artifacts remain real errors.
        runs = os.environ.get('PHASE11_RUNS', str(Path(__file__).resolve().parent/'runs/verified'))
        cls.result = analyze.experiment(Path(runs))

    def every_run(self, *checks):
        for name, run in self.result['runs'].items():
            for check in checks:
                self.assertTrue(run['checks'][check], name+': '+check)

    def comparison(self, *names):
        for name in names:
            self.assertTrue(self.result['comparisons'][name], name)

    def test_original_rope_and_source_integrity(self):
        self.every_run('unchanged_rope_and_no_flight_memory_writes','pinned_original_source_files_unchanged','original_baseline_integrity_guard_unchanged')

    def test_phase10_original_nine_roots_and_review_preserved(self):
        self.every_run('phase10_original_roots_and_review_preserved','original_p51_alignment_matrix_remains_valid')

    def test_source_hardware_addresses_and_signed_operations(self):
        self.every_run('source_counter_addresses','source_operation_sign_and_axis_mapping')

    def test_original_p47_readiness_and_navigation_execution(self):
        self.every_run('original_p47_selected_and_navigation_scheduled','original_calcrvg_interpreter_dispatch_observed','p47_uses_reference_navigation_route','no_new_program_alarms')

    def test_counter_events_are_accepted_and_observed_at_exact_cycles(self):
        self.every_run('input_packets_match_recorded_hardware_events','exact_requested_event_schedule_retained','every_pulse_has_genuine_next_cycle_counter_response')

    def test_physical_units_transform_and_sensor_quantization(self):
        self.every_run('sensor_si_force_and_duration_match_independent_transform','specific_force_subtracts_documented_nonzero_gravity','quantized_count_and_residual_match_physical_integral')

    def test_original_reader_consumes_pulses_and_clears_counters(self):
        self.every_run('original_servicer_consumes_exact_delivered_counts','original_reader_resets_genuine_counters_to_signed_zero','original_read_period_is_two_seconds')

    def test_original_navigation_updates_and_delta_v_accumulation(self):
        self.every_run('original_calcn83_accumulates_reference_delta_v','original_delta_v_transform_matches_rope_scaled_sensor_counts','navigation_rn_vn_copy_agrees_with_calculated_values','zero_bias_and_scale_error_are_observed_not_injected','navigation_state_stays_outside_lunar_reference_bound')

    def test_zero_specific_force_has_no_sensor_events(self):
        self.comparison('zero_specific_force_emits_no_pulses','zero_specific_force_still_has_original_gravity_velocity_change')

    def test_positive_force_original_velocity_and_position_response(self):
        self.comparison('positive_has_matched_original_piptime_samples','positive_original_velocity_matches_pipa_contribution','positive_original_position_response_is_causal','positive_original_accumulator_matches_quantized_force')

    def test_negative_force_original_velocity_and_position_response(self):
        self.comparison('negative_has_matched_original_piptime_samples','negative_original_velocity_matches_pipa_contribution','negative_original_position_response_is_causal','negative_original_accumulator_matches_quantized_force','positive_negative_velocity_responses_have_opposite_signs')

    def test_disconnection_is_a_real_causal_negative_control(self):
        self.every_run('disconnection_or_connection_observed')
        self.comparison('disconnected_original_velocity_matches_pipa_contribution','disconnected_original_position_response_is_causal','disconnected_matches_zero_navigation_words','disconnected_original_accumulator_matches_quantized_force')

    def test_deterministic_native_replay(self):
        self.comparison('positive_repeat_trace_byte_identical')

    def test_original_display_and_no_ignition(self):
        self.every_run('original_display_is_delta_velocity_n83','no_engine_on_commands_during_sensor_interval','only_dsky_and_source_pipa_hardware_inputs_after_review')

    def test_prior_evidence_preserved(self):
        self.every_run('preservation-before_all_prior_files_unchanged','preservation-after_all_prior_files_unchanged')

    def test_all_native_and_causal_checks_pass(self):
        self.assertTrue(self.result['all_pass'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
