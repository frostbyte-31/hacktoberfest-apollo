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
