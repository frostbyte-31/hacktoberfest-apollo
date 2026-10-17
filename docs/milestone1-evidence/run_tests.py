#!/usr/bin/env python3
"""Run unchanged evidence suites; retain actual errors and classify known gaps.

An accepted run is not a claim that the original 38 tests passed. Three original
preservation checks currently error on an absent historical log. Only that exact
exception, test identity, source frame and inventoried path may be classified as
a historical gap. All other failures, errors, skips and process failures fail
this runner. Original unittest output and every test outcome are retained.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUITES = {
    "phase2": ("docs/phase2-evidence", "test_validation.py", 2),
    "phase3": ("docs/phase3-evidence", "test_loop.py", 7),
    "phase4": ("docs/phase4-evidence", "test_control_path.py", 6),
    "phase5": ("docs/phase5-evidence", "test_readiness.py", 12),
    "phase6": ("docs/phase6-evidence", "test_demonstration.py", 11),
    "milestone1": ("docs/milestone1-evidence/tests", "test_*.py", None),
}
KNOWN_GAP_TESTS = {
    "test_control_path.ControlEvidence.test_prior_evidence_preserved":
        "docs/phase4-evidence/test_control_path.py",
    "test_readiness.EvidenceTests.test_prior_evidence_unchanged":
        "docs/phase5-evidence/test_readiness.py",
    "test_demonstration.DemonstrationTests.test_prior_evidence_preserved":
        "docs/phase6-evidence/test_demonstration.py",
}
KNOWN_FIRST_MISSING = "docs/phase3-evidence/build.log"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def validate_output(output, root):
    """Resolve aliases and reject retained evidence paths before any write."""
    root, output = root.resolve(), output.resolve()
    protected = [root / f"docs/phase{phase}-evidence" for phase in range(1, 7)]
    protected.append(root / "docs/audit-evidence")
    if any(output == directory or directory in output.parents for directory in protected):
        raise ValueError("Retained phase and audit evidence is read-only")
    if output == root or root in output.parents:
        allowed = [root / ".build", root / "docs/milestone1-evidence/runs"]
        if not any(directory in output.parents for directory in allowed):
            raise ValueError("Use a new subdirectory of .build or milestone1-evidence/runs, or external scratch")
    if output.exists():
        raise ValueError("Output already exists; use a new directory")
    return output


def historical_paths(path):
    inventory = json.loads(path.read_text())
    return {entry["path"] for entry in inventory["entries"]}


def classify_error(test_id, error, root, missing_paths):
    """Fail closed unless this is the audited first missing preservation log."""
    exception_type, exception, frames = error
    source = KNOWN_GAP_TESTS.get(test_id)
    if source is None or exception_type is not FileNotFoundError:
        return "unexpected_error"
    if exception.errno != errno.ENOENT or not isinstance(exception.filename, (str, os.PathLike)):
        return "unexpected_error"
    if KNOWN_FIRST_MISSING not in missing_paths:
        return "unexpected_error"
    expected_path = (root / KNOWN_FIRST_MISSING).resolve()
    if Path(exception.filename).resolve() != expected_path or expected_path.exists():
        return "unexpected_error"
    expected_source = (root / source).resolve()
    expected_function = test_id.rsplit(".", 1)[-1]
    if not any(Path(frame.filename).resolve() == expected_source
               and frame.name == expected_function
               for frame in traceback.extract_tb(frames)):
        return "unexpected_error"
    return "known_historical_gap"


class RecordingResult(unittest.TextTestResult):
    """Keep unittest's actual outcome while adding an independent policy label."""

    def __init__(self, *args, root, missing_paths, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = root
        self.missing_paths = missing_paths
        self.records = []
        self.started = {}

    def startTest(self, test):
        self.started[test.id()] = time.monotonic()
        super().startTest(test)

    def record(self, test, outcome, classification=None, error=None, reason=None):
        started = self.started.get(test.id())
        record = {
            "id": test.id(),
            "outcome": outcome,
            "classification": classification or outcome,
            "duration_seconds": time.monotonic() - started if started is not None else 0,
        }
        if error is not None:
            record["exception_type"] = error[0].__name__
            record["exception_message"] = str(error[1])
            record["traceback"] = "".join(traceback.format_exception(*error))
            if isinstance(error[1], OSError):
                record["errno"] = error[1].errno
                filename = error[1].filename
                if filename is not None:
                    try:
                        resolved = Path(filename).resolve()
                        try:
                            record["exception_filename"] = resolved.relative_to(self.root).as_posix()
                        except ValueError:
                            record["exception_filename"] = str(resolved)
                    except (OSError, TypeError, ValueError):
                        record["exception_filename"] = repr(filename)
        if reason is not None:
            record["reason"] = reason
        self.records.append(record)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addError(self, test, error):
        super().addError(test, error)
        classification = classify_error(test.id(), error, self.root, self.missing_paths)
        self.record(test, "error", classification, error)

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, "failed", error=error)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped", reason=reason)

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self.record(test, "expected_failure", error=error)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "unexpected_success")

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.record(subtest, "failed" if issubclass(error[0], test.failureException) else "error",
                        "unexpected_subtest_failure", error)


def suite_policy(records, tests_run, expected_count):
    """No missing test, setup error, skip or unexpected failure can be accepted."""
    if tests_run < 1 or len(records) != tests_run:
        return False
    if expected_count is not None and tests_run != expected_count:
        return False
    return all(record["outcome"] == "passed" or (
        record["outcome"] == "error" and record["classification"] == "known_historical_gap"
    ) for record in records)


def child_run(suite_name, root, inventory_path, result_path):
    relative, pattern, expected_count = SUITES[suite_name]
    loader = unittest.TestLoader()
    suite = loader.discover(str(root / relative), pattern=pattern)
    missing = historical_paths(inventory_path)
    runner = unittest.TextTestRunner(
        stream=sys.stderr, verbosity=2,
        resultclass=lambda *args, **kwargs: RecordingResult(
            *args, root=root, missing_paths=missing, **kwargs),
    )
    result = runner.run(suite)
    report = {
        "suite": suite_name,
        "discovery": {"directory": relative, "pattern": pattern},
        "tests_run": result.testsRun,
        "expected_test_count": expected_count,
        "unittest_successful": result.wasSuccessful(),
        "all_tests_passed": bool(result.records) and all(r["outcome"] == "passed" for r in result.records),
        "policy_satisfied": suite_policy(result.records, result.testsRun, expected_count),
        "outcomes": dict(Counter(r["outcome"] for r in result.records)),
        "classifications": dict(Counter(r["classification"] for r in result.records)),
        "tests": result.records,
    }
    write_json(result_path, report)
    return 0 if result.wasSuccessful() else 1


def load_integrity_module(root):
    path = root / "docs/milestone1-evidence/evidence.py"
    spec = importlib.util.spec_from_file_location("milestone1_evidence_for_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load evidence verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(root, output, inventory_path, baseline_path, timeout):
    # A fresh directory protects all earlier captures and makes partial failures visible.
    output = validate_output(output, root)
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "schema_version": 1,
        "started_utc": utc_now(),
        "argv": sys.argv,
        "cwd": str(Path.cwd()),
        "root": str(root),
        "python": {"executable": sys.executable, "version": sys.version},
        "platform": platform.platform(),
        "env_overrides": {"PYTHONDONTWRITEBYTECODE": "1"},
        "warning": "Historical-gap classification does not turn original unittest errors into passed tests.",
        "suites": [],
    }
    sources = {HERE / "run_tests.py", HERE / "evidence.py", inventory_path, baseline_path}
    for relative, pattern, _ in SUITES.values():
        sources.update((root / relative).glob(pattern))
    metadata["input_sha256"] = {}
    for source in sorted(sources):
        key = source.relative_to(root).as_posix() if source.is_relative_to(root) else str(source)
        metadata["input_sha256"][key] = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata["git"] = {}
    for name, argv in (("revision", ["git", "rev-parse", "HEAD"]),
                       ("working_tree", ["git", "status", "--short"])):
        command = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
        metadata["git"][name] = {"argv": argv, "exit_code": command.returncode,
                                  "stdout": command.stdout, "stderr": command.stderr}
    verifier = load_integrity_module(root)
    before = verifier.verify(root, baseline_path=baseline_path, missing_path=inventory_path)
    write_json(output / "integrity-before.json", before)
    policy_ok = bool(before["ok"])
    if policy_ok:
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for name in SUITES:
            result_path = output / f"{name}.json"
            argv = [sys.executable, "-B", str(HERE / "run_tests.py"), "--_child", name,
                    "--root", str(root), "--missing", str(inventory_path),
                    "--child-result", str(result_path)]
            command = {"suite": name, "argv": argv, "started_utc": utc_now()}
            with (output / f"{name}.stdout").open("w") as stdout, \
                    (output / f"{name}.stderr").open("w") as stderr:
                try:
                    process = subprocess.run(argv, cwd=root, env=environment, stdout=stdout,
                                             stderr=stderr, timeout=timeout, check=False)
                    command["exit_code"] = process.returncode
                except subprocess.TimeoutExpired:
                    command["exit_code"] = None
                    command["error"] = f"Suite exceeded {timeout} second timeout"
            command["finished_utc"] = utc_now()
            if result_path.is_file():
                report = json.loads(result_path.read_text())
                expected_exit = 0 if report["unittest_successful"] else 1
                accepted = report["policy_satisfied"] and command["exit_code"] == expected_exit
                command["result"] = report
            else:
                accepted = False
                command["error"] = command.get("error", "Suite exited without a result file")
            command["policy_satisfied"] = accepted
            policy_ok = policy_ok and accepted
            metadata["suites"].append(command)
    after = verifier.verify(root, baseline_path=baseline_path, missing_path=inventory_path)
    write_json(output / "integrity-after.json", after)
    policy_ok = policy_ok and bool(after["ok"])
    reports = [suite["result"] for suite in metadata["suites"] if "result" in suite]
    legacy = [r for r in reports if r["suite"] != "milestone1"]
    new = [r for r in reports if r["suite"] == "milestone1"]
    for label, group in (("legacy", legacy), ("milestone1", new)):
        records = [test for report in group for test in report["tests"]]
        metadata[label] = {
            "tests_run": sum(report["tests_run"] for report in group),
            "outcomes": dict(Counter(r["outcome"] for r in records)),
            "known_historical_errors": sum(r["classification"] == "known_historical_gap" for r in records),
        }
    metadata["finished_utc"] = utc_now()
    metadata["policy_satisfied"] = policy_ok
    metadata["all_tests_passed"] = policy_ok and bool(reports) and all(r["all_tests_passed"] for r in reports)
    metadata["status"] = ("passed" if metadata["all_tests_passed"] else
                          "verified_with_historical_gaps" if policy_ok else "failed")
    write_json(output / "results.json", metadata)
    print(json.dumps({"status": metadata["status"], "legacy": metadata["legacy"],
                      "milestone1": metadata["milestone1"], "results": str(output / "results.json")}, indent=2))
    return 0 if policy_ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path,
                        help="Fresh output directory; defaults to a timestamped milestone1 run")
    parser.add_argument("--missing", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--timeout", type=float, default=300,
                        help="Maximum seconds per suite (default: 300)")
    parser.add_argument("--_child", choices=SUITES, help=argparse.SUPPRESS)
    parser.add_argument("--child-result", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory = (args.missing or root / "docs/milestone1-evidence/missing-historical.json").resolve()
    baseline = (args.baseline or root / "docs/milestone1-evidence/baseline.json").resolve()
    if args._child:
        if args.child_result is None:
            parser.error("Internal child requires a result path")
        return child_run(args._child, root, inventory, args.child_result)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    default_name = datetime.now(timezone.utc).strftime("tests-%Y%m%dT%H%M%S.%fZ")
    output = (args.output or root / ".build/reproducibility/tests" / default_name).resolve()
    return run(root, output, inventory, baseline, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
