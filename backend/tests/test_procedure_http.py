"""Real loopback procedure boundary tests; native AGC is deliberately unused."""
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.procedure_service import MODE, ProcedureService
from backend.tests.test_http import FakeControls, http_server
from backend.tests.test_procedure_service import definition


class ProcedureHttpTests(unittest.TestCase):
    def setUp(self):
        logger = patch.object(http_server.ApolloHandler, 'log_message', return_value=None)
        logger.start()
        self.addCleanup(logger.stop)
        self.servers = []
        self.addCleanup(self.close_servers)
        self.server, self.controls, self.procedures = self.create_server()

    def create_server(self, replay_only=False, procedures=None):
        controls = FakeControls()
        procedures = procedures if procedures is not None else ProcedureService(definition=definition())
        server = http_server.make_server(0, controls=controls, procedures=procedures, replay_only=replay_only)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        worker.start()
        self.servers.append((server, worker))
        return server, controls, procedures

    def close_servers(self):
        for server, worker in self.servers:
            server.shutdown()
            server.server_close()
            server.controls.close()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())

    def request(self, method, path, value=None, headers=None, server=None):
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
            response = connection.getresponse()
            data = response.read()
            return response.status, dict(response.getheaders()), json.loads(data)
        finally:
            connection.close()

    def start(self, server=None):
        status, _, state = self.request('POST', '/api/procedure/start', {}, server=server)
        self.assertEqual(status, 202)
        return state

    def payload(self, state, **changes):
        step = state['currentStep']
        value = {'sessionId': state['sessionId'], 'sequence': state['lastSequence'] + 1,
                 'expectedRevision': state['revision'], 'role': step['role'],
                 'action': step['id'], 'value': step['correctValue']}
        value.update(changes)
        return value

    def test_bootstrap_adds_trainer_capabilities_without_changing_native_scope(self):
        status, headers, value = self.request('GET', '/api/bootstrap')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertTrue(value['procedureEnabled'])
        self.assertEqual(value['procedureCapabilities']['mode'], MODE)
        self.assertFalse(value['procedureCapabilities']['originalAgc'])
        self.assertFalse(value['procedureCapabilities']['flightPhysics'])
        self.assertEqual(value['axes'], ['yaw', 'pitch'])
        self.assertEqual(value['pulseLeaseSeconds'], .5)
        self.assertEqual(value['scope'], 'Bounded attitude only; no powered descent.')
        self.assertEqual(self.controls.calls, [])

    def test_status_read_is_idle_and_never_starts_native_or_training_session(self):
        status, _, state = self.request('GET', '/api/procedure/status')
        self.assertEqual(status, 200)
        self.assertEqual(state['classification'], MODE)
        self.assertEqual(state['status'], 'idle')
        self.assertIsNone(state['sessionId'])
        self.assertEqual(self.controls.calls, [])
        self.assertIsNone(self.controls.validation.thread)
        self.assertEqual(self.procedures.snapshot()['revision'], 0)

    def test_full_checklist_uses_server_ack_and_does_not_call_native_controls(self):
        state = self.start()
        while state['currentStep'] is not None:
            status, _, result = self.request('POST', '/api/procedure/action', self.payload(state))
            self.assertEqual(status, 202)
            self.assertTrue(result['accepted'])
            self.assertTrue(result['advanced'])
            state = result['snapshot']
        self.assertEqual(state['attachment'], 'released')
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['revision'], 5)
        self.assertEqual(len(state['events']), 5)
        self.assertEqual(self.controls.calls, [])
        self.assertIsNone(self.controls.validation.thread)
        self.assertNotIn('positionM', state)
        self.assertNotIn('dsky', state)

    def test_origin_host_token_and_fetch_boundary_precede_any_procedure_mutation(self):
        before = self.procedures.snapshot()
        cases = [({'Host': 'attacker.invalid'}, 421), ({'Origin': None}, 403),
                 ({'Origin': 'null'}, 403), ({'X-Apollo-Token': None}, 403),
                 ({'X-Apollo-Token': 'incorrect'}, 403), ({'Sec-Fetch-Site': 'cross-site'}, 403)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/procedure/start', {}, headers)[0], expected)
        self.assertEqual(self.procedures.snapshot(), before)
        self.assertEqual(self.request('GET', '/api/procedure/status',
                                      headers={'Host': 'attacker.invalid'})[0], 421)

    def test_exact_schema_and_json_guard_reject_extra_commands_without_mutation(self):
        state = self.start()
        normal = self.payload(state)
        invalid = [dict(normal, yaw=1), {key: value for key, value in normal.items() if key != 'expectedRevision'},
                   b'null', b'[]', b'{"sequence":0,"sequence":1}', b'{"value":NaN}',
                   b'{"value":"\xff"}', b'{']
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(self.request('POST', '/api/procedure/action', value)[0], 400)
        self.assertEqual(self.request('POST', '/api/procedure/start', {'reset': True})[0], 400)
        self.assertEqual(self.procedures.snapshot(), state)
        self.assertEqual(self.controls.calls, [])

    def test_wrong_role_stale_revision_and_out_of_order_action_fail_before_release(self):
        state = self.start()
        for changes, expected in (({'role': 'CDR'}, 403), ({'expectedRevision': 1}, 409),
                                  ({'action': 'release', 'role': 'CMP', 'value': 'EXTD/REL'}, 409),
                                  ({'sessionId': 'old-session'}, 409)):
            self.assertEqual(self.request('POST', '/api/procedure/action', self.payload(state, **changes))[0], expected)
        self.assertEqual(self.procedures.snapshot(), state)

    def test_request_size_transfer_encoding_and_content_type_are_bounded(self):
        cases = [({'Content-Length': '1025'}, 413), ({'Content-Type': 'text/plain'}, 415),
                 ({'Transfer-Encoding': 'chunked'}, 400), ({'Content-Length': None}, 411)]
        for headers, expected in cases:
            self.assertEqual(self.request('POST', '/api/procedure/start', {}, headers)[0], expected)
        self.assertIsNone(self.procedures.snapshot()['sessionId'])

    def test_replay_only_advertises_disabled_trainer_and_rejects_both_mutations(self):
        server, controls, procedures = self.create_server(replay_only=True)
        status, _, bootstrap = self.request('GET', '/api/bootstrap', server=server)
        self.assertEqual(status, 200)
        self.assertFalse(bootstrap['procedureEnabled'])
        self.assertFalse(bootstrap['liveEnabled'])
        self.assertIsNone(bootstrap['token'])
        status, _, state = self.request('GET', '/api/procedure/status', server=server)
        self.assertEqual(status, 200)
        self.assertFalse(state['available'])
        self.assertIn('replay-only', state['message'])
        for path, value in (('/api/procedure/start', {}),
                            ('/api/procedure/action', {'sessionId': 'x', 'sequence': 0,
                              'expectedRevision': 0, 'role': 'CMP', 'action': 'release', 'value': 'EXTD/REL'})):
            self.assertEqual(self.request('POST', path, value, server=server)[0], 409)
        self.assertIsNone(procedures.snapshot()['sessionId'])
        self.assertEqual(controls.calls, [])

    def test_missing_definition_disables_only_trainer_and_returns_clear_error(self):
        service = ProcedureService(definition_path=ROOT / '.build/missing-procedure-definition.json')
        server, controls, _ = self.create_server(procedures=service)
        self.assertFalse(self.request('GET', '/api/bootstrap', server=server)[2]['procedureEnabled'])
        self.assertFalse(self.request('GET', '/api/procedure/status', server=server)[2]['available'])
        status, _, error = self.request('POST', '/api/procedure/start', {}, server=server)
        self.assertEqual(status, 503)
        self.assertIn('unavailable', error['error'])
        self.assertEqual(self.request('POST', '/api/session/start', {}, server=server)[0], 202)
        self.assertEqual(controls.calls, [('start',)])

    def test_restart_invalidates_previous_browser_action_without_native_start(self):
        old = self.start()
        fresh = self.start()
        self.assertNotEqual(old['sessionId'], fresh['sessionId'])
        self.assertEqual(self.request('POST', '/api/procedure/action', self.payload(old))[0], 409)
        self.assertEqual(self.procedures.snapshot(), fresh)
        self.assertEqual(self.controls.calls, [])


if __name__ == '__main__':
    unittest.main()
