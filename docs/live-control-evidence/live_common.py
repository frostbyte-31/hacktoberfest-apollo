"""GPL-2.0-or-later. Integrity helpers for the new live-control experiments."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(part)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify_prior():
    recorded = json.loads((HERE / 'prior_hashes.json').read_text())
    failures = []
    for name, expected in recorded['sha256'].items():
        path = ROOT / name
        if not path.is_file() or digest(path) != expected:
            failures.append(name)
    return {'ok': not failures, 'files_checked': len(recorded['sha256']),
            'manifest_sha256': digest(HERE / 'prior_hashes.json'),
            'source_revision': recorded['source_revision'], 'changed_or_missing': failures}


def new_output(path):
    """Only create fresh .build outputs or an external temporary directory."""
    path = Path(path).resolve()
    if path.exists():
        raise ValueError('Output exists; preserve it and choose a new path: ' + str(path))
    if ROOT in path.parents and ROOT / '.build' not in path.parents:
        raise ValueError('Fresh experiment output must be inside .build or outside the checkout')
    path.mkdir(parents=True)
    return path
