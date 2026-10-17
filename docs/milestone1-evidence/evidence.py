#!/usr/bin/env python3
"""Verify retained evidence without manufacturing missing historical records.

The baseline pins the bytes present at the audit commit.  The separate gap
inventory is checked against that pinned audit and the original manifests.
An unchanged historical gap is reported explicitly, never counted as a file
match.  A recovered record is accepted only at its original recorded hash.
This module intentionally provides no command to regenerate the baseline.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


SCHEMA_VERSION = 1
SCOPE = {
    "directories": [f"docs/phase{phase}-evidence" for phase in range(1, 7)]
    + ["docs/audit-evidence"],
    "files": [
        "AGENTS.md",
        "docs/PROJECT_STATE_AUDIT.md",
        "docs/PHASE1_PROOF_PLAN.md",
        "docs/PHASE2_POWERED_DESCENT_FEASIBILITY.md",
        "docs/PHASE3_CLOSED_LOOP_FEASIBILITY.md",
        "docs/PHASE4_CONTROL_PATH_VALIDATION.md",
        "docs/PHASE5_IMU_READINESS.md",
        "docs/PHASE6_DEMONSTRATION.md",
    ],
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_object)


def _relative(value):
    if not isinstance(value, str):
        raise ValueError("Evidence path must be a string")
    path = PurePosixPath(value)
    if (not value or value != str(path) or path.is_absolute()
            or ".." in path.parts or "\\" in value or value == "."):
        raise ValueError(f"Unsafe evidence path: {value!r}")
    return value


def _hash(value):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"Invalid SHA-256: {value!r}")
    return value


def _in_scope(path):
    return path in SCOPE["files"] or any(
        path.startswith(directory + "/") for directory in SCOPE["directories"]
    )


def _safe_path(root, relative):
    """Reject symlinks even when they resolve inside the repository."""
    relative = _relative(relative)
    path = root
    for component in PurePosixPath(relative).parts:
        path = path / component
        if path.is_symlink():
            raise ValueError(f"Symlink is not retained evidence: {relative}")
    return path


def _manifest_entries(path):
    if path.suffix == ".json":
        values = _read_json(path)
        if not isinstance(values, dict):
            raise ValueError(f"Manifest is not a path/hash object: {path}")
        return values
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", line)
        if match is None:
            raise ValueError(f"Unparseable manifest line in {path}: {line!r}")
        digest, recorded = match.groups()
        if recorded in values:
            raise ValueError(f"Duplicate manifest path in {path}: {recorded}")
        values[recorded] = digest
    return values


def _audit_gaps(audit):
    """Derive the allowlist anew; the inventory cannot silently add exceptions."""
    gaps = {}
    for manifest in audit["manifests"]:
        for entry in manifest["entries"]:
            if entry["status"] != "missing":
                continue
            relative = _relative(entry["resolved_path"])
            expected = _hash(entry["expected_sha256"])
            previous = gaps.setdefault(relative, {
                "path": relative, "expected_sha256": expected,
                "manifest_references": [],
            })
            if previous["expected_sha256"] != expected:
                raise ValueError(f"Conflicting historical hashes: {relative}")
            previous["manifest_references"].append({
                "path": _relative(manifest["path"]),
                "recorded_path": _relative(entry["recorded_path"]),
                "expected_sha256": expected,
                "scope": manifest["scope"],
            })
    return [gaps[path] for path in sorted(gaps)]


def _validate_metadata(root, baseline, inventory, missing_path):
    if not isinstance(baseline, dict) or not isinstance(inventory, dict):
        raise ValueError("Integrity metadata must contain JSON objects")
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported baseline schema_version")
    if baseline.get("scope") != SCOPE:
        raise ValueError("Baseline retained scope differs from verifier scope")
    files = baseline.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Baseline must contain a nonempty files object")
    for relative, expected in files.items():
        if not _in_scope(_relative(relative)):
            raise ValueError(f"Baseline file outside retained scope: {relative}")
        _hash(expected)
    if sha256(missing_path) != _hash(baseline["missing_inventory_sha256"]):
        raise ValueError("Historical gap inventory differs from pinned hash")
    if inventory.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported missing inventory schema_version")
    audit_reference = inventory["audit_inventory"]
    audit_relative = _relative(audit_reference["path"])
    expected = _hash(audit_reference["sha256"])
    if files.get(audit_relative) != expected:
        raise ValueError("Historical inventory audit is not pinned in baseline")
    audit_path = _safe_path(root, audit_relative)
    if sha256(audit_path) != expected:
        raise ValueError("Historical source audit differs from pinned hash")
    entries = inventory.get("entries")
    if entries != _audit_gaps(_read_json(audit_path)):
        raise ValueError("Historical gap inventory differs from source audit")
    parsed = {}
    for entry in entries:
        relative = entry["path"]
        if not _in_scope(relative) or relative in files:
            raise ValueError(f"Historical gap overlaps or escapes baseline: {relative}")
        for reference in entry["manifest_references"]:
            manifest = reference["path"]
            if manifest not in files:
                raise ValueError(f"Historical manifest not pinned: {manifest}")
            path = _safe_path(root, manifest)
            if sha256(path) != files[manifest]:
                raise ValueError(f"Historical manifest changed: {manifest}")
            if manifest not in parsed:
                parsed[manifest] = _manifest_entries(path)
            recorded = reference["recorded_path"]
            if parsed[manifest].get(recorded) != entry["expected_sha256"]:
                raise ValueError(f"Historical hash absent from manifest: {manifest}: {recorded}")
            scope = reference["scope"]
            if scope == "repository":
                resolved = recorded
            elif scope == "phase-local":
                resolved = str(PurePosixPath(manifest).parent / recorded)
            else:
                raise ValueError(f"Unsupported historical reference scope: {scope}")
            if resolved != relative:
                raise ValueError(f"Historical manifest resolves to wrong path: {relative}")
    return files, entries


def _inventory_paths(root):
    observed = set()
    for relative in SCOPE["files"]:
        path = root / relative
        if path.exists() or path.is_symlink():
            observed.add(relative)
    for relative in SCOPE["directories"]:
        directory = root / relative
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            observed.add(relative)
            continue
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_symlink() or not path.is_dir():
                    observed.add(path.relative_to(root).as_posix())
    return observed


def verify(root, baseline_path=None, missing_path=None):
    """Return JSON-compatible inspection; ``ok`` permits only documented gaps.

    Historical completeness remains false while any allowlisted record is
    absent.  This does not run or reclassify any legacy preservation test.
    """
    root = Path(root).resolve()
    baseline_path = Path(baseline_path) if baseline_path is not None else root / "docs/milestone1-evidence/baseline.json"
    missing_path = Path(missing_path) if missing_path is not None else root / "docs/milestone1-evidence/missing-historical.json"
    report = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "historical_evidence_complete": False,
        "files": [],
        "errors": [],
    }
    try:
        baseline = _read_json(baseline_path)
        inventory = _read_json(missing_path)
        files, gaps = _validate_metadata(root, baseline, inventory, missing_path)
        observed = _inventory_paths(root)
        known = set(files)
        for relative, expected in sorted(files.items()):
            record = {"path": relative, "expected_sha256": expected}
            try:
                path = _safe_path(root, relative)
                if not path.exists():
                    record["status"] = "missing"
                elif not path.is_file():
                    record["status"] = "unsafe"
                else:
                    record["actual_sha256"] = sha256(path)
                    record["status"] = "match" if record["actual_sha256"] == expected else "mismatch"
            except (OSError, ValueError) as error:
                record.update(status="unsafe", error=str(error))
            report["files"].append(record)
        for entry in gaps:
            relative, expected = entry["path"], entry["expected_sha256"]
            known.add(relative)
            record = {"path": relative, "expected_sha256": expected}
            try:
                path = _safe_path(root, relative)
                if not path.exists():
                    record["status"] = "historical_missing"
                elif not path.is_file():
                    record["status"] = "unsafe"
                else:
                    record["actual_sha256"] = sha256(path)
                    record["status"] = "historical_recovered" if record["actual_sha256"] == expected else "historical_mismatch"
            except (OSError, ValueError) as error:
                record.update(status="unsafe", error=str(error))
            report["files"].append(record)
        for relative in sorted(observed - known):
            report["files"].append({"path": relative, "status": "unlisted"})
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append(str(error))
    statuses = ("match", "missing", "mismatch", "unsafe", "unlisted",
                "historical_missing", "historical_recovered", "historical_mismatch")
    report["summary"] = {
        status: sum(record["status"] == status for record in report["files"])
        for status in statuses
    }
    failures = ("missing", "mismatch", "unsafe", "unlisted", "historical_mismatch")
    report["ok"] = not report["errors"] and not any(report["summary"][status] for status in failures)
    report["historical_evidence_complete"] = report["ok"] and not report["summary"]["historical_missing"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--missing", type=Path)
    parser.add_argument("--output", type=Path, help="Also save the JSON report outside retained evidence")
    args = parser.parse_args(argv)
    report = verify(args.root, args.baseline, args.missing)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        try:
            destination = args.output.resolve()
            relative = destination.relative_to(args.root.resolve()).as_posix() if destination.is_relative_to(args.root.resolve()) else None
            metadata = [args.baseline or args.root / "docs/milestone1-evidence/baseline.json",
                        args.missing or args.root / "docs/milestone1-evidence/missing-historical.json"]
            if ((relative is not None and _in_scope(relative))
                    or any(destination == path.resolve() for path in metadata)):
                raise ValueError("Refusing to overwrite retained evidence or integrity metadata")
            destination.write_text(encoded, encoding="utf-8")
        except (OSError, ValueError) as error:
            print(f"Cannot write report: {error}", file=sys.stderr)
            return 2
    sys.stdout.write(encoded)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
