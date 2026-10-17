"""Exercise preservation failures and exact-hash historical recovery in isolation."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("milestone1_evidence", HERE / "evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.metadata = self.root / "docs/milestone1-evidence"
        self.metadata.mkdir(parents=True)
        self.baseline_path = self.metadata / "baseline.json"
        self.missing_path = self.metadata / "missing-historical.json"
        self.audit_relative = "docs/audit-evidence/2026-10-17/integrity.json"
        self.log_bytes = {
            "docs/phase2-evidence/run.log": b"original run\n",
            "docs/phase3-evidence/build.log": b"original build\n",
        }
        phase2 = "docs/phase2-evidence/49_sha256.txt"
        phase3 = "docs/phase3-evidence/sha256.json"
        self.write("AGENTS.md", b"Retain existing evidence.\n")
        self.write("docs/PHASE6_DEMONSTRATION.md", b"Bounded demonstration.\n")
        self.write(phase2, (digest(self.log_bytes["docs/phase2-evidence/run.log"]) + "  run.log\n").encode())
        self.write(phase3, json.dumps({"docs/phase3-evidence/build.log": digest(self.log_bytes["docs/phase3-evidence/build.log"])}).encode())
        self.audit = {"manifests": [
            {"path": phase2, "scope": "phase-local", "entries": [{
                "status": "missing", "resolved_path": "docs/phase2-evidence/run.log",
                "recorded_path": "run.log", "expected_sha256": digest(self.log_bytes["docs/phase2-evidence/run.log"]),
            }]},
            {"path": phase3, "scope": "repository", "entries": [{
                "status": "missing", "resolved_path": "docs/phase3-evidence/build.log",
                "recorded_path": "docs/phase3-evidence/build.log", "expected_sha256": digest(self.log_bytes["docs/phase3-evidence/build.log"]),
            }]},
        ]}
        self.write(self.audit_relative, json.dumps(self.audit).encode())
        self.inventory = {
            "schema_version": 1,
            "audit_inventory": {"path": self.audit_relative, "sha256": digest((self.root / self.audit_relative).read_bytes())},
            "entries": [
                {"path": "docs/phase2-evidence/run.log", "expected_sha256": digest(self.log_bytes["docs/phase2-evidence/run.log"]), "manifest_references": [{
                    "path": phase2, "recorded_path": "run.log", "scope": "phase-local", "expected_sha256": digest(self.log_bytes["docs/phase2-evidence/run.log"]),
                }]},
                {"path": "docs/phase3-evidence/build.log", "expected_sha256": digest(self.log_bytes["docs/phase3-evidence/build.log"]), "manifest_references": [{
                    "path": phase3, "recorded_path": "docs/phase3-evidence/build.log", "scope": "repository", "expected_sha256": digest(self.log_bytes["docs/phase3-evidence/build.log"]),
                }]},
            ],
        }
        self.baseline = {
            "schema_version": 1, "scope": copy.deepcopy(evidence.SCOPE),
            "files": {
                relative: digest((self.root / relative).read_bytes())
                for relative in ["AGENTS.md", "docs/PHASE6_DEMONSTRATION.md", self.audit_relative, phase2, phase3]
            },
        }
        self.save_metadata()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_metadata(self):
        self.missing_path.write_text(json.dumps(self.inventory))
        self.baseline["missing_inventory_sha256"] = digest(self.missing_path.read_bytes())
        self.baseline_path.write_text(json.dumps(self.baseline))

    def verify(self):
        return evidence.verify(self.root, self.baseline_path, self.missing_path)

    def test_known_gaps_remain_explicit_and_do_not_count_as_matches(self):
        report = self.verify()
        self.assertTrue(report["ok"], report)
        self.assertFalse(report["historical_evidence_complete"])
        self.assertEqual(report["summary"]["match"], 5)
        self.assertEqual(report["summary"]["historical_missing"], 2)
        self.assertEqual(report["summary"]["historical_recovered"], 0)
        self.assertFalse(any((self.root / path).exists() for path in self.log_bytes))

    def test_new_missing_retained_file_is_fatal(self):
        (self.root / "AGENTS.md").unlink()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"]["missing"], 1)
        self.assertEqual(report["summary"]["historical_missing"], 2)

    def test_changed_retained_file_is_fatal(self):
        self.write("docs/PHASE6_DEMONSTRATION.md", b"changed claim\n")
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"]["mismatch"], 1)

    def test_new_unlisted_evidence_is_fatal(self):
        self.write("docs/phase1-evidence/new.log", b"new evidence\n")
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"]["unlisted"], 1)

    def test_each_historical_record_requires_its_exact_original_hash(self):
        for relative, original in self.log_bytes.items():
            with self.subTest(path=relative, recovery="wrong bytes"):
                self.write(relative, b"replacement output cannot reconstruct history\n")
                report = self.verify()
                self.assertFalse(report["ok"])
                self.assertEqual(report["summary"]["historical_mismatch"], 1)
                self.assertEqual(report["summary"]["historical_missing"], 1)
            with self.subTest(path=relative, recovery="exact original bytes"):
                self.write(relative, original)
                report = self.verify()
                self.assertTrue(report["ok"], report)
                self.assertEqual(report["summary"]["historical_recovered"], 1)
                self.assertEqual(report["summary"]["historical_missing"], 1)
            (self.root / relative).unlink()

    def test_complete_recovery_is_reported_separately(self):
        for relative, original in self.log_bytes.items():
            self.write(relative, original)
        report = self.verify()
        self.assertTrue(report["ok"])
        self.assertTrue(report["historical_evidence_complete"])
        self.assertEqual(report["summary"]["historical_recovered"], 2)

    def test_inventory_cannot_add_or_drop_exceptions(self):
        self.inventory["entries"].pop()
        self.save_metadata()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("differs from source audit", " ".join(report["errors"]))

    def test_unpinned_inventory_change_is_fatal(self):
        self.missing_path.write_text(self.missing_path.read_text() + "\n")
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("differs from pinned hash", " ".join(report["errors"]))

    def test_original_manifest_is_verified_directly(self):
        relative = "docs/phase2-evidence/49_sha256.txt"
        self.write(relative, ("0" * 64 + "  run.log\n").encode())
        self.baseline["files"][relative] = digest((self.root / relative).read_bytes())
        self.save_metadata()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("absent from manifest", " ".join(report["errors"]))

    def test_conflicting_original_hashes_are_rejected(self):
        self.audit["manifests"][1]["entries"].append({
            "status": "missing", "resolved_path": "docs/phase2-evidence/run.log",
            "recorded_path": "docs/phase2-evidence/run.log", "expected_sha256": "0" * 64,
        })
        self.write(self.audit_relative, json.dumps(self.audit).encode())
        changed_hash = digest((self.root / self.audit_relative).read_bytes())
        self.baseline["files"][self.audit_relative] = changed_hash
        self.inventory["audit_inventory"]["sha256"] = changed_hash
        self.save_metadata()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("Conflicting historical hashes", " ".join(report["errors"]))

    def test_symlink_substitution_is_fatal_even_for_identical_bytes(self):
        original = (self.root / "AGENTS.md").read_bytes()
        self.write("other.txt", original)
        (self.root / "AGENTS.md").unlink()
        (self.root / "AGENTS.md").symlink_to(self.root / "other.txt")
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"]["unsafe"], 1)

    def test_baseline_paths_cannot_escape_repository(self):
        self.baseline["files"]["../outside"] = "0" * 64
        self.save_metadata()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("Unsafe evidence path", " ".join(report["errors"]))

    def test_missing_inventory_is_a_machine_readable_failure(self):
        self.missing_path.unlink()
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertTrue(report["errors"])

    def test_malformed_metadata_is_a_machine_readable_failure(self):
        self.baseline_path.write_text("null\n")
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("JSON objects", " ".join(report["errors"]))

    def test_duplicate_json_key_is_a_machine_readable_failure(self):
        self.baseline_path.write_text('{"schema_version": 1, "schema_version": 1}')
        report = self.verify()
        self.assertFalse(report["ok"])
        self.assertIn("Duplicate JSON key", " ".join(report["errors"]))

    def test_cli_exit_codes_and_report_output(self):
        output = self.root / "result.json"
        command = [sys.executable, "-B", str(HERE / "evidence.py"), "verify", "--root", str(self.root), "--output", str(output)]
        successful = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(successful.returncode, 0, successful.stderr)
        self.assertTrue(json.loads(output.read_text())["ok"])
        self.assertEqual(json.loads(successful.stdout), json.loads(output.read_text()))
        (self.root / "AGENTS.md").unlink()
        failed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertFalse(json.loads(failed.stdout)["ok"])

    def test_cli_refuses_to_overwrite_retained_evidence(self):
        path = self.root / "AGENTS.md"
        original = path.read_bytes()
        process = subprocess.run([sys.executable, "-B", str(HERE / "evidence.py"), "verify", "--root", str(self.root), "--output", str(path)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(path.read_bytes(), original)


class RetainedRepositoryTests(unittest.TestCase):
    def test_original_snapshot_and_29_gaps_are_intact(self):
        report = evidence.verify(ROOT)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["summary"]["match"], 307)
        self.assertEqual(report["summary"]["historical_missing"], 29)
        self.assertFalse(report["historical_evidence_complete"])


if __name__ == "__main__":
    unittest.main()
