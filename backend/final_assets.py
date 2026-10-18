"""Reuse verified scientific artifacts and locked native dependencies for the demo."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROPE_SHA = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
SEALS = {
    'phase10': '10b77abb67914dd6e0f4a13afb967b67f8e96b161217b63f9b0706f9a78fa7cc',
    'phase11': '184c996c9930f54d5851ad1c7f794ea5245d252fb0b79e03b636ccda092f7c47',
    'phase12': '353c3ef0cbadb2c19937ecf826450e029694c9f7ec328ff6e040407a6f5a8236',
}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            value.update(part)
    return value.hexdigest()


def verify_science():
    """Verify sealed evidence, never demand that new application code is old code."""
    rope = ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin'
    if digest(rope) != ROPE_SHA:
        raise RuntimeError('Original Luminary 099 rope integrity check failed')
    checked = {}
    for phase, expected in SEALS.items():
        manifest = ROOT/'docs'/(phase+'-evidence')/'checksums.json'
        if digest(manifest) != expected:
            raise RuntimeError('Changed original evidence manifest: '+phase)
        entries = json.loads(manifest.read_text())['sha256']
        for name, wanted in entries.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError('Invalid original evidence path')
            path = ROOT/relative
            if path.is_symlink() or not path.is_file() or digest(path) != wanted:
                raise RuntimeError('Changed original evidence: '+name)
        checked[phase] = len(entries)
    return {'ropeSha256': ROPE_SHA, 'sealedFiles': checked,
            'sourceRevision': 'f577e3fd917866c59334e6cdd32504f09df76f60'}


def common_repository():
    """Discover an existing shared cache through Git; no developer home paths."""
    try:
        raw = subprocess.check_output(['git', 'rev-parse', '--git-common-dir'],
                                      cwd=ROOT, text=True).strip()
        return (ROOT/raw).resolve().parent
    except (OSError, subprocess.CalledProcessError):
        return ROOT


def runtime_manifest(bootstrap=False):
    requested = os.environ.get('APOLLO_RUNTIME_MANIFEST')
    candidates = [Path(requested)] if requested else [
        ROOT/'.build/reproducibility/runtime-manifest.json',
        common_repository()/'.build/reproducibility/runtime-manifest.json']
    spec = importlib.util.spec_from_file_location('final_locked_runtime',
                         ROOT/'tools/reproducibility/bootstrap_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for candidate in candidates:
        if candidate.exists():
            module.validate_runtime(candidate)
            return candidate.resolve()
    if requested:
        raise RuntimeError('APOLLO_RUNTIME_MANIFEST does not exist')
    if bootstrap:
        module.bootstrap(ROOT/'.build/reproducibility')
        candidate = ROOT/'.build/reproducibility/runtime-manifest.json'
        module.validate_runtime(candidate)
        return candidate
    raise RuntimeError('Locked Tcl runtime is missing. Run make runtime, then relaunch.')


def prepare_demo_assets(bootstrap=False):
    """Use the existing attitude asset builder; preserve every scientific guard."""
    verify_science()
    from backend.native_session import prepare_assets
    return prepare_assets(runtime_manifest=runtime_manifest(bootstrap=bootstrap))


if __name__ == '__main__':
    assets = prepare_demo_assets(bootstrap='--bootstrap' in sys.argv)
    output = ROOT/'.build/final-demo-assets.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(assets, indent=2)+'\n')
    print(json.dumps({'assets': str(output), 'source': assets['source'], 'tcl': assets['tcl']}))
