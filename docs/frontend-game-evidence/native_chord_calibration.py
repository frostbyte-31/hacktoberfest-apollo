#!/usr/bin/env python3
"""Inspect real two-key browser control edges using unchanged native sessions."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from backend import native_session as native


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnostics(rows, reference_time):
    plants = [r for r in rows if r["ev"] == "plant" and r["cycle"] >= native.READY_CYCLE]
    result = {}
    for angle in (1.5, 2, 3):
        c, s = math.cos(math.radians(angle)/2), math.sin(math.radians(angle)/2)
        target = [c*c, s*c, c*s, s*s]
        values = []
        for frame in plants:
            dot = abs(sum(a*b for a, b in zip(frame["quaternion"], target)))
            values.append({"errorDegrees": math.degrees(2*math.acos(min(1, dot))),
                           "rateDegreesPerSecond": math.hypot(*frame["omega"]),
                           "elapsedPhysicalSeconds": frame["cycle"]*native.PERIOD-reference_time})
        thresholds = {}
        for rate_limit in (1, 1.3):
            matches = [v for v in values if v["errorDegrees"] <= 1 and v["rateDegreesPerSecond"] <= rate_limit]
            windows, current = [], []
            for value in matches:
                if current and value["elapsedPhysicalSeconds"]-current[-1]["elapsedPhysicalSeconds"] > .03:
                    windows.append(current)
                    current = []
                current.append(value)
            if current:
                windows.append(current)
            thresholds[str(rate_limit)] = {
                "matchingSamples": len(matches),
                "windows": [{"first": window[0], "last": window[-1],
                             "spanSeconds": window[-1]["elapsedPhysicalSeconds"]-window[0]["elapsedPhysicalSeconds"]}
                            for window in windows]}
        result[str(angle)] = {"minimumError": min(values, key=lambda v: v["errorDegrees"]),
                              "minimumErrorBelowOneDegreePerSecond": min(
                                  (v for v in values if v["rateDegreesPerSecond"] <= 1), key=lambda v: v["errorDegrees"]),
                              "rateThresholds": thresholds}
    return result


def analyze(trace, reference_time):
    rows = [json.loads(line) for line in Path(trace).open()]
    return {"trace": {"path": str(trace), "sha256": digest(trace)},
            "physicalReferenceSeconds": reference_time,
            "inputs": [r for r in rows if r["ev"] in ("pilot_command", "neutral")],
            "targetsDegreesEachAxis": diagnostics(rows, reference_time)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-record", type=Path)
    parser.add_argument("--retain", type=Path)
    args = parser.parse_args()
    if args.retain and args.retain.exists():
        raise ValueError("Refusing to replace retained evidence")
    out = native.new_output("game-chord", ROOT / ".build/game-ui/chord" / (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-")+uuid.uuid4().hex[:8]))
    out.mkdir(parents=True)
    report = {"status": "INCOMPLETE", "scope": "Fresh native yaw then two-axis hand-controller input; no changed physics",
              "sourceHashes": {str(Path(__file__).relative_to(ROOT)): digest(__file__),
                               "backend/native_session.py": digest(ROOT / "backend/native_session.py")},
              "cases": {}, "rawOutput": str(out)}
    if args.http_record:
        record = json.loads(args.http_record.read_text())
        report["browserRecord"] = {"path": str(args.http_record), "sha256": digest(args.http_record),
            "requests": record["pilotRequests"],
            **analyze(Path(record["session"]["frame"]["trace_path"]), 2199887*native.PERIOD)}
    assets = native.prepare_assets(out / "assets")
    report["provenance"] = assets["provenance"]
    shutil.copyfile(Path(__file__), out / "executed-native-chord-calibration.py")
    try:
        for seconds in (.3, .35, .4, .5, .6):
            name = "yaw_edge_then_both_"+str(seconds)
            session = native.NativeSession(assets, output=out / name)
            try:
                first = session.start()
                session.command(1, 0, duration_cycles=42666)
                pitch_start = native.READY_CYCLE+4265
                release = pitch_start+round(seconds/native.PERIOD)
                session.advance_to(pitch_start)
                session.command(1, 1, duration_cycles=42666)
                refresh = pitch_start+12795
                while refresh < release:
                    session.advance_to(refresh)
                    session.command(1, 1, duration_cycles=42666)
                    refresh += 12795
                session.advance_to(release)
                session.command(0, 0, duration_cycles=0)
                session.advance_to(native.END_CYCLE)
                assert session.summary["status"] == "VERIFIED bounded live session"
                report["cases"][name] = {"bothHoldSeconds": seconds, "yawLeadCycles": 4265,
                    "nativeSummary": session.summary,
                    **analyze(session.output / "trace.jsonl", first["physical_time"])}
                value = report["cases"][name]["targetsDegreesEachAxis"]["2"]["rateThresholds"]["1"]
                print(name, json.dumps(value), flush=True)
            finally:
                if not session.closed:
                    session.stop("chord calibration cleanup")
        report["status"] = "VERIFIED fresh native chord calibration"
    finally:
        raw = json.dumps(report, indent=2, allow_nan=False)+"\n"
        (out / "result.json").write_text(raw)
        if args.retain:
            args.retain.write_text(raw)


if __name__ == "__main__":
    main()
