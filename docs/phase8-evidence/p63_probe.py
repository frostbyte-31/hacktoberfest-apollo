"""GPL-2.0-or-later. Phase 8 bounded P63 selection probe after verified IMU readiness.

Reuses the Phase 5 plant_bridge.c and operate_inputs.txt unchanged (fresh
cpu_reset, IMU OPERATE asserted, V36E/V37E00E/V77E, yaw pulse). The only
addition is the keystroke sequence V37E63E at 3,000,000 CPU calls, using the same
channel-015 key codes as the Phase 5 schedule. No RAM writes, no flag forcing,
no fabricated sensors. Records MODREG, FAILREG, FLAGWRD3 (REFSMFLG = bit13),
IMODES30/33, THRUST counter 055, and every output on channels 011/012/013/014.
"""
from pathlib import Path
import ctypes, json, sys
ROOT = Path(__file__).resolve().parents[2]
P5 = ROOT / 'docs/phase5-evidence'
ADDR = {'MODREG': 0o1011, 'FLAGWRD3': 0o77, 'IMODES30': 0o1302, 'IMODES33': 0o1303,
        'THRUST': 0o55, 'FAILREG0': 0o375, 'FAILREG1': 0o376, 'FAILREG2': 0o377}
KEYS = [17, 3, 7, 28, 6, 3, 28]  # V 3 7 E 6 3 E (codes as in operate_inputs.txt)
END = 4600000

def main():
    library, output = sys.argv[1:]
    lib = ctypes.CDLL(library); lib.cpu_reset()
    lib.set_fixed((ctypes.c_ubyte * 73728).from_buffer_copy((ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()))
    lines = (P5 / 'operate_inputs.txt').read_text().splitlines()
    sched = [list(map(int, l.split())) for l in lines[1:]]
    sched += [[3000000 + i * 21333, 13, k] for i, k in enumerate(KEYS)]
    sched.sort(key=lambda r: r[0])
    log = Path(output).open('w')
    emit = lambda r: log.write(json.dumps(r, separators=(',', ':')) + '\n')
    snap = lambda t: {'ev': 'sample', 'cycle': t, **{k: lib.inspect_ram(a) for k, a in ADDR.items()}}
    emit({'ev': 'initial', 'end': END, 'added_keys_at': 3000000, 'keys': KEYS, 'ram_writes': 0})
    tick = idx = 0; last = None
    while tick < END:
        while idx < len(sched) and sched[idx][0] == tick:
            _, ch, v = sched[idx]; idx += 1
            emit({'ev': 'input', 'cycle': tick, 'channel': ch, 'value': v, 'accepted': lib.packet_write(ch, v)})
        n = min(853, END - tick)
        if idx < len(sched): n = min(n, sched[idx][0] - tick)
        used = lib.step_chunk(n)
        for i in range(used):
            w = lib.output_word(i); ch = (w >> 16) & 65535
            if ch in (0o11, 0o12, 0o13, 0o14):
                emit({'ev': 'output', 'cycle': lib.output_cycle(i), 'channel': ch, 'value': w & 32767})
        tick += n
        s = snap(tick); key = tuple(v for k, v in s.items() if k not in ('ev', 'cycle'))
        if key != last: emit(s); last = key
    emit(snap(tick)); log.close()

if __name__ == '__main__': main()
