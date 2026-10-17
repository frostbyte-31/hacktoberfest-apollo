#!/usr/bin/env python3
"""GPL-2.0-or-later. Paired yaw selector component validation using M2 probes."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
M2 = ROOT / "docs/milestone2-evidence/plant"
from fix_selector import apply_selector, IMU_RELATIVE, ORIGINAL_SHA256, AXIS_GUARD


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load_module("milestone3_retained_plant_probe", M2 / "run_validation.py")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def paired_validation(original, corrected):
    """Require numerical equivalence except intended negative FAST selection."""
    prior.validate_measurements(prior.summarize(prior.scenarios(), original))
    if len(original) != len(corrected):
        raise ValueError("Paired trace lengths differ")
    changed = 0
    for old, new in zip(original, corrected):
        if {k: v for k, v in old.items() if k != "packets"} != {
                k: v for k, v in new.items() if k != "packets"}:
            raise ValueError("Selector change altered component numerical state")
        if len(old["packets"]) != len(new["packets"]):
            raise ValueError("Selector change altered pulse count")
        for old_packet, new_packet in zip(old["packets"], new["packets"]):
            expected = dict(old_packet)
            if old["omega_yaw"] <= -4:
                expected["op"] += "_FAST"
                expected["code_decimal"] += 16
            if new_packet != expected:
                raise ValueError("Unexpected corrected packet or direction")
            changed += old_packet != new_packet
    summary = prior.summarize(prior.scenarios(), corrected)
    by_id = {row["id"]: row for row in summary}
    for magnitude in prior.RATE_MAGNITUDES:
        for sign in (1, -1):
            rate = magnitude * sign
            case = by_id["rate_" + str(rate)]
            op = ("P" if sign > 0 else "M") + "CDU" + ("_FAST" if magnitude >= 4 else "")
            if case["operations"] != {op: case["pulse_count"]}:
                raise ValueError("Corrected signed threshold selection is asymmetric")
    if by_id["opposite_delta_-8.0"]["operations"] != {"PCDU_FAST": 1}:
        raise ValueError("Direction depends on signed rate instead of angle residual")
    return {"status": "VERIFIED", "paired_scenarios": len(prior.scenarios()),
        "rows_per_model": len(original), "changed_packet_modes": changed,
        "equal_numerical_states": True, "equal_counts_and_directions": True,
        "scope": "Prescribed yaw/X motion component diagnostic, not AGC-controlled vehicle",
        "numerical_change": "abs(Omega_Yaw)<4 in X selector only",
        "limits": "No queue pacing, another axis, Phase7, powered descent or landing tested here"}


def guard_script(source, corrected):
    """Exercise public wrapper before original early-return/quantizer execution."""
    # Use Tcl argv paths rather than string-interpolating filenames into scripts.
    return """set src [lindex $argv 0]
set f [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set initialization [join [lrange [split [read $f] "\\n"] 123 240] "\\n"]
close $f
source [lindex $argv 1]
proc write_socket {op address} {global packets; lappend packets [list $op $address]}
foreach control {{Y 0.1 0.01 0 0 0} {Z 0.1 0 -0.01 0 0} {ZERO 0.1 0.01 0 1 0} {LOCKED 0.1 0 -0.01 0 1}} {
    eval $initialization
    lassign $control id dx dy dz zero locked
    set bo(12,5) $zero
    set gimbalLock $locked
    set packets {}
    set before [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE $PIMUX $PIMUY $PIMUZ $packets]
    set code [catch {modify_gimbal_angle $dx $dy $dz} message options]
    set after [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE $PIMUX $PIMUY $PIMUZ $packets]
    if {$code != 1 || [dict get $options -errorcode] ne {APOLLO MILESTONE3 UNSUPPORTED_AXIS} || $before ne $after} {
        error "Unsupported-axis guard failed for $id"
    }
    puts "$id\\t$code\\t[dict get $options -errorcode]\\tUNCHANGED"
}
puts {AXIS_GUARD_COMPLETE}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tcl", required=True, type=Path)
    parser.add_argument("--runtime-manifest", type=Path)
    args = parser.parse_args()
    output = prior.validate_output(args.output)
    output.mkdir(parents=True)
    commands = []
    try:
        runtime_module = prior.load_runtime_module()
        manifest_path = args.runtime_manifest or args.tcl.resolve().parent.parent.parent / "runtime-manifest.json"
        runtime = runtime_module.validate_runtime(manifest_path)
        if args.tcl.resolve() != Path(runtime["executable"]):
            raise ValueError("Tcl differs from validated runtime manifest")
        prior.capture_source_audit(args.source.resolve(), output)
        write_json(output / "environment.json", dict(runtime=runtime, python=sys.version,
            platform=platform.platform(), manifest=str(manifest_path.resolve())))
        corrected = output / "AGC_IMU.corrected-yaw.tcl"
        audit = apply_selector(args.source, corrected)
        write_json(output / "selector-audit.json", audit)
        (output / "selector.diff").write_text(audit["selector_diff"])
        (output / "complete.diff").write_text(audit["complete_diff"])
        prior_hashes = json.loads((HERE.parent / "prior_hashes.json").read_text())["sha256"]
        retained_probe = M2 / "probe.tcl"
        relative = str(retained_probe.relative_to(ROOT))
        if hashlib.sha256(retained_probe.read_bytes()).hexdigest() != prior_hashes[relative]:
            raise ValueError("Retained probe changed")
        original_probe_text = retained_probe.read_text()
        original_source = 'source "$src/Contributed/LM_Simulator/modules/AGC_IMU.tcl"'
        if original_probe_text.count(original_source) != 1:
            raise ValueError("Retained probe source hook changed")
        adapted_probe = output / "probe-with-module-argument.tcl"
        adapted_probe.write_text(original_probe_text.replace(original_source, "source [lindex $argv 1]", 1))
        (output / "probe-adapter.diff").write_text("".join(__import__("difflib").unified_diff(
            original_probe_text.splitlines(True), adapted_probe.read_text().splitlines(True),
            fromfile="retained-milestone2/probe.tcl", tofile="scratch/probe-with-module-argument.tcl")))
        cases = prior.scenarios()
        inputs = prior.input_text(cases)
        write_json(output / "scenarios.json", cases)
        (output / "probe-inputs.txt").write_text(inputs)
        env = runtime_module.clean_environment()

        def run(name, argv, stdin=None):
            start = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                result = subprocess.run(list(map(str, argv)), input=stdin, text=True,
                    capture_output=True, timeout=30, env=env, cwd=ROOT)
                code, stdout, stderr = result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired as error:
                code = "TIMEOUT"
                stdout, stderr = error.stdout or b"", error.stderr or b""
                stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
                stderr = stderr.decode() if isinstance(stderr, bytes) else stderr
            except OSError as error:
                code, stdout, stderr = "LAUNCH_ERROR", "", str(error) + "\n"
            (output / (name + ".stdout")).write_text(stdout)
            (output / (name + ".stderr")).write_text(stderr)
            commands.append(dict(argv=list(map(str, argv)), cwd=str(ROOT), label=name,
                start_utc=start, end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), exit=code,
                stdin="probe-inputs.txt" if stdin is not None else None,
                environment_overrides={"LC_ALL": "C", "LANG": "C", "TZ": "UTC"}))
            write_json(output / "commands.json", commands)
            if code != 0 or stderr:
                raise RuntimeError(f"{name} failed ({code}); inspect retained raw output")
            return stdout

        original_raw = run("original", [args.tcl, retained_probe, args.source], inputs)
        corrected_raw = run("corrected", [args.tcl, adapted_probe, args.source, corrected], inputs)
        original = prior.parse_output(original_raw, cases)
        changed = prior.parse_output(corrected_raw, cases)
        validation = paired_validation(original, changed)
        guard = output / "guard-probe.tcl"
        guard.write_text(guard_script(args.source, corrected))
        raw_guard = run("axis-guard", [args.tcl, guard, args.source, corrected])
        expected_guard = "".join(f"{name}\t1\tAPOLLO MILESTONE3 UNSUPPORTED_AXIS\tUNCHANGED\n"
                                  for name in ("Y", "Z", "ZERO", "LOCKED")) + "AXIS_GUARD_COMPLETE\n"
        if raw_guard != expected_guard:
            raise ValueError("Missing or incomplete unsupported-axis checks")
        validation["cross_axis_rejections_before_mutation"] = 4
        retained_raw = (M2 / "results/probe.stdout").read_text()
        validation["original_matches_retained_milestone2_bytes"] = original_raw == retained_raw
        if original_raw != retained_raw:
            raise ValueError("Original probe no longer matches retained M2 raw output")
        for name, rows in (("original", original), ("corrected", changed)):
            write_json(output / (name + ".summary.json"), prior.summarize(cases, rows))
            with (output / (name + ".jsonl")).open("w") as stream:
                for row in rows:
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
        write_json(output / "validation.json", validation)
        paths = [Path(__file__), HERE / "fix_selector.py", M2 / "probe.tcl", M2 / "run_validation.py",
                 M2 / "results/probe.stdout", corrected, adapted_probe, guard]
        write_json(output / "inputs_source_hashes.json", {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        print("VERIFIED 24 paired yaw-selector scenarios and 4 axis-boundary controls")
    except Exception as error:
        write_json(output / "failure.json", dict(status="FAILED or incomplete", error=str(error)))
        raise


if __name__ == "__main__":
    main()
