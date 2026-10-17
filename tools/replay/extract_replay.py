"""Read-only extraction of recorded Phase 7/8 traces into a compact replay file for the visual demo.

Reads docs/phase7-evidence/runs/{closed,feedback_off}.jsonl and docs/phase8-evidence/runs/p63.jsonl
(never writes there). Output: src/data/replay.json. Every value is copied from a recorded row; the
only processing is downsampling (one vehicle sample per ~0.1 s convention time) and source hashes.
"""
from pathlib import Path
import json, hashlib
ROOT = Path(__file__).resolve().parents[2]
SEC = 0.00001172

def rows(p): return [json.loads(l) for l in p.read_text().splitlines()]

def run7(name):
    p = ROOT / f'docs/phase7-evidence/runs/{name}.jsonl'
    r = rows(p); frames = []; cdu = [0, 0, 0]; jets = [0, 0]; last = -1e9; events = []
    for x in r:
        if x['ev'] == 'sample': cdu = x['cdu']
        if x['ev'] == 'input': events.append({'t': x['cycle'] * SEC, 'kind': 'input', 'text': f"INPUT ch{x['channel']:03o} = {x['value']:05o}"})
        if x['ev'] == 'output' and x['channel'] in (5, 6) and x['value'] != jets[x['channel'] - 5]:
            jets[x['channel'] - 5] = x['value']
            events.append({'t': x['cycle'] * SEC, 'kind': 'rcs', 'text': f"RCS ch{x['channel']:03o} = {x['value']:05o}"})
        if x['ev'] == 'plant' and x['cycle'] * SEC - last >= 0.1:
            last = x['cycle'] * SEC
            frames.append({'t': round(last, 4), 'omega': x['omega'], 'gimbals': x['gimbals'], 'jets': x['jets'], 'cdu': cdu})
    sensors = [x for x in r if x['ev'] == 'sensor']
    return {'name': name, 'source': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'frames': frames, 'events': events,
            'sensor_generated': len(sensors), 'sensor_delivered': sum(x['delivered'] for x in sensors),
            'final_cdu': [x for x in r if x['ev'] == 'sample'][-1]['cdu']}

def run8():
    p = ROOT / 'docs/phase8-evidence/runs/p63.jsonl'
    r = rows(p); events = []; prev = {}
    names = {17: 'VERB', 31: 'NOUN', 28: 'ENTR'}
    for x in r:
        if x['ev'] == 'input' and x['cycle'] >= 3000000:
            events.append({'t': x['cycle'] * SEC, 'kind': 'key', 'text': f"KEY {names.get(x['value'], x['value'])}"})
        if x['ev'] == 'output' and x['channel'] == 0o14 and x['value'] & 0o10:
            events.append({'t': x['cycle'] * SEC, 'kind': 'throttle', 'text': f"ch014 bit4 drive word {x['value']:05o} (meaning unverified)"})
        if x['ev'] == 'sample':
            for k in ('MODREG', 'FAILREG0', 'FAILREG1', 'THRUST'):
                if prev.get(k) != x[k] and x['cycle'] > 2900000:
                    kind = 'alarm' if k.startswith('FAIL') and x[k] else 'state'
                    events.append({'t': x['cycle'] * SEC, 'kind': kind, 'text': f"{k} = {x[k]:05o}"})
            prev = x
    final = [x for x in r if x['ev'] == 'sample'][-1]
    return {'source': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'events': events, 'final': final}

out = ROOT / 'src/data/replay.json'; out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'phase7': {'closed': run7('closed'), 'feedback_off': run7('feedback_off')}, 'phase8': run8()}, separators=(',', ':')))
print(out, out.stat().st_size)

# --- Phase 9 (added for the learning frontend; read-only on evidence) ---
def run9(name='alignment-05'):
    p = ROOT / f'docs/phase9-evidence/runs/{name}.jsonl'
    r = rows(p); states = []; events = []; prev = {}
    label = {'enter-p51': 'Driver keys V37E51E (select P51)', 'v50n25-proceed': 'PROCEED at V50N25 (start sightings)',
             'r54-accept': 'PROCEED to accept star-angle difference (V06N05)', 'p63-attempt': 'Driver keys V37E63E (select P63)'}
    for x in r:
        t = x.get('cycle', 0) * SEC
        if x['ev'] == 'step':
            n = x['name']; txt = label.get(n)
            if not txt:
                star = 'Star 1' if n.startswith('s1') else 'Star 2'
                txt = {'load-code': 'load star code (V21 N71)', 'pro-code': 'PROCEED star code', 'load-az': 'load AOT azimuth (V21 N87)',
                       'load-el': 'load AOT elevation (V22 N87)', 'pro-azel': 'PROCEED angles', 'marks': 'begin AOT marks',
                       'pro-marks': 'PROCEED after marks'}.get(n[3:], n)
                txt = f'{star}: {txt}'
            events.append({'t': t, 'kind': 'key', 'text': txt})
        if x['ev'] == 'mark' and x['bits']:
            events.append({'t': t, 'kind': 'input', 'text': f"AOT mark pulse ch016 bits {x['bits']:o}"})
        if x['ev'] == 'skip':
            events.append({'t': t, 'kind': 'input', 'text': f"Optional V05N71 flash not shown ({x['name']}); continued"})
        if x['ev'] == 'stall':
            events.append({'t': t, 'kind': 'input', 'text': 'Driver wait for P00 timed out; display V37 (continued to P63 step)'})
        if x['ev'] == 'sample':
            s = {'t': round(t, 4), 'prog': x['MODREG'], 'verb': x['VERBREG'], 'noun': x['NOUNREG'], 'f0': x['FAILREG0'],
                 'f1': x['FAILREG1'], 'f2': x['FAILREG2'], 'flag3': x['FLAGWRD3'], 'refs': any(x['REFSMMAT'])}
            if prev:
                if prev['prog'] != s['prog']: events.append({'t': t, 'kind': 'state', 'text': f"MODREG (PROG) = {s['prog']:02d}"})
                if prev['f0'] != s['f0'] and s['f0']: events.append({'t': t, 'kind': 'alarm', 'text': f"FAILREG0 = {s['f0']:05o}"})
                if prev['f1'] != s['f1'] and s['f1']: events.append({'t': t, 'kind': 'alarm', 'text': f"FAILREG1 = {s['f1']:05o}"})
                if (prev['flag3'] ^ s['flag3']) & 0o10000: events.append({'t': t, 'kind': 'state', 'text': f"REFSMFLG {'SET' if s['flag3'] & 0o10000 else 'CLEARED'} (FLAGWRD3 {s['flag3']:05o})"})
                if prev['refs'] != s['refs']: events.append({'t': t, 'kind': 'state', 'text': 'REFSMMAT populated (18 words nonzero)'})
            states.append(s); prev = s
    events.sort(key=lambda e: e['t'])
    final = [x for x in r if x['ev'] == 'sample'][-1]
    return {'name': name, 'source': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'states': states, 'events': events, 'initial': r[0], 'final_refsmmat': final['REFSMMAT']}

d = json.loads(out.read_text()); d['phase9'] = run9()
out.write_text(json.dumps(d, separators=(',', ':'))); print('phase9 added', out.stat().st_size)
