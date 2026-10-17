#!/usr/bin/env python3
"""Evidence assertions over actual native AGC executions, not synthetic outputs."""
import os
from pathlib import Path
import unittest

import analyze


class NativePropulsionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = os.environ.get('PHASE12_RUNS', str(Path(__file__).resolve().parent/'runs/verified'))
        cls.result = analyze.experiment(Path(directory))

    def every(self, *checks):
        for name, result in self.result['runs'].items():
            for check in checks:
                self.assertTrue(result['checks'][check], name+': '+check)

    def comparison(self, *checks):
        for check in checks:
            self.assertTrue(self.result['comparisons'][check],check)

    def test_original_rope_and_source_integrity(self):
        self.every('original_rope_no_flight_memory_writes','original_pinned_source_unchanged',
                   'original_phase10_baseline_guard_unchanged')

    def test_capture_checksums_instruction_observers_and_hardware_boundary(self):
        self.every('raw_capture_complete_monotonic_and_observer_map_matches',
                   'only_documented_hardware_input_channels')

    def test_original_alignment_p27_p63_and_crew_review(self):
        self.every('original_p51_reference_readiness_and_p63_review',
                   'original_dsky_v48_mass_load','original_crew_and_preignition_continuation')

    def test_engine_enable_request_is_not_an_ignition_claim(self):
        self.every('original_v99_crew_request_is_separate_from_engine_on',
                   'original_ignition_instruction_emits_engine_on')

    def test_engine_off_and_bounded_original_shutdown(self):
        self.every('engine_off_reset_observed_before_ignition',
                   'bounded_p63_horizon_followed_by_original_p00_shutdown',
                   'original_engine_off_cancels_reset_without_fabricated_counter_settlement',
                   'crew_disarm_is_separate_from_original_software_reset',
                   'physical_engine_off_stops_force_and_propellant_flow')

    def test_original_zoom_flatout_and_real_thrust_counter(self):
        self.every('original_p63_zoom_and_flatout_execute','flatout_original_counter_load_is_4096',
                   'flatout_sink_emits_4096_uninterrupted_positive_pulses',
                   'genuine_dinc_drives_counter_outputs',
                   'external_thrust_clock_has_source_3200_hz_phase',
                   'hardware_drive_latch_clear_requires_genuine_zout')

    def test_physical_thrust_mass_flow_and_three_dimensional_translation(self):
        self.every('physical_engine_model_observations_present',
                   'physical_units_frame_gravity_integration_and_mass_flow',
                   'zero_force_before_authentic_ignition',
                   'disconnected_engine_or_connected_physical_motion')

    def test_engine_connection_causes_physical_motion(self):
        self.comparison('same_authentic_ignition_cycle',
                        'engine_connection_causes_physical_velocity_position_and_fuel_change')

    def test_pipa_hardware_mapping_quantization_and_bounded_timing(self):
        self.every('source_pipa_addresses_and_sign_operations',
                   'bounded_sensor_coupling_and_real_packet_acceptance',
                   'physical_sensor_count_and_delivery_match')

    def test_original_reader_consumes_exact_physical_sensor_counts(self):
        self.every('original_navigation_consumes_delivered_counts')
        self.comparison('only_connected_feedback_delivers_pipa_hardware',
                        'engine_derived_feedback_reaches_original_navigation')

    def test_original_moon_navigation_matches_independent_arithmetic(self):
        self.every('original_munrvg_math_matches_independent_pulse_and_gravity_arithmetic',
                   'original_munrvg_period_remains_two_seconds')

    def test_causal_original_navigation_response(self):
        self.comparison('matched_original_navigation_epochs_sink',
                        'matched_original_navigation_epochs_no-feedback',
                        'independent_original_velocity_difference_budget_sink',
                        'independent_original_velocity_difference_budget_no-feedback',
                        'feedback_changes_original_navigation_words',
                        'disconnected_feedback_preserves_sink_original_navigation')

    def test_causal_original_guidance_and_throttle_response(self):
        self.comparison('feedback_changes_original_control_execution',
                        'feedback_changes_authentic_throttle_counter_output')

    def test_deterministic_native_repetition(self):
        self.comparison('connected_repeat_trace_byte_identical')

    def test_all_prior_evidence_preserved(self):
        self.every('preservation-before_all_prior_files_unchanged',
                   'preservation-after_all_prior_files_unchanged')

    def test_all_native_and_causal_assertions(self):
        self.assertTrue(self.result['all_pass'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
