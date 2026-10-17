# GPL-2.0-or-later.
"""One fresh locked-Tcl component run plus source/evidence boundary tests."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import apply_physics as adapter
import run_validation as validation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class FreshPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="apollo-phase7-physics-")
        cls.scratch = Path(cls.temporary.name).resolve()
        cls.source = cls.scratch / "source"
        hashes = json.loads((ROOT / "docs/phase6-evidence/corresponding-source-hashes.json").read_text())
        validation.reproduction.extract_source(ROOT / "docs/phase6-evidence/corresponding-source.tar.gz", cls.source, hashes)
        manifest_path = ROOT / ".build/reproducibility/runtime-manifest.json"
        manifest = validation.runtime_api.validate_runtime(manifest_path)
        cls.result_dir = cls.scratch / "results"
        argv = [sys.executable, "-B", HERE / "run_validation.py", "--source", cls.source,
            "--output", cls.result_dir, "--tcl", manifest["executable"], "--runtime-manifest", manifest_path]
        result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError("Actual physics component execution failed: " + result.stdout + result.stderr)
        cls.raw = (cls.result_dir / "physics.stdout").read_text()
        cls.legacy = (cls.result_dir / "legacy-yaw.stdout").read_text()
        cls.outcome = validation.analyze(cls.raw, cls.legacy)
        cls.audit = json.loads((cls.result_dir / "source-audit.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_fresh_actual_execution_and_complete_markers(self):
        commands = json.loads((self.result_dir / "commands.json").read_text())
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(row["exit"] == 0 for row in commands))
        self.assertEqual((self.result_dir / "physics.stderr").read_text(), "")
        self.assertEqual((self.result_dir / "legacy-yaw.stderr").read_text(), "")
        self.assertTrue(all(self.outcome["checks"].values()))

    def test_source_locked_selectors_and_exact_decode(self):
        changes = [line for line in self.audit["imu_diff"].splitlines()
                   if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        self.assertEqual(len(changes), 6)
        self.assertEqual(len(self.audit["selector_replacements"]), 3)
        self.assertIn(self.audit["exact_legacy_decode"], adapter.SERVER.read_text())
        self.assertFalse(self.audit["upstream_modified"])
        self.assertEqual(adapter.digest(self.source / adapter.IMU), self.audit["source_hashes"][adapter.IMU])

    def test_coordinate_roundtrip_and_rotation_matrix(self):
        self.assertLess(self.outcome["roundtrip_max_deg"], 1e-10)
        self.assertLess(self.outcome["rotation_matrix_max_error"], 1e-13)
        self.assertLess(self.outcome["orthogonality_max_error"], 1e-13)

    def test_original_gimbal_jacobian_matches_body_rate_quaternion(self):
        self.assertLess(self.outcome["original_jacobian_max_deg"], 1e-10)

    def test_constant_principal_torque_uses_declared_semiimplicit_step(self):
        self.assertTrue(self.outcome["checks"]["constant_principal_torque"])

    def test_unequal_inertia_torque_free_energy_and_momentum_norm(self):
        for row in self.outcome["torque_free"]:
            self.assertLess(row["energy_absolute_error"], 1e-10)
            self.assertLess(row["momentum_norm_squared_error"], 1e-10)
            self.assertLess(row["quaternion_norm_error"], 1e-13)

    def test_inertial_momentum_direction_converges_at_first_order(self):
        coarse, fine = self.outcome["torque_free"]
        ratio = fine["inertial_momentum_relative_error"]/coarse["inertial_momentum_relative_error"]
        self.assertGreater(ratio, .45)
        self.assertLess(ratio, .55)

    def test_assumed_inertias_and_source_jet_torque_are_positive_physical(self):
        yaw = self.outcome["vehicles"]["yaw"][0]
        expected = [20681.71127225267, 20381.255503614386, 20565.10208054076]
        for actual, wanted in zip(yaw["inertia_before"], expected):
            self.assertAlmostEqual(actual, wanted, places=8)
        self.assertAlmostEqual(yaw["values"][13], 1780, places=7)
        self.assertLess(yaw["mass_after"], yaw["mass_before"])
        i, j, k = yaw["inertia_before"]
        self.assertTrue(i+j > k and j+k > i and i+k > j)

    def test_two_torques_include_induced_third_axis_motion(self):
        values = self.outcome["vehicles"]["coupled"][-1]["values"]
        self.assertGreater(values[0], 0)
        self.assertGreater(values[1], 0)
        self.assertGreater(abs(values[2]), 1e-6)
        self.assertGreater(abs(values[5]), 1e-6)
        self.assertAlmostEqual(values[15], 0, places=7)

    def test_yaw_remains_within_legacy_predeclared_tolerance(self):
        self.assertLess(self.outcome["yaw_legacy_max_rate_difference_deg_s"], 1e-9)
        self.assertLess(self.outcome["yaw_legacy_max_angle_difference_deg"], 360/32768)

    def test_principal_physical_motion_emits_correct_signed_cdu_axis(self):
        self.assertTrue(self.outcome["checks"]["principal_signed_sensor_counters"])

    def test_translation_logs_suppression_and_never_produces_pipa(self):
        self.assertTrue(self.outcome["checks"]["translation_explicitly_suppressed_without_pipa"])

    def test_bounds_and_nonconvergence_fail_explicitly(self):
        self.assertEqual(len(self.outcome["rejected_cases"]), 5)
        self.assertIn("20 iterations", self.outcome["rejected_cases"]["nonconvergence"])
        self.assertIn("80 degrees", self.outcome["rejected_cases"]["singularity"])

    def test_parser_rejects_incomplete_or_wrong_convention_trace(self):
        with self.assertRaises(ValueError):
            validation.analyze(self.raw.replace("PHASE7_PHYSICS_COMPONENT_COMPLETE", ""), self.legacy)
        lines = self.raw.splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("roundtrip|17"))
        fields = lines[index].split("|")
        fields[2] = "0 0 0"
        lines[index] = "|".join(fields)
        with self.assertRaisesRegex(ValueError, "checks failed"):
            validation.analyze("\n".join(lines), self.legacy)

    def test_adapter_rejects_changed_source_and_existing_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            wrong = root / "wrong-source" / adapter.IMU
            wrong.parent.mkdir(parents=True)
            wrong.write_text("changed")
            target = root / "not-created.tcl"
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                adapter.apply_physics(root / "wrong-source", target)
            self.assertFalse(target.exists())
            target.write_text("existing")
            with self.assertRaisesRegex(ValueError, "exists"):
                adapter.apply_physics(self.source, target)
            self.assertEqual(target.read_text(), "existing")

    def test_adapter_protects_retained_paths_and_symlinks(self):
        with self.assertRaisesRegex(ValueError, "scratch"):
            adapter.new_scratch(HERE / "not-created.tcl")
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "alias"
            alias.symlink_to(Path(directory) / "missing")
            with self.assertRaisesRegex(ValueError, "symlink"):
                adapter.new_scratch(alias)


if __name__ == "__main__":
    unittest.main()
