"""Real HTTP security and isolation for the separate CSM instrument owner."""
from copy import deepcopy
import threading
import unittest
from unittest.mock import patch

from backend.control_service import ControlError
from backend.earth_alignment_service import MODE, validate_control
from backend.final_server import FinalHandler, close_server, make_server
from backend.tests import test_earth_orbit_http as http_support
from backend.tests.test_http import FakeControls


class AlignmentSpy(http_support.FakeService):
    def __init__(self, available=True):
        super().__init__(available)
        self.state['mode'] = MODE

    def capabilities(self):
        value = super().capabilities()
        value.update(mode=MODE, supportedControls=['power_imu', 'optics_mode', 'optics_slew', 'mark'] if self.available else [])
        return value

    def instrument(self, sessionId, sequence, control, value):
        validate_control(control, value)
        if (type(sequence) is not int or sessionId != self.state['sessionId']
                or sequence != self.state['nextSequence']):
            raise ControlError(409, 'Wrong CSM session or sequence.')
        self.calls.append(('instrument', sessionId, sequence, control, deepcopy(value)))
        self.state.update(revision=self.state['revision']+1, nextSequence=sequence+1)
        result = self.snapshot()
        result['ack'] = {'sessionId': sessionId, 'sequence': sequence, 'control': control,
                         'value': deepcopy(value), 'queuedAtCycle': 100, 'afterCycle': 200}
        return result


class EarthAlignmentHttpTests(unittest.TestCase):
    request = http_support.EarthOrbitHttpTests.request

    def setUp(self):
        logger = patch.object(FinalHandler, 'log_message', return_value=None)
        logger.start()
        self.addCleanup(logger.stop)
        self.cmc = http_support.FakeService()
        self.alignment = AlignmentSpy()
        self.server = make_server(0, assets=None, earth_orbit=self.cmc, earth_alignment=self.alignment)
        self.server.controls.close()
        self.server.controls = FakeControls()
        self.server.live_enabled = True
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.worker.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        close_server(self.server)
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())
        self.assertTrue(self.alignment.closed)
        self.assertTrue(self.cmc.closed)

    def start(self):
        status, _, state = self.request('POST', '/api/earth-alignment/start', {})
        self.assertEqual(status, 200)
        return state

    def test_observations_never_start_or_mutate_a_computer(self):
        for name in ('capabilities', 'status'):
            status, headers, state = self.request('GET', '/api/earth-alignment/'+name)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(state['mode'], MODE)
            if name == 'capabilities':
                self.assertEqual(state['token'], self.server.control_token)
                self.assertIn('mark', state['supportedControls'])
            else:
                self.assertIsNone(state['computer'])
        self.assertEqual(self.alignment.calls, [])
        self.assertEqual(self.cmc.calls, [])
        self.assertEqual(self.server.controls.calls, [])

    def test_real_keys_and_controls_share_sequence_and_only_reach_alignment_owner(self):
        state = self.start()
        identity = state['sessionId']
        requests = [('/key', {'sessionId': identity, 'sequence': 0, 'key': 'VERB'}),
                    ('/instrument', {'sessionId': identity, 'sequence': 1, 'control': 'optics_mode', 'value': 'MANUAL'}),
                    ('/instrument', {'sessionId': identity, 'sequence': 2, 'control': 'optics_slew',
                        'value': {'shaft': 1, 'trunnion': -1, 'rate': 'LOW', 'seconds': .25}}),
                    ('/instrument', {'sessionId': identity, 'sequence': 3, 'control': 'mark', 'value': 'MARK'}),
                    ('/key', {'sessionId': identity, 'sequence': 4, 'key': 'PRO'})]
        for suffix, body in requests:
            status, _, state = self.request('POST', '/api/earth-alignment'+suffix, body)
            self.assertEqual(status, 200)
            self.assertEqual(state['ack']['sequence'], body['sequence'])
            self.assertEqual(state['nextSequence'], body['sequence']+1)
            self.assertEqual(state['revision'], body['sequence']+1)
        self.assertEqual(self.request('POST', '/api/earth-alignment/instrument',
            {'sessionId': identity, 'sequence': 3, 'control': 'mark', 'value': 'MARK'})[0], 409)
        self.assertEqual(self.request('POST', '/api/earth-alignment/stop', {'sessionId': identity})[0], 200)
        self.assertEqual(self.cmc.calls, [])
        self.assertEqual(self.server.controls.calls, [])

    def test_origin_host_fetch_site_and_token_checks_precede_controls(self):
        bad = [({'Host': 'elsewhere.invalid'}, 421), ({'Origin': None}, 403),
               ({'Origin': 'null'}, 403), ({'Origin': 'https://elsewhere.invalid'}, 403),
               ({'Sec-Fetch-Site': 'cross-site'}, 403), ({'X-Apollo-Token': None}, 403),
               ({'X-Apollo-Token': 'invalid'}, 403)]
        for headers, expected in bad:
            self.assertEqual(self.request('POST', '/api/earth-alignment/start', {}, headers)[0], expected)
        for headers, expected in [({'Host': 'elsewhere.invalid'}, 421),
                                  ({'Sec-Fetch-Site': 'cross-site'}, 403),
                                  ({'Origin': 'https://elsewhere.invalid'}, 403)]:
            self.assertEqual(self.request('GET', '/api/earth-alignment/status', headers=headers)[0], expected)
        self.assertEqual(self.alignment.calls, [])

    def test_exact_control_schema_and_bounded_values_are_required(self):
        state = self.start()
        good = {'sessionId': state['sessionId'], 'sequence': 0, 'control': 'mark', 'value': 'MARK'}
        for body in [dict(good, rawChannel=0o16), {name: item for name, item in good.items() if name != 'value'},
                     dict(good, action='mark'), dict(good, control='mark', value='LAND'),
                     dict(good, control='power_imu', value=1),
                     dict(good, control='optics_slew', value={'shaft': 1, 'trunnion': 0, 'rate': 'LOW', 'seconds': 10})]:
            self.assertEqual(self.request('POST', '/api/earth-alignment/instrument', body)[0], 400)
        for path, body in [('/start', {'checkpoint': 'P52-complete'}), ('/key', {'key': 'PRO'}), ('/stop', {})]:
            self.assertEqual(self.request('POST', '/api/earth-alignment'+path, body)[0], 400)
        self.assertEqual(self.alignment.calls, [('start',)])

    def test_malformed_duplicate_nonfinite_and_oversized_requests_never_delegate(self):
        for body in [b'{"sequence":0,"sequence":1}', b'{"value":NaN}', b'{"value":Infinity}',
                     b'{"value":"\xff"}', b'null', b'[]', b'{']:
            self.assertEqual(self.request('POST', '/api/earth-alignment/instrument', body)[0], 400)
        for headers, status in [({'Content-Type': 'text/plain'}, 415), ({'Content-Length': '8193'}, 413),
                                ({'Content-Length': None}, 411), ({'Transfer-Encoding': 'chunked'}, 400)]:
            self.assertEqual(self.request('POST', '/api/earth-alignment/start', {}, headers)[0], status)
        self.assertEqual(self.alignment.calls, [])

    def test_unknown_mutations_and_head_cannot_start_alignment(self):
        for method, path, expected in [('GET', '/start', 404), ('POST', '/status', 404),
                                       ('POST', '/advance', 404), ('POST', '/load-memory', 404),
                                       ('HEAD', '/status', 405)]:
            self.assertEqual(self.request(method, '/api/earth-alignment'+path,
                                          {} if method == 'POST' else None)[0], expected)
        self.assertEqual(self.alignment.calls, [])

    def test_unavailable_alignment_leaves_static_and_cold_start_routes_operational(self):
        self.alignment.available = False
        status, _, capability = self.request('GET', '/api/earth-alignment/capabilities')
        self.assertEqual(status, 200)
        self.assertFalse(capability['available'])
        self.assertIsNone(capability['token'])
        self.assertEqual(self.request('POST', '/api/earth-alignment/start', {})[0], 503)
        self.assertEqual(self.request('GET', '/campaign.html')[0], 200)
        self.assertEqual(self.request('GET', '/api/earth-orbit/capabilities')[0], 200)
        self.assertEqual(self.request('POST', '/api/earth-orbit/start', {})[0], 200)
        self.assertEqual(self.request('GET', '/api/v1/capabilities')[0], 200)
        self.assertEqual(self.cmc.calls, [('start',)])


if __name__ == '__main__':
    unittest.main()
