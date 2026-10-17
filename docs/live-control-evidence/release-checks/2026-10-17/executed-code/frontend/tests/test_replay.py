"""Checks the presentation export against genuine retained native traces."""

import gzip
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "tools/export_replay.py"
SPEC = importlib.util.spec_from_file_location("export_replay", TOOL)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class ReplayExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replay = exporter.build_replay()
        cls.cases = {case["id"]: case for case in cls.replay["cases"]}
        cls.rows = {}
        for case in cls.replay["cases"]:
            path = exporter.ROOT / case["source"]["tracePath"]
            cls.rows[case["id"]] = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]

    def test_real_export_is_current_and_deterministic(self):
        self.assertEqual(exporter.DEFAULT_OUTPUT.read_bytes(), exporter.encoded(self.replay))
        self.assertEqual(exporter.encoded(self.replay), exporter.encoded(exporter.build_replay()))

    def test_five_cases_and_evidence_level_are_explicit(self):
        self.assertEqual(list(self.cases), ["yaw", "pitch", "pitch_off", "combined", "combined_off"])
        self.assertEqual(self.replay["schemaVersion"], 1)
        self.assertTrue(self.replay["provenance"]["capability"].startswith("C"))
        for key, case in self.cases.items():
            self.assertEqual(case["feedbackConnected"], not key.endswith("_off"))

    def test_clock_horizons_and_queue_tail(self):
        for key, case in self.cases.items():
            horizon = 3200000 if key.startswith("combined") else 4000000
            self.assertEqual(case["horizonCycle"], horizon)
            self.assertEqual(case["durationSeconds"], horizon * 12 / 1024000)
            self.assertGreaterEqual(case["settledCycle"], horizon)
            self.assertEqual(case["quietCycle"], case["settledCycle"] + 1000)
            for frame in case["frames"]:
                self.assertAlmostEqual(frame["t"], frame["cycle"] * 12 / 1024000, places=12)
        combined = self.cases["combined"]
        self.assertEqual(combined["frames"][-1]["cdu"][1], 1476)
        self.assertEqual(combined["finalCdu"][1], 1477)
        self.assertEqual(combined["settledCycle"], 3200034)

    def test_every_frame_is_an_exact_original_model_sample(self):
        fields = {"q": "quaternion", "omega": "omega", "gimbals": "gimbals", "torque": "torque_Nm", "alpha": "alpha_rad_s2", "rcs": "jets"}
        for key, case in self.cases.items():
            plants = {row["cycle"]: row for row in self.rows[key] if row["ev"] == "plant"}
            for frame in case["frames"]:
                original = plants[frame["cycle"]]
                for field, source in fields.items():
                    self.assertEqual(frame[field], original[source], (key, frame["cycle"], field))

    def test_display_sampling_is_bounded_and_endpoints_retained(self):
        for key, case in self.cases.items():
            self.assertLess(len(case["frames"]), 500)
            times = [frame["t"] for frame in case["frames"]]
            self.assertTrue(all(a < b for a, b in zip(times, times[1:])))
            self.assertLess(max(b - a for a, b in zip(times, times[1:])), 0.111)
            self.assertEqual(case["frames"][-1]["cycle"], case["horizonCycle"])
            for field, source in [("q", "quaternion"), ("omega", "omega"), ("gimbals", "gimbals")]:
                self.assertEqual(case["frames"][-1][field], case["finalModel"][source])

    def test_quaternion_normalization_and_signed_body_rates(self):
        for case in self.cases.values():
            for frame in case["frames"]:
                self.assertLess(abs(sum(v * v for v in frame["q"]) - 1), 1e-12)
                self.assertTrue(all(math.isfinite(value) for field in ["q", "omega", "gimbals", "torque", "alpha"] for value in frame[field]))
        self.assertLess(self.cases["combined"]["finalModel"]["omega"][0], 0)
        self.assertGreater(self.cases["combined"]["finalModel"]["omega"][1], 0)
        self.assertLess(self.cases["yaw"]["finalModel"]["gimbals"][0], 360)
        self.assertGreater(self.cases["yaw"]["finalModel"]["gimbals"][0], 300)

    def test_exact_agc_output_packet_sequence_is_preserved(self):
        for key, case in self.cases.items():
            actual = [(row["cycle"], row["channel"], row["value"], row["tail"]) for row in self.rows[key] if row["ev"] == "output" and row["channel"] in (5, 6)]
            exported = [(row["cycle"], row["channel"], row["value"], row["tail"]) for row in case["rcsEvents"]]
            self.assertEqual(exported, actual)
            self.assertTrue(any(row["value"] != 0 for row in case["rcsEvents"]))
            self.assertTrue(any(row["changed"] for row in case["rcsEvents"]))

    def test_readiness_and_cdu_are_only_prior_actual_readbacks(self):
        for key, case in self.cases.items():
            cdu = []
            readiness = []
            for row in self.rows[key]:
                if row["ev"] in ("startup_checkpoint", "freeze"):
                    cdu.append((row["cycle"], row["state"]["cdu"]))
                elif row["ev"] == "application":
                    cdu.append((row["cycle"], row["after"]["cdu"]))
                if row["ev"] == "execution_sample":
                    readiness.append((row["cycle"], {"cycle": row["cycle"], **row["registers"]}))
                elif row["ev"] == "startup_checkpoint":
                    readiness.append((row["cycle"], {field: row[field] for field in ("cycle", "modreg", "failreg", "dapbools", "imodes30", "imodes33")}))
            cdu.sort(key=lambda item: item[0])
            readiness.sort(key=lambda item: item[0])
            for frame in case["frames"]:
                self.assertEqual(frame["cdu"], exporter.latest(cdu, frame["cycle"]))
                self.assertEqual(frame["readiness"], exporter.latest(readiness, frame["cycle"]))
                if frame["readiness"]:
                    self.assertLessEqual(frame["readiness"]["cycle"], frame["cycle"])
            self.assertIsNone(case["frames"][0]["cdu"])

    def test_disconnected_controls_keep_zero_actual_counters(self):
        for key in ["pitch_off", "combined_off"]:
            case = self.cases[key]
            self.assertEqual(case["sensorsApplied"], 0)
            self.assertEqual(case["finalCdu"], [0, 0, 0])
            self.assertGreater(sum(axis["intentional_omissions"] for axis in case["counts"]), 0)
            self.assertTrue(all(frame["cdu"] in (None, [0, 0, 0]) for frame in case["frames"]))
        self.assertEqual(self.cases["pitch"]["sensorsApplied"], 1707)
        self.assertEqual(self.cases["combined"]["sensorsApplied"], 2960)
        self.assertNotEqual(self.cases["combined"]["finalModel"]["omega"], self.cases["combined_off"]["finalModel"]["omega"])

    def test_no_altitude_position_or_dsky_is_invented(self):
        self.assertEqual(self.replay["labels"]["missing"], {"altitude": None, "position": None, "dsky": None})
        for case in self.cases.values():
            for frame in case["frames"]:
                for key in ("altitude", "position", "dsky"):
                    self.assertIsNone(frame[key])

    def test_pinned_trace_hashes_match_both_compressed_and_raw_bytes(self):
        retention = json.loads(exporter.checked_bytes(exporter.EVIDENCE / "retention.json", exporter.RETENTION_SHA256))
        records = {item["retained_path"]: item for item in retention["lossless_trace_compression"]}
        for key, case in self.cases.items():
            compressed = (exporter.ROOT / case["source"]["tracePath"]).read_bytes()
            record = records[f"validation/integration/{key}.jsonl.gz"]
            self.assertEqual(exporter.sha256(compressed), record["gzip_sha256"])
            self.assertEqual(exporter.sha256(gzip.decompress(compressed)), record["sha256"])

    def test_integrity_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.jsonl"
            path.write_bytes(b"changed trace")
            with self.assertRaisesRegex(ValueError, "Integrity mismatch"):
                exporter.checked_bytes(path, exporter.ROPE_SHA256)


if __name__ == "__main__":
    unittest.main()
