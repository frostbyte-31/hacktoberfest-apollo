#!/usr/bin/env python3
"""Bounded original P47 navigation experiment, after unchanged Phase10 P63.

Stages the sealed historical baseline so its original preservation guards run
unchanged. New code supplies hardware counter packets and read-only observers.
No flight-memory writes, saved cores, ignition inputs or instruction changes.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
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


def preserve():
    expected = json.loads((HERE/'prior_hashes.json').read_text())['sha256']
    changed = [name for name, digest in expected.items()
               if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
    if changed:
        raise ValueError('Earlier files changed: '+repr(changed))
    return {'files_checked': len(expected), 'changed_or_missing': changed}


EXTRA = {'PIPAX': 1, 'PIPAY': 1, 'PIPAZ': 1, 'DELV': 6,
         'PIPATMPX': 1, 'PIPATMPY': 1, 'PIPATMPZ': 1,
         'DELVREF': 6, 'DELVCTL': 6, 'DELVIMU': 6,
         'RN': 6, 'VN': 6, 'RN1': 6, 'VN1': 6,
         'PGUIDE': 2, 'PIPTIME': 2, 'PIPTIME1': 2, 'GDT/2': 6,
         'PIPASCF': 6, 'PIPABIAS': 6, 'AVEGEXIT': 2, 'FLAGWRD6': 1, 'FLAGWRD2': 1}
CHECKPOINTS = ['P47LM', 'MIDTOAV2', 'STARTP47', 'PREREAD', 'BIBIBIAS',
               'READACCS', 'PIPASR', 'SERVICER', 'CALCRVG', 'COPYCYCL',
               'CALCN83', 'SERVEXIT', 'PIPSDONE', 'CANTROO', 'POOH', 'GOMOD']


def build(p10, source, symbols, output):
    addresses, checkpoints = p10.build(source, symbols, output)
    mapping = json.loads((output/'observer-map.json').read_text())
    snapshot = mapping['snapshot_addresses']
    watches = set(mapping['watch_addresses'])
    for name, size in EXTRA.items():
        address = p10.p9.address(symbols[name])
        if address is None:
            raise ValueError('Missing original observer '+name)
        addresses[name] = address
        for a in range(address, address+size):
            if a not in snapshot:
                snapshot.append(a)
    for name in ('PIPAX', 'PIPAY', 'PIPAZ'):
        watches.add(addresses[name])
    for name in CHECKPOINTS:
        symbol = symbols[name]
        z = symbol.get('sRegister', symbol.get('value'))
        checkpoints[name] = [symbol.get('fixedBank', 2 if z < 0o6000 else 3), z]
    arrays = {'p9_snapshot_addresses': snapshot,
              'p9_watch_addresses': sorted(watches),
              'p9_checkpoint_banks': [v[0] for v in checkpoints.values()],
              'p9_checkpoint_z': [v[1] for v in checkpoints.values()]}
    header = '#define P9_WATCH_COUNT {}\n#define P9_CHECKPOINT_COUNT {}\n#define P9_SNAPSHOT_COUNT {}\n'.format(len(watches), len(checkpoints), len(snapshot))
    header += '\n'.join('static const unsigned {}[] = {{{}}};'.format(k, ','.join(map(str, v))) for k, v in arrays.items())+'\n'
    (output/'p9_watch.h').write_text(header)
    save(output/'observer-map.json', {'addresses': addresses, 'snapshot_addresses': snapshot,
                                      'watch_addresses': sorted(watches), 'checkpoints': checkpoints})
    newops_z = symbols['NEWOPS'].get('sRegister', symbols['NEWOPS'].get('value'))
    constants = {'NEWOPS_BANK': symbols['NEWOPS'].get('fixedBank', 2 if newops_z < 0o6000 else 3),
                 'NEWOPS_Z': newops_z,
                 'LOC': addresses['LOC'], 'BANKSET': addresses['BANKSET'],
                 'CALCRVG_Z': symbols['CALCRVG']['sRegister'],
                 'CALCRVG_BANK': symbols['CALCRVG']['fixedBank'],
                 'CALCRVG_INDEX': list(checkpoints).index('CALCRVG')}
    (output/'p11_dispatch.h').write_text(''.join('#define P11_{} {}\n'.format(k, v) for k, v in constants.items()))
    save(output/'interpretive-dispatch.json', constants)
    command = json.loads((output/'commands.json').read_text())[0]['argv']
    command[command.index(str(p10.p9.HERE/'hardware_bridge.c'))] = str(HERE/'pipa_bridge.c')
    command.insert(1, '-I'+str(p10.p9.HERE))
    with (output/'build.stdout').open('a') as out, (output/'build.stderr').open('a') as err:
        result = subprocess.run(command, stdout=out, stderr=err)
    save(output/'phase11-observer-build.json', {'argv': command, 'exit': result.returncode})
    if result.returncode:
        raise ValueError('Read-only observer build failed')
    return addresses, checkpoints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New .build/phase11 directory')
    parser.add_argument('--setup', type=Path, help='Existing verified prepare.py setup; reverified')
    parser.add_argument('--archive', type=Path, help='Pinned original source archive for fresh preparation')
    parser.add_argument('--case', choices=['zero', 'positive', 'negative', 'disconnected'], default='zero')
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = ROOT/'.build/phase11'
    if allowed not in output.parents:
        raise ValueError('Output must be a new directory below .build/phase11')
    driver = None
    demo = load('phase11_demo_staging', ROOT/'tools/demo/demo.py')
    snapshot = demo.stage_baseline(ROOT, output)
    run = output/'native'
    run.mkdir()
    try:
        save(run/'preservation-before.json', preserve())
        sys.path.insert(0, str(snapshot/'docs/phase9-evidence'))
        p10 = load('phase11_original_mission', snapshot/'docs/phase10-evidence/run_mission.py')
        if not p10.preserve()['ok']:
            raise ValueError('Original 4098-file preservation guard failed')
        setup = args.setup
        if setup is None:
            command = [sys.executable, '-B', str(snapshot/'docs/phase9-evidence/prepare.py'),
                       '--cache', str(output/'dependencies')]
            if args.archive:
                command += ['--archive', str(args.archive.resolve())]
            demo.run_logged(command, snapshot, output, 'prepare',
                            {'SOURCE_DATE_EPOCH': demo.SOURCE_DATE_EPOCH})
            setups = sorted((output/'dependencies/setups').glob('*/setup.json'))
            if len(setups) != 1:
                raise ValueError('Ambiguous prepared setup')
            setup = setups[0]
        source, symbols, source_hashes = p10.p9.verified_setup(setup.resolve(), run)
        table = json.loads(symbols.read_text())['symbols']
        addresses, checkpoints = build(p10, source, table, run)
        config = json.loads((snapshot/'docs/phase10-evidence/configs/mission-15km.json').read_text())
        save(run/'configuration.json', {'case': args.case, 'phase10': config,
             'scope': 'SYNTHETIC stationary instrument; P63 review then original P47; no ignition',
             'sensor_input': 'constant stable-member X specific force, 6 seconds, then 4 seconds settlement'})
        save(run/'execution.json', {'argv': sys.argv, 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'platform': platform.platform(), 'python': sys.version,
             'rope_sha256': p10.p9.ROPE_SHA, 'engine_sha256': sha(run/'engine.so'),
             'driver_sha256': sha(Path(__file__)), 'sensor_sha256': sha(HERE/'pipa_sensor.py'),
             'observer_sha256': sha(run/'p9_watch.h'), 'pipa_bridge_sha256': sha(HERE/'pipa_bridge.c')})
        for path in (Path(__file__), HERE/'pipa_sensor.py', HERE/'pipa_bridge.c'):
            shutil.copyfile(path, run/('executed-'+path.name))
        driver = p10.Driver(run, addresses, checkpoints, True, config=config)
        driver.all_addresses = {name: p10.p9.address(value) for name, value in table.items()}
        p10.p9.execute(driver)
        driver.step(config['post_selection_horizon_cpu_calls']-400000)
        driver.emit('phase10_review', state=driver.snapshot(), mission_state=driver.mission_state())
        if driver.decoder.snapshot()['VERB'] != '06' or driver.decoder.snapshot()['NOUN'] != '61':
            raise ValueError('Original Phase10 V06N61 baseline did not reproduce')
        p10.p9.Driver.keys(driver, 'V37E00E')
        driver.wait('original P00 before P47', lambda: driver.read('MODREG') == 0)
        driver.wait('original V37 cleanup clears NODOFLAG', lambda: not driver.read('FLAGWRD2') & 1,
                    3000000)
        driver.step(170667)
        p10.p9.Driver.keys(driver, 'V37E47E')
        driver.wait('original P47 selected', lambda: driver.read('MODREG') == 47)
        # MIDTOAV2 precision integration is scheduled 20s into the future;
        # allow 30s for original initialization/clearing and navigation cycles.
        sensor = load('phase11_sensor_model', HERE/'pipa_sensor.py')
        from fractions import Fraction
        mct = sensor.MCT_SECONDS
        driver.step(int(Fraction(30)/mct))
        def state():
            return {name: [driver.lib.inspect_ram(addresses[name]+i) for i in range(size)]
                    for name, size in EXTRA.items()}
        driver.emit('sensor_start', case=args.case, state=driver.snapshot(), navigation=state())
        # Phase9 matrix uses half-unit entries: stable = REFSMMAT * REF.
        # Decode signed DP; retain the actual AGC-set synthetic rotation.
        def dp(words):
            return sum((-(0o77777-w) if w & 0o40000 else w)*Fraction(1, 2**(14*(i+1))) for i, w in enumerate(words))
        refs = driver.snapshot()['refsmmat']
        rotation = [[float(2*dp(refs[6*i+2*j:6*i+2*j+2])) for j in range(3)] for i in range(3)]
        sign = -1 if args.case == 'negative' else 0 if args.case == 'zero' else 1
        # R is almost identity but use its transpose to express the requested
        # stable-axis force in REF coordinates. No body/screen-axis assumption.
        force = [Fraction(str(sign*rotation[0][j])) for j in range(3)]
        rn = state()['RN']
        position = [float(dp(rn[i:i+2])*2**29) for i in (0, 2, 4)]
        radius = math.sqrt(sum(x*x for x in position))
        mu = config['synthetic_geometry']['mu_m3_s2']
        gravity = [Fraction(str(-mu*x/radius**3)) for x in position]
        total_acceleration = [g+f for g, f in zip(gravity, force)]
        model = sensor.PipaSensor(start_cycle=driver.cycle, inertial_to_stable=rotation)
        start = driver.cycle
        end = start+int(Fraction(6)/mct)
        interval = model.sample(end, total_acceleration_m_s2=total_acceleration,
                                gravity_m_s2=gravity, connected=args.case != 'disconnected')
        driver.emit('sensor_plan', start_cycle=start, end_cycle=end, mct_seconds=float(mct),
                    ref_to_stable=rotation, force_ref_m_s2=list(map(float, force)),
                    gravity_ref_m_s2=list(map(float, gravity)), total_acceleration_ref_m_s2=list(map(float, total_acceleration)),
                    diagnostic_position_ref_m=position,
                    assumption='Held constant diagnostic a/g vectors; original AGC owns navigation/gravity. No external trajectory integration.',
                    interval=interval.to_dict())
        for event in interval.events:
            driver.step(event.cycle-driver.cycle)
            driver.packet(event.channel, event.operation, 'synthetic PIPA '+event.axis)
            driver.emit('pipa_delivered', requested_cycle=event.cycle, axis=event.axis,
                        counter=event.counter, operation=event.operation)
        driver.step(end-driver.cycle)
        driver.emit('sensor_end', navigation=state(), state=driver.snapshot())
        driver.step(int(Fraction(4)/mct))
        driver.emit('settled', navigation=state(), state=driver.snapshot())
        driver.emit('finish', navigation=state(), state=driver.snapshot())
        save(run/'completion.json', {'case': args.case, 'cycle': driver.cycle,
                                     'state': driver.snapshot(), 'navigation': state()})
        save(run/'preservation-after.json', preserve())
        save(run/'original-preservation-after.json', p10.preserve())
        changed = [name for name, expected in source_hashes.items() if sha(source/name) != expected]
        save(run/'source-integrity/after-execution.json', {'files_checked': len(source_hashes), 'changed_or_missing': changed})
        if changed:
            raise ValueError('Pinned source changed')
        print(json.dumps({'case': args.case, 'cycle': driver.cycle, 'state': driver.snapshot()}))
    except BaseException as error:
        save(run/'failure.json', {'error': repr(error)})
        if driver:
            driver.emit('failure', error=repr(error), state=driver.snapshot())
        raise
    finally:
        if driver:
            driver.trace.close()
            save(run/'trace-sha256.json', {'sha256': sha(run/'trace.jsonl'), 'bytes': (run/'trace.jsonl').stat().st_size})


if __name__ == '__main__':
    main()
