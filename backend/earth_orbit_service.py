"""Live original CMC console; no spacecraft physics or flight-completion authority.

One owner thread runs a separate unchanged Comanche/yaAGC process. HTTP threads
only submit bounded physical-key requests and read published observations.
"""
from concurrent.futures import Future, TimeoutError
from copy import deepcopy
from pathlib import Path
from queue import Queue, Empty
import json
import secrets
import threading
import time

from backend.control_service import ControlError

ROOT = Path(__file__).resolve().parents[1]
MODE = 'LIVE ORIGINAL CMC EXECUTION'
KEYS = tuple([str(i) for i in range(10)] + ['+', '-', 'VERB', 'NOUN', 'CLR', 'PRO', 'KEY REL', 'ENTR', 'RSET'])
SCOPE = ('Cold-start Columbia CMC control bench in the Earth-orbit chapter. Original Comanche 055 '
         'processes your DSKY keys. No historical orbital state, calibrated IMU, known REFSMMAT, '
         'optical star measurements, spacecraft motion or TLI execution is supplied.')


def task_definition():
    return [
        {'id': 'display-test', 'title': 'Learn the original DSKY',
         'description': 'Familiarization: press VERB 3 5 ENTR. Observe the original all-8 digit test. V35 is a real computer test, not a claimed flown Earth-orbit checklist action.'},
        {'id': 'p00', 'title': 'Establish the idle program',
         'description': 'Wait for the original display test to finish (about five CPU seconds). Press RSET, then press VERB 3 7 ENTR 0 0 ENTR. Observe program 00.'},
        {'id': 'clock', 'title': 'Read the computer clock',
         'description': 'Press VERB 1 6 NOUN 3 6 ENTR. Inspect the original clock display. This is this cold-start computer clock, not historical Apollo 11 GET.'},
        {'id': 'p52-gate', 'title': 'Request the historical alignment program',
         'description': 'Press VERB 3 7 ENTR 5 2 ENTR. Collins used P52 before TLI. This cold-start bench has no operating IMU. Then press VERB 0 5 NOUN 0 9 ENTR and find 00210 in the three original alarm registers. Other cold-start alarms remain visible; no alignment is inferred.'},
        {'id': 'recover', 'title': 'Recover and verify P00',
         'description': 'Acknowledge with RSET, then press VERB 3 7 ENTR 0 0 ENTR. Verify program 00. The diagnostic ends here; real alignment and TLI remain unavailable.'},
    ]


class EarthOrbitService:
    def __init__(self, factory=None, discovery=None, output_root=None, pace=True, idle_timeout=600, enabled=True):
        self.factory, self.discovery = factory, discovery
        self.output_root = Path(output_root or ROOT/'.build/earth-orbit/sessions')
        self.pace, self.idle_timeout = pace, idle_timeout
        self.enabled = enabled
        self.lock = threading.RLock()
        self.queue = Queue(maxsize=16)
        self.closed = False
        self.engine = None
        self.thread = None
        self.last_activity = time.monotonic()
        self.marks = []
        self.history = []
        self.clock_candidate = None
        self.log = None
        self.state = {'schemaVersion': 1, 'mode': MODE, 'available': False, 'status': 'idle',
                      'sessionId': None, 'revision': 0, 'nextSequence': 0,
                      'computer': None, 'inputs': [], 'error': None}

    def capabilities(self):
        if not self.enabled:
            return {'available': False, 'mode': MODE, 'software': 'Comanche055', 'scope': SCOPE,
                    'supportedKeys': [], 'unavailableReason': 'Live CMC execution is disabled in recorded-only mode.'}
        if self.discovery:
            data = self.discovery()
        else:
            try:
                from backend.cmc_native import availability
                data = availability()
            except Exception as error:
                data = {'available': False, 'unavailableReason': str(error)}
        return {**data, 'mode': MODE, 'software': 'Comanche055', 'scope': SCOPE,
                'supportedKeys': list(KEYS) if data.get('available') is True else [],
                'flightExecuted': False, 'alignmentCompleted': False}

    def _task(self):
        steps = task_definition()
        for index, item in enumerate(steps):
            item.update(complete=index < len(self.marks), active=index == len(self.marks))
        complete = len(self.marks) == len(steps)
        return {'id': 'cmc-readiness-diagnostic', 'title': 'Columbia computer readiness diagnostic',
                'complete': complete, 'steps': steps,
                'nextInstruction': ('Computer diagnostic complete. A known-reference IMU/optics integration is needed before P52 alignment or TLI can proceed.'
                                    if complete else steps[len(self.marks)]['description']),
                'scope': SCOPE, 'flightExecuted': False, 'alignmentCompleted': False,
                'checkpoints': deepcopy(self.marks)}

    def snapshot(self):
        with self.lock:
            value = deepcopy(self.state)
            value['available'] = self.capabilities()['available'] is True
            value['task'] = self._task()
            return value

    def _call(self, operation, *args):
        with self.lock:
            if self.closed:
                raise ControlError(503, 'The CMC console is closed.')
            if not self.thread:
                self.thread = threading.Thread(target=self._run, name='apollo-cmc-owner', daemon=True)
                self.thread.start()
        future = Future()
        try:
            self.queue.put_nowait((operation, args, future))
        except Exception:
            raise ControlError(429, 'The CMC input queue is busy. Wait for its acknowledgment.')
        try:
            return future.result(timeout=20)
        except TimeoutError:
            raise ControlError(503, 'CMC execution timed out. Inspect status before sending another key; the input was not retried.')

    def start(self):
        return self._call('start')

    def key(self, sessionId, sequence, key):
        if type(sequence) is not int or not 0 <= sequence <= 2**31-1:
            raise ControlError(400, 'CMC sequence must be a nonnegative integer.')
        if not isinstance(key, str) or key not in KEYS:
            raise ControlError(400, 'Unsupported DSKY hardware key.')
        return self._call('key', sessionId, sequence, key)

    def stop(self, sessionId):
        return self._call('stop', sessionId)

    def _check_id(self, identity):
        if not isinstance(identity, str) or identity != self.state['sessionId']:
            raise ControlError(409, 'CMC session identity does not match. Refresh before using the console.')

    def _event(self, event, **values):
        if self.log:
            with self.log.open('a') as stream:
                stream.write(json.dumps({'event': event, **values}, allow_nan=False, separators=(',', ':'))+'\n')

    def _observe(self, computer):
        if (not isinstance(computer, dict) or computer.get('software') != 'Comanche055'
                or type(computer.get('cycle')) is not int or computer['cycle'] < 0
                or not isinstance(computer.get('dsky'), dict)):
            raise ValueError('Original CMC observer returned an invalid computer frame.')
        dsky = computer['dsky']
        for name, width in [('PROG', 2), ('VERB', 2), ('NOUN', 2), ('R1', 5), ('R2', 5), ('R3', 5)]:
            value = dsky.get(name)
            if not isinstance(value, str) or len(value) != width or any(c not in ' 0123456789?' for c in value):
                raise ValueError('Original CMC observer returned an invalid DSKY digit field.')
        if self.state['computer'] and computer['cycle'] < self.state['computer']['cycle']:
            raise ValueError('Original CMC clock moved backwards.')
        last_key = self.state['computer'].get('lastKey') if self.state['computer'] else None
        self.state['computer'] = deepcopy(computer)
        self.state['computer']['lastKey'] = last_key
        index = len(self.marks)
        condition = [
            self._command_seen(['VERB', '3', '5', 'ENTR']) and all(dsky[name] == '8'*width for name, width in [('PROG', 2), ('VERB', 2), ('NOUN', 2), ('R1', 5), ('R2', 5), ('R3', 5)]),
            dsky['PROG'] == '00' and bool(self.marks) and self._command_seen(['VERB', '3', '7', 'ENTR', '0', '0', 'ENTR'], self.marks[0]['cycle']),
            self._clock_observed(computer),
            dsky['VERB'] == '05' and dsky['NOUN'] == '09' and any(dsky[name] == '00210' for name in ('R1', 'R2', 'R3')) and len(self.marks)>=3 and self._command_seen(['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'], self.marks[2]['cycle']) and self._command_seen(['VERB', '0', '5', 'NOUN', '0', '9', 'ENTR'], self.marks[2]['cycle']),
            dsky['PROG'] == '00' and dsky['VERB'] != '05' and self._recovery_entered(),
        ]
        if index < len(condition) and condition[index]:
            mark = {'id': task_definition()[index]['id'], 'cycle': computer['cycle'],
                    'dsky': deepcopy(dsky), 'dskySource': deepcopy(computer.get('dskySource'))}
            self.marks.append(mark)
            self._event('original_output_checkpoint', **mark)

    def _recovery_entered(self):
        # This is only an operator-action witness combined with observed P00;
        # it does not supply any computer display or bypass original software.
        if len(self.marks) < 4:
            return False
        after = self.marks[3]['cycle']
        keys = [row['key'] for row in self.history if row['queuedAtCycle'] >= after]
        return 'RSET' in keys and ''.join(keys).endswith('VERB37ENTR00ENTR')

    def _clock_observed(self, computer):
        dsky = computer['dsky']
        if (len(self.marks) != 2 or dsky['VERB'] != '16' or dsky['NOUN'] != '36'
                or not self._command_seen(['VERB', '1', '6', 'NOUN', '3', '6', 'ENTR'], self.marks[1]['cycle'])
                or not all(dsky[name].isdigit() for name in ('R1', 'R2', 'R3'))):
            return False
        value = tuple(dsky[name] for name in ('R1', 'R2', 'R3'))
        previous = self.clock_candidate
        self.clock_candidate = (computer['cycle'], value)
        return previous is not None and computer['cycle'] > previous[0] and value != previous[1]

    def _command_seen(self, sequence, since=0):
        keys = [row['key'] for row in self.history if row['queuedAtCycle'] >= since]
        return any(keys[index:index+len(sequence)] == sequence for index in range(len(keys)-len(sequence)+1))

    def _advance(self, seconds):
        """Validation-only clock advancement; intentionally has no HTTP route."""
        if not self.engine or self.state['status'] != 'ready':
            raise ControlError(409, 'No live CMC is ready.')
        self._observe(self.engine.advance(seconds))
        return self.snapshot()

    def _start(self):
        if self.capabilities()['available'] is not True:
            raise ControlError(503, 'Original Comanche assets are unavailable. '+str(self.capabilities().get('unavailableReason', '')))
        if self.engine:
            self.engine.close()
            self.engine = None
        self.marks, self.history = [], []
        self.clock_candidate = None
        identity = secrets.token_hex(16)
        folder = self.output_root/identity
        folder.mkdir(parents=True, exist_ok=False)
        self.log = folder/'console.jsonl'
        self.state.update(status='idle', sessionId=identity, revision=0, nextSequence=0, computer=None, inputs=[], error=None)
        self._event('start', sessionId=identity, mode=MODE, scope=SCOPE)
        if self.factory:
            self.engine = self.factory()
        else:
            from backend.cmc_native import CmcProcess, prepare_cmc_assets
            self.engine = CmcProcess(prepare_cmc_assets())
        self._observe(self.engine.boot())
        self.state['status'] = 'ready'
        self.last_activity = time.monotonic()
        return self.snapshot()

    def _key(self, identity, sequence, key):
        self._check_id(identity)
        if self.state['status'] != 'ready' or not self.engine:
            raise ControlError(409, 'Start the original CMC before pressing a DSKY key.')
        if sequence != self.state['nextSequence']:
            raise ControlError(409, 'Stale, repeated or skipped CMC key sequence. Refresh status; input was not repeated.')
        value = self.engine.key(key)
        packet, computer = value['ackpacket'], value['computer']
        if (packet.get('key') != key or type(packet.get('channel')) is not int
                or type(packet.get('code')) is not int or type(packet.get('queuedAtCycle')) is not int
                or type(packet.get('afterCycle')) is not int or packet['afterCycle'] < packet['queuedAtCycle']):
            raise ValueError('Original CMC key packet acknowledgment is invalid.')
        row = {**deepcopy(packet), 'sequence': sequence}
        self.history.append(row)
        self.state.update(nextSequence=sequence+1, revision=self.state['revision']+1,
                          inputs=deepcopy(self.history[-30:]))
        self._observe(computer)
        self.state['computer']['lastKey'] = {'key': key, 'code': packet['code'],
            'channel': packet['channel'], 'cycle': packet['queuedAtCycle'], 'sequence': sequence}
        self.last_activity = time.monotonic()
        self._event('hardware_key', **row)
        result = self.snapshot()
        result['ack'] = {**deepcopy(packet), 'sessionId': identity, 'sequence': sequence}
        return result

    def _stop(self, identity):
        self._check_id(identity)
        if self.engine:
            self.engine.close()
            self.engine = None
        self.state['status'] = 'stopped'
        self._event('stop', sessionId=identity)
        return self.snapshot()

    def _fault(self, error):
        self.state.update(status='error', error='Original CMC execution stopped: '+str(error))
        try:
            self._event('fault', message=str(error))
        except Exception:
            # A full disk or unreadable audit path must not abandon a worker.
            pass
        finally:
            if self.engine:
                try:
                    self.engine.close()
                except Exception as failure:
                    self.state['error'] += '; worker cleanup: '+str(failure)
                finally:
                    self.engine = None

    def _run(self):
        while True:
            try:
                item = self.queue.get(timeout=.1)
            except Empty:
                if self.pace:
                    with self.lock:
                        if self.engine and self.state['status'] == 'ready':
                            try:
                                if time.monotonic()-self.last_activity > self.idle_timeout:
                                    self._stop(self.state['sessionId'])
                                else:
                                    self._observe(self.engine.advance(.1))
                            except Exception as error:
                                self._fault(error)
                continue
            operation, args, future = item
            if operation == 'close':
                with self.lock:
                    if self.engine:
                        self.engine.close()
                        self.engine = None
                future.set_result(None)
                return
            try:
                with self.lock:
                    result = getattr(self, '_'+operation)(*args)
                future.set_result(result)
            except ControlError as error:
                future.set_exception(error)
            except Exception as error:
                with self.lock:
                    self._fault(error)
                future.set_exception(ControlError(503, 'The original CMC could not execute. '+str(error)))

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            worker = self.thread
        if worker:
            future = Future()
            self.queue.put(('close', (), future), timeout=3)
            future.result(timeout=10)
            worker.join(timeout=3)
            if worker.is_alive():
                raise RuntimeError('CMC owner did not shut down.')
