#!/usr/bin/env python3
"""GPL-2.0-or-later. Source-locked external-model overlay; no AGC changes."""
from pathlib import Path
import hashlib
import difflib
import json
import argparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMU = "Contributed/LM_Simulator/modules/AGC_IMU.tcl"
MODEL = "Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
SERVER = ROOT / "docs/phase5-evidence/plant_server.tcl"
REPLACEMENTS = (("if {$Omega_Yaw < 4} {", "if {abs($Omega_Yaw) < 4} {"),
                ("if {$Omega_Pitch < 4.0} {", "if {abs($Omega_Pitch) < 4.0} {"),
                ("if {$Omega_Roll < 4.0} {", "if {abs($Omega_Roll) < 4.0} {"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_scratch(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Destination must not be a symlink")
    path = path.resolve()
    if path.exists():
        raise ValueError("Destination exists")
    if path == ROOT or (ROOT in path.parents and ROOT / ".build" not in path.parents):
        raise ValueError("Derived physics requires .build or external scratch")
    return path


def apply_physics(source, destination):
    source, destination = Path(source).resolve(), new_scratch(destination)
    expected = json.loads((ROOT / "docs/phase6-evidence/corresponding-source-hashes.json").read_text())
    for name in (IMU, MODEL, "Contributed/LM_Simulator/lm_simulator.tcl"):
        if digest(source / name) != expected[name]:
            raise ValueError("Pinned original source mismatch: " + name)
    prior = json.loads((HERE.parent / "prior_hashes.json").read_text())["sha256"]
    if digest(SERVER) != prior[SERVER.relative_to(ROOT).as_posix()]:
        raise ValueError("Retained plant server changed")
    original = (source / IMU).read_text()
    corrected = original
    for before, after in REPLACEMENTS:
        if corrected.count(before) != 1:
            raise ValueError("Unexpected signed selector count")
        corrected = corrected.replace(before, after, 1)
    server = SERVER.read_text()
    start = server.index(" set j 0\n foreach name")
    end = server.index(" set Delta_Time2 0", start)
    decode = server[start:end]
    overlay = (HERE / "orientation.tcl").read_text()
    if overlay.count("@LEGACY_JET_DECODE@") != 1:
        raise ValueError("Missing exact decode insertion")
    overlay = overlay.replace("@LEGACY_JET_DECODE@", decode.rstrip(), 1)
    derived = corrected + "\n" + overlay
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        stream.write(derived)
    return {"status": "DERIVED", "source_revision": "f577e3fd917866c59334e6cdd32504f09df76f60",
        "source_hashes": {name: expected[name] for name in (IMU, MODEL, "Contributed/LM_Simulator/lm_simulator.tcl")},
        "retained_server_sha256": digest(SERVER), "overlay_sha256": digest(HERE / "orientation.tcl"),
        "destination": str(destination), "derived_sha256": digest(destination),
        "selector_replacements": REPLACEMENTS, "exact_legacy_decode": decode,
        "imu_diff": "".join(difflib.unified_diff(original.splitlines(True), corrected.splitlines(True),
            fromfile="pinned/AGC_IMU.tcl", tofile="phase7/AGC_IMU.tcl")),
        "upstream_modified": False,
        "assumptions": "Synthetic effective perjet torque components445Nm (1m assumed component arm); I(m)=445/legacyAlphaRad; perinterval frozen I and corotating expelled-mass angular-momentum flux cancels I_dot*omega"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    args.audit = new_scratch(args.audit)
    if args.audit == args.destination.resolve():
        parser.error("Audit and model must differ")
    audit = apply_physics(args.source, args.destination)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2) + "\n")


if __name__ == "__main__":
    main()
