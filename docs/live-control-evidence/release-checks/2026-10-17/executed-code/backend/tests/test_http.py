"""Real loopback HTTP boundary tests with no native AGC or vehicle execution."""
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.control_service import ControlError, ControlService

spec = importlib.util.spec_from_file_location('apollo_http_under_test', ROOT / 'frontend/serve.py')
http_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(http_server)


class FakeControls:
    """Use real input validation while deliberately creating no native worker."""
    def __init__(self):
        self.validation = ControlService()
        self.calls = []
        self.starts = 0

    def snapshot(self):
        value = self.validation.snapshot()
        value['classification'] = 'HTTP unit fixture; no AGC execution'
        return value

    def start(self):
        if self.validation.state['status'] != 'idle':
            raise ControlError(409, 'Unit session already started')
        self.starts += 1
        self.validation.state.update(status='ready', sessionId='unit-session-{}'.format(self.starts))
        self.calls.append(('start',))
        return self.snapshot()

    def command(self, identity, sequence, yaw, pitch):
        result = self.validation.command(identity, sequence, yaw, pitch)
        self.calls.append(('input', identity, sequence, yaw, pitch))
        return result

    def stop(self, identity):
        result = self.validation.stop(identity)
        self.calls.append(('stop', identity))
        return result

    def record(self):
        value = self.validation.record()
        value['scope'] = 'HTTP unit fixture; no AGC execution or native telemetry'
        return value

    def close(self):
        self.validation.close()


class HttpTests(unittest.TestCase):
    def setUp(self):
        logger = patch.object(http_server.ApolloHandler, 'log_message', return_value=None)
        logger.start()
        self.addCleanup(logger.stop)
        self.servers = []
        self.addCleanup(self.close_servers)
        self.server, self.controls = self.create_server()

    def create_server(self, replay_only=False):
        controls = FakeControls()
        server = http_server.make_server(port=0, controls=controls, replay_only=replay_only)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        worker.start()
        self.servers.append((server, worker))
        return server, controls

    def close_servers(self):
        for server, worker in self.servers:
            server.shutdown()
            server.server_close()
            server.controls.close()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())

    def request(self, method, path, value=None, headers=None, server=None, incomplete=False):
        server = server or self.server
        host = '127.0.0.1:{}'.format(server.server_port)
        raw = value if isinstance(value, bytes) else json.dumps(value).encode() if value is not None else b''
        outgoing = {'Host': host}
        if method == 'POST':
            outgoing.update({'Origin': 'http://' + host, 'Sec-Fetch-Site': 'same-origin',
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
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def start(self, server=None):
        status, _, raw = self.request('POST', '/api/session/start', {}, server=server)
        self.assertEqual(status, 202)
        return json.loads(raw)['sessionId']

    def test_read_only_routes_do_not_create_session_or_submit_inputs(self):
        for path in ('/', '/api/bootstrap', '/api/status'):
            status, headers, raw = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertFalse(any(name.lower().startswith('access-control-') for name in headers))
            if path == '/api/bootstrap':
                data = json.loads(raw)
                self.assertTrue(data['liveEnabled'])
                self.assertEqual(data['token'], self.server.control_token)
                self.assertEqual(data['axes'], ['yaw', 'pitch'])
            elif path == '/api/status':
                self.assertIsNone(json.loads(raw)['sessionId'])
        for path in ('/api/session/start', '/api/input', '/api/session/stop'):
            self.assertEqual(self.request('GET', path)[0], 404)
        self.assertEqual(self.controls.calls, [])
        self.assertIsNone(self.controls.validation.thread)

    def test_start_input_and_stop_preserve_session_identity_and_forward_only_pilot_inputs(self):
        identity = self.start()
        payload = {'sessionId': identity, 'sequence': 0, 'yaw': -1, 'pitch': 1}
        status, _, raw = self.request('POST', '/api/input', payload)
        self.assertEqual(status, 202)
        accepted = json.loads(raw)
        self.assertEqual(accepted['sessionId'], identity)
        self.assertIn('not AGC consumption', accepted['meaning'])
        self.assertEqual(self.request('POST', '/api/input', payload)[0], 409)
        payload.update(sessionId='previous-session', sequence=1)
        self.assertEqual(self.request('POST', '/api/input', payload)[0], 409)
        self.assertEqual(self.request('POST', '/api/session/stop', {'sessionId': 'previous-session'})[0], 409)
        self.assertEqual(self.request('POST', '/api/session/stop', {'sessionId': identity})[0], 202)
        self.assertEqual(self.controls.calls, [('start',), ('input', identity, 0, -1, 1), ('stop', identity)])
        self.assertIsNone(self.controls.validation.thread)

    def test_host_origin_and_fetch_site_reject_cross_site_control_before_state_changes(self):
        host = '127.0.0.1:{}'.format(self.server.server_port)
        cases = [({'Host': 'attacker.invalid'}, 421), ({'Host': None}, 421),
                 ({'Host': '127.0.0.1:1'}, 421), ({'Origin': None}, 403),
                 ({'Origin': 'null'}, 403), ({'Origin': 'https://' + host}, 403),
                 ({'Origin': 'http://attacker.invalid'}, 403),
                 ({'Origin': 'http://' + host + '.attacker.invalid'}, 403),
                 ({'Sec-Fetch-Site': 'cross-site'}, 403), ({'Sec-Fetch-Site': 'same-site'}, 403)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/session/start', {}, headers)[0], expected)
        self.assertEqual(self.controls.calls, [])
        self.assertEqual(self.request('GET', '/api/bootstrap', headers={'Host': 'attacker.invalid'})[0], 421)
        self.assertEqual(self.request('GET', '/api/status', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_localhost_requires_its_own_matching_origin(self):
        host = 'localhost:{}'.format(self.server.server_port)
        self.assertEqual(self.request('POST', '/api/session/start', {}, {'Host': host})[0], 403)
        self.assertEqual(self.request('POST', '/api/session/start', {},
                                      {'Host': host, 'Origin': 'http://' + host})[0], 202)

    def test_token_is_required_for_mutation_and_record_and_non_ascii_is_rejected(self):
        for token in (None, '', 'incorrect', '\u00e9'):
            with self.subTest(token=token):
                headers = {'X-Apollo-Token': token}
                self.assertEqual(self.request('POST', '/api/session/start', {}, headers)[0], 403)
                self.assertEqual(self.request('GET', '/api/record', headers=headers)[0], 403)
        self.assertEqual(self.controls.calls, [])
        identity = self.start()
        status, headers, raw = self.request('GET', '/api/record',
                                            headers={'X-Apollo-Token': self.server.control_token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['session']['sessionId'], identity)
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_preflight_has_no_cors_grant_and_cannot_start_native_work(self):
        status, headers, _ = self.request('OPTIONS', '/api/session/start',
                                          headers={'Origin': 'https://attacker.invalid',
                                                   'Access-Control-Request-Method': 'POST',
                                                   'Access-Control-Request-Headers': 'X-Apollo-Token'})
        self.assertEqual(status, 403)
        self.assertFalse(any(name.lower().startswith('access-control-') for name in headers))
        self.assertEqual(self.controls.calls, [])

    def test_exact_fields_and_pilot_value_bounds_reject_without_forwarding(self):
        identity = self.start()
        normal = {'sessionId': identity, 'sequence': 0, 'yaw': 1, 'pitch': 0}
        bad_values = [dict(normal, **{'channel': 5}), {key: value for key, value in normal.items() if key != 'pitch'}]
        for field in ('yaw', 'pitch'):
            for invalid in (True, 1.0, '1', None, 2, -2, {}, []):
                bad_values.append(dict(normal, **{field: invalid}))
        for invalid in (True, 1.0, '0', None, -1, 2**31):
            bad_values.append(dict(normal, sequence=invalid))
        for payload in bad_values:
            with self.subTest(payload=payload):
                self.assertEqual(self.request('POST', '/api/input', payload)[0], 400)
        for path, payload in (('/api/session/start', {'unexpected': 1}),
                              ('/api/session/stop', {'sessionId': identity, 'yaw': 0}),
                              ('/api/session/stop', {})):
            self.assertEqual(self.request('POST', path, payload)[0], 400)
        self.assertEqual(self.controls.calls, [('start',)])
        self.assertEqual(self.controls.validation.sequence, -1)

    def test_non_finite_duplicate_malformed_and_non_object_json_never_submit_inputs(self):
        identity = self.start()
        prefix = ('{"sessionId":"' + identity + '","sequence":0,"yaw":').encode()
        invalid = [prefix + number + b',"pitch":0}' for number in (b'NaN', b'Infinity', b'-Infinity')]
        invalid.extend([prefix + b'1,"yaw":1,"pitch":0}', b'{"nested":{"x":1,"x":2}}',
                        b'{', b'null', b'[]', b'false', b'42', b'{"yaw":"\xff"}'])
        for raw in invalid:
            with self.subTest(body=raw):
                self.assertEqual(self.request('POST', '/api/input', raw)[0], 400)
        self.assertEqual(self.controls.calls, [('start',)])
        self.assertEqual(self.controls.validation.sequence, -1)

    def test_request_framing_body_limit_and_content_type_fail_before_mutation(self):
        cases = [({'Content-Length': None}, 411), ({'Content-Length': 'invalid'}, 411),
                 ({'Content-Length': '-1'}, 413), ({'Content-Length': '0'}, 413),
                 ({'Content-Length': '1025'}, 413), ({'Content-Type': 'text/plain'}, 415),
                 ({'Content-Type': None}, 415), ({'Transfer-Encoding': 'chunked'}, 400)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/session/start', b'{}', headers)[0], expected)
        self.assertEqual(self.request('POST', '/api/session/start', b'{}',
                                      {'Content-Length': '3'}, incomplete=True)[0], 400)
        self.assertEqual(self.controls.calls, [])

    def test_static_routes_serve_dist_and_never_repository_source(self):
        status, _, raw = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Apollo', raw)
        for path in ('/serve.py', '/../backend/native_session.py', '/%2e%2e/backend/native_session.py',
                     '/docs/phase7-evidence/source/mappings.json', '/../../AGENTS.md', '/api/throttle'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)
        self.assertEqual(self.request('POST', '/api/throttle', {})[0], 404)
        self.assertEqual(self.controls.calls, [])

    def test_replay_only_server_discloses_disabled_live_and_rejects_all_mutations(self):
        server, controls = self.create_server(replay_only=True)
        status, _, raw = self.request('GET', '/api/bootstrap', server=server)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertFalse(data['liveEnabled'])
        self.assertIsNone(data['token'])
        for path, payload in (('/api/session/start', {}),
                              ('/api/input', {'sessionId': 'unit', 'sequence': 0, 'yaw': 1, 'pitch': 0}),
                              ('/api/session/stop', {'sessionId': 'unit'})):
            self.assertEqual(self.request('POST', path, payload, server=server)[0], 409)
        self.assertEqual(controls.calls, [])


if __name__ == '__main__':
    unittest.main()
