"""Build the unmodified pinned engine and execute bounded feedback controls."""
from pathlib import Path
import subprocess, sys, json, hashlib
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    source, output = map(lambda p: Path(p).resolve(), sys.argv[1:])
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    def run(cmd, name):
        cmd = [str(x) for x in cmd]
        with (output / (name + '.stdout')).open('w') as f, (output / (name + '.stderr')).open('w') as e:
            result = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=e)
        commands.append({'command': cmd, 'cwd': str(ROOT), 'exit': result.returncode})
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode: raise RuntimeError(name)
    engine = source / 'yaAGC'
    files = [engine / f for f in ['wasm.c', 'agc_engine.c', 'agc_engine_init.c', 'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c']]
    run(['gcc', '-shared', '-fPIC', '-O2', '-I' + str(engine), HERE / 'plant_bridge.c', *files, '-lm', '-o', output / 'engine.so'], 'build')
    for mode in ['closed', 'feedback_off', 'blocked', 'negative', 'repeat']:
        run(['python3', HERE / 'run_loop.py', source, output / 'engine.so', output / (mode + '.jsonl'), 'closed' if mode == 'repeat' else mode], mode)
    paths = [*files, HERE / 'plant_bridge.c', HERE / 'plant_server.tcl', HERE / 'run_loop.py', HERE / 'run_loop_validation.py', HERE / 'operate_inputs.txt', ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin', source / 'Contributed/LM_Simulator/lm_simulator.tcl', source / 'Contributed/LM_Simulator/modules/AGC_IMU.tcl', source / 'Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl']
    (output / 'inputs_source_hashes.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n')

if __name__ == '__main__': main()