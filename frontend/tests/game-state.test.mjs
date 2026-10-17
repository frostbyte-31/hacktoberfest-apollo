import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { CHALLENGES, createGameState, resetGame, updateGame, finishGame, notePilotInput,
  targetQuaternion, quaternionErrorDeg, quaternionErrorVectorDeg } from '../dist/game-state.mjs';

const execution = {modreg:0,imodes30:15889,imodes33:15360,dapbools:8910,failreg:[0,0,0]};
const startTime = 25.78125, horizon = 11.71875;
function update(t=0,q=[1,0,0,0],omega=[0,0,0],status='running',extra={}) {
  return {mode:'live',sessionId:'native-session-1',status,
    frame:{ready:status!=='stopped',execution,physical_time:startTime+t,
      remaining_time:Math.max(0,horizon-t),model:{quaternion:q,omega}},...extra};
}
function ready(config={}) {return updateGame(createGameState(config),update(0,undefined,undefined,'ready'));}
function near(actual,expected,tolerance=1e-8) {assert.ok(Math.abs(actual-expected)<tolerance,`${actual} ≠ ${expected}`);}

test('target rotations preserve quaternion convention and contain no roll objective',()=>{
  const yaw = targetQuaternion([1,0,0,0],3,0);
  near(quaternionErrorDeg([1,0,0,0],yaw),3);
  const vector = quaternionErrorVectorDeg([1,0,0,0],yaw);
  near(vector[0],3);near(vector[1],0);near(vector[2],0);
  const pitch = targetQuaternion([1,0,0,0],0,3);
  near(quaternionErrorVectorDeg([1,0,0,0],pitch)[1],3);
  assert.deepEqual(Object.keys(CHALLENGES),['yaw','pitch','combined']);
  for (const value of ['roll','toString','__proto__']) assert.throws(()=>createGameState({challenge:value}),/Unsupported challenge/);
});

test('relative quaternion errors handle sign-equivalent orientation and arbitrary reference frames',()=>{
  const base = targetQuaternion([1,0,0,0],40,30);
  const target = targetQuaternion(base,3,0);
  near(quaternionErrorDeg(base,target),3);
  near(quaternionErrorDeg(target,target.map(value=>-value)),0);
  const vector=quaternionErrorVectorDeg(base,target);
  near(vector[0],3);near(vector[1],0);near(vector[2],0);
  assert.equal(quaternionErrorDeg([0,0,0,0],target),null);
  assert.throws(()=>targetQuaternion([0,0,0,0],3,0),/Invalid/);
});

test('a genuine ready sample anchors a fixed target and waits without wall-clock progress',()=>{
  const state=ready({challenge:'yaw'});
  assert.equal(state.phase,'await-input');
  assert.equal(state.target.yawDeg,3);assert.equal(state.target.pitchDeg,0);
  assert.equal(state.metrics.elapsedSeconds,0);
  assert.equal(state.metrics.remainingSeconds,horizon);
  near(state.metrics.errorDeg,3);
  assert.strictEqual(updateGame(state,update(0,undefined,undefined,'ready')),state);
  const intent=notePilotInput(state,{yaw:1,pitch:0});
  assert.equal(intent.phase,'await-input');assert.equal(intent.metrics.elapsedSeconds,0);
  assert.deepEqual(intent.input,{yaw:1,pitch:0});
  assert.strictEqual(notePilotInput(state,{yaw:2,pitch:0}),state);
});

test('authoritative movement starts elapsed time; native angular rate units stay degrees/second',()=>{
  const state=updateGame(ready(),update(.1,undefined,[.4,.3,0]));
  assert.equal(state.phase,'running');near(state.metrics.elapsedSeconds,.1);
  near(state.metrics.rateDegS,.5);
  assert.equal(state.result,null);
});

test('success requires observed target acquisition and low rates over contiguous physical samples',()=>{
  let state=ready();const target=state.target.q;
  state=updateGame(state,update(.1,target));
  assert.equal(state.metrics.holdSeconds,0);assert.equal(state.phase,'running');
  for(const t of [.2,.3,.4])state=updateGame(state,update(t,target));
  assert.equal(state.phase,'running');
  state=updateGame(state,update(.5,target));
  assert.equal(state.phase,'result');assert.equal(state.result.outcome,'success');
  assert.equal(state.result.score,1000);assert.equal(state.bestScore,1000);
  // The target is a training mark. No state reducer changes backend orientation.
  near(quaternionErrorDeg(state.target.q,target),0);
});

test('duplicate polls, a frozen CPU, and a presentation timestamp cannot earn a hold',()=>{
  let state=ready();const target=state.target.q;
  state=updateGame(state,update(.1,target));
  for(let i=0;i<100;i++)state=updateGame(state,{...update(.1,target),wallTime:i*1000,renderTime:100});
  assert.equal(state.metrics.holdSeconds,0);assert.equal(state.result,null);
  near(state.metrics.elapsedSeconds,.1);
});

test('a large telemetry gap resets hold instead of assuming unobserved stability',()=>{
  let state=ready();const target=state.target.q;
  for(const t of [.1,.2,.3])state=updateGame(state,update(t,target));
  assert.ok(state.metrics.holdSeconds>.19);
  state=updateGame(state,update(2,target));
  assert.equal(state.metrics.holdSeconds,0);assert.equal(state.result,null);
});

test('high rate or leaving the target clears the measured hold',()=>{
  let state=ready();const target=state.target.q;
  for(const t of [.1,.2,.3])state=updateGame(state,update(t,target));
  state=updateGame(state,update(.4,target,[1.01,0,0]));
  assert.equal(state.metrics.holdSeconds,0);
  state=updateGame(state,update(.5,target));
  state=updateGame(state,update(.6,target));
  assert.ok(state.metrics.holdSeconds>.09);
  state=updateGame(state,update(.7));
  assert.equal(state.metrics.holdSeconds,0);assert.equal(state.result,null);
});

test('replay, absent telemetry, invalid data, and missing original readiness cannot grant success',()=>{
  const state=ready();
  const cases=[{...update(.1,state.target.q),mode:'replay'},
    {...update(.1),frame:null},
    {...update(.1),frame:{...update(.1).frame,physical_time:NaN}},
    {...update(.1),frame:{...update(.1).frame,model:{quaternion:[1,0,0,0],omega:[NaN,0,0]}}},
    {...update(.1),frame:{...update(.1).frame,execution:{...execution,failreg:[1,0,0]}}},
    {...update(.1),frame:{...update(.1).frame,ready:false}},
    {...update(.1),status:'disconnected'},
    {...update(.1),status:'fault'}];
  for(const value of cases){const next=updateGame(state,value);assert.equal(next.phase,'unavailable');assert.equal(next.result,null);assert.equal(next.bestScore,null);}
});

test('backward model time and changing orientation at a frozen time invalidate a run',()=>{
  const state=updateGame(ready(),update(.2));
  assert.equal(updateGame(state,update(.1)).phase,'unavailable');
  assert.equal(updateGame(state,update(.2,state.target.q)).phase,'unavailable');
  assert.equal(updateGame(state,update(.2,undefined,[1,0,0])).phase,'unavailable');
});

test('a stop cannot turn a near-target sample into success and horizon completion is a timeout',()=>{
  let state=ready();state=updateGame(state,update(.1,state.target.q));
  assert.equal(finishGame(state).result.outcome,'aborted');
  assert.equal(updateGame(state,{...update(.2),status:'stopping'}).result.outcome,'aborted');
  const stopped=updateGame(state,update(.5,state.target.q,[0,0,0],'stopped'));
  assert.equal(stopped.result.outcome,'aborted');assert.equal(stopped.bestScore,null);
  const timed=updateGame(state,update(horizon,state.target.q,[0,0,0],'stopped'));
  assert.equal(timed.result.outcome,'timeout');assert.equal(timed.bestScore,null);
});

test('new native sessions and resets clear the target and score while retaining an earned personal best',()=>{
  let state=ready({challenge:'pitch'});const target=state.target.q;
  for(const t of [.1,.2,.3,.4,.5])state=updateGame(state,update(t,target));
  const reset=resetGame(state,{challenge:'yaw'});
  assert.equal(reset.bestScore,1000);assert.equal(reset.metrics,null);assert.equal(reset.target,null);
  assert.equal(reset.config.challenge,'yaw');
  const fresh=updateGame(state,{...update(0,undefined,undefined,'ready'),sessionId:'native-session-2'});
  assert.equal(fresh.phase,'await-input');assert.equal(fresh.bestScore,1000);
  assert.equal(fresh.metrics.score,0);assert.equal(fresh.metrics.holdSeconds,0);
});

test('running state cannot silently define its own initial reference after missing the ready sample',()=>{
  const state=updateGame(createGameState(),update(.1));
  assert.equal(state.phase,'unavailable');assert.equal(state.target,null);
});

test('reducer and target calculations do not modify input snapshots or earlier game state',()=>{
  const state=ready(),input=update(.1,state.target.q),before=JSON.stringify({state,input});
  const next=updateGame(state,input);
  assert.equal(JSON.stringify({state,input}),before);
  next.lastSample.q[0]=0;
  assert.notEqual(input.frame.model.quaternion[0],0);
  assert.notEqual(state.lastSample.q[0],0);
});

test('training rule validation rejects impossible or nonfinite thresholds',()=>{
  for(const key of ['toleranceDeg','maxRateDegS','holdSeconds','maxSampleGapSeconds']) {
    for(const value of [0,-1,NaN,Infinity])assert.throws(()=>createGameState({[key]:value}),/Invalid challenge/);
  }
});

const nativeCases = [
  {challenge:'yaw',name:'yaw_short_pulse',report:'native-result.json'},
  {challenge:'pitch',name:'pitch_short_pulse',report:'native-result.json'},
  {challenge:'combined',name:'combined_short_pulse',report:'native-combined-result.json'},
];
const evidenceUrl = name => new URL(`../../docs/frontend-game-evidence/${name}`,import.meta.url);
const readinessEvidence = JSON.parse(readFileSync(evidenceUrl('readiness-metadata.json'),'utf8'));
function capturedCase(fixture) {
  const bytes = readFileSync(evidenceUrl(fixture.report));
  const report = JSON.parse(bytes);
  const readback = readinessEvidence.cases[fixture.name];
  const record = report.cases[fixture.name];
  assert.equal(createHash('sha256').update(bytes).digest('hex'),readback.sourceReport.sha256,
    'Readiness extraction must identify this exact retained report.');
  assert.equal(readback.sourceTrace.sha256,record.trace.sha256);
  assert.equal(readback.verifiedStartup,true);
  assert.equal(readback.actualStartupCheckpoint.verified,true);
  assert.equal(readback.actualStartupCheckpoint.category,'agc_diagnostic_readback');
  assert.deepEqual(readback.execution,readback.actualStartupCheckpoint.registers);
  assert.equal(readback.readbackCycle,record.frames[0].cycle);
  assert.equal(record.input.durationCycles,34133);
  assert.equal(record.nativeSummary.state_writes,0);
  assert.equal(record.frames[0].originalReady,true);
  assert.equal(record.frames.at(-1).originalReady,false);
  return {record,readback};
}
function capturedUpdate(fixture,record,readback,index) {
  const sample = record.frames[index];
  // Test-only envelope: attitude, rates and clocks are captured native data.
  // The exact startup diagnostic is the initial readiness fixture. Subsequent
  // compact records retain originalReady, not fresh per-frame register dumps.
  // This validates scoring against the captured trajectory; production replay
  // never adapts recordings into a live session and cannot earn achievements.
  return {mode:'live',sessionId:`captured-scoring-test-${fixture.name}`,
    status:index===0 ? 'ready' : sample.originalReady ? 'running':'stopped',
    frame:{ready:sample.originalReady,execution:readback.execution,
      physical_time:sample.physicalTimeSeconds,remaining_time:sample.remainingSeconds,
      model_cycle:sample.modelCycle,cycle:sample.cycle,
      sim_time:sample.cpuTimeSeconds,interactive_time:sample.interactiveTimeSeconds,
      model:{quaternion:sample.quaternionWxyz,omega:sample.bodyRatesDegreesPerSecond}}};
}

for (const fixture of nativeCases) {
  test(`actual captured ${fixture.challenge} short-pulse attitude achieves the training target before the CPU settlement tail`,()=>{
    const {record,readback} = capturedCase(fixture);
    let state = createGameState({challenge:fixture.challenge});
    let acquired = null, acquiredSample = null;
    for (let index=0;index<record.frames.length;index++) {
      state = updateGame(state,capturedUpdate(fixture,record,readback,index));
      if (state.result?.outcome==='success' && !acquired) {
        acquired=state;acquiredSample=record.frames[index];
      }
    }
    assert.ok(acquired,'The real recorded maneuver must support this advertised training objective.');
    assert.equal(state.result.outcome,'success');
    assert.strictEqual(state,acquired,'Later physical evolution and CPU settlement cannot improve the earned result.');
    assert.equal(acquiredSample.originalReady,true);
    assert.ok(acquiredSample.remainingSeconds>0);
    assert.ok(state.metrics.errorDeg<=state.config.toleranceDeg);
    assert.ok(state.metrics.rateDegS<=state.config.maxRateDegS);
    assert.ok(state.metrics.holdSeconds>=state.config.holdSeconds);
    assert.deepEqual(state.lastSample.q,acquiredSample.quaternionWxyz);
    assert.deepEqual(state.lastSample.omega,acquiredSample.bodyRatesDegreesPerSecond);
    near(state.metrics.elapsedSeconds,
      acquiredSample.physicalTimeSeconds-record.frames[0].physicalTimeSeconds);
    assert.equal(state.bestScore,state.result.score);
  });
}

test('captured completion with no achieved hold times out using physical epochs, excluding the real CPU settlement tail',()=>{
  const fixture=nativeCases[2], {record,readback}=capturedCase(fixture);
  let state=createGameState({challenge:fixture.challenge,holdSeconds:100});
  for(let index=0;index<record.frames.length;index++) {
    state=updateGame(state,capturedUpdate(fixture,record,readback,index));
  }
  const first=record.frames[0], final=record.frames.at(-1);
  assert.equal(state.result.outcome,'timeout');assert.equal(state.bestScore,null);
  assert.equal(state.metrics.holdSeconds,0);
  near(state.metrics.elapsedSeconds,final.physicalTimeSeconds-first.physicalTimeSeconds);
  assert.ok(final.cpuTimeSeconds>final.physicalTimeSeconds);
  assert.ok(final.cycle>final.modelCycle);
  assert.ok(Math.abs(state.metrics.elapsedSeconds-final.interactiveTimeSeconds)>.01,
    'The native CPU settlement clock must not become physical elapsed time.');
  const score=state.result.score, elapsed=state.metrics.elapsedSeconds;
  state=updateGame(state,capturedUpdate(fixture,record,readback,record.frames.length-1));
  assert.equal(state.result.score,score);assert.equal(state.metrics.elapsedSeconds,elapsed);
});
