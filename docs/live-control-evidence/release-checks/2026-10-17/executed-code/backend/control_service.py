"""Single-owner session service. HTTP threads never call the native AGC."""
from collections import deque
from copy import deepcopy
import datetime
import json
from pathlib import Path
import secrets
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
STEP_CYCLES = 4265
PERIOD = 12 / 1024000
LEASE_CYCLES = 42666


class ControlError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class ControlService:
    """Serialize bounded RHC requests and publish copies of authoritative state."""
    def __init__(self, prepare=None, factory=None, output_root=None,
                 wall_lease=.55, idle_timeout=60., pace=True):
        self.prepare, self.factory = prepare, factory
        self.output_root = Path(output_root or ROOT / '.build/live/http')
        self.wall_lease, self.idle_timeout, self.pace = wall_lease, idle_timeout, pace
        self.lock = threading.RLock()
        self.wake, self.stop_event = threading.Event(), threading.Event()
        self.thread = None
        self.pending, self.arrivals = deque(), deque()
        self.requests = []
        self.sequence = -1
        self.gateway_log = self.provenance = None
        self.stop_reason = 'operator stop'
        self.state = {'status': 'idle', 'sessionId': None, 'message': 'Start a fresh native AGC session.',
                      'frame': None, 'appliedSequence': -1, 'summary': None}

    def _event(self, event, **values):
        row = {'event': event, 'wallUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(), **values}
        if self.gateway_log:
            with self.gateway_log.open('a') as stream:
                stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ControlError(409, 'A native session is already active or finishing.')
            identity = secrets.token_hex(16)
            folder = self.output_root / identity
            folder.mkdir(parents=True, exist_ok=False)
            self.gateway_log = folder / 'requests.jsonl'
            self.pending.clear()
            self.arrivals.clear()
            self.requests, self.sequence, self.provenance = [], -1, None
            self.stop_event.clear()
            self.wake.clear()
            self.stop_reason = 'operator stop'
            self.state = {'status': 'initializing', 'sessionId': identity,
                          'message': 'Verifying sources and executing original startup…',
                          'frame': None, 'appliedSequence': -1, 'summary': None}
            self._event('session_start', sessionId=identity)
            self.thread = threading.Thread(target=self._run, name='apollo-native-owner', daemon=True)
            self.thread.start()
            return deepcopy(self.state)

    def _check_id(self, identity):
        if not isinstance(identity, str) or identity != self.state['sessionId']:
            raise ControlError(409, 'Session identity does not match this run.')

    def command(self, identity, sequence, yaw, pitch):
        if type(sequence) is not int or not 0 <= sequence <= 2**31 - 1:
            raise ControlError(400, 'Sequence must be a nonnegative integer.')
        if any(type(v) is not int or v not in (-1, 0, 1) for v in (yaw, pitch)):
            raise ControlError(400, 'Yaw and pitch must be integer -1, 0 or +1.')
        with self.lock:
            self._check_id(identity)
            if self.state['status'] not in ('ready', 'running') or self.stop_event.is_set():
                raise ControlError(409, 'Original native readiness is required.')
            if sequence <= self.sequence:
                raise ControlError(409, 'Stale or repeated controller sequence.')
            now = time.monotonic()
            while self.arrivals and now - self.arrivals[0] > 1:
                self.arrivals.popleft()
            neutral = yaw == pitch == 0
            if not neutral and (len(self.arrivals) >= 20 or len(self.pending) >= 16):
                raise ControlError(429, 'Controller queue is busy; release to neutral.')
            if neutral:
                while self.pending:
                    old = self.pending.popleft()
                    old['status'] = 'cancelled by neutral release'
                    self._event('cancelled', sequence=old['sequence'])
            row = {'sequence': sequence, 'yaw': yaw, 'pitch': pitch, 'status': 'queued',
                   'receivedWallUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'receivedMonotonic': now}
            self.sequence = sequence
            self.arrivals.append(now)
            self.requests.append(row)
            self.pending.append(row)
            self._event('input_queued', sequence=sequence, yaw=yaw, pitch=pitch)
            self.wake.set()
            return {'accepted': True, 'sequence': sequence, 'sessionId': identity,
                    'meaning': 'Queued pilot input; acceptance is not AGC consumption.'}

    def stop(self, identity, reason='operator stop'):
        with self.lock:
            self._check_id(identity)
            if self.state['status'] in ('initializing', 'ready', 'running'):
                self.stop_reason = reason
                self.state.update(status='stopping', message='Neutralizing inputs and draining native sensor queues…')
                self.stop_event.set()
                self.wake.set()
                self._event('stop_requested', reason=reason)
            return deepcopy(self.state)

    def record(self):
        with self.lock:
            if self.state['sessionId'] is None:
                raise ControlError(409, 'No live session exists.')
            return deepcopy({'session': self.state, 'pilotRequests': self.requests,
                             'provenance': self.provenance, 'requestLog': str(self.gateway_log),
                             'scope': 'Live native AGC; synthetic bounded attitude only. No powered descent.'})

    def close(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.stop_reason = 'server shutdown'
                self.stop_event.set()
                self.wake.set()
        if self.thread:
            self.thread.join(timeout=30)
            if self.thread.is_alive():
                raise RuntimeError('Native worker did not finish bounded shutdown.')

    def _publish(self, frame, status, message):
        with self.lock:
            self.state.update(frame=deepcopy(frame), status=status, message=message)

    def _run(self):
        native = None
        try:
            if self.prepare is None or self.factory is None:
                from backend.native_session import NativeSession, prepare_assets
                prepare, factory = self.prepare or prepare_assets, self.factory or NativeSession
            else:
                prepare, factory = self.prepare, self.factory
            assets = prepare()
            with self.lock:
                self.provenance = deepcopy(assets.get('provenance'))
            native = factory(assets)
            frame = native.start()
            if not frame.get('ready'):
                raise RuntimeError('Original native readiness was not established.')
            if not self.stop_event.is_set():
                self._publish(frame, 'ready', 'Original readiness established. CPU paused until your first deflection.')
            armed_at = last_input = time.monotonic()
            running, desired = False, (0, 0)
            deadline = armed_at
            while not self.stop_event.is_set():
                with self.lock:
                    request = self.pending.popleft() if self.pending else None
                now = time.monotonic()
                if request is not None and (request['yaw'] or request['pitch']) and now - request['receivedMonotonic'] > self.wall_lease:
                    with self.lock:
                        request['status'] = 'expired before native application'
                        self._event('expired_input', sequence=request['sequence'])
                    request = None
                if request is not None:
                    desired = (request['yaw'], request['pitch'])
                    if not running and desired == (0, 0):
                        applied = {'cycle': frame['cycle'], 'meaning': 'Already neutral; CPU remains paused.'}
                    else:
                        applied = native.command(*desired, duration_cycles=LEASE_CYCLES)
                        if not running:
                            running, deadline = True, now
                    last_input = request['receivedMonotonic']
                    with self.lock:
                        request.update(status='applied to input interface' if running else 'already neutral', native=deepcopy(applied))
                        self.state['appliedSequence'] = request['sequence']
                        self._event('input_applied', sequence=request['sequence'], native=applied)
                if not running:
                    if now - armed_at >= self.idle_timeout:
                        self.stop_reason = 'armed session idle timeout'
                        break
                    self.wake.wait(.1)
                    self.wake.clear()
                    continue
                if desired != (0, 0) and now - last_input > self.wall_lease:
                    native.command(0, 0, duration_cycles=0)
                    desired = (0, 0)
                    self._event('wall_lease_neutral', cycle=frame['cycle'])
                frame = native.advance(STEP_CYCLES)
                if native.closed:
                    break
                if not frame.get('ready'):
                    raise RuntimeError('Original readiness changed; controls stopped.')
                self._publish(frame, 'running', 'Live native execution · authoritative simulation clock.')
                if self.pace:
                    deadline += STEP_CYCLES * PERIOD
                    self.stop_event.wait(max(0, deadline - time.monotonic()))
            summary = native.summary if native.closed else native.stop(self.stop_reason)
            with self.lock:
                self.state['summary'] = deepcopy(summary)
            frame = native.frame()
            self._publish(frame, 'fault' if native.status == 'failed' else 'stopped',
                          frame.get('error') or 'Run ended. Physics frozen; queue settlement is not stability.')
            self._event('session_finished', status=self.state['status'], cycle=frame['cycle'])
        except Exception as error:
            if native is not None and not native.closed:
                try:
                    native.stop('backend error: ' + str(error))
                except Exception:
                    pass
            with self.lock:
                self.state.update(status='fault', message=str(error),
                                  frame=deepcopy(native.frame()) if native is not None else None,
                                  summary=deepcopy(getattr(native, 'summary', None)))
                self._event('session_fault', error=str(error))
        finally:
            with self.lock:
                for request in self.pending:
                    request['status'] = 'not applied before session ended'
                self.pending.clear()
                if self.gateway_log:
                    (self.gateway_log.parent / 'record.json').write_text(json.dumps(self.record(), indent=2, allow_nan=False) + '\n')
