#!/usr/bin/env python3
"""Derive the educational replay exclusively from sealed Phase 10 evidence.

This is a read-only evidence adapter, not an AGC, physics engine or controller.
The browser receives sampled-and-held observations with source line pointers.
No native CPU runs and no spacecraft motion is calculated by this exporter.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/phase10-evidence"
RUNS = EVIDENCE / "runs/final-validation"
DEFAULT_OUTPUT = ROOT / "frontend/dist/data/guidance.json"
SEAL_SHA256 = "10b77abb67914dd6e0f4a13afb967b67f8e96b161217b63f9b0706f9a78fa7cc"
ROPE_SHA256 = "1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e"
EMULATOR_REVISION = "f577e3fd917866c59334e6cdd32504f09df76f60"
SECONDS_PER_CALL = 12 / 1024000
CASES = (
    ("nominal", "final", "Synthetic 15 km orbit", "run"),
    ("altitude-16km", "altitude-16km", "Synthetic 16 km orbit", "altitude_variant"),
    ("missing-site", "missing-site", "Missing landing-site initialization", "missing_site_control"),
)
DECODER_SHA256 = "2d290eb0095af194ddf52560f0d87a97ccb575a95c9e587d390ff8c42ef7a86e"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_bytes(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if sha256(data) != expected:
        raise ValueError(f"Evidence integrity mismatch: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return data


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def verified_inventory() -> dict:
    """Check the Phase 10 seal itself and every file within its immutable scope.

    The earlier whole-repository freeze also included application files. This
    adapter does not reinterpret or modify that historical freeze; Phase 10.5
    separately preserves all historical evidence while changing the frontend.
    """
    seal = json.loads(checked_bytes(EVIDENCE / "checksums.json", SEAL_SHA256))
    for relative, expected in seal["sha256"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Evidence path escapes repository")
        checked_bytes(path, expected)
    checked_bytes(ROOT / "docs/phase1-evidence/artifacts/MAIN.agc.bin", ROPE_SHA256)
    checked_bytes(ROOT / "docs/phase1-evidence/m2_dsky_client.py", DECODER_SHA256)
    return seal


def source(row: dict, line: int, **extra) -> dict:
    return {"rawLine": line, "cycle": row["cycle"], **extra}


def export_case(identifier: str, retained_name: str, title: str, analysis_key: str,
                inventory: dict, retained_analysis: dict, analyzer) -> dict:
    directory = RUNS / retained_name
    relative = directory.relative_to(ROOT).as_posix()
    compressed = checked_bytes(directory / "trace.jsonl.gz", inventory["sha256"][relative + "/trace.jsonl.gz"])
    raw = gzip.decompress(compressed)
    fingerprint = json.loads((directory / "trace-sha256.json").read_text())
    if sha256(raw) != fingerprint["sha256"] or len(raw) != fingerprint["bytes"]:
        raise ValueError("Decompressed trace fingerprint mismatch")
    actual = analyzer.analyze_run(directory, identifier == "missing-site")
    expected = retained_analysis[analysis_key]
    # Native words, source checkpoints, exact Fraction-derived root data and
    # every original assertion must agree. Independent sqrt/acos diagnostics
    # are required to pass their original bounds, rather than demanding a
    # particular host libm's final floating-point bit.
    native_fields = ("classification", "checks", "all_pass", "raw_sha256", "raw_bytes",
                     "checkpoint_counts", "polynomial_entries", "returned_roots",
                     "final_state", "ignition_solution")
    if not actual["all_pass"] or any(actual[key] != expected[key] for key in native_fields):
        raise ValueError("Original Phase 10 checks or retained analysis disagree")
    run = analyzer.p9.load_run(directory)
    rows, mapping = run["rows"], run["mapping"]
    config = json.loads((directory / "configuration.json").read_text())
    execution = json.loads((directory / "execution.json").read_text())
    setup = json.loads((directory / "setup-used.json").read_text())
    if setup["sourceRevision"] != EMULATOR_REVISION or setup["ropeSHA256"] != ROPE_SHA256:
        raise ValueError("Unexpected original software revision")
    # Every checkpoint name must identify the actual observed bank/address.
    for row in rows:
        if row["ev"] == "checkpoint" and [row["pre_bank"], row["pre_z"]] != mapping["checkpoints"][row["routine"]]:
            raise ValueError("Checkpoint address disagrees with source mapping")
    for relative_path, expected_sha in execution["dependency_sha256"].items():
        checked_bytes(ROOT / relative_path, expected_sha)
    checked_bytes(EVIDENCE / "run_mission.py", execution["driver_sha256"])
    checked_bytes(directory / "p9_watch.h", execution["generated_observer_sha256"])
    config_bytes = (directory / "configuration.json").read_bytes()
    if sha256(config_bytes) != execution["config_sha256"]:
        raise ValueError("Execution/configuration mismatch")

    diagnostic = analyzer.mathcheck
    decoder = module("guidance_dsky_" + identifier.replace("-", "_"), ROOT / "docs/phase1-evidence/m2_dsky_client.py")
    geometry = config["synthetic_geometry"]
    state_line, state_row = next((i, r) for i, r in enumerate(rows, 1)
                                if r["ev"] == "mission_block_stored" and r["symbol"] == "UPSVFLAG")
    state = state_row["mission_state"]
    position = diagnostic.decode_vector(state["RRECTLEM"], 27)
    velocity = diagnostic.decode_vector(state["VRECTLEM"], 5, 100)
    site_record = next(((i, r) for i, r in enumerate(rows, 1)
                        if r["ev"] == "mission_block_stored" and r["symbol"] == "RLS"), None)
    site = diagnostic.decode_vector(site_record[1]["actual_words"], 27) if site_record else None
    # Original MMATRIX convention: Moon-fixed = M * basic REF. The inverse is
    # M transpose for the documented nominal, zero-libration rotation. This
    # independently calculated static site illustration is never AGC telemetry.
    matrix = geometry["independent_physical_moon_matrix_at_TLAND"]
    site_ref = [sum(matrix[j][i] * site[j] for j in range(3)) for i in range(3)] if site else None
    initial = {
        "classification": "SYNTHETIC initialized state; not historical flight telemetry",
        "positionM": position, "velocityMps": velocity,
        "landingSiteMoonFixedM": site, "landingSiteBasicRefAtTlandM": site_ref,
        "epochSeconds": diagnostic.physical_dp(state["TETLEM"], 28) / 100,
        "targetLandingTimeSeconds": geometry["TLAND_cs"] / 100,
        "lunarRadiusM": geometry["lunar_reference_radius_m"],
        "altitudeM": math.sqrt(sum(x*x for x in position)) - geometry["lunar_reference_radius_m"],
        "speedMps": math.sqrt(sum(x*x for x in velocity)),
        "projection": "Static basic REF X–Z: spacecraft at navigation epoch 120 s; planned site at nominal TLAND 784.4 s",
        "positionFrame": "Moon-centered basic REF inertial, metres",
        "velocityFrame": "Moon-centered basic REF inertial, metres/second",
        "siteFrame": "Moon-fixed input independently transformed to basic REF at TLAND; not a propagated site",
        "source": source(state_row, state_line, symbols=["RRECTLEM", "VRECTLEM", "TETLEM"]),
        "siteSource": source(site_record[1], site_record[0], symbol="RLS") if site_record else None,
        "transformSource": {"configurationPath": relative + "/configuration.json",
                            "field": "synthetic_geometry.independent_physical_moon_matrix_at_TLAND"},
    }
    frames, events = [], []
    observed = {
        "dsky": decoder.snapshot(), "stage": "Computer startup",
        "observedClockSeconds": None, "signedTimeToGoSeconds": None,
        "ignitionTimeSeconds": None, "ignitionLeadSeconds": None,
        "rootCount": 0, "alarms": [],
        "observationSources": {"dsky": None, "clock": None, "timeToGo": None,
                               "ignitionTime": None, "ignitionLead": None, "alarms": None},
    }
    root_results = {r["cycle"]: r for r in actual["returned_roots"]}
    ignition_results = {r["cycle"]: r for r in actual["ignition_solution"]}
    review_seen = False
    def event(row, line, event_id, event_title, description, stage=None):
        if stage:
            observed["stage"] = stage
        events.append({"id": event_id, "title": event_title, "description": description,
                       "cycle": row["cycle"], "t": row["cycle"] * SECONDS_PER_CALL,
                       "source": source(row, line, **({"routine": row["routine"]} if "routine" in row else {}))})

    for line, row in enumerate(rows, 1):
        ev = row["ev"]
        previous = copy.deepcopy(observed)
        event_count = len(events)
        pointer = source(row, line)
        if ev == "output" and row["channel"] == 0o10:
            decoder.apply010(row["value"])
            display = decoder.snapshot()
            if display != row["display"]:
                raise ValueError("Reconstructed DSKY differs from actual retained packet")
            if display != observed["dsky"]:
                observed["dsky"] = display
                observed["observationSources"]["dsky"] = {**pointer, "channelOctal": "010", "valueOctal": format(row["value"], "05o")}
            if not review_seen and display["PROG"] == "63" and display["VERB"] == "06" and display["NOUN"] == "61" and observed["ignitionTimeSeconds"] is not None:
                review_seen = True
                event(row, line, "crew-review", "V06 N61 · crew review", "Original display requests pre-ignition review. No crew continuation or ignition was executed.", "Pre-ignition crew review")
        if "snapshot_words" in row:
            observed["observedClockSeconds"] = diagnostic.physical_dp(analyzer.words(row, mapping, "TIME2", 2), 28) / 100
            observed["observationSources"]["clock"] = {**pointer, "symbol": "TIME2/TIME1", "scale": "DP B28 centiseconds"}
            fail_words = analyzer.words(row, mapping, "FAILREG", 3)
            alarms = [format(value, "05o") for value in fail_words if value not in (0, 0o77777)]
            if alarms != observed["alarms"]:
                additions = [value for value in alarms if value not in observed["alarms"]]
                observed["alarms"] = alarms
                observed["observationSources"]["alarms"] = {**pointer, "symbol": "FAILREG"}
                for alarm in additions:
                    alarm_description = "Original software recorded this alarm at this retained observation."
                    if alarm == "01520":
                        alarm_description = "Preserved legacy startup alarm; the initial P00 request was rejected."
                    elif alarm == "01107":
                        alarm_description = "Original software recorded this alarm during startup, before mission initialization; it is distinct from later guidance outcomes."
                    elif alarm == "01406" and identifier == "missing-site":
                        alarm_description = "Original numerical guidance recorded 01406 in this intentional missing-landing-site negative control."
                    event(row, line, "alarm-" + alarm, "Program alarm " + alarm,
                          alarm_description)
        if ev == "startup_complete":
            event(row, line, "startup", "Verified startup complete", "The unchanged Phase 5 startup is complete; the instrument fixture is stationary.")
        elif ev == "alignment_result":
            event(row, line, "alignment", "P51 alignment completes", "Original P51 populated REFSMMAT and set REFSMFLG from synthetic star sightings. Physical calibration is not established.", "Alignment complete")
        elif ev == "mission_initialization_start":
            event(row, line, "mission-inputs", "P27 mission-state initialization", "Documented state and target inputs are entered through authentic V71 DSKY transactions.", "Loading mission inputs")
        elif ev == "mission_block_stored":
            event(row, line, "stored-" + row["symbol"], row["symbol"] + " accepted", "Original P27 stored the documented input block; this is initialized mission data, not computed guidance.")
        elif ev == "mission_initialization_complete":
            event(row, line, "inputs-complete", "Mission inputs complete", "Navigation inputs and targeting padloads are available to the original numerical guidance.")
        elif ev == "checkpoint":
            routine = row["routine"]
            if routine == "P51":
                event(row, line, "p51", "P51 · star-sighting alignment", "Original alignment instructions execute using clearly synthetic instrument sightings.", "P51 alignment")
            elif routine == "P63LM":
                event(row, line, "p63", "P63 selected", "Normal V37E63E input selected original Luminary P63.", "P63 pre-ignition guidance")
            elif routine == "P63_AFTER_R02":
                event(row, line, "readiness", "Reference readiness check passes", "Original R02BOTH returned to P63 with the reference-matrix flag set.")
            elif routine == "ROOTPSRS":
                count = sum(e["id"].startswith("root-entry-") for e in events) + 1
                event(row, line, "root-entry-" + str(count), "ROOTPSRS · calculation " + str(count), "Original software is solving its time-to-go polynomial; an entry is not yet a successful result.", "Solving guidance equations")
            elif routine == "ROOTSTOR_RESULT":
                result = root_results[row["cycle"]]
                if not result["actual_normal_return_and_original_TTF_store"]:
                    raise ValueError("Root observation lacks verified subsequent original TTF store")
                observed["rootCount"] += 1
                observed["signedTimeToGoSeconds"] = result["diagnostics"]["signed_time_to_go_seconds"]
                observed["observationSources"]["timeToGo"] = {**pointer, "routine": routine, "symbol": "MPAC", "rawWordsOctal": [format(w, "05o") for w in analyzer.words(row, mapping, "MPAC", 2)], "scale": "DP fraction * 2^17 / 100 seconds"}
                event(row, line, "root-return-" + str(observed["rootCount"]), "Root solution observed", "Original result is available in MPAC; its normal return and TTF store are separately verified by the subsequent QUADGUID continuation.")
            elif routine == "IGNALGRT":
                result = ignition_results[row["cycle"]]
                observed["ignitionTimeSeconds"] = result["TIG_cs"] / 100
                observed["ignitionLeadSeconds"] = (result["TIG_cs"] - result["TIME2_cs"]) / 100
                observed["observationSources"]["ignitionTime"] = {**pointer, "routine": routine, "symbol": "TIG", "rawWordsOctal": [format(w, "05o") for w in analyzer.words(row, mapping, "TIG", 2)], "scale": "DP B28 centiseconds"}
                observed["observationSources"]["ignitionLead"] = {**pointer, "calculation": "(TIG - TIME2/TIME1) at this same original checkpoint, seconds"}
                event(row, line, "ignition-solution", "Ignition-time calculation completes", "Original IGNALGRT records an absolute synthetic mission time. Engine ignition and thrust response were not run.", "Ignition solution calculated")
            elif routine == "1406POO":
                event(row, line, "root-failure", "Time-to-go calculation fails", "Original ROOTPSRS reached its authentic 01406 alarm path with the landing site absent.", "Guidance stopped · missing input")
        elif ev == "finish":
            event(row, line, "finish", "Recorded experiment ends", "The bounded native experiment stops here. No flight motion or subsequent execution is invented.")
        if previous != observed or len(events) != event_count or ev in ("initial", "finish"):
            frame = {"cycle": row["cycle"], "t": row["cycle"] * SECONDS_PER_CALL,
                     **copy.deepcopy(observed), "source": pointer}
            if frames and frames[-1]["cycle"] == frame["cycle"]:
                frames[-1] = frame
            else:
                frames.append(frame)
    if observed["dsky"] != rows[-1]["state"]["display"]:
        raise ValueError("Final DSKY does not agree with completed native run")
    return {
        "id": identifier, "title": title,
        "outcome": "Authentic 01406 failure · landing site absent" if identifier == "missing-site" else "Verified ignition-time calculation · V06 N61 review",
        "horizonCycle": rows[-1]["cycle"], "durationSeconds": rows[-1]["cycle"] * SECONDS_PER_CALL,
        "initialState": initial, "assumptions": geometry["assumptions"],
        "frames": frames, "events": events,
        "result": {"rootCount": observed["rootCount"], "ignitionTimeSeconds": observed["ignitionTimeSeconds"],
                   "observedClockSeconds": observed["observedClockSeconds"],
                   "ignitionLeadSeconds": observed["ignitionLeadSeconds"], "finalAlarms": observed["alarms"],
                   "reviewReached": review_seen, "finalDsky": observed["dsky"], "allOriginalChecksPass": actual["all_pass"]},
        "sources": {"tracePath": relative + "/trace.jsonl.gz", "rawSha256": sha256(raw),
                    "gzipSha256": sha256(compressed), "observerMapPath": relative + "/observer-map.json",
                    "observerMapSha256": sha256((directory / "observer-map.json").read_bytes()),
                    "configurationPath": relative + "/configuration.json", "configurationSha256": sha256(config_bytes),
                    "executionPath": relative + "/execution.json", "analysisPath": "docs/phase10-evidence/runs/final-validation/analysis.json"},
    }


def build_guidance() -> dict:
    inventory = verified_inventory()
    analyzer = module("mvp_original_phase10_analysis", EVIDENCE / "analyze.py")
    analysis = json.loads((RUNS / "analysis.json").read_text())
    if not analysis["all_pass"] or not all(analysis["comparisons"].values()):
        raise ValueError("Phase 10 retained experiment is not verified")
    return {
        "schemaVersion": 1, "mode": "RECORDED AUTHENTIC EXECUTION REPLAY",
        "clock": {"secondsPerCpuCall": SECONDS_PER_CALL, "sampling": "Sample and hold from actual retained observations; no interpolation, fabricated events, wall-clock coupling or predicted telemetry."},
        "provenance": {"sourceRevision": inventory["base_revision"], "emulatorRevision": EMULATOR_REVISION,
                       "ropeSha256": ROPE_SHA256, "evidenceRoot": RUNS.relative_to(ROOT).as_posix(),
                       "phase10SealSha256": SEAL_SHA256, "phase10Report": "docs/PHASE10_MISSION_INITIALIZATION.md",
                       "nativeExecution": "Retained original Luminary 099 instructions through pinned Virtual AGC; browser playback does not run the AGC.",
                       "integrity": "Sealed Phase 10 files, rope, raw/compressed traces, checkpoint mappings, DSKY decoder and original read-only analysis verified before export."},
        "labels": {
            "scenario": "SYNTHETIC lunar mission inputs with published preflight target padloads; not the historical Apollo 11 trajectory.",
            "replay": "RECORDED AUTHENTIC EXECUTION REPLAY. Playback controls explore existing traces and do not send commands to a live AGC.",
            "clock": "Replay position uses CPU-call time. Observed AGC clock and initialized navigation epoch are separate quantities; observations are held until the next recorded readback.",
            "timeToGo": "Signed original ROOTPSRS time-to-go result (seconds). Negative values retain the original guidance convention; this is not time remaining until ignition.",
            "ignitionTime": "Absolute TIG in the synthetic mission clock, available only after original IGNALGRT completes.",
            "ignitionLead": "TIG minus observed AGC clock at the same IGNALGRT checkpoint. Held solution lead, not a continuously updated countdown.",
            "dsky": "Actual channel 010 digit relay fields from the retained Phase 1 decoder. Blank and unknown digits are preserved; sign lamps are not decoded by this display adapter.",
            "projection": "Static X–Z projection: spacecraft at initialized epoch 120 s; planned site at nominal TLAND 784.4 s. These markers are not simultaneous observations. Orbit outline is an independent circular-state illustration; no spacecraft trajectory is replayed or propagated.",
            "scope": "Pre-ignition numerical guidance only. Physical alignment calibration, engine ignition, thrust response, powered descent and landing are NOT RUN.",
        },
        "cases": [export_case(*case, inventory, analysis, analyzer) for case in CASES],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Verify existing generated JSON without modifying it")
    args = parser.parse_args()
    content = encoded(build_guidance())
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != content:
            raise ValueError("Generated guidance data is absent or stale; run exporter without --check")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    print(json.dumps({"result": "VERIFIED", "mode": "recorded authentic replay", "bytes": len(content), "sha256": sha256(content), "checked": args.check}, indent=2))


if __name__ == "__main__":
    main()
