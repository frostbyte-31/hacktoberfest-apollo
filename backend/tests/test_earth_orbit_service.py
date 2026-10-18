"""CMC gateway invariants plus a fresh original-Comanche task, not flight proof."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import tempfile
import unittest

from backend.control_service import ControlError
from backend.earth_orbit_service import EarthOrbitService, MODE


def digits(**changes):
    return dict(PROG='00', VERB='  ', NOUN='  ', R1='     ', R2='     ', R3='     ', **{}) | changes


class FakeEngine:
    """Gateway transport double; the separate native test supplies authentic proof."""
    def __init__(self):
        self.cycle = 1000
        self.display = digits()
        self.keys = []
        self.closed = False

    def frame(self):
        return {'software': 'Comanche055', 'cycle': self.cycle, 'cpuSeconds': self.cycle*12/1024000,
                'dsky': deepcopy(self.display), 'dskySource': {'channel': 8, 'cycle': self.cycle},
                'provenance': {'ropeSha256': 'a'*64, 'engineSha256': 'b'*64,
                               'sourceUrl': 'https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html'}}

    def boot(self):
        return self.frame()

    def key(self, key):
        before = self.cycle
        self.keys.append(key)
        self.cycle += 100
        return {'computer': self.frame(), 'ackpacket': {'key': key, 'channel': 13, 'code': 17,
                'queuedAtCycle': before, 'consumedAtCycle': before+1, 'afterCycle': self.cycle}}

    def advance(self, seconds):
        self.cycle += 100
        return self.frame()

    def close(self):
        self.closed = True


class EarthOrbitServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='apollo-cmc-service-')
        self.addCleanup(self.tmp.cleanup)
        self.engines = []
        def factory():
            item = FakeEngine()
            self.engines.append(item)
            return item
        self.service = EarthOrbitService(factory=factory,
            discovery=lambda: {'available': True, 'unavailableReason': None},
            output_root=self.tmp.name, pace=False)
        self.addCleanup(self.service.close)

    def key(self, state, name):
        return self.service.key(state['sessionId'], state['nextSequence'], name)

    def test_discovery_and_status_do_not_start_a_computer_or_fabricate_a_display(self):
        self.assertTrue(self.service.capabilities()['available'])
        state = self.service.snapshot()
        self.assertEqual(state['mode'], MODE)
        self.assertEqual(state['status'], 'idle')
        self.assertIsNone(state['computer'])
        self.assertIsNone(self.service.thread)
        self.assertEqual(self.engines, [])
        self.assertFalse(state['task']['complete'])
        self.assertFalse(state['task']['alignmentCompleted'])
        self.assertFalse(state['task']['flightExecuted'])

    def test_input_requires_exact_session_and_sequence_and_known_hardware_key(self):
        state = self.service.start()
        for sequence, key in [(True, 'VERB'), (-1, 'VERB'), (0, 'THRUST'), (0, '__proto__')]:
            with self.assertRaises(ControlError):
                self.service.key(state['sessionId'], sequence, key)
        for identity, sequence in [('wrong-run', 0), (state['sessionId'], 1)]:
            with self.assertRaises(ControlError) as error:
                self.service.key(identity, sequence, 'VERB')
            self.assertEqual(error.exception.status, 409)
        state = self.key(state, 'VERB')
        self.assertEqual(state['nextSequence'], 1)
        self.assertEqual(state['ack']['sequence'], 0)
        self.assertEqual(state['computer']['lastKey']['key'], 'VERB')
        with self.assertRaises(ControlError):
            self.service.key(state['sessionId'], 0, 'VERB')
        self.assertEqual(self.engines[0].keys, ['VERB'])

    def test_two_racing_requests_cannot_apply_the_same_key_sequence_twice(self):
        state = self.service.start()
        def request():
            try:
                return self.service.key(state['sessionId'], 0, 'VERB')['nextSequence']
            except ControlError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: request(), range(2)))
        self.assertCountEqual(results, [1, 409])
        self.assertEqual(self.engines[0].keys, ['VERB'])

    def test_correct_key_script_without_original_output_does_not_complete_a_step(self):
        state = self.service.start()
        for key in ['VERB', '3', '5', 'ENTR', 'RSET', 'VERB', '3', '7', 'ENTR', '0', '0', 'ENTR']:
            state = self.key(state, key)
        self.assertFalse(any(item['complete'] for item in state['task']['steps']))
        self.assertFalse(state['task']['complete'])
        self.assertEqual(state['computer']['dsky'], digits())

    def test_an_unrequested_startup_sweep_does_not_count_as_player_display_test(self):
        self.service.start()
        self.engines[0].display = digits(PROG='88', VERB='88', NOUN='88', R1='88888', R2='88888', R3='88888')
        state = self.service._call('advance', .1)
        self.assertFalse(state['task']['steps'][0]['complete'])

    def test_observed_output_and_operator_request_together_establish_a_checkpoint(self):
        state = self.service.start()
        for key in ['VERB', '3', '5', 'ENTR']:
            state = self.key(state, key)
        self.engines[0].display = digits(PROG='88', VERB='88', NOUN='88', R1='88888', R2='88888', R3='88888')
        state = self.service._call('advance', .1)
        self.assertTrue(state['task']['steps'][0]['complete'])
        mark = state['task']['checkpoints'][0]
        self.assertEqual(mark['dskySource']['channel'], 8)
        self.assertEqual(mark['dsky'], self.engines[0].display)
        self.assertFalse(state['task']['complete'])

    def test_restart_uses_a_new_process_and_invalidates_old_browser_requests(self):
        old = self.service.start()
        fresh = self.service.start()
        self.assertNotEqual(old['sessionId'], fresh['sessionId'])
        self.assertTrue(self.engines[0].closed)
        self.assertEqual(fresh['nextSequence'], 0)
        with self.assertRaises(ControlError):
            self.service.key(old['sessionId'], 0, 'VERB')
        self.service.stop(fresh['sessionId'])
        self.assertTrue(self.engines[1].closed)
        with self.assertRaises(ControlError):
            self.service.key(fresh['sessionId'], 0, 'VERB')

    def test_execution_failure_keeps_last_real_observation_stale_and_stops_keys(self):
        self.service.start()
        self.engines[0].display = digits(PROG='not-real')
        with self.assertRaises(ControlError):
            self.service._call('advance', .1)
        state = self.service.snapshot()
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['computer']['dsky'], digits())
        self.assertTrue(self.engines[0].closed)
        self.assertIn('invalid DSKY', state['error'])

    def test_recorded_only_disables_this_native_service_without_starting_it(self):
        service = EarthOrbitService(enabled=False)
        self.addCleanup(service.close)
        self.assertFalse(service.capabilities()['available'])
        self.assertIsNone(service.snapshot()['computer'])
        with self.assertRaises(ControlError) as error:
            service.start()
        self.assertEqual(error.exception.status, 503)

    def test_clock_needs_entered_command_and_changing_numeric_observations(self):
        state = self.service.start()
        self.service.marks = [{'id': 'display-test', 'cycle': 0}, {'id': 'p00', 'cycle': 0}]
        for key in ['VERB','1','6','NOUN','3','6']:
            state = self.key(state, key)
        self.engines[0].display = digits(VERB='16', NOUN='36', R1='00000', R2='00000', R3='00100')
        state = self.service._call('advance', .1)
        self.engines[0].display['R3'] = '00200'
        state = self.service._call('advance', .1)
        self.assertFalse(state['task']['steps'][2]['complete'], 'Entry echo is not an executed monitor command')
        state = self.key(state, 'ENTR')
        state = self.service._call('advance', .1)
        self.assertFalse(state['task']['steps'][2]['complete'], 'A held numeric display does not establish a running clock')
        self.engines[0].display['R3'] = '00300'
        state = self.service._call('advance', .1)
        self.assertTrue(state['task']['steps'][2]['complete'])

    def test_fault_logging_failure_still_closes_worker_and_resolves_request(self):
        from unittest.mock import patch
        self.service.start()
        self.engines[0].display = digits(PROG='invalid')
        with patch.object(self.service, '_event', side_effect=OSError('audit storage unavailable')):
            with self.assertRaises(ControlError):
                self.service._call('advance', .1)
        self.assertTrue(self.engines[0].closed)
        self.assertIsNone(self.service.engine)
        self.assertTrue(self.service.thread.is_alive())
        self.assertEqual(self.service.snapshot()['status'], 'error')

    def test_server_shutdown_attempts_every_owned_service_even_after_one_failure(self):
        from types import SimpleNamespace
        from backend.final_server import close_server
        calls = []
        def broken():
            calls.append('cmc')
            raise RuntimeError('worker failure')
        server = SimpleNamespace(earth_orbit=SimpleNamespace(close=broken),
            missions=SimpleNamespace(close=lambda: calls.append('missions')),
            controls=SimpleNamespace(close=lambda: calls.append('controls')),
            server_close=lambda: calls.append('socket'))
        with self.assertRaises(RuntimeError):
            close_server(server)
        self.assertEqual(calls, ['cmc', 'missions', 'controls', 'socket'])


class OriginalCmcTaskTests(unittest.TestCase):
    def test_fresh_original_comanche_performs_entire_playable_diagnostic(self):
        from backend.cmc_native import prepare_cmc_assets, CmcProcess
        assets = prepare_cmc_assets()
        with tempfile.TemporaryDirectory(prefix='apollo-real-cmc-task-') as folder:
            service = EarthOrbitService(factory=lambda: CmcProcess(assets),
                discovery=lambda: {'available': True}, output_root=folder, pace=False)
            try:
                state = service.start()
                stages = [
                    ('display-test', ['VERB','3','5','ENTR']),
                    ('p00', ['RSET','VERB','3','7','ENTR','0','0','ENTR']),
                    ('clock', ['VERB','1','6','NOUN','3','6','ENTR']),
                    (None, ['VERB','3','7','ENTR','5','2','ENTR']),
                    ('p52-gate', ['VERB','0','5','NOUN','0','9','ENTR']),
                    ('recover', ['RSET','VERB','3','7','ENTR','0','0','ENTR']),
                ]
                for expected, keys in stages:
                    for key in keys:
                        before = state['computer']['cycle']
                        state = service.key(state['sessionId'], state['nextSequence'], key)
                        self.assertGreaterEqual(state['ack']['queuedAtCycle'], before)
                        self.assertGreater(state['ack']['consumedAtCycle'], state['ack']['queuedAtCycle'])
                        self.assertEqual(state['ack']['accepted'], 4)  # Actual four-byte ringbuffer packet.
                    state = service._call('advance', 2)
                    if expected == 'clock':
                        for _ in range(5):
                            if state['task']['steps'][2]['complete']:
                                break
                            state = service._call('advance', .25)
                    if expected:
                        self.assertTrue(next(item for item in state['task']['steps'] if item['id']==expected)['complete'], state)
                    if expected == 'display-test':
                        self.assertEqual(state['computer']['dsky']['R1'], '88888')
                        state = service._call('advance', 5)
                    if expected == 'p52-gate':
                        self.assertIn('00210', [state['computer']['dsky'][key] for key in ['R1','R2','R3']])
                self.assertTrue(state['task']['complete'])
                self.assertFalse(state['task']['flightExecuted'])
                self.assertFalse(state['task']['alignmentCompleted'])
                self.assertEqual(state['computer']['dsky']['PROG'], '00')
                self.assertEqual(len(state['task']['checkpoints']), 5)
                self.assertIsNone(state['computer']['flightState'])
                self.assertFalse(state['computer']['historicalCheckpointLoaded'])
            finally:
                service.close()


if __name__ == '__main__':
    unittest.main()
