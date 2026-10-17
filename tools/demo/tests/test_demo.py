"""Integrity/path/packaging tests for the portable demo entry point."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('phase105_demo', ROOT / 'tools/demo/demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoGuards(unittest.TestCase):
    def test_sealed_phase10_and_original_rope_match_actual_files(self):
        result = demo.verify_artifacts(ROOT)
        self.assertTrue(result['verified'])
        self.assertEqual(result['phase10_sealed_files'], 739)
        self.assertEqual(result['canonical_raw_trace_sha256']['final'],
                         result['canonical_raw_trace_sha256']['repeat'])

    def test_hash_guard_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'value').write_bytes(b'original')
            expected = {'value': hashlib.sha256(b'original').hexdigest()}
            self.assertEqual(demo.verify_hashes(root, expected), 1)
            (root / 'value').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Integrity mismatch'):
                demo.verify_hashes(root, expected)

    def test_manifest_guard_rejects_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'real').write_bytes(b'original')
            (root / 'alias').symlink_to(root / 'real')
            for name in ('../outside', '/absolute', 'alias'):
                with self.assertRaises(ValueError, msg=name):
                    demo.relative_file(root, name)

    def test_native_staging_uses_original_revision_and_excludes_new_application(self):
        # A real git archive proves the new app/Makefile never replace the old
        # preservation inventory. This does not execute AGC instructions.
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'staging'
            snapshot = demo.stage_baseline(ROOT, work)
            prior = json.loads((snapshot / 'docs/phase10-evidence/prior_hashes.json').read_text())
            self.assertEqual(demo.verify_hashes(snapshot, prior['sha256']), 4098)
            self.assertNotEqual(demo.digest(ROOT / 'Makefile'), demo.digest(snapshot / 'Makefile'))
            self.assertEqual(demo.digest(snapshot / 'Makefile'), prior['sha256']['Makefile'])
            self.assertFalse((snapshot / 'frontend/dist/guidance.html').exists())
            self.assertEqual(demo.digest(snapshot / demo.P10_MANIFEST), demo.P10_MANIFEST_SHA)

    def test_archive_rejects_escaping_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'malicious.tar'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('../outside')
                member.size = 3
                output.addfile(member, io.BytesIO(b'bad'))
            destination = root / 'destination'
            destination.mkdir()
            with self.assertRaisesRegex(ValueError, 'Unsafe Git archive'):
                demo.extract_baseline(archive, destination)
            self.assertFalse((root / 'outside').exists())

    def test_archive_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'valid.tar'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('file')
                member.size = 3
                output.addfile(member, io.BytesIO(b'new'))
            destination = root / 'destination'
            destination.mkdir()
            (destination / 'file').write_bytes(b'old')
            with self.assertRaises(FileExistsError):
                demo.extract_baseline(archive, destination)
            self.assertEqual((destination / 'file').read_bytes(), b'old')


if __name__ == '__main__':
    unittest.main()
