#!/usr/bin/env python3
"""Independent inspection of Phase 10 original-state numerical observations.

Reads traces only. Does not solve a polynomial, drive a CPU, mutate memory,
or change a mission configuration to fit an observed result.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from candidate_geometry import moon_matrix
from diagnostics import (coefficient_diagnostics, decode_vector, dot, dp_fraction,
                         expected_coefficient_fractions, matrix_diagnostics, norm,
                         physical_dp, read_trace)


def matvec(matrix, vector):
    return [dot(row, vector) for row in matrix]


def transpose(matrix):
    return list(map(list, zip(*matrix)))


def cross(left, right):
    a, b, c = left
    d, e, f = right
    return [b*f-c*e, c*d-a*f, a*e-b*d]


def difference(left, right):
    return [a-b for a, b in zip(left, right)]


def inspect_run(run):
    trace = run/'trace.jsonl'
    if not trace.exists():
        trace = trace.with_suffix('.jsonl.gz')
    raw, rows = read_trace(trace)
    mapping = json.loads((run/'observer-map.json').read_text())
    configuration = json.loads((run/'configuration.json').read_text())
    candidate = configuration['synthetic_geometry']
    constants = {name: data['fraction'] for name, data in candidate['immutable_rope_constants'].items()}
    addresses = mapping['snapshot_addresses']

    def words(row, name, size):
        start = mapping['addresses'][name]
        return [row['snapshot_words'][addresses.index(start+i)] for i in range(size)]

    def relative(row, name):
        start = words(row, 'FIXLOC', 1)[0]+mapping['relative_offsets'][name]['offset']
        return [row['snapshot_words'][addresses.index(start+i)]
                for i in range(mapping['relative_offsets'][name]['size'])]

    checkpoints = [row for row in rows if row['ev'] == 'checkpoint']
    entries = [row for row in checkpoints if row['routine'] == 'ROOTPSRS']
    results = [row for row in checkpoints if row['routine'] == 'ROOTSTOR_RESULT']
    output = {'scope': 'Independent diagnostics of actual native guidance, not substitute guidance',
              'input_run': str(run), 'raw_trace_sha256': hashlib.sha256(raw).hexdigest(),
              'observer_map_sha256': hashlib.sha256((run/'observer-map.json').read_bytes()).hexdigest(),
              'configuration_sha256': hashlib.sha256((run/'configuration.json').read_bytes()).hexdigest(),
              'root_entries': len(entries), 'original_normal_returns': len(results), 'passes': []}
    for index, entry in enumerate(entries):
        next_cycle = entries[index+1]['cycle'] if index+1 < len(entries) else float('inf')
        returns = [row for row in results if entry['cycle'] < row['cycle'] < next_cycle]
        result = returns[0] if len(returns) == 1 else None
        table = words(entry, 'TABLTTF', 8)
        observed_coefficients = [dp_fraction(table[i:i+2]) for i in (0, 2, 4, 6)]
        expected = expected_coefficient_fractions(
            dp_fraction(words(entry, 'RBRFG', 6)[4:]), dp_fraction(words(entry, 'RGU', 6)[4:]),
            dp_fraction(words(entry, 'VGU', 6)[4:]), dp_fraction(words(entry, 'VBRFG*', 2)),
            dp_fraction(words(entry, 'ABRFG*', 2)), dp_fraction(words(entry, 'JBRFG*', 2)))
        ref = matrix_diagnostics(words(entry, 'REFSMMAT', 18))
        refmatrix = ref['direction_cosines_reference_to_stable_member']
        cg = matrix_diagnostics(words(entry, 'CG', 18))
        cgmatrix = cg['direction_cosines_reference_to_stable_member']
        tpip_cs = physical_dp(words(entry, 'TPIP', 2), 28)
        tland_cs = physical_dp(words(entry, 'TLAND', 2), 28)
        site = decode_vector(words(entry, 'RLS', 6), 27)
        land = decode_vector(words(entry, 'LAND', 6), 24)
        # Original GUILDRET moves LAND from its earlier TPIP to the current
        # PIPTIME1. A first-pass LAND must be compared at TPIP, not TLAND.
        site_at_landing = matvec(refmatrix, matvec(transpose(moon_matrix(constants, tland_cs)), site))
        site_at_current = matvec(refmatrix, matvec(transpose(moon_matrix(constants, tpip_cs)), site))
        r = decode_vector(words(entry, 'R', 6), 24)
        v = decode_vector(words(entry, 'V', 6), 7, 100)
        omega = decode_vector(words(entry, 'WM', 6), -17, 100)
        rgu = decode_vector(words(entry, 'RGU', 6), 24)
        vgu = decode_vector(words(entry, 'VGU', 6), 10, 100)
        rgu_expected = matvec(cgmatrix, difference(r, land))
        vgu_expected = matvec(cgmatrix, difference(v, cross(omega, r)))
        ratt1 = decode_vector(relative(entry, 'RATT1'), 27)
        r_expected = matvec(refmatrix, ratt1)
        record = {'entry_cycle': entry['cycle'], 'normal_return_cycle': result['cycle'] if result else None,
                  'original_result': coefficient_diagnostics(table, words(result, 'MPAC', 2) if result else None),
                  'coefficient_ideal_minus_observed_DP_LSB': [float((a-b)*2**28)
                                                             for a, b in zip(expected, observed_coefficients)],
                  'REFSMMAT': ref, 'CG': cg,
                  'TPIP_cs': tpip_cs, 'TLAND_cs': tland_cs,
                  'AGC_COMPUTED': {'R_m_SM': r, 'V_m_s_SM': v, 'LAND_m_SM_at_TPIP': land,
                                   'RGU_m': rgu, 'VGU_m_s': vgu, 'omega_rad_s_SM': omega,
                                   'integration_RATT1_m_REF': ratt1},
                  'INDEPENDENT_VALIDATION': {
                      'site_m_SM_at_TLAND': site_at_landing, 'site_m_SM_at_TPIP': site_at_current,
                      'LAND_minus_independent_current_epoch_m': difference(land, site_at_current),
                      'LAND_current_epoch_error_norm_m': norm(difference(land, site_at_current)),
                      'R_minus_REFSM_transformed_RATT1_m': difference(r, r_expected),
                      'RGU_minus_CG_R_minus_LAND_m': difference(rgu, rgu_expected),
                      'VGU_minus_CG_surface_velocity_m_s': difference(vgu, vgu_expected)}}
        if index == 0:
            # Independent evaluation of the source's first-order lunar rotation
            # update, using actual original WM rather than a modern rate model.
            dt_seconds = (tpip_cs-tland_cs)/100
            unnormalized = difference(site_at_landing, [dt_seconds*x for x in cross(site_at_landing, omega)])
            first_order = [x*norm(site)/norm(unnormalized) for x in unnormalized]
            record['INDEPENDENT_VALIDATION'].update(
                original_TTFINCR_first_order_formula_m=first_order,
                LAND_minus_source_transport_formula_m=difference(land, first_order),
                LAND_source_transport_error_norm_m=norm(difference(land, first_order)))
        output['passes'].append(record)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite prior diagnostics')
    result = inspect_run(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'root_entries': result['root_entries'], 'original_normal_returns': result['original_normal_returns'],
                      'root_seconds': [r['original_result'].get('signed_time_to_go_seconds') for r in result['passes']],
                      'current_epoch_LAND_errors_m': [r['INDEPENDENT_VALIDATION']['LAND_current_epoch_error_norm_m'] for r in result['passes']],
                      'max_coefficient_comparison_DP_LSB': max((max(map(abs, r['coefficient_ideal_minus_observed_DP_LSB']))
                                                              for r in result['passes']), default=None)}, indent=2))


if __name__ == '__main__':
    main()
