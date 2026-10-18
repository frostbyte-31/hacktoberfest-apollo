"""Real loopback HTTP boundaries for the independently owned original CMC console.

The injected service is a transport spy, not an AGC or spacecraft model. Actual
native execution and source-driven task transitions are tested separately.
"""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.control_service import ControlError
from backend.final_server import FinalHandler, close_server, make_server
from backend.tests.test_http import FakeControls

MODE = 'LIVE ORIGINAL CMC EXECUTION'


class FakeService:
    """Record exactly what the HTTP boundary delegates, without native startup."""
    def __init__(self, available=True):
        self.available = available
        self.calls = []
        self.observations = []
        self.closed = False
        self.state = {'schemaVersion': 1, 'mode': MODE, 'available': available,
                      'status': 'idle', 'sessionId': None, 'revision': 0,
                      'nextSequence': 0, 'computer': None, 'inputs': [], 'error': None,
                      'task': {'flightExecuted': False, 'alignmentCompleted': False}}

    def capabilities(self):
        self.observations.append('capabilities')
        return {'available': self.available, 'mode': MODE, 'software': 'Comanche055',
                'scope': 'Transport-test cold-start CMC only; no flight.',
                'supportedKeys': ['VERB', 'PRO'] if self.available else [],
                'unavailableReason': None if self.available else 'Pinned CMC assets missing.'}

    def snapshot(self):
        self.observations.append('status')
        return deepcopy(self.state)

    def start(self):
        self.calls.append(('start',))
        if not self.available:
            raise ControlError(503, 'Original CMC assets unavailable.')
        self.state.update(status='ready', sessionId='http-cmc-session', revision=0,
                          nextSequence=0)
        return self.snapshot()

    def key(self, sessionId, sequence, key):
        if type(sequence) is not int or not isinstance(key, str) or key not in ('VERB', 'PRO'):
            raise ControlError(400, 'Unsupported hardware key or sequence.')
        if sessionId != self.state['sessionId'] or sequence != self.state['nextSequence']:
            raise ControlError(409, 'Stale CMC session or sequence.')
        self.calls.append(('key', sessionId, sequence, key))
        self.state.update(revision=self.state['revision']+1, nextSequence=sequence+1)
        result = self.snapshot()
        result['ack'] = {'sessionId': sessionId, 'sequence': sequence, 'key': key,
                         'channel': 26 if key == 'PRO' else 13,
                         'code': 8192 if key == 'PRO' else 17,
                         'queuedAtCycle': 100, 'afterCycle': 200}
        return result

    def stop(self, sessionId):
        if sessionId != self.state['sessionId']:
            raise ControlError(409, 'Wrong CMC session.')
        self.calls.append(('stop', sessionId))
        self.state.update(status='stopped')
        return self.snapshot()

    def close(self):
        self.closed = True


class EarthOrbitHttpTests(unittest.TestCase):
    def setUp(self):
        logger = patch.object(FinalHandler, 'log_message', return_value=None)
        logger.start()
        self.addCleanup(logger.stop)
        self.servers = []
        self.addCleanup(self.close_servers)
        self.server, self.cmc, self.controls = self.create_server()

    def create_server(self, available=True):
        service = FakeService(available)
        server = make_server(0, assets=None, earth_orbit=service)
        # A transport spy makes any accidental call into the legacy LM console
        # visible without booting an emulator or enabling spacecraft physics.
        server.controls.close()
        server.controls = FakeControls()
        server.live_enabled = True
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        worker.start()
        self.servers.append((server, worker))
        return server, service, server.controls

    def close_servers(self):
        for server, worker in self.servers:
            server.shutdown()
            close_server(server)
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertTrue(server.earth_orbit.closed)

    def request(self, method, path, value=None, headers=None, server=None, incomplete=False):
        server = server or self.server
        host = '127.0.0.1:'+str(server.server_port)
        raw = value if isinstance(value, bytes) else json.dumps(value).encode() if value is not None else b''
        outgoing = {'Host': host}
        if method == 'POST':
            outgoing.update({'Origin': 'http://'+host, 'Sec-Fetch-Site': 'same-origin',
                             'X-Apollo-Token': server.control_token,
                             'Content-Type': 'application/json', 'Content-Length': str(len(raw))})
        for key, item in (headers or {}).items():
            if item is None:
                outgoing.pop(key, None)
            else:
                outgoing[key] = item
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for key, item in outgoing.items():
                connection.putheader(key, item)
            connection.endheaders()
            if raw:
                connection.send(raw)
            if incomplete:
                connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            data = response.read()
            response_headers = dict(response.getheaders())
            parsed = json.loads(data) if data and response_headers.get('Content-Type', '').startswith('application/json') else data
            return response.status, response_headers, parsed
        finally:
            connection.close()

    def start(self, server=None):
        status, _, value = self.request('POST', '/api/earth-orbit/start', {}, server=server)
        self.assertEqual(status, 200)
        return value

    def test_capabilities_and_status_are_observations_without_any_computer_start(self):
        for path in ('/api/earth-orbit/capabilities', '/api/earth-orbit/status'):
            status, headers, value = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(value['mode'], MODE)
            self.assertTrue(value['available'])
            if path.endswith('capabilities'):
                self.assertEqual(value['token'], self.server.control_token)
                self.assertEqual(value['software'], 'Comanche055')
            else:
                self.assertEqual(value['status'], 'idle')
                self.assertIsNone(value['sessionId'])
                self.assertIsNone(value['computer'])
        self.assertEqual(self.cmc.calls, [])
        self.assertEqual(self.controls.calls, [])
        self.assertIsNone(self.controls.validation.thread)
        self.assertNotIn('token', self.cmc.capabilities())

    def test_exact_hardware_key_and_stop_requests_route_only_to_cmc_owner(self):
        state = self.start()
        for sequence, key, expected_channel in ((0, 'VERB', 13), (1, 'PRO', 26)):
            body = {'sessionId': state['sessionId'], 'sequence': sequence, 'key': key}
            status, _, state = self.request('POST', '/api/earth-orbit/key', body)
            self.assertEqual(status, 200)
            self.assertEqual(state['ack']['key'], key)
            self.assertEqual(state['ack']['sequence'], sequence)
            self.assertEqual(state['ack']['channel'], expected_channel)
            self.assertEqual(state['nextSequence'], sequence+1)
        status, _, stopped = self.request('POST', '/api/earth-orbit/stop', {'sessionId': state['sessionId']})
        self.assertEqual(status, 200)
        self.assertEqual(stopped['status'], 'stopped')
        self.assertEqual(self.cmc.calls, [('start',), ('key', 'http-cmc-session', 0, 'VERB'),
                                         ('key', 'http-cmc-session', 1, 'PRO'), ('stop', 'http-cmc-session')])
        self.assertEqual(self.controls.calls, [])
        self.assertIsNone(self.controls.validation.thread)

    def test_origin_host_token_and_fetch_guards_precede_any_cmc_mutation(self):
        cases = [({'Host': 'attacker.invalid'}, 421), ({'Origin': None}, 403),
                 ({'Origin': 'null'}, 403), ({'Origin': 'https://127.0.0.1'}, 403),
                 ({'X-Apollo-Token': None}, 403), ({'X-Apollo-Token': 'wrong-token'}, 403),
                 ({'Sec-Fetch-Site': 'cross-site'}, 403)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/earth-orbit/start', {}, headers)[0], expected)
        self.assertEqual(self.cmc.calls, [])
        self.assertEqual(self.controls.calls, [])
        for path in ('/api/earth-orbit/capabilities', '/api/earth-orbit/status'):
            for headers, expected in (({'Host': 'attacker.invalid'}, 421),
                                      ({'Origin': 'https://attacker.invalid'}, 403),
                                      ({'Sec-Fetch-Site': 'cross-site'}, 403)):
                self.assertEqual(self.request('GET', path, headers=headers)[0], expected)

    def test_exact_schemas_reject_missing_extra_and_non_object_commands_without_delegation(self):
        state = self.start()
        before = deepcopy(self.cmc.calls)
        good = {'sessionId': state['sessionId'], 'sequence': 0, 'key': 'VERB'}
        invalid = [dict(good, yaw=1), dict(good, expectedRevision=0),
                   {name: value for name, value in good.items() if name != 'key'},
                   {name: value for name, value in good.items() if name != 'sessionId'},
                   {name: value for name, value in good.items() if name != 'sequence'},
                   b'null', b'[]', b'"VERB"', b'1']
        for body in invalid:
            with self.subTest(body=body):
                self.assertEqual(self.request('POST', '/api/earth-orbit/key', body)[0], 400)
        for path, body in (('/api/earth-orbit/start', {'program': 52}),
                           ('/api/earth-orbit/stop', {}),
                           ('/api/earth-orbit/stop', {'sessionId': state['sessionId'], 'key': 'RSET'})):
            self.assertEqual(self.request('POST', path, body)[0], 400)
        self.assertEqual(self.cmc.calls, before)
        self.assertEqual(self.cmc.state['nextSequence'], 0)

    def test_duplicate_keys_nonfinite_invalid_utf8_and_malformed_json_are_rejected_before_service(self):
        bodies = [b'{"sessionId":"x","sessionId":"y","sequence":0,"key":"VERB"}',
                  b'{"sequence":NaN}', b'{"sequence":Infinity}', b'{"sequence":-Infinity}',
                  b'{"key":"\xff"}', b'{', b'{"key":"VERB",}']
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.request('POST', '/api/earth-orbit/key', body)[0], 400)
        self.assertEqual(self.cmc.calls, [])

    def test_body_length_transfer_encoding_and_media_type_stay_bounded(self):
        cases = [({'Content-Length': '8193'}, 413), ({'Content-Length': '0'}, 413),
                 ({'Content-Length': '-1'}, 413), ({'Content-Length': 'invalid'}, 411),
                 ({'Content-Length': None}, 411), ({'Transfer-Encoding': 'chunked'}, 400),
                 ({'Content-Type': 'text/plain'}, 415), ({'Content-Type': None}, 415)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/earth-orbit/start', {}, headers)[0], expected)
        self.assertEqual(self.request('POST', '/api/earth-orbit/start', b'{',
                                      {'Content-Length': '2'}, incomplete=True)[0], 400)
        self.assertEqual(self.cmc.calls, [])

    def test_unknown_paths_and_observation_methods_do_not_mutate_a_computer(self):
        for method, path, expected in (('GET', '/api/earth-orbit/unknown', 404),
                                       ('GET', '/api/earth-orbit/start', 404),
                                       ('POST', '/api/earth-orbit/unknown', 404),
                                       ('POST', '/api/earth-orbit/status', 404),
                                       ('HEAD', '/api/earth-orbit/status', 405),
                                       ('OPTIONS', '/api/earth-orbit/start', 403)):
            self.assertEqual(self.request(method, path, {} if method == 'POST' else None)[0], expected)
        self.assertEqual(self.cmc.calls, [])

    def test_service_conflicts_remain_explicit_and_never_fall_through_to_lm_controls(self):
        state = self.start()
        for body in ({'sessionId': 'old-session', 'sequence': 0, 'key': 'VERB'},
                     {'sessionId': state['sessionId'], 'sequence': 42, 'key': 'VERB'}):
            self.assertEqual(self.request('POST', '/api/earth-orbit/key', body)[0], 409)
        self.assertEqual(self.request('POST', '/api/earth-orbit/key',
                                      {'sessionId': state['sessionId'], 'sequence': 0, 'key': 'V37E52E'})[0], 400)
        self.assertEqual(self.cmc.calls, [('start',)])
        self.assertEqual(self.controls.calls, [])

    def test_legacy_lm_status_bootstrap_and_input_routes_keep_their_separate_contract(self):
        status, _, bootstrap = self.request('GET', '/api/bootstrap')
        self.assertEqual(status, 200)
        self.assertEqual(bootstrap['axes'], ['yaw', 'pitch'])
        self.assertEqual(bootstrap['pulseLeaseSeconds'], .5)
        self.assertEqual(bootstrap['scope'], 'Bounded attitude only; no powered descent.')
        self.assertEqual(self.request('GET', '/api/status')[0], 200)
        status, _, session = self.request('POST', '/api/session/start', {})
        self.assertEqual(status, 202)
        self.assertEqual(self.request('POST', '/api/input', {'sessionId': session['sessionId'],
                                      'sequence': 0, 'yaw': 1, 'pitch': 0})[0], 202)
        self.assertEqual(self.controls.calls[0], ('start',))
        self.assertEqual(self.cmc.calls, [])
        self.assertIsNone(self.cmc.state['sessionId'])

    def test_unavailable_cmc_does_not_disable_static_history_or_other_service_apis(self):
        server, service, controls = self.create_server(available=False)
        status, _, capabilities = self.request('GET', '/api/earth-orbit/capabilities', server=server)
        self.assertEqual(status, 200)
        self.assertFalse(capabilities['available'])
        self.assertIsNone(capabilities['token'])
        self.assertEqual(capabilities['supportedKeys'], [])
        self.assertEqual(self.request('GET', '/api/earth-orbit/status', server=server)[0], 200)
        self.assertEqual(self.request('POST', '/api/earth-orbit/start', {}, server=server)[0], 503)
        status, _, html = self.request('GET', '/campaign.html?stage=earth-parking', server=server,
                                     headers={'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document',
                                              'Sec-Fetch-Site': 'cross-site'})
        self.assertEqual(status, 200)
        self.assertIn(b'Apollo 11', html)
        self.assertEqual(self.request('GET', '/api/v1/capabilities', server=server)[0], 200)
        self.assertEqual(self.request('GET', '/api/procedure/status', server=server)[0], 200)
        self.assertEqual(self.request('POST', '/api/session/start', {}, server=server)[0], 202)
        self.assertEqual(controls.calls, [('start',)])
        self.assertEqual(service.calls, [('start',)])


if __name__ == '__main__':
    unittest.main()
