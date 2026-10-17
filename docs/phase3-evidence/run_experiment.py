"""Reproduce the limited native experiment into a NEW output directory."""
from pathlib import Path
import subprocess, sys, hashlib, json, platform

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
source = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=False)
env = {'platform': platform.platform(), 'python':sys.version,
       'utc':subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),
       'gcc':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0]}
(out/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
commands=[]
def run(cmd,name):
    with (out/(name+'.stdout')).open('w') as stdout, (out/(name+'.stderr')).open('w') as stderr:
        result=subprocess.run([str(c) for c in cmd],stdout=stdout,stderr=stderr,cwd=ROOT)
    commands.append({'command':[str(c) for c in cmd],'cwd':str(ROOT),'exit':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    if result.returncode: raise RuntimeError(f'{name} exited {result.returncode}')
exe=out/'gimbal_loop'
files=['wasm.c','agc_engine.c','agc_engine_init.c','agc_utilities.c','ringbuffer_api.c','ringbuffer.c','rfopen.c']
run(['gcc','-O2','-I'+str(source/'yaAGC'),HERE/'gimbal_loop.c',*[source/'yaAGC'/f for f in files],'-lm','-o',exe],'build')
rope=ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin'
for name,fixture,mode in [('positive','positive','closed'),('repeat','positive','closed'),('open','positive','open'),('blocked','positive','blocked'),('negative','negative','closed')]:
    run([exe,rope,HERE/(fixture+'_inputs.txt'),mode],name)
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rope,HERE/'gimbal_loop.c',HERE/'positive_inputs.txt',HERE/'negative_inputs.txt',*[source/'yaAGC'/f for f in files]]}
(out/'inputs_and_source_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'runs':len(commands)-1,'directory':str(out)}))