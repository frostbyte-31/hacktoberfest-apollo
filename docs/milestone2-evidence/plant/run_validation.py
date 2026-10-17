#!/usr/bin/env python3
"""GPL-2.0-or-later. Characterize signed yaw/X CDU quantization, without edits.

Uses the retained Tcl plant procedures. Prescribed motion is a component
diagnostic, not an AGC-controlled spacecraft or a multi-axis experiment.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INITIALIZER = "Contributed/LM_Simulator/lm_simulator.tcl"
IMU = "Contributed/LM_Simulator/modules/AGC_IMU.tcl"
MODEL = "Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
INCREMENT = 360.0 / 32768.0
DT = 853 * 0.00001172
RATE_MAGNITUDES = (1.0, 3.999, 4.0, 4.001, 8.0)


def load_runtime_module():
    spec = importlib.util.spec_from_file_location(
        "plant_runtime", ROOT / "tools/reproducibility/bootstrap_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def validate_output(output):
    resolved = output.resolve()
    if resolved.exists():
        raise ValueError("Output exists; use a new directory")
    if resolved == ROOT or ROOT in resolved.parents:
        build = ROOT / ".build"
        if resolved == build or build not in resolved.parents:
            raise ValueError("Generated results require .build or external scratch")
    return resolved


def scenarios():
    rows = []
    for magnitude in RATE_MAGNITUDES:
        for sign in (1, -1):
            rate = magnitude * sign
            rows.append(dict(id="rate_" + str(rate), mode="rate", rate=rate,
                dt=DT, steps=100, dx=0.0, initial_x=0.0, zero=0, locked=0))
    for sign in (1, -1):
        for multiple in (0.999, 1.0, 1.001, 2.0):
            rows.append(dict(id=f"quant_{sign}_{multiple}", mode="delta", rate=sign,
                dt=DT, steps=1, dx=sign * multiple * INCREMENT,
                initial_x=0.0, zero=0, locked=0))
    # Separates motion direction from rate-mode selection.
    for rate, dx in ((8.0, -2 * INCREMENT), (-8.0, 2 * INCREMENT)):
        rows.append(dict(id=f"opposite_delta_{rate}", mode="delta", rate=rate,
            dt=DT, steps=1, dx=dx, initial_x=0.0, zero=0, locked=0))
    for name, initial_x, dx in (("wrap_positive", 359.99, 0.03),
                                 ("wrap_negative", 0.01, -0.03)):
        rows.append(dict(id=name, mode="delta", rate=1.0 if dx > 0 else -1.0,
            dt=DT, steps=1, dx=dx, initial_x=initial_x, zero=0, locked=0))
    for field in ("zero", "locked"):
        rows.append(dict(id="inhibit_" + field, mode="delta", rate=8.0,
            dt=DT, steps=1, dx=1.0, initial_x=0.0,
            zero=int(field == "zero"), locked=int(field == "locked")))
    return rows


def input_text(cases):
    fields = ("id", "mode", "rate", "dt", "steps", "dx", "initial_x", "zero", "locked")
    return "".join(" ".join(str(case[key]) for key in fields) + "\n" for case in cases)


def parse_output(raw, cases):
    lines = raw.splitlines()
    if not lines or lines[0] != "TCL\t8.6.16" or lines[-1] != "COMPONENT_PROBE_COMPLETE":
        raise ValueError("Tcl version/completion marker missing")
    expected = {(case["id"], step) for case in cases for step in range(1, case["steps"] + 1)}
    rows = []
    for line in lines[1:-1]:
        values = line.split("\t")
        if len(values) != 12:
            raise ValueError("Malformed probe row")
        key = (values[0], int(values[1]))
        if key not in expected:
            raise ValueError("Unexpected or duplicate probe step")
        expected.remove(key)
        numbers = list(map(float, values[2:11]))
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("Nonfinite probe state")
        if any(numbers[index] != 0 for index in (4, 5, 6, 7)):
            raise ValueError("Unsupported cross-axis motion")
        packets = []
        if values[11]:
            for operation in values[11].split(";"):
                op, octal_address = operation.split(",")
                if op not in ("PCDU", "MCDU", "PCDU_FAST", "MCDU_FAST") or octal_address != "32":
                    raise ValueError("Unsupported operation or cross-axis feedback")
                packets.append({"op": op, "counter_octal": octal_address,
                    "code_decimal": {"PCDU": 1, "MCDU": 3, "PCDU_FAST": 17, "MCDU_FAST": 19}[op]})
        rows.append(dict(id=key[0], step=key[1], seconds=numbers[0], omega_yaw=numbers[1],
            imu_x_deg=numbers[2], fed_x_deg=numbers[3], imu_y_deg=numbers[4],
            imu_z_deg=numbers[5], omega_pitch=numbers[6], omega_roll=numbers[7],
            increment_deg=numbers[8], packets=packets))
    if expected:
        raise ValueError("Probe output incomplete")
    return rows


def summarize(cases, rows):
    result = []
    for case in cases:
        trace = [row for row in rows if row["id"] == case["id"]]
        packets = [packet for row in trace for packet in row["packets"]]
        operations = {}
        for packet in packets:
            operations[packet["op"]] = operations.get(packet["op"], 0) + 1
        result.append(dict(**case, duration_seconds=case["steps"] * case["dt"],
            pulse_count=len(packets), operations=operations,
            final_imu_x_deg=trace[-1]["imu_x_deg"], final_fed_x_deg=trace[-1]["fed_x_deg"],
            pulse_count_per_second=len(packets)/(case["steps"] * case["dt"])))
    return result


def validate_measurements(summary):
    by_id = {row["id"]: row for row in summary}
    for magnitude in RATE_MAGNITUDES:
        positive = by_id["rate_" + str(magnitude)]
        negative = by_id["rate_" + str(-magnitude)]
        if positive["pulse_count"] != negative["pulse_count"]:
            raise ValueError("Unequal signed pulse counts in matched component probes")
        for case in (positive, negative):
            ideal_count = abs(case["rate"]) * case["duration_seconds"] / INCREMENT
            if not ideal_count - 1.000001 <= case["pulse_count"] <= ideal_count + 0.000001:
                raise ValueError("Quantization differs by more than one pulse")
            expected_op = ("P" if case["rate"] > 0 else "M") + "CDU"
            if case["rate"] >= 4.0:
                expected_op += "_FAST"
            if case["operations"] != {expected_op: case["pulse_count"]}:
                raise ValueError("Source selector differs from measured output")
    for sign in (1, -1):
        for multiple, expected_count in ((0.999, 0), (1.0, 0), (1.001, 1), (2.0, 1)):
            if by_id[f"quant_{sign}_{multiple}"]["pulse_count"] != expected_count:
                raise ValueError("Strict quantization boundary changed")
    if by_id["opposite_delta_8.0"]["operations"] != {"MCDU_FAST": 1}:
        raise ValueError("Gimbal delta did not determine decrement direction")
    if by_id["opposite_delta_-8.0"]["operations"] != {"PCDU": 1}:
        raise ValueError("Gimbal delta did not determine increment direction")
    for name in ("inhibit_zero", "inhibit_locked"):
        if by_id[name]["pulse_count"] != 0 or by_id[name]["final_imu_x_deg"] != 0:
            raise ValueError("Readiness-related model inhibit was bypassed")
    for name, op in (("wrap_positive", "PCDU"), ("wrap_negative", "MCDU")):
        case = by_id[name]
        if case["operations"] != {op: 2} or not 0 <= case["final_imu_x_deg"] < 360:
            raise ValueError("Signed wraparound did not preserve short rotation")


def capture_source_audit(source, output):
    expected = json.loads((ROOT / "docs/phase6-evidence/corresponding-source-hashes.json").read_text())
    audit = []
    ranges = {INITIALIZER: ((124, 147), (710, 755)), IMU: ((496, 541), (652, 692)),
              MODEL: ((208, 215), (290, 303))}
    for name in (INITIALIZER, IMU, MODEL):
        path = source / name
        actual = digest(path)
        if actual != expected[name]:
            raise ValueError("Pinned source hash mismatch: " + name)
        lines = path.read_text().splitlines()
        for start, end in ranges[name]:
            audit.append(dict(source=name, sha256=actual, start_line=start, end_line=end,
                lines=[dict(line=index, text=lines[index - 1]) for index in range(start, end + 1)]))
    write_json(output / "source-audit.json", dict(
        revision="f577e3fd917866c59334e6cdd32504f09df76f60",
        expected_hashes="docs/phase6-evidence/corresponding-source-hashes.json", excerpts=audit))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tcl", type=Path, required=True)
    args = parser.parse_args()
    output = validate_output(args.output)
    output.mkdir(parents=True)
    try:
        runtime_module = load_runtime_module()
        runtime = runtime_module.validate_runtime(args.tcl.resolve().parent.parent.parent / "runtime-manifest.json")
        if args.tcl.resolve() != Path(runtime["executable"]):
            raise ValueError("Tcl executable differs from validated runtime manifest")
        write_json(output / "environment.json", dict(python=sys.version, platform=platform.platform(),
            runtime_manifest=runtime, scope="Imposed-motion yaw/X component diagnostic; no AGC process"))
        capture_source_audit(args.source.resolve(), output)
        cases = scenarios()
        write_json(output / "scenarios.json", cases)
        inputs = input_text(cases)
        (output / "probe-inputs.txt").write_text(inputs)
        command = [str(args.tcl.resolve()), str(HERE / "probe.tcl"), str(args.source.resolve())]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        env = runtime_module.clean_environment()
        completed = subprocess.run(command, input=inputs, text=True, capture_output=True, timeout=30, env=env)
        (output / "probe.stdout").write_text(completed.stdout)
        (output / "probe.stderr").write_text(completed.stderr)
        write_json(output / "commands.json", [dict(argv=command, cwd=str(ROOT), start_utc=started,
            end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), exit=completed.returncode,
            stdin="probe-inputs.txt", environment_overrides={"LC_ALL": "C", "LANG": "C", "TZ": "UTC"})])
        if completed.returncode != 0 or completed.stderr:
            raise RuntimeError("Tcl component probe failed; inspect captured process output")
        rows = parse_output(completed.stdout, cases)
        with (output / "raw-trace.jsonl").open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
        summary = summarize(cases, rows)
        write_json(output / "summary.json", summary)
        validate_measurements(summary)
        write_json(output / "validation.json", dict(status="VERIFIED", scenarios=len(cases),
            trace_rows=len(rows), axis="Yaw / X gimbal only", imposed_motion=True,
            quantization_deg=INCREMENT, coupling_seconds=DT,
            finding="Signed rate selector uses Omega_Yaw < 4, not speed magnitude. At -8 deg/s pulses are slow; at +8 fast.",
            upstream_changed=False,
            limitations=["No AGC execution or FIFO pacing measured by this component probe.",
                "GUI wallclock socket loop is not run; retained cycle-coupled wrapper sets Delta_Time2 explicitly.",
                "No multi-axis control, powered descent or landing tested."]))
        print(f"VERIFIED {len(cases)} single-axis imposed-motion component scenarios")
    except Exception as error:
        write_json(output / "failure.json", dict(status="FAILED", error=str(error)))
        raise


if __name__ == "__main__":
    main()
