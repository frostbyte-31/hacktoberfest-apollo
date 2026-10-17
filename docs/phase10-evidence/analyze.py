#!/usr/bin/env python3
"""Inspect actual Phase10 instructions/data; never supplies AGC guidance."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'docs/phase9-evidence'))
# This file has the same basename as its predecessor. Load the retained
# independent packet/display checker explicitly instead of relying on sys.path.
import importlib.util
spec = importlib.util.spec_from_file_location('retained_p9_analysis', ROOT/'docs/phase9-evidence/analyze.py')
p9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p9)
sys.path.insert(0, str(HERE/'math'))
import diagnostics as mathcheck


def words(row, mapping, name, size=1):
    if name in mapping.get('relative_offsets', {}):
        offset = mapping['relative_offsets'][name]['offset']
        base = p9.words_for(row, mapping, 'FIXLOC')[0]
        indices = mapping['snapshot_addresses']
        try:
            return [row['snapshot_words'][indices.index(base+offset+i)] for i in range(size)]
        except ValueError as error:
            raise ValueError('Relative observer outside captured VAC area') from error
    return p9.words_for(row, mapping, name, size)


def read_json(path):
    return json.loads(Path(path).read_text())


def analyze_run(directory, negative=False):
    run = p9.load_run(directory)
    rows, mapping = run['rows'], run['mapping']
    config = read_json(Path(directory)/'configuration.json')
    old_checks = p9.analyze_run(run)['checks']
    # These two existing Phase9 assertions remain in its unmodified tests.
    # The new mission-input experiment has different expected root behavior.
    phase9_only = {'next_observed_alarm_is_01406_not_00220', 'root_failure_original_routines_observed'}
    checks = {'retained_'+name: value for name, value in old_checks.items() if name not in phase9_only}
    checkpoints = [r for r in rows if r['ev'] == 'checkpoint']
    routine = lambda name: [r for r in checkpoints if r['routine'] == name]
    plans = [r for r in rows if r['ev'] == 'mission_block']
    stores = [r for r in rows if r['ev'] == 'mission_block_stored']
    aligned = next(r for r in rows if r['ev'] == 'alignment_result')
    end = rows[-1]['state']
    checks.update({
        'all_configured_inputs_have_real_p27_transactions': [r['definition'] for r in plans] == config['blocks'] and len(stores) == len(plans) == len(routine('UPSTORE')) == len(routine('UPEND71')),
        'all_generic_padloads_match_actual_original_stores': all(r['actual_words'] == r['expected_words'] for r in stores if r['symbol'] != 'UPSVFLAG'),
        'state_update_original_intwake_clears_identifier_and_populates_permanent_state': any(r['symbol'] == 'UPSVFLAG' and r['mission_state']['UPSVFLAG'][0] in (0, 0o77777)
            and r['mission_state']['RRECTLEM'] == r['expected_words'][1:7] and r['mission_state']['VRECTLEM'] == r['expected_words'][7:13]
            and r['mission_state']['TETLEM'] == r['expected_words'][13:15] for r in stores),
        'alignment_matrix_and_flag_preserved_through_mission_inputs': end['refsmmat'] == aligned['state']['refsmmat'] and end['refsmflg'],
        'explicit_nominal_epoch_and_zero_libration': all(r['mission_state']['TEPHEM'] == [0]*3 and r['mission_state']['504LM'] == [0]*6 for r in stores),
        'p63_reaches_original_polynomial_construction': bool(routine('TTF/8CL')) and bool(routine('ROOTPSRS')),
    })
    polynomial_records = []
    root_records = []
    entries = routine('ROOTPSRS')
    for row in entries:
        table = words(row, mapping, 'TABLTTF', 10)
        expected = mathcheck.expected_coefficient_fractions(
            mathcheck.dp_fraction(words(row, mapping, 'RBRFG', 6)[4:6]),
            mathcheck.dp_fraction(words(row, mapping, 'RGU', 6)[4:6]),
            mathcheck.dp_fraction(words(row, mapping, 'VGU', 6)[4:6]),
            mathcheck.dp_fraction(words(row, mapping, 'VBRFG*', 2)),
            mathcheck.dp_fraction(words(row, mapping, 'ABRFG*', 2)),
            mathcheck.dp_fraction(words(row, mapping, 'JBRFG*', 2)))
        error_lsb = [float((mathcheck.dp_fraction(table[i*2:i*2+2])-value)*2**28) for i, value in enumerate(expected)]
        polynomial_records.append({'cycle': row['cycle'], 'observed': mathcheck.coefficient_diagnostics(table),
            'independent_formula_error_DP_LSB': error_lsb,
            'initial_guess_seconds': mathcheck.physical_dp(words(row, mapping, 'MPAC', 2), 17)/100,
            'RGU_m': mathcheck.decode_vector(words(row, mapping, 'RGU', 6), 24),
            'VGU_m_s': mathcheck.decode_vector(words(row, mapping, 'VGU', 6), 10, 100),
            'PIPTIME1_cs': mathcheck.physical_dp(words(row, mapping, 'PIPTIME1', 2), 28),
            'LAND_m': mathcheck.decode_vector(words(row, mapping, 'LAND', 6), 24)})
    for row in routine('ROOTSTOR_RESULT'):
        result = words(row, mapping, 'MPAC', 3)
        diag = mathcheck.coefficient_diagnostics(words(row, mapping, 'TABLTTF', 10), result[:2])
        dx = abs(float(mathcheck.dp_fraction(words(row, mapping, 'DXCRIT', 2))))
        continuation = next((r for r in routine('QUADGUID') if r['cycle'] > row['cycle']), None)
        root_records.append({'cycle': row['cycle'], 'iterations': result[2], 'diagnostics': diag,
            'original_DXCRIT_fraction': dx,
            'residual_within_original_step_tolerance_plus_32_DP_LSB': abs(diag['residual_fraction']) <= abs(diag['derivative_fraction'])*dx+32/2**28,
            'actual_normal_return_and_original_TTF_store': continuation is not None and words(continuation, mapping, 'TTF/8', 2) == result[:2]})
    checks['original_coefficients_match_independent_operand_formulas_within_2_DP_LSB'] = bool(polynomial_records) and all(max(map(abs, r['independent_formula_error_DP_LSB'])) <= 2 for r in polynomial_records)
    matrix = mathcheck.matrix_diagnostics(aligned['state']['refsmmat'])
    candidate = config['synthetic_geometry']
    state_input = next(r for r in stores if r['symbol'] == 'UPSVFLAG')['mission_state']
    state_diag = mathcheck.state_diagnostics(mathcheck.decode_vector(state_input['RRECTLEM'], 27),
        mathcheck.decode_vector(state_input['VRECTLEM'], 5, 100), [candidate['lunar_reference_radius_m'], 0, 0],
        candidate['mu_m3_s2'], candidate['lunar_reference_radius_m'])
    checks['input_state_is_bound_nearly_circular_lunar_orbit'] = (state_diag['bound_two_body_energy'] and 14000 < state_diag['altitude_above_reference_m'] < 17000
        and abs(state_diag['radial_velocity_m_s']) < .001 and abs(state_diag['speed_m_s']-state_diag['circular_speed_at_radius_m_s']) < .001)
    checks['actual_p51_matrix_numerically_proper'] = matrix['max_orthogonality_error'] < 1e-6 and abs(matrix['determinant']-1) < 1e-6
    if negative:
        checks.update({'site_really_absent': not any(p['definition']['symbol'] == 'RLS' for p in plans) and all(not any(words(r, mapping, 'RLS', 6)) for r in entries),
            'missing_site_reproduces_authentic_root_failure': bool(routine('BADROOT')) and bool(routine('1406POO')) and 0o1406 in end['failreg'],
            'missing_site_prevents_completed_ignition_solution': not routine('IGNALGRT')})
    else:
        checks.update({
            'nondegenerate_scaled_cubic_inputs': bool(polynomial_records) and all(not r['observed']['degenerate_all_zero'] and r['observed']['derivative_coefficient_abs_lt_one'] for r in polynomial_records),
            'each_original_root_returns_normally_and_stores_ttf': len(entries) == len(root_records) > 0 and all(r['actual_normal_return_and_original_TTF_store'] for r in root_records),
            'returned_countdowns_have_nonzero_derivative_and_small_residual': bool(root_records) and all(-1310.72 < r['diagnostics']['signed_time_to_go_seconds'] < 0 and r['diagnostics']['derivative_fraction'] != 0
                and r['residual_within_original_step_tolerance_plus_32_DP_LSB'] for r in root_records),
            'original_ignition_time_iteration_converges': bool(routine('IGNALGRT')),
            'no_new_program_alarms': end['failreg'] == [0o1520, 0, 0] and not routine('BADROOT') and not routine('1406POO'),
            'actual_next_display_is_preignition_n61': end['modreg'] == 63 and end['display']['VERB'] == '06' and end['display']['NOUN'] == '61',
            'original_ignition_solution_is_in_the_future': bool(routine('IGNALGRT')) and all(mathcheck.physical_dp(words(r, mapping, 'TIG', 2), 28)
                > mathcheck.physical_dp(words(r, mapping, 'TIME2', 2), 28) for r in routine('IGNALGRT')),
            'initial_ignition_lead_satisfies_source_midtoav1_schedule_bound': bool(routine('IGNALGRT')) and all(mathcheck.physical_dp(words(r, mapping, 'TIG', 2), 28)
                - 2990 - mathcheck.physical_dp(words(r, mapping, 'TIME2', 2), 28) >= 2000 for r in routine('IGNALGRT')),
        })
    checks = {name: bool(value) for name, value in checks.items()}
    return {'classification': 'VERIFIED negative control' if negative and all(checks.values()) else 'VERIFIED bounded numerical guidance' if all(checks.values()) else 'UNRESOLVED',
            'checks': checks, 'all_pass': all(checks.values()), 'raw_sha256': run['sha256'], 'raw_bytes': run['bytes'],
            'checkpoint_counts': {name: len(routine(name)) for name in mapping['checkpoints'] if routine(name)},
            'input_state_independent_diagnostics': state_diag, 'actual_p51_matrix_diagnostics': matrix,
            'polynomial_entries': polynomial_records, 'returned_roots': root_records, 'final_state': end,
            'ignition_solution': [{'cycle': r['cycle'], 'PIPTIME1_cs': mathcheck.physical_dp(words(r, mapping, 'PIPTIME1', 2), 28),
                'TIG_cs': mathcheck.physical_dp(words(r, mapping, 'TIG', 2), 28),
                'TIME2_cs': mathcheck.physical_dp(words(r, mapping, 'TIME2', 2), 28),
                'midtoav1_schedule_lead_cs_not_executed': mathcheck.physical_dp(words(r, mapping, 'TIG', 2), 28)-2990-mathcheck.physical_dp(words(r, mapping, 'TIME2', 2), 28),
                'TDEC1_cs': mathcheck.physical_dp(words(r, mapping, 'TDEC1', 2), 28)} for r in routine('IGNALGRT')]}


def experiment(directory, baseline):
    directory = Path(directory)
    final = analyze_run(directory/'final')
    repeat = analyze_run(directory/'repeat')
    variant = analyze_run(directory/'altitude-16km')
    missing = analyze_run(directory/'missing-site', True)
    p9baseline = read_json(baseline)
    comparisons = {
        'phase9_negative_baseline_reproduced_without_changes': p9baseline['all_pass'] and p9baseline['run']['raw_sha256'] == '343419a500fdcf9d548fabdc6eba4805a72490d72161e23153461fa31a3e7128',
        'full_repeat_native_trace_byte_identical': p9.raw(directory/'final/trace.jsonl') == p9.raw(directory/'repeat/trace.jsonl'),
        'coherent_altitude_change_changes_original_coefficients_and_root': final['polynomial_entries'][0]['observed']['coefficient_raw_octal'] != variant['polynomial_entries'][0]['observed']['coefficient_raw_octal']
            and final['returned_roots'][0]['diagnostics']['root_fraction'] != variant['returned_roots'][0]['diagnostics']['root_fraction'],
        'missing_landing_site_changes_actual_root_behavior': bool(final['returned_roots']) and not missing['ignition_solution'] and 0o1406 in missing['final_state']['failreg'],
    }
    return {'run': final, 'repeat': repeat, 'altitude_variant': variant, 'missing_site_control': missing,
            'comparisons': comparisons, 'all_pass': all(r['all_pass'] for r in (final, repeat, variant, missing)) and all(comparisons.values()),
            'scope': 'SYNTHETIC coherent lunar navigation + historical target padloads; original numerical guidance only; no powered descent'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--baseline-analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite analysis')
    result = experiment(args.runs, args.baseline_analysis)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'all_pass': result['all_pass'], 'comparisons': result['comparisons'],
        'failed_checks': {name: [k for k, v in result[name]['checks'].items() if not v] for name in ('run', 'repeat', 'altitude_variant', 'missing_site_control')}}))
    raise SystemExit(0 if result['all_pass'] else 1)
