#!/usr/bin/env python3
"""Validate the corrected yaw selector and paced negative single-axis feedback."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
from common import ROOT, HERE, retained, load_module, digest, write_json, verify_prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runtime-manifest', type=Path,
                        default=ROOT / '.build/reproducibility/runtime-manifest.json')
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = parser.parse_args()
    proposed = args.output or ROOT / '.build/milestone3/runs' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    output = retained.validate_output(proposed)
    output.mkdir(parents=True)
    commands = []
    try:
        before = verify_prior()
        write_json(output / 'preservation-before.json', before)
        if not before['ok']:
            raise ValueError('Prior evidence changed; refusing experiments')
        runtime_module = load_module('milestone3_locked_runtime', ROOT / 'tools/reproducibility/bootstrap_runtime.py')
        runtime = runtime_module.validate_runtime(args.runtime_manifest.resolve())
        compiler = shutil.which(args.cc)
        if compiler is None:
            raise RuntimeError('Missing compiler: ' + args.cc)
        bundle = ROOT / 'docs/phase6-evidence/corresponding-source.tar.gz'
        member_manifest = ROOT / 'docs/phase6-evidence/corresponding-source-hashes.json'
        source = output / 'source'
        retained.extract_source(bundle, source, json.loads(member_manifest.read_text()))
        write_json(output / 'environment.json', {'argv': sys.argv, 'cwd': str(Path.cwd()),
            'python': sys.version, 'platform': platform.platform(), 'compiler': compiler,
            'runtime_manifest_sha256': digest(args.runtime_manifest), 'runtime': runtime,
            'scope': 'Modern yaw/X selector correction and paced native feedback only'})
        paths = [HERE / 'prior_hashes.json', bundle, member_manifest,
                 ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin']
        for directory in (HERE, HERE / 'model', HERE / 'feedback'):
            paths += [p for p in directory.iterdir() if p.is_file() and p.suffix in ('.py', '.c', '.tcl')]
        write_json(output / 'inputs_source_hashes.json', {str(p): digest(p) for p in sorted(set(paths))})
        for name in ('model', 'feedback'):
            argv = [sys.executable, '-B', HERE / name / 'run_validation.py',
                    '--source', source, '--output', output / name, '--tcl', runtime['executable'],
                    '--runtime-manifest', args.runtime_manifest.resolve()]
            if name == 'feedback':
                argv += ['--cc', compiler]
            retained.run_command(argv, name, output, commands, timeout=300)
        after = verify_prior()
        write_json(output / 'preservation-after.json', after)
        if not after['ok']:
            raise ValueError('Prior evidence changed during experiments')
        write_json(output / 'completion.json', {'status': 'VERIFIED',
            'experiments': ['source-locked yaw magnitude selector', 'paced negative X feedback and diagnostic queue settlement'],
            'prior_files_preserved': after['files_checked'],
            'limits': 'Synthetic single-axis fixture; queue settlement is distinct from physical vehicle stability; not Phase7, descent or landing'})
        print('Milestone 3 validation records: ' + str(output))
    except Exception as error:
        write_json(output / 'failure.json', {'status': 'FAILED or incomplete', 'error': str(error)})
        raise


if __name__ == '__main__':
    main()
