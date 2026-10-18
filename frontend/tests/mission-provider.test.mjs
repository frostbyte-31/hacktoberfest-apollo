import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { RecordedTraceProvider, LiveBackendProvider, CREW_ROLES, MISSION_CAPABILITIES } from '../dist/mission-provider.mjs';

const recording = JSON.parse(readFileSync(new URL('../dist/data/guidance.json', import.meta.url), 'utf8'));
const provider = new RecordedTraceProvider(recording);
const response = value => ({ok:true,status:200,json:async()=>value});
const clone = () => JSON.parse(JSON.stringify(recording));

// These are presentation-contract tests against retained data, not native AGC execution claims.
test('recorded provider preserves actual three scenarios and trace fingerprints', () => {
  assert.deepEqual(provider.recording, recording);
  assert.deepEqual(provider.recording.cases.map(c=>c.id), ['nominal','altitude-16km','missing-site']);
  const snapshot=provider.getSnapshot('nominal',227.62208203125002);
  assert.equal(snapshot.mode,'VERIFIED_RECORDED_EXECUTION');
  assert.equal(snapshot.source.sha256,'6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2');
  assert.equal(snapshot.source.rawLine,41026);
  assert.equal(snapshot.dsky.digits.PROG,'63');
  assert.equal(snapshot.dsky.digits.VERB,'06');
  assert.equal(snapshot.dsky.digits.NOUN,'61');
  assert.equal(snapshot.guidance.observedRootCount,9);
});

test('provider defensively copies and deeply freezes validated data and snapshots', () => {
  const caller=clone();const fresh=new RecordedTraceProvider(caller);
  caller.cases[0].frames[0].dsky.PROG='99';
  assert.equal(fresh.recording.cases[0].frames[0].dsky.PROG,'??');
  assert.throws(()=>{fresh.recording.cases[0].frames[0].dsky.PROG='99';},TypeError);
  assert.throws(()=>{fresh.recording=null;},TypeError);
  const state=fresh.getSnapshot('nominal',0);
  assert.throws(()=>{state.spacecraft.position.value[0]=0;},TypeError);
});

test('sample-and-hold retains per-field evidence instead of interpolating clock or guidance', () => {
  const scenario=provider.getScenario('nominal');
  const index=scenario.frames.findIndex((f,i)=>i>0&&f.t>scenario.frames[i-1].t+0.001&&scenario.frames[i-1].observedClockSeconds!==null);
  assert.ok(index>0);
  const earlier=scenario.frames[index-1],later=scenario.frames[index];
  const time=(earlier.t+later.t)/2;
  const state=provider.getSnapshot('nominal',time);
  assert.equal(state.replayElapsedSeconds,time);
  assert.equal(state.observedFrameSeconds,earlier.t);
  assert.equal(state.missionClock.value,earlier.observedClockSeconds);
  assert.equal(state.missionClock.source.cycle,earlier.observationSources.clock.cycle);
  assert.equal(state.guidance.timeToGo.value,earlier.signedTimeToGoSeconds);
  assert.deepEqual(state.frame,earlier);
});

test('absolute ignition time, signed time to go and solution lead remain distinct', () => {
  const state=provider.getSnapshot('nominal',1e6);
  assert.equal(state.guidance.ignitionTime.value,360.29);
  assert.equal(state.guidance.ignitionTime.unit,'s GET');
  assert.equal(state.guidance.timeToGo.value,-582.7947216796875);
  assert.equal(state.guidance.ignitionLeadAtSolution.value,139.03);
  assert.equal(state.missionClock.value,221.26);
  assert.ok(state.missionClock.value!==state.replayElapsedSeconds);
});

test('static three-dimensional state discloses frame, units, separate epochs and no propagation', () => {
  const start=provider.getSnapshot('nominal',0),end=provider.getSnapshot('nominal',1e6);
  assert.deepEqual(start.spacecraft,end.spacecraft);
  assert.equal(start.spacecraft.propagation,'NONE');
  assert.equal(start.spacecraft.position.unit,'m');
  assert.equal(start.spacecraft.velocity.unit,'m/s');
  assert.equal(start.spacecraft.position.epochSeconds,120);
  assert.equal(start.spacecraft.landingSite.epochSeconds,784.4);
  assert.equal(start.spacecraft.position.value.length,3);
  assert.match(start.spacecraft.position.coordinateFrame,/Moon-centered basic REF inertial/);
  assert.equal(start.spacecraft.landingSite.source.classification,'INDEPENDENT_PROJECTION');
  assert.equal(start.spacecraft.position.mode,'STATIC_EDUCATIONAL_ILLUSTRATION');
});

test('missing-site scenario reports authentic failure, unavailable target and no ignition result', () => {
  const state=provider.getSnapshot('missing-site',1e6);
  assert.equal(state.spacecraft.landingSite.value,null);
  assert.equal(state.spacecraft.landingSite.availability,'UNAVAILABLE');
  assert.equal(state.guidance.ignitionTime.value,null);
  assert.equal(state.guidance.ignitionTime.availability,'UNAVAILABLE');
  assert.ok(state.guidance.alarms.includes('01406'));
  assert.equal(state.guidance.observedRootCount,3);
});

test('DSKY digit strings are unchanged and undecoded light states are unavailable', () => {
  const start=provider.getSnapshot('nominal',0),end=provider.getSnapshot('nominal',1e6);
  assert.equal(start.dsky.digits.PROG,'??');
  assert.deepEqual(end.dsky.digits,recording.cases[0].result.finalDsky);
  assert.equal(end.dsky.signLights.availability,'UNAVAILABLE');
  assert.equal(end.dsky.indicatorLights.availability,'UNAVAILABLE');
  assert.equal(end.dsky.source.sha256,end.source.sha256);
});

test('events include only actual observations at or before replay cursor', () => {
  const state=provider.getSnapshot('nominal',100);
  assert.ok(state.events.length>0);
  assert.ok(state.events.every(event=>event.t<=100));
  assert.ok(state.events.every(event=>event.evidence.rawLine===event.source.rawLine));
  assert.deepEqual(state.events.map(({mode,evidence,...event})=>event),recording.cases[0].events.filter(event=>event.t<=100));
});

test('scenario comparison uses final retained outcomes independently of current cursor', () => {
  const comparison=provider.compareScenarios();
  assert.equal(comparison.length,3);
  assert.deepEqual(comparison.map(item=>item.ignitionTimeSeconds),[360.29,360.44,null]);
  assert.deepEqual(comparison.map(item=>item.reviewReached),[true,true,false]);
  assert.deepEqual(comparison.map(item=>item.rootCount),[9,9,3]);
  assert.equal(provider.getSnapshot('nominal',0).guidance.observedRootCount,0);
  assert.equal(comparison[0].mode,'VERIFIED_RECORDED_EXECUTION');
});

test('unknown scenarios, invalid time, missing provenance and extra scenarios are rejected', () => {
  assert.throws(()=>provider.getScenario('unverified'),/Unknown/);
  assert.throws(()=>provider.getSnapshot('nominal',NaN),/Invalid replay time/);
  const bad=clone();bad.cases[0].frames[10].observationSources.clock=null;
  assert.throws(()=>new RecordedTraceProvider(bad),/source/);
  const extra=clone();extra.cases.push({...extra.cases[0],id:'fabricated'});
  assert.throws(()=>new RecordedTraceProvider(extra),/exactly three/);
  const badFrame=clone();badFrame.cases[0].initialState.positionFrame='';
  assert.throws(()=>new RecordedTraceProvider(badFrame),/coordinate-frame/);
});

test('recorded loading performs GET and reports HTTP or malformed data failures', async () => {
  const calls=[];
  const loaded=await RecordedTraceProvider.load({fetchImpl:async(path,init)=>{calls.push([path,init.method]);return response(recording);}});
  assert.deepEqual(calls,[['./data/guidance.json','GET']]);
  assert.deepEqual(loaded.compareScenarios(),provider.compareScenarios());
  await assert.rejects(RecordedTraceProvider.load({fetchImpl:async()=>({ok:false,status:404,json:async()=>({})})}),/HTTP 404/);
  await assert.rejects(RecordedTraceProvider.load({fetchImpl:async()=>response({})}),/Unsupported guidance recording/);
});

test('live discovery reads existing endpoints only and never starts a native session or publishes token', async () => {
  const calls=[];
  const live=new LiveBackendProvider({fetchImpl:async(path,init)=>{
    calls.push([path,init.method]);
    return response(path==='/api/bootstrap'?{liveEnabled:true,axes:['yaw','pitch'],token:'private-control-token'}:{status:'idle',sessionId:null,frame:null,message:'No native session started.'});
  }});
  const status=await live.discover();
  assert.deepEqual(calls,[['/api/bootstrap','GET'],['/api/status','GET']]);
  assert.equal(status.liveEnabled,true);
  assert.equal(status.available,true);
  assert.equal(status.status,'idle');
  assert.equal(status.capabilities.find(cap=>cap.id==='live-attitude').availability,'AVAILABLE');
  assert.equal(status.capabilities.find(cap=>cap.id==='live-guidance').availability,'UNAVAILABLE');
  assert.ok(!JSON.stringify(status).includes('private-control-token'));
  assert.equal(live.command({program:'P63'}).status,'UNSUPPORTED');
  assert.equal(calls.length,2);
});

test('replay-only discovery distinguishes available status service from disabled live execution', async () => {
  const live=new LiveBackendProvider({fetchImpl:async(path)=>response(path==='/api/bootstrap'?{liveEnabled:false,axes:['yaw','pitch'],token:null}:{status:'idle',sessionId:null,frame:null})});
  const status=await live.discover();
  assert.equal(status.available,true);
  assert.equal(status.liveEnabled,false);
  assert.equal(status.capabilities.find(cap=>cap.id==='live-attitude').availability,'UNAVAILABLE');
  assert.equal(status.capabilities.find(cap=>cap.id==='guidance-replay').availability,'AVAILABLE');
  assert.equal((await live.getStatus()).mode,'LIVE_BACKEND_STATUS');
});

test('offline, invalid and failed-status backend data return explicit unavailability', async () => {
  const offline=new LiveBackendProvider({fetchImpl:async()=>{throw new Error('offline');}});
  assert.equal((await offline.discover()).available,false);
  assert.equal((await offline.getStatus()).attitudeFrame,null);
  const missing=new LiveBackendProvider({fetchImpl:async()=>({ok:false,status:404,json:async()=>({})})});
  assert.match((await missing.discover()).message,/HTTP 404/);
  const invalid=new LiveBackendProvider({fetchImpl:async()=>response({liveEnabled:true,axes:['roll']})});
  assert.equal((await invalid.discover()).available,false);
  const statusFailed=new LiveBackendProvider({fetchImpl:async(path)=>path==='/api/bootstrap'?response({liveEnabled:true,axes:['yaw','pitch']}):response({status:'idle'})});
  const failedStatus=await statusFailed.discover();
  assert.equal(failedStatus.available,false);
  assert.equal(failedStatus.capabilities.find(cap=>cap.id==='live-attitude').availability,'UNAVAILABLE');
});

test('crew metadata contains exactly three correct positions without active multiplayer or AI', () => {
  assert.deepEqual(CREW_ROLES.map(crew=>crew.name),['Neil Armstrong','Buzz Aldrin','Michael Collins']);
  assert.match(CREW_ROLES[2].location,/Command Module in lunar orbit/);
  assert.ok(CREW_ROLES.every(crew=>crew.availability==='PLANNED'));
  assert.ok(CREW_ROLES.every(crew=>crew.participantTypes.join(',')==='HUMAN,AI'));
  assert.equal(new Set(CREW_ROLES.map(crew=>crew.id)).size,3);
  assert.equal(MISSION_CAPABILITIES.find(cap=>cap.id==='ai-crew').availability,'PLANNED');
  assert.equal(MISSION_CAPABILITIES.find(cap=>cap.id==='propulsion').availability,'UNAVAILABLE');
});


test('default browser transport preserves Window.fetch receiver for recording and discovery', async () => {
  const originalFetch=globalThis.fetch;
  const calls=[];
  // Browser WebIDL fetch implementations may reject any receiver other than their Window.
  globalThis.fetch=async function(path,init) {
    assert.equal(this,globalThis,'native fetch must retain its global receiver');
    calls.push([path,init.method]);
    if(path==='./data/guidance.json')return response(recording);
    return response(path==='/api/bootstrap'?{liveEnabled:false,axes:['yaw','pitch']}:{status:'idle',sessionId:null,frame:null});
  };
  try {
    assert.equal((await RecordedTraceProvider.load()).getScenario('nominal').id,'nominal');
    assert.equal((await new LiveBackendProvider().discover()).available,true);
    assert.deepEqual(calls,[['./data/guidance.json','GET'],['/api/bootstrap','GET'],['/api/status','GET']]);
  } finally { globalThis.fetch=originalFetch; }
});

test('injected fetch transport is never invoked with the provider as its receiver', async () => {
  let calls=0;
  const live=new LiveBackendProvider({fetchImpl:async function(path) {
    assert.equal(this,undefined,'transport injection must not change its receiver');
    calls++;
    return response(path==='/api/bootstrap'?{liveEnabled:false,axes:['yaw','pitch']}:{status:'idle',sessionId:null,frame:null});
  }});
  assert.equal((await live.discover()).available,true);
  assert.equal(calls,2);
});
