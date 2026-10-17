"""Reproduce Phase 4 and test only an active-low IMU-operate correction.

GPL-2.0-or-later. No flight-state writes or generated sensor packets.
"""
from pathlib import Path
import subprocess, sys, json, hashlib, platform, datetime
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    source = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands = []
    def run(cmd, name):
        cmd = [str(x) for x in cmd]
        with (out / (name + '.stdout')).open('w') as stdout, (out / (name + '.stderr')).open('w') as stderr:
            proc = subprocess.run(cmd, cwd=ROOT, stdout=stdout, stderr=stderr)
        commands.append({'command': cmd, 'cwd': str(ROOT), 'exit': proc.returncode})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if proc.returncode:
            raise RuntimeError(f'{name}: {proc.returncode}')
    files = [source / 'yaAGC' / f for f in ['wasm.c', 'agc_engine.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c']]
    rope = ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin'
    run(['gcc', '--version'], 'gcc_version')
    run(['gcc', '-O2', '-I' + str(source / 'yaAGC'), HERE / 'readiness_probe.c', *files, '-lm', '-o', out / 'readiness_probe'], 'build')
    for name in ['baseline', 'operate', 'repeat', 'off']:
        schedule = HERE / (('operate' if name == 'repeat' else name) + '_inputs.txt')
        run([out / 'readiness_probe', rope, schedule], name)
    paths = [rope, HERE / 'readiness_probe.c', HERE / 'run_validation.py', *HERE.glob('*_inputs.txt'), *files]
    (out / 'inputs_source_hashes.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n')
    (out / 'environment.json').write_text(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'python': sys.version, 'platform': platform.platform(), 'source_revision': 'f577e3fd917866c59334e6cdd32504f09df76f60'}, indent=2) + '\n')
    print(json.dumps(commands, indent=2))

if __name__ == '__main__':
    main()