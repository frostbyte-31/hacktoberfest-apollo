"""Failure-path checks for the locked runtime, without compiling test binaries."""
from pathlib import Path
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("apollo_runtime_tested", ROOT / "tools/reproducibility/bootstrap_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeChecks(unittest.TestCase):
    def test_cache_cannot_write_retained_evidence_even_through_build_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            retained = root / "docs/phase6-evidence"
            retained.mkdir(parents=True)
            for cache in (root, root / ".build", retained / "new-runtime"):
                with self.subTest(cache=cache), self.assertRaisesRegex(RuntimeError, "read-only"):
                    runtime.validate_cache(cache, root)
            (root / ".build").symlink_to(retained, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "read-only"):
                runtime.validate_cache(root / ".build/new-runtime", root)
            self.assertEqual(list(retained.iterdir()), [])
            outside = Path(temp) / "external-scratch"
            self.assertEqual(runtime.validate_cache(outside, root), outside.resolve())

    def test_real_build_cache_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            cache = root / ".build/reproducibility"
            self.assertEqual(runtime.validate_cache(cache, root), cache.resolve())

    def test_corrupt_offline_archive_is_not_extracted(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / "wrong.tar.gz"
            archive.write_bytes(b"not the pinned Tcl archive")
            with mock.patch.object(runtime.shutil, "which", return_value="/unused/build/tool"):
                with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                    runtime.bootstrap(base / "cache", archive=archive)
            self.assertFalse((base / "cache/sources").exists())
            self.assertFalse((base / "cache/runtime").exists())

    def test_archive_members_are_all_checked_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive, destination = base / "unsafe.tar.gz", base / "source"
            destination.mkdir()
            with tarfile.open(archive, "w:gz") as tar:
                for name in ("safe/first.txt", "../escape.txt"):
                    item = tarfile.TarInfo(name)
                    item.size = 1
                    tar.addfile(item, io.BytesIO(b"x"))
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                runtime.extract_source_archive(archive, destination)
            self.assertEqual(list(destination.iterdir()), [])
            self.assertFalse((base / "escape.txt").exists())

    def test_archive_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive, destination = base / "unsafe.tar.gz", base / "source"
            destination.mkdir()
            with tarfile.open(archive, "w:gz") as tar:
                item = tarfile.TarInfo("link")
                item.type, item.linkname = tarfile.SYMTYPE, "/tmp"
                tar.addfile(item)
            with self.assertRaisesRegex(RuntimeError, "link or special file"):
                runtime.extract_source_archive(archive, destination)
            self.assertEqual(list(destination.iterdir()), [])

    def fixture(self, base):
        """An inert filesystem fixture; smoke is mocked only after hash checks."""
        archive, source, install = base / "source.tar.gz", base / "source", base / "runtime"
        archive.write_bytes(b"fixture archive")
        source.mkdir()
        (source / "original.c").write_bytes(b"source fixture")
        (install / "bin").mkdir(parents=True)
        executable = install / "bin/tclsh8.6"
        executable.write_bytes(b"inert executable fixture")
        (install / "init.tcl").write_text("fixture library\n")
        lock = base / "lock.json"
        runtime.write_json(lock, {"tcl": {"version": "8.6.16", "sha256": runtime.digest(archive),
                                          "executable": "bin/tclsh8.6"}})
        manifest = base / "manifest.json"
        runtime.write_json(manifest, {"schema": 1, "version": "8.6.16", "source_sha256": runtime.digest(archive),
            "lock_sha256": runtime.digest(lock), "archive_path": str(archive), "source_path": str(source),
            "source_tree_sha256": runtime.tree_digest(source), "runtime_path": str(install),
            "runtime_tree_sha256": runtime.tree_digest(install), "executable": str(executable),
            "executable_sha256": runtime.digest(executable)})
        return lock, manifest, archive, source, install

    def test_lock_mismatch_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, *_ = self.fixture(Path(temp))
            lock.write_text(lock.read_text() + "\n")
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                with self.assertRaisesRegex(RuntimeError, "current runtime lock"):
                    runtime.validate_runtime(manifest)
                smoke.assert_not_called()

    def test_archive_mismatch_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, archive, *_ = self.fixture(Path(temp))
            archive.write_bytes(b"changed archive")
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                with self.assertRaisesRegex(RuntimeError, "archive checksum mismatch"):
                    runtime.validate_runtime(manifest)
                smoke.assert_not_called()

    def test_changed_source_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, _, source, _ = self.fixture(Path(temp))
            (source / "original.c").write_bytes(b"changed")
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                with self.assertRaisesRegex(RuntimeError, "source changed"):
                    runtime.validate_runtime(manifest)
                smoke.assert_not_called()

    def test_changed_library_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, _, _, install = self.fixture(Path(temp))
            (install / "init.tcl").write_text("changed library\n")
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                with self.assertRaisesRegex(RuntimeError, "runtime changed"):
                    runtime.validate_runtime(manifest)
                smoke.assert_not_called()

    def test_added_runtime_file_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, _, _, install = self.fixture(Path(temp))
            (install / "added.tcl").write_text("extra library\n")
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                with self.assertRaisesRegex(RuntimeError, "runtime changed"):
                    runtime.validate_runtime(manifest)
                smoke.assert_not_called()

    def test_matching_files_reach_smoke_test(self):
        with tempfile.TemporaryDirectory() as temp:
            lock, manifest, *_ = self.fixture(Path(temp))
            with mock.patch.object(runtime, "LOCK_PATH", lock), mock.patch.object(runtime, "smoke_test") as smoke:
                data = runtime.validate_runtime(manifest)
                smoke.assert_called_once_with(Path(data["executable"]), "8.6.16")

    def test_zero_exit_without_smoke_marker_fails(self):
        result = subprocess.CompletedProcess(["fixture"], 0, "", "script failed\n")
        with mock.patch.object(runtime.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "runtime smoke failed"):
                runtime.smoke_test(Path("/inert/fixture"), "8.6.16")


if __name__ == "__main__":
    unittest.main()
