#!/usr/bin/env python3
"""GPL-2.0-or-later. Create a source-locked, bounded yaw model in scratch.

This modifies the modern external simulator, not Luminary or the emulator.
The numerical change is one exact X/yaw selector; the appended public wrapper
rejects unsupported axes before the original quantizer can change any state.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMU_RELATIVE = Path("Contributed/LM_Simulator/modules/AGC_IMU.tcl")
ORIGINAL_SHA256 = "4f63cf0954d4587ec6e983428d7e43d4473c11da72210444c2aa0ae4204e9c7e"
ORIGINAL_SELECTOR = "if {$Omega_Yaw < 4} {"
CORRECTED_SELECTOR = "if {abs($Omega_Yaw) < 4} {"
AXIS_GUARD = """
# Milestone 3 boundary: only yaw / X-gimbal motion is validated.
# The original procedure body above differs only in the X rate selector.
namespace eval ::milestone3_yaw {}
rename modify_gimbal_angle ::milestone3_yaw::upstream_modify_gimbal_angle
proc modify_gimbal_angle {dx dy dz} {
    if {$dy != 0 || $dz != 0} {
        return -code error -errorcode {APOLLO MILESTONE3 UNSUPPORTED_AXIS} \\
            {Milestone 3 supports yaw / X-gimbal increments only}
    }
    ::milestone3_yaw::upstream_modify_gimbal_angle $dx $dy $dz
}
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_destination(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing a symlink destination")
    resolved = path.resolve()
    if resolved.exists():
        raise ValueError("Refusing to replace an existing file")
    if resolved == ROOT or ROOT in resolved.parents:
        build = ROOT / ".build"
        if resolved == build or build not in resolved.parents:
            raise ValueError("Generated model requires .build or external scratch")
    return resolved


def apply_selector(source, destination):
    """Write one corrected+axis-bounded module and return its complete audit.

    ``source`` is the unchanged complete AGC_IMU.tcl or its extracted source
    root. ``destination`` must be a new scratch file. Nothing is sourced here;
    the caller sources the returned destination exactly once in fresh Tcl.
    """
    original = Path(source).resolve()
    if original.is_dir():
        original = original / IMU_RELATIVE
    destination = validate_destination(destination)
    raw = original.read_bytes()
    if sha256(raw) != ORIGINAL_SHA256:
        raise ValueError("Pinned complete AGC_IMU.tcl hash mismatch")
    text = raw.decode("utf-8")
    if text.count(ORIGINAL_SELECTOR) != 1:
        raise ValueError("Expected exactly one X/yaw selector")
    corrected = text.replace(ORIGINAL_SELECTOR, CORRECTED_SELECTOR, 1)
    bounded = corrected + AXIS_GUARD
    changed_line = next(index for index, line in enumerate(text.splitlines(), 1)
                        if ORIGINAL_SELECTOR in line)
    audit = {
        "revision": "f577e3fd917866c59334e6cdd32504f09df76f60",
        "source": str(original), "destination": str(destination),
        "original_sha256": ORIGINAL_SHA256,
        "selector_only_sha256": sha256(corrected.encode()),
        "bounded_module_sha256": sha256(bounded.encode()),
        "axis_guard_sha256": sha256(AXIS_GUARD.encode()),
        "selector_changed_line": changed_line,
        "original_selector": ORIGINAL_SELECTOR,
        "corrected_selector": CORRECTED_SELECTOR,
        "selector_replacements": 1,
        "numerical_change": "Use abs(Omega_Yaw) for the existing <4 degree/second rate-mode boundary",
        "boundary_change": "Public modify_gimbal_angle rejects nonzero dy/dz before invoking the upstream body",
        "selector_diff": "".join(difflib.unified_diff(text.splitlines(True), corrected.splitlines(True),
            fromfile="pinned/AGC_IMU.tcl", tofile="selector-corrected/AGC_IMU.tcl")),
        "complete_diff": "".join(difflib.unified_diff(text.splitlines(True), bounded.splitlines(True),
            fromfile="pinned/AGC_IMU.tcl", tofile="bounded-corrected/AGC_IMU.tcl")),
        "upstream_source_modified": False,
        "scope": "Modern external model only; yaw / X-gimbal; no AGC, emulator or other-axis numerical change",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(bounded.encode())
    if original.read_bytes() != raw:
        raise RuntimeError("Original source changed while creating derived model")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    audit_path = validate_destination(args.audit)
    if audit_path == args.destination.resolve():
        parser.error("Audit and model destinations must differ")
    audit = apply_selector(args.source, args.destination)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("x") as stream:
        stream.write(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
