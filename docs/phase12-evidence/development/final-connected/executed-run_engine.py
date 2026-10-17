#!/usr/bin/env python3
"""Original P63 continuation, initially into a disconnected diagnostic sink.

No flight-memory setter, restored core, instruction patch or fabricated output.
Reuses sealed Phase10 startup/alignment/P27 and the Phase11 read-only observer.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


EXTRA = {'THRUST': 1, 'PIF': 2, 'PSEUDO55': 1, 'FC': 2, 'FP': 2,
         'FCOLD': 1, 'FWEIGHT': 2, '/AFC/': 2, 'ABDELV': 1,
         'MASS': 2, 'L*WCR*T': 1, 'H*GHCR*T': 1, 'LOWCRIT': 1, 'HIGHCRIT': 1,
         'LEMMASS': 1, 'DAPDATR1': 1, 'DAPBOOLS': 1, 'FLGWRD10': 1,
         'FMAXPOS': 2, 'FMAXODD': 2, 'TTHROT': 1, 'FLAGWRD0': 1,
         'FLAGWRD1': 1, 'FLAGWRD4': 1, 'FLAGWRD5': 1, 'FLAGWRD8': 1,
         'R1S':6,'V1S':6,'DVTHRUSH':1,'DVCNTR':1,'OVFIND':1,'GDT1/2':6}
CHECKPOINTS = ['ASTNRETN', 'R51P63', 'R60LEM', 'P63SPOT3', 'P63SPOT4',
               'BURNBABY', 'P40AUTO', 'ENGINOF3', 'MIDTOAV1', 'READACCS',
               'IGNITION', 'P63IGN', 'P63ZOOM', 'FLATOUT', 'THROTTLE',
               'DOIT', 'THROTRET', 'SERVICER', 'SERVEXIT', 'MUNRETRN','COPYCYC2','GDUMP1']


def build(p11, p10, source, table, output):
    addresses, checkpoints = p11.build(p10, source, table, output)
    mapping = json.loads((output/'observer-map.json').read_text())
    snapshot = mapping['snapshot_addresses']
    sizes = dict(p10.EXTRA, **p11.EXTRA)
    missing = []
    for name, size in EXTRA.items():
        if name not in table:
            missing.append(name)
            continue
        address = p10.p9.address(table[name])
        if address is None:
            missing.append(name+' (fixed rope constant, not erasable)')
            continue
        addresses[name] = address
        sizes[name] = size
        for address in range(addresses[name], addresses[name]+size):
            if address not in snapshot:
                snapshot.append(address)
    for name in CHECKPOINTS:
        if name not in table:
            missing.append(name)
            continue
        symbol = table[name]
        z = symbol.get('sRegister', symbol.get('value'))
        checkpoints[name] = [symbol.get('fixedBank', 2 if z < 0o6000 else 3), z]
    watches = sorted(set(mapping['watch_addresses']+[addresses['THRUST']]))
    arrays = {'p9_snapshot_addresses': snapshot, 'p9_watch_addresses': watches,
              'p9_checkpoint_banks': [v[0] for v in checkpoints.values()],
              'p9_checkpoint_z': [v[1] for v in checkpoints.values()]}
    header = '#define P9_WATCH_COUNT {}\n#define P9_CHECKPOINT_COUNT {}\n#define P9_SNAPSHOT_COUNT {}\n'.format(len(watches), len(checkpoints), len(snapshot))
    header += '\n'.join('static const unsigned {}[] = {{{}}};'.format(k, ','.join(map(str, v))) for k, v in arrays.items())+'\n'
    (output/'p9_watch.h').write_text(header)
    save(output/'observer-map.json', {'addresses': addresses, 'snapshot_addresses': snapshot,
          'watch_addresses': watches, 'checkpoints': checkpoints, 'sizes': sizes,
          'optional_symbols_missing': missing})
    interpreted=['CALCRVG','MUNRVG','LUNLAND','MIDTOAV1','MIDTOAV2','MUNRETRN','COPYCYC2']
    for name in interpreted:
        symbol=table[name];checkpoints[name]=[symbol['fixedBank'],symbol['sRegister']]
    # Regenerate with interpreted entries present in the same ordered map.
    arrays['p9_checkpoint_banks']=[v[0] for v in checkpoints.values()]
    arrays['p9_checkpoint_z']=[v[1] for v in checkpoints.values()]
    header='#define P9_WATCH_COUNT {}\n#define P9_CHECKPOINT_COUNT {}\n#define P9_SNAPSHOT_COUNT {}\n'.format(len(watches),len(checkpoints),len(snapshot))
    header+='\n'.join('static const unsigned {}[] = {{{}}};'.format(k,','.join(map(str,v))) for k,v in arrays.items())+'\n'
    (output/'p9_watch.h').write_text(header)
    save(output/'observer-map.json',{'addresses':addresses,'snapshot_addresses':snapshot,'watch_addresses':watches,'checkpoints':checkpoints,'sizes':sizes,'optional_symbols_missing':missing})
    newops=table['NEWOPS']['value']
    dispatch={'NEWOPS_BANK':3,'NEWOPS_Z':newops,'LOC':addresses['LOC'],'BANKSET':addresses['BANKSET'],'INTERPRETED_COUNT':len(interpreted)}
    h=''.join('#define P12_{} {}\n'.format(k,v) for k,v in dispatch.items())
    for key,values in [('bank',[table[n]['fixedBank'] for n in interpreted]),('z',[table[n]['sRegister'] for n in interpreted]),('index',[list(checkpoints).index(n) for n in interpreted])]:
        h+='static const unsigned p12_interpreted_{}[] = {{{}}};\n'.format(key,','.join(map(str,values)))
    (output/'p12_dispatch.h').write_text(h)
    command = json.loads((output/'phase11-observer-build.json').read_text())['argv']
    command[command.index(str(p11.HERE/'pipa_bridge.c'))]=str(HERE/'engine_bridge.c')
    with (output/'build.stdout').open('a') as out, (output/'build.stderr').open('a') as err:
        result = subprocess.run(command, stdout=out, stderr=err)
    save(output/'phase12-observer-build.json', {'argv': command, 'exit': result.returncode})
    if result.returncode:
        raise ValueError('Phase12 read-only observer build failed')
    return addresses, checkpoints, sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case',choices=['sink','connected','no-feedback'],default='sink')
    parser.add_argument('--plant-source',type=Path)
    parser.add_argument('--tcl',type=Path)
    parser.add_argument('--runtime-manifest',type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT/'.build/phase12' not in output.parents:
        raise ValueError('Require a new output directory below .build/phase12')
    demo = load('p12_stage', ROOT/'tools/demo/demo.py')
    baseline = demo.stage_baseline(ROOT, output)
    run = output/'native'; run.mkdir()
    driver = None
    try:
        expected = json.loads((HERE/'prior_hashes.json').read_text())['sha256']
        def preserve():
            bad = [n for n,h in expected.items() if not (ROOT/n).is_file() or sha(ROOT/n) != h]
            if bad:
                raise ValueError('Prior files changed: '+repr(bad))
            return {'files_checked':len(expected),'changed_or_missing':bad}
        save(run/'preservation-before.json', preserve())
        sys.path.insert(0, str(baseline/'docs/phase9-evidence'))
        p10 = load('p12_original_mission', baseline/'docs/phase10-evidence/run_mission.py')
        p11 = load('p12_verified_pipa', ROOT/'docs/phase11-evidence/run_pipa.py')
        source, symbols, hashes = p10.p9.verified_setup(args.setup.resolve(), run)
        table = json.loads(symbols.read_text())['symbols']
        addresses, checkpoints, sizes = build(p11, p10, source, table, run)
        config = json.loads((baseline/'docs/phase10-evidence/configs/mission-15km.json').read_text())
        config['protocol_probe']=True
        Driver=load('p12_driver',HERE/'driver.py').driver_class(p10)
        driver = Driver(run, addresses, checkpoints, True, config=config)
        driver.all_addresses = {name:p10.p9.address(value) for name,value in table.items()}
        def state():
            return {n:[driver.lib.inspect_ram(addresses[n]+i) for i in range(size)] for n,size in sizes.items() if n in addresses and not n.startswith('VAC')}
        def stage(name):
            driver.emit('stage', name=name, state=driver.snapshot(), observed_words=state(),
                        channels={str(c):driver.lib.inspect_channel(c) for c in (0o11,0o14,0o30,0o31,0o32,0o33)})
        save(run/'execution.json', {'argv':sys.argv,'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
             'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':sha(Path(__file__)),
             'engine_sha256':sha(run/'engine.so'),'rope_sha256':p10.p9.ROPE_SHA,
             'scope':'SYNTHETIC stationary fixture; actual P63 commands into disconnected sink; no thrust model'})
        paths=[HERE/n for n in ('run_engine.py','driver.py','engine_bridge.c','propulsion.py','legacy_engine.tcl')]
        save(run/'phase12-code.json',{str(p.relative_to(ROOT)):sha(p) for p in paths})
        for p in paths:shutil.copyfile(p,run/('executed-'+p.name))
        try:p10.p9.execute(driver)
        except p10.ProbeComplete:pass
        driver.keys('V48E');driver.display('01','46')
        stage('original-DAP-config-review')
        driver.keys('V21N46E');driver.display('21','46');driver.keys('20000E')
        driver.display('01','46');driver.keys('V33E');driver.display('06','47')
        driver.keys('V21N47E');driver.display('21','47');driver.keys('+33069E')
        driver.display('06','47');driver.keys('V33E');driver.display('06','48')
        driver.keys('V34E');driver.step(100000);stage('original-mass-load-complete')
        driver.keys('V37E63E')
        driver.step(config['post_selection_horizon_cpu_calls'])
        stage('phase10-V06N61')
        if args.plant_source or args.tcl:
            if not args.plant_source or not args.tcl:
                raise ValueError('Both verified plant source and Tcl are required')
            physical=load('p12_propulsion',HERE/'propulsion.py')
            sensor=load('p12_sensor',ROOT/'docs/phase11-evidence/pipa_sensor.py')
            from fractions import Fraction
            def dp(words):
                return sum((-(0o77777-w) if w&0o40000 else w)*Fraction(1,2**(14*(i+1))) for i,w in enumerate(words))
            refs=driver.snapshot()['refsmmat']
            rotation=[[float(2*dp(refs[6*i+2*j:6*i+2*j+2])) for j in range(3)] for i in range(3)]
            # CDUs remain zero: body-to-SM is identity; transpose maps to REF.
            matrix=[[rotation[j][i] for j in range(3)] for i in range(3)]
            qw=math.sqrt(1+sum(matrix[i][i] for i in range(3)))/2
            q=[qw,(matrix[2][1]-matrix[1][2])/(4*qw),(matrix[0][2]-matrix[2][0])/(4*qw),(matrix[1][0]-matrix[0][1])/(4*qw)]
            norm=math.sqrt(sum(x*x for x in q));q=[x/norm for x in q]
            geometry=config['synthetic_geometry'];inputs=geometry['input_candidates']
            mass=float(dp(state()['MASS'])*2**16)
            driver.plant=physical.PropulsionPlant(source=args.plant_source,tcl=args.tcl,
                runtime_manifest=args.runtime_manifest,
                position_ref_m=inputs['RRECTLEM']['encoded_si_readback'],
                velocity_ref_m_s=inputs['VRECTLEM']['encoded_si_readback'],
                quaternion_body_to_ref=q,mass_kg=mass,fuel_kg=mass-6804,
                connected=args.case!='sink',mu_m3_s2=geometry['mu_m3_s2'])
            driver.receiver=physical.DpsReceiver()
            now_cs=float(dp(state()['TIME2'])*2**28)
            remaining=now_cs/100-geometry['state_epoch_cs']/100
            while remaining>1e-12:
                dt=min(.01,remaining)
                initial=driver.plant.step(dt,enabled=False,thrust_n=0)
                remaining-=dt
            driver.last_plant_cycle=driver.cycle
            driver.sensor=sensor.PipaSensor(start_cycle=driver.cycle,inertial_to_stable=rotation)
            driver.feedback=args.case=='connected'
            driver.emit('plant_initialization',case=args.case,telemetry=initial,
                        initialization_epoch_cs=geometry['state_epoch_cs'],current_clock_cs=now_cs,
                        refs_to_stable=rotation,initial_mass_kg=mass,initial_fuel_kg=mass-6804,
                        physical_provenance=driver.plant.engine.provenance,
                        classification='SYNTHETIC engine plant, fixed measured CDU fixture; no achieved burn maneuver claimed')
        elif args.case!='sink':
            raise ValueError('Connected experiments require the verified existing plant')
        driver.keys('V33E')
        driver.display('50','25')
        driver.wait('original R51 checklist14 displayed',lambda:driver.decoder.snapshot()['R1']=='00014')
        stage('R51-checklist')
        driver.keys('E')
        driver.display('50','18', limit=1000000)
        stage('R60-crew-attitude-review')
        driver.keys('E')
        driver.step(100000)
        stage('after-attitude-review')
        # Real external switch settings, active-low, never internal flags.
        # Auto throttle, engine armed, G+N control, ATT MODE AUTO.
        for channel, clear in ((0o30, (1<<2)|(1<<4)|(1<<9)), (0o31,1<<13), (0o33,1<<5)):
            driver.packet(channel, driver.lib.inspect_channel(channel) & (0o77777 ^ clear),
                          'documented synthetic crew switch setting')
        driver.step(21333)
        if driver.receiver:
            driver.receiver.set_hardware(armed=not(driver.lib.inspect_channel(0o30)&4),
                                         autothrottle=not(driver.lib.inspect_channel(0o30)&0o20))
        stage('crew-switches-set')
        # Original P40AUTO/radar checklist, when presented: normal PROCEED.
        for _ in range(3):
            d = driver.decoder.snapshot()
            if d['VERB']=='50' and d['NOUN']=='25':
                stage('crew-switch-checklist')
                driver.keys('V33E')
                driver.step(100000)
        stage('preignition-wait')
        driver.display('99','62',limit=16000000)
        stage('original-engine-enable-request')
        driver.keys('V33E')
        driver.step(3000000)
        stage('bounded-post-enable-horizon')
        driver.emit('finish', state=driver.snapshot(), observed_words=state())
        save(run/'completion.json', {'cycle':driver.cycle,'state':driver.snapshot(),'observed_words':state()})
        save(run/'preservation-after.json', preserve())
        save(run/'original-preservation-after.json',p10.preserve())
        changed=[n for n,h in hashes.items() if sha(source/n)!=h]
        save(run/'source-integrity/after-execution.json',{'files_checked':len(hashes),'changed_or_missing':changed})
        if changed:
            raise ValueError('Pinned source changed')
        print(json.dumps({'cycle':driver.cycle,'state':driver.snapshot()}))
    except BaseException as error:
        save(run/'failure.json',{'error':repr(error)})
        if driver:driver.emit('failure',error=repr(error),state=driver.snapshot())
        raise
    finally:
        if driver:
            if driver.plant:driver.plant.close()
            driver.trace.close()
            save(run/'trace-sha256.json',{'sha256':sha(run/'trace.jsonl'),'bytes':(run/'trace.jsonl').stat().st_size})


if __name__=='__main__':main()
