"""GPL-2.0-or-later. Summarize Phase 7 raw traces; checks computed only from recorded rows."""
from pathlib import Path
import json, sys, collections, hashlib

def load(p): return [json.loads(l) for l in Path(p).read_text().splitlines()]

def summary(rows):
    out = [r for r in rows if r['ev'] == 'output']
    plants = [r for r in rows if r['ev'] == 'plant']
    sensors = [r for r in rows if r['ev'] == 'sensor']
    samples = [r for r in rows if r['ev'] == 'sample']
    jets = [(r['cycle'], r['channel'], r['value']) for r in out if r['channel'] in (5, 6)]
    first = lambda f: next((r for r in rows if f(r)), None)
    return {
        'mode': rows[0]['mode'],
        'nonzero_jet_words_octal': dict(collections.Counter(f'{c:03o}:{v:05o}' for _, c, v in jets if v)),
        'first_ch005_nonzero': first(lambda r: r['ev'] == 'output' and r['channel'] == 5 and r['value']),
        'first_pitch_motion': first(lambda r: r['ev'] == 'plant' and r['omega'][1] != 0),
        'first_sensor': first(lambda r: r['ev'] == 'sensor'),
        'first_cdu_y_readback': first(lambda r: r['ev'] == 'sample' and r['cdu'][1] != 0),
        'peak_abs_omega_yaw_pitch_roll_deg_s': [max(abs(r['omega'][i]) for r in plants) for i in range(3)],
        'final_model': plants[-1],
        'sensor_generated_by_counter_octal': {f'{k:03o}': v for k, v in collections.Counter(r['counter'] for r in sensors).items()},
        'sensor_delivered': sum(r['delivered'] for r in sensors),
        'sensor_accepted': sum(1 for r in sensors if r['delivered'] and r['accepted'] > 0),
        'final_agc_readback': samples[-1],
        'jets': jets,
    }

def main(d):
    d = Path(d); s = {m: summary(load(d / f'{m}.jsonl')) for m in ('closed', 'feedback_off', 'negative', 'repeat')}
    c, off, neg = s['closed'], s['feedback_off'], s['negative']
    sign = lambda x: (x > 0) - (x < 0)
    pk = lambda m: max((r for r in load(d / f'{m}.jsonl') if r['ev'] == 'plant'), key=lambda r: abs(r['omega'][1]))['omega'][1]
    baseline = hashlib.sha256((d / 'yaw_baseline.jsonl').read_bytes()).hexdigest()
    checks = {
        'single_axis_baseline_matches_phase6': baseline == '9708a22c8066d2d829e756b5f3a865f0ab68a7ff5c27dae05403174944fdad99',
        'agc_emits_nonzero_channel005': c['first_ch005_nonzero'] is not None,
        'pitch_motion_from_agc_jets': c['peak_abs_omega_yaw_pitch_roll_deg_s'][1] > 0,
        'cdu_y_readback_nonzero_connected': c['final_agc_readback']['cdu'][1] != 0,
        'feedback_changes_agc_jet_transcript': c['jets'] != off['jets'],
        'disconnected_readback_all_zero': off['final_agc_readback']['cdu'] == [0, 0, 0],
        'disconnected_generated_none_delivered': off['sensor_delivered'] == 0 and sum(off['sensor_generated_by_counter_octal'].values()) > 0,
        'connected_all_sensor_accepted': c['sensor_delivered'] == c['sensor_accepted'] > 0,
        'negative_reverses_pitch_sign': sign(pk('closed')) == -sign(pk('negative')) != 0,
        'replay_byte_identical': (d / 'closed.jsonl').read_bytes() == (d / 'repeat.jsonl').read_bytes(),
        'no_yaw_axis_motion_in_pitch_runs': all(s[m]['peak_abs_omega_yaw_pitch_roll_deg_s'][0] == 0 for m in s),
    }
    cross = {m: {'peak_roll_deg_s': s[m]['peak_abs_omega_yaw_pitch_roll_deg_s'][2],
                 'final_gimbals_deg': s[m]['final_model']['gimbals'],
                 'final_cdu': s[m]['final_agc_readback']['cdu']} for m in s}
    for v in s.values(): v.pop('jets')
    (d / 'summary.json').write_text(json.dumps({'runs': s, 'cross_axis': cross}, indent=2) + '\n')
    (d / 'validation.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2)); print(json.dumps(cross, indent=2))
    if not all(checks.values()): sys.exit(1)

if __name__ == '__main__': main(sys.argv[1])
