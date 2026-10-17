"""Fail-closed tests for classification of missing historical evidence."""
import errno
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("milestone1_test_runner", HERE.parent / "run_tests.py")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class HistoricalGapClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.test_id = "test_readiness.EvidenceTests.test_prior_evidence_unchanged"
        self.source = self.root / runner.KNOWN_GAP_TESTS[self.test_id]
        self.source.parent.mkdir(parents=True)
        self.missing = self.root / runner.KNOWN_FIRST_MISSING
        self.paths = {runner.KNOWN_FIRST_MISSING}

    def exception(self, exception=None, source=None, function=None):
        exception = exception or FileNotFoundError(errno.ENOENT, "No such file", str(self.missing))
        function = function or self.test_id.rsplit(".", 1)[-1]
        namespace = {"exception": exception}
        code = compile(f"def {function}():\n    raise exception\n{function}()\n",
                       str(source or self.source), "exec")
        try:
            exec(code, namespace)
        except Exception:
            return sys.exc_info()
        self.fail("Fixture did not raise")

    def classify(self, error=None, test_id=None, paths=None):
        return runner.classify_error(test_id or self.test_id, error or self.exception(),
                                     self.root, self.paths if paths is None else paths)

    def test_exact_known_gap_retains_error_and_explicit_classification(self):
        error = self.exception()
        self.assertEqual(self.classify(error), "known_historical_gap")
        result = runner.RecordingResult(unittest.runner._WritelnDecorator(io.StringIO()),
                                        True, 2, root=self.root, missing_paths=self.paths)
        class LegacyTest(unittest.TestCase):
            def runTest(self):
                pass
            def id(inner):
                return self.test_id
        test = LegacyTest()
        result.startTest(test)
        result.addError(test, error)
        result.stopTest(test)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.records[0]["outcome"], "error")
        self.assertEqual(result.records[0]["classification"], "known_historical_gap")
        self.assertIn("FileNotFoundError", result.records[0]["traceback"])
        self.assertTrue(runner.suite_policy(result.records, 1, 1))

    def test_same_missing_path_in_unrelated_test_is_fatal(self):
        self.assertEqual(self.classify(test_id="other.Test.test_prior_evidence_unchanged"), "unexpected_error")

    def test_different_missing_path_in_preservation_check_is_fatal(self):
        other = FileNotFoundError(errno.ENOENT, "No such file", str(self.root / "other.log"))
        self.assertEqual(self.classify(self.exception(other)), "unexpected_error")

    def test_uninventoried_missing_log_is_fatal(self):
        self.assertEqual(self.classify(paths=set()), "unexpected_error")

    def test_unrelated_source_frame_is_fatal(self):
        self.assertEqual(self.classify(self.exception(source=self.root / "other.py")), "unexpected_error")

    def test_unrelated_function_is_fatal(self):
        self.assertEqual(self.classify(self.exception(function="different")), "unexpected_error")

    def test_other_exception_types_are_fatal(self):
        for exception in [ValueError("bad"), AssertionError("changed digest"),
                          PermissionError(errno.EACCES, "Denied", str(self.missing))]:
            with self.subTest(exception=type(exception).__name__):
                self.assertEqual(self.classify(self.exception(exception)), "unexpected_error")

    def test_other_errno_is_fatal(self):
        error = FileNotFoundError(errno.EACCES, "Denied", str(self.missing))
        self.assertEqual(self.classify(self.exception(error)), "unexpected_error")

    def test_missing_filename_is_fatal(self):
        self.assertEqual(self.classify(self.exception(FileNotFoundError("missing"))), "unexpected_error")

    def test_bytes_filename_cannot_match_known_gap(self):
        exception = FileNotFoundError(errno.ENOENT, "No such file", bytes(self.missing))
        self.assertEqual(self.classify(self.exception(exception)), "unexpected_error")

    def test_previously_missing_path_now_present_cannot_be_exempted(self):
        self.missing.parent.mkdir(parents=True)
        self.missing.write_text("real recovered log")
        self.assertEqual(self.classify(), "unexpected_error")

    def test_suite_policy_rejects_every_unverified_outcome(self):
        for outcome in ["failed", "error", "skipped", "unexpected_success", "expected_failure"]:
            with self.subTest(outcome=outcome):
                self.assertFalse(runner.suite_policy([
                    {"outcome": outcome, "classification": "unexpected_error"}], 1, 1))

    def test_missing_tests_and_setup_errors_are_fatal(self):
        passed = [{"outcome": "passed", "classification": "passed"}]
        self.assertFalse(runner.suite_policy([], 0, None))
        self.assertFalse(runner.suite_policy(passed, 0, None))
        self.assertFalse(runner.suite_policy(passed, 1, 2))
        self.assertTrue(runner.suite_policy(passed, 1, 1))


class OutputProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repository"
        self.root.mkdir()

    def test_retained_phase_and_audit_outputs_rejected_before_any_write(self):
        paths = [f"docs/phase{phase}-evidence/new-output" for phase in range(1, 7)]
        paths.append("docs/audit-evidence/new-output")
        for relative in paths:
            with self.subTest(path=relative):
                output = self.root / relative
                with mock.patch.object(Path, "mkdir", side_effect=AssertionError("Unexpected write")):
                    with self.assertRaisesRegex(ValueError, "read-only"):
                        runner.run(self.root, output, self.root / "missing.json",
                                   self.root / "baseline.json", 10)
                self.assertFalse(output.parent.exists())

    def test_symlink_alias_to_retained_evidence_is_rejected(self):
        retained = self.root / "docs/phase6-evidence"
        retained.mkdir(parents=True)
        alias = Path(self.temporary.name) / "alias"
        alias.symlink_to(retained, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "read-only"):
            runner.validate_output(alias / "new-output", self.root)
        self.assertFalse((retained / "new-output").exists())

    def test_build_milestone_records_and_external_scratch_are_allowed(self):
        for output in [self.root / ".build/reproducibility/tests/fresh",
                       self.root / "docs/milestone1-evidence/runs/fresh",
                       Path(self.temporary.name) / "scratch/fresh"]:
            with self.subTest(output=output):
                self.assertEqual(runner.validate_output(output, self.root), output.resolve())
                self.assertFalse(output.exists())

    def test_unrelated_repository_outputs_and_existing_directories_are_rejected(self):
        for output in [self.root, self.root / ".build", self.root / "application/results",
                       self.root / "docs/milestone1-evidence/runs"]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                runner.validate_output(output, self.root)
        existing = self.root / ".build/already-exists"
        existing.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            runner.validate_output(existing, self.root)


if __name__ == "__main__":
    unittest.main()
