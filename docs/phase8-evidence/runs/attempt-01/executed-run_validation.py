#!/usr/bin/env python3
"""GPL-2.0-or-later. Phase 5 unchanged startup plus only V37E63E.

Fresh native processes, pinned ringbuffer backend, read-only observers. Outputs
must go to a new scratch directory; this runner never replaces earlier evidence.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = 'f577e3fd917866c59334e6cdd32504f09df76f60'
ENGINE_FILES = ('wasm.c','agc_engine.c','agc_engine_init.c','agc_utilities.c',
                'ringbuffer_api.c','ringbuffer.c','rfopen.c')
KEYS = [('V',17),('3',3),('7',7),('E',28),('6',6),('3',3),('E',28)]
P63_START = 2200000
KEY_SPACING = 21333

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def schedules():
    original = (ROOT/'docs/phase5-evidence/operate_inputs.txt').read_text()
    rows = [tuple(map(int,row.split())) for row in original.splitlines()[1:]]
    added = [(P63_START+i*KEY_SPACING,0o15,key) for i,(_,key) in enumerate(KEYS)]
    p63 = original.splitlines()[0]+'\n'+''.join(f'{t} {c} {v}\n' for t,c,v in sorted(rows+added))
    return original,p63

def read_trace(path):
    return [json.loads(row) for row in path.read_text().splitlines()]

def summarize(path):
    rows=read_trace(path)
    states=[r for r in rows if r['ev'] in ('sample','state')]
    alarms=[];prior=None
    for row in states:
        if row['failreg']!=prior:
            alarms.append({'cycle':row['cycle'],'failreg':row['failreg']})
            prior=row['failreg']
    throttle=[r for r in rows if r['ev']=='output' and r['channel']==0o14]
    thrust=[];prior=None
    for row in states:
        if row['thrust']!=prior:
            thrust.append({'cycle':row['cycle'],'thrust':row['thrust']})
            prior=row['thrust']
    return {'raw_sha256':digest(path),'rows':len(rows),'last_state':states[-1],
            'first_p63':next((r['cycle'] for r in states if r['modreg']==0o63),None),
            'alarm_changes':alarms,'channel014_outputs':throttle,'thrust_changes':thrust,
            'nonzero_rcs_outputs':sum(r['ev']=='output' and r['channel'] in (5,6) and bool(r['value']) for r in rows)}

def validate(output):
    baseline=read_trace(output/'baseline.stdout');p63=read_trace(output/'p63.stdout')
    replay=read_trace(output/'repeat.stdout')
    original,selected=schedules()
    added=[{'ev':'input','cycle':P63_START+i*KEY_SPACING,'channel':0o15,'value':key,'accepted':1}
           for i,(_,key) in enumerate(KEYS)]
    base_inputs=[r for r in baseline if r['ev']=='input']
    p63_inputs=[r for r in p63 if r['ev']=='input']
    checks={
        'original_phase5_schedule_byte_identical':(output/'baseline.inputs.txt').read_text()==original,
        'only_added_input_is_v37e63e':p63_inputs==sorted(base_inputs+added,key=lambda r:r['cycle']),
        'startup_trace_unchanged_before_addition':[r for r in baseline if r.get('cycle',0)<P63_START]==[r for r in p63 if r.get('cycle',0)<P63_START],
        'fresh_phase5_probe_matches_retained_operate_trace':(output/'phase5-operate.stdout').read_bytes()==(ROOT/'docs/phase5-evidence/runs/operate.stdout').read_bytes(),
        'exact_fresh_process_replay':p63==replay and (output/'p63.stdout').read_bytes()==(output/'repeat.stdout').read_bytes(),
        'no_external_ram_writes':all(rows[0]['ram_writes']==0 for rows in (baseline,p63,replay)),
        'no_counter_operation_inputs':all(not r['channel']&128 for r in p63_inputs),
    }
    result={'checks':checks,'all_pass':all(checks.values()),'baseline':summarize(output/'baseline.stdout'),
            'p63':summarize(output/'p63.stdout'),'repeat':summarize(output/'repeat.stdout')}
    write_json(output/'validation.json',result)
    if not result['all_pass']:
        raise RuntimeError('Failed checks: '+', '.join(k for k,v in checks.items() if not v))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--checkpoints',type=Path,default=HERE/'checkpoints.txt')
    parser.add_argument('--cc',default='cc')
    args=parser.parse_args()
    source,output=args.source.resolve(),args.output.resolve()
    if output.exists():raise ValueError('Refusing to overwrite a prior run')
    if ROOT in output.parents and ROOT/'.build' not in output.parents:
        raise ValueError('Use .build/ or a new external scratch directory')
    output.mkdir(parents=True)
    expected=json.loads((ROOT/'docs/phase6-evidence/corresponding-source-hashes.json').read_text())
    for name,sha in expected.items():
        if digest(source/name)!=sha:raise ValueError('Pinned source mismatch: '+name)
    commands=[]
    def run(argv,name):
        argv=list(map(str,argv));start=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (output/(name+'.stdout')).open('w') as out,(output/(name+'.stderr')).open('w') as err:
            try:code=subprocess.run(argv,cwd=ROOT,stdout=out,stderr=err,timeout=180).returncode
            except subprocess.TimeoutExpired:code='TIMEOUT'
            except OSError as error:err.write(str(error)+'\n');code='LAUNCH_ERROR'
        commands.append({'argv':argv,'cwd':str(ROOT),'start_utc':start,'end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':code})
        write_json(output/'commands.json',commands)
        if code!=0:raise RuntimeError(f'{name}: {code}')
    rope=ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin'
    engine=source/'yaAGC';files=[engine/name for name in ENGINE_FILES]
    inputs=[rope,HERE/'p63_probe.c',HERE/'run_validation.py',args.checkpoints,
            ROOT/'docs/phase5-evidence/readiness_probe.c',ROOT/'docs/phase5-evidence/operate_inputs.txt',
            *[source/name for name in expected]]
    write_json(output/'input_source_hashes.json',{str(p):digest(p) for p in inputs})
    shutil.copy2(HERE/'p63_probe.c',output/'executed-p63_probe.c')
    shutil.copy2(HERE/'run_validation.py',output/'executed-run_validation.py')
    shutil.copy2(args.checkpoints,output/'checkpoints.txt')
    write_json(output/'environment.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'platform':platform.platform(),'python':sys.version,'source_revision':REVISION,
        'repository_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'engine_backend':'pinned ringbuffer','engine_seconds_per_cpu_call':12/1024000,
        'initialization':'fresh cpu_reset/set_fixed; original Phase5 operate_inputs unchanged',
        'vehicle_model':False,'external_erasable_writes':0,
        'p63_keys':[(P63_START+i*KEY_SPACING,name,key) for i,(name,key) in enumerate(KEYS)]})
    run([args.cc,'--version'],'compiler-version')
    run([args.cc,'-O2','-I'+str(engine),HERE/'p63_probe.c',*files,'-lm','-o',output/'p63_probe'],'build')
    run([args.cc,'-O2','-I'+str(engine),ROOT/'docs/phase5-evidence/readiness_probe.c',*files,'-lm','-o',output/'phase5_probe'],'phase5-build')
    write_json(output/'binary_hashes.json',{'p63_probe':digest(output/'p63_probe'),'phase5_probe':digest(output/'phase5_probe')})
    original,p63=schedules()
    for name,data in [('baseline',original),('p63',p63),('repeat',p63)]:
        schedule=output/(name+'.inputs.txt');schedule.write_text(data)
        run([output/'p63_probe',rope,schedule,output/'checkpoints.txt'],name)
    run([output/'phase5_probe',rope,ROOT/'docs/phase5-evidence/operate_inputs.txt'],'phase5-operate')
    result=validate(output)
    write_json(output/'completion.json',{'status':'VERIFIED reproducibility controls','checks':len(result['checks']),
                                      'all_pass':result['all_pass'],'native_executions':4})
    print(json.dumps({'output':str(output),'checks':result['checks'],'p63':result['p63']},indent=2))

if __name__=='__main__':main()
