"""GPL-2.0-or-later. Phase 9 bounded experiment: authentic P51 IMU alignment.

Reuses the Phase 5 operate_inputs.txt schedule unchanged (fresh cpu_reset, IMU
OPERATE asserted, V36E/V37E00E/V77E). The only additions, starting at
3,000,000 CPU calls, are DSKY keystrokes on channel 015 (Phase 1 key map),
PRO on channel 032 bit 14 (0o20000; an earlier attempt used bit 15 in error - see the Phase 9 report), and AOT mark discretes on
channel 016 with KEYRUPT2 (the hardware path; the socket API cannot raise it
- see alignment_bridge.c header). No memory writes, no flag forcing.

The driver is event-driven: each step waits until Pinball's flash registers
(VERBREG 01001, NOUNREG 01002) show the expected display before acting, and
each data load waits until the target erasable shows the loaded value. A step
that is not satisfied within STALL_LIMIT calls is recorded as a stall and the
run continues to the end for evidence.

Procedure (all through the original software):
  V37E51E              enter P51 (IMU orientation determination)
  PRO                  V50N25 00015 -> P51B (skip optional gimbal zero)
  V21N71E 00701 E, PRO load AOTCODE = COAS detent 7 + star code 01 (star 37),
                       then proceed past the V01N71 flash
  V21N87E az E,        load COAS optic-axis az/el aimed at star 37, PRO past
  V22N87E el E, PRO    the V06N87 flash
  X mark, Y mark, PRO  V54N71: one mark pair; MARKRUPT captures CDUX/Y/Z (=0)
  (same for star 23, code 15)
  PRO                  V06N05 (R54 separation discrepancy) -> accept
  V37E63E              then attempt P63 selection again (Phase 8 baseline)

Why V21/V22 loads: GOMARKF flashes block direct data-in (DSPCOUNT negative,
observed), so data is loaded with the standard load-data verbs V21 (R1) and
V22 (R2), which write the noun's erasables through Pinball's normal monitor
path (DISPLAY_INTERFACE_ROUTINES.agc:1238 LOADITIS).

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
        'THRUST': 0o55, 'FAILREG0': 0o375, 'FAILREG1': 0o376, 'FAILREG2': 0o377,
        'VERBREG': 0o1001, 'NOUNREG': 0o1002, 'AOTCODE': 0o735,
        'AZ': 0o1347, 'EL': 0o1350, 'MARKSTAT': 0o1312,
        'MARKCNTR': 0o3545, 'STARIND': 0o2642}
REFSMMAT = 0o1733  # bank 3, 18 words (9 DP elements), ERASABLE_ASSIGNMENTS.agc:972
START = 3000000
END = 24000000
KEYGAP = 21333          # same key spacing as Phases 5/8
STALL_LIMIT = 3000000   # calls a step may wait for its precondition
SETTLE = 200000         # calls to wait after a flash appears before acting

KEY = {**{str(d): d for d in range(1, 10)},
       '0': 16, 'V': 17, 'N': 31, '+': 26, '-': 27, 'E': 28}  # Phase 1 key map
PRO_CH, PRO_BIT = 0o32, 0o20000  # PRO = channel 032 bit 14 (INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:203)

# Catalog star unit vectors (CONTROLLED_CONSTANTS.agc, B-1 halved values doubled)
STAR37 = (0.8342971408, -0.2392481515, -0.4966976975)  # code 01
STAR23 = (-0.5812035376, -0.2909171294, 0.7599800468)  # code 15

def az_el(star):
    x, y, z = star
    return math.degrees(math.atan2(y, z)), math.degrees(math.asin(x))

def deg_str(value):
    """CDU DEG noun entry text: sign + 5 digits (xxx.xx). Width 6 includes the
    decimal point; :05.2f under-pads values < 100 deg (4 digits), which Pinball
    rejects as an incomplete field (alignment-02 EL stall)."""
    return ('+' if value >= 0 else '-') + f'{abs(value):06.2f}'.replace('.', '')

def main():
    library, output = sys.argv[1:]
    lib = ctypes.CDLL(library); lib.cpu_reset()
    lib.set_fixed((ctypes.c_ubyte * 73728).from_buffer_copy(
        (ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes()))

    sched = []  # (time, kind, payload); kinds: packet, mark
    for l in (P5 / 'operate_inputs.txt').read_text().splitlines()[1:]:
        t, ch, v = map(int, l.split())
        sched.append((t, 'packet', (ch, v)))

    az1, el1 = az_el(STAR37)
    az2, el2 = az_el(STAR23)

    # Event-driven script. Each step: (name, precondition, actions).
    # precondition: ('flash', verb, noun) on VERBREG/NOUNREG, or ('p00',).
    # actions: ('keys', text), ('pro',), ('marks',), ('load', verb, noun, text)
    # Every action of a step waits for the step's precondition to hold again
    # before firing, because a monitor load (V21/V22) replaces VERBREG/NOUNREG
    # until Pinball re-establishes the flash (observed at cycle 4516257 in the
    # 2026-10-17 debug run).
    def sighting(code_text, az, el):
        return [('load-code', ('flash', 1, 71), [('load', '21', '71', code_text)]),
                ('pro-code', ('flash', 1, 71), [('pro',)]),
                ('load-az', ('flash', 6, 87), [('load', '21', '87', deg_str(az))]),
                ('load-el', ('flash', 6, 87), [('load', '22', '87', deg_str(el))]),
                ('pro-azel', ('flash', 6, 87), [('pro',)]),
                ('marks', ('flash', 54, 71), [('marks',)]),
                ('pro-marks', ('flash', 54, 71), [('pro',)]),
                ('reject-accept', ('maybe-flash', 5, 71, 1500000), [('pro',)])]
    steps = [
        ('enter-p51', ('always',), [('keys', 'V37E51E')]),
        ('v50n25-proceed', ('flash', 50, 25), [('pro',)]),
    ] + [('s1-' + n, p, a) for n, p, a in sighting('00701', az1, el1)] \
      + [('s2-' + n, p, a) for n, p, a in sighting('00717', az2, el2)] + [
        ('r54-accept', ('flash', 6, 5), [('pro',)]),  # V06N05 mark-difference display after star 2
        ('p51-done', ('p00',), []),  # P51 sets REFSMMAT and exits via GOTOPOOH (P51-P53.agc P51G)
        ('p63-attempt', ('always',), [('keys', 'V37E63E')]),
    ]

    log = Path(output).open('w')
    emit = lambda r: log.write(json.dumps(r, separators=(',', ':')) + '\n')
    def snap(tick):
        s = {'ev': 'sample', 'cycle': tick}
        for k, a in ADDR.items(): s[k] = lib.inspect_ram(a)
        s['REFSMMAT'] = [lib.inspect_ram(REFSMMAT + i) for i in range(18)]
        return s
    emit({'ev': 'initial', 'start': START, 'end': END, 'ram_writes': 0,
          'star37': {'code': 1, 'az': az1, 'el': el1, 'az_text': deg_str(az1), 'el_text': deg_str(el1)},
          'star23': {'code': 15, 'az': az2, 'el': el2, 'az_text': deg_str(az2), 'el_text': deg_str(el2)},
          'az_el_rule': 'EL=asin(x), AZ=atan2(y,z); catalog B-1 vectors; OANB convention',
          'load_rule': 'V21/V22 load-data verbs; GOMARKF flashes block direct data-in',
          'mark_path': 'channel 016 bits 3/4 + KEYRUPT2 (index 6) via alignment_bridge.c'})

    queue = []          # pending (due_time, kind, payload) for scheduled actions
    step_i = 0
    action_q = []       # actions of the current step
    step_since = None
    ok_since = None     # when the current precondition was first observed
    started = False     # whether the current step's actions were loaded
    def start_actions(tick):
        nonlocal action_q, step_since
        action_q = list(steps[step_i][2])
        step_since = tick
        emit({'ev': 'step', 'cycle': tick, 'name': steps[step_i][0]})
    def queue_action(tick, act):
        kind = act[0]
        if kind == 'keys':
            for k in act[1]:
                queue.append((tick, 'packet', (0o15, KEY[k]))); tick += KEYGAP
        elif kind == 'load':
            seq = 'V' + act[1] + 'N' + act[2] + 'E' + act[3] + 'E'
            for k in seq:
                queue.append((tick, 'packet', (0o15, KEY[k]))); tick += KEYGAP
        elif kind == 'pro':
            queue.append((tick, 'packet', (PRO_CH, PRO_BIT))); tick += KEYGAP
            queue.append((tick, 'packet', (PRO_CH, 0))); tick += KEYGAP
        elif kind == 'marks':
            for b in (0o4, 0, 0o10, 0):
                queue.append((tick, 'mark', b)); tick += KEYGAP
        return tick

    tick = idx = 0; last = None
    while tick < END:
        while idx < len(sched) and sched[idx][0] == tick:
            _, kind, payload = sched[idx]; idx += 1
            emit({'ev': 'input', 'cycle': tick, 'channel': payload[0], 'value': payload[1],
                  'accepted': lib.packet_write(*payload)})
        while queue and queue[0][0] == tick:
            _, kind, payload = queue.pop(0)
            if kind == 'packet':
                emit({'ev': 'input', 'cycle': tick, 'channel': payload[0], 'value': payload[1],
                      'accepted': lib.packet_write(*payload)})
            else:
                lib.mark_write(payload, 1 if payload else 0)
                emit({'ev': 'mark', 'cycle': tick, 'bits': payload})
        n = min(853, END - tick)
        if idx < len(sched): n = min(n, sched[idx][0] - tick)
        if queue: n = min(n, queue[0][0] - tick)
        if n <= 0: n = 1
        used = lib.step_chunk(n)
        for i in range(used):
            w = lib.output_word(i); ch = (w >> 16) & 65535
            if ch in (0o11, 0o14, 0o16):
                emit({'ev': 'output', 'cycle': lib.output_cycle(i), 'channel': ch,
                      'value': w & 32767})
        tick += n
        s = snap(tick); key = tuple(v for k, v in s.items() if k not in ('ev', 'cycle'))
        if key != last: emit(s); last = key
        # Event-driven step machine (only after the baseline schedule).
        if tick >= START and step_i < len(steps) and not queue:
            name, pre, _ = steps[step_i]
            ok = False
            if pre[0] == 'always':
                ok = True
            elif pre[0] == 'flash':
                ok = (s['VERBREG'] == pre[1] and s['NOUNREG'] == pre[2])
            elif pre[0] == 'p00':
                ok = (s['MODREG'] == 0o77777)
            elif pre[0] == 'maybe-flash':
                ok = (s['VERBREG'] == pre[1] and s['NOUNREG'] == pre[2])
            if started:
                if action_q:
                    if ok:
                        if ok_since is None:
                            ok_since = tick
                        if tick - ok_since >= SETTLE:
                            queue_action(tick + KEYGAP, action_q.pop(0))
                            ok_since = None
                    else:
                        ok_since = None  # flash hidden by a monitor load; wait
                else:
                    # All actions queued and drained; the flash may already be
                    # gone (e.g. after PRO), so completion does not re-check pre.
                    step_i += 1
                    step_since = ok_since = None; started = False
            elif ok:
                if ok_since is None:
                    ok_since = tick
                if tick - ok_since >= SETTLE:
                    start_actions(tick)  # emits 'step', fills action_q
                    started = True
                    ok_since = None
            else:
                ok_since = None
                if step_since is None:
                    step_since = tick
                    emit({'ev': 'await', 'cycle': tick, 'name': name, 'pre': list(pre)})
                elif pre[0] == 'maybe-flash' and tick - step_since > pre[3]:
                    emit({'ev': 'skip', 'cycle': tick, 'name': name, 'pre': list(pre)})
                    step_i += 1
                    step_since = ok_since = None; started = False
                elif tick - step_since > STALL_LIMIT:
                    emit({'ev': 'stall', 'cycle': tick, 'name': name, 'pre': list(pre),
                          'verb': s['VERBREG'], 'noun': s['NOUNREG']})
                    step_i += 1
                    step_since = ok_since = None; started = False
    emit(snap(tick)); log.close()

if __name__ == '__main__': main()
