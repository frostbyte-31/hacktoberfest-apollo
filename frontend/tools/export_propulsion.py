#!/usr/bin/env python3
"""Read-only browser adapter for the sealed Phase 12 release experiment.

No AGC executes, no flight memory changes, and no physics is integrated here.
Every displayed observation is sampled and held from a retained native trace.
The bounded synthetic fixed-attitude experiment is never a historical landing.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/phase12-release-evidence"
RUNS = EVIDENCE / "phase12-runs"
DEFAULT_OUTPUT = ROOT / "frontend/dist/data/propulsion.json"
SEAL_SHA256 = "5bf1b34d2a467d22a142859e2ef67994adc0c3210729bb2bcfbeeba565dfee40"
ROPE_SHA256 = "1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e"
DECODER_SHA256 = "2d290eb0095af194ddf52560f0d87a97ccb575a95c9e587d390ff8c42ef7a86e"
SECONDS_PER_CALL = 12 / 1024000
PHYSICAL_SAMPLE_SECONDS = .25
CASES = (
    ("connected", "Engine + sensor feedback", "Physical engine and PIPA feedback connected."),
    ("sink", "Engine disconnected", "Original commands retained; physical engine force disconnected."),
    ("no-feedback", "Sensor feedback disconnected", "Physical engine connected; generated PIPA counts withheld from the AGC."),
    ("repeat", "Deterministic repeat", "A separate native run is byte-identical to the connected execution."),
)
STAGES = {
    "original-DAP-config-review": ("DAP configuration review", "Original V48 displays the DAP configuration. The retained fixture changes it with V21 N46."),
    "original-mass-load-complete": ("Mass input complete", "Original V48/V21 N47 transactions have loaded +33069. This is retained experiment input, not Apollo 11 historical mass telemetry."),
    "phase10-V06N61": ("P63 · pre-ignition review", "Original Luminary displays V06 N61. The physical plant begins at this retained observation."),
    "R51-checklist": ("R51 · checklist 14", "The actual V50 N25 display requests checklist 14. The retained crew transaction enters ENTR."),
    "R60-crew-attitude-review": ("R60 · attitude review", "The actual V50 N18 attitude display is presented. Fixed CDUs are a diagnostic limitation; an achieved burn attitude is not established."),
    "after-attitude-review": ("Crew switch review", "The actual V50 N25 display shows checklist 00500 before documented external hardware inputs."),
    "crew-switches-set": ("Recorded cockpit discretes set", "The harness sets active-low engine ARM, AUTO throttle, G+N control and ATT MODE AUTO hardware inputs. These are recorded fixture transactions, not an interactive cockpit."),
    "crew-switch-checklist": ("Checklist continuation", "Original P40AUTO checklist is continued through the recorded V33E transaction."),
    "preignition-wait": ("Awaiting original ignition request", "The engine is armed but remains off. A crew enable request and actual engine-on output are separate observations."),
    "original-engine-enable-request": ("V99 N62 · crew enable request", "Original Luminary requests crew permission. This display is not engine ignition; the recorded continuation is V33E."),
    "bounded-post-enable-horizon": ("Bounded engine experiment", "The retained P63 diagnostic horizon has been reached. It does not complete powered descent or a landing."),
    "original-shutdown-reset-requested": ("P00 · software shutdown", "Original P00 has commanded ENGINE OFF. The incomplete automatic-counter reset is preserved rather than fabricated as a full reset."),
    "crew-disarmed": ("Crew disarm", "A separate external engine DISARM input clears the external accumulator after the original software shutdown."),
}
CHECKPOINT_EVENTS = {
    "P51": ("P51 alignment starts", "Original P51 executes with synthetic star sightings; this is not the historical Apollo 11 alignment sequence."),
    "P63LM": ("P63 selected", "Recorded V37E63E selects original Luminary powered-descent initiation."),
    "P63_AFTER_R02": ("Reference readiness passes", "Original reference-matrix readiness returns to P63."),
    "IGNITION": ("Original IGNITION routine", "This source checkpoint identifies original instruction execution; the engine-on output is separately observed."),
    "P63IGN": ("Original P63IGN continuation", "Original powered-descent ignition continuation executes."),
    "P63ZOOM": ("Original P63ZOOM", "Original P63 transition logic executes in the bounded diagnostic."),
    "FLATOUT": ("Original FLATOUT", "Original Luminary loads the 4096-count throttle command; genuine external clock pulses deliver it."),
    "DOIT": ("Original throttle DOIT", "Original throttle instructions execute; no browser throttle calculation is substituted."),
}


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def checked_bytes(path: Path, expected: str) -> bytes:
    content = path.read_bytes()
    if sha256(content) != expected:
        raise ValueError(f"Evidence integrity mismatch: {path}")
    return content


def verified_inventory() -> dict:
    seal = json.loads(checked_bytes(EVIDENCE / "checksums.json", SEAL_SHA256))
    for relative, expected in seal["sha256"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(EVIDENCE):
            raise ValueError("Release seal path escapes its evidence directory")
        checked_bytes(path, expected)
    checked_bytes(ROOT / "docs/phase1-evidence/artifacts/MAIN.agc.bin", ROPE_SHA256)
    checked_bytes(ROOT / "docs/phase1-evidence/m2_dsky_client.py", DECODER_SHA256)
    return seal


def decoder_for(identifier):
    spec = importlib.util.spec_from_file_location(
        "p12_display_" + identifier.replace("-", "_"), ROOT / "docs/phase1-evidence/m2_dsky_client.py")
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    return decoder


def pointer(row, line, **extra):
    return {"rawLine": line, "cycle": row["cycle"], **extra}


def physical_state(row, line, initial_time):
    telemetry = row["telemetry"]
    names = {
        "positionM": "position_ref_m", "velocityMps": "velocity_ref_m_s",
        "quaternion": "quaternion_body_to_ref", "physicalTimeSeconds": "time_s",
        "massKg": "mass_kg", "fuelKg": "fuel_kg",
        "deliveredThrustN": "delivered_thrust_n", "commandedThrustN": "commanded_thrust_n",
        "engineEnabled": "engine_enabled", "requestedEngineEnabled": "requested_engine_enabled",
        "physicalEngineConnected": "physical_engine_connected",
        "specificForceMps2": "specific_force_ref_m_s2", "gravityMps2": "gravity_ref_m_s2",
        "totalAccelerationMps2": "total_acceleration_ref_m_s2",
        "thrustVectorN": "thrust_vector_ref_n", "massFlowKgPerSecond": "mass_flow_kg_s",
        "angularVelocityRadPerSecond": "angular_velocity_body_rad_s",
    }
    result = {name: telemetry[key] for name, key in names.items()}
    result["elapsedPhysicalSeconds"] = telemetry["time_s"] - initial_time
    result["source"] = pointer(row, line)
    return result


def receiver_state(receiver, row, line):
    names = {"armed": "armed", "autothrottle": "autothrottle", "requestedEngineOn": "requested_engine_on",
             "enabled": "enabled", "automaticCount": "automatic_count", "commandedThrustN": "commanded_thrust_n"}
    return {**{name: receiver[key] for name, key in names.items()}, "source": pointer(row, line)}


def export_case(identifier, title, description, inventory, analysis):
    directory = RUNS / identifier
    relative = directory.relative_to(ROOT).as_posix()
    compressed = checked_bytes(directory / "trace.jsonl.gz", inventory["sha256"][relative + "/trace.jsonl.gz"])
    raw = gzip.decompress(compressed)
    fingerprint = json.loads((directory / "trace-sha256.json").read_bytes())
    if sha256(raw) != fingerprint["sha256"] or len(raw) != fingerprint["bytes"]:
        raise ValueError("Decompressed Phase 12 fingerprint mismatch")
    result = analysis["runs"][identifier]
    if not result["all_pass"] or not all(result["checks"].values()):
        raise ValueError("Retained original Phase 12 assertions did not pass")
    if result["raw_sha256"] != fingerprint["sha256"] or result["raw_bytes"] != fingerprint["bytes"]:
        raise ValueError("Retained Phase 12 analysis does not identify this trace")
    execution = json.loads((directory / "execution.json").read_bytes())
    if execution["rope_sha256"] != ROPE_SHA256:
        raise ValueError("Unexpected original rope")
    mapping = json.loads((directory / "observer-map.json").read_bytes())
    decoder = decoder_for(identifier)
    observed = {"dsky": decoder.snapshot(), "stage": "Original software startup", "observedProgram": None,
                "spacecraft": None, "receiver": None, "crewDiscretes": {},
                "pipa": {"generatedCounts": [0, 0, 0], "deliveredCounts": [0, 0, 0], "source": None},
                "observationSources": {"dsky": None, "program": None}}
    frames, events, keys, navigation_samples = [], [], [], []
    event_snapshots = {}
    navigation_by_cycle = {sample["cycle"]: sample for sample in result["navigation_samples"]}
    physical_initial_time = None
    last_sampled_physical = None
    last_engine_signature = None
    previous_cycle = -1
    first_ignition = None
    physical_count = 0
    initial_geometry = None
    first_checkpoint = set()
    event_serial = 0
    first_generated = first_delivered = first_consumed = False

    def event(row, line, event_id, event_title, text, kind="execution", **extra):
        nonlocal event_serial
        event_serial += 1
        events.append({"id": f"{event_id}-{event_serial}", "title": event_title, "description": text,
                       "kind": kind, "cycle": row["cycle"], "t": row["cycle"] * SECONDS_PER_CALL,
                       "source": pointer(row, line), **extra})

    def observation(row, line):
        return {"cycle": row["cycle"], "t": row["cycle"] * SECONDS_PER_CALL,
                "source": pointer(row, line), **copy.deepcopy(observed)}

    def frame(row, line):
        value = observation(row, line)
        if frames and frames[-1]["cycle"] == row["cycle"]:
            frames[-1] = value
        else:
            frames.append(value)

    for line, content in enumerate(raw.splitlines(), 1):
        row = json.loads(content)
        events_before_row = len(events)
        ev = row["ev"]
        cycle = row["cycle"]
        if cycle < previous_cycle:
            raise ValueError("Native trace cycles are not monotonic")
        previous_cycle = cycle
        capture = line == 1
        if ev == "initial" and (row["original_ram_writes"] != 0 or row["rope_sha256"] != ROPE_SHA256):
            raise ValueError("Trace is not original rope with no original RAM setter")
        if ev == "output" and row["channel"] == 0o10:
            decoder.apply010(row["value"])
            display = decoder.snapshot()
            if display != row["display"]:
                raise ValueError("Original channel 010 DSKY decoding disagrees with retained output")
            if display != observed["dsky"]:
                observed["dsky"] = display
                observed["observationSources"]["dsky"] = pointer(row, line, channelOctal="010", valueOctal=format(row["value"], "05o"))
                capture = True
        if "state" in row and "modreg" in row["state"]:
            observed["observedProgram"] = row["state"]["modreg"]
            observed["observationSources"]["program"] = pointer(row, line)
        if ev == "key_sequence":
            keys.append({"text": row["text"], "cycle": cycle, "t": cycle * SECONDS_PER_CALL, "source": pointer(row, line)})
            event(row, line, "keys", "Recorded DSKY · " + row["text"],
                  "Actual retained key sequence. E means ENTR; V33E is a recorded verb transaction, not a claim that the PRO key was pressed.",
                  "dsky-input", keys=row["text"])
            capture = True
        elif ev == "mission_initialization_start":
            geometry = row["config"]["synthetic_geometry"]
            initial_geometry = {"lunarRadiusM": geometry["lunar_reference_radius_m"],
                "initializedEpochSeconds": geometry["state_epoch_cs"] / 100,
                "positionFrame": "Moon-centered basic REF inertial", "velocityFrame": "Moon-centered basic REF inertial",
                "quaternionFrame": "Scalar-first body-to-basic-REF; fixed measured CDU fixture",
                "classification": "SYNTHETIC circular-orbit fixture, not Apollo 11 historical trajectory",
                "source": pointer(row, line)}
            observed["stage"] = "P27 · synthetic mission initialization"
            event(row, line, "initialization", "P27 mission inputs", "Original P27 receives documented synthetic navigation state and target padloads through normal DSKY transactions.")
            capture = True
        elif ev == "alignment_result":
            observed["stage"] = "P51 · reference alignment complete"
            event(row, line, "aligned", "P51 reference alignment complete", "Original software set reference readiness from synthetic star inputs; no historical Apollo 11 calibration is implied.")
            capture = True
        elif ev == "stage":
            stage_title, stage_description = STAGES[row["name"]]
            observed["stage"] = stage_title
            event(row, line, row["name"], stage_title, stage_description, "crew-review")
            if row.get("receiver") is not None:
                observed["receiver"] = receiver_state(row["receiver"], row, line)
            for channel, value in row["channels"].items():
                if int(channel) in (0o30, 0o31, 0o33):
                    observed["crewDiscretes"][format(int(channel), "03o")] = {"value": value, "valueOctal": format(value, "05o"), "source": pointer(row, line)}
            capture = True
        elif ev == "input" and "crew" in row.get("origin", ""):
            observed["crewDiscretes"][format(row["channel"], "03o")] = {"value": row["value"], "valueOctal": format(row["value"], "05o"), "source": pointer(row, line)}
            event(row, line, "hardware-input", "Recorded hardware input · channel " + format(row["channel"], "03o"),
                  row["origin"] + "; exact active-low packet is retained.", "cockpit-input",
                  channelOctal=format(row["channel"], "03o"), valueOctal=format(row["value"], "05o"))
            capture = True
        elif ev == "checkpoint":
            routine = row["routine"]
            # Seven interpreted entries are observed at their NEWOPS dispatch,
            # rather than pretending the dispatcher PC is the interpreted PC.
            interpreted = routine in ("CALCRVG", "MUNRVG", "LUNLAND", "MIDTOAV1", "MIDTOAV2", "MUNRETRN", "COPYCYC2")
            expected_pcs = [mapping["checkpoints"][routine]] + ([[3, 3128]] if interpreted else [])
            if [row["pre_bank"], row["pre_z"]] not in expected_pcs:
                raise ValueError("Checkpoint does not match original source bank/address")
            if routine in CHECKPOINT_EVENTS and routine not in first_checkpoint:
                first_checkpoint.add(routine)
                event_title, text = CHECKPOINT_EVENTS[routine]
                event(row, line, routine.lower(), event_title, text, routine=routine)
                capture = True
            if cycle in navigation_by_cycle:
                sample = navigation_by_cycle[cycle]
                if routine != "MUNRETRN":
                    raise ValueError("Retained navigation solution is not at original MUNRETRN")
                navigation_samples.append({"cycle": cycle, "t": cycle * SECONDS_PER_CALL,
                    "positionM": sample["R_computed_stable_m"], "velocityMps": sample["V_computed_stable_m_s"],
                    "coordinateFrame": "IMU stable member; distinct from physical basic REF state",
                    "timeSeconds": sample["PIPTIME_cs"] / 100, "periodSeconds": sample["period_s"],
                    "pipaConsumedCounts": sample["consumed_counts"], "pulseDeltaVMps": sample["pulse_delta_v_stable_m_s"],
                    "source": pointer(row, line, routine=routine),
                    "analysisPath": "docs/phase12-release-evidence/phase12-validation/analysis.json"})
                if any(sample["consumed_counts"]) and not first_consumed:
                    first_consumed = True
                    event(row, line, "navigation-feedback", "Original navigation consumes thrust feedback",
                          "At this actual MUNRETRN observation, original Luminary navigation has consumed the physical engine-derived PIPA counts.", "sensor")
                capture = True
        elif ev in ("plant_initialization", "plant"):
            physical_count += ev == "plant"
            if physical_initial_time is None:
                physical_initial_time = row["telemetry"]["time_s"]
                event(row, line, "physical-init", "Physical state becomes available", "Actual retained external plant samples begin here. Earlier physical motion is not available for browser replay.", "physical")
                capture = True
            observed["spacecraft"] = physical_state(row, line, physical_initial_time)
            telemetry = row["telemetry"]
            signature = (telemetry["engine_enabled"], telemetry["requested_engine_enabled"])
            if last_engine_signature is not None and signature != last_engine_signature:
                event(row, line, "physical-engine", "Physical thrust enabled" if telemetry["engine_enabled"] else "Physical thrust stopped",
                      "This is an actual external plant observation, separate from the original command output.", "physical")
                capture = True
            last_engine_signature = signature
            if last_sampled_physical is None or telemetry["time_s"] - last_sampled_physical >= PHYSICAL_SAMPLE_SECONDS:
                capture = True
            if capture:
                last_sampled_physical = telemetry["time_s"]
            interval = row.get("sensor_interval")
            if interval:
                generated = observed["pipa"]["generatedCounts"]
                generated[:] = [a + b for a, b in zip(generated, interval["generated_counts"])]
                observed["pipa"]["source"] = pointer(row, line)
                if any(interval["generated_counts"]) and not first_generated:
                    first_generated = True
                    event(row, line, "pipa-generated", "Physical acceleration produces PIPA counts",
                          "The external physical sensor quantizes actual engine-derived specific impulse. Gravity is not fabricated as accelerometer thrust feedback.", "sensor")
                    capture = True
        elif ev == "pipa_measurement" and row["connected"]:
            axis = "XYZ".index(row["axis"])
            observed["pipa"]["deliveredCounts"][axis] += 1 if row["operation"] == 0 else -1
            observed["pipa"]["source"] = pointer(row, line)
            if not first_delivered:
                first_delivered = True
                event(row, line, "pipa-delivered", "PIPA counter packet delivered",
                      "An actual engine-derived counter-operation packet reaches the original AGC. The retained source includes its bounded coupling delay.", "sensor")
                capture = True
        elif ev == "engine_receiver":
            observed["receiver"] = receiver_state(row["receiver"], row, line)
            if row["source_channel"] == 0o11:
                if row["receiver"]["requested_engine_on"] and first_ignition is None:
                    first_ignition = cycle
                    event(row, line, "engine-on", "Original ENGINE ON output", "Original Luminary's actual channel 011 output now commands engine on. V99 crew permission occurred earlier.", "engine-command")
                    capture = True
                elif not row["receiver"]["requested_engine_on"]:
                    event(row, line, "engine-off", "Original ENGINE OFF output", "Original software output removes the engine-on request; physical force-off and later crew disarm are separately observed.", "engine-command")
                    capture = True
        elif ev == "finish":
            event(row, line, "end", "Retained experiment ends", "The native run ends after P00 and crew disarm. No lunar landing or subsequent mission phase was executed.", "boundary")
            capture = True
        if capture:
            frame(row, line)
        # Distinct raw rows can share one CPU cycle. An event selection must
        # retain the held state exactly at that row, before later hardware
        # packets, plant initialization or displays with an equal timestamp.
        for emitted in events[events_before_row:]:
            event_snapshots[emitted["id"]] = observation(row, line)

    if len(navigation_samples) != len(navigation_by_cycle):
        raise ValueError("Original navigation analysis sample is missing from raw trace")
    if physical_count != result["physical"]["rows"] or first_ignition != result["first_engine_on"]["cycle"]:
        raise ValueError("Retained physical/ignition summary does not match native trace")
    final = observed["spacecraft"]
    if final["positionM"] != result["physical"]["final"]["position_ref_m"]:
        raise ValueError("Retained final physical state differs from analysis")
    if observed["pipa"]["generatedCounts"] != result["sensor"]["generated_counts"] or observed["pipa"]["deliveredCounts"] != result["sensor"]["delivered_counts"]:
        raise ValueError("Raw physical sensor counts disagree with retained analysis")
    return {"id": identifier, "title": title, "description": description,
        "classification": "SYNTHETIC fixed-attitude P63 engine/PIPA/navigation experiment; not a historical Apollo 11 flight",
        "mode": "VERIFIED RECORDED EXECUTION", "startCycle": 0, "endCycle": previous_cycle,
        "durationSeconds": previous_cycle * SECONDS_PER_CALL,
        "physicalEngineConnected": execution["physical_engine_connected"],
        "sensorFeedbackConnected": execution["pipa_feedback_connected"],
        "initialGeometry": initial_geometry, "frames": frames, "events": events, "eventSnapshots": event_snapshots, "keySequences": keys,
        "navigationSamples": navigation_samples,
        "sources": {"tracePath": relative + "/trace.jsonl.gz", "gzipSha256": sha256(compressed),
            "rawSha256": sha256(raw), "rawBytes": len(raw), "observerMapPath": relative + "/observer-map.json",
            "observerMapSha256": inventory["sha256"][relative + "/observer-map.json"],
            "executionPath": relative + "/execution.json", "analysisPath": "docs/phase12-release-evidence/phase12-validation/analysis.json"},
        "outcome": {"allOriginalChecksPass": True, "originalChecks": result["checks"],
            "firstEngineOn": result["first_engine_on"], "firstFlatoutCycle": result["first_flatout_cycle"],
            "finalSpacecraft": final, "sensor": result["sensor"],
            "shutdown": result["counter_clock"]["software_shutdown_reset"],
            "physicalSpecificImpulseRefMps": result["physical"]["physical_specific_impulse_REF_m_s"],
            "maximumPlantIntervalSeconds": result["physical"]["max_interval_s"],
            "physicalSourceProvenance": result["physical"]["initialization"]["physical_provenance"],
            "classification": result["classification"]}}


def build_propulsion():
    inventory = verified_inventory()
    analysis = json.loads((EVIDENCE / "phase12-validation/analysis.json").read_bytes())
    if not analysis["all_pass"] or not all(analysis["comparisons"].values()):
        raise ValueError("Retained causal comparisons did not all pass")
    cases = [export_case(*case, inventory, analysis) for case in CASES]
    if cases[0]["sources"]["rawSha256"] != cases[3]["sources"]["rawSha256"]:
        raise ValueError("Connected/repeat captures no longer match")
    return {"schema": 1, "schemaVersion": 1, "mode": "VERIFIED RECORDED EXECUTION",
        "scope": "Bounded synthetic fixed-attitude original P63 engine/PIPA/navigation experiment. No achieved burn attitude, historical trajectory, full descent or landing is established.",
        "provenance": {"releaseSealPath": "docs/phase12-release-evidence/checksums.json", "releaseSealSha256": SEAL_SHA256,
            "sealedFilesChecked": inventory["files"], "ropeSha256": ROPE_SHA256,
            "emulatorRevision": "f577e3fd917866c59334e6cdd32504f09df76f60", "dskyDecoderSha256": DECODER_SHA256},
        "units": {"position": "m", "velocity": "m/s", "thrust": "N", "mass": "kg", "acceleration": "m/s²",
            "angularVelocity": "rad/s", "time": "s", "quaternion": "dimensionless scalar-first [w,x,y,z]"},
        "frames": {"position": "Moon-centered basic REF inertial", "velocity": "Moon-centered basic REF inertial",
            "attitude": "body-to-basic-REF, fixed measured CDU fixture", "pipa": "IMU stable member"},
        "sampling": {"method": "sample and hold only; no interpolation, extrapolation or browser physics",
            "physicalSpacingSeconds": PHYSICAL_SAMPLE_SECONDS,
            "cpuClock": "t = actual native cycle × 12 / 1024000 seconds; not historical GET",
            "physicalClock": "physicalTimeSeconds is the recorded external plant elapsed time from the initialized state epoch (120 s); it is separate from CPU replay time and AGC TIME2/TIME1",
            "sourcePointers": "Each changing field preserves its actual source rawLine/cycle. A frame combines last-known asynchronous observations; it is not one simultaneous sensor packet."},
        "dskyScope": "Original channel 010 digit relay output. Register sign lamps and indicator channels are not decoded by this inherited digit-only decoder; no signs or lamps are invented.",
        "limitations": ["Retained crew steps are experiment transactions, not Apollo 11's historical mission checklist.",
            "CDUs and body attitude remain fixed. A commanded attitude display is not an achieved physical attitude.",
            "Nominal instantaneous engine response and guidance pulse-to-force scale are model assumptions, not flight-calibrated engine dynamics.",
            "Live arbitrary DSKY input, cockpit mode interlocks, coupled free attitude, translation controls and complete descent are not exposed by this recorded adapter."],
        "cases": cases, "comparisons": analysis["comparisons"],
        "causalNavigationComparisons": analysis["causal_navigation_comparisons"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Require the existing export to match without writing it")
    args = parser.parse_args()
    content = encoded(build_propulsion())
    if args.check:
        if args.output.read_bytes() != content:
            raise ValueError("Propulsion browser export is stale")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    print(json.dumps({"output": str(args.output), "bytes": len(content), "sha256": sha256(content), "source": "sealed Phase 12 release evidence", "mode": "VERIFIED RECORDED EXECUTION"}))


if __name__ == "__main__":
    main()
