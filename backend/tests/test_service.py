"""Deterministic gateway lifecycle tests; FakeNative never executes AGC code."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend import control_service as service_module

REAL_MONOTONIC = time.monotonic


class Clock:
    def __init__(self):
        self.value = 100.0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def set(self, value):
        with self.lock:
            self.value = value


class FakeNative:
    """A gated modern test double, with no fabricated authentic telemetry."""
    def __init__(self, assets, blocked_start=False, ready=True):
        self.owner = threading.get_ident()
        self.calls = []
        self.closed = False
        self.status = 'created'
        self.summary = {'classification': 'Unit test double; not AGC execution'}
        self.cycle = 0
        self.ready = ready
        self.control = (0, 0)
        self.start_entered = threading.Event()
        self.start_release = threading.Event()
        if not blocked_start:
            self.start_release.set()
        self.permits = queue.Queue()
        self.condition = threading.Condition()
        self.advance_count = 0

    def _call(self, operation, **values):
        if threading.get_ident() != self.owner:
            raise AssertionError('A request thread called the native test double')
        self.calls.append((operation, values))

    def start(self):
        self._call('start')
        self.start_entered.set()
        if not self.start_release.wait(timeout=5):
            raise RuntimeError('Test startup gate timed out')
        self.status = 'running'
        return self.frame()

    def command(self, yaw, pitch, duration_cycles):
        self._call('command', yaw=yaw, pitch=pitch, duration_cycles=duration_cycles)
        self.control = (yaw, pitch)
        return {'cycle': self.cycle, 'yaw': yaw, 'pitch': pitch}

    def advance(self, cycles):
        self._call('advance', cycles=cycles)
        with self.condition:
            self.advance_count += 1
            self.condition.notify_all()
        try:
            self.permits.get(timeout=5)
        except queue.Empty:
            raise RuntimeError('Test advance gate timed out')
        self.cycle += cycles
        return self.frame()

    def frame(self):
        self._call('frame')
        return {'cycle': self.cycle, 'ready': self.ready and not self.closed,
                'model': {'unitValues': [1, 2, 3]}, 'control': list(self.control)}

    def stop(self, reason):
        self._call('stop', reason=reason)
        self.closed, self.status = True, 'stopped'
        self.summary = {'classification': 'Unit test double; not AGC execution', 'reason': reason}
        return self.summary

    def wait_advance(self, count):
        with self.condition:
            if not self.condition.wait_for(lambda: self.advance_count >= count, timeout=3):
                raise AssertionError('Native owner did not reach the requested advance gate')

    def controls(self):
        return [(row['yaw'], row['pitch']) for operation, row in self.calls if operation == 'command']


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.clock = Clock()
        patcher = patch.object(service_module.time, 'monotonic', self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.instances = []
        self.created = threading.Event()
        self.services = []
        self.addCleanup(self.finish_workers)

    def finish_workers(self):
        for service in self.services:
            service.stop_event.set()
            service.wake.set()
        for native in self.instances:
            native.start_release.set()
            for _ in range(4):
                native.permits.put(None)
        for service in self.services:
            service.close()

    def new_service(self, blocked_start=False, ready=True):
        def factory(assets):
            native = FakeNative(assets, blocked_start, ready)
            self.instances.append(native)
            self.created.set()
            return native
        service = service_module.ControlService(
            prepare=lambda: {'provenance': {'unitSources': [1, 2]}}, factory=factory,
            output_root=Path(self.directory.name), pace=False)
        self.services.append(service)
        self.created.clear()
        identity = service.start()['sessionId']
        self.assertTrue(self.created.wait(timeout=3))
        native = self.instances[-1]
        self.assertTrue(native.start_entered.wait(timeout=3))
        return service, identity, native

    def wait_status(self, service, expected):
        deadline = REAL_MONOTONIC() + 3
        while REAL_MONOTONIC() < deadline:
            state = service.snapshot()
            if state['status'] == expected:
                return state
            threading.Event().wait(.002)
        self.fail('Expected status {}: {}'.format(expected, service.snapshot()))

    def assert_control_error(self, status, call):
        with self.assertRaises(service_module.ControlError) as caught:
            call()
        self.assertEqual(caught.exception.status, status)

    def test_ready_is_paused_and_neutral_does_not_start_native_time(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        service.command(identity, 0, 0, 0)
        deadline = REAL_MONOTONIC() + 3
        while service.snapshot()['appliedSequence'] != 0 and REAL_MONOTONIC() < deadline:
            threading.Event().wait(.002)
        self.assertEqual(service.snapshot()['appliedSequence'], 0)
        self.assertEqual(native.advance_count, 0)
        self.assertEqual(native.controls(), [])
        self.assertEqual(service.snapshot()['status'], 'ready')

    def test_strict_inputs_session_identity_and_sequence_rejection_do_not_reach_native(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        for invalid in (True, 1.0, '1', None, -2, 2):
            for yaw, pitch in ((invalid, 0), (0, invalid)):
                self.assert_control_error(400, lambda: service.command(identity, 0, yaw, pitch))
        for sequence in (True, 1.0, '1', None, -1, 2**31):
            self.assert_control_error(400, lambda: service.command(identity, sequence, 0, 0))
        self.assert_control_error(409, lambda: service.command('previous session', 0, 1, 0))
        service.command(identity, 5, 0, 0)
        for sequence in (0, 4, 5):
            self.assert_control_error(409, lambda: service.command(identity, sequence, 1, 0))
        self.assertEqual(native.controls(), [])
        self.assertEqual(native.advance_count, 0)

    def test_one_owner_drives_commands_stop_and_persisted_record(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        service.command(identity, 1, -1, 1)
        native.wait_advance(1)
        self.assertNotEqual(native.owner, threading.get_ident())
        self.assertEqual(native.controls(), [(-1, 1)])
        self.assert_control_error(409, service.start)
        service.stop(identity)
        native.permits.put(None)
        self.wait_status(service, 'stopped')
        service.close()
        self.assertFalse(service.thread.is_alive())
        self.assertEqual([op for op, _ in native.calls].count('stop'), 1)
        record = json.loads((service.gateway_log.parent / 'record.json').read_text())
        self.assertEqual(record['session']['status'], 'stopped')
        self.assertEqual(record['pilotRequests'][0]['status'], 'applied to input interface')

    def test_expired_queued_deflection_never_reaches_native_and_lost_client_neutralizes(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        service.command(identity, 1, 1, 0)
        native.wait_advance(1)
        service.command(identity, 2, -1, 0)
        self.clock.set(101.0)
        native.permits.put(None)
        native.wait_advance(2)
        self.assertEqual(native.controls(), [(1, 0), (0, 0)])
        self.assertEqual(service.record()['pilotRequests'][1]['status'], 'expired before native application')
        self.assertEqual(service.snapshot()['appliedSequence'], 1)

    def test_processing_delay_does_not_extend_receipt_based_wall_lease(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        service.command(identity, 1, 1, 0)
        native.wait_advance(1)
        self.clock.set(100.1)
        service.command(identity, 2, 0, -1)
        self.clock.set(100.5)
        native.permits.put(None)
        native.wait_advance(2)
        self.assertEqual(native.controls(), [(1, 0), (0, -1)])
        self.clock.set(100.7)
        native.permits.put(None)
        native.wait_advance(3)
        self.assertEqual(native.controls(), [(1, 0), (0, -1), (0, 0)])

    def test_neutral_cancels_a_full_pending_queue_and_bypasses_rate_limit(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        service.command(identity, 1, 1, 0)
        native.wait_advance(1)
        for sequence in range(2, 18):
            service.command(identity, sequence, -1, 1)
        self.assert_control_error(429, lambda: service.command(identity, 18, 1, 1))
        service.command(identity, 19, 0, 0)
        requests = service.record()['pilotRequests']
        self.assertTrue(all(row['status'] == 'cancelled by neutral release' for row in requests[1:-1]))
        native.permits.put(None)
        native.wait_advance(2)
        self.assertEqual(native.controls(), [(1, 0), (0, 0)])
        self.assertEqual(service.snapshot()['appliedSequence'], 19)

    def test_cached_snapshots_and_downloads_cannot_mutate_authoritative_state(self):
        service, identity, native = self.new_service()
        self.wait_status(service, 'ready')
        snapshot = service.snapshot()
        snapshot['frame']['model']['unitValues'][0] = 999
        record = service.record()
        record['session']['status'] = 'forged'
        record['provenance']['unitSources'][0] = 999
        self.assertEqual(service.snapshot()['frame']['model']['unitValues'], [1, 2, 3])
        self.assertEqual(service.record()['provenance']['unitSources'], [1, 2])
        self.assertEqual(service.snapshot()['status'], 'ready')
        self.assertEqual(native.advance_count, 0)

    def test_unready_startup_faults_and_never_accepts_pilot_input(self):
        service, identity, native = self.new_service(ready=False)
        self.wait_status(service, 'fault')
        self.assert_control_error(409, lambda: service.command(identity, 1, 1, 0))
        self.assertEqual(native.controls(), [])
        self.assertEqual(native.advance_count, 0)
        self.assertTrue(native.closed)

    def test_stop_during_startup_does_not_publish_ready_or_accept_input(self):
        service, identity, native = self.new_service(blocked_start=True)
        self.assertEqual(service.snapshot()['status'], 'initializing')
        service.stop(identity)
        self.assertEqual(service.snapshot()['status'], 'stopping')
        self.assert_control_error(409, lambda: service.command(identity, 1, 1, 0))
        native.start_release.set()
        self.wait_status(service, 'stopped')
        self.assertEqual(native.controls(), [])
        self.assertEqual(native.advance_count, 0)
        self.assertTrue(native.closed)


if __name__ == '__main__':
    unittest.main()
