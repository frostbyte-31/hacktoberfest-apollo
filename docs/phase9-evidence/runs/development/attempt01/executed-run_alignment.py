#!/usr/bin/env python3
"""Original P51 via event-driven DSKY and documented external mark events.

No flight-memory writes, alignment-flag forcing, restored core or actuator model.
All observed geometry is synthetic stationary COAS data, not Apollo telemetry.
"""
import argparse
import ctypes
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROPE_SHA = '1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'
KEY_INTERVAL = 21333


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def address(symbol):
    return symbol.get('linearErasable', symbol.get('value'))


def build(source, symbols, output):
    names = ['FLAGWRD3', 'MODREG', 'IMODES30', 'IMODES33', 'FAILREG', 'CDUX', 'CDUY', 'CDUZ',
             'MARKSTAT', 'MARKCNTR', 'AOTCODE', 'AZ', 'EL', 'STARIND', 'REFSMMAT']
    addresses = {name: address(symbols[name]) for name in names}
    if any(value is None for value in addresses.values()):
        raise ValueError('Required observer symbol is not an erasable address')
    a = addresses
    snapshot = [a['FLAGWRD3'], a['MODREG'], a['IMODES30'], a['IMODES33'],
                a['FAILREG'], a['FAILREG']+1, a['FAILREG']+2, a['CDUX'], a['CDUY'], a['CDUZ'],
                a['MARKSTAT'], a['MARKCNTR'], *range(a['REFSMMAT'], a['REFSMMAT']+18)]
    watches = sorted(set([*snapshot, a['AOTCODE'], a['AZ'], a['EL'], a['STARIND']]))
    checkpoints = {}
    for name in ['P51', 'P51B', 'P51C', 'P51E', 'P51G', 'AOTMARK', 'MARKRUPT', 'GETDAT',
                 'CODE7', 'GETMKS', 'MARKCHEX', 'AVESTAR', 'CHKSDATA', 'AXISGEN', 'MATMOVE',
                 'R02BOTH', 'P63LM', 'IGNALG', 'GUIDINIT', 'LEMPREC', 'VARALARM']:
        symbol = symbols[name]
        z = symbol.get('sRegister', symbol.get('value'))
        bank = symbol.get('fixedBank', 2 if z < 0o6000 else 3)
        checkpoints[name] = [bank, z]
    # Actual listing continuation immediately after original R02 BANKCALL/CADR.
    checkpoints['P63_AFTER_R02'] = [symbols['P63LM']['fixedBank'], symbols['P63LM']['sRegister']+4]
    arrays = {'p9_snapshot_addresses': snapshot, 'p9_watch_addresses': watches,
              'p9_checkpoint_banks': [v[0] for v in checkpoints.values()],
              'p9_checkpoint_z': [v[1] for v in checkpoints.values()]}
    header = '#define P9_WATCH_COUNT {}\n#define P9_CHECKPOINT_COUNT {}\n'.format(len(watches), len(checkpoints))
    header += '\n'.join('static const unsigned {}[] = {{{}}};'.format(k, ','.join(map(str, v))) for k, v in arrays.items())+'\n'
    (output/'p9_watch.h').write_text(header)
    save(output/'observer-map.json', {'addresses': addresses, 'snapshot_addresses': snapshot,
                                     'watch_addresses': watches, 'checkpoints': checkpoints})
    files = [source/'yaAGC'/name for name in ('wasm.c', 'agc_engine.c', 'agc_engine_init.c',
             'agc_utilities.c', 'ringbuffer_api.c', 'ringbuffer.c', 'rfopen.c')]
    command = ['cc', '-shared', '-fPIC', '-O2', '-I'+str(source/'yaAGC'),
               '-I'+str(ROOT/'docs/phase5-evidence'), '-I'+str(output),
               str(HERE/'hardware_bridge.c'), *map(str, files), '-lm', '-o', str(output/'engine.so')]
    with (output/'build.stdout').open('w') as out, (output/'build.stderr').open('w') as err:
        result = subprocess.run(command, stdout=out, stderr=err)
    save(output/'commands.json', [{'argv': command, 'cwd': str(ROOT), 'exit': result.returncode}])
    if result.returncode:
        raise ValueError('Native build failed; inspect preserved build.stderr')
    return addresses, checkpoints


class Event(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ('kind', 'cycle', 'a', 'b', 'bank', 'z')]+[('snapshot', ctypes.c_uint32*30)]


class Driver:
    def __init__(self, output, addresses, checkpoints, enable_mark_irq):
        self.output, self.addresses = output, addresses
        self.checkpoints, self.enable_mark_irq = list(checkpoints), enable_mark_irq
        self.lib = ctypes.CDLL(str(output/'engine.so'))
        self.lib.set_fixed.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.lib.packet_write.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
        self.lib.p9_step.argtypes = [ctypes.c_uint]
        self.lib.p9_step.restype = ctypes.c_uint
        self.lib.p9_events.restype = ctypes.POINTER(Event)
        self.lib.inspect_ram.argtypes = [ctypes.c_uint]
        self.lib.inspect_channel.argtypes = [ctypes.c_uint]
        self.decoder = load_module('p9_retained_display', ROOT/'docs/phase1-evidence/m2_dsky_client.py')
        self.cycle = 0
        self.trace = (output/'trace.jsonl').open('w')
        self.lib.cpu_reset()
        rope = (ROOT/'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()
        if hashlib.sha256(rope).hexdigest() != ROPE_SHA:
            raise ValueError('Retained rope integrity mismatch')
        self.rope = (ctypes.c_ubyte*len(rope)).from_buffer_copy(rope)
        self.lib.set_fixed(self.rope)
        self.lib.p9_observer_init()
        self.emit('initial', original_ram_writes=0, hardware_bridge='documented interrupt6 after channel016 mark packet' if enable_mark_irq else 'disabled negative control', rope_sha256=ROPE_SHA)

    def emit(self, event, **values):
        self.trace.write(json.dumps({'ev': event, 'cycle': self.cycle, **values}, separators=(',', ':'), allow_nan=False)+'\n')

    def read(self, name):
        return self.lib.inspect_ram(self.addresses[name])

    def snapshot(self):
        a = self.addresses
        return {'modreg': self.read('MODREG'), 'flagword3': self.read('FLAGWRD3'),
                'refsmflg': bool(self.read('FLAGWRD3') & 0o10000),
                'imodes30': self.read('IMODES30'), 'imodes33': self.read('IMODES33'),
                'failreg': [self.lib.inspect_ram(a['FAILREG']+i) for i in range(3)],
                'refsmmat': [self.lib.inspect_ram(a['REFSMMAT']+i) for i in range(18)],
                'cdu': [self.read(n) for n in ('CDUX', 'CDUY', 'CDUZ')],
                'markstat': self.read('MARKSTAT'), 'markcntr': self.read('MARKCNTR'),
                'aotcode': self.read('AOTCODE'), 'az': self.read('AZ'), 'el': self.read('EL'),
                'starind': self.read('STARIND'), 'display': self.decoder.snapshot()}

    def step(self, count):
        while count:
            chunk = min(count, 1000)
            used = self.lib.p9_step(chunk)
            if used == 0xffffffff:
                raise ValueError('Native observer capacity exceeded; no observations discarded')
            pointer = self.lib.p9_events()
            for i in range(used):
                event = pointer[i]
                row = {'ev': ('output' if event.kind == 1 else 'transition' if event.kind == 2 else 'checkpoint'),
                       'cycle': event.cycle, 'pre_bank': event.bank, 'pre_z': event.z}
                if event.kind == 1:
                    row.update(channel=event.a, value=event.b)
                    if event.a == 0o10:
                        self.decoder.apply010(event.b)
                        row['display'] = self.decoder.snapshot()
                else:
                    row['snapshot_words'] = list(event.snapshot)
                    if event.kind == 2:
                        row.update(address=event.a, value=event.b)
                    else:
                        row['routine'] = self.checkpoints[event.a]
                self.trace.write(json.dumps(row, separators=(',', ':'))+'\n')
            self.cycle += chunk
            count -= chunk

    def packet(self, channel, value, origin):
        accepted = self.lib.packet_write(channel, value)
        self.emit('input', channel=channel, value=value, accepted_bytes=accepted, origin=origin)
        if accepted <= 0:
            raise ValueError('Actual packet queue rejected input')

    def keys(self, text):
        self.emit('key_sequence', text=text, display=self.decoder.snapshot())
        for key in text:
            self.packet(0o15, self.decoder.KEY[key], 'authentic DSKY '+key)
            self.step(KEY_INTERVAL)

    def wait(self, description, predicate, limit=400000):
        self.emit('wait', description=description, state=self.snapshot())
        end = self.cycle+limit
        while not predicate():
            if self.cycle >= end:
                self.emit('wait_timeout', description=description, state=self.snapshot())
                raise ValueError('Timed out waiting for '+description)
            self.step(min(1000, end-self.cycle))
        self.emit('observed', description=description, state=self.snapshot())
        self.trace.flush()

    def display(self, verb, noun, limit=400000):
        self.wait('display V{}N{}'.format(verb, noun), lambda: self.decoder.snapshot()['VERB'] == verb and self.decoder.snapshot()['NOUN'] == noun, limit)

    def mark(self, word):
        self.packet(0o16, word, 'synthetic stationary optical mark button')
        self.wait('actual channel016 packet consumed', lambda: self.lib.inspect_channel(0o16) == word, 1000)
        if self.enable_mark_irq:
            accepted = self.lib.p9_mark_interrupt()
            self.emit('hardware_interrupt', interrupt=6, channel=0o16, readback=self.lib.inspect_channel(0o16), accepted=accepted)
            if accepted != 1:
                raise ValueError('Documented mark interrupt assertion rejected')
        self.step(KEY_INTERVAL)
        self.packet(0o16, 0, 'mark button release; no release interrupt')
        self.step(KEY_INTERVAL)


def execute(driver):
    # Exact unchanged Phase5 startup prefix, including its early rejected P00.
    entries = [tuple(map(int, line.split())) for line in (ROOT/'docs/phase5-evidence/operate_inputs.txt').read_text().splitlines()[1:]]
    startup = [entry for entry in entries if entry[0] < 2200000]
    driver.emit('startup_plan', schedule=startup, source='docs/phase5-evidence/operate_inputs.txt', end=2200000)
    for tick, channel, value in startup:
        driver.step(tick-driver.cycle)
        driver.packet(channel, value, 'unchanged Phase5 startup')
    driver.step(2200000-driver.cycle)
    driver.emit('startup_complete', state=driver.snapshot())
    driver.keys('V37E51E')
    driver.display('50', '25')
    driver.keys('V33E')
    for star, code, angles in ((1, '00701', ('+00309', '+06103')), (2, '00702', ('+15088', '+06911'))):
        driver.emit('synthetic_star_plan', star=star, detent=7, code=code, azimuth_field=angles[0], elevation_field=angles[1], cdu=driver.snapshot()['cdu'])
        driver.display('01', '71')
        driver.keys('V21N71E')
        driver.display('21', '71')
        driver.keys(code+'E')
        driver.display('01', '71')
        driver.keys('V33E')
        driver.display('06', '87')
        driver.keys('V24N87E')
        driver.display('24', '87')
        driver.keys(angles[0]+'E'+angles[1]+'E')
        driver.display('06', '87')
        driver.keys('V33E')
        driver.display('54', '71')
        before = driver.read('MARKSTAT')
        driver.mark(4)
        driver.mark(8)
        driver.emit('mark_pair_result', star=star, before=before, after=driver.read('MARKSTAT'), state=driver.snapshot())
        if not driver.enable_mark_irq:
            driver.emit('negative_control_complete', reason='Channel016 packets alone, no fabricated interrupt or marks', state=driver.snapshot())
            return 'packet-only negative control completed'
        driver.wait('original mark pair complete', lambda: driver.read('MARKSTAT') & 0o23000 == 0o23000)
        driver.keys('V33E')
    driver.display('06', '05')
    driver.emit('star_separation_check', state=driver.snapshot())
    driver.keys('V33E')
    driver.wait('original REFSMFLG set', lambda: bool(driver.read('FLAGWRD3') & 0o10000))
    driver.emit('alignment_result', state=driver.snapshot())
    driver.keys('V37E63E')
    driver.step(400000)
    driver.emit('p63_result', state=driver.snapshot())
    return 'alignment and subsequent P63 feasibility execution completed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--symbols', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-mark-irq', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    driver = None
    try:
        table = json.loads(args.symbols.read_text())['symbols']
        addresses, checkpoints = build(args.source.resolve(), table, output)
        paths = [Path(__file__), HERE/'hardware_bridge.c', ROOT/'docs/phase5-evidence/plant_bridge.c',
                 ROOT/'docs/phase5-evidence/operate_inputs.txt', ROOT/'docs/phase1-evidence/m2_dsky_client.py', args.symbols.resolve()]
        paths += list((args.source/'yaAGC').glob('*.[ch]'))
        save(output/'execution.json', {'argv': sys.argv, 'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'platform': platform.platform(), 'python': sys.version, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'input_sha256': {str(p): sha(p) for p in paths}, 'engine_sha256': sha(output/'engine.so'),
             'scope': 'Authentic P51, external documented mark IRQ, synthetic stationary COAS geometry; no flight-memory writes or thrust plant'})
        for path in (Path(__file__), HERE/'hardware_bridge.c'):
            shutil.copyfile(path, output/('executed-'+path.name))
        driver = Driver(output, addresses, checkpoints, not args.no_mark_irq)
        result = execute(driver)
        driver.emit('finish', result=result, state=driver.snapshot())
        save(output/'completion.json', {'result': result, 'state': driver.snapshot(), 'cycle': driver.cycle})
        print(json.dumps({'output': str(output), 'result': result, 'cycle': driver.cycle, 'state': driver.snapshot()}, indent=2))
    except BaseException as error:
        save(output/'failure.json', {'error': repr(error), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        if driver:
            driver.emit('failure', error=repr(error), state=driver.snapshot())
        raise
    finally:
        if driver:
            driver.trace.close()
            save(output/'trace-sha256.json', {'sha256': sha(output/'trace.jsonl'), 'bytes': (output/'trace.jsonl').stat().st_size})


if __name__ == '__main__':
    main()
