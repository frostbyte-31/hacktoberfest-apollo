"""Reject dependency substitutions and unsafe or changed retained source."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repro = load('reproduce_under_test', 'reproduce.py')
adapter = load('adapter_under_test', 'run_loop_with_tcl.py')


class DependencyAdapterTests(unittest.TestCase):
    def test_direct_adapter_cannot_write_retained_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            for output, record in ((adapter.PRIOR / 'new.jsonl', scratch / 'launch.json'),
                                   (scratch / 'new.jsonl', adapter.PRIOR / 'new.json')):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    adapter.validate_destinations(output, record)
                self.assertFalse(output.exists())
                self.assertFalse(record.exists())
            adapter.validate_destinations(scratch / 'new.jsonl', scratch / 'launch.json')
            (scratch / 'new.jsonl.tcl.stderr').write_text('original')
            with self.assertRaises(ValueError):
                adapter.validate_destinations(scratch / 'new.jsonl', scratch / 'launch.json')

    def test_only_exact_retained_launch_is_translated(self):
        source, tcl = Path('/scratch/source'), Path('/locked/bin/tclsh8.6')
        legacy = ['nix', 'shell', 'nixpkgs#tcl', '-c', 'tclsh',
                  str(adapter.PRIOR / 'plant_server.tcl'), str(source)]
        self.assertEqual(adapter.plant_command(legacy, tcl, source),
                         [str(tcl), str(adapter.PRIOR / 'plant_server.tcl'), str(source)])
        for command in (legacy + ['extra'], ['sh', '-c', 'arbitrary'],
                        legacy[:-1] + ['/other/source'],
                        legacy[:5] + ['/other/plant.tcl', str(source)]):
            with self.subTest(command=command), self.assertRaises(ValueError):
                adapter.plant_command(command, tcl, source)


class SourceAndOutputTests(unittest.TestCase):
    def test_retained_bundle_extracts_with_exact_member_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'source'
            manifest = json.loads((repro.PHASE6 / 'corresponding-source-hashes.json').read_text())
            repro.extract_source(repro.PHASE6 / 'corresponding-source.tar.gz', dest, manifest)
            self.assertEqual(len(list(p for p in dest.rglob('*') if p.is_file())), 24)
            for name, wanted in manifest.items():
                self.assertEqual(repro.digest(dest / name), wanted)

    def test_changed_or_unsafe_archive_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name, kind, expected_content in [('good', tarfile.REGTYPE, b'expected'),
                                                  ('../escape', tarfile.REGTYPE, b'actual'),
                                                  ('link', tarfile.SYMTYPE, b'actual')]:
                with self.subTest(name=name):
                    archive_path = base / 'input.tar.gz'
                    with tarfile.open(archive_path, 'w:gz') as archive:
                        item = tarfile.TarInfo(name)
                        item.type = kind
                        item.linkname = '/outside'
                        item.size = len(b'actual') if kind == tarfile.REGTYPE else 0
                        archive.addfile(item, io.BytesIO(b'actual') if item.size else None)
                    dest = base / 'output'
                    with self.assertRaises(ValueError):
                        repro.extract_source(archive_path, dest,
                            {name: hashlib.sha256(expected_content).hexdigest()})
                    self.assertFalse(dest.exists())

    def test_duplicate_archive_members_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / 'input.tar.gz'
            with tarfile.open(archive_path, 'w:gz') as archive:
                for _ in range(2):
                    item = tarfile.TarInfo('one')
                    item.size = 1
                    archive.addfile(item, io.BytesIO(b'x'))
            with self.assertRaisesRegex(ValueError, 'inventory'):
                repro.extract_source(archive_path, Path(directory) / 'out',
                                     {'one': hashlib.sha256(b'x').hexdigest()})

    def test_prior_evidence_and_existing_outputs_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output in (root, root / 'docs/phase5-evidence/new', root / '.build'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    repro.validate_output(output, root)
            allowed = root / '.build/new'
            self.assertEqual(repro.validate_output(allowed, root), allowed.resolve())
            allowed.mkdir(parents=True)
            with self.assertRaises(ValueError):
                repro.validate_output(allowed, root)

    def test_build_symlink_cannot_authorize_writes_into_old_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            retained = root / 'docs/phase6-evidence'
            retained.mkdir(parents=True)
            (root / '.build').symlink_to(retained, target_is_directory=True)
            output = root / '.build/new/result.jsonl'
            with self.assertRaises(ValueError):
                repro.validate_output(output, root)
            with mock.patch.object(adapter, 'ROOT', root), self.assertRaises(ValueError):
                adapter.validate_destinations(output, root / '.build/new/launch.json')
            self.assertFalse((retained / 'new').exists())

    def test_failed_and_timed_out_commands_leave_execution_records(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            commands = []
            with self.assertRaises(RuntimeError):
                repro.run_command([sys.executable, '-c', 'raise SystemExit(7)'],
                                  'failure', out, commands)
            self.assertEqual(commands[-1]['exit'], 7)
            with self.assertRaises(RuntimeError):
                repro.run_command([sys.executable, '-c', 'import time; time.sleep(10)'],
                                  'timeout', out, commands, timeout=0.05)
            self.assertEqual(commands[-1]['exit'], 'TIMEOUT')
            with self.assertRaises(RuntimeError):
                repro.run_command([out / 'no-such-program'], 'missing', out, commands)
            self.assertEqual(commands[-1]['exit'], 'LAUNCH_ERROR')
            self.assertEqual(len(json.loads((out / 'commands.json').read_text())), 3)


if __name__ == '__main__':
    unittest.main()
