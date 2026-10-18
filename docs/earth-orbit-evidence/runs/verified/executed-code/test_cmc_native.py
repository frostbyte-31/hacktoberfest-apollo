"""Original CMC packet/CPU integration; no expectations synthesized in flight RAM."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import cmc_native as cmc


class DecoderTests(unittest.TestCase):
    def test_unobserved_registers_are_unavailable(self):
        decoder = cmc.DskyDecoder()
        value = decoder.snapshot()
        self.assertEqual(value["PROG"], "??")
        self.assertEqual(value["R1"], "?????")
        self.assertIsNone(value["signs"]["R1"])
        self.assertIsNone(value["lamps"]["operatorError"])
        self.assertIsNone(decoder.last_cycle)

    def test_relay_word_controls_only_its_actual_digit_pair(self):
        decoder = cmc.DskyDecoder()
        decoder.apply(0o10, 11 << 11, 100)
        self.assertEqual(decoder.snapshot()["PROG"], "  ")
        self.assertEqual(decoder.snapshot()["VERB"], "??")
        decoder.apply(0o10, (10 << 11) | (30 << 5) | 25, 101)
        self.assertEqual(decoder.snapshot()["VERB"], "52")
        self.assertEqual(decoder.last_cycle, 101)
        self.assertEqual(decoder.rows["10"]["value"], (10 << 11) | (30 << 5) | 25)

    def test_discovery_has_no_build_or_computer_side_effect(self):
        with patch.object(cmc.subprocess, "run", side_effect=AssertionError("Discovery must not spawn builds")):
            available = cmc.availability()
        self.assertEqual(available["software"], "Comanche055")
        self.assertEqual(len(available["supportedKeys"]), 19)
        self.assertEqual(available["ropeSha256"], cmc.ROPE_SHA256)
        self.assertIsNone(available["engineSha256"])

    def test_missing_input_is_unavailable_not_a_fake_computer(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cmc, "EVIDENCE", Path(directory)):
            value = cmc.availability()
        self.assertFalse(value["available"])
        self.assertIn("missing", value["unavailableReason"])


@unittest.skipUnless(cmc.availability()["available"], "Pinned CMC inputs and a C compiler are required")
class NativeCmcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.assets = cmc.prepare_cmc_assets(Path(cls.directory.name) / "assets")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.process = cmc.CmcProcess(self.assets)
        self.initial = self.process.boot()

    def tearDown(self):
        self.process.close()

    def keys(self, values):
        result = None
        for key in values:
            result = self.process.key(key)
            ack = result["ackpacket"]
            self.assertGreater(ack["accepted"], 0)
            self.assertGreater(ack["consumedAtCycle"], ack["queuedAtCycle"])
            self.assertEqual(ack["afterCycle"], result["computer"]["cycle"])
            for packet in ack["packets"]:
                self.assertGreater(packet["consumedAtCycle"], packet["queuedAtCycle"])
        return self.process.advance(2)

    def test_original_lights_test_is_real_channel010_output(self):
        snapshot = self.keys(["VERB", "3", "5", "ENTR"])
        self.assertEqual([snapshot["dsky"][name] for name in ("PROG", "VERB", "NOUN")], ["88"] * 3)
        self.assertEqual([snapshot["dsky"][name] for name in ("R1", "R2", "R3")], ["88888"] * 3)
        self.assertEqual(snapshot["dskySource"]["channel"], 0o10)
        self.assertGreater(snapshot["dskySource"]["cycle"], self.initial["cycle"])
        self.assertFalse(snapshot["historicalCheckpointLoaded"])
        self.assertIsNone(snapshot["flightState"])
        self.assertFalse(snapshot["provenance"]["hostFlightMemoryWrites"])

    def test_withholding_keys_does_not_manufacture_a_lights_test(self):
        idle = self.process.advance(10)
        self.assertNotEqual(idle["dsky"]["PROG"], "88")
        self.assertNotEqual(idle["dsky"]["R1"], "88888")
        self.assertIsNone(idle["flightState"])

    def test_original_software_rejects_invalid_verb_and_rset_clears_operator_error(self):
        invalid = self.keys(["VERB", "0", "0", "ENTR"])
        self.assertTrue(invalid["dsky"]["lamps"]["operatorError"])
        self.process.key("RSET")
        self.assertFalse(self.process.advance(2)["dsky"]["lamps"]["operatorError"])

    def test_original_clock_advances_and_p00_selection_works(self):
        snapshot = self.keys(["VERB", "3", "7", "ENTR", "0", "0", "ENTR"])
        self.assertEqual(snapshot["dsky"]["PROG"], "00")
        first = self.keys(["VERB", "1", "6", "NOUN", "3", "6", "ENTR"])
        second = self.process.advance(3)
        self.assertEqual(first["dsky"]["VERB"], "16")
        self.assertEqual(first["dsky"]["NOUN"], "36")
        self.assertNotEqual(first["dsky"]["R3"], second["dsky"]["R3"])
        self.assertGreater(second["cycle"], first["cycle"])

    def test_original_p52_blocks_missing_imu_and_can_recover(self):
        self.keys(["VERB", "3", "7", "ENTR", "0", "0", "ENTR"])
        self.keys(["VERB", "3", "7", "ENTR", "5", "2", "ENTR"])
        alarm = self.keys(["VERB", "0", "5", "NOUN", "0", "9", "ENTR"])
        self.assertIn("00210", [alarm["dsky"][name] for name in ("R1", "R2", "R3")])
        self.assertEqual(alarm["dsky"]["VERB"], "05")
        self.assertEqual(alarm["dsky"]["NOUN"], "09")
        recovered = self.keys(["RSET", "VERB", "3", "7", "ENTR", "0", "0", "ENTR"])
        self.assertEqual(recovered["dsky"]["PROG"], "00")
        self.assertEqual(recovered["dsky"]["VERB"], "  ")
        self.assertIsNone(recovered["flightState"])

    def test_cold_start_phase_alarm_is_visible_and_real_rset_clears_it(self):
        alarms = self.keys(["VERB", "0", "5", "NOUN", "0", "9", "ENTR"])
        self.assertEqual(alarms["dsky"]["R1"], "01107")
        self.process.key("RSET")
        cleared = self.keys(["VERB", "0", "5", "NOUN", "0", "9", "ENTR"])
        self.assertEqual([cleared["dsky"][name] for name in ("R1", "R2", "R3")], ["00000"] * 3)

    def test_pro_is_separate_active_low_discrete_and_release(self):
        result = self.process.key("PRO")
        ack = result["ackpacket"]
        self.assertEqual(ack["channel"], 0o32)
        self.assertEqual([p["channel"] for p in ack["packets"]], [0o432, 0o32, 0o32])
        self.assertEqual([p["value"] for p in ack["packets"]], [0o20000, 0, 0o20000])
        self.assertEqual(ack["packets"][0]["observedRingPacket"] >> 31, 1)
        self.assertGreater(ack["consumedAtCycle"], ack["queuedAtCycle"])

    def test_invalid_key_sequences_and_time_do_not_run(self):
        before = self.process.advance(0)["cycle"]
        for value in ("V35E", "AUTO", "UP", "V", "", None):
            with self.assertRaises(ValueError):
                self.process.key(value)
        for value in (-1, 31, float("inf"), float("nan"), True, "1"):
            with self.assertRaises(ValueError):
                self.process.advance(value)
        self.assertEqual(self.process.advance(0)["cycle"], before)

    def test_worker_timeout_terminates_the_owned_native_process(self):
        with patch.object(cmc.select, "select", return_value=([], [], [])):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.process.advance(0)
        self.assertIsNotNone(self.process.proc.poll())

    def test_fresh_workers_start_with_identical_original_state(self):
        other = cmc.CmcProcess(self.assets)
        try:
            initial = other.boot()
            self.assertEqual(initial, self.initial)
            for key in ("VERB", "3", "5", "ENTR"):
                self.assertEqual(self.process.key(key), other.key(key))
            self.assertEqual(self.process.advance(2), other.advance(2))
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
