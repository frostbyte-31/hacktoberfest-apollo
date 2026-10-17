#!/usr/bin/env python3
"""Prepare documented mission INPUT words; never creates guidance results."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'math'))
from diagnostics import encode_physical


def create(candidate_name, name, omit_site=False):
    candidate = json.loads((HERE/'math'/candidate_name).read_text())
    tape = json.loads((HERE/'research/padload-transcription.json').read_text())
    targets = {item['symbol']: item for item in tape['mission_tape']}
    blocks = []

    def add(symbol, words, provenance, units, reason):
        blocks.append({'symbol': symbol, 'words': words,
                       'words_octal': [format(w, '05o') for w in words],
                       'provenance': provenance, 'units_and_scales': units, 'reason': reason})

    inputs = candidate['input_candidates']
    r, v = inputs['RRECTLEM'], inputs['VRECTLEM']
    state = [0o77775]+[int(w, 8) for data in (r, v) for w in data['raw_octal']]
    state += encode_physical(candidate['state_epoch_cs'], 28)
    add('UPSVFLAG', state, 'SYNTHETIC circular orbit: math/'+candidate_name+'; UPDATE_PROGRAM.agc:119-143 original LM lunar-state identifier',
        '77775 identifier; R metres B27, V m/cs B5, epoch cs B28; Moon-centered basic REF',
        'Original INTWAKEU/ATOPLEM establishes permanent navigation state and its own flags')
    add('TEPHEM', [0]*3, 'SYNTHETIC midnight 1 July 1969 epoch; LUNAR_AND_SOLAR_EPHEMERIDES_SUBROUTINES.agc:91-94',
        'TP centiseconds B42; TIMSUBO aliases TEPHEM', 'Explicitly anchor original lunar orientation constants')
    add('504LM', [0]*6, 'SYNTHETIC zero libration; PLANETARY_INERTIAL_ORIENTATION.agc:33-58',
        'DP radians B0 in Moon-fixed coordinates', 'Document the bounded nominal orientation approximation')
    if not omit_site:
        add('RLS', [int(w, 8) for w in inputs['RLS']['raw_octal']],
            'SYNTHETIC geometry from original MOONMX formulas; math/'+candidate_name,
            'Moon-fixed metres B27', 'Landing direction corresponds to basic REF +X at nominal TLAND; verify actual original RP-TO-R result')
    add('TLAND', encode_physical(candidate['TLAND_cs'], 28),
        'SYNTHETIC '+str(candidate['TLAND_cs'])+' cs; initial state epoch + original GUIDDURN 66440 cs',
        'DP centiseconds B28 from synthetic AGC clock zero', 'Original P63 selects its first integrated state epoch from TLAND-GUIDDURN')
    for group in [('RBRFG', 'VBRFG', 'ABRFG'), ('VBRFG*', 'ABRFG*', 'JBRFG*', 'GAINBRAK', 'TCGFBRAK', 'TCGIBRAK'),
                  ('VIGN', 'RIGNX', 'RIGNZ', 'KIGNX/B4', 'KIGNY/B8', 'KIGNV/B4'), ('ZOOMTIME',)]:
        records = [targets[symbol] for symbol in group]
        words = [int(w, 8) for record in records for w in record['words']]
        for left, right in zip(records, records[1:]):
            assert int(left['address'], 8)+len(left['words']) == int(right['address'], 8)
        add(group[0], words, {'kind': 'Published historical preflight target inputs, not a recovered flight state',
                            'source': tape['source'], 'sha256': tape['sha256'], 'records': records},
            [{'symbol': r['symbol'], 'units': r['units'], 'binary_scale': r['sf']} for r in records],
            'Original braking cubic/quadratic guidance, coordinate erection, and ignition-time iteration; never TABLTTF/TTF or readiness flags')
    result = {'classification': 'SYNTHETIC numerical-guidance fixture using published Apollo 11 target padloads',
              'candidate_file': 'math/'+candidate_name, 'synthetic_geometry': candidate,
              'negative_control': 'RLS omitted; incoherent landing geometry expected' if omit_site else False,
              'post_selection_horizon_cpu_calls': 1000000, 'blocks': blocks,
              'scope': 'Original P51/P27/P63 numerical initialization; no propulsion plant or descent demonstration'}
    (HERE/'configs').mkdir(exist_ok=True)
    (HERE/'configs'/(name+'.json')).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    create('synthetic-candidate-t120-angle050.json', 'mission-15km')
    create('synthetic-candidate-t120-angle050-alt16km.json', 'mission-16km')
    create('synthetic-candidate-t120-angle050.json', 'missing-site', omit_site=True)
