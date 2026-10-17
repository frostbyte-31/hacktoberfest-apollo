"""Fail before experiments if retained evidence changes or grows unexpectedly."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from common import verify_prior


class PreservationTests(unittest.TestCase):
    def test_modified_missing_extra_and_symlinked_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old = root / 'docs/milestone1-evidence/record.txt'
            old.parent.mkdir(parents=True)
            old.write_text('retained')
            manifest = root / 'prior.json'
            manifest.write_text(json.dumps({'source_revision': 'prior', 'sha256': {
                str(old.relative_to(root)): hashlib.sha256(old.read_bytes()).hexdigest()}}))
            self.assertTrue(verify_prior(root, manifest)['ok'])
            old.write_text('changed')
            self.assertFalse(verify_prior(root, manifest)['ok'])
            old.unlink()
            self.assertFalse(verify_prior(root, manifest)['ok'])
            old.write_text('retained')
            extra = old.with_name('new-record.txt')
            extra.write_text('extra')
            self.assertFalse(verify_prior(root, manifest)['ok'])
            extra.unlink()
            target = root / 'elsewhere.txt'
            target.write_text('retained')
            old.unlink()
            old.symlink_to(target)
            self.assertFalse(verify_prior(root, manifest)['ok'])

    def test_unsafe_inventory_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'prior.json'
            manifest.write_text(json.dumps({'source_revision': 'prior', 'sha256': {'../escape': '0'*64}}))
            with self.assertRaises(ValueError):
                verify_prior(root, manifest)


if __name__ == '__main__':
    unittest.main()
