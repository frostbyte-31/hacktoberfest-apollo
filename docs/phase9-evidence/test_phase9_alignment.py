"""Phase 9 regression tests: P51 alignment experiment driver and evidence.

Run from the project root:  python3 docs/phase9-evidence/test_phase9_alignment.py
These tests check the driver corrections and the recorded evidence; they do not
re-run the emulator (the probe itself is the execution test).
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = os.path.join(ROOT, 'docs', 'phase9-evidence')
RUNS = os.path.join(EV, 'runs')

passed = failed = 0


def check(name, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
        print('PASS', name)
    else:
        failed += 1
        print('FAIL', name, detail)


def load(run):
    with open(os.path.join(RUNS, run)) as f:
        return [json.loads(l) for l in f]


# 1. Driver uses the authentic PRO bit: channel 032 bit 14 = 0o20000
#    (INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc: "BIT 14 INDICATES PROCEED KEY
#    IS DEPRESSED"). Bit 15 (0o40000) was the original bug.
src = open(os.path.join(EV, 'alignment_probe.py')).read()
check('pro-bit', 'PRO_CH, PRO_BIT = 0o32, 0o20000' in src)

# 2. deg_str must emit 5 digits for values < 100 deg (CDU DEG field xxx.xx).
sys.path.insert(0, EV)
import alignment_probe as ap  # noqa: E402
check('deg-str-width', ap.deg_str(56.54) == '+05654' and ap.deg_str(-20.95) == '-02095',
      ap.deg_str(56.54) + ' ' + ap.deg_str(-20.95))
check('deg-str-large', ap.deg_str(-154.27) == '-15427', ap.deg_str(-154.27))

# 3. alignment-05 (the completing run): P51 finished through original software.
r5 = load('alignment-05.jsonl')
steps5 = [r['name'] for r in r5 if r.get('ev') == 'step']
check('all-steps-fired', 'r54-accept' in steps5 and 'p63-attempt' in steps5, str(steps5))
check('no-stall-before-r54', not any(r.get('ev') == 'stall' and r['name'] not in ('p51-done',)
                                     for r in r5))
last5 = [r for r in r5 if r.get('ev') == 'sample'][-1]
check('refsmmat-nonzero', any(w != 0 for w in last5['REFSMMAT']))
check('refsmflg-set', last5['FLAGWRD3'] & 0o10000 != 0, 'FLAGWRD3=%o' % last5['FLAGWRD3'])

# 4. P63 was selected and passed the R02 REFSMMAT check: no alarm 00220;
#    the ignition algorithm aborted with POODOO 01406 on uninitialized
#    descent targeting data (expected without a P64-target load).
check('p63-selected', last5['MODREG'] == 0o77, 'MODREG=%o' % last5['MODREG'])
check('no-00220', last5['FAILREG0'] != 0o220 and last5['FAILREG1'] != 0o220)
check('ignition-abort-01406', last5['FAILREG1'] == 0o1406, 'FAILREG1=%o' % last5['FAILREG1'])
# FAILREG0=01520 is pre-existing from the unchanged Phase 5 startup (V37 request
# rejected at cycle 1128851, long before P51 entry at 3554763).
check('startup-1520-preserved', last5['FAILREG0'] == 0o1520)

# 5. Replay determinism: alignment-05 and alignment-06 are byte-identical events.
r6 = load('alignment-06.jsonl')
check('replay-identical', r5 == r6)

# 6. Prior evidence (Phases 1-8) unchanged.
with open(os.path.join(EV, 'prior_hashes.json')) as f:
    H = json.load(f)
files = H if isinstance(H, dict) else H.get('files', H)
bad = [p for p, h in files.items()
       if not os.path.exists(p) or hashlib.sha256(open(p, 'rb').read()).hexdigest() != h]
check('prior-evidence-intact', not bad, str(bad[:5]))

print('Phase 9: %d passed, %d failed' % (passed, failed))
sys.exit(1 if failed else 0)
