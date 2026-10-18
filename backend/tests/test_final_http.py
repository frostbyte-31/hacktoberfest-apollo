"""Real three-client HTTP integration over the actual educational Tcl plant.

These tests verify shared application authority and transport, not Apollo
guidance or a historical landing. Native Phase 12 proof is tested separately.
Prepare .build/final-demo-assets.json with backend.final_assets first.
"""
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend.final_server import FinalHandler, close_server, make_server
from backend.mission_service import MissionService, ROLE_IDS

ROOT = Path(__file__).resolve().parents[2]


class Client:
    """An independent browser-equivalent credential/sequence context."""
    def __init__(self, server):
        self.server = server
        self.global_token = None
        self.token = self.identity = self.run_id = None
        self.sequence = -1
        status, _, raw = self.request('GET', '/api/v1/capabilities')
        if status != 200:
            raise AssertionError('Actual HTTP capability discovery failed: '+repr(raw))
        self.global_token = json.loads(raw)['token']

    def request(self, method, path, value=None, headers=None, incomplete=False):
        host = '127.0.0.1:'+str(self.server.server_port)
        raw = value if isinstance(value, bytes) else json.dumps(value).encode() if value is not None else b''
        outgoing = {'Host': host}
        if method == 'POST':
            outgoing.update(Origin='http://'+host, **{'Sec-Fetch-Site': 'same-origin',
                'X-Apollo-Token': self.global_token, 'Content-Type': 'application/json',
                'Content-Length': str(len(raw))})
        if self.token:
            outgoing['X-Apollo-Participant'] = self.token
        for key, value in (headers or {}).items():
            if value is None:
                outgoing.pop(key, None)
            else:
                outgoing[key] = value
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=7)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for key, value in outgoing.items():
                if value is not None:
                    connection.putheader(key, value)
            connection.endheaders()
            if raw:
                connection.send(raw)
            if incomplete:
                connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def create(self, role='commander', modes=None):
        status, _, raw = self.request('POST', '/api/v1/missions', {
            'scenarioId': 'training', 'name': 'Commander client', 'role': role,
            'crewModes': modes or {name: 'human' for name in ROLE_IDS}})
        data = json.loads(raw)
        if status == 200:
            self.identity, self.token = data['missionId'], data['participantToken']
            self.run_id = data['snapshot']['runId']
        return status, data

    def join(self, identity, role, name):
        status, _, raw = self.request('POST', '/api/v1/missions/'+identity+'/join', {'role': role, 'name': name})
        data = json.loads(raw)
        if status == 200:
            self.identity, self.token = data['missionId'], data['participantToken']
            self.run_id = data['snapshot']['runId']
        return status, data

    def command(self, action, payload=None, **overrides):
        value = {'sequence': self.sequence+1, 'runId': self.run_id, 'action': action,
                 'payload': {} if payload is None else payload}
        value.update(overrides)
        status, _, raw = self.request('POST', '/api/v1/missions/'+self.identity+'/command', value)
        data = json.loads(raw)
        if status == 200:
            self.sequence = data['sequence']
            self.run_id = data['snapshot']['runId']
        return status, data

    def snapshot(self):
        status, _, raw = self.request('GET', '/api/v1/missions/'+self.identity)
        return status, json.loads(raw)


class FinalHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('APOLLO_FINAL_TEST_ASSETS', ROOT/'.build/final-demo-assets.json'))
        cls.assets = json.loads(path.read_text())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='apollo-final-http-')
        self.addCleanup(self.directory.cleanup)
        self.servers = []
        self.addCleanup(self.close_servers)
        logger = patch.object(FinalHandler, 'log_message', return_value=None)
        logger.start()
        self.addCleanup(logger.stop)
        self.server, self.service = self.server_for(self.assets)
        self.host = Client(self.server)

    def server_for(self, assets):
        directory = Path(self.directory.name)/str(len(self.servers))
        service = MissionService(assets=assets, output_root=directory, pace=False, clock=lambda: 0.)
        try:
            server = make_server(port=0, assets=assets, missions=service,
                                 assets_error='Locked native dependencies unavailable' if assets is None else None)
        except BaseException:
            service.close()
            raise
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return server, service

    def close_servers(self):
        for server, thread in self.servers:
            server.shutdown()
            close_server(server)
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())

    def crew(self):
        commander = self.host
        self.assertEqual(commander.create()[0], 200)
        pilot, collins = Client(self.server), Client(self.server)
        self.assertEqual(pilot.join(commander.identity, 'lunar-module-pilot', 'Pilot client')[0], 200)
        self.assertEqual(collins.join(commander.identity, 'command-module-pilot', 'Orbital client')[0], 200)
        self.assertEqual(len({commander.token, pilot.token, collins.token}), 3)
        return commander, pilot, collins

    def start(self, crew):
        for client in crew:
            self.assertEqual(client.command('ready', {'ready': True})[0], 200)
        self.assertEqual(crew[0].command('start')[0], 200)

    def test_three_independent_clients_share_one_real_physical_state_and_audit(self):
        crew = self.crew()
        self.start(crew)
        self.assertEqual(crew[0].command('controls', {'throttle': .5, 'pitch': .25})[0], 200)
        self.assertEqual(crew[1].command('checklist', {'item': 'state-vector'})[0], 200)
        self.assertEqual(crew[2].command('message', {'text': 'Orbital support is monitoring the shared mission.'})[0], 200)
        before = crew[0].snapshot()[1]['physics']
        self.service.advance(crew[0].identity, ticks=10)  # Actual server owner, no public step endpoint.
        snapshots = [client.snapshot()[1] for client in crew]
        self.assertEqual([row['you']['role'] for row in snapshots], list(ROLE_IDS))
        self.assertEqual(snapshots[0]['physics'], snapshots[1]['physics'])
        self.assertEqual(snapshots[1]['physics'], snapshots[2]['physics'])
        self.assertEqual(len(self.service.missions), 1)
        physical = snapshots[0]['physics']
        self.assertEqual(physical['mode'], 'EDUCATIONAL_PHYSICS_LAB')
        self.assertEqual(physical['tick'], 10)
        self.assertLess(physical['spacecraft']['fuelKg'], before['spacecraft']['fuelKg'])
        self.assertNotEqual(physical['spacecraft']['positionM'], before['spacecraft']['positionM'])
        self.assertTrue(snapshots[0]['checklist']['state-vector']['done'])
        self.assertEqual(snapshots[0]['messages'][-1]['name'], 'Orbital client')
        self.assertEqual(snapshots[0]['crew'][2]['location'], 'Command Module in lunar orbit')
        self.assertFalse(snapshots[0]['capabilities']['authenticAGC'])
        logs = list(Path(self.directory.name).rglob('audit.jsonl'))
        self.assertEqual(len(logs), 1)
        raw = logs[0].read_text()
        records = [json.loads(line) for line in raw.splitlines()]
        actions = {row['value'].get('action') for row in records if row['kind']=='command'}
        self.assertTrue({'controls', 'checklist', 'message'}.issubset(actions))
        self.assertTrue(any(row['kind']=='physics' and row['value']['tick']==10 for row in records))
        for client in crew:
            self.assertNotIn(client.token, raw)

    def test_role_permissions_prevent_flight_or_state_writes_and_preserve_sequence(self):
        crew = self.crew()
        self.start(crew)
        before = crew[0].snapshot()[1]['physics']
        for client in crew[1:]:
            self.assertEqual(client.command('controls', {'throttle': 1, 'pitch': 0})[0], 403)
            self.assertEqual(client.command('pause')[0], 403)
        self.assertEqual(crew[2].command('checklist', {'item': 'braking'})[0], 403)
        self.assertEqual(crew[0].command('checklist', {'item': 'braking'})[0], 403)
        self.assertEqual(crew[0].command('set_state', {'positionM': [0,0,0]})[0], 400)
        self.assertEqual(crew[0].command('controls', {'throttle': .5, 'pitch': 0, 'velocityMps': [0,0,0]})[0], 400)
        self.assertEqual(crew[0].snapshot()[1]['physics'], before)
        # Failed commands did not consume sequence numbers or change roles.
        self.assertEqual(crew[1].snapshot()[1]['you']['lastSequence'], 0)
        self.assertEqual(crew[1].command('message', {'text': 'Still an authorized pilot.'})[0], 200)
        self.assertEqual(crew[1].sequence, 1)

    def test_start_requires_exactly_three_occupied_ready_roles_and_seats_cannot_collide(self):
        self.assertEqual(self.host.create()[0], 200)
        self.assertEqual(self.host.command('start')[0], 409)
        competitor = Client(self.server)
        self.assertEqual(competitor.join(self.host.identity, 'commander', 'Duplicate commander')[0], 409)
        self.assertEqual(competitor.join(self.host.identity, 'command-module-pilot', 'Orbital client')[0], 200)
        self.assertEqual(self.host.command('ready', {'ready': True})[0], 200)
        self.assertEqual(competitor.command('ready', {'ready': True})[0], 200)
        self.assertEqual(self.host.command('start')[0], 409)
        pilot = Client(self.server)
        self.assertEqual(pilot.join(self.host.identity, 'lunar-module-pilot', 'Pilot client')[0], 200)
        self.assertEqual(self.host.command('start')[0], 409)
        self.assertEqual(pilot.command('ready', {'ready': True})[0], 200)
        self.assertEqual(self.host.command('start')[0], 200)
        late = Client(self.server)
        self.assertEqual(late.join(self.host.identity, 'commander', 'Late client')[0], 409)
        self.assertEqual(len(self.host.snapshot()[1]['crew']), 3)

    def test_restart_stale_epoch_duplicate_sequence_and_reload_state(self):
        crew = self.crew()
        self.start(crew)
        self.assertEqual(crew[0].command('controls', {'throttle': .4, 'pitch': 0})[0], 200)
        self.service.advance(self.host.identity, ticks=10)
        old_run, old_sequence = crew[0].run_id, crew[0].sequence
        self.assertEqual(crew[0].command('restart')[0], 200)
        self.assertNotEqual(crew[0].run_id, old_run)
        self.assertEqual(crew[0].snapshot()[1]['physics']['tick'], 0)
        self.assertEqual(crew[1].command('message', {'text': 'Stale epoch rejected.'})[0], 409)
        self.assertEqual(crew[0].command('message', {'text': 'Duplicate rejected.'}, sequence=old_sequence)[0], 409)
        reloaded = Client(self.server)
        reloaded.identity, reloaded.token = crew[0].identity, crew[0].token
        status, snapshot = reloaded.snapshot()
        self.assertEqual(status, 200)
        self.assertEqual(snapshot['you']['lastSequence'], crew[0].sequence)
        reloaded.sequence, reloaded.run_id = snapshot['you']['lastSequence'], snapshot['runId']
        self.assertEqual(reloaded.command('message', {'text': 'Reloaded participant preserved authority.'})[0], 200)
        self.assertEqual(reloaded.sequence, crew[0].sequence+1)
        self.assertEqual(reloaded.snapshot()[1]['physics']['tick'], 0)

    def test_identical_http_inputs_and_owner_ticks_are_deterministic(self):
        first = self.crew()
        self.start(first)
        self.assertEqual(first[0].command('controls', {'throttle': .25, 'pitch': -.2})[0], 200)
        self.service.advance(first[0].identity, ticks=20)
        expected = first[0].snapshot()[1]['physics']
        second = tuple(Client(self.server) for _ in ROLE_IDS)
        self.assertEqual(second[0].create()[0], 200)
        self.assertEqual(second[1].join(second[0].identity, ROLE_IDS[1], 'Second pilot')[0], 200)
        self.assertEqual(second[2].join(second[0].identity, ROLE_IDS[2], 'Second orbital client')[0], 200)
        self.start(second)
        self.assertEqual(second[0].command('controls', {'throttle': .25, 'pitch': -.2})[0], 200)
        self.service.advance(second[0].identity, ticks=20)
        self.assertEqual(second[0].snapshot()[1]['physics'], expected)

    def test_global_token_origin_host_and_participant_auth_are_enforced(self):
        identity = self.crew()[0].identity
        value = {'sequence': 0, 'runId': self.host.run_id, 'action': 'ready', 'payload': {'ready': True}}
        path = '/api/v1/missions/'+identity+'/command'
        for headers, expected in [({'X-Apollo-Token': None},403), ({'X-Apollo-Token':'bad'},403),
                                   ({'Origin':None},403), ({'Origin':'http://attacker.invalid'},403),
                                   ({'Sec-Fetch-Site':'cross-site'},403), ({'Host':'attacker.invalid'},421),
                                   ({'X-Apollo-Participant':None},403), ({'X-Apollo-Participant':'bad'},403)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.host.request('POST', path, value, headers)[0], expected)
        self.assertEqual(self.host.snapshot()[1]['you']['lastSequence'], -1)
        spectator = Client(self.server)
        self.assertEqual(spectator.request('GET', '/api/v1/missions/'+identity)[0], 200)
        self.assertIsNone(json.loads(spectator.request('GET', '/api/v1/missions/'+identity)[2])['you'])
        self.assertEqual(spectator.request('GET', '/api/v1/missions/'+identity,
                         headers={'X-Apollo-Participant':'bad'})[0], 403)

    def test_invalid_json_nonfinite_duplicates_and_extra_fields_never_create_a_mission(self):
        invalid = [b'{', b'null', b'[]', b'false', b'42', b'{"value":NaN}',
                   b'{"value":Infinity}', b'{"value":-Infinity}', b'{"x":1,"x":2}',
                   b'{"nested":{"x":1,"x":2}}', b'{"name":"\xff"}']
        for raw in invalid:
            with self.subTest(raw=raw):
                self.assertEqual(self.host.request('POST','/api/v1/missions', raw)[0], 400)
        self.assertEqual(self.host.request('POST','/api/v1/missions', {'extra': True})[0], 400)
        self.assertEqual(len(self.service.missions), 0)

    def test_request_size_type_length_and_incomplete_bodies_fail_closed(self):
        path = '/api/v1/missions'
        for headers, status in [({'Content-Type':'text/plain'},415), ({'Content-Length':None},411),
                                 ({'Content-Length':'not-an-integer'},411), ({'Content-Length':'0'},413),
                                 ({'Content-Length':'8193'},413), ({'Transfer-Encoding':'chunked'},400)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.host.request('POST', path, b'{}', headers)[0], status)
        self.assertEqual(self.host.request('POST', path, b'{}', {'Content-Length':'20'}, incomplete=True)[0], 400)
        self.assertEqual(len(self.service.missions), 0)

    def test_unsupported_actions_invalid_actuators_and_cross_mission_tokens_are_rejected(self):
        crew = self.crew()
        self.start(crew)
        before = crew[0].snapshot()[1]['physics']
        for value in [True, '1', -1, 2, None]:
            self.assertEqual(crew[0].command('controls', {'throttle':value, 'pitch':0})[0], 400)
        self.assertEqual(crew[0].command('controls', {'throttle':.4, 'pitch':2})[0], 400)
        self.assertEqual(crew[0].command('controls', {'throttle':.4, 'pitch':0}, sequence=True)[0], 409)
        self.assertEqual(crew[0].command('arbitrary_dsky', {'keys':'V37E63E'})[0], 400)
        self.assertEqual(crew[0].snapshot()[1]['physics'], before)
        other = Client(self.server)
        self.assertEqual(other.create()[0], 200)
        payload = {'sequence': 2, 'runId': crew[0].run_id, 'action':'pause', 'payload':{}}
        self.assertEqual(other.request('POST', '/api/v1/missions/'+crew[0].identity+'/command', payload)[0], 403)

    def test_unavailable_native_capabilities_keep_authentic_recordings_accessible(self):
        server, service = self.server_for(None)
        client = Client(server)
        status, _, raw = client.request('GET','/api/v1/capabilities')
        self.assertEqual(status, 200)
        caps = json.loads(raw)
        self.assertFalse(caps['capabilities']['physicsLab'])
        self.assertFalse(caps['capabilities']['liveAuthenticAttitude'])
        self.assertFalse(caps['capabilities']['authenticLanding'])
        self.assertIsNotNone(caps['dependencyError'])
        self.assertEqual(client.create()[0], 503)
        self.assertEqual(len(service.missions), 0)
        status, _, raw = client.request('GET','/api/bootstrap')
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)['liveEnabled'])
        for path in ('/guidance.html','/data/guidance.json','/data/propulsion.json',
                     '/data/propulsion-lab.json'):
            self.assertEqual(client.request('GET', path)[0], 200)

    def test_python_only_undocking_stays_playable_without_native_assets(self):
        server, service = self.server_for(None)
        client = Client(server)
        status, _, raw = client.request('GET', '/api/bootstrap')
        bootstrap = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertFalse(bootstrap['liveEnabled'])
        self.assertTrue(bootstrap['procedureEnabled'])
        self.assertEqual(bootstrap['token'], client.global_token)
        self.assertEqual(client.request('POST', '/api/session/start', {})[0], 409)
        self.assertEqual(server.controls.snapshot()['status'], 'idle')
        self.assertIsNone(server.controls.snapshot()['frame'])

        status, _, raw = client.request('POST', '/api/procedure/start', {})
        self.assertEqual(status, 202)
        state = json.loads(raw)
        self.assertEqual(state['mode'], 'INTERACTIVE PROCEDURE TRAINER')
        self.assertTrue(state['available'])
        for _ in range(28):
            step = state['currentStep']
            status, _, raw = client.request('POST', '/api/procedure/action', {
                'sessionId': state['sessionId'], 'sequence': state['lastSequence'] + 1,
                'expectedRevision': state['revision'], 'role': step['role'],
                'action': step['id'], 'value': step['correctValue'],
            })
            self.assertEqual(status, 202)
            reply = json.loads(raw)
            self.assertTrue(reply['advanced'])
            state = reply['snapshot']
        self.assertTrue(state['completed'])
        self.assertEqual(state['attachment'], 'released')
        self.assertFalse(state['capabilities']['originalAgc'])
        self.assertFalse(state['capabilities']['flightPhysics'])
        self.assertEqual(server.controls.snapshot()['status'], 'idle')
        self.assertIsNone(server.controls.snapshot()['frame'])
        self.assertEqual(len(service.missions), 0)

    def test_preserved_old_routes_and_static_data_do_not_start_native_execution(self):
        for path in ('/api/bootstrap','/api/status','/guidance.html','/index.html','/mission.html',
                     '/data/guidance.json','/data/replay.json','/data/propulsion.json',
                     '/data/propulsion-lab.json'):
            status, headers, raw = self.host.request('GET',path)
            self.assertEqual(status, 200, path)
            self.assertGreater(len(raw), 0)
            self.assertFalse(any(k.lower().startswith('access-control-') for k in headers))
            if path == '/api/bootstrap':
                self.assertEqual(json.loads(raw)['axes'], ['yaw','pitch'])
                self.assertEqual(json.loads(raw)['token'], self.host.global_token)
            if path == '/api/status':
                self.assertEqual(json.loads(raw)['status'], 'idle')
                self.assertIsNone(json.loads(raw)['sessionId'])
        self.assertEqual(self.server.controls.snapshot()['status'], 'idle')
        self.assertEqual(len(self.service.missions), 0)

    def test_unknown_routes_and_no_public_arbitrary_time_step_endpoint(self):
        self.assertEqual(self.host.request('GET','/api/v1/missions/0000000000000000')[0], 404)
        self.assertEqual(self.host.request('GET','/api/v1/missing-capability')[0], 404)
        self.assertEqual(self.host.request('GET','/data/definitely-not-an-evidence-file.json')[0], 404)
        self.assertEqual(self.host.create()[0], 200)
        for suffix in ('step','state','arbitrary-input'):
            self.assertEqual(self.host.request('POST','/api/v1/missions/'+self.host.identity+'/'+suffix, {'ticks':1000})[0], 404)
        self.assertEqual(self.host.request('GET','/api/v1/missions/'+self.host.identity+'/command')[0], 404)
        self.assertEqual(self.host.snapshot()[1]['physics']['tick'], 0)

    def test_cross_site_navigation_allows_static_documents_only_with_a_valid_host(self):
        navigation = {'Origin': 'https://outside.example', 'Sec-Fetch-Site': 'cross-site',
                      'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
        for path in ('/mission.html', '/guidance.html', '/index.html'):
            self.assertEqual(self.host.request('GET', path, headers=navigation)[0], 200)
        for path in ('/api/v1/capabilities', '/api/bootstrap', '/api/status'):
            self.assertEqual(self.host.request('GET', path, headers=navigation)[0], 403)
        self.assertEqual(self.host.request('POST', '/api/v1/missions', {}, navigation)[0], 403)
        self.assertEqual(self.host.request('GET', '/mission-app.mjs', headers={
            **navigation, 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'script'})[0], 403)
        self.assertEqual(self.host.request('GET', '/mission.html', headers={
            **navigation, 'Host': 'outside.example'})[0], 421)
        self.assertEqual(self.host.request('HEAD', '/mission.html', headers={
            **navigation, 'Host': 'outside.example'})[0], 421)
        self.assertEqual(len(self.service.missions), 0)


if __name__ == '__main__':
    unittest.main()
