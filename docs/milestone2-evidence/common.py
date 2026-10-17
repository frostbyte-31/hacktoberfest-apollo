"""GPL-2.0-or-later. Shared provenance for bounded milestone 2 probes."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


retained = load_module('milestone1_reproduction_utilities',
                       ROOT / 'docs/milestone1-evidence/reproduce.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify_prior(root=ROOT, manifest_path=HERE / 'prior_hashes.json'):
    """Check every retained file, including milestone 1, without rebaselining."""
    root = root.resolve()
    document = json.loads(manifest_path.read_text())
    expected = document['sha256']
    if not expected:
        raise ValueError('Empty prior evidence inventory')
    frozen_directories = set()
    mismatches, missing, unsafe = [], [], []
    for relative, wanted in expected.items():
        name = PurePosixPath(relative)
        if name.is_absolute() or '..' in name.parts or str(name) != relative or '\\' in relative:
            raise ValueError('Unsafe prior evidence path')
        if len(name.parts) > 2 and name.parts[0] in ('docs', 'tools'):
            frozen_directories.add('/'.join(name.parts[:2]))
        path = root
        for component in name.parts:
            path = path / component
            if path.is_symlink():
                unsafe.append(relative)
                break
        else:
            if not path.is_file():
                missing.append(relative)
            elif digest(path) != wanted:
                mismatches.append(relative)
    unlisted = []
    for relative in sorted(frozen_directories):
        directory = root / relative
        for path in directory.rglob('*'):
            if path.is_symlink() or not path.is_dir():
                name = path.relative_to(root).as_posix()
                if name not in expected:
                    unlisted.append(name)
    result = {'source_revision': document['source_revision'],
        'manifest_sha256': digest(manifest_path), 'files_checked': len(expected),
        'missing': missing, 'mismatches': mismatches, 'unsafe': unsafe,
        'unlisted': unlisted}
    result['ok'] = not any(result[key] for key in ('missing', 'mismatches', 'unsafe', 'unlisted'))
    return result
