#!/usr/bin/env python3
"""Reproduce small-angle game inputs through the unchanged retained native fixture.

No guidance, model, sensor or attitude writes are introduced. Raw native traces
stay in a new .build directory. A small sample/summary document may be retained
beside this harness using --retain; it is never an application data provider.
"""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from backend import native_session as native

STEP_CYCLES = 4265
CASES = {
    "yaw_one_second": (1, 0, 85333),
    "pitch_one_second": (0, 1, 85333),
    "yaw_short_pulse": (1, 0, 34133),
    "pitch_short_pulse": (0, 1, 34133),
    "combined_short_pulse": (1, 1, 34133),
    "combined_brief_pulse": (1, 1, 17066),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def sample(frame):
    model = frame["model"]
    return {"cycle": frame["cycle"], "modelCycle": frame["model_cycle"],
            "cpuTimeSeconds": frame["sim_time"],
            "physicalTimeSeconds": frame["physical_time"],
            "interactiveTimeSeconds": frame["interactive_time"],
            "remainingSeconds": frame["remaining_time"],
            "quaternionWxyz": model["quaternion"],
            "bodyRatesDegreesPerSecond": model["omega"],
            "gimbalsDegrees": model["gimbals"], "cdu": frame["cdu"],
            "control": frame["control"], "jets": frame["jets"],
            "originalReady": frame["ready"]}


def distance_degrees(quaternion, target):
    dot = sum(a*b for a, b in zip(quaternion, target))
    return math.degrees(2 * math.acos(min(1, abs(dot))))


def run_case(assets, output, name, control):
    yaw, pitch, hold_cycles = control
    session = native.NativeSession(assets, output=output / name)
    frames, commands = [], []
    try:
        startup = session.start()
        assert startup["ready"] and startup["cycle"] == native.READY_CYCLE
        frames.append(sample(startup))
        commands.append(session.command(yaw, pitch, duration_cycles=hold_cycles))
        while not session.closed:
            frame = session.advance(STEP_CYCLES)
            frames.append(sample(frame))
        summary = session.summary
        if session.status != "stopped" or not summary or not summary["status"].startswith("VERIFIED"):
            raise RuntimeError("Native session did not finish successfully: " + str(summary))
    finally:
        if not session.closed:
            session.stop("game calibration cleanup")
    angle = 2 if yaw and pitch else 3
    half_angle = math.radians(angle) / 2
    c, s = math.cos(half_angle), math.sin(half_angle)
    # Same target convention as the game: initial * qX(yaw) * qY(pitch).
    target = [c*c, s*c, c*s, s*s] if yaw and pitch else (
        [c, s, 0, 0] if yaw else [c, 0, s, 0])
    matching = []
    for frame in frames:
        error = distance_degrees(frame["quaternionWxyz"], target)
        rate = math.hypot(*frame["bodyRatesDegreesPerSecond"])
        if error <= 1 and rate <= 1:
            matching.append({"physicalTimeSeconds": frame["physicalTimeSeconds"],
                             "interactiveTimeSeconds": frame["physicalTimeSeconds"]-native.READY_CYCLE*native.PERIOD,
                             "targetErrorDegrees": error, "rateDegreesPerSecond": rate})
    return {"status": "VERIFIED fresh native execution", "input": {"yaw": yaw, "pitch": pitch,
            "durationCycles": hold_cycles, "durationSeconds": hold_cycles*native.PERIOD},
            "commands": commands, "nativeSummary": summary,
            "targetDiagnostic": {"targetYawDegrees": angle if yaw else 0,
                "targetPitchDegrees": angle if pitch else 0,
                "targetQuaternionWxyz": target,
                "thresholdDegrees": 1, "rateThresholdDegreesPerSecond": 1,
                "matchingSamples": matching,
                "minimumTargetErrorDegrees": min(distance_degrees(f["quaternionWxyz"], target) for f in frames)},
            "trace": {"path": str(session.output / "trace.jsonl"), "sha256": digest(session.output / "trace.jsonl")},
            "frames": frames}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", choices=list(CASES))
    parser.add_argument("--retain", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / ".build/game-ui/native" / (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    output = native.new_output("game-native", output)
    output.mkdir(parents=True)
    paths = [Path(__file__).resolve(), ROOT / "backend/native_session.py", ROOT / "backend/control_service.py",
             ROOT / "docs/phase7-evidence/integration/run_validation.py",
             ROOT / "docs/phase7-evidence/physics/orientation.tcl",
             ROOT / "tools/reproducibility/runtime-lock.json"]
    report = {"status": "INCOMPLETE", "startedUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Fresh authentic Luminary RHC input; synthetic bounded 3D attitude only; no descent or landing",
        "repositoryHead": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sourceHashes": {str(p.relative_to(ROOT)): digest(p) for p in paths},
        "readyCycle": native.READY_CYCLE, "endCycle": native.END_CYCLE,
        "cycleSeconds": native.PERIOD, "sampleStepCycles": STEP_CYCLES,
        "casePlan": CASES, "rawOutput": str(output), "cases": {}}
    try:
        assets = native.prepare_assets(output / "assets")
        report["provenance"] = assets["provenance"]
        for path in paths:
            snapshot = output / "executed-code" / path.relative_to(ROOT)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, snapshot)
        for name in args.case or CASES:
            report["cases"][name] = run_case(assets, output, name, CASES[name])
            write_json(output / "native-result.json", report)
            result = report["cases"][name]["targetDiagnostic"]
            print(name, json.dumps({k: v for k, v in result.items() if k != "matchingSamples"}),
                  "matching_samples=" + str(len(result["matchingSamples"])), flush=True)
        report.update(status="VERIFIED fresh native bounded executions",
                      completedUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        write_json(output / "native-result.json", report)
        if args.retain:
            args.retain.parent.mkdir(parents=True, exist_ok=True)
            if args.retain.exists():
                raise ValueError("Refusing to overwrite retained game evidence: " + str(args.retain))
            write_json(args.retain, report)
    print("Native game input calibration: " + str(output), flush=True)


if __name__ == "__main__":
    main()
