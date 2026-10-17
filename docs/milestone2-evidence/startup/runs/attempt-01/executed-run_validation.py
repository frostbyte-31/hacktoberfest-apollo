#!/usr/bin/env python3
"""GPL-2.0-or-later. Bounded native startup comparisons, without flight-state writes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = 'f577e3fd917866c59334e6cdd32504f09df76f60'
ENGINE_FILES = ('wasm.c', 'agc_engine.c', 'agc_engine_init.c', 'agc_utilities.c',
                'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')

def schedules():
    legacy = (ROOT / 'docs/phase5-evidence/operate_inputs.txt').read_text()
    rows = [list(map(int, line.split())) for line in legacy.splitlines()[1:]]
    def make(v37, v36=True, off=False):
        data = []
        for tick, channel, value in rows:
            if not v36 and 426665 <= tick <= 490664:
                continue
            if 1000000 <= tick <= 1127998:
                tick += v37 - 1000000
            # No V77 nor RHC stimulus: pure stationary startup/P00 experiment.
            elif tick >= 1600000:
                continue
            if off and tick == 100001:
                value = 15871
            data.append((tick, channel, value))
        return '2200000\n' + ''.join(f'{t} {c} {v}\n' for t,c,v in sorted(data))
    return {'legacy': make(1000000), 'delayed': make(1600000),
            'repeat': make(1600000), 'without_v36': make(1600000, v36=False),
            'imu_off': make(1600000, off=True),
            'v37_before_ready': make(1300000),
            'v37_after_ready': make(1500000)}

def read_trace(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def summarize(path):
    rows = read_trace(path)
    states = [r for r in rows if r['ev'] in ('sample', 'state')]
    mode = [r for r in states if r['modreg'] == 0 and r['cycle'] > 500000]
    alarms = []
    for row in rows:
        if row['ev'] == 'state' and any(row['failreg']):
            alarms.append({'cycle': row['cycle'], 'failreg': row['failreg']})
    return {'status': 'VERIFIED observations', 'raw_sha256': digest(path),
            'first_modreg_p00_after_v36': mode[0]['cycle'] if mode else None,
            'first_issup_clear': next((r['cycle'] for r in rows if r['ev']=='before'
                and r['bank']==6 and r['z']==0o2327 and not r['imodes33'] & 32), None),
            'first_startdap': next((r['cycle'] for r in rows if r['ev']=='before'
                and r['bank']==0o16 and r['z']==0o2046), None),
            'first_cantroo': next((r['cycle'] for r in rows if r['ev']=='before'
                and r['bank']==4 and r['z']==0o2065), None),
            'ptbad_cycles': [r['cycle'] for r in rows if r['ev']=='before'
                and r['bank']==5 and r['z']==0o3054],
            'alarms': alarms, 'last_state': states[-1],
            'nonzero_jet_words': sum(r['ev']=='output' and r['channel'] in (5,6)
                and r['value'] != 0 for r in rows)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite existing evidence')
    output.mkdir(parents=True)
    commands = []
    def run(argv, name):
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (output/(name+'.stdout')).open('w') as out, (output/(name+'.stderr')).open('w') as err:
            result = subprocess.run(list(map(str,argv)), cwd=ROOT, stdout=out, stderr=err, timeout=180)
        commands.append({'argv':list(map(str,argv)), 'cwd':str(ROOT), 'start_utc':start,
            'end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit':result.returncode})
        write_json(output/'commands.json',commands)
        if result.returncode:
            raise RuntimeError(f'{name}: {result.returncode}; inspect preserved stderr')
    engine = source/'yaAGC'
    rope = ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin'
    files = [engine/f for f in ENGINE_FILES]
    hashes = {str(p):digest(p) for p in [rope,HERE/'startup_probe.c',HERE/'run_validation.py',
              ROOT/'docs/phase5-evidence/operate_inputs.txt',*files,*sorted((HERE/'source').glob('*.agc'))]}
    write_json(output/'inputs_source_hashes.json',hashes)
    write_json(output/'initial_conditions.json', {'revision':REVISION,'rope_sha256':digest(rope),
        'reset':'fresh native process; cpu_reset zeros erasable; original entry Z=04000',
        'model':'stationary zero-angle; no vehicle integration or counter packets',
        'flight_state_writes':0,'clock_seconds_per_cpu_call':0.00001172,
        'first_input_cpu_call':100000,'v36_keys_cpu_calls':[426665,447998,469331,490664],
        'duration_cpu_calls':2200000,'environment':{'platform':platform.platform(),'python':sys.version}})
    run([args.cc,'--version'],'compiler-version')
    run([args.cc,'-O2','-I'+str(engine),HERE/'startup_probe.c',*files,'-lm','-o',output/'startup_probe'],'build')
    write_json(output/'binary_hashes.json',{'startup_probe':digest(output/'startup_probe')})
    summary = {}
    for name, data in schedules().items():
        path = output/(name+'.inputs.txt'); path.write_text(data)
        run([output/'startup_probe',rope,path],name)
        summary[name]=summarize(output/(name+'.stdout'))
    write_json(output/'summary.json',summary)
    replay = (output/'delayed.stdout').read_bytes() == (output/'repeat.stdout').read_bytes()
    write_json(output/'completion.json',{'native_runs':len(summary),'exact_replay':replay,
        'status':'VERIFIED' if replay else 'FAILED',
        'scope':'Cold restart alarm cause and source-observed readiness/P00, stationary single-axis prerequisite only'})
    if not replay:
        raise RuntimeError('Delayed startup replay differs')
    print(output)

if __name__ == '__main__':
    main()
