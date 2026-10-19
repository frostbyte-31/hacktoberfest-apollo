"""Evidence-to-presentation checks; these do not replace native AGC tests."""

import gzip
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools/export_guidance.py"
SPEC = importlib.util.spec_from_file_location("educational_guidance_export", TOOL)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class GuidanceDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = exporter.build_guidance()
        cls.cases = {case["id"]: case for case in cls.data["cases"]}
        cls.rows = {case["id"]: [json.loads(line) for line in gzip.decompress(
            (exporter.ROOT / case["sources"]["tracePath"]).read_bytes()).splitlines()]
            for case in cls.data["cases"]}
        cls.analyzer = exporter.module("mvp_test_p10_analysis", exporter.EVIDENCE / "analyze.py")

    def row(self, identifier, pointer):
        row = self.rows[identifier][pointer["rawLine"] - 1]
        self.assertEqual(row["cycle"], pointer["cycle"])
        return row

    def test_generated_data_is_current_and_byte_deterministic(self):
        self.assertEqual(exporter.DEFAULT_OUTPUT.read_bytes(), exporter.encoded(self.data))
        self.assertEqual(exporter.encoded(self.data), exporter.encoded(exporter.build_guidance()))

    def test_static_illustration_dot_product_keeps_export_order_across_python_versions(self):
        # Python3.12+ sum(float) preserves the two unit terms; Python3.11's
        # left-to-right sum rounds both away. Serialized presentation geometry
        # must use the existing order regardless of the host Python version.
        terms = [1e16, 1., 1.]
        self.assertEqual(math.fsum(terms), 1e16+2)
        self.assertEqual(exporter.ordered_dot3(terms, [1., 1., 1.]), 1e16)
        self.assertEqual(self.cases['nominal']['initialState']['landingSiteBasicRefAtTlandM'][0],
                         1738089.94652812)
        self.assertEqual(self.cases['altitude-16km']['initialState']['landingSiteBasicRefAtTlandM'][0],
                         1738089.94652812)

    def test_only_three_verified_cases_and_recorded_mode_are_exposed(self):
        self.assertEqual(list(self.cases), ["nominal", "altitude-16km", "missing-site"])
        self.assertEqual(self.data["mode"], "RECORDED AUTHENTIC EXECUTION REPLAY")
        self.assertEqual(self.data["provenance"]["ropeSha256"], exporter.ROPE_SHA256)
        self.assertEqual(self.data["provenance"]["emulatorRevision"], exporter.EMULATOR_REVISION)
        self.assertTrue(all(case["result"]["allOriginalChecksPass"] for case in self.cases.values()))

    def test_synthetic_scope_and_unimplemented_physics_are_explicit(self):
        labels = self.data["labels"]
        self.assertIn("SYNTHETIC", labels["scenario"])
        self.assertIn("NOT RUN", labels["scope"])
        self.assertIn("engine ignition", labels["scope"])
        self.assertIn("not the historical", labels["scenario"])
        self.assertIn("not simultaneous", labels["projection"])
        self.assertIn("sign lamps are not decoded", labels["dsky"])

    def test_compressed_and_raw_trace_hashes_match_source(self):
        for case in self.cases.values():
            source = case["sources"]
            content = (exporter.ROOT / source["tracePath"]).read_bytes()
            self.assertEqual(exporter.sha256(content), source["gzipSha256"])
            self.assertEqual(exporter.sha256(gzip.decompress(content)), source["rawSha256"])
            for path_key, hash_key in (("observerMapPath", "observerMapSha256"), ("configurationPath", "configurationSha256")):
                self.assertEqual(exporter.sha256((exporter.ROOT / source[path_key]).read_bytes()), source[hash_key])

    def test_integrity_checker_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace"
            path.write_bytes(b"original")
            expected = exporter.sha256(path.read_bytes())
            path.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                exporter.checked_bytes(path, expected)

    def test_frames_have_actual_ordered_cycles_and_recorded_endpoints(self):
        for identifier, case in self.cases.items():
            cycles = [frame["cycle"] for frame in case["frames"]]
            self.assertEqual(cycles[0], 0)
            self.assertEqual(cycles[-1], self.rows[identifier][-1]["cycle"])
            self.assertTrue(all(a < b for a, b in zip(cycles, cycles[1:])))
            self.assertLess(len(cycles), 2000)
            for frame in case["frames"]:
                self.assertEqual(frame["t"], frame["cycle"] * exporter.SECONDS_PER_CALL)
                self.row(identifier, frame["source"])

    def test_each_display_is_held_from_an_actual_channel_010_packet(self):
        for identifier, case in self.cases.items():
            for frame in case["frames"]:
                pointer = frame["observationSources"]["dsky"]
                if pointer is None:
                    self.assertTrue(all("?" in text for text in frame["dsky"].values()))
                    continue
                row = self.row(identifier, pointer)
                self.assertEqual((row["ev"], row["channel"]), ("output", 0o10))
                self.assertEqual(frame["dsky"], row["display"])
                self.assertLessEqual(pointer["cycle"], frame["cycle"])
            self.assertEqual(case["frames"][-1]["dsky"], self.rows[identifier][-1]["state"]["display"])

    def test_observed_clocks_are_decoded_only_from_native_snapshots(self):
        for identifier, case in self.cases.items():
            mapping = json.loads((exporter.ROOT / case["sources"]["observerMapPath"]).read_text())
            for frame in case["frames"]:
                pointer = frame["observationSources"]["clock"]
                if pointer is None:
                    self.assertIsNone(frame["observedClockSeconds"])
                    continue
                row = self.row(identifier, pointer)
                words = self.analyzer.words(row, mapping, "TIME2", 2)
                self.assertEqual(frame["observedClockSeconds"], self.analyzer.mathcheck.physical_dp(words, 28) / 100)
                self.assertLessEqual(pointer["cycle"], frame["cycle"])
            self.assertNotEqual(case["durationSeconds"], case["result"]["observedClockSeconds"])
            self.assertEqual(case["initialState"]["epochSeconds"], 120)

    def test_signed_root_outputs_keep_original_words_and_are_not_ignition_countdowns(self):
        for identifier, case in self.cases.items():
            mapping = json.loads((exporter.ROOT / case["sources"]["observerMapPath"]).read_text())
            for frame in case["frames"]:
                pointer = frame["observationSources"]["timeToGo"]
                if pointer is None:
                    self.assertIsNone(frame["signedTimeToGoSeconds"])
                    continue
                row = self.row(identifier, pointer)
                self.assertEqual(row["routine"], "ROOTSTOR_RESULT")
                words = self.analyzer.words(row, mapping, "MPAC", 2)
                self.assertEqual(pointer["rawWordsOctal"], [format(word, "05o") for word in words])
                expected = float(self.analyzer.mathcheck.dp_fraction(words)) * 2**17 / 100
                self.assertEqual(frame["signedTimeToGoSeconds"], expected)
                self.assertLessEqual(pointer["cycle"], frame["cycle"])
        self.assertLess(self.cases["nominal"]["frames"][-1]["signedTimeToGoSeconds"], 0)
        self.assertIn("not time remaining until ignition", self.data["labels"]["timeToGo"])

    def test_ignition_solution_available_only_after_original_completion(self):
        for identifier, case in self.cases.items():
            mapping = json.loads((exporter.ROOT / case["sources"]["observerMapPath"]).read_text())
            for frame in case["frames"]:
                pointer = frame["observationSources"]["ignitionTime"]
                if pointer is None:
                    self.assertIsNone(frame["ignitionTimeSeconds"])
                    self.assertIsNone(frame["ignitionLeadSeconds"])
                    continue
                row = self.row(identifier, pointer)
                self.assertEqual(row["routine"], "IGNALGRT")
                tig = self.analyzer.mathcheck.physical_dp(self.analyzer.words(row, mapping, "TIG", 2), 28)
                clock = self.analyzer.mathcheck.physical_dp(self.analyzer.words(row, mapping, "TIME2", 2), 28)
                self.assertEqual(frame["ignitionTimeSeconds"], tig / 100)
                self.assertEqual(frame["ignitionLeadSeconds"], (tig - clock) / 100)
                self.assertLessEqual(pointer["cycle"], frame["cycle"])
        self.assertEqual(self.cases["nominal"]["result"]["ignitionTimeSeconds"], 360.29)
        self.assertEqual(self.cases["nominal"]["result"]["ignitionLeadSeconds"], 139.03)

    def test_causal_scenarios_retain_real_difference_and_negative_failure(self):
        nominal, variant, missing = [self.cases[name] for name in ("nominal", "altitude-16km", "missing-site")]
        self.assertEqual(nominal["result"]["rootCount"], 9)
        self.assertEqual(variant["result"]["rootCount"], 9)
        self.assertEqual(missing["result"]["rootCount"], 3)  # Genuine provisional returns before failure.
        self.assertNotEqual(nominal["result"]["ignitionTimeSeconds"], variant["result"]["ignitionTimeSeconds"])
        self.assertIsNone(missing["result"]["ignitionTimeSeconds"])
        self.assertFalse(missing["result"]["reviewReached"])
        self.assertIn("01406", missing["result"]["finalAlarms"])
        for case in self.cases.values():
            self.assertIn("01520", case["result"]["finalAlarms"])

    def test_static_three_dimensional_inputs_match_original_p27_stores(self):
        for identifier, case in self.cases.items():
            initial = case["initialState"]
            row = self.row(identifier, initial["source"])
            self.assertEqual(row["symbol"], "UPSVFLAG")
            state = row["mission_state"]
            self.assertEqual(initial["positionM"], self.analyzer.mathcheck.decode_vector(state["RRECTLEM"], 27))
            self.assertEqual(initial["velocityMps"], self.analyzer.mathcheck.decode_vector(state["VRECTLEM"], 5, 100))
            self.assertAlmostEqual(initial["altitudeM"], math.sqrt(sum(v*v for v in initial["positionM"])) - initial["lunarRadiusM"])
            self.assertEqual(initial["targetLandingTimeSeconds"], 784.4)
            if identifier == "missing-site":
                self.assertIsNone(initial["landingSiteMoonFixedM"])
                self.assertIsNone(initial["landingSiteBasicRefAtTlandM"])
                self.assertIsNone(initial["siteSource"])
            else:
                site_row = self.row(identifier, initial["siteSource"])
                self.assertEqual(initial["landingSiteMoonFixedM"], self.analyzer.mathcheck.decode_vector(site_row["actual_words"], 27))
                # Synthetic planned site is approximately basic REF +X, with
                # finite quantization retained instead of snapped coordinates.
                ref = initial["landingSiteBasicRefAtTlandM"]
                self.assertLess(abs(ref[0] - initial["lunarRadiusM"]), 1)
                self.assertLess(abs(ref[1]), 1)
                self.assertLess(abs(ref[2]), 1)

    def test_no_trajectory_or_interpolated_motion_exists_in_frames(self):
        for case in self.cases.values():
            self.assertNotIn("trajectory", case)
            for frame in case["frames"]:
                self.assertNotIn("position", frame)
                self.assertNotIn("positionM", frame)
                self.assertNotIn("velocityMps", frame)
                self.assertNotIn("thrust", frame)

    def test_events_point_to_real_recorded_rows_and_source_routines(self):
        for identifier, case in self.cases.items():
            ids = [event["id"] for event in case["events"]]
            for name in ("p51", "alignment", "p63", "readiness", "stored-UPSVFLAG", "finish"):
                self.assertIn(name, ids)
            self.assertEqual(len(ids), len(set(ids)))
            for event in case["events"]:
                row = self.row(identifier, event["source"])
                self.assertEqual(event["t"], row["cycle"] * exporter.SECONDS_PER_CALL)
                if "routine" in event["source"]:
                    self.assertEqual(event["source"]["routine"], row["routine"])
            if identifier == "missing-site":
                self.assertIn("root-failure", ids)
                self.assertNotIn("ignition-solution", ids)
                self.assertNotIn("crew-review", ids)
            else:
                self.assertIn("ignition-solution", ids)
                self.assertIn("crew-review", ids)


if __name__ == "__main__":
    unittest.main()
