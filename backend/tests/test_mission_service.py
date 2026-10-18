"""Shared authority, permissions and real Tcl-backed educational crew flights.

Deterministic fallback participation is explicitly not original AGC guidance
or an LLM. Tests issue only the public mission command validation interface.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

from backend.control_service import ControlError
from backend.mission_service import CHECKLIST, CONTROL_LEASE, MissionService, ROLE_IDS

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self):self.value=100.0
    def __call__(self):return self.value


class MissionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(os.environ.get('APOLLO_TEST_ASSETS',str(ROOT/'.build/final-demo-assets.json')))
        cls.assets=json.loads(path.read_text())

    def setUp(self):
        output=ROOT/'.build/mission-service-tests'
        output.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=output)
        self.clock=Clock()
        self.service=MissionService(assets=self.assets,pace=False,clock=self.clock,
                                    output_root=Path(self.temp.name)/'missions')

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def create(self,modes=None,role='commander'):
        return self.service.create({'scenarioId':'training','name':'Test host','role':role,
                                    'crewModes':modes or dict.fromkeys(ROLE_IDS,'human')})

    def command(self,client,action,payload=None,**overrides):
        state=self.service.snapshot(client['missionId'],client['participantToken'])
        value={'sequence':state['you']['lastSequence']+1,'runId':state['runId'],
               'action':action,'payload':payload or {}}
        value.update(overrides)
        return self.service.command(client['missionId'],client['participantToken'],value)

    def crew(self,modes=None):
        host=self.create(modes)
        clients=[host]
        for role in ROLE_IDS[1:]:
            if not modes or modes[role]=='human':
                clients.append(self.service.join(host['missionId'],{'name':'Human '+role,'role':role}))
        for client in clients:self.command(client,'ready',{'ready':True})
        return clients

    def error(self,status,call,*args,**kwargs):
        with self.assertRaises(ControlError) as caught:call(*args,**kwargs)
        self.assertEqual(caught.exception.status,status)

    def test_exactly_three_roles_and_collins_remains_orbital_support(self):
        host=self.create()
        snapshot=host['snapshot']
        self.assertEqual(tuple(r['id'] for r in snapshot['crew']),ROLE_IDS)
        self.assertEqual(len(snapshot['crew']),3)
        self.assertIn('lunar orbit',snapshot['crew'][2]['location'])
        self.error(400,self.service.join,host['missionId'],{'name':'Fourth','role':'mission-control'})
        self.error(409,self.service.join,host['missionId'],{'name':'Duplicate','role':'commander'})
        caps=self.service.capabilities()['capabilities']
        self.assertTrue(caps['physicsLab']);self.assertTrue(caps['multiplayer'])
        self.assertFalse(caps['authenticLanding']);self.assertFalse(caps['llmConfigured'])

    def test_all_three_occupied_ready_seats_required_before_start(self):
        host=self.create()
        self.error(409,self.command,host,'start')
        self.command(host,'ready',{'ready':True})
        self.error(409,self.command,host,'start')
        pilot=self.service.join(host['missionId'],{'name':'Pilot','role':ROLE_IDS[1]})
        collins=self.service.join(host['missionId'],{'name':'Orbital support','role':ROLE_IDS[2]})
        self.command(pilot,'ready',{'ready':True})
        self.error(409,self.command,host,'start')
        self.command(collins,'ready',{'ready':True})
        self.assertEqual(self.command(host,'start')['snapshot']['status'],'running')

    def test_role_permissions_prevent_collins_and_lmp_from_flight_control(self):
        commander,pilot,collins=self.crew()
        self.command(commander,'start')
        for other in (pilot,collins):
            self.error(403,self.command,other,'controls',{'throttle':.5,'pitch':0})
            self.error(403,self.command,other,'assist',{'enabled':True})
            self.error(403,self.command,other,'pause')
        for other in (commander,collins):
            self.error(403,self.command,other,'checklist',{'item':CHECKLIST[0]})
        self.command(pilot,'checklist',{'item':CHECKLIST[0]})
        self.command(collins,'message',{'text':'Orbital support telemetry received.'})
        state=self.command(commander,'controls',{'throttle':.4,'pitch':-.1})['snapshot']
        self.assertTrue(state['checklist'][CHECKLIST[0]]['done'])
        self.assertEqual(state['messages'][-1]['role'],ROLE_IDS[2])
        self.assertFalse(state['capabilities']['authenticAGC'])

    def test_shared_three_client_views_are_copies_of_one_authoritative_state(self):
        clients=self.crew();host=clients[0]
        self.command(host,'start');self.command(host,'controls',{'throttle':.4,'pitch':.2})
        self.service.advance(host['missionId'],5)
        views=[self.service.snapshot(c['missionId'],c['participantToken']) for c in clients]
        for view in views[1:]:
            for field in ('runId','revision','physics','trajectory','crew'):
                self.assertEqual(view[field],views[0][field])
        views[0]['physics']['spacecraft']['positionM'][0]=0
        self.assertNotEqual(self.service.snapshot(host['missionId'])['physics']['spacecraft']['positionM'][0],0)

    def test_monotonic_sequences_and_restart_reject_stale_run_commands(self):
        host=self.crew()[0];self.command(host,'start')
        current=self.service.snapshot(host['missionId'],host['participantToken'])
        old_run=current['runId'];old_sequence=current['you']['lastSequence']
        self.error(409,self.command,host,'message',{'text':'stale'},sequence=old_sequence)
        restarted=self.command(host,'restart')['snapshot']
        self.assertEqual(restarted['status'],'lobby')
        self.assertNotEqual(restarted['runId'],old_run)
        self.assertEqual(restarted['physics']['tick'],0)
        sequence=restarted['you']['lastSequence']+1
        self.error(409,self.command,host,'message',{'text':'old run'},runId=old_run,sequence=sequence)
        self.assertEqual(self.command(host,'message',{'text':'new run'},sequence=sequence)['accepted'],True)
        self.error(409,self.command,host,'controls',{'throttle':.5,'pitch':0})

    def test_pause_freezes_simulation_and_resume_reuses_authoritative_lab(self):
        host=self.crew()[0];self.command(host,'start')
        before=self.service.advance(host['missionId'],10)['physics']
        self.command(host,'pause')
        self.assertEqual(self.service.advance(host['missionId'],100)['physics'],before)
        self.error(409,self.command,host,'controls',{'throttle':.5,'pitch':0})
        self.command(host,'resume')
        after=self.service.advance(host['missionId'],5)['physics']
        self.assertEqual(after['tick'],before['tick']+5)

    def test_control_lease_releases_engine_and_pitch_once(self):
        host=self.crew(dict.fromkeys(ROLE_IDS,'fallback')|{'commander':'human'})[0]
        self.command(host,'start');self.command(host,'controls',{'throttle':1,'pitch':1})
        active=self.service.advance(host['missionId'],5)
        self.assertGreater(active['physics']['engine']['thrustN'],0)
        self.clock.value+=CONTROL_LEASE+.01
        released=self.service.advance(host['missionId'],5)
        self.assertEqual(released['physics']['controls'],{'throttle':0,'pitch':0})
        self.assertEqual(released['physics']['engine']['thrustN'],0)
        again=self.service.advance(host['missionId'],5)
        self.assertEqual(sum(e['type']=='control-lease' for e in again['events']),1)

    def test_finite_controls_payload_shapes_and_ready_boolean_are_validated(self):
        host=self.crew()[0];self.command(host,'start')
        initial=self.service.snapshot(host['missionId'])['physics']
        for throttle,pitch in ((math.nan,0),(math.inf,0),(-.1,0),(1.1,0),(True,0),(0,False),(0,-1.1),(0,1.1)):
            self.error(400,self.command,host,'controls',{'throttle':throttle,'pitch':pitch})
            self.assertEqual(self.service.snapshot(host['missionId'])['physics'],initial)
        self.error(400,self.command,host,'controls',{'throttle':.5})
        self.error(400,self.command,host,'controls',{'throttle':.5,'pitch':0,'position':0})
        self.error(400,self.command,host,'ready',{'ready':'yes'})
        self.error(400,self.command,host,'invented')
        self.error(409,self.command,host,'message',{'text':'bad sequence'},sequence=True)

    def test_create_rejects_unhashable_scenario_and_invalid_compositions(self):
        value={'scenarioId':'training','name':'Host','role':'commander','crewModes':dict.fromkeys(ROLE_IDS,'human')}
        for invalid in ([],{},None,12):
            self.error(400,self.service.create,{**value,'scenarioId':invalid})
        self.error(400,self.service.create,{**value,'crewModes':{'commander':'human'}})
        self.error(400,self.service.create,{**value,'crewModes':dict.fromkeys(ROLE_IDS,'robot')})
        self.error(400,self.service.create,{**value,'crewModes':dict.fromkeys(ROLE_IDS,'fallback')})
        self.error(409,self.service.create,{**value,'crewModes':dict.fromkeys(ROLE_IDS,'llm'),'role':None})

    def test_all_required_human_fallback_compositions_use_three_seats(self):
        for humans in (3,2,1,0):
            modes={role:'human' if i<humans else 'fallback' for i,role in enumerate(ROLE_IDS)}
            if humans:
                clients=self.crew(modes);host=clients[0]
            else:
                host=self.create(modes,role=None)
            state=self.command(host,'start')['snapshot']
            self.assertEqual(sum(r['kind']=='human' for r in state['crew']),humans)
            self.assertEqual(sum(r['kind']=='fallback' for r in state['crew']),3-humans)
            self.assertEqual(len(state['crew']),3)
            advanced=self.service.advance(host['missionId'],5)
            self.assertEqual(advanced['physics']['tick'],5)
            self.assertFalse(advanced['capabilities']['authenticAGC'])

    def test_assistance_is_labeled_and_manual_override_requires_disabling(self):
        host=self.crew(dict.fromkeys(ROLE_IDS,'fallback')|{'commander':'human'})[0]
        self.command(host,'start');self.command(host,'assist',{'enabled':True})
        state=self.service.advance(host['missionId'],5)
        self.assertTrue(state['assistance'])
        self.assertGreater(state['physics']['engine']['thrustN'],0)
        self.error(409,self.command,host,'controls',{'throttle':0,'pitch':0})
        rows=[json.loads(line) for line in (self.service.missions[host['missionId']]['directory']/'audit.jsonl').read_text().splitlines()]
        self.assertTrue(any(r['kind']=='command' and r['value']['action']=='controls'
                            and r['value']['role']=='commander'
                            and r['value']['origin']=='DETERMINISTIC_FALLBACK' for r in rows))
        self.assertTrue(any(r['kind']=='rejected' and r['value']['action']=='controls'
                            and r['value']['status']==409 for r in rows))
        self.command(host,'assist',{'enabled':False})
        self.command(host,'controls',{'throttle':0,'pitch':0})
        self.assertEqual(self.service.advance(host['missionId'],5)['physics']['engine']['thrustN'],0)

    def test_accepted_and_rejected_commands_have_distinct_audit_records(self):
        commander,pilot,collins=self.crew();self.command(commander,'start')
        self.error(403,self.command,collins,'controls',{'throttle':1,'pitch':0})
        self.command(pilot,'checklist',{'item':'braking'})
        self.command(commander,'controls',{'throttle':.5,'pitch':0})
        directory=self.service.missions[commander['missionId']]['directory']
        rows=[json.loads(line) for line in (directory/'audit.jsonl').read_text().splitlines()]
        applied=[r['value'] for r in rows if r['kind']=='command']
        rejected=[r['value'] for r in rows if r['kind']=='rejected']
        self.assertTrue(any(r['action']=='controls' and r['role']=='commander' and r['origin']=='human' for r in applied))
        self.assertTrue(any(r['action']=='controls' and r['role']==ROLE_IDS[2] and r['status']==403 for r in rejected))
        self.assertEqual([r['order'] for r in applied],sorted(set(r['order'] for r in applied)))

    def test_all_fallback_real_physics_flight_is_deterministic_and_not_an_llm(self):
        results=[]
        command_runs=[]
        for repetition in range(2):
            host=self.create(dict.fromkeys(ROLE_IDS,'fallback'),role=None)
            self.command(host,'start')
            for _ in range(4000):
                state=self.service.advance(host['missionId'],5)
                if state['status']!='running':break
            print(json.dumps({'experiment':'actual three-fallback educational flight','repetition':repetition,
                'classification':'DETERMINISTIC_FALLBACK; not LLM or original AGC control',
                'outcome':state['physics']['outcome'],'simTimeSeconds':state['physics']['simTimeSeconds'],
                'physics_sha256':hashlib.sha256(json.dumps(state['physics'],sort_keys=True).encode()).hexdigest()},allow_nan=False))
            self.assertEqual(state['status'],'completed')
            self.assertIsNotNone(state['debrief'])
            self.assertEqual(state['physics']['status'],'landed')
            self.assertTrue(state['debrief']['outcome']['success'])
            self.assertEqual(set(state['checklist']),set(CHECKLIST))
            self.assertTrue(any(m['role']==ROLE_IDS[2] and m['source']=='DETERMINISTIC_FALLBACK' for m in state['messages']))
            self.assertTrue(all(r['kind']=='fallback' for r in state['crew']))
            result={'physics':state['physics'],'debrief':state['debrief'],'checklist':state['checklist']}
            results.append(deepcopy(result))
            directory=self.service.missions[host['missionId']]['directory']
            raw=(directory/'audit.jsonl').read_text()
            command_lines=[line for line in raw.splitlines(keepends=True) if json.loads(line)['kind']=='command']
            commands=[json.loads(line)['value'] for line in command_lines]
            command_runs.append(commands)
            evidence=os.environ.get('APOLLO_MISSION_TEST_EVIDENCE')
            if evidence:
                destination=Path(evidence)
                destination.mkdir(parents=True,exist_ok=True)
                with (destination/('fallback-'+str(repetition)+'-audit.jsonl')).open('x') as stream:stream.write(raw)
                with (destination/('fallback-'+str(repetition)+'-commands.jsonl')).open('x') as stream:stream.writelines(command_lines)
            print(json.dumps({'experiment':'actual validated fallback command schedule',
                'repetition':repetition,'commands':len(commands),
                'command_values_sha256':hashlib.sha256(json.dumps(commands,sort_keys=True).encode()).hexdigest(),
                'comparison_scope':'Compare actual audited command values; retain unique run IDs in unmodified raw audit copies.'}))
        self.assertEqual(results[0],results[1])
        self.assertEqual(command_runs[0],command_runs[1])


if __name__=='__main__':unittest.main(verbosity=2)
