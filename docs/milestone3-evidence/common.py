"""GPL-2.0-or-later. Reuse retained build and preservation utilities."""
import importlib.util
from pathlib import Path
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


prior = load_module('milestone3_retained_provenance',
                    ROOT / 'docs/milestone2-evidence/common.py')
retained = prior.retained
digest = prior.digest
write_json = prior.write_json


def verify_prior(root=ROOT, manifest_path=HERE / 'prior_hashes.json'):
    return prior.verify_prior(root, manifest_path)
