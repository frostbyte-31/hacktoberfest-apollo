"""Run a bounded readiness probe and active-model component checks in new scratch output."""
from pathlib import Path
import subprocess,sys,json,hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def main():
 source=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
 commands=[]
 def run(cmd,name):
  with (out/(name+'.stdout')).open('w') as stdout,(out/(name+'.stderr')).open('w') as stderr:
   p=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=stdout,stderr=stderr)
  commands.append({'command':[str(x) for x in cmd],'cwd':str(ROOT),'exit':p.returncode})
  (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  if p.returncode:raise RuntimeError(f'{name}: {p.returncode}')
 files=[source/'yaAGC'/f for f in ['wasm.c','agc_engine.c','agc_engine_init.c','agc_utilities.c','ringbuffer_api.c','ringbuffer.c','rfopen.c']]
 run(['gcc','-O2','-I'+str(source/'yaAGC'),HERE/'control_probe.c',*files,'-lm','-o',out/'control_probe'],'build')
 rope=ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin'
 for name in ['probe','repeat']:run([out/'control_probe',rope,HERE/'probe_inputs.txt'],name)
 run(['nix','shell','nixpkgs#tcl','-c','tclsh',HERE/'simulator_component.tcl',source],'component')
 hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rope,HERE/'control_probe.c',HERE/'probe_inputs.txt',HERE/'simulator_component.tcl',*files]}
 (out/'inputs_source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
 print(json.dumps(commands,indent=2))
if __name__=='__main__':main()