"""Native adapter unit rejection checks, separate from authentic AGC execution."""
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend import native_session as native


class NativeContractTests(unittest.TestCase):
    def test_all_source_mapped_signed_rhc_switch_words(self):
        expected = {(-1, -1): 12277, (-1, 0): 12279, (-1, 1): 12278,
                    (0, -1): 12285, (0, 0): 28671, (0, 1): 12286,
                    (1, -1): 12281, (1, 0): 12283, (1, 1): 12282}
        for signs, word in expected.items():
            self.assertEqual(native.rhc_word(*signs), word)

    def test_rhc_rejects_bool_float_string_and_out_of_range_values(self):
        for invalid in [True, False, 1.0, '1', None, 2, -2]:
            for signs in [(invalid, 0), (0, invalid)]:
                with self.assertRaises(ValueError):
                    native.rhc_word(*signs)

    def test_slow_sensor_mode_is_limited_by_actual_gimbal_rate(self):
        for code in [1, 3]:
            for rate in [4.00001, -4.00001, 9.8]:
                with self.assertRaisesRegex(ValueError, 'actual gimbal rate'):
                    native.validate_sensor_mode(1, code, {'gimbal_rates_deg_s': [0, rate, 0]})
            for rate in [-4, 0, 4]:
                native.validate_sensor_mode(1, code, {'gimbal_rates_deg_s': [0, rate, 0]})

    def test_conservative_fast_sensor_choice_is_permitted(self):
        for code in [17, 19]:
            for rate in [-4.1, -3.9, 0, 3.9, 4.1]:
                native.validate_sensor_mode(2, code, {'gimbal_rates_deg_s': [0, 0, rate]})

    def session(self, directory):
        return native.NativeSession({}, output=Path(directory) / 'new-session')

    def test_unstarted_session_rejects_commands_and_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(directory)
            with self.assertRaisesRegex(ValueError, 'not ready'):
                session.command(yaw=1)
            with self.assertRaisesRegex(ValueError, 'cannot advance'):
                session.advance_to(1)
            with self.assertRaisesRegex(ValueError, 'not started'):
                session.stop()
            self.assertFalse(session.output.exists())

    def test_wrong_thread_rejected_before_native_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(directory)
            errors = []
            def invoke():
                for call in [session.start, lambda: session.command(yaw=1),
                             lambda: session.advance_to(10), session.stop]:
                    try:
                        call()
                    except BaseException as error:
                        errors.append(error)
            with patch.object(native.INTEGRATION, 'Engine') as engine:
                worker = threading.Thread(target=invoke)
                worker.start()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                engine.assert_not_called()
            self.assertEqual(len(errors), 4)
            self.assertTrue(all(isinstance(error, RuntimeError) for error in errors))

    def test_execution_rejects_invalid_cycle_values(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(directory)
            session.status, session.ready = 'running', True
            session.tick = native.READY_CYCLE
            for value in [True, 1.0, None, -1, 0]:
                with self.assertRaises(ValueError):
                    session.advance(value)
            for value in [True, 1.0, None, native.READY_CYCLE-1, native.END_CYCLE+1]:
                with self.assertRaises(ValueError):
                    session.advance_to(value)

    def test_command_lease_bounds_and_zero_duration_neutral(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(directory)
            session.status, session.ready = 'running', True
            session.tick = native.READY_CYCLE
            with patch.object(session, '_check_ready'), patch.object(session, '_set_control') as set_control:
                for value in [True, 1.0, None, -1, 0, native.MAX_PULSE_CYCLES+1]:
                    with self.assertRaises(ValueError):
                        session.command(yaw=1, duration_cycles=value)
                set_control.assert_not_called()
                result = session.command(yaw=0, pitch=0, duration_cycles=0)
                self.assertEqual(result['duration_cycles'], 0)
                set_control.assert_called_once_with(0, 0, None, 'browser pilot')

    def test_returned_frame_cannot_mutate_authoritative_state(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self.session(directory)
            frame = session.frame()
            frame['counts'][0]['applied'] = 99
            frame['control']['yaw'] = 1
            self.assertEqual(session.counts[0]['applied'], 0)
            self.assertEqual(session.control['yaw'], 0)

    def assets(self, directory):
        """Modern unit files only; these never execute or claim to be AGC code."""
        directory = Path(directory)
        source = directory / 'unit-source'
        source.mkdir()
        unit = source / 'unit.c'
        unit.write_bytes(b'unit integrity fixture, never executed\n')
        manifest = directory / 'unit-runtime-manifest.json'
        manifest.write_text('{}\n')
        return {'source': str(source), 'tcl': '/unit/not-executed',
                'provenance': {'inputs_sha256': {}, 'source_sha256': {'unit.c': native.digest(unit)},
                    'runtime_manifest': str(manifest), 'runtime_manifest_sha256': native.digest(manifest)}}

    def test_tampered_prepared_source_rejected_before_engine_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = self.assets(directory)
            (Path(assets['source']) / 'unit.c').write_bytes(b'deliberately altered unit source\n')
            session = native.NativeSession(assets, output=Path(directory) / 'session')
            with patch.object(native, 'validate_contract', return_value={}), patch.object(native.INTEGRATION, 'Engine') as engine:
                with self.assertRaisesRegex(ValueError, 'Prepared pinned source changed'):
                    session.start()
                engine.assert_not_called()
            self.assertTrue(session.closed)
            self.assertFalse(native._ACTIVE.locked())

    def test_tampered_runtime_manifest_rejected_before_engine_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = self.assets(directory)
            Path(assets['provenance']['runtime_manifest']).write_text('{"altered":true}\n')
            session = native.NativeSession(assets, output=Path(directory) / 'session')
            with patch.object(native, 'validate_contract', return_value={}), patch.object(native.INTEGRATION, 'Engine') as engine:
                with self.assertRaisesRegex(ValueError, 'Prepared runtime manifest changed'):
                    session.start()
                engine.assert_not_called()

    def test_runtime_tree_validation_failure_prevents_engine_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = self.assets(directory)
            def reject_unit_runtime(path):
                raise RuntimeError('unit runtime tree mismatch')
            runtime = SimpleNamespace(validate_runtime=reject_unit_runtime)
            session = native.NativeSession(assets, output=Path(directory) / 'session')
            with patch.object(native, 'validate_contract', return_value={}), patch.object(native, '_load', return_value=runtime), patch.object(native.INTEGRATION, 'Engine') as engine:
                with self.assertRaisesRegex(RuntimeError, 'runtime tree mismatch'):
                    session.start()
                engine.assert_not_called()


if __name__ == '__main__':
    unittest.main()
