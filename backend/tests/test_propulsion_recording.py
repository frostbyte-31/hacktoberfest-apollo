"""Recording provenance/contract tests, distinct from native AGC execution."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from backend import propulsion_recording as recording


class PropulsionRecordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = recording.build_recording()
        cls.cases = {case['id']: case for case in cls.data['cases']}

    def test_original_evidence_seal_and_true_raw_repeat_verified(self):
        proof = self.data['provenance']
        seal = recording.read_json(recording.ROOT/recording.PACKAGE/'checksums.json')
        self.assertEqual(proof['filesVerified'], seal['files'])
        self.assertEqual(proof['sealSha256'], recording.digest(recording.ROOT/recording.PACKAGE/'checksums.json'))
        self.assertTrue(proof['connectedRepeatByteIdentical'])
        self.assertEqual(proof['rawTraces']['connected'], proof['rawTraces']['repeat'])

    def test_modes_and_unavailable_capabilities_are_explicit(self):
        self.assertEqual(self.data['mode'], 'RECORDED_AUTHENTIC_AGC_EXPERIMENT')
        self.assertEqual(tuple(self.cases), recording.CASES)
        self.assertFalse(self.data['capabilities']['liveExecution'])
        self.assertFalse(self.data['capabilities']['arbitraryCommands'])
        self.assertFalse(self.data['capabilities']['completeDescent'])
        self.assertFalse(self.data['capabilities']['landing'])
        self.assertTrue(any('SYNTHETIC' in text for text in self.data['limitations']))
        self.assertTrue(any('not live' in text for text in self.data['limitations']))

    def test_sample_hold_has_real_endpoints_and_bounded_gaps(self):
        for case in self.cases.values():
            frames = case['frames']
            self.assertGreater(len(frames), 10)
            self.assertEqual(frames[0]['cycle'], case['source']['t0Cycle'])
            self.assertEqual(frames[0]['t'], 0)
            self.assertEqual(frames[-1]['t'], case['durationSeconds'])
            for a, b in zip(frames, frames[1:]):
                self.assertLess(a['cycle'], b['cycle'])
                self.assertLessEqual(b['cycle']-a['cycle'], recording.MAX_SAMPLE_CYCLES)
            for frame in frames:
                self.assertEqual(frame['cycle'], frame['source']['cycle'])
                self.assertEqual(frame['t'], float((frame['cycle']-frames[0]['cycle'])*recording.MCT))
                self.assertEqual(frame['source']['traceSha256'], case['traceSha256'])
                self.assertIsNone(frame['physics']['engine']['throttle'])
                self.assertIsNone(frame['physics']['outcome'])

    def test_every_selected_frame_and_dsky_matches_exact_raw_observation(self):
        # Independently stream the genuine source. No exporter helper constructs
        # the expected physical or display values used by these comparisons.
        for case in self.cases.values():
            selected = {frame['source']['rawLine']: frame for frame in case['frames']}
            mapping = recording.read_json(recording.ROOT/recording.PACKAGE/'runs/verified'/case['id']/'observer-map.json')
            index = mapping['snapshot_addresses'].index(mapping['addresses']['MODREG'])
            latest_display = latest_program = display_source = program_source = None
            found = 0
            with gzip.open(recording.ROOT/case['source']['tracePath'], 'rt') as stream:
                for line_no, text in enumerate(stream, 1):
                    row = json.loads(text)
                    source = {'rawLine': line_no, 'cycle': row['cycle'], 'traceSha256': case['traceSha256']}
                    if row['ev'] == 'output' and row['channel'] == 0o10:
                        latest_display, display_source = row['display'], source
                    if row['ev'] == 'checkpoint':
                        latest_program, program_source = row['snapshot_words'][index], source
                    if line_no not in selected:
                        continue
                    found += 1
                    frame = selected[line_no]
                    self.assertIn(row['ev'], ('plant_initialization', 'plant'))
                    raw = row['telemetry']
                    state, engine = frame['physics']['spacecraft'], frame['physics']['engine']
                    for exposed, original in (('positionM','position_ref_m'), ('velocityMps','velocity_ref_m_s'),
                                               ('accelerationMps2','total_acceleration_ref_m_s2'),
                                               ('quaternionBodyToRef','quaternion_body_to_ref'),
                                               ('angularVelocityRadps','angular_velocity_body_rad_s'),
                                               ('massKg','mass_kg'), ('fuelKg','fuel_kg')):
                        self.assertEqual(state[exposed], raw[original])
                    self.assertEqual(engine['enabled'], raw['engine_enabled'])
                    self.assertEqual(engine['thrustN'], raw['delivered_thrust_n'])
                    self.assertEqual(engine['thrustVectorN'], raw['thrust_vector_ref_n'])
                    self.assertEqual(engine['massFlowKgps'], raw['mass_flow_kg_s'])
                    self.assertEqual(frame['physics']['simTimeSeconds'], raw['time_s'])
                    self.assertEqual(frame['agc']['dsky'], latest_display)
                    self.assertEqual(frame['agc']['dskySource'], display_source)
                    self.assertEqual(frame['agc']['program'], latest_program)
                    self.assertEqual(frame['agc']['programSource'], program_source)
                    self.assertEqual(frame['agc']['sourceCycle'], display_source['cycle'])
                    self.assertLessEqual(display_source['cycle'], frame['cycle'])
            self.assertEqual(found, len(selected))

    def test_display_projection_sum_does_not_follow_host_python_algorithm_changes(self):
        # Python3.12+ builtin sum(float) retains these small terms; Python3.11
        # rounded them in insertion order. Projection export must retain its
        # existing operation order without changing raw recorded measurements.
        for values, expected in [([1e16, 1., 1.], 1e16),
                                  ([1e16, 1., -1e16], 0.)]:
            with self.subTest(values=values):
                self.assertEqual(recording._ordered_projection_sum(values), expected)
                self.assertNotEqual(math.fsum(values), expected)

    def test_display_projection_is_independent_math_not_dynamics(self):
        for case in self.cases.values():
            origin = case['source']['initialProjectionAngleRad']
            radius = case['source']['lunarRadiusM']
            for frame in case['frames']:
                state = frame['physics']['spacecraft']
                r, v = state['positionM'], state['velocityMps']
                magnitude = math.sqrt(sum(x*x for x in r))
                vertical = sum(a*b for a, b in zip(r, v))/magnitude
                self.assertAlmostEqual(state['altitudeM'], magnitude-radius, places=8)
                self.assertAlmostEqual(state['verticalSpeedMps'], vertical, places=10)
                self.assertAlmostEqual(state['horizontalSpeedMps'], math.sqrt(max(0,sum(x*x for x in v)-vertical**2)), places=10)
                signed = (-r[2]*v[0]+r[0]*v[2])/math.hypot(r[0], r[2])
                self.assertAlmostEqual(state['horizontalVelocityMps'], signed, places=10)
                self.assertAlmostEqual(state['downrangeM'], radius*(math.atan2(r[2],r[0])-origin), places=8)
                # Phase12's fixed quaternion has a tiny nonzero rotation. This
                # independent formula compares its XZ-projected body +X angle.
                w,x,y,z = state['quaternionBodyToRef']
                bx, bz = 1-2*(y*y+z*z), 2*(x*z-w*y)
                expected = math.degrees(math.atan2(r[2],r[0])-math.atan2(bz,bx))
                self.assertAlmostEqual(state['pitchDeg'], expected, places=5)

    def test_event_sources_and_original_routine_counts_match_raw(self):
        for case in self.cases.values():
            wanted = {event['source']['rawLine']: [] for event in case['events']}
            for event in case['events']:
                wanted[event['source']['rawLine']].append(event)
            counts = Counter()
            with gzip.open(recording.ROOT/case['source']['tracePath'], 'rt') as stream:
                for line_no, text in enumerate(stream, 1):
                    row = json.loads(text)
                    if row['ev'] == 'checkpoint':
                        counts[row['routine']] += 1
                    for event in wanted.get(line_no, []):
                        self.assertEqual(event['cycle'], row['cycle'])
                        self.assertEqual(event['source']['traceSha256'], case['traceSha256'])
                        self.assertEqual(event['t'], float((row['cycle']-case['source']['t0Cycle'])*recording.MCT))
                        self.assertIn(row['ev'], ('stage','checkpoint','output','plant','plant_initialization'))
            self.assertEqual(case['result']['originalThrottleCalls'], counts['THROTTLE'])
            self.assertEqual(case['result']['originalLunarNavigationPasses'], counts['MUNRVG'])
            self.assertEqual(len({event['id'] for event in case['events']}), len(case['events']))

    def test_causal_controls_are_preserved_without_claiming_a_landing(self):
        connected, disconnected, sink = (self.cases[n] for n in ('connected','no-feedback','sink'))
        self.assertGreater(connected['result']['originalThrottleCalls'], 0)
        self.assertEqual(disconnected['result']['originalThrottleCalls'], 0)
        self.assertEqual(sink['result']['originalThrottleCalls'], 0)
        self.assertGreater(connected['result']['sensor']['consumed_counts'][0], 0)
        self.assertEqual(disconnected['result']['sensor']['delivered_counts'], [0,0,0])
        self.assertFalse(any(frame['physics']['engine']['enabled'] for frame in sink['frames']))
        self.assertTrue(any(frame['physics']['engine']['enabled'] for frame in disconnected['frames']))
        for case in self.cases.values():
            self.assertEqual(case['result']['landing'], 'NOT RUN')
            self.assertEqual(case['result']['navigation']['coordinateFrame'], 'IMU stable member')
            self.assertTrue(case['result']['originalChecksPass'])

    def test_export_is_reproducible_from_verified_source(self):
        existing = (recording.ROOT/'frontend/dist/data/propulsion-lab.json').read_text()
        comparison = recording.verify_export(existing, self.data)
        self.assertTrue(comparison['recordedObservationsExact'])
        self.assertEqual(comparison['derivedProjectionUlpLimit'], 8)
        exact = recording.verify_export(recording.serialize(self.data), self.data)
        self.assertTrue(exact['byteIdentical'])
        self.assertEqual(exact['derivedProjectionDifferences'], 0)

    def test_export_allows_only_bounded_derived_projection_rounding(self):
        expected = deepcopy(self.data)
        # A small contract fixture value keeps the ULP boundary unambiguous.
        expected['cases'][0]['frames'][0]['physics']['spacecraft']['pitchDeg'] = 1.5
        actual = deepcopy(expected)
        field = actual['cases'][0]['frames'][0]['physics']['spacecraft']
        for _ in range(8):
            field['pitchDeg'] = math.nextafter(field['pitchDeg'], math.inf)
        comparison = recording.verify_export(recording.serialize(actual), expected)
        self.assertFalse(comparison['byteIdentical'])
        self.assertTrue(comparison['recordedObservationsExact'])
        self.assertEqual(comparison['derivedProjectionDifferences'], 1)
        field['pitchDeg'] = math.nextafter(field['pitchDeg'], math.inf)
        with self.assertRaisesRegex(ValueError, 'pitchDeg'):
            recording.verify_export(recording.serialize(actual), expected)

    def test_export_rejects_even_one_ulp_change_in_raw_observations(self):
        for field in ('positionM', 'velocityMps', 'quaternionBodyToRef'):
            actual = deepcopy(self.data)
            vector = actual['cases'][0]['frames'][0]['physics']['spacecraft'][field]
            vector[0] = math.nextafter(vector[0], math.inf)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                recording.verify_export(recording.serialize(actual), self.data)

    def test_export_rejects_source_hash_cycle_order_and_schema_tampering(self):
        for mutate in (
            lambda value: value['cases'][0]['frames'][0]['source'].update(traceSha256='0'*64),
            lambda value: value['cases'][0]['frames'][0].update(cycle=0),
            lambda value: value['cases'][0]['frames'].reverse(),
            lambda value: value.update(extra='unsupported'),
            lambda value: value.update(schemaVersion=True),
        ):
            actual = deepcopy(self.data)
            mutate(actual)
            with self.assertRaises(ValueError):
                recording.verify_export(recording.serialize(actual), self.data)

    def test_export_rejects_duplicate_or_nonfinite_json_fields(self):
        for text in ('{"schemaVersion":1,"schemaVersion":1}', '{"value":NaN}',
                     '{"value":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                recording.verify_export(text, self.data)

    def test_changed_raw_bytes_fail_even_when_gzip_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic-integrity-unit-fixture.jsonl.gz'
            content = b'{"unit_fixture":true}\n'
            expected = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
            path.write_bytes(gzip.compress(content, mtime=0))
            self.assertEqual(recording.verify_trace(path, expected), expected)
            path.write_bytes(gzip.compress(content+b' ', mtime=0))
            with self.assertRaisesRegex(ValueError, 'raw trace differs'):
                recording.verify_trace(path, expected)

    def test_nonfinite_physical_projection_fails_closed(self):
        state = self.cases['connected']['frames'][0]['physics']['spacecraft']
        invalid = {'position_ref_m': deepcopy(state['positionM'])}
        invalid['position_ref_m'][0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            recording.project_physics(invalid, 1738090, 0)


if __name__ == '__main__':
    unittest.main()
