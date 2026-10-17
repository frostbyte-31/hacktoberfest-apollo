"""GPL-2.0-or-later. Phase 9 bounded experiment: authentic P51 IMU alignment.

Reuses the Phase 5 operate_inputs.txt schedule unchanged (fresh cpu_reset, IMU
OPERATE asserted, V36E/V37E00E/V77E). The only additions, starting at
3,000,000 CPU calls, are DSKY keystrokes on channel 015 (same key codes as
Phase 1/5/8), PRO on channel 032 bit14 (Phase 1 mechanism), and AOT mark
discretes on channel 016 with KEYRUPT2 (the hardware path; the socket API
cannot raise it - see alignment_bridge.c header).

Procedure (all through the original software, no memory writes, no flag
forcing):
  V37E51E            enter P51 (IMU orientation determination)
  PRO                V50N25 00015 -> P51B (skip optional gimbal zero)
  00701 E, PRO       V01N71: AOTCODE = COAS detent 7 + star code 01 (star 37)
  AZ, EL, PRO        V06N87: COAS optic-axis az/el aimed at star 37
  X mark, Y mark, PRO  V54: one mark pair; MARKRUPT captures CDUX/Y/Z (=0)
  00717 E, PRO       V01N71: COAS + star code 15 (star 23)
  AZ, EL, PRO        V06N87 aimed at star 23
  X mark, Y mark, PRO  second mark pair
  PRO                V06N05 (R54 separation discrepancy) -> accept
  V37E63E            then attempt P63 selection again (Phase 8 baseline)

Geometry: the fixture holds the IMU at zero gimbal angles, so the
stable-member frame equals the navigation-base frame. COAS az/el are chosen
so the optic axis equals the catalog star direction: EL=asin(x),
AZ=atan2(y,z) from the B-1 unit vectors in CONTROLLED_CONSTANTS.agc:357-507
(OANB convention, AOTMARK.agc:222-248). With rotation 0 the measured LOS
equals the optic axis (AOTMARK.agc:326-408), so R54's separation check
compares two identical angle pairs and AXISGEN should yield a near-identity
REFSMMAT. Star catalog indexing: code N -> CATLOG + 6N (P51-P53.agc:1515-
1552), so code 1 = star 37 and code 15 = star 23.

AZ/EL are entered at the DSKY's 0.01-degree resolution, so the measured
vectors differ from the catalog vectors by up to ~0.01 deg; this is recorded,
not hidden.
"""
from pathlib import Path
import ctypes, json, math, sys

ROOT = Path(__file__).resolve().parents[2]
P5 = ROOT / 'docs/phase5-evidence'
ADDR = {'MODREG': 0o1011, 'FLAGWRD3': 0o77, 'IMODES30': 0o1302, 'IMODES33': 0o1303,
        'THRUST': 0o55, 'FAILREG0': 0o375, 'FAILREG1': 0o376, 'FAILREG2': 0o377}
REFSMMAT = 0o1733  # bank 3, 18 words (9 DP elements), ERASABLE_ASSIGNMENTS.agc:972
END = 7600000
GAP = 50000

KEY = {**{str(d): d for d in range(1, 10)},
       '0': 16, 'V': 17, 'N': 31, '+': 26, '-': 27, 'E': 28}  # Phase 1 key map
PRO_CH, PRO_BIT = 0o32, 0o40000  # Phase 1: PRO = channel 032 bit 14

# Catalog star unit vectors (CONTROLLED_CONSTANTS.agc, B-1 halved values doubled)
STAR37 = (0.8342971408, -0.2392481515, -0.4966976975)  # code 01
STAR23 = (-0.5812035376, -0.2909171294, 0.7599800468)  # code 15

def az_el(star):
    x, y, z = star
    el = math.degrees(math.asin(x))
    az = math.degrees(math.atan2(y, z))
    return az, el

def deg_keys(value):
    """CDU DEG noun entry: sign + 5 digits (xxx.xx)."""
    sign = '+' if value >= 0 else '-'
    digits = f'{abs(value):05.2f}'.replace('.', '')
    return [KEY[sign]] + [KEY[d] for d in digits] + [KEY['E']]

def main():
    library, output = sys.argv[1:]
    lib = ctypes.CDLL(library); lib.cpu_reset()
    lib.set_fixed((ctypes.c_ubyte * 73728).from_buffer_copy(
        (ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()))

    sched = []  # (time, kind, payload)
    lines = (P5 / 'operate_inputs.txt').read_text().splitlines()
    for l in lines[1:]:
        t, ch, v = map(int, l.split())
        sched.append((t, 'packet', (ch, v)))

    t = 3000000
    def keys(seq):
        nonlocal t
        for k in seq:
            sched.append((t, 'packet', (0o15, KEY[k] if isinstance(k, str) else k)))
            t += GAP
    def pro():
        nonlocal t
        sched.append((t, 'packet', (PRO_CH, PRO_BIT))); t += GAP
        sched.append((t, 'packet', (PRO_CH, 0))); t += GAP
    def markpair():
        nonlocal t
        sched.append((t, 'mark', 0o4)); t += GAP          # X mark, ch016 bit3
        sched.append((t, 'mark', 0)); t += GAP
        sched.append((t, 'mark', 0o10)); t += GAP         # Y mark, ch016 bit4
        sched.append((t, 'mark', 0)); t += GAP

    az1, el1 = az_el(STAR37)
    az2, el2 = az_el(STAR23)

    keys('V37E51E')                                   # enter P51
    pro()                                             # V50N25 00015 -> P51B
    keys(['0', '0', '7', '0', '1', 'E'])              # V01N71: COAS + star 37
    pro()
    keys(deg_keys(az1))                               # V06N87: AZ
    keys(deg_keys(el1))                               # EL
    pro()                                             # -> V54
    markpair()
    pro()                                             # process marks -> star 2
    keys(['0', '0', '7', '1', '7', 'E'])              # V01N71: COAS + star 23
    pro()
    keys(deg_keys(az2))
    keys(deg_keys(el2))
    pro()
    markpair()
    pro()                                             # -> R54 V06N05
    pro()                                             # accept -> P51G, REFSMFLG
    t += 4 * GAP                                      # settle in P00
    keys('V37E63E')                                   # Phase 8 baseline attempt
    sched.sort(key=lambda r: r[0])

    log = Path(output).open('w')
    emit = lambda r: log.write(json.dumps(r, separators=(',', ':')) + '\n')
    def snap(tick):
        s = {'ev': 'sample', 'cycle': tick}
        for k, a in ADDR.items(): s[k] = lib.inspect_ram(a)
        s['REFSMMAT'] = [lib.inspect_ram(REFSMMAT + i) for i in range(18)]
        s['CH16'] = lib.inspect_channel(0o16)
        return s
    emit({'ev': 'initial', 'end': END, 'ram_writes': 0,
          'star37': {'code': 1, 'az': az1, 'el': el1},
          'star23': {'code': 15, 'az': az2, 'el': el2},
          'az_el_rule': 'EL=asin(x), AZ=atan2(y,z); catalog B-1 vectors; OANB convention',
          'mark_path': 'channel 016 bits 3/4 + KEYRUPT2 (index 6) via alignment_bridge.c'})
    tick = idx = 0; last = None
    while tick < END:
        while idx < len(sched) and sched[idx][0] == tick:
            _, kind, payload = sched[idx]; idx += 1
            if kind == 'packet':
                ch, v = payload
                emit({'ev': 'input', 'cycle': tick, 'channel': ch, 'value': v,
                      'accepted': lib.packet_write(ch, v)})
            else:
                lib.mark_write(payload, 1 if payload else 0)
                emit({'ev': 'mark', 'cycle': tick, 'bits': payload})
        n = min(853, END - tick)
        if idx < len(sched): n = min(n, sched[idx][0] - tick)
        used = lib.step_chunk(n)
        for i in range(used):
            w = lib.output_word(i); ch = (w >> 16) & 65535
            if ch in (0o11, 0o14, 0o16):
                emit({'ev': 'output', 'cycle': lib.output_cycle(i), 'channel': ch,
                      'value': w & 32767})
        tick += n
        s = snap(tick); key = tuple(v for k, v in s.items() if k not in ('ev', 'cycle'))
        if key != last: emit(s); last = key
    emit(snap(tick)); log.close()

if __name__ == '__main__': main()
