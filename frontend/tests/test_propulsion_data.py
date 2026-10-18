"""Trace-to-browser contract tests; no AGC or physics is reimplemented here."""

import gzip
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools/export_propulsion.py"
SPEC = importlib.util.spec_from_file_location("propulsion_browser_export", TOOL)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class PropulsionDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = exporter.build_propulsion()
        cls.cases = {case["id"]: case for case in cls.data["cases"]}
        cls.rows = {}
        # Retain only rows which the browser actually cites. All raw bytes and
        # native counters were already checked by the read-only exporter.
        for identifier, case in cls.cases.items():
            needed = set()
            for frame in case["frames"] + list(case["eventSnapshots"].values()):
                needed.add(frame["source"]["rawLine"])
                for field in ("spacecraft", "receiver"):
                    if frame[field] is not None:
                        needed.add(frame[field]["source"]["rawLine"])
                for source in frame["observationSources"].values():
                    if source is not None:
                        needed.add(source["rawLine"])
                for discrete in frame["crewDiscretes"].values():
                    needed.add(discrete["source"]["rawLine"])
                if frame["pipa"]["source"] is not None:
                    needed.add(frame["pipa"]["source"]["rawLine"])
            needed.update(item["source"]["rawLine"] for item in case["events"])
            needed.update(item["source"]["rawLine"] for item in case["keySequences"])
            cls.rows[identifier] = {line: json.loads(content) for line, content in enumerate(
                gzip.open(exporter.ROOT / case["sources"]["tracePath"], "rt"), 1) if line in needed}

    def row(self, identifier, source):
        row = self.rows[identifier][source["rawLine"]]
        self.assertEqual(row["cycle"], source["cycle"])
        return row

    def test_generated_export_matches_fresh_verified_read_only_derivation(self):
        self.assertEqual(exporter.DEFAULT_OUTPUT.read_bytes(), exporter.encoded(self.data))
        self.assertEqual(exporter.encoded(self.data), exporter.encoded(json.loads(exporter.encoded(self.data))))

    def test_four_causal_cases_and_immutable_original_software_are_identified(self):
        self.assertEqual(list(self.cases), ["connected", "sink", "no-feedback", "repeat"])
        self.assertEqual(self.data["schemaVersion"], 1)
        self.assertEqual(self.data["mode"], "VERIFIED RECORDED EXECUTION")
        self.assertEqual(self.data["provenance"]["sealedFilesChecked"], 468)
        self.assertEqual(self.data["provenance"]["ropeSha256"], exporter.ROPE_SHA256)
        self.assertTrue(all(case["outcome"]["allOriginalChecksPass"] for case in self.cases.values()))
        self.assertTrue(all(self.data["comparisons"].values()))

    def test_full_release_seal_and_trace_fingerprints_still_match(self):
        self.assertEqual(exporter.sha256((exporter.EVIDENCE / "checksums.json").read_bytes()), exporter.SEAL_SHA256)
        for case in self.cases.values():
            source = case["sources"]
            compressed = (exporter.ROOT / source["tracePath"]).read_bytes()
            raw = gzip.decompress(compressed)
            self.assertEqual(exporter.sha256(compressed), source["gzipSha256"])
            self.assertEqual(exporter.sha256(raw), source["rawSha256"])
            self.assertEqual(len(raw), source["rawBytes"])

    def test_integrity_guard_rejects_changed_source_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace"
            path.write_bytes(b"actual source")
            fingerprint = exporter.sha256(path.read_bytes())
            path.write_bytes(b"modified source")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                exporter.checked_bytes(path, fingerprint)

    def test_cpu_replay_is_chronological_and_keeps_both_native_endpoints(self):
        for identifier, case in self.cases.items():
            frames = case["frames"]
            self.assertEqual(frames[0]["cycle"], 0)
            self.assertEqual(frames[-1]["cycle"], case["endCycle"])
            self.assertLess(len(frames), 2500)
            self.assertTrue(all(a["cycle"] < b["cycle"] for a, b in zip(frames, frames[1:])))
            self.assertEqual(case["durationSeconds"], case["endCycle"] * exporter.SECONDS_PER_CALL)
            for frame in frames:
                self.assertEqual(frame["t"], frame["cycle"] * exporter.SECONDS_PER_CALL)
                self.row(identifier, frame["source"])

    def test_every_dsky_display_is_an_actual_held_relay_observation(self):
        for identifier, case in self.cases.items():
            for frame in case["frames"]:
                source = frame["observationSources"]["dsky"]
                if source is None:
                    self.assertTrue(all("?" in field for field in frame["dsky"].values()))
                else:
                    row = self.row(identifier, source)
                    self.assertEqual((row["ev"], row["channel"]), ("output", 0o10))
                    self.assertEqual(frame["dsky"], row["display"])
                    self.assertLessEqual(source["cycle"], frame["cycle"])
            self.assertIn("sign lamps", self.data["dskyScope"])
            self.assertEqual(case["frames"][-1]["dsky"], self.row(identifier, case["frames"][-1]["source"])["state"]["display"])

    def test_physical_values_are_copied_without_extrapolation_or_frame_conversion(self):
        for identifier, case in self.cases.items():
            before_initialization = True
            for frame in case["frames"]:
                state = frame["spacecraft"]
                if state is None:
                    self.assertTrue(before_initialization)
                    continue
                before_initialization = False
                row = self.row(identifier, state["source"])
                telemetry = row["telemetry"]
                self.assertIn(row["ev"], ("plant", "plant_initialization"))
                self.assertEqual(state["positionM"], telemetry["position_ref_m"])
                self.assertEqual(state["velocityMps"], telemetry["velocity_ref_m_s"])
                self.assertEqual(state["quaternion"], telemetry["quaternion_body_to_ref"])
                self.assertEqual(state["physicalTimeSeconds"], telemetry["time_s"])
                self.assertEqual(state["fuelKg"], telemetry["fuel_kg"])
                self.assertEqual(state["deliveredThrustN"], telemetry["delivered_thrust_n"])
                self.assertLessEqual(state["source"]["cycle"], frame["cycle"])
            self.assertEqual(case["outcome"]["finalSpacecraft"], case["frames"][-1]["spacecraft"])

    def test_physical_clock_units_and_fixed_attitude_are_explicit(self):
        for case in self.cases.values():
            geometry = case["initialGeometry"]
            self.assertEqual(geometry["lunarRadiusM"], 1738090)
            self.assertEqual(geometry["initializedEpochSeconds"], 120)
            physical = [frame["spacecraft"] for frame in case["frames"] if frame["spacecraft"] is not None]
            first = physical[0]
            self.assertEqual(first["physicalTimeSeconds"], 119.99000000000001)
            self.assertEqual(first["elapsedPhysicalSeconds"], 0)
            self.assertNotEqual(first["physicalTimeSeconds"], first["source"]["cycle"] * exporter.SECONDS_PER_CALL)
            for state in physical:
                self.assertEqual(state["elapsedPhysicalSeconds"], state["physicalTimeSeconds"] - first["physicalTimeSeconds"])
                self.assertEqual(state["quaternion"], first["quaternion"])
                self.assertAlmostEqual(math.sqrt(sum(v*v for v in state["quaternion"])), 1)
            self.assertIn("fixed", geometry["quaternionFrame"])
        self.assertEqual(self.data["units"]["velocity"], "m/s")
        self.assertEqual(self.data["units"]["angularVelocity"], "rad/s")
        self.assertIn("not historical GET", self.data["sampling"]["cpuClock"])

    def test_physical_samples_keep_original_first_final_and_approx_quarter_second_spacing(self):
        for case in self.cases.values():
            samples = {}
            for frame in case["frames"]:
                if frame["spacecraft"] is not None:
                    sample = frame["spacecraft"]
                    samples[sample["source"]["rawLine"]] = sample
            values = list(samples.values())
            self.assertGreater(len(values), 350)
            self.assertTrue(all(0 < b["physicalTimeSeconds"] - a["physicalTimeSeconds"] < .26
                                for a, b in zip(values, values[1:])))

    def test_actual_key_transactions_and_cockpit_discretes_are_not_fake_live_controls(self):
        for identifier, case in self.cases.items():
            texts = [item["text"] for item in case["keySequences"]]
            self.assertEqual(len(texts), 144)
            self.assertIn("V37E51E", texts)
            self.assertIn("V48E", texts)
            self.assertIn("+33069E", texts)
            self.assertIn("V37E63E", texts)
            self.assertIn("V37E00E", texts)
            for item in case["keySequences"]:
                row = self.row(identifier, item["source"])
                self.assertEqual(row["ev"], "key_sequence")
                self.assertEqual(row["text"], item["text"])
            setting = next(event for event in case["events"] if event["title"] == "Recorded cockpit discretes set")
            frame = next(frame for frame in case["frames"] if frame["cycle"] == setting["cycle"])
            self.assertEqual(frame["crewDiscretes"]["030"]["value"], 15595)
            self.assertEqual(frame["crewDiscretes"]["031"]["value"], 20479)
            self.assertEqual(frame["crewDiscretes"]["033"]["value"], 32735)
            self.assertTrue(frame["receiver"]["armed"])
            self.assertTrue(frame["receiver"]["autothrottle"])
            self.assertFalse(frame["receiver"]["requestedEngineOn"])

    def test_crew_permission_ignition_flatout_software_stop_and_disarm_remain_separate(self):
        for identifier, case in self.cases.items():
            by_title = {event["title"]: event for event in case["events"]}
            names = ["V99 N62 · crew enable request", "Original ENGINE ON output", "Original FLATOUT", "P00 · software shutdown", "Crew disarm", "Retained experiment ends"]
            cycles = [by_title[name]["cycle"] for name in names]
            self.assertTrue(all(a < b for a, b in zip(cycles[:5], cycles[1:5])))
            # Crew-disarm observation and finish are separate retained rows at
            # the same CPU cycle, rather than a fabricated extra time step.
            self.assertLessEqual(cycles[4], cycles[5])
            self.assertEqual(cycles[1], 25169081)
            for event in case["events"]:
                self.row(identifier, event["source"])
            self.assertFalse(case["frames"][-1]["receiver"]["armed"])
            self.assertFalse(case["frames"][-1]["spacecraft"]["engineEnabled"])
            self.assertEqual(case["frames"][-1]["spacecraft"]["deliveredThrustN"], 0)

    def test_causal_disconnections_have_actual_distinct_physical_and_sensor_outcomes(self):
        connected, sink, disconnected, repeat = [self.cases[name] for name in self.cases]
        self.assertTrue(connected["physicalEngineConnected"])
        self.assertTrue(connected["sensorFeedbackConnected"])
        self.assertFalse(sink["physicalEngineConnected"])
        self.assertFalse(sink["sensorFeedbackConnected"])
        self.assertTrue(disconnected["physicalEngineConnected"])
        self.assertFalse(disconnected["sensorFeedbackConnected"])
        self.assertEqual(sink["outcome"]["sensor"]["generated_counts"], [0, 0, 0])
        self.assertEqual(disconnected["outcome"]["sensor"]["delivered_counts"], [0, 0, 0])
        self.assertEqual(disconnected["outcome"]["sensor"]["generated_counts"], [3296, 0, 0])
        self.assertEqual(connected["outcome"]["sensor"]["delivered_counts"], [3301, 0, 0])
        self.assertEqual(sink["outcome"]["finalSpacecraft"]["fuelKg"], 8196)
        self.assertLess(connected["outcome"]["finalSpacecraft"]["fuelKg"], 8196)
        self.assertNotEqual(connected["outcome"]["finalSpacecraft"]["positionM"], disconnected["outcome"]["finalSpacecraft"]["positionM"])
        self.assertEqual(connected["sources"]["rawSha256"], repeat["sources"]["rawSha256"])
        self.assertEqual(connected["frames"], repeat["frames"])

    def test_original_navigation_stays_distinct_from_physical_plant_state(self):
        analysis = json.loads((exporter.EVIDENCE / "phase12-validation/analysis.json").read_bytes())
        for identifier, case in self.cases.items():
            samples = case["navigationSamples"]
            self.assertEqual(len(samples), 32)
            for native, sample in zip(analysis["runs"][identifier]["navigation_samples"], samples):
                self.assertEqual(self.row(identifier, sample["source"])["routine"], "MUNRETRN")
                self.assertEqual(sample["positionM"], native["R_computed_stable_m"])
                self.assertEqual(sample["velocityMps"], native["V_computed_stable_m_s"])
                self.assertEqual(sample["pipaConsumedCounts"], native["consumed_counts"])
                self.assertEqual(sample["timeSeconds"], native["PIPTIME_cs"] / 100)
                self.assertIn("IMU stable member", sample["coordinateFrame"])
                self.assertEqual(sample["periodSeconds"], 2)
        connected = {event["title"]: event for event in self.cases["connected"]["events"]}
        names = ("Physical acceleration produces PIPA counts", "PIPA counter packet delivered", "Original navigation consumes thrust feedback")
        cycles = [connected[name]["cycle"] for name in names]
        self.assertTrue(all(a <= b for a, b in zip(cycles, cycles[1:])))
        source_lines = [connected[name]["source"]["rawLine"] for name in names]
        self.assertTrue(all(a < b for a, b in zip(source_lines, source_lines[1:])))
        for case in (self.cases["sink"], self.cases["no-feedback"]):
            self.assertNotIn("Original navigation consumes thrust feedback", [event["title"] for event in case["events"]])

    def test_no_historical_flight_or_landing_claims_are_introduced(self):
        self.assertIn("No achieved burn attitude", self.data["scope"])
        self.assertIn("not Apollo 11's historical", self.data["limitations"][0])
        for case in self.cases.values():
            self.assertIn("SYNTHETIC", case["classification"])
            self.assertIn("not a historical Apollo 11", case["classification"])
            self.assertIn("No lunar landing", case["events"][-1]["description"])

    def test_every_event_has_an_exact_raw_row_snapshot_with_no_later_held_source(self):
        for identifier, case in self.cases.items():
            self.assertEqual(set(case["eventSnapshots"]), {event["id"] for event in case["events"]})
            for event in case["events"]:
                frame = case["eventSnapshots"][event["id"]]
                self.assertEqual(frame["source"], event["source"])
                self.assertEqual(frame["cycle"], event["cycle"])
                self.assertEqual(frame["t"], event["t"])
                self.row(identifier, frame["source"])
                sources = list(frame["observationSources"].values())
                sources.extend(value["source"] for value in frame["crewDiscretes"].values())
                sources.extend(frame[name]["source"] for name in ("spacecraft", "receiver") if frame[name] is not None)
                sources.append(frame["pipa"]["source"])
                for source in filter(None, sources):
                    self.assertLessEqual(source["cycle"], event["cycle"])
                    self.assertLessEqual(source["rawLine"], event["source"]["rawLine"])
                    self.row(identifier, source)

    def test_same_cycle_reviews_precede_initial_physics_and_each_crew_packet(self):
        for case in self.cases.values():
            by_title = {event["title"]: event for event in case["events"]}
            review = by_title["P63 · pre-ignition review"]
            initialized = by_title["Physical state becomes available"]
            self.assertEqual(review["cycle"], initialized["cycle"])
            self.assertIsNone(case["eventSnapshots"][review["id"]]["spacecraft"])
            self.assertIsNotNone(case["eventSnapshots"][initialized["id"]]["spacecraft"])
            names = ["Crew switch review", "Recorded hardware input · channel 030", "Recorded hardware input · channel 031", "Recorded hardware input · channel 033"]
            # Channel 030 is used again for later crew DISARM; retain the
            # first arming packet rather than conflating equal channel labels.
            frames = [case["eventSnapshots"][next(event["id"] for event in case["events"] if event["title"] == name)] for name in names]
            self.assertTrue(all(frame["cycle"] == frames[0]["cycle"] for frame in frames))
            self.assertTrue(all(a["source"]["rawLine"] < b["source"]["rawLine"] for a, b in zip(frames, frames[1:])))
            self.assertEqual(frames[0]["crewDiscretes"]["030"]["value"], 15615)
            self.assertEqual(frames[1]["crewDiscretes"]["030"]["value"], 15595)
            self.assertEqual(frames[1]["crewDiscretes"]["031"]["value"], 28671)
            self.assertEqual(frames[2]["crewDiscretes"]["031"]["value"], 20479)
            self.assertEqual(frames[2]["crewDiscretes"]["033"]["value"], 32767)
            self.assertEqual(frames[3]["crewDiscretes"]["033"]["value"], 32735)


if __name__ == "__main__":
    unittest.main()
