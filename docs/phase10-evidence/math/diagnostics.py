#!/usr/bin/env python3
"""Independent Phase 10 arithmetic checks; never loads or drives the AGC.

All inputs are observed raw words. Modern arithmetic is used only to inspect
original AGC results, never to supply a controller or replace ROOTPSRS.
"""
import argparse
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path

WORD_MASK = 0o77777
SIGN = 0o40000
DP_DENOMINATOR = 1 << 28


def signed_sp(word):
    """Signed magnitude of a 15-bit one's-complement word; both zeros -> 0."""
    if type(word) is not int or not 0 <= word <= WORD_MASK:
        raise ValueError('Expected a 15-bit AGC word without parity/overflow')
    return -(word ^ WORD_MASK) if word & SIGN else word


def dp_count(words):
    """Exact DP integer, including unlike signs and signed-zero low words.

    agc_engine.c SpToDecent describes the two signed SP words, MSW first.
    A word contributes its one's-complement signed value with 14-bit radix.
    Thus [20000,77777] octal is +.5, not .500061... .
    """
    if len(words) != 2:
        raise ValueError('DP requires exactly two adjacent words')
    return signed_sp(words[0]) * (1 << 14) + signed_sp(words[1])


def dp_fraction(words):
    return Fraction(dp_count(words), DP_DENOMINATOR)


def encode_fraction(value):
    """Canonical DP words rounded as original Parse2DEC; input preparation only."""
    value = Fraction(value)
    if abs(value) >= 1:
        raise ValueError('DP fractional magnitude must be less than one')
    magnitude = abs(value) * DP_DENOMINATOR
    count = magnitude.numerator // magnitude.denominator
    if magnitude-count >= Fraction(1, 2):
        count += 1
    if count >= DP_DENOMINATOR:
        raise ValueError('Rounded DP fraction overflows')
    words = [count >> 14, count & 0o37777]
    return [word ^ WORD_MASK for word in words] if value < 0 else words


def encode_physical(value, binary_scale, centiseconds_per_second=1):
    """Prepare specified mission input; this function never loads AGC memory."""
    value = Fraction(str(value))
    return encode_fraction(value / (Fraction(2)**binary_scale * centiseconds_per_second))


def physical_dp(words, binary_scale, centiseconds_per_second=1):
    """Decode quantity with physical unit scale Bn; optional cs -> s factor."""
    if type(binary_scale) is not int or centiseconds_per_second not in (1, 100):
        raise ValueError('Explicit binary scale and 1 or 100 cs conversion required')
    return float(dp_fraction(words) * Fraction(2) ** binary_scale * centiseconds_per_second)


def decode_vector(words, binary_scale, centiseconds_per_second=1):
    if len(words) != 6:
        raise ValueError('A DP vector requires six words')
    return [physical_dp(words[i:i+2], binary_scale, centiseconds_per_second)
            for i in (0, 2, 4)]


def dot(left, right):
    return sum(a*b for a, b in zip(left, right))


def norm(vector):
    return math.sqrt(dot(vector, vector))


def state_diagnostics(position_m, velocity_m_s, landing_site_m, mu_m3_s2, reference_radius_m):
    """SI sanity checks of declared input/observed state, not orbital propagation."""
    vectors = (position_m, velocity_m_s, landing_site_m)
    if any(len(v) != 3 or any(not math.isfinite(x) for x in v) for v in vectors):
        raise ValueError('Finite three-dimensional vectors required')
    radius, speed, site_radius = norm(position_m), norm(velocity_m_s), norm(landing_site_m)
    if min(radius, site_radius, mu_m3_s2, reference_radius_m) <= 0:
        raise ValueError('Positive radii and gravitational parameter required')
    radial_velocity = dot(position_m, velocity_m_s)/radius
    angle = math.acos(max(-1, min(1, dot(position_m, landing_site_m)/(radius*site_radius))))
    energy = speed**2/2-mu_m3_s2/radius
    return {'radius_m': radius, 'altitude_above_reference_m': radius-reference_radius_m,
            'speed_m_s': speed, 'radial_velocity_m_s': radial_velocity,
            'tangential_speed_m_s': math.sqrt(max(0, speed**2-radial_velocity**2)),
            'landing_site_radius_m': site_radius, 'site_central_angle_rad': angle,
            'surface_arc_distance_m': angle*reference_radius_m,
            'circular_speed_at_radius_m_s': math.sqrt(mu_m3_s2/radius),
            'specific_orbital_energy_J_kg': energy,
            'bound_two_body_energy': energy < 0,
            'point_gravity_m_s2': mu_m3_s2/radius**2,
            'scope': 'Independent two-body diagnostics, not original AGC navigation or propagated flight'}


def matrix_diagnostics(words):
    """REFSMMAT fractional elements are half physical direction cosines."""
    if len(words) != 18:
        raise ValueError('REFSMMAT requires all eighteen observed words')
    matrix = [[float(2*dp_fraction(words[i+j:i+j+2])) for j in (0, 2, 4)]
              for i in (0, 6, 12)]
    gram = [[dot(matrix[i], matrix[j]) for j in range(3)] for i in range(3)]
    error = [[gram[i][j]-(1 if i == j else 0) for j in range(3)] for i in range(3)]
    a, b, c = matrix
    determinant = (a[0]*(b[1]*c[2]-b[2]*c[1])
                   - a[1]*(b[0]*c[2]-b[2]*c[0])
                   + a[2]*(b[0]*c[1]-b[1]*c[0]))
    return {'raw_words_octal': [format(w, '05o') for w in words],
            'direction_cosines_reference_to_stable_member': matrix,
            'row_dot_products': gram, 'determinant': determinant,
            'max_orthogonality_error': max(abs(x) for row in error for x in row),
            'max_identity_difference': max(abs(matrix[i][j]-(i == j))
                                           for i in range(3) for j in range(3)),
            'classification': 'VERIFIED numerical properties of observed words',
            'physical_calibration': 'NOT RUN; numerical rotation validity does not prove mission alignment'}


def coefficient_diagnostics(table, root_words=None):
    """Inspect original TABLTTF fractions and optionally its observed root.

    This does not solve the polynomial or claim the Newton result is physical.
    Original ROOTPSRS requires |i*A(i)| < 1 (source pp. 823-825).
    """
    if len(table) < 8:
        raise ValueError('Four observed DP coefficients required')
    coefficients = [dp_fraction(table[i:i+2]) for i in (0, 2, 4, 6)]
    output = {'coefficient_raw_octal': [format(w, '05o') for w in table[:8]],
              'fractional_coefficients_A0_to_A3': list(map(float, coefficients)),
              'degenerate_all_zero': not any(coefficients),
              'derivative_coefficient_abs_lt_one': all(abs(i*c) < 1
                                                      for i, c in enumerate(coefficients)),
              'source_limits': 'No guarantee of polynomial-evaluation overflow absence from this inequality alone'}
    if root_words is not None:
        root = dp_fraction(root_words)
        residual = sum(c * root**i for i, c in enumerate(coefficients))
        derivative = sum(i*c*root**(i-1) for i, c in enumerate(coefficients) if i)
        terms = [abs(c*root**i) for i, c in enumerate(coefficients)]
        output.update(root_fraction=float(root), signed_time_to_go_seconds=float(root*Fraction(2**17, 100)),
                      residual_fraction=float(residual), derivative_fraction=float(derivative),
                      relative_residual=float(abs(residual)/sum(terms)) if sum(terms) else None,
                      diagnostic_newton_correction_fraction=float(residual/derivative) if derivative else None)
    return output


def expected_coefficient_fractions(rdg_z, rgu_z, vgu_z, vdg2ttf, adg2ttf, jdg2ttf):
    """Independent check of the exact operations at TTF/8CL.

    Arguments are observed fractional operands, not physical SI values. Returns
    ideal exact arithmetic for comparison with rounded AGC execution; callers
    must disclose quantization. Never write these results into AGC memory.
    """
    return [Fraction(3, 8)*(rdg_z-rgu_z),
            Fraction(3, 4)*vgu_z+vdg2ttf, adg2ttf, jdg2ttf]


def read_trace(path):
    path = Path(path)
    compressed = path.read_bytes()
    raw = gzip.decompress(compressed) if path.suffix == '.gz' else compressed
    return raw, [json.loads(line) for line in raw.splitlines()]


def phase9_report(trace):
    raw, rows = read_trace(trace)
    alignment = next(row for row in rows if row['ev'] == 'alignment_result')
    state = alignment['state']
    return {'scope': 'Independent numerical inspection of retained Phase 9 AGC-computed REFSMMAT',
            'input_trace': str(Path(trace)), 'raw_trace_sha256': hashlib.sha256(raw).hexdigest(),
            'observed_cycle': alignment['cycle'], 'agc_set_refsmflg': state['refsmflg'],
            'matrix': matrix_diagnostics(state['refsmmat'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase9-trace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite prior diagnostics')
    report = phase9_report(args.phase9_trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
