#!/usr/bin/env python3
"""Retain the actual dated browser and final-check outputs, without old edits."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
from live_common import HERE, ROOT, digest, verify_prior, write_json
from analyze import analyze_trace


def main():
    destination = HERE / 'release-checks/2026-10-17'
    destination.mkdir(parents=True, exist_ok=False)
    retained, omitted = {}, []

    def copy_tree(source, target):
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            if path.is_symlink():
                raise ValueError('Refuse evidence symlink: ' + str(path))
            if 'source' in relative.parts or '__pycache__' in relative.parts or path.suffix in ('.so', '.o', '.bin'):
                omitted.append({'source': str(path.relative_to(ROOT)), 'sha256': digest(path),
                                'reason': 'Rebuilt binary or original extracted source; pinned source bundle already retained.'})
                continue
            raw = path.read_bytes()
            if raw[:4] in (b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'):
                omitted.append({'source': str(path.relative_to(ROOT)), 'sha256': digest(path), 'reason': 'Rebuilt native executable; source and build commands retained.'})
                continue
            output = target / relative
            compressed = path.suffix == '.jsonl' or len(raw) > 1024*1024
            if compressed:
                output = output.with_name(output.name + '.gz')
                raw_output = gzip.compress(raw, mtime=0)
            else:
                raw_output = raw
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw_output)
            retained[str(output.relative_to(destination))] = {'source': str(path.relative_to(ROOT)),
                'raw_sha256': hashlib.sha256(raw).hexdigest(), 'stored_sha256': digest(output),
                'raw_bytes': len(raw), 'compressed': compressed}

    runs = {
        'restricted-attempt': '.build/live-control/final-checks/20261017T172942Z-74586677',
        'permitted-contracts': '.build/live-control/final-checks/20261017T173143Z-3064cc37',
        'native/old-tests': '.build/reproducibility/tests/tests-20261017T172943.243943Z',
        'native/milestone2-tests': '.build/milestone2/tests/20261017T172944Z-e0d060d1',
        'native/milestone3-tests': '.build/milestone3/tests/20261017T172947Z-65f1d357',
        'native/phase7-tests': '.build/phase7/tests/20261017T173015Z-079e8ac1',
        'native/phase6-reproduction': '.build/reproducibility/runs/20261017T172950Z-a4d91d3e',
        'native/milestone2': '.build/milestone2/runs/20261017T172957Z-40881365',
        'native/milestone3': '.build/milestone3/runs/20261017T173001Z-353a5141',
        'native/phase7': '.build/phase7/runs/20261017T173021Z-5ee2562e',
    }
    for name, source in runs.items():
        copy_tree(ROOT / source, destination / name)
    browser = []
    for identity, label, sign in (
            ('fc7543fbcf6adda4f028d4cb74d98155', 'keyboard', 1),
            ('716619a53367808b061e82de853f4d93', 'buttons', -1)):
        gateway = ROOT / '.build/live/http' / identity
        record = json.loads((gateway / 'record.json').read_text())
        download = Path('/Users/ggtrinkalipu/Downloads') / ('apollo-live-' + identity + '.json')
        if json.loads(download.read_text()) != record:
            raise ValueError('Browser download differs from finalized gateway record')
        native = Path(record['session']['frame']['trace_path']).parent
        result = analyze_trace(native / 'trace.jsonl', sign, 0, fixed_plan=False)
        copy_tree(gateway, destination / 'browser' / label / 'gateway')
        copy_tree(native, destination / 'browser' / label / 'native')
        assets = Path(record['provenance']['inputs_sha256'].keys().__iter__().__next__())
        asset_paths = [Path(p) for p in record['provenance']['inputs_sha256'] if p.endswith('/server.tcl')]
        if len(asset_paths) != 1:
            raise ValueError('Missing unique actual model assets')
        copy_tree(asset_paths[0].parent, destination / 'browser' / label / 'assets')
        target = destination / 'browser' / label / 'download.json'
        shutil.copyfile(download, target)
        retained[str(target.relative_to(destination))] = {'source': str(download), 'raw_sha256': digest(download), 'stored_sha256': digest(target), 'compressed': False}
        browser.append({'case': label, 'sessionId': identity, 'analysis': result,
                        'summary': record['session']['summary'], 'download_matches_gateway': True})
    copy_tree(ROOT / '.build/live-ui/screenshots', destination / 'browser/screenshots')
    write_json(destination / 'browser/results.json', browser)
    production = [p for base in ('backend', 'frontend') for p in (ROOT / base).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts]
    production += [ROOT / 'Makefile', ROOT / 'README.md', Path(__file__), HERE / 'run_final_checks.py']
    for path in production:
        target = destination / 'executed-code' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    preservation = verify_prior()
    if not preservation['ok']:
        raise ValueError('Earlier evidence changed')
    write_json(destination / 'preservation.json', preservation)
    write_json(destination / 'retention.json', {'files': retained, 'omitted': omitted,
        'note': 'Actual outputs. Restricted HTTP bind errors are retained as errors; permitted rerun separately passed. The first keyboard screenshot precedes the interface-label/accessibility wording change; the second browser run uses the captured final frontend source. No missing earlier source text is reconstructed.'})
    print(json.dumps({'output': str(destination), 'files': len(retained), 'prior_preserved': preservation['files_checked']}))


if __name__ == '__main__':
    main()
