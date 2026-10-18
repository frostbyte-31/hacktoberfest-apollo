"""Async crew integration using explicit model stubs and the real Tcl plant.

No remote model or real credential is used. Native Apollo execution is not
claimed by these tests of the independent educational mission service.
"""
from concurrent.futures import wait
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from backend.mission_service import CONTROL_LEASE, MissionService, ROLE_IDS

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self): self.value = 100.
    def __call__(self): return self.value


class StubProvider:
    """Event-controlled, clearly synthetic provider; never an actual LLM."""
    def __init__(self, response=None, gates=None):
        self.response = response if response is not None else [{'action':'message','payload':{'text':'UNIT TEST model stub response'}}]
        self.gates = gates or {}
        self.release = threading.Event()
        self.condition = threading.Condition()
        self.calls = []
        self.key = 'UNIT_PRIVATE_PROVIDER_MARKER'

    def decide(self, role, snapshot, results):
        with self.condition:
            index = len(self.calls)+1
            self.calls.append({'role':role,'snapshot':deepcopy(snapshot),'results':deepcopy(results),'index':index})
            self.condition.notify_all()
        gate = self.gates.get(index, self.release)
        if not gate.wait(10):
            raise TimeoutError('Synthetic test provider was not released')
        response = self.response(role,index,snapshot) if callable(self.response) else self.response
        if isinstance(response, Exception): raise response
        return deepcopy(response)

    def started(self, count, timeout=3):
        with self.condition:
            return self.condition.wait_for(lambda: len(self.calls)>=count, timeout)

    def unblock(self):
        self.release.set()
        for gate in self.gates.values(): gate.set()


class MissionAiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('APOLLO_FINAL_TEST_ASSETS', ROOT/'.build/final-demo-assets.json'))
        cls.assets = json.loads(path.read_text())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='apollo-stub-ai-')
        self.clock = Clock()
        self.services, self.providers = [], []

    def tearDown(self):
        # Always release deliberately blocked test jobs before executor close.
        for provider in self.providers: provider.unblock()
        for service in self.services: service.close()
        self.directory.cleanup()

    def service(self, provider):
        service = MissionService(assets=self.assets, ai_provider=provider, pace=False,
                 clock=self.clock, output_root=Path(self.directory.name)/str(len(self.services)))
        self.providers.append(provider)
        self.services.append(service)
        return service

    def command(self, service, client, action, payload=None):
        state = service.snapshot(client['missionId'],client['participantToken'])
        return service.command(client['missionId'],client['participantToken'],
                {'sequence':state['you']['lastSequence']+1, 'runId':state['runId'],
                 'action':action, 'payload':{} if payload is None else payload})

    def mission(self, service, modes):
        human_roles = [role for role in ROLE_IDS if modes[role]=='human']
        role = human_roles[0] if human_roles else None
        host = service.create({'scenarioId':'training','name':'Unit test host','role':role,'crewModes':modes})
        clients = [host]
        for other in human_roles[1:]:
            clients.append(service.join(host['missionId'],{'name':'Unit test '+other,'role':other}))
        for client in clients:
            if client['role'] is not None:self.command(service,client,'ready',{'ready':True})
        self.command(service,host,'start')
        return host

    def model_commander(self, provider):
        service = self.service(provider)
        modes = dict.fromkeys(ROLE_IDS,'human');modes['commander']='llm'
        host = self.mission(service,modes)
        return service,host

    def future(self, service, host, role='commander'):
        return service.missions[host['missionId']]['aiState'][role]['future']

    def completed(self, future):
        done, _ = wait([future],timeout=3)
        self.assertIn(future,done)

    def poll_agents(self, service, host):
        service.advance(host['missionId'],20)
        return service.advance(host['missionId'],1)

    def audit(self, service, host):
        folder = service.missions[host['missionId']]['directory']
        return [json.loads(line) for line in (folder/'audit.jsonl').read_text().splitlines()]

    def test_pending_model_job_cannot_block_actual_physics_and_fallback_is_labeled(self):
        provider = StubProvider()
        service,host = self.model_commander(provider)
        finished = threading.Event();results=[]
        def advance():
            try:results.append(service.advance(host['missionId'],5))
            finally:finished.set()
        worker = threading.Thread(target=advance,daemon=True);worker.start()
        self.assertTrue(provider.started(1))
        self.assertTrue(finished.wait(2),'Physics waited on the deliberately blocked provider')
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(provider.release.is_set())
        self.assertEqual(results[0]['physics']['tick'],5)
        commander = results[0]['crew'][0]
        self.assertIn('fallback',commander['agentStatus'])
        commands=[row['value'] for row in self.audit(service,host) if row['kind']=='command']
        self.assertTrue(any(row['origin']=='DETERMINISTIC_FALLBACK' and row['action']=='controls' for row in commands))

    def test_model_flight_proposal_uses_normal_audited_validation_and_private_tokens_stay_private(self):
        provider=StubProvider([{'action':'controls','payload':{'throttle':.8,'pitch':-.2}}])
        service,host=self.model_commander(provider)
        service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
        provider.release.set();self.completed(self.future(service,host))
        state=self.poll_agents(service,host)
        self.assertEqual(state['physics']['controls'],{'throttle':.8,'pitch':-.2})
        self.assertGreater(state['physics']['engine']['thrustN'],0)
        commands=[row['value'] for row in self.audit(service,host) if row['kind']=='command']
        controls=[row for row in commands if row['origin']=='LLM_PROVIDER' and row['action']=='controls']
        self.assertTrue(controls)
        self.assertTrue(all(row['role']=='commander' and row['result']=='applied' for row in controls))
        self.assertEqual([row['sequence'] for row in controls],sorted(set(row['sequence'] for row in controls)))
        public=json.dumps(state);submitted=json.dumps(provider.calls[0]['snapshot'])
        for token in service.missions[host['missionId']]['participants']:
            self.assertNotIn(token,public);self.assertNotIn(token,submitted)
        self.assertNotIn(provider.key,public);self.assertNotIn(provider.key,submitted)
        self.assertFalse(state['capabilities']['authenticAGC'])

    def test_lmp_and_collins_model_cannot_operate_flight_controls(self):
        for role in ROLE_IDS[1:]:
            provider=StubProvider([{'action':'controls','payload':{'throttle':1,'pitch':1}}])
            service=self.service(provider);modes=dict.fromkeys(ROLE_IDS,'human');modes[role]='llm'
            host=self.mission(service,modes)
            service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
            provider.release.set();self.completed(self.future(service,host,role))
            state=self.poll_agents(service,host)
            self.assertEqual(state['physics']['controls'],{'throttle':0.,'pitch':0.})
            rows=self.audit(service,host)
            self.assertTrue(any(row['kind']=='rejected' and row['value']['action']=='controls'
                and row['value']['role']==role and row['value']['status']==403 for row in rows))
            self.assertTrue(any(row['type']=='model-fallback' for row in state['events']))

    def test_model_payload_shape_bounds_and_arbitrary_state_actions_are_rejected(self):
        for proposals in (
            [{'action':'controls','payload':{'throttle':True,'pitch':0}}],
            [{'action':'controls','payload':{'throttle':2,'pitch':0}}],
            [{'action':'controls','payload':{'throttle':.5,'pitch':0,'positionM':[0,0,0]}}],
            [{'action':'set_state','payload':{'velocityMps':[0,0,0]}}],
            [{'action':'message','payload':{'text':'x'},'role':'commander'}],
            [{'action':'message','payload':{'text':'x'}}]*5):
            provider=StubProvider(proposals);service,host=self.model_commander(provider)
            service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
            provider.release.set();self.completed(self.future(service,host))
            state=self.poll_agents(service,host)
            commands=[row['value'] for row in self.audit(service,host) if row['kind']=='command']
            self.assertFalse(any(row['origin']=='LLM_PROVIDER' for row in commands))
            self.assertIn('fallback',state['crew'][0]['agentStatus'])
            self.assertNotEqual(state['physics']['spacecraft']['positionM'],[0,0,0])

    def test_provider_error_is_sanitized_and_fallback_remains_operational(self):
        provider=StubProvider(TimeoutError('UNIT_PRIVATE_PROVIDER_MARKER private transport data'))
        service,host=self.model_commander(provider)
        service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
        provider.release.set();self.completed(self.future(service,host))
        state=self.poll_agents(service,host)
        self.assertIn('fallback',state['crew'][0]['agentStatus'])
        self.assertNotIn(provider.key,json.dumps(state))
        self.assertGreater(state['physics']['tick'],5)
        self.assertTrue(any(row['type']=='model-fallback' for row in state['events']))
        self.assertNotIn(provider.key,json.dumps(self.audit(service,host)))

    def test_held_model_controls_expire_into_explicitly_labeled_fallback(self):
        provider=StubProvider([{'action':'controls','payload':{'throttle':.95,'pitch':.5}}])
        service,host=self.model_commander(provider)
        service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
        provider.release.set();self.completed(self.future(service,host))
        accepted=self.poll_agents(service,host)
        self.assertEqual(accepted['physics']['controls'],{'throttle':.95,'pitch':.5})
        self.clock.value+=CONTROL_LEASE+.1
        fallback=self.poll_agents(service,host)
        self.assertNotEqual(fallback['physics']['controls'],{'throttle':.95,'pitch':.5})
        self.assertIn('fallback',fallback['crew'][0]['agentStatus'])
        controls=[row['value'] for row in self.audit(service,host) if row['kind']=='command' and row['value']['action']=='controls']
        self.assertEqual(controls[-1]['origin'],'DETERMINISTIC_FALLBACK')

    def test_old_run_provider_response_is_ignored_after_restart(self):
        old_gate,new_gate=threading.Event(),threading.Event()
        def response(role,index,snapshot):
            return [{'action':'message','payload':{'text':'OLD_RUN_RESPONSE' if index==1 else 'NEW_RUN_RESPONSE'}}]
        provider=StubProvider(response,{1:old_gate,2:new_gate})
        service,host=self.model_commander(provider)
        service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
        old_future=self.future(service,host);old_run=service.snapshot(host['missionId'])['runId']
        restarted=self.command(service,host,'restart')['snapshot']
        self.assertNotEqual(restarted['runId'],old_run)
        self.command(service,host,'start')
        service.advance(host['missionId'],5);self.assertTrue(provider.started(2))
        new_future=self.future(service,host)
        old_gate.set();self.completed(old_future)
        pending=self.poll_agents(service,host)
        self.assertFalse(any(message['text']=='OLD_RUN_RESPONSE' for message in pending['messages']))
        new_gate.set();self.completed(new_future)
        current=self.poll_agents(service,host)
        self.assertTrue(any(message['text']=='NEW_RUN_RESPONSE' for message in current['messages']))
        self.assertFalse(any(message['text']=='OLD_RUN_RESPONSE' for message in current['messages']))

    def test_global_model_jobs_are_bounded_and_second_mission_still_advances(self):
        provider=StubProvider();service=self.service(provider)
        modes=dict.fromkeys(ROLE_IDS,'llm')
        first=self.mission(service,modes);second=self.mission(service,modes)
        service.advance(first['missionId'],5);self.assertTrue(provider.started(3))
        advanced=service.advance(second['missionId'],5)
        self.assertEqual(advanced['physics']['tick'],5)
        self.assertEqual(len(provider.calls),3)
        self.assertEqual(len([job for job in service.ai_jobs if not job.done()]),3)
        self.assertTrue(all('fallback' in role['agentStatus'] for role in advanced['crew']))

    def test_wall_request_cadence_is_bounded_and_recent_results_are_returned(self):
        provider=StubProvider();provider.release.set();service,host=self.model_commander(provider)
        service.advance(host['missionId'],5);self.assertTrue(provider.started(1))
        self.completed(self.future(service,host));self.poll_agents(service,host)
        self.clock.value+=3.9;self.poll_agents(service,host)
        self.assertEqual(len(provider.calls),1)
        self.clock.value+=.1;self.poll_agents(service,host)
        self.assertTrue(provider.started(2))
        self.assertTrue(any(row.get('accepted') for row in provider.calls[1]['results']))

    def test_all_human_model_compositions_use_exactly_three_roles_with_stub_only(self):
        for humans in (3,2,1,0):
            provider=StubProvider();provider.release.set();service=self.service(provider)
            modes={role:'human' if i<humans else 'llm' for i,role in enumerate(ROLE_IDS)}
            host=self.mission(service,modes)
            service.advance(host['missionId'],5)
            expected=3-humans
            if expected:
                self.assertTrue(provider.started(expected))
                for role,state in service.missions[host['missionId']]['aiState'].items():
                    if state.get('future'):self.completed(state['future'])
            state=self.poll_agents(service,host)
            self.assertEqual(sum(role['kind']=='human' for role in state['crew']),humans)
            self.assertEqual(sum(role['kind']=='llm' for role in state['crew']),expected)
            self.assertEqual(len(state['crew']),3)
            self.assertEqual(len(provider.calls),expected)
            self.assertFalse(state['capabilities']['authenticAGC'])
            applied=[row['value'] for row in self.audit(service,host) if row['kind']=='command' and row['value']['origin']=='LLM_PROVIDER']
            self.assertEqual(len([row for row in applied if row['action']=='message']),expected)


if __name__ == '__main__':unittest.main()
