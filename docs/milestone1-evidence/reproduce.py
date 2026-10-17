#!/usr/bin/env python3
"""GPL-2.0-or-later. Rebuild and replay the retained single-axis demonstration."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PHASE6 = ROOT / 'docs/phase6-evidence'
PHASE5 = ROOT / 'docs/phase5-evidence'
ENGINE_FILES = ('wasm.c', 'agc_engine.c', 'agc_engine_init.c',
                'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_source(archive_path, destination, expected):
    """Validate every regular-file member before writing any extracted source."""
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Source bundle inventory mismatch')
        data = {}
        for member in members:
            name = Path(member.name)
            if not member.isfile() or name.is_absolute() or '..' in name.parts:
                raise ValueError('Unsafe source bundle member')
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != expected[member.name]:
                raise ValueError('Source member hash mismatch: ' + member.name)
            data[member.name] = content
    destination.mkdir()
    for name, content in data.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def validate_output(output, root=ROOT):
    output, root = output.resolve(), root.resolve()
    if output.exists():
        raise ValueError('Output already exists; use a new directory')
    if output == root or root in output.parents:
        # Keep the boundary lexical after resolving the destination. Otherwise
        # a .build symlink into retained evidence would authorize that evidence.
        allowed = root / '.build'
        if output != allowed and allowed not in output.parents:
            raise ValueError('Use .build or external scratch; retained evidence is read-only')
        if output == allowed:
            raise ValueError('Use a new subdirectory inside .build')
    return output


def run_command(argv, label, output, commands, timeout=180):
    argv = list(map(str, argv))
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with (output / (label + '.stdout')).open('w') as stdout, (output / (label + '.stderr')).open('w') as stderr:
        try:
            process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stdout,
                                       stderr=stderr, start_new_session=True)
        except OSError as error:
            stderr.write(str(error) + '\n')
            code = 'LAUNCH_ERROR'
        else:
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                code = 'TIMEOUT'
    commands.append({'argv': argv, 'cwd': str(ROOT), 'start_utc': start,
        'end_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'exit': code, 'timeout_seconds': timeout})
    write_json(output / 'commands.json', commands)
    if code != 0:
        raise RuntimeError(label + ' failed: ' + str(code) + '; see preserved stderr')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runtime-manifest', type=Path,
                        default=ROOT / '.build/reproducibility/runtime-manifest.json')
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = parser.parse_args()
    proposed = args.output or ROOT / '.build/reproducibility/runs' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    output = validate_output(proposed)
    output.mkdir(parents=True)
    commands = []
    try:
        run_command([sys.executable, HERE / 'evidence.py', 'verify',
                     '--output', output / 'retained-integrity.json'], 'integrity', output, commands)
        bootstrap = load_module('locked_runtime', ROOT / 'tools/reproducibility/bootstrap_runtime.py')
        runtime = bootstrap.validate_runtime(args.runtime_manifest.resolve())
        tcl = Path(runtime['executable'])
        compiler = shutil.which(args.cc)
        if compiler is None:
            raise RuntimeError('Missing C compiler: ' + args.cc)
        archive = PHASE6 / 'corresponding-source.tar.gz'
        expected = json.loads((PHASE6 / 'corresponding-source-hashes.json').read_text())
        source = output / 'source'
        extract_source(archive, source, expected)
        write_json(output / 'environment.json', {'platform': platform.platform(),
            'python': sys.version, 'python_executable': sys.executable,
            'launcher_argv': sys.argv, 'cwd': str(Path.cwd()),
            'runtime_manifest': str(args.runtime_manifest.resolve()),
            'runtime_manifest_sha256': digest(args.runtime_manifest), 'runtime': runtime,
            'compiler': compiler, 'upstream_revision': 'f577e3fd917866c59334e6cdd32504f09df76f60',
            'scope': 'retained native single-axis feedback; no new mission experiment'})
        inputs = [PHASE5 / name for name in ('plant_bridge.c', 'plant_server.tcl',
                  'run_loop.py', 'operate_inputs.txt')]
        inputs += [HERE / 'run_loop_with_tcl.py', HERE / 'reproduce.py',
                   HERE / 'evidence.py', HERE / 'baseline.json', HERE / 'missing-historical.json',
                   ROOT / 'tools/reproducibility/bootstrap_runtime.py',
                   ROOT / 'tools/reproducibility/runtime-lock.json',
                   PHASE6 / 'demonstrate.py', archive,
                   ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin']
        inputs += [source / name for name in expected]
        write_json(output / 'inputs_source_hashes.json', {str(p): digest(p) for p in inputs})
        write_json(output / 'initial_conditions.json', {
            'schedule': (PHASE5 / 'operate_inputs.txt').read_text(),
            'reset': 'Fresh cpu_reset and Tcl plant per run; no memory patches',
            'model': 'Unchanged upstream LM-7 defaults; yaw/X-CDU only',
            'coupling_cpu_calls': 853, 'cycle_seconds': 0.00001172,
            'modes': ['closed', 'feedback_off', 'closed replay'],
            'dependency_adapter': 'Only replaces exact legacy Nix Tcl launch with locked Tcl executable'})
        run_command([compiler, '--version'], 'compiler-version', output, commands)
        engine = source / 'yaAGC'
        library = output / 'engine.so'
        run_command([compiler, '-shared', '-fPIC', '-O2', '-I' + str(engine),
            PHASE5 / 'plant_bridge.c', *[engine / f for f in ENGINE_FILES],
            '-lm', '-o', library], 'build', output, commands)
        write_json(output / 'binary_hashes.json', {'engine.so': digest(library),
                   'tcl_executable': digest(tcl)})
        for name in ('closed', 'feedback_off', 'repeat'):
            run_command([sys.executable, HERE / 'run_loop_with_tcl.py', '--tcl', tcl,
                '--source', source, '--library', library, '--output', output / (name + '.jsonl'),
                '--mode', 'closed' if name == 'repeat' else name,
                '--launch-record', output / (name + '.launch.json')], name, output, commands)
        demo = load_module('retained_phase6_analysis', PHASE6 / 'demonstrate.py')
        demo.summarize(output)
        comparison = {}
        for name in ('closed', 'feedback_off', 'repeat'):
            reference = PHASE6 / 'demo-run' / (name + '.jsonl')
            fresh = output / (name + '.jsonl')
            comparison[name] = {'fresh_sha256': digest(fresh),
                'retained_sha256': digest(reference),
                'retained_reference': str(reference.relative_to(ROOT)),
                'byte_identical': fresh.read_bytes() == reference.read_bytes()}
        write_json(output / 'retained-trace-comparison.json', comparison)
        if not all(row['byte_identical'] for row in comparison.values()):
            raise ValueError('Fresh trace differs from retained baseline; inspect raw evidence')
        run_command([sys.executable, HERE / 'evidence.py', 'verify',
                     '--output', output / 'preservation-after.json'], 'preservation-after', output, commands)
        write_json(output / 'completion.json', {'status': 'VERIFIED', 'runs': 3,
            'replay': 'byte-identical', 'retained_raw_trace_agreement': True,
            'integration': 'unchanged Phase5 runner/model; explicit Tcl dependency adapter',
            'limits': 'Synthetic yaw only; not Phase7, powered descent, or landing'})
        print('Fresh reproduction verified: ' + str(output))
    except Exception as error:
        write_json(output / 'failure.json', {'status': 'FAILED or incomplete', 'error': str(error)})
        raise


if __name__ == '__main__':
    main()
