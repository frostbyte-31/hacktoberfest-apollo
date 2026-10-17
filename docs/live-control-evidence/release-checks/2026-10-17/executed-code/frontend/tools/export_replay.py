#!/usr/bin/env python3
"""Export a small, read-only browser replay from retained Phase 7 evidence.

No emulator or physics runs here. Every frame is an existing model sample;
AGC packets retain their original execution cycles in a separate event stream.
Only the output path is configurable, so a different experiment cannot silently
replace the verified demo. Python standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/phase7-evidence/runs/2026-10-17-verified-check"
DEFAULT_OUTPUT = ROOT / "frontend/dist/data/replay.json"
RETENTION_SHA256 = "63f30a510198ad9d0b77727b2a924dbd0d0313e958705ec6e0bbc976a2bf12b8"
SUMMARY_SHA256 = "12903a0c27dec74a20dc36bb81967dd63bcc19f4af78f2af62025595f01127b8"
EMULATOR_REVISION = "f577e3fd917866c59334e6cdd32504f09df76f60"
ROPE_SHA256 = "1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e"
SECONDS_PER_CYCLE = 12 / 1024000
SAMPLE_SECONDS = 0.1
TITLES = {
    "yaw": "Yaw · connected feedback",
    "pitch": "Pitch · connected feedback",
    "pitch_off": "Pitch · disconnected control",
    "combined": "Yaw + pitch · connected feedback",
    "combined_off": "Yaw + pitch · disconnected control",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_bytes(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    actual = sha256(data)
    if actual != expected:
        raise ValueError(f"Integrity mismatch: {path}: {actual} != {expected}")
    return data


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def timestamp(cycle: int) -> dict:
    return {"cycle": cycle, "t": cycle * SECONDS_PER_CYCLE}


def latest(samples: list[tuple[int, object]], cycle: int) -> object:
    """Return an actual readback at or before cycle, with no interpolation."""
    low, high = 0, len(samples)
    while low < high:
        middle = (low + high) // 2
        if samples[middle][0] <= cycle:
            low = middle + 1
        else:
            high = middle
    index = low - 1
    return samples[index][1] if index >= 0 else None


def sampled_plants(plants: list[dict]) -> list[dict]:
    """Keep the first recorded model endpoint at each 100 ms display mark."""
    chosen = []
    next_tick = 0
    for plant in plants:
        if plant["cycle"] * SECONDS_PER_CYCLE + 1e-12 >= next_tick * SAMPLE_SECONDS:
            chosen.append(plant)
            next_tick += 1
    if chosen[-1] is not plants[-1]:
        chosen.append(plants[-1])
    return chosen


def export_case(case: str, summary: dict, retained: dict) -> dict:
    rel = f"validation/integration/{case}.jsonl.gz"
    record = next(item for item in retained["lossless_trace_compression"] if item["retained_path"] == rel)
    compressed = checked_bytes(EVIDENCE / rel, record["gzip_sha256"])
    raw = gzip.decompress(compressed)
    if sha256(raw) != record["sha256"] or len(raw) != record["bytes"]:
        raise ValueError(f"Raw trace mismatch: {case}")
    rows = [json.loads(line) for line in raw.splitlines()]
    initial = rows[0]
    actual_summary = next(row for row in reversed(rows) if row["ev"] == "summary")
    expected = summary["cases"][case]
    if initial["ev"] != "initial" or initial["scenario"] != actual_summary["scenario"]:
        raise ValueError(f"Scenario mismatch: {case}")
    if expected["raw_sha256"] != record["sha256"]:
        raise ValueError(f"Summary/trace mismatch: {case}")
    for key in ("counts", "settled", "quiet", "final_model", "peak_abs_omega_deg_s"):
        if actual_summary[key] != expected[key]:
            raise ValueError(f"Summary value mismatch: {case}/{key}")
    if initial["cycle_seconds"] != SECONDS_PER_CYCLE:
        raise ValueError("Unexpected CPU clock")

    plants = sorted((row for row in rows if row["ev"] == "plant"), key=lambda row: row["cycle"])
    if plants[-1]["cycle"] != initial["end"]:
        raise ValueError(f"Missing final physical endpoint: {case}")
    cdu_readbacks = []
    readiness = []
    checkpoints = []
    rcs_events = []
    input_events = []
    packet_latches = {5: None, 6: None}
    for row in rows:
        event = row["ev"]
        if event == "execution_sample":
            registers = row["registers"]
            readiness.append((row["cycle"], {"cycle": row["cycle"], **registers}))
        elif event == "startup_checkpoint":
            cdu_readbacks.append((row["cycle"], row["state"]["cdu"]))
            snapshot = {key: row[key] for key in ("modreg", "failreg", "dapbools", "imodes30", "imodes33")}
            readiness.append((row["cycle"], {"cycle": row["cycle"], **snapshot}))
            checkpoints.append({"name": "startup", **timestamp(row["cycle"]), **snapshot, "cdu": row["state"]["cdu"]})
        elif event == "application":
            cdu_readbacks.append((row["cycle"], row["after"]["cdu"]))
        elif event == "freeze":
            cdu_readbacks.append((row["cycle"], row["state"]["cdu"]))
            checkpoints.append({"name": "freeze", **timestamp(row["cycle"]), "cdu": row["state"]["cdu"]})
        elif event == "settled":
            checkpoints.append({"name": "settled", **timestamp(row["state"]["cycle"]), "cdu": row["state"]["cdu"]})
        elif event == "output" and row["channel"] in (5, 6):
            channel = row["channel"]
            changed = packet_latches[channel] != row["value"]
            packet_latches[channel] = row["value"]
            rcs_events.append({**timestamp(row["cycle"]), "channel": channel, "value": row["value"], "changed": changed, "tail": row["tail"]})
        elif event == "input":
            input_events.append({**timestamp(row["cycle"]), "channel": row["channel"], "value": row["value"]})
    cdu_readbacks.sort(key=lambda item: item[0])
    readiness.sort(key=lambda item: item[0])
    rcs_events.sort(key=lambda item: item["cycle"])
    input_events.sort(key=lambda item: item["cycle"])
    frames = []
    for plant in sampled_plants(plants):
        cycle = plant["cycle"]
        frames.append({
            **timestamp(cycle),
            "q": plant["quaternion"],
            "omega": plant["omega"],
            "gimbals": plant["gimbals"],
            "torque": plant["torque_Nm"],
            "alpha": plant["alpha_rad_s2"],
            "cdu": latest(cdu_readbacks, cycle),
            "rcs": plant["jets"],
            "readiness": latest(readiness, cycle),
            "altitude": None,
            "position": None,
            "dsky": None,
        })
    horizon = initial["end"]
    return {
        "id": case,
        "title": TITLES[case],
        "feedbackConnected": not initial["feedback_disconnected"],
        "source": {"tracePath": str((EVIDENCE / rel).relative_to(ROOT)), "rawSha256": record["sha256"], "gzipSha256": record["gzip_sha256"]},
        "horizonCycle": horizon,
        "durationSeconds": horizon * SECONDS_PER_CYCLE,
        "settledCycle": expected["settled"]["cycle"],
        "quietCycle": expected["quiet"]["cycle"],
        "initialConditions": initial["initial_conditions"],
        "notes": [
            "Recorded experiment replay. Controls select playback; they do not command a live AGC.",
            "Only yaw and pitch control were validated; roll motion from rigid-body coupling is retained.",
            "Physical evolution freezes at the horizon. Authentic CPU and queued sensor operations then settle; settlement is not attitude stability.",
            "Quaternion, rates, torque and gimbals are simulated fixture outputs, not historical Apollo flight telemetry.",
            "CDU words and readiness are held from the latest recorded readback; null means no readback yet.",
        ] + (["Disconnected control intentionally omits every generated CDU feedback operation."] if initial["feedback_disconnected"] else []),
        "counts": expected["counts"],
        "sensorsApplied": sum(axis["applied"] for axis in expected["counts"]),
        "peakOmegaDegS": expected["peak_abs_omega_deg_s"],
        "finalModel": expected["final_model"],
        "finalCdu": expected["settled"]["cdu"],
        "frames": frames,
        "rcsEvents": rcs_events,
        "inputEvents": input_events,
        "checkpoints": checkpoints,
    }


def build_replay() -> dict:
    retention = json.loads(checked_bytes(EVIDENCE / "retention.json", RETENTION_SHA256))
    summary = json.loads(checked_bytes(EVIDENCE / "validation/integration/summary.json", SUMMARY_SHA256))
    inputs_rel = "validation/integration/inputs_source_hashes.json"
    inputs_record = next(item for item in retention["copied_files"] if item["retained_path"] == inputs_rel)
    inputs = json.loads(checked_bytes(EVIDENCE / inputs_rel, inputs_record["sha256"]))
    if inputs["upstream_revision"] != EMULATOR_REVISION:
        raise ValueError("Emulator revision mismatch")
    checked_bytes(ROOT / "docs/phase1-evidence/artifacts/MAIN.agc.bin", ROPE_SHA256)
    if summary["capability"] != "C" or not summary["levels"]["C"] or summary["levels"]["D"]:
        raise ValueError("Unexpected evidence capability")
    return {
        "schemaVersion": 1,
        "clock": {"secondsPerCycle": SECONDS_PER_CYCLE, "displaySampleSeconds": SAMPLE_SECONDS, "sampling": "Actual model endpoints at approximately 10 Hz, plus final endpoint; no synthetic/interpolated physics samples."},
        "provenance": {
            "sourceRevision": retention["source_revision"],
            "emulatorRevision": EMULATOR_REVISION,
            "ropeSha256": ROPE_SHA256,
            "evidenceRoot": str(EVIDENCE.relative_to(ROOT)),
            "retentionSha256": RETENTION_SHA256,
            "summarySha256": SUMMARY_SHA256,
            "capability": "C — bounded simultaneous yaw/pitch control",
            "rawTraceIntegrity": "All five compressed and decompressed traces checked against the pinned Phase 7 retention inventory.",
        },
        "labels": {
            "agc": "Authentic retained Luminary 099 execution: output packets, CDU readbacks and readiness registers.",
            "model": "Modern external synthetic rigid-body/IMU fixture: quaternion, angular rate, torque and gimbals.",
            "quaternion": "Scalar-first [w,x,y,z], active body-to-stable right-handed orientation.",
            "omega": "Body [P,Q,R] = model [yaw,pitch,roll], degrees/second.",
            "gimbals": "[O,I,M] = outer/inner/middle, degrees, from C=Ry(I) Rz(M) Rx(O).",
            "torque": "Body [P,Q,R], newton-metres; effective 1 m lever arm, synthetic inertias.",
            "alpha": "Body [P,Q,R], radians/second squared, including Euler angular-momentum coupling.",
            "cdu": "Actual AGC counters [032,033,034] (octal addresses), unsigned 15-bit angle counts; quantum 360/32768 degrees.",
            "rcs": "Frame rcs=[channel005,channel006] packet latches applied during that model interval; exact new packet timings are in rcsEvents.",
            "readiness": "Actual diagnostic memory readback, not a decoded DSKY display; cycle gives readback age.",
            "missing": {"altitude": None, "position": None, "dsky": None},
            "limits": "No descent, terrain, landing, calibrated flight fidelity, live piloting or full three-axis control demonstration.",
        },
        "cases": [export_case(case, summary, retention) for case in TITLES],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    replay = build_replay()
    content = encoded(replay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(content)
    print(json.dumps({"output": str(args.output), "bytes": len(content), "sha256": sha256(content), "cases": {case["id"]: {"frames": len(case["frames"]), "rcsPackets": len(case["rcsEvents"]), "sensorsApplied": case["sensorsApplied"]} for case in replay["cases"]}}, indent=2))


if __name__ == "__main__":
    main()
