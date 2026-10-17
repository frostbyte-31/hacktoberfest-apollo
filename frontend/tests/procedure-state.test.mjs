import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { RecordedTraceProvider } from '../dist/mission-provider.mjs';
import { buildProcedure, procedureSelection } from '../dist/procedure-state.mjs';
import { labControlGuidance, stickDirections } from '../dist/control-guidance.mjs';

const provider=new RecordedTraceProvider(JSON.parse(readFileSync(new URL('../dist/data/guidance.json',import.meta.url),'utf8')));

test('every procedure item comes from its own retained scenario event and cannot execute a command',()=>{
  for(const scenario of provider.listScenarios()){
    const steps=buildProcedure(provider,scenario.id);
    assert.equal(steps.length,8);
    for(const step of steps){
      const original=provider.getScenario(scenario.id).events.find(event=>event.id===step.event.id);
      assert.ok(original);assert.equal(step.event.t,original.t);assert.equal(step.event.source.rawLine,original.source.rawLine);
      assert.equal(step.commandAvailable,false);assert.equal(step.classification,'recorded experiment observation');
    }
  }
});
test('nominal and altitude variants reach their actual review display without substituting final digits',()=>{
  for(const id of ['nominal','altitude-16km']){
    const selection=procedureSelection(provider,id,7);
    assert.equal(selection.step.event.id,'crew-review');assert.equal(selection.atBoundary,true);
    const exact=provider.getSnapshot(id,selection.step.event.t);
    assert.deepEqual(selection.snapshot.dsky,exact.dsky);
    assert.equal(selection.snapshot.guidance.ignitionTime.value,id==='nominal'?360.29:360.44);
    assert.equal(selection.commandSent,false);assert.equal(selection.flightCompleted,false);
  }
});
test('P63 program entry retains the genuinely lagging P00 display instead of inventing P63 digits',()=>{
  const selected=procedureSelection(provider,'nominal',5);
  assert.equal(selected.step.event.id,'p63');
  assert.equal(selected.snapshot.frame.stage,'P63 pre-ignition guidance');
  assert.equal(selected.snapshot.dsky.PROG,'00');
  assert.equal(selected.snapshot.dsky.VERB,'37');
  assert.equal(selected.snapshot.dsky.NOUN,'63');
});
test('negative control exposes the actual failure and never fabricates crew review or ignition',()=>{
  const steps=buildProcedure(provider,'missing-site');
  assert.equal(steps[6].event.id,'root-failure');assert.equal(steps[7].event.id,'alarm-01406');
  const selected=procedureSelection(provider,'missing-site',7);
  assert.ok(selected.snapshot.guidance.alarms.includes('01406'));
  assert.equal(selected.snapshot.guidance.ignitionTime.value,null);assert.equal(selected.flightCompleted,false);
});
test('briefing contains unknown DSKY digits and cannot be mistaken for a completed action',()=>{
  const selected=procedureSelection(provider,'nominal');
  assert.equal(selected.step,null);assert.equal(selected.snapshot.dsky.availability,'unavailable');
  assert.equal(selected.snapshot.dsky.PROG,'??');assert.equal(selected.commandSent,false);
  assert.throws(()=>procedureSelection(provider,'nominal',8),/Invalid/);
  assert.throws(()=>procedureSelection(provider,'nominal',.5),/Invalid/);
});
test('a missing required event fails rather than skipping a procedure checkpoint',()=>{
  assert.throws(()=>buildProcedure({getEvents:()=>[]},'nominal'),/Missing recorded/);
});
test('lab directional cue uses body relative error rather than camera orientation',()=>{
  const config={toleranceDeg:1,maxRateDegS:1};
  assert.deepEqual(labControlGuidance({errorVectorDeg:[3,-2,0],errorDeg:3.6,rateDegS:0},config).keys,['yaw+','pitch-']);
  assert.deepEqual(labControlGuidance({errorVectorDeg:[-3,2,0],errorDeg:3.6,rateDegS:0},config).keys,['yaw-','pitch+']);
  assert.deepEqual(labControlGuidance(null,config).keys,[]);
  assert.match(labControlGuidance({errorVectorDeg:[0,0,2],errorDeg:2,rateDegS:0},config).text,/unsupported roll/);
  assert.match(labControlGuidance({errorVectorDeg:[.2,.1,0],errorDeg:.3,rateDegS:2},config).text,/countersteer/);
});
test('illustrative controller quantizes only existing supported axes with a neutral deadband',()=>{
  assert.deepEqual(stickDirections(0,0),{yaw:0,pitch:0});
  assert.deepEqual(stickDirections(.1,-.2),{yaw:0,pitch:0});
  assert.deepEqual(stickDirections(.8,-.8),{yaw:1,pitch:1});
  assert.deepEqual(stickDirections(-.8,.8),{yaw:-1,pitch:-1});
  assert.throws(()=>stickDirections(NaN,0),/Invalid/);
});
