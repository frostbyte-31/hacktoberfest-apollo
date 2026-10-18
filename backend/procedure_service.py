"""Server-owned checklist training; no original AGC or flight physics execution.

Control selections and crew reports are training evidence only.  In particular,
releasing the modeled docking attachment never creates a position, velocity,
hardware sensor observation or historical mission clock.
"""
from copy import deepcopy
import datetime
import hashlib
import json
from pathlib import Path
import secrets
import threading

from backend.control_service import ControlError


ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / 'frontend/dist/data/undocking-procedure.json'
MODE = 'INTERACTIVE PROCEDURE TRAINER'
ROLES = ('CDR', 'LMP', 'CMP')
KINDS = ('crew-report', 'select', 'momentary')
MAX_SEQUENCE = 2**31 - 1
MAX_ACTIONS = 4096


def _scalar(value):
    return ((type(value) is str and 0 < len(value) <= 160)
            or type(value) is bool
            or (type(value) is int and -MAX_SEQUENCE <= value <= MAX_SEQUENCE))


def _same(left, right):
    # Python's True == 1 must never make a different cockpit selection valid.
    return type(left) is type(right) and left == right


def validate_definition(value):
    """Validate training-contract structure, not the truth of historical sources."""
    if (not isinstance(value, dict) or type(value.get('schemaVersion')) is not int
            or value.get('schemaVersion') != 1):
        raise ValueError('Procedure definition schema is unavailable.')
    sources = value.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('Procedure sources are required.')
    source_ids = set()
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get('id'), str)
                or not source['id'] or source['id'] in source_ids
                or not isinstance(source.get('url'), str)
                or not source['url'].startswith('https://')):
            raise ValueError('Procedure source identity or HTTPS citation is invalid.')
        source_ids.add(source['id'])
    controls = value.get('initialControls', {})
    if not isinstance(controls, dict) or any(
            not isinstance(key, str) or not key or not _scalar(item)
            for key, item in controls.items()):
        raise ValueError('Initial trainer controls must contain named scalar values.')
    steps = value.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 128:
        raise ValueError('Procedure steps are required and must be bounded.')
    identities, releases = set(), 0
    for step in steps:
        if (not isinstance(step, dict) or not isinstance(step.get('id'), str)
                or not step['id'] or step['id'] in identities
                or step.get('kind') not in KINDS or step.get('role') not in ROLES
                or not isinstance(step.get('label'), str) or not step['label']
                or not isinstance(step.get('locator'), str) or not step['locator']
                or not _scalar(step.get('correctValue'))):
            raise ValueError('Procedure step identity, role, kind or expected value is invalid.')
        identities.add(step['id'])
        citations = step.get('sourceIds')
        if (not isinstance(citations, list) or not citations
                or len(set(citations)) != len(citations)
                or any(source not in source_ids for source in citations)):
            raise ValueError('Every procedure step needs valid source references.')
        if step['kind'] == 'select':
            options = step.get('options')
            if (not isinstance(step.get('controlId'), str) or not step['controlId']
                    or not isinstance(options, list) or not 2 <= len(options) <= 12
                    or any(not isinstance(option, dict)
                           or not _scalar(option.get('value'))
                           or not isinstance(option.get('label'), str)
                           or not option['label'] for option in options)
                    or not any(_same(option['value'], step['correctValue']) for option in options)):
                raise ValueError('A selector needs a named control and valid options.')
            if len({(type(option['value']), option['value']) for option in options}) != len(options):
                raise ValueError('Selector options must be unique.')
        effect = step.get('effect')
        if effect not in (None, 'release'):
            raise ValueError('Unsupported procedure effect.')
        if effect == 'release':
            releases += 1
            if step['kind'] != 'momentary' or step['role'] != 'CMP':
                raise ValueError('Modeled docking release requires a CMP momentary control.')
    if releases != 1:
        raise ValueError('Exactly one sourced mechanical release step is required.')
    return value


class ProcedureService:
    """Serialize a single local training session independently of native control."""

    def __init__(self, definition=None, definition_path=None):
        self.lock = threading.RLock()
        self.definition = None
        self.definition_sha256 = None
        self.unavailable_reason = None
        try:
            if definition is None:
                raw = Path(definition_path or DEFINITION).read_bytes()
                definition = json.loads(raw)
            else:
                raw = json.dumps(definition, sort_keys=True, separators=(',', ':'),
                                 allow_nan=False).encode()
            self.definition = deepcopy(validate_definition(definition))
            self.definition_sha256 = hashlib.sha256(raw).hexdigest()
        except (OSError, ValueError, TypeError) as error:
            self.unavailable_reason = str(error)
        self.state = self._initial(None)

    @property
    def available(self):
        return self.definition is not None

    def capabilities(self):
        return {'mode': MODE, 'crewReports': self.available,
                'modeledSelectors': self.available, 'modeledMechanicalRelease': self.available,
                'originalAgc': False, 'flightPhysics': False, 'sensorReadback': False,
                'historicalMissionClock': False, 'definitionSha256': self.definition_sha256}

    def _initial(self, identity):
        definition = self.definition or {}
        steps = definition.get('steps', [])
        return {'schemaVersion': 1, 'mode': MODE, 'classification': MODE,
                'available': self.available, 'sessionId': identity,
                'status': 'active' if identity else 'idle', 'revision': 0, 'lastSequence': -1,
                'currentStepIndex': 0, 'currentStep': deepcopy(steps[0]) if steps else None,
                'completedStepIds': [], 'completed': False,
                'controls': deepcopy(definition.get('initialControls', {})),
                'controlEvidence': {}, 'crewReports': {}, 'attachment': 'docked',
                'attachmentEvidence': 'initial-trainer-configuration',
                'chapterId': 'docked-preparation', 'unlockedChapterIds': ['docked-preparation'],
                'events': [], 'definitionSha256': self.definition_sha256,
                'capabilities': self.capabilities(),
                'message': self.unavailable_reason or 'Begin a new checklist training session.',
                'scope': 'Crew reports and modeled controls only; no original AGC execution, '
                         'observed spacecraft sensors or flight dynamics.'}

    def snapshot(self, enabled=True):
        with self.lock:
            value = deepcopy(self.state)
            if not enabled:
                value.update(available=False, message='Interactive procedures are disabled on this replay-only server.')
            return value

    def start(self):
        with self.lock:
            if not self.available:
                raise ControlError(503, 'Procedure definition unavailable: ' + str(self.unavailable_reason))
            self.state = self._initial(secrets.token_hex(16))
            self.state['message'] = 'Training session started. Complete the current crew action in checklist order.'
            return deepcopy(self.state)

    def action(self, sessionId, sequence, expectedRevision, role, action, value):
        if (type(sequence) is not int or not 0 <= sequence <= MAX_SEQUENCE
                or type(expectedRevision) is not int or not 0 <= expectedRevision <= MAX_SEQUENCE):
            raise ControlError(400, 'Sequence and expectedRevision must be bounded nonnegative integers.')
        if role not in ROLES or not isinstance(action, str) or not action or not _scalar(value):
            raise ControlError(400, 'Use a supported crew role, action identity and scalar control value.')
        with self.lock:
            if not self.available:
                raise ControlError(503, 'Procedure definition is unavailable.')
            state = self.state
            if not isinstance(sessionId, str) or not state['sessionId'] or sessionId != state['sessionId']:
                raise ControlError(409, 'Procedure session identity does not match this run.')
            if sequence <= state['lastSequence']:
                raise ControlError(409, 'Stale or repeated procedure sequence.')
            if expectedRevision != state['revision']:
                raise ControlError(409, 'Procedure revision changed; read current state before acting.')
            step = state['currentStep']
            if state['status'] != 'active' or step is None:
                raise ControlError(409, 'This checklist session is complete. Start a new session to repeat it.')
            if action != step['id']:
                raise ControlError(409, 'Complete the current checklist step before another action.')
            if role != step['role']:
                raise ControlError(403, 'This action belongs to the {} station.'.format(step['role']))
            correct = _same(value, step['correctValue'])
            if step['kind'] == 'select':
                if not any(_same(value, option['value']) for option in step['options']):
                    raise ControlError(400, 'Unsupported position for this modeled selector.')
            elif not correct:
                raise ControlError(400, 'This action does not match the current checklist instruction.')
            if len(state['events']) >= MAX_ACTIONS:
                raise ControlError(429, 'Training action limit reached. Start a new session.')
            # All rejection checks precede mutation. No emulator or physics call occurs.
            state['lastSequence'] = sequence
            state['revision'] += 1
            evidence = 'crew-report' if step['kind'] == 'crew-report' else 'trainer-control'
            observation = {'evidenceKind': evidence, 'value': deepcopy(value),
                           'revision': state['revision'], 'role': role,
                           'sourceIds': deepcopy(step['sourceIds']), 'locator': step['locator']}
            if step['kind'] == 'crew-report':
                state['crewReports'][step['id']] = observation
            elif step.get('controlId'):
                state['controls'][step['controlId']] = deepcopy(value)
                state['controlEvidence'][step['controlId']] = observation
            if correct:
                state['completedStepIds'].append(step['id'])
                if step.get('effect') == 'release':
                    state['attachment'] = 'released'
                    state['attachmentEvidence'] = 'modeled-mechanical-release'
                    state['chapterId'] = 'undocking'
                    state['unlockedChapterIds'].append('undocking')
                state['currentStepIndex'] += 1
                index = state['currentStepIndex']
                state['currentStep'] = (deepcopy(self.definition['steps'][index])
                                        if index < len(self.definition['steps']) else None)
                if state['currentStep'] is None:
                    state['status'], state['completed'] = 'complete', True
            meaning = ('Checklist action accepted; procedure advanced.' if correct
                       else 'Modeled control selected; required checklist setting not reached.')
            if step.get('effect') == 'release':
                meaning = 'Modeled docking attachment released. No physical clearance or flight state is inferred.'
            event = {'sessionId': sessionId, 'sequence': sequence, 'revision': state['revision'],
                     'action': action, 'role': role, 'kind': step['kind'],
                     'value': deepcopy(value), 'advanced': correct, 'evidenceKind': evidence,
                     'sourceIds': deepcopy(step['sourceIds']), 'locator': step['locator'],
                     'wallUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'meaning': meaning}
            state['events'].append(event)
            state['message'] = meaning
            return {'accepted': True, 'advanced': correct, 'meaning': meaning,
                    'snapshot': deepcopy(state)}
