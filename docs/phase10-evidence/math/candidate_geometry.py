#!/usr/bin/env python3
"""SYNTHETIC initial-state geometry derived from immutable rope constants.

Only source-supported input coordinate preparation and independent diagnostics.
No guidance calculations, CPU driver, memory loader, or original-state mutation.
The moon matrix formula follows PLANETARY_INERTIAL_ORIENTATION.agc:151-263.
Actual AGC RP-TO-R/MMATRIX output must independently agree before claiming the
runtime state is coherent; this calculation is not evidence of that agreement.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from diagnostics import dp_fraction, encode_physical, decode_vector, state_diagnostics


def fixed_words(rope, symbols, name):
    symbol = symbols[name]
    bank = symbol['fixedBank']
    # Exact set_fixed file ordering from pinned yaAGC/wasm.c:62-91.
    file_bank = {2: 0, 3: 1, 0: 2, 1: 3}.get(bank, bank)
    offset = 2*(1024*file_bank+symbol['offset'])
    return [int.from_bytes(rope[offset+i:offset+i+2], 'big') >> 1 for i in (0, 2)]


def moon_matrix(constants, time_cs):
    # NEWANGLE X=X0+XDOT*(T+T0); diagnostic T0=0 (synthetic nominal epoch).
    b = math.tau*(constants['BSUBO']+constants['BDOT']*2**-28*time_cs)
    n = math.tau*(constants['NODIO']+constants['NODDOT']*2**-28*time_cs)
    f = math.tau*(constants['FSUBO']+constants['FDOT']*2**-27*time_cs)
    ci, si = 2*constants['COSI'], 2*constants['SINI']
    a = [math.cos(n), math.sin(n)*math.cos(b), math.sin(n)*math.sin(b)]
    bvec = [-math.sin(n), math.cos(n)*math.cos(b), math.cos(n)*math.sin(b)]
    c = [0, -math.sin(b), math.cos(b)]
    d = [ci*x-si*y for x, y in zip(bvec, c)]
    return [[-(x*math.cos(f)+y*math.sin(f)) for x, y in zip(a, d)],
            [x*math.sin(f)-y*math.cos(f) for x, y in zip(a, d)],
            [si*x+ci*y for x, y in zip(bvec, c)]]


def build_candidate(rope_path, symbols_path, epoch_cs, theta=.15, altitude_m=15000):
    rope = rope_path.read_bytes()
    table = json.loads(symbols_path.read_text())['symbols']
    names = ['MUM', 'RSUBM', 'COSI', 'SINI', 'BSUBO', 'NODIO', 'FSUBO', 'BDOT', 'NODDOT', 'FDOT', 'MOONRATE']
    words = {name: fixed_words(rope, table, name) for name in names}
    values = {name: float(dp_fraction(raw)) for name, raw in words.items()}
    mu = values['MUM']*2**30*10000
    rm = values['RSUBM']*2**29
    r = rm+altitude_m
    v = math.sqrt(mu/r)
    landing_cs = epoch_cs+66440
    matrix = moon_matrix(values, landing_cs)
    # The landing site at TLAND is +X in basic REF: RP=M(TLAND)*[RM,0,0].
    site = [row[0]*rm for row in matrix]
    position = [r*math.cos(theta), 0, -r*math.sin(theta)]
    velocity = [v*math.sin(theta), 0, v*math.cos(theta)]
    inputs = {'RRECTLEM': {'value': position, 'units': 'm', 'binary_scale': 27},
              'VRECTLEM': {'value': velocity, 'units': 'm/s', 'binary_scale': 5, 'cs_factor': 100},
              'RLS': {'value': site, 'units': 'm Moon-fixed', 'binary_scale': 27}}
    for value in inputs.values():
        encoded = sum((encode_physical(x, value['binary_scale'], value.get('cs_factor', 1))
                       for x in value['value']), [])
        value.update(raw_octal=[format(w, '05o') for w in encoded],
                     encoded_si_readback=decode_vector(encoded, value['binary_scale'], value.get('cs_factor', 1)))
    return {'classification': 'SYNTHETIC CANDIDATE, not native experiment evidence',
            'rope_sha256': hashlib.sha256(rope).hexdigest(),
            'symbols_sha256': hashlib.sha256(symbols_path.read_bytes()).hexdigest(),
            'assumptions': ['Moon-centered basic-REF inertial circular orbit',
                            'Clock zero at synthetic nominal lunar orientation epoch, TEPHEM=0',
                            'Zero libration, not historical Apollo 11 geometry',
                            'Fixed stable member uses actual near-identity Phase 9 matrix',
                            'Landing direction is basic REF +X at nominal landing time',
                            'State initialized at epoch, no modern propagation or guidance'],
            'immutable_rope_constants': {name: {'raw_octal': [format(w, '05o') for w in words[name]],
                                               'fraction': values[name]} for name in names},
            'mu_m3_s2': mu, 'lunar_reference_radius_m': rm, 'state_epoch_cs': epoch_cs,
            'TLAND_cs': landing_cs, 'initial_angle_behind_target_rad': theta,
            'independent_physical_moon_matrix_at_TLAND': matrix,
            'input_candidates': inputs,
            'diagnostics': state_diagnostics(position, velocity, [rm, 0, 0], mu, rm),
            'caution': 'All targeting padloads remain separately specified mission inputs; this geometry alone does not establish a guidance solution'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rope', required=True, type=Path)
    parser.add_argument('--symbols', required=True, type=Path)
    parser.add_argument('--epoch-cs', required=True, type=int)
    parser.add_argument('--theta', default=.15, type=float)
    parser.add_argument('--altitude-m', default=15000, type=float)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite prior candidate')
    result = build_candidate(args.rope, args.symbols, args.epoch_cs, args.theta, args.altitude_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
