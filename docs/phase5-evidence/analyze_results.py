"""Summarize retained observations, not expected or synthesized emulator outputs."""
from pathlib import Path
import json, collections, hashlib
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def rows(path): return [json.loads(l) for l in path.read_text().splitlines()]
def main():
    result = {'readiness': {}, 'loop': {}}
    for name in ['baseline', 'operate', 'repeat', 'off']:
        data = rows(HERE / 'runs' / (name + '.stdout'))
        checkpoints = collections.Counter((r['bank'], r['z']) for r in data if r['ev'] == 'checkpoint')
        rcs = [r for r in data if r['ev'] == 'output' and r['channel'] in (5, 6)]
        before = [r for r in data if r['ev'] == 'before']
        result['readiness'][name] = {
            'checkpoints': {f'{b:02o},{z:04o}': c for (b, z), c in checkpoints.items()},
            'rcs_packets': len(rcs), 'nonzero_rcs_packets': sum(bool(r['value']) for r in rcs),
            'first_nonzero_rcs': next((r for r in rcs if r['value']), None),
            'first_readiness_cleared_snapshot': next((r for r in before if r['bank'] == 6 and not r['imodes33'] & 32), None),
            'last_sample': [r for r in data if r['ev'] == 'sample'][-1]}
    for name in ['closed', 'feedback_off', 'blocked', 'negative', 'repeat']:
        data = rows(HERE / 'loop-runs' / (name + '.jsonl'))
        plant = [r for r in data if r['ev'] == 'plant']
        samples = [r for r in data if r['ev'] == 'sample']
        rcs = [r for r in data if r['ev'] == 'output' and r['channel'] in (5, 6)]
        sensors = [r for r in data if r['ev'] == 'sensor']
        result['loop'][name] = {
            'nonzero_rcs_words': {f'{c:03o}:{v:05o}': n for (c, v), n in collections.Counter((r['channel'], r['value']) for r in rcs if r['value']).items()},
            'first_nonzero_rcs': next((r for r in rcs if r['value']), None),
            'sensor_packets_generated': len(sensors), 'sensor_packets_delivered': sum(r['delivered'] for r in sensors),
            'first_sensor_readback': next((r for r in samples if any(r['cdu'])), None),
            'max_abs_yaw_rate': max(abs(r['omega'][0]) for r in plant),
            'final_plant': plant[-1], 'final_sample': samples[-1],
            'nonzero_channel005': sum(r['channel'] == 5 and bool(r['value']) for r in rcs),
            'non_x_sensor_packets': sum(r['counter'] != 0o32 for r in sensors)}
    result['readiness_replay_byte_identical'] = (HERE / 'runs/operate.stdout').read_bytes() == (HERE / 'runs/repeat.stdout').read_bytes()
    result['loop_replay_byte_identical'] = (HERE / 'loop-runs/closed.jsonl').read_bytes() == (HERE / 'loop-runs/repeat.jsonl').read_bytes()
    baseline = rows(HERE / 'runs/baseline.stdout')
    prior = rows(ROOT / 'docs/phase4-evidence/runs/probe.stdout')
    result['baseline_preserves_phase4_outputs_and_samples'] = [r for r in baseline if r['ev'] in ('initial', 'input', 'output', 'sample')] == [r for r in prior if r['ev'] in ('initial', 'input', 'output', 'sample')]
    hashes = json.loads((HERE / 'prior_hashes.json').read_text())
    bad = [p for p, h in hashes.items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    result['prior_preservation'] = {'files': len(hashes), 'mismatches': bad}
    (HERE / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
if __name__ == '__main__': main()