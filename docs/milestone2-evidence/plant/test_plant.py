# GPL-2.0-or-later.
"""Tests of captured real pinned-model behavior and evidence rejection guards."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("signed_plant_probe", HERE / "run_validation.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class CapturedPlantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = HERE / "results"
        cls.cases = json.loads((cls.results / "scenarios.json").read_text())
        cls.stdout = (cls.results / "probe.stdout").read_text()
        cls.rows = probe.parse_output(cls.stdout, cls.cases)
        cls.summary = probe.summarize(cls.cases, cls.rows)
        cls.by_id = {row["id"]: row for row in cls.summary}

    def test_actual_process_completed_with_locked_tcl(self):
        commands = json.loads((self.results / "commands.json").read_text())
        self.assertEqual(commands[0]["exit"], 0)
        self.assertEqual((self.results / "probe.stderr").read_text(), "")
        environment = json.loads((self.results / "environment.json").read_text())
        self.assertEqual(environment["runtime_manifest"]["version"], "8.6.16")
        self.assertEqual(len(self.rows), 1014)

    def test_summary_recomputes_from_raw_process_output(self):
        retained = json.loads((self.results / "summary.json").read_text())
        self.assertEqual(self.summary, retained)
        probe.validate_measurements(self.summary)

    def test_matched_slow_signed_motion_emits_opposite_counts(self):
        self.assertEqual(self.by_id["rate_1.0"]["operations"], {"PCDU": 90})
        self.assertEqual(self.by_id["rate_-1.0"]["operations"], {"MCDU": 90})

    def test_positive_four_threshold_switches_mode(self):
        self.assertEqual(self.by_id["rate_3.999"]["operations"], {"PCDU": 363})
        self.assertEqual(self.by_id["rate_4.0"]["operations"], {"PCDU_FAST": 363})
        self.assertEqual(self.by_id["rate_4.001"]["operations"], {"PCDU_FAST": 364})

    def test_existing_negative_fast_motion_selects_slow_mode(self):
        self.assertEqual(self.by_id["rate_8.0"]["operations"], {"PCDU_FAST": 727})
        self.assertEqual(self.by_id["rate_-8.0"]["operations"], {"MCDU": 727})
        self.assertGreater(self.by_id["rate_-8.0"]["pulse_count_per_second"], 400)

    def test_delta_controls_direction_independently_of_rate_selector(self):
        self.assertEqual(self.by_id["opposite_delta_8.0"]["operations"], {"MCDU_FAST": 1})
        self.assertEqual(self.by_id["opposite_delta_-8.0"]["operations"], {"PCDU": 1})

    def test_exact_increment_is_retained_until_exceeded(self):
        for sign in (1, -1):
            self.assertEqual(self.by_id[f"quant_{sign}_1.0"]["pulse_count"], 0)
            self.assertEqual(self.by_id[f"quant_{sign}_1.001"]["pulse_count"], 1)
            self.assertEqual(self.by_id[f"quant_{sign}_2.0"]["pulse_count"], 1)

    def test_zeroing_and_lock_inhibits_still_apply(self):
        for name in ("inhibit_zero", "inhibit_locked"):
            self.assertEqual(self.by_id[name]["pulse_count"], 0)
            self.assertEqual(self.by_id[name]["final_imu_x_deg"], 0)

    def test_angle_wrap_keeps_short_signed_direction(self):
        self.assertEqual(self.by_id["wrap_positive"]["operations"], {"PCDU": 2})
        self.assertEqual(self.by_id["wrap_negative"]["operations"], {"MCDU": 2})

    def test_only_x_gimbal_and_octal_counter_32_are_observed(self):
        for row in self.rows:
            self.assertEqual((row["imu_y_deg"], row["imu_z_deg"], row["omega_pitch"], row["omega_roll"]), (0, 0, 0, 0))
            self.assertEqual(row["increment_deg"], 360 / 32768)
            for packet in row["packets"]:
                self.assertEqual(packet["counter_octal"], "32")

    def test_parse_fails_without_completion_marker(self):
        with self.assertRaisesRegex(ValueError, "completion"):
            probe.parse_output(self.stdout.rsplit("COMPONENT_PROBE_COMPLETE", 1)[0], self.cases)

    def test_parse_rejects_cross_axis_state(self):
        lines = self.stdout.splitlines()
        fields = lines[1].split("\t")
        fields[6] = "1.0"
        lines[1] = "\t".join(fields)
        with self.assertRaisesRegex(ValueError, "cross-axis"):
            probe.parse_output("\n".join(lines), self.cases)

    def test_parse_rejects_cross_axis_counter(self):
        raw = self.stdout.replace("PCDU,32", "PCDU,33", 1)
        with self.assertRaisesRegex(ValueError, "cross-axis"):
            probe.parse_output(raw, self.cases)

    def test_parse_rejects_duplicate_steps(self):
        lines = self.stdout.splitlines()
        lines.insert(2, lines[1])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            probe.parse_output("\n".join(lines), self.cases)

    def test_measurements_reject_fabricated_signed_agreement(self):
        summary = copy.deepcopy(self.summary)
        for case in summary:
            if case["id"] == "rate_-8.0":
                case["operations"] = {"MCDU_FAST": case["pulse_count"]}
        with self.assertRaisesRegex(ValueError, "selector"):
            probe.validate_measurements(summary)

    def test_output_guard_rejects_retained_evidence(self):
        with self.assertRaisesRegex(ValueError, "Generated results"):
            probe.validate_output(HERE / "new-attempt-must-not-be-created")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "exists"):
                probe.validate_output(Path(directory))


if __name__ == "__main__":
    unittest.main()
