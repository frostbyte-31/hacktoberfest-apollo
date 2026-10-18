"""Checklist authority and training evidence tests; no native emulator starts."""
from copy import deepcopy
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.control_service import ControlError
from backend.procedure_service import MODE, ProcedureService, validate_definition


def definition():
    """Small explicitly nonhistorical contract fixture, never application evidence."""
    base = {'sourceIds': ['fixture'], 'locator': 'Unit-test fixture only'}
    return {'schemaVersion': 1,
            'sources': [{'id': 'fixture', 'url': 'https://example.invalid/training-fixture'}],
            'initialControls': {'guidance': 'UNKNOWN'}, 'steps': [
                dict(base, id='closeout', label='Report closeout', kind='crew-report',
                     role='LMP', correctValue='CONFIRMED'),
                dict(base, id='guidance', label='Select guidance', kind='select', role='CDR',
                     controlId='guidance', correctValue='AGS',
                     options=[{'value': 'PGNS', 'label': 'PGNS'}, {'value': 'AGS', 'label': 'AGS'}]),
                dict(base, id='ready', label='Report ready', kind='crew-report', role='CDR',
                     correctValue='CONFIRMED'),
                dict(base, id='release', label='Release modeled attachment', kind='momentary',
                     role='CMP', controlId='probe', correctValue='EXTD/REL', effect='release'),
                dict(base, id='confirm', label='Report separation', kind='crew-report',
                     role='CMP', correctValue='CONFIRMED')]}


class ProcedureServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ProcedureService(definition=definition())
        self.state = self.service.start()

    def act(self, value=None, **changes):
        state = self.service.snapshot()
        step = state['currentStep']
        payload = {'sessionId': state['sessionId'], 'sequence': state['lastSequence'] + 1,
                   'expectedRevision': state['revision'], 'role': step['role'],
                   'action': step['id'], 'value': step['correctValue'] if value is None else value}
        payload.update(changes)
        return self.service.action(**payload)

    def advance_to(self, identity):
        while self.service.snapshot()['currentStep']['id'] != identity:
            self.act()

    def assert_rejected_without_mutation(self, status, **changes):
        before = self.service.snapshot()
        with self.assertRaises(ControlError) as caught:
            self.act(**changes)
        self.assertEqual(caught.exception.status, status)
        self.assertEqual(self.service.snapshot(), before)

    def test_initial_session_is_distinct_training_with_unavailable_flight_capabilities(self):
        state = self.service.snapshot()
        self.assertEqual(state['classification'], MODE)
        self.assertEqual(state['status'], 'active')
        self.assertEqual(state['attachment'], 'docked')
        self.assertEqual(state['revision'], 0)
        self.assertEqual(state['lastSequence'], -1)
        self.assertEqual(state['controls']['guidance'], 'UNKNOWN')
        self.assertEqual(state['controlEvidence'], {})
        for name in ('originalAgc', 'flightPhysics', 'sensorReadback', 'historicalMissionClock'):
            self.assertIs(state['capabilities'][name], False)
        for name in ('positionM', 'velocityMps', 'quaternion', 'dsky', 'missionGet', 'cycle'):
            self.assertNotIn(name, state)

    def test_future_release_and_wrong_crew_cannot_bypass_checklist(self):
        self.assert_rejected_without_mutation(409, action='release', role='CMP', value='EXTD/REL')
        self.assert_rejected_without_mutation(403, role='CDR')
        self.advance_to('release')
        self.assert_rejected_without_mutation(403, role='CDR')
        self.assertEqual(self.service.snapshot()['attachment'], 'docked')

    def test_wrong_selector_position_is_acknowledged_without_claiming_step_completion(self):
        self.advance_to('guidance')
        response = self.act('PGNS')
        self.assertTrue(response['accepted'])
        self.assertFalse(response['advanced'])
        state = response['snapshot']
        self.assertEqual(state['controls']['guidance'], 'PGNS')
        self.assertEqual(state['currentStep']['id'], 'guidance')
        self.assertNotIn('guidance', state['completedStepIds'])
        self.assertEqual(state['controlEvidence']['guidance']['evidenceKind'], 'trainer-control')
        self.assertEqual(state['revision'], 2)
        self.assertIn('not reached', response['meaning'])
        self.assertTrue(self.act()['advanced'])

    def test_invalid_selector_and_unconfirmed_reports_reject_atomically(self):
        self.assert_rejected_without_mutation(400, value='NOT CHECKED')
        self.advance_to('guidance')
        self.assert_rejected_without_mutation(400, value='AUTO')

    def test_manual_reports_never_become_sensor_readbacks(self):
        result = self.act()['snapshot']
        report = result['crewReports']['closeout']
        self.assertEqual(report['evidenceKind'], 'crew-report')
        self.assertEqual(report['role'], 'LMP')
        self.assertEqual(report['sourceIds'], ['fixture'])
        self.assertEqual(result['events'][0]['evidenceKind'], 'crew-report')
        self.assertEqual(result['controlEvidence'], {})

    def test_release_changes_attachment_only_after_sourced_cmp_control(self):
        self.advance_to('release')
        before = self.service.snapshot()
        result = self.act()['snapshot']
        self.assertEqual(before['attachment'], 'docked')
        self.assertEqual(result['attachment'], 'released')
        self.assertEqual(result['attachmentEvidence'], 'modeled-mechanical-release')
        self.assertEqual(result['chapterId'], 'undocking')
        self.assertEqual(result['unlockedChapterIds'], ['docked-preparation', 'undocking'])
        self.assertEqual(result['controlEvidence']['probe']['evidenceKind'], 'trainer-control')
        self.assertFalse(result['capabilities']['flightPhysics'])
        self.assertIn('No physical clearance', result['message'])

    def test_complete_requires_final_crew_report_and_refuses_further_inputs(self):
        self.advance_to('confirm')
        self.assertFalse(self.service.snapshot()['completed'])
        result = self.act()['snapshot']
        self.assertTrue(result['completed'])
        self.assertEqual(result['status'], 'complete')
        self.assertIsNone(result['currentStep'])
        self.assertEqual(result['completedStepIds'], ['closeout', 'guidance', 'ready', 'release', 'confirm'])
        before = self.service.snapshot()
        with self.assertRaises(ControlError) as caught:
            self.service.action(before['sessionId'], 6, before['revision'], 'CMP', 'confirm', 'CONFIRMED')
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(before, self.service.snapshot())

    def test_stale_sequence_revision_and_identity_do_not_change_state(self):
        original = self.service.snapshot()
        self.act()
        self.assert_rejected_without_mutation(409, sequence=0)
        self.assert_rejected_without_mutation(409, expectedRevision=original['revision'])
        self.assert_rejected_without_mutation(409, sessionId='previous-tab')

    def test_restart_invalidates_old_tab_and_resets_model_not_historical_evidence(self):
        self.act()
        old = self.service.snapshot()
        fresh = self.service.start()
        self.assertNotEqual(old['sessionId'], fresh['sessionId'])
        self.assertEqual(fresh['attachment'], 'docked')
        self.assertEqual(fresh['completedStepIds'], [])
        self.assertEqual(fresh['events'], [])
        self.assert_rejected_without_mutation(409, sessionId=old['sessionId'])

    def test_type_confusion_nonfinite_nested_and_boolean_sequences_reject(self):
        for field in ('sequence', 'expectedRevision'):
            for invalid in (True, 0.0, '0', None, -1, 2**31, [], {}):
                with self.subTest(field=field, value=invalid):
                    self.assert_rejected_without_mutation(400, **{field: invalid})
        for invalid in ([], {}, 1.0, float('nan'), '', 'x' * 161):
            with self.subTest(value=invalid):
                self.assert_rejected_without_mutation(400, value=invalid)
        # A scalar of the wrong type cannot acknowledge a string-valued report.
        self.assert_rejected_without_mutation(400, value=True)

    def test_shared_snapshot_and_definition_mutations_cannot_change_authority(self):
        state = self.service.snapshot()
        state['currentStep']['correctValue'] = 'BYPASS'
        state['completedStepIds'].append('release')
        state['controls']['guidance'] = 'AUTO'
        self.assert_rejected_without_mutation(400, value='BYPASS')
        self.assertEqual(self.service.snapshot()['controls']['guidance'], 'UNKNOWN')

    def test_two_concurrent_requests_at_same_revision_have_one_atomic_winner(self):
        original = self.service.snapshot()
        barrier, results = threading.Barrier(2), []
        def worker(sequence):
            barrier.wait()
            try:
                self.service.action(original['sessionId'], sequence, 0, 'LMP', 'closeout', 'CONFIRMED')
                results.append('accepted')
            except ControlError as error:
                results.append(error.status)
        workers = [threading.Thread(target=worker, args=(sequence,)) for sequence in (0, 1)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        self.assertCountEqual(results, ['accepted', 409])
        self.assertEqual(len(self.service.snapshot()['events']), 1)
        self.assertEqual(self.service.snapshot()['revision'], 1)

    def test_status_reads_are_copies_and_never_advance_time_or_checklist(self):
        before = self.service.snapshot()
        for _ in range(3):
            self.assertEqual(self.service.snapshot(), before)
        disabled = self.service.snapshot(enabled=False)
        self.assertFalse(disabled['available'])
        self.assertEqual(self.service.snapshot(), before)

    def test_missing_or_invalid_definition_disables_only_procedure_service(self):
        unavailable = ProcedureService(definition_path=ROOT / '.build/no-such-procedure.json')
        self.assertFalse(unavailable.available)
        self.assertFalse(unavailable.snapshot()['available'])
        with self.assertRaises(ControlError) as caught:
            unavailable.start()
        self.assertEqual(caught.exception.status, 503)
        invalid = definition()
        invalid['steps'][3]['role'] = 'CDR'
        self.assertFalse(ProcedureService(definition=invalid).available)

    def test_source_contract_rejects_unsourced_duplicate_or_unbounded_steps(self):
        for mutate in (lambda item: item['steps'][0].update(sourceIds=['invented']),
                       lambda item: item['steps'][1].update(id='closeout'),
                       lambda item: item['steps'][3].update(kind='select'),
                       lambda item: item.update(steps=[])):
            candidate = deepcopy(definition())
            mutate(candidate)
            with self.assertRaises(ValueError):
                validate_definition(candidate)

    def test_application_definition_keeps_cmp_probe_release_then_off_in_defined_order(self):
        service = ProcedureService()
        self.assertTrue(service.available, service.unavailable_reason)
        steps = service.definition['steps']
        release = next(step for step in steps if step.get('effect') == 'release')
        self.assertEqual(release['role'], 'CMP')
        self.assertEqual(release['kind'], 'momentary')
        self.assertEqual(release['correctValue'], 'EXTD/REL')
        release_index = steps.index(release)
        self.assertTrue(any(step['kind'] == 'select' and step.get('controlId') == release['controlId']
                            and step['correctValue'] == 'OFF' for step in steps[release_index + 1:]))
        state = service.start()
        for step in steps:
            self.assertEqual(state['currentStep']['id'], step['id'])
            if steps.index(step) <= release_index:
                self.assertEqual(state['attachment'], 'docked')
            state = service.action(state['sessionId'], state['lastSequence'] + 1,
                                   state['revision'], step['role'], step['id'],
                                   step['correctValue'])['snapshot']
        self.assertEqual(state['attachment'], 'released')
        self.assertTrue(state['completed'])
        self.assertEqual(state['controls'][release['controlId']], 'OFF')
        self.assertEqual(state['completedStepIds'], [step['id'] for step in steps])
        self.assertTrue(all(event['sourceIds'] and event['locator'] for event in state['events']))
        self.assertFalse(state['capabilities']['originalAgc'])
        self.assertFalse(state['capabilities']['flightPhysics'])


if __name__ == '__main__':
    unittest.main()
