# GPL-2.0-or-later.
"""No-runtime tests of source locking and captured paired component execution."""
import copy
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import fix_selector as adapter
import run_validation as validation

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


class SourceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tarfile.open(adapter.ROOT / "docs/phase6-evidence/corresponding-source.tar.gz") as archive:
            cls.original = archive.extractfile(adapter.IMU_RELATIVE.as_posix()).read()
        if hashlib.sha256(cls.original).hexdigest() != adapter.ORIGINAL_SHA256:
            raise ValueError("Original retained bundle changed")

    def test_only_selector_changes_in_original_body_plus_explicit_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            source = scratch / "original.tcl"
            source.write_bytes(self.original)
            derived = scratch / "derived.tcl"
            audit = adapter.apply_selector(source, derived)
            expected = self.original.decode().replace(adapter.ORIGINAL_SELECTOR, adapter.CORRECTED_SELECTOR, 1)
            self.assertEqual(derived.read_text(), expected + adapter.AXIS_GUARD)
            self.assertEqual(source.read_bytes(), self.original)
            self.assertEqual(audit["selector_changed_line"], 527)
            self.assertEqual(audit["selector_replacements"], 1)
            self.assertEqual(audit["bounded_module_sha256"], hashlib.sha256(derived.read_bytes()).hexdigest())
            self.assertEqual(audit["selector_only_sha256"], hashlib.sha256(expected.encode()).hexdigest())
            changed_lines = [line for line in audit["selector_diff"].splitlines()
                             if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
            self.assertEqual(changed_lines, ["-     " + adapter.ORIGINAL_SELECTOR,
                                            "+     " + adapter.CORRECTED_SELECTOR])

    def test_source_root_input_selects_only_locked_complete_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            source = scratch / "root" / adapter.IMU_RELATIVE
            source.parent.mkdir(parents=True)
            source.write_bytes(self.original)
            audit = adapter.apply_selector(scratch / "root", scratch / "derived.tcl")
            self.assertEqual(Path(audit["source"]), source.resolve())

    def test_modified_source_fails_before_creating_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            source = scratch / "wrong.tcl"
            source.write_bytes(self.original + b"\n")
            derived = scratch / "must-not-exist.tcl"
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                adapter.apply_selector(source, derived)
            self.assertFalse(derived.exists())

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            source, derived = scratch / "original.tcl", scratch / "existing.tcl"
            source.write_bytes(self.original)
            derived.write_text("retained")
            with self.assertRaisesRegex(ValueError, "existing"):
                adapter.apply_selector(source, derived)
            self.assertEqual(derived.read_text(), "retained")

    def test_retained_and_symlink_destinations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "scratch"):
            adapter.validate_destination(HERE / "not-created.tcl")
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            target = scratch / "target.tcl"
            link = scratch / "alias.tcl"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                adapter.validate_destination(link)
            self.assertFalse(target.exists())


class PairedComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = validation.prior.scenarios()
        cls.original = validation.prior.parse_output((RESULTS / "original.stdout").read_text(), cls.cases)
        cls.corrected = validation.prior.parse_output((RESULTS / "corrected.stdout").read_text(), cls.cases)
        cls.summary = {row["id"]: row for row in validation.prior.summarize(cls.cases, cls.corrected)}

    def test_real_tcl_processes_completed_with_locked_runtime(self):
        commands = json.loads((RESULTS / "commands.json").read_text())
        self.assertEqual([row["label"] for row in commands], ["original", "corrected", "axis-guard"])
        self.assertTrue(all(row["exit"] == 0 for row in commands))
        for row in commands:
            self.assertEqual((RESULTS / (row["label"] + ".stderr")).read_text(), "")
        environment = json.loads((RESULTS / "environment.json").read_text())
        self.assertEqual(environment["runtime"]["version"], "8.6.16")
        self.assertEqual(len(self.original), 1014)

    def test_pair_reconciliation_changes_only_1455_packet_modes(self):
        result = validation.paired_validation(self.original, self.corrected)
        self.assertEqual(result["changed_packet_modes"], 1455)
        self.assertTrue(result["equal_numerical_states"])
        self.assertTrue(result["equal_counts_and_directions"])

    def test_original_raw_output_matches_retained_milestone2_exactly(self):
        self.assertEqual((RESULTS / "original.stdout").read_bytes(),
            (validation.M2 / "results/probe.stdout").read_bytes())

    def test_both_signs_switch_at_exact_four_degree_threshold(self):
        for rate, operation in ((3.999, "PCDU"), (-3.999, "MCDU"),
                                (4.0, "PCDU_FAST"), (-4.0, "MCDU_FAST"),
                                (8.0, "PCDU_FAST"), (-8.0, "MCDU_FAST")):
            row = self.summary["rate_" + str(rate)]
            self.assertEqual(row["operations"], {operation: row["pulse_count"]})

    def test_direction_still_comes_from_signed_gimbal_delta(self):
        self.assertEqual(self.summary["opposite_delta_8.0"]["operations"], {"MCDU_FAST": 1})
        self.assertEqual(self.summary["opposite_delta_-8.0"]["operations"], {"PCDU_FAST": 1})

    def test_quantization_wrap_and_inhibits_are_numerically_unchanged(self):
        old_summary = {row["id"]: row for row in validation.prior.summarize(self.cases, self.original)}
        for name, row in self.summary.items():
            if not name.startswith(("rate_", "opposite_delta_")):
                self.assertEqual(row, old_summary[name])

    def test_unsupported_axes_rejected_before_any_gimbal_or_packet_change(self):
        lines = (RESULTS / "axis-guard.stdout").read_text().splitlines()
        self.assertEqual(lines[-1], "AXIS_GUARD_COMPLETE")
        self.assertEqual([line.split("\t") for line in lines[:-1]],
            [[name, "1", "APOLLO MILESTONE3 UNSUPPORTED_AXIS", "UNCHANGED"]
             for name in ("Y", "Z", "ZERO", "LOCKED")])

    def test_reconciler_rejects_missing_pulse_and_changed_numerics(self):
        for field in ("packets", "imu_x_deg"):
            broken = copy.deepcopy(self.corrected)
            row = next(row for row in broken if row["id"] == "rate_-8.0" and row["packets"])
            if field == "packets":
                row["packets"].pop()
            else:
                row[field] += 0.001
            with self.assertRaisesRegex(ValueError, "state|pulse count"):
                validation.paired_validation(self.original, broken)

    def test_reconciler_rejects_faked_fast_mode_for_slow_motion(self):
        broken = copy.deepcopy(self.corrected)
        row = next(row for row in broken if row["id"] == "rate_-1.0" and row["packets"])
        row["packets"][0] = {"op": "MCDU_FAST", "counter_octal": "32", "code_decimal": 19}
        with self.assertRaisesRegex(ValueError, "packet"):
            validation.paired_validation(self.original, broken)


if __name__ == "__main__":
    unittest.main()
