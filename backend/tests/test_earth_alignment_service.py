"""Alignment owner/transport checks; native tests supply original execution proof."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import math
import tempfile
import unittest
from unittest.mock import patch

from backend.control_service import ControlError
from backend.earth_alignment_service import EarthAlignmentService, MODE, validate_control
from backend.tests.test_earth_orbit_service import FakeEngine, digits


class InstrumentEngine(FakeEngine):
    """Transport double: deliberately never predicts any Apollo response."""
    def __init__(self):
        super().__init__()
        self.controls = []
        self.instruments = {'mode': 'MODELED CSM INSTRUMENTS', 'imuPowered': True,
            'opticsMode': 'MANUAL', 'shaftDeg': 0., 'trunnionDeg': 40.,
            'mechanicalTrunnionDeg': 20.224609375, 'stars': [], 'markCount': 0,
            'alignment': {'referenceInitialized': True, 'p52Complete': False, 'p52Marks': 0,
                'torqueApproved': False, 'torqueOutputCount': 0, 'completionCycle': None}}
        self.instruments['alignment']['gyroSensorFeedbackOperations'] = 0

    def frame(self):
        return {**super().frame(), 'instruments': deepcopy(self.instruments),
                'flightState': None, 'historicalCheckpointLoaded': False}

    def instrument(self, action, value):
        before = self.cycle
        self.controls.append((action, deepcopy(value)))
        self.cycle += 100
        return {'computer': self.frame(), 'ackpacket': {'action': action,
            'value': deepcopy(value), 'queuedAtCycle': before, 'afterCycle': self.cycle}}


class EarthAlignmentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='apollo-alignment-service-')
        self.addCleanup(self.tmp.cleanup)
        self.engines = []
        def factory():
            engine = InstrumentEngine()
            self.engines.append(engine)
            return engine
        self.service = EarthAlignmentService(factory=factory, discovery=lambda: {'available': True},
            output_root=self.tmp.name, pace=False)
        self.addCleanup(self.service.close)

    def keys(self, state, keys):
        for key in keys:
            state = self.service.key(state['sessionId'], state['nextSequence'], key)
        return state

    def instrument(self, state, control='mark', value='MARK'):
        return self.service.instrument(state['sessionId'], state['nextSequence'], control, value)

    def observe(self, **changes):
        self.engines[-1].display.update(changes)
        return self.service._call('advance', .1)

    def test_discovery_and_status_do_not_start_or_imply_flight_or_alignment(self):
        capability = self.service.capabilities()
        self.assertTrue(capability['available'])
        self.assertEqual(capability['mode'], MODE)
        self.assertEqual(len(capability['supportedKeys']), 19)
        self.assertEqual(capability['supportedControls'], ['power_imu', 'optics_mode', 'optics_slew', 'mark'])
        self.assertFalse(capability['flightExecuted'])
        self.assertFalse(capability['translunarInjection'])
        state = self.service.snapshot()
        self.assertIsNone(self.service.thread)
        self.assertIsNone(state['computer'])
        self.assertFalse(state['task']['alignmentCompleted'])
        self.assertFalse(state['task']['complete'])
        self.assertEqual(self.engines, [])

    def test_keys_and_instrument_controls_use_one_strict_sequence_and_native_acks(self):
        state = self.service.start()
        state = self.keys(state, ['VERB'])
        state = self.instrument(state, 'optics_mode', 'MANUAL')
        self.assertEqual(state['nextSequence'], 2)
        self.assertEqual(state['revision'], 2)
        self.assertEqual(state['ack']['sequence'], 1)
        self.assertEqual(state['ack']['control'], 'optics_mode')
        self.assertEqual(state['ack']['action'], 'optics_mode')
        self.assertEqual(state['computer']['lastKey']['key'], 'VERB')
        self.assertEqual(state['computer']['lastControl']['value'], 'MANUAL')
        for request in [lambda: self.service.key(state['sessionId'], 1, 'ENTR'),
                        lambda: self.service.instrument(state['sessionId'], 1, 'mark', 'MARK'),
                        lambda: self.service.instrument('other-session', 2, 'mark', 'MARK')]:
            with self.assertRaises(ControlError) as error:
                request()
            self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.engines[0].keys, ['VERB'])
        self.assertEqual(self.engines[0].controls, [('optics_mode', 'MANUAL')])

    def test_racing_key_and_mark_cannot_consume_one_sequence_twice(self):
        state = self.service.start()
        def key():
            try:
                return self.service.key(state['sessionId'], 0, 'VERB')['nextSequence']
            except ControlError as error:
                return error.status
        def mark():
            try:
                return self.service.instrument(state['sessionId'], 0, 'mark', 'MARK')['nextSequence']
            except ControlError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda action: action(), [key, mark]))
        self.assertCountEqual(results, [1, 409])
        self.assertEqual(len(self.engines[0].keys)+len(self.engines[0].controls), 1)

    def test_invalid_controls_never_reach_or_start_the_native_worker(self):
        cases = [('power_imu', 1), ('power_imu', 'true'), ('optics_mode', 'AUTO'),
                 ('optics_mode', 'CMC'),
                 ('mark', 'PRO'), ('unknown', True), ('optics_slew', {}),
                 ('optics_slew', {'shaft': 0, 'trunnion': 0, 'rate': 'LOW', 'seconds': 2}),
                 ('optics_slew', {'shaft': math.nan, 'trunnion': 0, 'rate': 'LOW', 'seconds': .1}),
                 ('optics_slew', {'shaft': True, 'trunnion': 0, 'rate': 'LOW', 'seconds': .1}),
                 ('optics_slew', {'shaft': 0, 'trunnion': 0, 'rate': 'LOW', 'seconds': .1, 'target': 1})]
        for control, value in cases:
            with self.subTest(control=control, value=value), self.assertRaises(ControlError):
                self.service.instrument('none', 0, control, value)
        with self.assertRaises(ControlError):
            self.service.instrument('none', True, 'mark', 'MARK')
        self.assertIsNone(self.service.thread)
        self.assertEqual(self.engines, [])
        for control, value in [('power_imu', False), ('optics_mode', 'ZERO'), ('mark', 'REJECT'),
                              ('optics_slew', {'shaft': -1, 'trunnion': 1, 'rate': 'HIGH', 'seconds': 1})]:
            validate_control(control, value)

    def test_nonmanual_optics_slew_is_a_conflict_without_faulting_the_computer(self):
        state = self.service.start()
        self.engines[0].instruments['opticsMode'] = 'ZERO'
        self.service._call('advance', .1)
        with self.assertRaises(ControlError) as error:
            self.instrument(state, 'optics_slew', {'shaft': 1, 'trunnion': 0, 'rate': 'LOW', 'seconds': .1})
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.service.snapshot()['status'], 'ready')
        self.assertFalse(self.engines[0].closed)
        self.assertEqual(self.engines[0].controls, [])

    def test_known_p51_reference_and_correct_script_do_not_claim_p52_completion(self):
        state = self.service.start()
        self.assertTrue(state['computer']['instruments']['alignment']['referenceInitialized'])
        state = self.keys(state, ['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR',
                                 'PRO', 'PRO', 'VERB', '3', '7', 'ENTR', '0', '0', 'ENTR'])
        state = self.instrument(state)
        state = self.instrument(state)
        self.assertFalse(state['task']['complete'])
        self.assertFalse(any(step['complete'] for step in state['task']['steps']))
        self.assertEqual(state['computer']['dsky'], digits())

    def test_native_completion_boolean_alone_is_insufficient(self):
        self.service.start()
        alignment = self.engines[0].instruments['alignment']
        alignment.update(p52Complete=True, p52Marks=2, torqueApproved=True,
                         torqueOutputCount=100, completionCycle=1000)
        state = self.observe(PROG='00')
        self.assertFalse(state['task']['complete'])
        self.assertFalse(state['task']['alignmentCompleted'])

    def test_all_original_observations_operator_marks_and_final_p00_are_required(self):
        state = self.service.start()
        state = self.keys(state, ['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'])
        state = self.observe(PROG='52')
        self.assertTrue(state['task']['steps'][0]['complete'])
        state = self.instrument(state)
        state = self.instrument(state)
        alignment = self.engines[0].instruments['alignment']
        alignment['p52Marks'] = 2
        state = self.observe(VERB='06', NOUN='05', R1='00001')
        self.assertTrue(state['task']['steps'][1]['complete'])
        self.assertTrue(state['task']['steps'][2]['complete'])
        state = self.observe(VERB='06', NOUN='93', R1='00000', R2='00012', R3='00000')
        self.assertTrue(state['task']['steps'][3]['complete'])
        alignment.update(p52Complete=True, torqueApproved=True, completionCycle=self.engines[0].cycle)
        state = self.observe(VERB='50', NOUN='25', R1='00014')
        self.assertNotIn('completion-display', self.service.observed, 'Missing gyro output must keep the gate closed')
        alignment['torqueOutputCount'] = 700
        state = self.observe()
        self.assertNotIn('completion-display', self.service.observed, 'Gyro output without sensor feedback must keep the gate closed')
        alignment['gyroSensorFeedbackOperations'] = 2
        state = self.observe()
        self.assertIn('completion-display', self.service.observed)
        state = self.observe(PROG='00')
        self.assertFalse(state['task']['complete'], 'An unsolicited P00 is insufficient')
        state = self.keys(state, ['VERB', '3', '7', 'ENTR', '0', '0', 'ENTR'])
        self.assertTrue(state['task']['complete'])
        self.assertTrue(state['task']['alignmentCompleted'])
        self.assertFalse(state['task']['flightExecuted'])
        self.assertIsNone(state['computer']['flightState'])
        self.assertEqual(len(state['task']['checkpoints']), 6)

    def test_displayed_angle_difference_without_two_real_mark_requests_does_not_advance(self):
        state = self.service.start()
        self.keys(state, ['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'])
        self.observe(PROG='52')
        self.engines[0].instruments['alignment']['p52Marks'] = 2
        state = self.observe(VERB='06', NOUN='05', R1='00001')
        self.assertFalse(state['task']['steps'][1]['complete'])
        self.assertFalse(state['task']['steps'][2]['complete'])

    def test_selecting_p52_again_clears_prior_attempt_checkpoints(self):
        state = self.service.start()
        self.keys(state, ['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'])
        state = self.observe(PROG='52')
        state = self.instrument(state)
        state = self.instrument(state)
        self.engines[0].instruments['alignment']['p52Marks'] = 2
        self.observe(VERB='06', NOUN='05', R1='00001')
        self.assertIn('star-angle', self.service.observed)
        state = self.observe(PROG='00')
        self.keys(state, ['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'])
        self.engines[0].instruments['alignment']['p52Marks'] = 0
        state = self.observe(PROG='52', VERB='04', NOUN='06')
        self.assertEqual(list(self.service.observed), ['select-p52'])
        self.assertFalse(state['task']['steps'][1]['complete'])

    def test_restart_stops_old_process_and_invalidates_old_controls(self):
        old = self.service.start()
        fresh = self.service.start()
        self.assertTrue(self.engines[0].closed)
        self.assertNotEqual(old['sessionId'], fresh['sessionId'])
        with self.assertRaises(ControlError):
            self.service.instrument(old['sessionId'], 0, 'mark', 'MARK')
        self.service.stop(fresh['sessionId'])
        self.assertTrue(self.engines[1].closed)
        with self.assertRaises(ControlError):
            self.service.instrument(fresh['sessionId'], 0, 'mark', 'MARK')

    def test_invalid_observation_keeps_last_real_frame_and_closes_worker(self):
        state = self.service.start()
        old = deepcopy(state['computer'])
        self.engines[0].instruments['shaftDeg'] = math.inf
        with patch.object(self.service, '_event', side_effect=OSError('audit disk full')):
            with self.assertRaises(ControlError):
                self.service._call('advance', .1)
        state = self.service.snapshot()
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['computer'], old)
        self.assertTrue(self.engines[0].closed)
        self.assertIsNone(self.service.engine)

    def test_recorded_only_disables_alignment_without_disabling_other_services(self):
        service = EarthAlignmentService(enabled=False)
        self.addCleanup(service.close)
        self.assertFalse(service.capabilities()['available'])
        self.assertEqual(service.capabilities()['supportedControls'], [])
        with self.assertRaises(ControlError) as error:
            service.start()
        self.assertEqual(error.exception.status, 503)


class OriginalP52ServiceTests(unittest.TestCase):
    def test_complete_alignment_uses_fresh_original_comanche_and_sensor_feedback(self):
        from backend.cmc_alignment import CmcAlignmentProcess, prepare_alignment_assets
        assets = prepare_alignment_assets()
        with tempfile.TemporaryDirectory(prefix='apollo-original-p52-service-') as folder:
            service = EarthAlignmentService(factory=lambda: CmcAlignmentProcess(assets),
                discovery=lambda: {'available': True}, output_root=folder, pace=False)
            try:
                state = service.start()
                self.assertEqual(state['computer']['dsky']['PROG'], '00')
                self.assertTrue(state['computer']['instruments']['alignment']['referenceInitialized'])
                self.assertFalse(state['task']['alignmentCompleted'])
                def keys(text):
                    nonlocal state
                    for key in text.split():
                        state = service.key(state['sessionId'], state['nextSequence'], key)
                        self.assertEqual(state['ack']['accepted'], 4)
                    state = service._call('advance', 3)
                def instrument(control, value):
                    nonlocal state
                    state = service.instrument(state['sessionId'], state['nextSequence'], control, value)
                keys('VERB 3 7 ENTR 5 2 ENTR')
                self.assertIn('option 3', state['task']['nextInstruction'])
                keys('VERB 2 2 ENTR 0 0 0 0 3 ENTR PRO')
                keys('ENTR')
                keys('VERB 2 1 ENTR 0 0 0 3 0 ENTR PRO')
                self.assertEqual(state['computer']['dsky']['VERB'], '51')
                instrument('mark', 'MARK')
                keys('PRO')
                keys('PRO')
                keys('VERB 2 1 ENTR 0 0 0 3 7 ENTR PRO')
                target = state['computer']['instruments']['stars'][1]['shaftDeg']
                for _ in range(15):
                    difference = target-state['computer']['instruments']['shaftDeg']
                    if abs(difference) < 1e-6:
                        break
                    instrument('optics_slew', {'shaft': max(-1, min(1, difference/20)),
                        'trunnion': 0, 'rate': 'HIGH', 'seconds': 1})
                self.assertLess(abs(target-state['computer']['instruments']['shaftDeg']), 1e-6)
                instrument('mark', 'MARK')
                keys('PRO')
                keys('PRO')
                self.assertEqual(state['computer']['dsky']['NOUN'], '05')
                self.assertTrue(state['task']['steps'][2]['complete'])
                keys('PRO')
                self.assertEqual(state['computer']['dsky']['NOUN'], '93')
                keys('PRO')
                state = service._call('advance', 15)
                alignment = state['computer']['instruments']['alignment']
                self.assertTrue(alignment['p52Complete'])
                self.assertGreater(alignment['torqueOutputCount'], 0)
                self.assertGreater(alignment['gyroSensorFeedbackOperations'], 0)
                self.assertFalse(state['task']['complete'], 'Task still requires final original P00')
                keys('VERB 3 7 ENTR 0 0 ENTR')
                self.assertTrue(state['task']['complete'], state['task'])
                self.assertTrue(state['task']['alignmentCompleted'])
                self.assertFalse(state['task']['flightExecuted'])
                self.assertIsNone(state['computer']['flightState'])
                self.assertFalse(state['computer']['historicalCheckpointLoaded'])
            finally:
                service.close()


if __name__ == '__main__':
    unittest.main()
