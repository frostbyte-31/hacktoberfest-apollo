import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildSessionSummary } from '../dist/session-summary.mjs';
import { createCrewSetup, updateHumanParticipation } from '../dist/crew-setup.mjs';

// The real modern service produces every fixture and enforces the retained
// definition. This runs no emulator, plant, flight physics or historical harness.
const script = `
import json
from backend.procedure_service import ProcedureService
s=ProcedureService()
idle=s.snapshot()
started=s.start()
partial=None
for index,step in enumerate(s.definition['steps']):
    if step['id']=='lm-guidance':
        state=s.snapshot()
        s.action(state['sessionId'],state['lastSequence']+1,state['revision'],step['role'],step['id'],'PGNS')
    state=s.snapshot()
    s.action(state['sessionId'],state['lastSequence']+1,state['revision'],step['role'],step['id'],step['correctValue'])
    if index==5: partial=s.snapshot()
print(json.dumps({'idle':idle,'started':started,'partial':partial,'complete':s.snapshot()}))
`;
const actual = JSON.parse(execFileSync('python3',['-B','-c',script],{
  cwd:fileURLToPath(new URL('../../',import.meta.url)),encoding:'utf8',
}));
const clone = value => JSON.parse(JSON.stringify(value));

test('real completed procedure derives a portable training receipt without claiming flight completion', () => {
  const result = buildSessionSummary(actual.complete, createCrewSetup());
  assert.equal(result.schemaVersion, 1);
  assert.equal(result.classification, 'INTERACTIVE PROCEDURE TRAINER');
  assert.equal(result.completedActionCount, 28);
  assert.equal(result.eventCount, 29);
  assert.equal(result.wrongSelections, 1);
  assert.equal(result.crewReportCount, 9);
  assert.equal(result.controlCommandCount, 20);
  assert.equal(result.sourceSha256, actual.complete.definitionSha256);
  assert.equal(result.nextOperation, 'Relative-motion management and Eagle inspection');
  assert.equal(result.flightSimulationCompleted, false);
  assert.equal(result.originalAgcExecuted, false);
  assert.deepEqual(result.crewRoster.map(seat => [seat.role,seat.participant,seat.vehicle]), [
    ['CDR','human','Eagle'],['LMP','human','Eagle'],['CMP','human','Columbia'],
  ]);
});

test('coherent idle, started and partial modern sessions do not receive a completion report', () => {
  for (const snapshot of [actual.idle, actual.started, actual.partial]) {
    assert.equal(buildSessionSummary(snapshot,createCrewSetup()), null);
  }
});

test('report is immutable, contains no tokens or session identity, and does not mutate its inputs', () => {
  const snapshot = clone(actual.complete), before = clone(snapshot);
  snapshot.token = 'do-not-export'; snapshot.headers = {'X-Apollo-Token':'do-not-export'};
  const result = buildSessionSummary(snapshot,createCrewSetup('human-crew'));
  assert.equal(result.humanParticipation,'shared-device');
  assert.equal(JSON.stringify(result).includes('do-not-export'),false);
  assert.equal(JSON.stringify(result).includes(snapshot.sessionId),false);
  for (const key of ['sessionId','events','wallUtc','missionClock','score','token','headers','capabilities']) {
    assert.equal(Object.hasOwn(result,key),false);
  }
  delete snapshot.token; delete snapshot.headers;
  assert.deepEqual(snapshot,before);
  assert.ok(Object.isFrozen(result)); assert.ok(Object.isFrozen(result.crewRoster[0]));
  assert.throws(()=>{result.crewRoster[0].participant='ai';},TypeError);
});

test('AI, remote and malformed crew configurations cannot appear as supported local crew', () => {
  for (const setup of [createCrewSetup('commander-ai'), updateHumanParticipation(createCrewSetup(),'network'), {}]) {
    assert.throws(()=>buildSessionSummary(actual.complete,setup),/local human crew/);
  }
});

test('inconsistent completion, release and source metadata fail instead of producing a summary', () => {
  const changes = [
    {status:'active'}, {completed:false}, {currentStepIndex:27}, {currentStep:{id:'inspection-handoff'}},
    {attachment:'docked'}, {attachmentEvidence:'sensor-observation'},
    {definitionSha256:'not-a-hash'}, {definitionSha256:'b'.repeat(64)},
    {completedStepIds:actual.complete.completedStepIds.slice(0,27)},
    {revision:28}, {lastSequence:50},
  ];
  for(const change of changes) assert.throws(()=>buildSessionSummary({...clone(actual.complete),...change},createCrewSetup()),/Invalid/);
});

test('missing, reordered, duplicated and cross-session acknowledgements fail closed', () => {
  for (const mutate of [
    value=>{value.events.splice(2,1);},
    value=>{[value.events[0],value.events[1]]=[value.events[1],value.events[0]];},
    value=>{value.events[1].sequence=value.events[0].sequence;},
    value=>{value.events[3].sessionId='other-session';},
    value=>{value.events[3].action='skipped-check';},
    value=>{value.events[3].advanced='true';},
    value=>{value.events[0].evidenceKind='sensor-readback';},
    value=>{value.events[0].sourceIds=[];},
    value=>{value.events[0].locator='';},
  ]) {
    const value=clone(actual.complete);mutate(value);
    assert.throws(()=>buildSessionSummary(value,createCrewSetup()),/Invalid training summary/);
  }
});

test('an invalid release command or powered-probe handoff cannot count as completed undocking', () => {
  for(const mutate of [
    value=>{value.events.find(event=>event.action==='csm-release-probe').role='CDR';},
    value=>{value.events.find(event=>event.action==='csm-release-probe').value='RETRACT';},
    value=>{value.events.find(event=>event.action==='csm-probe-off').value='EXTD/REL';},
    value=>{value.events.find(event=>!event.advanced).kind='crew-report';},
  ]) {
    const value=clone(actual.complete);mutate(value);
    assert.throws(()=>buildSessionSummary(value,createCrewSetup()),/Invalid training summary/);
  }
});

test('AGC, live flight, replay and inferred telemetry cannot be repackaged as procedure completion', () => {
  for(const change of [
    {mode:'LIVE AGC EXECUTION'}, {classification:'VERIFIED RECORDED EXECUTION'},
    {positionM:[0,0,0]}, {missionClock:100},
    {capabilities:{...actual.complete.capabilities,originalAgc:true}},
  ]) assert.throws(()=>buildSessionSummary({...clone(actual.complete),...change},createCrewSetup()),/Invalid procedure snapshot/);
});
