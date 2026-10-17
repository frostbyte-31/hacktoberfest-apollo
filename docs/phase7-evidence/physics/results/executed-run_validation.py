#!/usr/bin/env python3
"""GPL-2.0-or-later. Execute bounded physics/coordinate component experiments."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
from apply_physics import apply_physics, digest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime_api = load("phase7_physics_runtime", ROOT / "tools/reproducibility/bootstrap_runtime.py")
reproduction = load("phase7_physics_reproduction", ROOT / "docs/milestone1-evidence/reproduce.py")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def numbers(text):
    result = list(map(float, text.split()))
    if not all(math.isfinite(x) for x in result):
        raise ValueError("Nonfinite physics component result")
    return result


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def matrix_product(a, b):
    return [sum(a[3*r+k]*b[3*k+c] for k in range(3)) for r in range(3) for c in range(3)]


def rotation_oracle(angles):
    o, i, m = map(math.radians, angles)
    rx = [1, 0, 0, 0, math.cos(o), -math.sin(o), 0, math.sin(o), math.cos(o)]
    ry = [math.cos(i), 0, math.sin(i), 0, 1, 0, -math.sin(i), 0, math.cos(i)]
    rz = [math.cos(m), -math.sin(m), 0, math.sin(m), math.cos(m), 0, 0, 0, 1]
    return matrix_product(matrix_product(ry, rz), rx)


def angle_error(a, b):
    return abs((a-b+180) % 360 - 180)


def analyze(raw, legacy_raw):
    lines = raw.splitlines()
    if lines[0] != "TCL|8.6.16" or lines[-1] != "PHASE7_PHYSICS_COMPONENT_COMPLETE":
        raise ValueError("Missing physics execution/version markers")
    groups = {}
    for line in lines[1:-1]:
        fields = line.split("|")
        groups.setdefault(fields[0], []).append(fields[1:])
    checks = {}
    maximum_roundtrip = maximum_matrix_error = maximum_orthogonality = 0.0
    for angles, recovered, q, matrix in groups["roundtrip"]:
        angles, recovered, q, matrix = map(numbers, (angles, recovered, q, matrix))
        maximum_roundtrip = max(maximum_roundtrip, *(angle_error(a, b) for a, b in zip(angles, recovered)))
        expected = rotation_oracle(angles)
        maximum_matrix_error = max(maximum_matrix_error, *(abs(a-b) for a, b in zip(matrix, expected)))
        if abs(dot(q, q)-1) > 1e-13:
            raise ValueError("Quaternion norm not preserved")
        for r in range(3):
            for c in range(3):
                maximum_orthogonality = max(maximum_orthogonality,
                    abs(dot(matrix[3*r:3*r+3], matrix[3*c:3*c+3]) - int(r == c)))
    checks["source_convention_roundtrips"] = len(groups["roundtrip"]) == 8 and maximum_roundtrip < 1e-10 and maximum_matrix_error < 1e-13 and maximum_orthogonality < 1e-13
    jacobian_error = max(angle_error(a, b) for _, old, modern in groups["jacobian"] for a, b in zip(numbers(old), numbers(modern)))
    checks["original_gimbal_jacobian_agrees_locally"] = len(groups["jacobian"]) == 3 and jacobian_error < 1e-10
    omega, quat, _ = map(numbers, groups["constant_torque"][0])
    expected_angle = 0.2 * 0.001**2 * 1000*1001/2
    checks["constant_principal_torque"] = abs(omega[0] - 0.2) < 1e-12 and omega[1:] == [0, 0] and abs(quat[0]-math.cos(expected_angle/2)) < 1e-12 and abs(quat[1]-math.sin(expected_angle/2)) < 1e-12
    free = []
    initial = [.2, .3, .4]
    inertia = [2, 3, 4]
    initial_momentum = [x*y for x, y in zip(initial, inertia)]
    initial_energy = sum(i*w*w for i, w in zip(inertia, initial))/2
    for dt, omega, quat, matrix in groups["free"]:
        omega, quat, matrix = map(numbers, (omega, quat, matrix))
        momentum = [i*w for i, w in zip(inertia, omega)]
        inertial = [dot(matrix[3*r:3*r+3], momentum) for r in range(3)]
        energy_error = abs(sum(i*w*w for i, w in zip(inertia, omega))/2-initial_energy)
        momentum_norm_error = abs(dot(momentum, momentum)-dot(initial_momentum, initial_momentum))
        direction_error = math.sqrt(sum((a-b)**2 for a, b in zip(inertial, initial_momentum)))/math.sqrt(dot(initial_momentum, initial_momentum))
        free.append(dict(dt=float(dt), energy_absolute_error=energy_error,
            momentum_norm_squared_error=momentum_norm_error, inertial_momentum_relative_error=direction_error,
            quaternion_norm_error=abs(dot(quat, quat)-1)))
    checks["torque_free_body_energy_and_momentum_norm"] = all(r["energy_absolute_error"] < 1e-10 and r["momentum_norm_squared_error"] < 1e-10 and r["quaternion_norm_error"] < 1e-13 for r in free)
    checks["first_order_inertial_momentum_convergence"] = free[1]["inertial_momentum_relative_error"] < .001 and .45 < free[1]["inertial_momentum_relative_error"]/free[0]["inertial_momentum_relative_error"] < .55
    vehicles = {}
    for name, step, values, before, after, mass_before, mass_after in groups["vehicle"]:
        values, before, after = map(numbers, (values, before, after))
        if len(values) != 16 or any(i <= 0 for i in before+after):
            raise ValueError("Invalid physics telemetry dimensions/inertia")
        vehicles.setdefault(name, []).append(dict(step=int(step), values=values, inertia_before=before,
            inertia_after=after, mass_before=float(mass_before), mass_after=float(mass_after)))
    checks["retained_jet_torque_and_mass"] = all(row["mass_after"] < row["mass_before"] for rows in vehicles.values() for row in rows) and abs(vehicles["yaw"][0]["values"][13]-1780) < 1e-8 and abs(vehicles["pitch"][0]["values"][14]-1780) < 1e-8
    coupled = vehicles["coupled"][-1]["values"]
    checks["two_torques_generate_coupled_third_rate"] = coupled[0] > 0 and coupled[1] > 0 and abs(coupled[2]) > 1e-6 and abs(coupled[5]) > 1e-6 and abs(coupled[15]) < 1e-8
    for name in ("yaw", "pitch"):
        positive = vehicles[name][-1]["values"]
        negative = vehicles[name+"_negative"][-1]["values"]
        axis = 0 if name == "yaw" else 1
        if abs(positive[axis]+negative[axis]) > 1e-10:
            raise ValueError("Principal-axis signed response mismatch")
    checks["principal_signed_rate_symmetry"] = True
    packet_groups = dict(groups["packets"])
    for name, counter in (("yaw", "32"), ("pitch", "33"), ("yaw_negative", "32"), ("pitch_negative", "33")):
        direction = "MCDU" if name.endswith("negative") else "PCDU"
        if not re.fullmatch(r"(?:\{" + direction + r"(?:_FAST)? " + counter + r"\} ?)+", packet_groups[name]):
            raise ValueError("Principal-axis physical response produced wrong signed sensor counter")
        if direction + "_FAST " + counter not in packet_groups[name]:
            raise ValueError("Principal-axis rate never exercised matching fast sensor mode")
    checks["principal_signed_sensor_counters"] = True
    legacy = numbers(legacy_raw.splitlines()[-1].split("|")[0])
    modern = vehicles["yaw"][-1]["values"][:6]
    legacy_difference = max(abs(a-b) for a, b in zip(legacy[:3], modern[:3]))
    legacy_angle_error = max(angle_error(a, b) for a, b in zip(legacy[3:], modern[3:]))
    checks["yaw_retains_legacy_response_below_one_quantum"] = legacy_difference < 1e-9 and legacy_angle_error < 360/32768
    translation = groups["translation"][0]
    checks["translation_explicitly_suppressed_without_pipa"] = bool(translation[1]) and not translation[2] and numbers(translation[3]) == [0, 0, 0]
    for rate, counter, packets in groups["selector"]:
        if not re.fullmatch(r"(?:\{PCDU_FAST " + counter + r"\} ?)+", packets):
            raise ValueError("Magnitude selector failed on derived gimbal counter")
    checks["three_signed_magnitude_selectors"] = len(groups["selector"]) == 6
    rejections = {name: message for name, message in groups["rejection"]}
    checks["bounded_unsupported_cases_rejected"] = len(rejections) == 5 and "20 iterations" in rejections["nonconvergence"]
    if not all(checks.values()):
        raise ValueError("Physics checks failed: " + str([name for name, passed in checks.items() if not passed]))
    return dict(status="VERIFIED", checks=checks, roundtrip_max_deg=maximum_roundtrip,
        rotation_matrix_max_error=maximum_matrix_error, orthogonality_max_error=maximum_orthogonality,
        original_jacobian_max_deg=jacobian_error, torque_free=free, vehicles=vehicles,
        yaw_legacy_max_rate_difference_deg_s=legacy_difference, yaw_legacy_max_angle_difference_deg=legacy_angle_error,
        rejected_cases=rejections, scope="Component mechanics and sensor-coordinate checks; no AGC-controlled multi-axis claim")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tcl", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path)
    args = parser.parse_args()
    source, tcl = args.source.resolve(), args.tcl.resolve()
    output = reproduction.validate_output(args.output)
    output.mkdir(parents=True)
    commands = []
    try:
        manifest_path = args.runtime_manifest or tcl.parent.parent.parent / "runtime-manifest.json"
        runtime = runtime_api.validate_runtime(manifest_path)
        if tcl != Path(runtime["executable"]):
            raise ValueError("Tcl differs from validated runtime")
        overlay = output / "derived-physics.tcl"
        audit = apply_physics(source, overlay)
        write_json(output / "source-audit.json", audit)
        write_json(output / "environment.json", dict(runtime=runtime, python=sys.version))
        source_paths = (Path(__file__), HERE / "orientation.tcl", HERE / "apply_physics.py", HERE / "probe.tcl", overlay)
        write_json(output / "inputs_source_hashes.json", {str(p): digest(p) for p in source_paths})
        for path in source_paths[:-1]:
            (output / ("executed-" + path.name)).write_bytes(path.read_bytes())
        (output / "imu-selectors.diff").write_text(audit["imu_diff"])
        inputs = "0.01 0 85 0 0\n" * 100
        (output / "legacy-inputs.txt").write_text(inputs)
        def run(label, argv, stdin=None):
            start = datetime.datetime.now(datetime.timezone.utc).isoformat()
            completed = subprocess.run(list(map(str, argv)), input=stdin, text=True, capture_output=True,
                timeout=60, cwd=ROOT, env=runtime_api.clean_environment())
            (output / (label + ".stdout")).write_text(completed.stdout)
            (output / (label + ".stderr")).write_text(completed.stderr)
            commands.append(dict(argv=list(map(str, argv)), cwd=str(ROOT), start_utc=start,
                end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), exit=completed.returncode,
                stdin="legacy-inputs.txt" if stdin is not None else None))
            write_json(output / "commands.json", commands)
            if completed.returncode or completed.stderr:
                raise RuntimeError("Component process failed: " + label)
            return completed.stdout
        raw = run("physics", [tcl, HERE / "probe.tcl", source, overlay])
        legacy = run("legacy-yaw", [tcl, ROOT / "docs/phase5-evidence/plant_server.tcl", source], inputs)
        write_json(output / "validation.json", analyze(raw, legacy))
        print("VERIFIED source-locked rotational component checks")
    except Exception as error:
        write_json(output / "failure.json", dict(status="FAILED or incomplete", error=str(error)))
        raise


if __name__ == "__main__":
    main()
