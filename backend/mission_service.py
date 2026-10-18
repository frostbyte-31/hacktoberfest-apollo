"""One authoritative educational mission shared by exactly three crew roles.

This service never sends invented AGC output or modifies navigation memory.
Manual/fallback commands operate the explicitly separate educational plant.
Original guidance and live attitude demonstrations retain their own providers.
"""
from collections import deque
from copy import deepcopy
import datetime
import json
import math
from pathlib import Path
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.control_service import ControlError
from backend.physics_lab import PhysicsLab, SCENARIOS, TERMINAL

ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    {'id': 'commander', 'name': 'Neil Armstrong', 'role': 'Commander',
     'location': 'Lunar Module', 'responsibility': 'Educational flight controls'},
    {'id': 'lunar-module-pilot', 'name': 'Buzz Aldrin', 'role': 'Lunar Module Pilot',
     'location': 'Lunar Module', 'responsibility': 'Telemetry and learning checklist'},
    {'id': 'command-module-pilot', 'name': 'Michael Collins', 'role': 'Command Module Pilot',
     'location': 'Command Module in lunar orbit', 'responsibility': 'Communication and mission coordination'},
)
ROLE_IDS = tuple(r['id'] for r in ROLES)
CHECKLIST = ('state-vector', 'braking', 'propellant')
CONTROL_LEASE = 1.5


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ControlError(400, 'Fields must be exactly: '+', '.join(expected))


def text(value, limit, label):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ControlError(400, label+' must contain 1–'+str(limit)+' characters.')
    return value.strip()


def fallback_controls(physics):
    """Modern teaching assistance, never original Apollo guidance.

    Reads measured lab telemetry and requests only permitted engine/pitch
    actuator settings. No state assignment or future trajectory is supplied.
    """
    state = physics['spacecraft']
    altitude = max(0., state['altitudeM'])
    # A bounded slope avoids requesting an abrupt last-second slowdown.
    # This modern teaching law is independent of original Apollo guidance.
    desired_speed = -min(6., .6+.12*altitude)
    gravity = math.sqrt(sum(v*v for v in state['gravityMps2']))
    radial = max(.65, min(4., gravity+.8*(desired_speed-state['verticalSpeedMps'])))
    sideways = max(-.12, min(.12, -.35*state['horizontalVelocityMps']-.004*state['downrangeM']))
    target_pitch = math.atan2(-sideways, radial)
    angle = math.radians(state['pitchDeg'])
    omega = state['angularVelocityRadps'][1]
    pitch = max(-1., min(1., 10*(target_pitch-angle)-2*omega))
    force = state['massKg']*math.hypot(radial, sideways)
    throttle = max(0., min(1., (force-4560)/(45040-4560)))
    return {'throttle': throttle, 'pitch': pitch}


class MissionService:
    def __init__(self, assets=None, factory=PhysicsLab, output_root=None, pace=True,
                 clock=time.monotonic, ai_provider=None):
        self.assets, self.factory, self.pace, self.clock = assets, factory, pace, clock
        self.ai_provider = ai_provider
        self.ai_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='apollo-model') if ai_provider else None
        self.ai_jobs = set()
        self.output_root = Path(output_root or ROOT/'.build/final-missions')
        self.missions = {}
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.worker = None
        if pace:
            self.worker = threading.Thread(target=self._run, daemon=True, name='apollo-shared-physics')
            self.worker.start()

    def capabilities(self):
        return {'schemaVersion': 1, 'capabilities': {
            'recordedGuidance': True, 'liveAuthenticAttitude': self.assets is not None,
            'recordedPropulsion': (ROOT/'frontend/dist/data/propulsion-lab.json').is_file(),
            'physicsLab': self.assets is not None, 'multiplayer': self.assets is not None,
            'deterministicCrew': self.assets is not None,
            'llmConfigured': self.ai_provider is not None, 'authenticLanding': False},
            'crewRoles': deepcopy(ROLES),
            'scenarios': [{**deepcopy(s), 'description': 'Synthetic manual-control landing laboratory; no AGC guidance.'}
                          for s in SCENARIOS.values()],
            'networkScope': 'Shared local server; three browser clients use one authoritative mission.',
            'limitations': ['Original AGC-guided landing has not been demonstrated.',
                'Educational lab controls are independent of Luminary; deterministic assistance is not an LLM.',
                'Recorded authentic propulsion remains a fixed-attitude bounded experiment.']}

    def _mission(self, identity):
        if not isinstance(identity, str) or identity not in self.missions:
            raise ControlError(404, 'Mission not found. Create a mission or check its invite ID.')
        return self.missions[identity]

    def _participant(self, mission, token):
        if not isinstance(token, str) or token not in mission['participants']:
            raise ControlError(403, 'Join this mission before sending crew commands.')
        actor = mission['participants'][token]
        actor['seen'] = self.clock()
        return actor

    def _event(self, m, kind, message, actor='Mission control', **details):
        row = {'id': m['eventOrder'], 'timeSeconds': m['lab'].tick*.01,
               'type': kind, 'text': message, 'actor': actor, **details}
        m['eventOrder'] += 1
        m['events'].append(row)
        self._write(m, 'event', row)

    def _write(self, m, kind, value):
        with (m['directory']/'audit.jsonl').open('a') as stream:
            stream.write(json.dumps({'kind': kind, 'runId': m['runId'], 'value': value},
                                    separators=(',', ':'), allow_nan=False)+'\n')

    def _actor(self, name, role, kind='human', host=False):
        return {'name': name, 'role': role, 'kind': kind, 'host': host,
                'lastSequence': -1, 'seen': self.clock(), 'ready': kind != 'human'}

    def create(self, value):
        fields(value, ('scenarioId', 'name', 'role', 'crewModes'))
        name = text(value['name'], 32, 'Crew name')
        if not isinstance(value['scenarioId'], str) or value['scenarioId'] not in SCENARIOS or value['role'] not in (*ROLE_IDS, None):
            raise ControlError(400, 'Choose an available scenario and crew role.')
        fields(value['crewModes'], ROLE_IDS)
        modes = value['crewModes']
        if any(type(mode) is not str or mode not in ('human', 'fallback', 'llm') for mode in modes.values()):
            raise ControlError(400, 'Crew modes are human, fallback or llm.')
        if value['role'] and modes[value['role']] != 'human':
            raise ControlError(400, 'Your selected seat must be a human seat.')
        if 'llm' in modes.values() and self.ai_provider is None:
            raise ControlError(409, 'No server-side model provider is configured. Choose a labeled fallback.')
        if self.assets is None:
            raise ControlError(503, 'Verified physical dependencies are unavailable; recorded demonstrations remain available.')
        with self.lock:
            if len(self.missions) >= 8:
                raise ControlError(429, 'This local demo supports eight missions; restart the server to clear old sessions.')
            identity, token = secrets.token_hex(8), secrets.token_urlsafe(32)
            folder = self.output_root/identity
            folder.mkdir(parents=True, exist_ok=False)
            lab = self.factory(self.assets, scenario=value['scenarioId'])
            m = {'id': identity, 'runId': secrets.token_hex(8), 'scenario': value['scenarioId'],
                'title': SCENARIOS[value['scenarioId']]['title'], 'lab': lab, 'directory': folder,
                'status': 'lobby', 'revision': 0, 'participants': {}, 'seats': {},
                'events': deque(maxlen=200), 'messages': deque(maxlen=100), 'eventOrder': 0,
                'checklist': {}, 'assistance': False, 'trajectory': deque(maxlen=2000),
                'lastControlsAt': None, 'leaseExpired': False, 'lastAgentTick': -100,
                'debrief': None, 'agentAnnouncements': set(), 'fault': None, 'aiState': {}}
            m['participants'][token] = self._actor(name, value['role'], host=True)
            if value['role']:
                m['seats'][value['role']] = token
            for role, mode in modes.items():
                if mode != 'human':
                    secret = secrets.token_urlsafe(32)
                    m['participants'][secret] = self._actor(
                        'Deterministic fallback' if mode == 'fallback' else 'Configured model', role, mode)
                    m['seats'][role] = secret
            assist_token = secrets.token_urlsafe(32)
            m['participants'][assist_token] = self._actor('Deterministic teaching assistance', 'commander', 'assist')
            m['assistToken'] = assist_token
            self.missions[identity] = m
            self._event(m, 'created', 'Educational physics lab created. This mode has no AGC guidance.')
            self._record_frame(m)
            return {'missionId': identity, 'participantToken': token, 'role': value['role'],
                    'snapshot': self._snapshot(m, token)}

    def join(self, identity, value):
        fields(value, ('name', 'role'))
        name = text(value['name'], 32, 'Crew name')
        if value['role'] not in ROLE_IDS:
            raise ControlError(400, 'Choose one of the three crew positions.')
        with self.lock:
            m = self._mission(identity)
            if value['role'] in m['seats']:
                raise ControlError(409, 'That crew position is already occupied.')
            if m['status'] != 'lobby':
                raise ControlError(409, 'Join the crew before mission start.')
            token = secrets.token_urlsafe(32)
            m['participants'][token] = self._actor(name, value['role'])
            m['seats'][value['role']] = token
            m['revision'] += 1
            self._event(m, 'crew', name+' joined '+value['role']+'.', name)
            return {'missionId': identity, 'participantToken': token, 'role': value['role'],
                    'snapshot': self._snapshot(m, token)}

    def snapshot(self, identity, token=None):
        with self.lock:
            m = self._mission(identity)
            if token is not None:
                self._participant(m, token)
            return self._snapshot(m, token)

    def _snapshot(self, m, token=None):
        you = m['participants'].get(token)
        crew = []
        for definition in ROLES:
            participant = m['participants'].get(m['seats'].get(definition['id']))
            crew.append({**definition, 'occupied': participant is not None,
                'displayName': participant['name'] if participant else 'Open human seat',
                'kind': participant['kind'] if participant else 'human',
                'ready': participant['ready'] if participant else False,
                'connected': bool(participant and (participant['kind'] != 'human' or self.clock()-participant['seen'] < 5)),
                'agentStatus': m['aiState'].get(definition['id'], {}).get('status',
                    'deterministic fallback' if participant and participant['kind'] == 'fallback' else None)})
        return deepcopy({'schemaVersion': 1, 'id': m['id'], 'runId': m['runId'],
            'title': m['title'], 'mode': 'EDUCATIONAL_PHYSICS_LAB', 'status': m['status'],
            'revision': m['revision'], 'physics': m['lab'].snapshot(), 'crew': crew,
            'events': list(m['events']), 'messages': list(m['messages']),
            'checklist': m['checklist'], 'assistance': m['assistance'],
            'trajectory': list(m['trajectory']), 'debrief': m['debrief'], 'fault': m['fault'],
            'capabilities': {'canControlThrust': True, 'canControlPitch': True,
                             'hasAGCNavigationFeedback': False, 'authenticAGC': False},
            'you': {k: you[k] for k in ('name', 'role', 'host', 'lastSequence')} if you else None})

    def command(self, identity, token, value, origin='human'):
        with self.lock:
            m = self._mission(identity)
            actor = self._participant(m, token)
            try:
                fields(value, ('sequence', 'runId', 'action', 'payload'))
                sequence, action, payload = value['sequence'], value['action'], value['payload']
                if type(sequence) is not int or not 0 <= sequence < 2**31 or sequence <= actor['lastSequence']:
                    raise ControlError(409, 'Stale or invalid crew command sequence; refresh shared state.')
                if value['runId'] != m['runId']:
                    raise ControlError(409, 'This command belongs to an earlier mission run.')
                if not isinstance(action, str):
                    raise ControlError(400, 'Action must be a supported command name.')
                self._apply(m, actor, action, payload, origin)
                actor['lastSequence'] = sequence
                m['revision'] += 1
                self._write(m, 'command', {'order': m['revision'], 'sequence': sequence,
                    'timeSeconds': m['lab'].tick*.01, 'role': actor['role'], 'name': actor['name'],
                    'origin': origin, 'action': action, 'payload': payload, 'result': 'applied'})
                return {'accepted': True, 'sequence': sequence, 'revision': m['revision'],
                        'snapshot': self._snapshot(m, token)}
            except ControlError as error:
                self._write(m, 'rejected', {'timeSeconds': m['lab'].tick*.01,
                    'role': actor['role'], 'action': str(value.get('action', 'invalid'))[:80] if isinstance(value, dict) else 'invalid',
                    'reason': str(error), 'status': error.status})
                raise

    def _ready(self, m):
        return all(role in m['seats'] and m['participants'][m['seats'][role]]['ready'] for role in ROLE_IDS)

    def _apply(self, m, actor, action, payload, origin):
        commander = actor['role'] == 'commander'
        lifecycle = commander or actor['host']
        if action == 'ready':
            fields(payload, ('ready',))
            if actor['role'] is None or type(payload['ready']) is not bool:
                raise ControlError(400, 'A seated crew member must provide a boolean ready state.')
            actor['ready'] = payload['ready']
        elif action in ('start', 'pause', 'resume', 'restart'):
            fields(payload, ())
            if not lifecycle:
                raise ControlError(403, 'Only the commander or mission host controls mission lifecycle.')
            if action == 'start' and (m['status'] != 'lobby' or not self._ready(m)):
                raise ControlError(409, 'All three crew positions must be occupied and ready before start.')
            if action == 'pause' and m['status'] != 'running':
                raise ControlError(409, 'Only a running mission can pause.')
            if action == 'resume' and m['status'] != 'paused':
                raise ControlError(409, 'Only a paused mission can resume.')
            if action == 'restart':
                old = m['lab']
                replacement = self.factory(self.assets, scenario=m['scenario'])
                old.close()
                m.update(lab=replacement, runId=secrets.token_hex(8), status='lobby',
                         debrief=None, lastControlsAt=None, assistance=False, leaseExpired=False,
                         lastAgentTick=-100, checklist={}, fault=None)
                m['trajectory'].clear()
                m['events'].clear()
                m['messages'].clear()
                m['agentAnnouncements'].clear()
                for state in m['aiState'].values():
                    if state.get('future'):
                        state['future'].cancel()
                m['aiState'].clear()
                self._record_frame(m)
            else:
                m['status'] = 'paused' if action == 'pause' else 'running'
            self._event(m, action, 'Mission '+action+'.', actor['name'])
        elif action in ('controls', 'assist'):
            if not commander:
                raise ControlError(403, 'Only the commander can operate flight actuators.')
            if action == 'assist':
                fields(payload, ('enabled',))
                if type(payload['enabled']) is not bool:
                    raise ControlError(400, 'Assistance requires a boolean enabled state.')
                m['assistance'] = payload['enabled']
                m['lastAgentTick'] = -100
                self._event(m, 'assistance', 'Modern deterministic teaching assistance '+('enabled' if payload['enabled'] else 'disabled')+'.', actor['name'])
            else:
                fields(payload, ('throttle', 'pitch'))
                if m['status'] != 'running':
                    raise ControlError(409, 'Start or resume the lab before controlling its actuators.')
                if m['assistance'] and actor['kind'] != 'assist':
                    raise ControlError(409, 'Disable teaching assistance before taking manual control.')
                try:
                    m['lab'].command(payload['throttle'], payload['pitch'])
                except ValueError as error:
                    raise ControlError(400, str(error))
                m['lastControlsAt'], m['leaseExpired'] = self.clock(), False
        elif action == 'message':
            fields(payload, ('text',))
            message = text(payload['text'], 300, 'Crew message')
            row = {'id': m['eventOrder'], 'timeSeconds': m['lab'].tick*.01,
                   'role': actor['role'], 'name': actor['name'], 'text': message,
                   'source': origin}
            m['messages'].append(row)
            self._event(m, 'message', message, actor['name'])
        elif action == 'checklist':
            fields(payload, ('item',))
            if actor['role'] != 'lunar-module-pilot':
                raise ControlError(403, 'The Lunar Module Pilot owns the educational checklist.')
            if payload['item'] not in CHECKLIST:
                raise ControlError(400, 'Unknown educational checklist item.')
            m['checklist'][payload['item']] = {'done': True, 'by': actor['name'], 'timeSeconds': m['lab'].tick*.01}
            self._event(m, 'checklist', 'Crew marked educational check: '+payload['item']+'.', actor['name'])
        else:
            raise ControlError(400, 'Unsupported mission command.')

    def _internal_command(self, m, token, action, payload, origin='DETERMINISTIC_FALLBACK'):
        actor = m['participants'][token]
        return self.command(m['id'], token, {'sequence': actor['lastSequence']+1,
            'runId': m['runId'], 'action': action, 'payload': payload},
            origin=origin)

    def _model_tick(self, m):
        """Nonblocking proposals; ordinary role/epoch/sequence validation applies."""
        if self.ai_provider is None:
            return
        now = self.clock()
        self.ai_jobs = {job for job in self.ai_jobs if not job.done()}
        active = len(self.ai_jobs)
        for role, token in m['seats'].items():
            if m['participants'][token]['kind'] != 'llm':
                continue
            state = m['aiState'].setdefault(role, {'status': 'deterministic fallback while model is pending',
                'lastRequest': -1e9, 'results': [], 'heldControls': None, 'validAt': -1e9})
            if state['heldControls'] and now-state['validAt'] > CONTROL_LEASE:
                state['heldControls'] = None
                state['status'] = 'model control lease expired; deterministic fallback active'
            future = state.get('future')
            if future and future.done():
                state['future'] = None
                try:
                    proposals = future.result()
                    if state['requestedRunId'] != m['runId']:
                        raise ValueError('Stale model response belongs to an earlier run')
                    if not isinstance(proposals, list) or len(proposals) > 4:
                        raise ValueError('Model command list is outside the bounded contract')
                    for proposal in proposals:
                        fields(proposal, ('action', 'payload'))
                        if proposal['action'] not in ('controls', 'message', 'checklist'):
                            raise ControlError(403, 'Models may use only role-specific crew tools.')
                        result = self._internal_command(m, token, proposal['action'], proposal['payload'], origin='LLM_PROVIDER')
                        if proposal['action'] == 'controls':
                            state['heldControls'], state['validAt'] = deepcopy(proposal['payload']), now
                        state['results'].append({'action': proposal['action'], 'accepted': result['accepted']})
                    state['status'] = 'configured model response applied' if proposals else 'model made no tool call; deterministic fallback'
                except Exception:
                    # Never include raw provider exceptions: an upstream error
                    # body may echo private configuration. The audit is explicit.
                    state['status'], state['heldControls'] = 'provider error; deterministic fallback', None
                    state['results'].append({'accepted': False, 'reason': 'Provider error or rejected role command'})
                    self._event(m, 'model-fallback', 'Configured model did not return a valid permitted command; deterministic fallback is active.', role)
                state['results'] = state['results'][-6:]
            if not state.get('future') and now-state['lastRequest'] >= 4 and active < 3:
                state['lastRequest'], state['requestedRunId'] = now, m['runId']
                state['future'] = self.ai_pool.submit(self.ai_provider.decide, role,
                        self._snapshot(m), deepcopy(state['results']))
                self.ai_jobs.add(state['future'])
                active += 1
                if not state['heldControls']:
                    state['status'] = 'model pending; deterministic fallback active'

    def _agents(self, m):
        tick = m['lab'].tick
        if tick-m['lastAgentTick'] < 20:
            return
        m['lastAgentTick'] = tick
        self._model_tick(m)
        state = m['lab'].snapshot()
        commander = m['seats'].get('commander')
        pilot = m['seats'].get('lunar-module-pilot')
        collins = m['seats'].get('command-module-pilot')
        if commander and m['participants'][commander]['kind'] in ('fallback', 'llm'):
            model = m['aiState'].get('commander', {})
            if model.get('heldControls') and self.clock()-model.get('validAt', -1e9) <= CONTROL_LEASE:
                self._internal_command(m, commander, 'controls', model['heldControls'], origin='LLM_PROVIDER')
            else:
                self._internal_command(m, commander, 'controls', fallback_controls(state))
        elif m['assistance']:
            self._internal_command(m, m['assistToken'], 'controls', fallback_controls(state))
        if pilot and m['participants'][pilot]['kind'] in ('fallback', 'llm'):
            for item in CHECKLIST:
                if item not in m['checklist']:
                    self._internal_command(m, pilot, 'checklist', {'item': item})
            key = 'pilot-introduction'
            if key not in m['agentAnnouncements']:
                self._internal_command(m, pilot, 'message', {'text': 'State vector and propellant are visible. This is a manual physics laboratory, independent of Luminary.'})
                m['agentAnnouncements'].add(key)
        if collins and m['participants'][collins]['kind'] in ('fallback', 'llm'):
            altitude = state['spacecraft']['altitudeM']
            marker = next((h for h in (20, 50, 100, 1000) if altitude <= h), 1000)
            key = 'collins-'+str(marker)
            if key not in m['agentAnnouncements']:
                self._internal_command(m, collins, 'message', {'text': 'Orbital support: altitude {:.1f} m, vertical velocity {:.1f} m/s. Thrust changes acceleration before it reverses motion.'.format(altitude, state['spacecraft']['verticalSpeedMps'])})
                m['agentAnnouncements'].add(key)

    def _record_frame(self, m):
        frame = m['lab'].snapshot()
        state = frame['spacecraft']
        m['trajectory'].append({'t': frame['simTimeSeconds'], 'altitudeM': state['altitudeM'],
            'downrangeM': state['downrangeM'], 'positionM': state['positionM']})
        self._write(m, 'physics', frame)

    def advance(self, identity, ticks=5):
        """Server/test owner only; there is no HTTP route for arbitrary stepping."""
        with self.lock:
            m = self._mission(identity)
            if m['status'] != 'running':
                return self._snapshot(m)
            self._agents(m)
            if m['lastControlsAt'] is not None and self.clock()-m['lastControlsAt'] > CONTROL_LEASE and not m['leaseExpired']:
                m['lab'].command(0, 0)
                m['leaseExpired'] = True
                self._event(m, 'control-lease', 'Flight input lease expired; engine and pitch commands released to zero.')
            m['lab'].step(ticks)
            m['revision'] += 1
            if m['lab'].tick % 10 == 0 or m['lab'].status in TERMINAL:
                self._record_frame(m)
            if m['lab'].status in TERMINAL:
                m['status'], m['debrief'] = 'completed', m['lab'].debrief()
                self._event(m, 'completed', 'Physical outcome: '+m['lab'].status+'.')
                (m['directory']/('debrief-'+m['runId']+'.json')).write_text(json.dumps(m['debrief'], indent=2)+'\n')
            return self._snapshot(m)

    def _run(self):
        deadline = self.clock()
        while not self.closed.is_set():
            with self.lock:
                identities = list(self.missions)
            for identity in identities:
                try:
                    self.advance(identity)
                except Exception as error:
                    with self.lock:
                        m = self.missions[identity]
                        m.update(status='fault', fault=str(error))
                        self._event(m, 'fault', 'Physical simulation stopped: '+str(error))
            deadline += .05
            now = self.clock()
            if deadline < now-.1:
                deadline = now
            self.closed.wait(max(0, deadline-now))

    def close(self):
        self.closed.set()
        if self.worker:
            self.worker.join(timeout=5)
        with self.lock:
            for m in self.missions.values():
                m['lab'].close()
        if self.ai_pool:
            self.ai_pool.shutdown(wait=True)
