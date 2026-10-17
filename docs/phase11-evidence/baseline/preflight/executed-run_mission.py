#!/usr/bin/env python3
"""Phase10 DSKY mission-data fixture; original Phase9 alignment is reused.

No erasable setter, restored core, guidance replacement, or fabricated outputs.
P27 input is octal through the normal channel015 key path, including V33 verify.
"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'docs/phase9-evidence'))
import run_alignment as p9


def preserve():
    expected = json.loads((HERE/'prior_hashes.json').read_text())['sha256']
    changed = [name for name, digest in expected.items()
               if not (ROOT/name).is_file() or (ROOT/name).is_symlink() or p9.sha(ROOT/name) != digest]
    return {'ok': not changed, 'files_checked': len(expected), 'changed_or_missing': changed}


EXTRA = {'TIME2': 2, 'UPCOUNT': 1, 'COMPNUMB': 1, 'UPBUFF': 20, 'UPSVFLAG': 1,
         'FLAGWRD7': 1, 'RRECTLEM': 6, 'VRECTLEM': 6, 'TETLEM': 2,
         'FIXLOC': 1, 'VAC1': 44, 'VAC2': 44, 'VAC3': 44, 'VAC4': 44, 'VAC5': 44,
         'R': 6, 'V': 6, 'LAND': 6,
         'RBRFG': 6, 'VBRFG': 6, 'ABRFG': 6, 'VBRFG*': 2, 'ABRFG*': 2,
         'JBRFG*': 2, 'CG': 18, 'WM': 6, '/LAND/': 2, 'TPIP': 2,
         'PIPTIME1': 2, 'TIG': 2, 'NIGNLOOP': 1, 'ZOOMTIME': 1,
         'TEPHEM': 3, 'TIMSUBO': 3, '504LM': 6}
RELATIVE = {'RATT1': 6, 'VATT1': 6, 'TAT': 2, 'TDEC1': 2, 'MMATRIX': 18}
ALLOWED_BLOCKS = {'UPSVFLAG': 15, 'TEPHEM': 3, '504LM': 6, 'RLS': 6,
                  'TLAND': 18, 'ABRFG': 18, 'VBRFG*': 10, 'VIGN': 12,
                  'RBRFG': 18, 'ZOOMTIME': 1}


def build(source, symbols, output):
    # Reuse the retained external mark hardware bridge and its read-only observer.
    # Only generated observation addresses/checkpoints change; engine files do not.
    addresses, checkpoints = p9.build(source, symbols, output)
    mapping = json.loads((output/'observer-map.json').read_text())
    snapshot = mapping['snapshot_addresses']
    for name, size in EXTRA.items():
        addresses[name] = p9.address(symbols[name])
        snapshot.extend(range(addresses[name], addresses[name]+size))
    for name in ['V71UPDAT', 'UPSTORE', 'UPEND71', 'INTWAKE0', 'ATOPLEM',
                 'CALCRGVG', 'CGCALC', 'RGVGCALC', 'DDUMCALC', 'DDUMGOOD',
                 'ROOTSTOR', 'QUADGUID', 'IGNALGRT', 'ASTNRET', 'P63SPOT2']:
        symbol = symbols[name]
        z = symbol.get('sRegister', symbol.get('value'))
        checkpoints[name] = [symbol.get('fixedBank', 2 if z < 0o6000 else 3), z]
    # At these continuations the preceding original stores have completed,
    # even when the current instruction spans several engine calls.
    bank, z = checkpoints['ROOTSTOR']
    checkpoints['ROOTSTOR_RESULT'] = [bank, z+4]
    watches = mapping['watch_addresses']
    arrays = {'p9_snapshot_addresses': snapshot, 'p9_watch_addresses': watches,
              'p9_checkpoint_banks': [x[0] for x in checkpoints.values()],
              'p9_checkpoint_z': [x[1] for x in checkpoints.values()]}
    header = '#define P9_WATCH_COUNT {}\n#define P9_CHECKPOINT_COUNT {}\n#define P9_SNAPSHOT_COUNT {}\n'.format(len(watches), len(checkpoints), len(snapshot))
    header += '\n'.join('static const unsigned {}[] = {{{}}};'.format(k, ','.join(map(str, v))) for k, v in arrays.items())+'\n'
    (output/'p9_watch.h').write_text(header)
    mapping.update(addresses=addresses, snapshot_addresses=snapshot, checkpoints=checkpoints, extra_sizes=EXTRA,
                   relative_offsets={name: {'offset': p9.address(symbols[name]), 'size': size} for name, size in RELATIVE.items()},
                   checkpoint_semantics='CPU-call observation at pre_bank/pre_z; pending multi-cycle instructions may not yet have committed. Continuations prove preceding stores.')
    p9.save(output/'observer-map.json', mapping)
    command = json.loads((output/'commands.json').read_text())[0]['argv']
    with (output/'build.stdout').open('a') as out, (output/'build.stderr').open('a') as err:
        result = subprocess.run(command, stdout=out, stderr=err)
    p9.save(output/'observer-build.json', {'argv': command, 'exit': result.returncode})
    if result.returncode:
        raise ValueError('Extended read-only observer build failed')
    return addresses, checkpoints


class Driver(p9.Driver):
    def __init__(self, *args, config, **kwargs):
        super().__init__(*args, **kwargs)
        self.config, self.injected = config, False

    def mission_state(self):
        return {name: [self.lib.inspect_ram(self.addresses[name]+i) for i in range(size)]
                for name, size in EXTRA.items() if not name.startswith('VAC')}

    def block(self, item):
        name, words = item['symbol'], item['words']
        if name not in ALLOWED_BLOCKS or len(words) > ALLOWED_BLOCKS[name] or not all(item.get(key) for key in ('provenance', 'units_and_scales', 'reason')):
            raise ValueError('Undocumented or unsupported mission input block')
        start = self.addresses.get(name)
        if start is None:
            start = self.all_addresses[name]
        if not 1 <= len(words) <= 18 or start//256 != (start+len(words)-1)//256:
            raise ValueError('Original P27 block count/bank restriction')
        before = self.read('FLAGWRD7')
        self.emit('mission_block', definition=item, address=start,
                  method='Original P27 V71 normal DSKY; V33 verify', before_veriflag=before)
        p9.Driver.keys(self, 'V71E')
        self.display('21', '01')
        p9.Driver.keys(self, format(len(words)+2, '05o')+'E')
        self.wait('P27 accepted count', lambda: self.read('UPCOUNT') == 2)
        for index, word in enumerate([start, *words], start=2):
            if not 0 <= word <= 0o77777:
                raise ValueError('Not a 15-bit octal input word')
            p9.Driver.keys(self, format(word, '05o')+'E')
            if index < len(words)+2:
                self.wait('P27 next component '+str(index+1), lambda: self.read('UPCOUNT') == index+1)
        self.display('21', '02')
        p9.Driver.keys(self, 'V33E')
        self.wait('P27 verified store and return P00', lambda: self.read('MODREG') == 0 and bool((self.read('FLAGWRD7') ^ before) & 4), 800000)
        observed = [self.lib.inspect_ram(start+i) for i in range(len(words))]
        self.emit('mission_block_stored', symbol=name, address=start, expected_words=words,
                  actual_words=observed, mission_state=self.mission_state(), state=self.snapshot())
        # State-vector updates are consumed/rectified by original INTWAKEU;
        # the incoming block need not remain bit-identical after integration.
        if name != 'UPSVFLAG' and observed != words:
            raise ValueError('P27 data store did not match entered mission data')
        if name == 'UPSVFLAG':
            state = self.mission_state()
            if self.read('UPSVFLAG') not in (0, 0o77777) or state['RRECTLEM'] != words[1:7] or state['VRECTLEM'] != words[7:13] or state['TETLEM'] != words[13:15]:
                raise ValueError('Original LM state-vector update did not establish the supplied permanent state')

    def keys(self, text):
        if text == 'V37E63E' and not self.injected:
            self.injected = True
            p9.Driver.keys(self, 'V37E00E')
            self.wait('original P00 for P27', lambda: self.read('MODREG') == 0)
            self.emit('mission_initialization_start', config=self.config, state=self.snapshot())
            for item in self.config['blocks']:
                self.block(item)
            self.emit('mission_initialization_complete', mission_state=self.mission_state(), state=self.snapshot())
            if self.config.get('protocol_probe'):
                raise ProbeComplete('P27 protocol probe complete; P63 NOT RUN')
        return p9.Driver.keys(self, text)


class ProbeComplete(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    driver = None
    try:
        before = preserve()
        p9.save(output/'preservation-before.json', before)
        if not before['ok']:
            raise ValueError('Pre-Phase10 tracked input changed')
        source, symbols, source_hashes = p9.verified_setup(args.setup.resolve(), output)
        table = json.loads(symbols.read_text())['symbols']
        addresses, checkpoints = build(source, table, output)
        config = json.loads(args.config.read_text())
        p9.save(output/'configuration.json', config)
        shutil.copyfile(__file__, output/'executed-run_mission.py')
        p9.save(output/'execution.json', {'argv': sys.argv, 'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'platform': platform.platform(),
                'python': sys.version, 'rope_sha256': p9.ROPE_SHA, 'symbols_sha256': p9.sha(symbols),
                'driver_sha256': p9.sha(__file__), 'engine_sha256': p9.sha(output/'engine.so'),
                'config_sha256': p9.sha(args.config),
                'dependency_sha256': {str(p.relative_to(ROOT)): p9.sha(p) for p in
                    [ROOT/'docs/phase9-evidence/run_alignment.py', ROOT/'docs/phase9-evidence/hardware_bridge.c',
                     ROOT/'docs/phase5-evidence/plant_bridge.c', ROOT/'docs/phase5-evidence/operate_inputs.txt',
                     ROOT/'docs/phase1-evidence/m2_dsky_client.py']},
                'generated_observer_sha256': p9.sha(output/'p9_watch.h'),
                'scope': 'SYNTHETIC mission-input feasibility; original P51 and P27/P63 instructions; no thrust plant'})
        driver = Driver(output, addresses, checkpoints, True, config=config)
        driver.all_addresses = {name: p9.address(value) for name, value in table.items()}
        try:
            result = p9.execute(driver)
            horizon = config['post_selection_horizon_cpu_calls']
            if not 400000 <= horizon <= 2000000:
                raise ValueError('Unsupported unbounded P63 horizon')
            driver.step(horizon-400000)
            driver.emit('bounded_horizon_result', horizon_cpu_calls=horizon, mission_state=driver.mission_state(), state=driver.snapshot())
        except ProbeComplete as end:
            result = str(end)
        driver.emit('finish', result=result, state=driver.snapshot())
        p9.save(output/'completion.json', {'result': result, 'cycle': driver.cycle, 'state': driver.snapshot()})
        after = preserve()
        p9.save(output/'preservation-after.json', after)
        changed = [name for name, expected in source_hashes.items() if p9.sha(source/name) != expected]
        p9.save(output/'source-integrity/after-execution.json', {'files_checked': len(source_hashes), 'changed_or_missing': changed})
        if not after['ok'] or changed:
            raise ValueError('Original inputs changed during execution')
        print(json.dumps({'result': result, 'output': str(output), 'cycle': driver.cycle, 'state': driver.snapshot()}))
    except BaseException as error:
        p9.save(output/'failure.json', {'error': repr(error)})
        if driver:
            driver.emit('failure', error=repr(error), state=driver.snapshot())
        raise
    finally:
        if driver:
            driver.trace.close()
            p9.save(output/'trace-sha256.json', {'sha256': p9.sha(output/'trace.jsonl'), 'bytes': (output/'trace.jsonl').stat().st_size})


if __name__ == '__main__':
    main()
