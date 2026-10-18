import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {PropulsionTraceProvider,validatePropulsion,RECORDED_MODE,MISSION_CAPABILITIES,missionGate,observedCockpitSignals} from '../dist/propulsion-provider.mjs';

const data=JSON.parse(readFileSync(new URL('../dist/data/propulsion.json',import.meta.url),'utf8'));
const provider=new PropulsionTraceProvider(data);
const connected=provider.getCase('connected');
const clone=()=>structuredClone(data);
const changed=mutation=>{const value=clone();mutation(value);return value;};
const firstPhysical=connected.frames.find(frame=>frame.spacecraft);

test('provider accepts all four actual retained causal executions and preserves recorded source mode',()=>{
  assert.equal(validatePropulsion(data),data);
  assert.equal(provider.mode,RECORDED_MODE);
  assert.deepEqual(provider.listCases().map(item=>item.id),['connected','sink','no-feedback','repeat']);
  assert.equal(connected.sources.rawSha256,provider.getCase('repeat').sources.rawSha256);
  assert.equal(provider.getCase('sink').physicalEngineConnected,false);
  assert.equal(provider.getCase('no-feedback').sensorFeedbackConnected,false);
});

test('provider owns an immutable copy without freezing or mutating caller data',()=>{
  const supplied=clone(),originalTitle=supplied.cases[0].title;
  const independent=new PropulsionTraceProvider(supplied);
  assert.notEqual(independent.data,supplied);
  assert.equal(Object.isFrozen(supplied),false);
  supplied.cases[0].title='caller edit';
  assert.equal(independent.getCase('connected').title,originalTitle);
  assert.equal(Object.isFrozen(independent),true);
  assert.equal(Object.isFrozen(independent.listCases()),true);
  assert.equal(Object.isFrozen(independent.getCase('connected').frames),true);
  assert.throws(()=>{independent.data.cases[0].title='forged';},TypeError);
  const snapshot=independent.getSnapshot('connected',connected.durationSeconds);
  assert.equal(Object.isFrozen(snapshot),true);
  assert.equal(Object.isFrozen(snapshot.spacecraft.positionM),true);
  assert.throws(()=>{snapshot.spacecraft.positionM[0]=0;},TypeError);
});

test('snapshot holds actual samples between native observations without interpolation',()=>{
  const index=connected.frames.findIndex((frame,i)=>i>0&&frame.spacecraft&&connected.frames[i-1].spacecraft&&frame.spacecraft.source.cycle!==connected.frames[i-1].spacecraft.source.cycle);
  const before=connected.frames[index-1],after=connected.frames[index],time=(before.t+after.t)/2;
  const snapshot=provider.getSnapshot('connected',time);
  assert.equal(snapshot.frame,before);
  assert.equal(snapshot.spacecraft.positionM,before.spacecraft.positionM);
  assert.equal(snapshot.spacecraft.quaternion,before.spacecraft.quaternion);
  assert.notDeepEqual(snapshot.spacecraft.positionM,after.spacecraft.positionM);
  assert.equal(provider.getSnapshot('connected',after.t).frame,after);
  assert.equal(snapshot.replay.clock,'CPU-call elapsed; not historical GET');
  assert.equal(snapshot.spacecraft.coordinateFrame,'Moon-centered basic REF inertial');
  assert.equal(snapshot.spacecraft.units.position,'m');
  assert.equal(snapshot.spacecraft.units.velocity,'m/s');
});

test('physical state remains unavailable before its first actual observation',()=>{
  assert.equal(provider.getSnapshot('connected',0).spacecraft,null);
  assert.equal(provider.getSnapshot('connected',firstPhysical.t-1e-6).spacecraft,null);
  assert.deepEqual(provider.getSnapshot('connected',firstPhysical.t).spacecraft.positionM,firstPhysical.spacecraft.positionM);
  assert.deepEqual(provider.trajectoryThrough('connected',firstPhysical.t-1e-6),[]);
  assert.equal(provider.getSnapshot('connected',0).event,null);
});

test('no snapshot exposes an event or value whose source is after the requested clock',()=>{
  for(const item of provider.listCases()){
    for(const frame of item.frames){
      const snapshot=provider.getSnapshot(item.id,frame.t);
      assert.ok(snapshot.source.cycle<=frame.cycle);
      if(snapshot.event)assert.ok(snapshot.event.t<=frame.t);
      for(const source of Object.values(snapshot.frame.observationSources))if(source)assert.ok(source.cycle<=frame.cycle);
      if(snapshot.spacecraft)assert.ok(snapshot.spacecraft.source.cycle<=frame.cycle);
      if(snapshot.frame.receiver)assert.ok(snapshot.frame.receiver.source.cycle<=frame.cycle);
      if(snapshot.frame.pipa.source)assert.ok(snapshot.frame.pipa.source.cycle<=frame.cycle);
    }
  }
});

test('snapshot and trajectory requests respect native bounds and reject invalid times',()=>{
  assert.equal(provider.getSnapshot('connected',-100).frame,connected.frames[0]);
  assert.equal(provider.getSnapshot('connected',1e9).frame,connected.frames.at(-1));
  assert.deepEqual(provider.trajectoryThrough('connected',-1),[]);
  assert.deepEqual(provider.trajectoryThrough('connected',1e9),provider.trajectoryThrough('connected',connected.durationSeconds));
  for(const time of [NaN,Infinity,-Infinity,'300',undefined]){
    assert.throws(()=>provider.getSnapshot('connected',time),/Invalid execution time/);
    assert.throws(()=>provider.trajectoryThrough('connected',time),/Invalid execution time/);
  }
  assert.throws(()=>provider.getSnapshot('unknown',0),/Unknown retained execution/);
});

test('trajectory contains only observed physical endpoints through the requested instant',()=>{
  const until=connected.events.find(event=>event.title==='Original ENGINE ON output').t;
  const expected=[];let previous=-1;
  for(const frame of connected.frames){
    if(frame.t>until)break;
    if(frame.spacecraft&&frame.spacecraft.source.cycle!==previous){expected.push(frame.spacecraft.positionM);previous=frame.spacecraft.source.cycle;}
  }
  const trajectory=provider.trajectoryThrough('connected',until);
  assert.deepEqual(trajectory,expected);
  assert.ok(trajectory.length<provider.trajectoryThrough('connected',connected.durationSeconds).length);
  assert.notDeepEqual(trajectory.at(-1),connected.frames.at(-1).spacecraft.positionM);
  assert.equal(Object.isFrozen(trajectory[0]),true);
  trajectory.pop();
  assert.deepEqual(provider.trajectoryThrough('connected',until),expected);
});

test('active-low cockpit signals match actual crew-set channel words',()=>{
  const event=connected.events.find(event=>event.title==='Recorded cockpit discretes set');
  const frame=provider.getSnapshot('connected',event.t).frame;
  assert.equal(frame.crewDiscretes['030'].value,15595);
  assert.equal(frame.crewDiscretes['031'].value,20479);
  assert.equal(frame.crewDiscretes['033'].value,32735);
  const signals=observedCockpitSignals(frame);
  for(const name of ['pgns','autoThrottle','engineArmed','autoAttitude','radarPosition1']){
    assert.equal(signals[name].asserted,true);
    assert.ok(signals[name].source.cycle<=frame.cycle);
  }
  const disarmed=observedCockpitSignals(connected.frames.at(-1));
  assert.equal(disarmed.engineArmed.asserted,false);
});

test('missing or deasserted AUTO never invents ATT HOLD, OFF, AGS, or manual mode',()=>{
  const missing=observedCockpitSignals({crewDiscretes:{}});
  assert.deepEqual(missing,{pgns:null,autoThrottle:null,engineArmed:null,autoAttitude:null,radarPosition1:null});
  const value={value:0o77777,source:{rawLine:1,cycle:0}};
  const inactive=observedCockpitSignals({crewDiscretes:{'030':value,'031':value,'033':value}});
  assert.ok(Object.values(inactive).every(signal=>signal.asserted===false));
  for(const unsupported of ['attitudeHold','attitudeOff','ags','manualThrottle'])assert.equal(Object.hasOwn(inactive,unsupported),false);
});

test('capabilities prevent a historical mission start and do not enable synthetic live substitutes',async()=>{
  assert.equal(Object.isFrozen(MISSION_CAPABILITIES),true);
  assert.equal(missionGate().available,false);
  assert.equal(missionGate({...MISSION_CAPABILITIES,liveHistoricalInitialization:true}).available,false);
  assert.equal(missionGate({...MISSION_CAPABILITIES,liveUndocking:true}).available,false);
  assert.equal(missionGate({...MISSION_CAPABILITIES,liveHistoricalInitialization:true,liveUndocking:true}).available,true);
  assert.equal(missionGate({liveHistoricalInitialization:'false',liveUndocking:'true'}).available,false);
  assert.equal(missionGate(null).available,false);
  for(const capability of ['liveDsky','liveCockpitSwitches','liveThreeAxisAca','liveTtca','liveRod','livePoweredDescent','liveLanding'])assert.equal(provider.capabilities[capability],false);
  const result=await provider.command({type:'dsky',keys:'V37E63E'});
  assert.equal(result.accepted,false);
  assert.equal(result.status,'unavailable');
  assert.equal(result.mode,RECORDED_MODE);
  assert.match(result.reason,/No live cockpit command was sent/);
});

test('loading fetches only the recording with explicit cache and signal options',async()=>{
  const requests=[],controller=new AbortController();
  const loaded=await PropulsionTraceProvider.load('/data/propulsion.json',{signal:controller.signal,fetchImpl:async(url,options)=>{
    requests.push({url,options});return {ok:true,json:async()=>data};
  }});
  await loaded.command({type:'engine-arm'});
  assert.equal(requests.length,1);
  assert.equal(requests[0].url,'/data/propulsion.json');
  assert.deepEqual(requests[0].options,{cache:'no-store',signal:controller.signal});
  await assert.rejects(PropulsionTraceProvider.load('/missing',{fetchImpl:async()=>({ok:false,status:503})}),/could not load \(503\)/);
});

test('missing release fingerprints, unsafe trace paths, wrong units, and mode masquerading are rejected',()=>{
  for(const mutate of [
    value=>{delete value.provenance;},
    value=>{value.provenance.releaseSealSha256='';},
    value=>{value.provenance.emulatorRevision='unidentified emulator';},
    value=>{value.provenance.releaseSealPath='docs/../../private/checksums.json';},
    value=>{value.cases[0].sources.rawSha256='not a digest';},
    value=>{value.cases[0].sources.tracePath='https://example.com/trace';},
    value=>{value.units.position='km';},
    value=>{value.frames.position='body';},
    value=>{delete value.cases[0].initialGeometry.quaternionFrame;},
    value=>{value.mode='LIVE AGC EXECUTION';},
  ])assert.throws(()=>validatePropulsion(changed(mutate)),/Invalid propulsion recording/);
});

test('future-dated display, physical, receiver, hardware, and sensor sources are rejected',()=>{
  const index=data.cases[0].frames.findIndex(frame=>frame.spacecraft&&frame.receiver&&frame.pipa.source&&frame.crewDiscretes['030']);
  for(const mutate of [
    frame=>{frame.observationSources.dsky.cycle=frame.cycle+1;},
    frame=>{frame.spacecraft.source.cycle=frame.cycle+1;},
    frame=>{frame.receiver.source.cycle=frame.cycle+1;},
    frame=>{frame.crewDiscretes['030'].source.cycle=frame.cycle+1;},
    frame=>{frame.pipa.source.cycle=frame.cycle+1;},
  ])assert.throws(()=>validatePropulsion(changed(value=>mutate(value.cases[0].frames[index]))),/source|discrete/);
});

test('malformed event clocks, duplicate native frames, invalid attitudes, and nonphysical quantities are rejected',()=>{
  const index=data.cases[0].frames.findIndex(frame=>frame.spacecraft&&frame.receiver);
  for(const mutate of [
    value=>{value.cases[0].events[0].t=NaN;},
    value=>{value.cases[0].events[0].source.cycle=0;},
    value=>{value.cases[0].frames[1]=structuredClone(value.cases[0].frames[0]);},
    value=>{value.cases[0].frames[index].spacecraft.quaternion=[0,0,0,0];},
    value=>{value.cases[0].frames[index].spacecraft.fuelKg=-1;},
    value=>{value.cases[0].frames[index].spacecraft.deliveredThrustN=-1;},
    value=>{value.cases[0].frames[index].receiver.armed='true';},
  ])assert.throws(()=>validatePropulsion(changed(mutate)),/Invalid propulsion recording/);
});

test('event selection preserves exact row identity and never exposes a later held source in the same CPU cycle',()=>{
  for(const item of provider.listCases())for(const event of item.events){
    const snapshot=provider.getEventSnapshot(item.id,event.id);
    assert.equal(snapshot.event,event);
    assert.equal(snapshot.source.rawLine,event.source.rawLine);
    assert.equal(snapshot.frame,item.eventSnapshots[event.id]);
    assert.equal(snapshot.frame.cycle,event.cycle);
    assert.equal(snapshot.replay.seconds,event.t);
    assert.equal(Object.isFrozen(snapshot),true);
    const sources=[...Object.values(snapshot.frame.observationSources),snapshot.spacecraft?.source,snapshot.frame.receiver?.source,snapshot.frame.pipa.source,...Object.values(snapshot.frame.crewDiscretes).map(value=>value.source)];
    for(const source of sources.filter(Boolean)){
      assert.ok(source.cycle<=event.cycle);
      assert.ok(source.rawLine<=event.source.rawLine);
    }
  }
});

test('crew switch review precedes each of the three distinct active-low packets at one CPU timestamp',()=>{
  for(const item of provider.listCases()){
    const before=item.events.find(event=>event.title==='Crew switch review');
    const packetTitles=['Recorded hardware input · channel 030','Recorded hardware input · channel 031','Recorded hardware input · channel 033'];
    const packets=packetTitles.map(title=>item.events.find(event=>event.title===title));
    const snapshots=[before,...packets].map(event=>provider.getEventSnapshot(item.id,event.id));
    assert.ok(snapshots.every(snapshot=>snapshot.replay.seconds===before.t));
    const expected=[
      {engineArmed:false,autoThrottle:false,autoAttitude:false,radarPosition1:false},
      {engineArmed:true,autoThrottle:true,autoAttitude:false,radarPosition1:false},
      {engineArmed:true,autoThrottle:true,autoAttitude:true,radarPosition1:false},
      {engineArmed:true,autoThrottle:true,autoAttitude:true,radarPosition1:true},
    ];
    snapshots.forEach((snapshot,index)=>{
      const signals=observedCockpitSignals(snapshot.frame);
      for(const [key,value] of Object.entries(expected[index]))assert.equal(signals[key].asserted,value);
      if(index)assert.ok(snapshots[index-1].source.rawLine<snapshot.source.rawLine);
    });
    assert.equal(observedCockpitSignals(provider.getSnapshot(item.id,before.t).frame).engineArmed.asserted,true);
  }
});

test('event-scoped state and trajectory remain unavailable immediately before same-cycle plant initialization',()=>{
  for(const item of provider.listCases()){
    const review=item.events.find(event=>event.title==='P63 · pre-ignition review');
    const initialized=item.events.find(event=>event.title==='Physical state becomes available');
    assert.equal(review.t,initialized.t);
    const before=provider.getEventSnapshot(item.id,review.id),after=provider.getEventSnapshot(item.id,initialized.id);
    assert.equal(before.spacecraft,null);
    assert.deepEqual(provider.trajectoryThrough(item.id,before.replay.seconds,{rawLine:before.source.rawLine}),[]);
    assert.ok(after.spacecraft);
    assert.deepEqual(provider.trajectoryThrough(item.id,after.replay.seconds,{rawLine:after.source.rawLine}),[after.spacecraft.positionM]);
    assert.ok(before.source.rawLine<after.source.rawLine);
    assert.ok(provider.getSnapshot(item.id,review.t).spacecraft);
  }
});

test('same-cycle PIPA generation and counter delivery retain distinct recorded counter totals',()=>{
  const generated=connected.events.find(event=>event.title==='Physical acceleration produces PIPA counts');
  const delivered=connected.events.find(event=>event.title==='PIPA counter packet delivered');
  assert.equal(generated.t,delivered.t);
  const before=provider.getEventSnapshot('connected',generated.id),after=provider.getEventSnapshot('connected',delivered.id);
  assert.deepEqual(before.frame.pipa.generatedCounts,[1,0,0]);
  assert.deepEqual(before.frame.pipa.deliveredCounts,[0,0,0]);
  assert.deepEqual(after.frame.pipa.deliveredCounts,[1,0,0]);
  assert.ok(before.source.rawLine<after.source.rawLine);
});

test('tied final crew disarm and experiment finish remain separately selectable without future program sources',()=>{
  for(const item of provider.listCases()){
    const disarm=item.events.find(event=>event.title==='Crew disarm'),finish=item.events.at(-1);
    assert.equal(disarm.t,finish.t);
    const before=provider.getEventSnapshot(item.id,disarm.id),after=provider.getEventSnapshot(item.id,finish.id);
    assert.notEqual(before.event.id,after.event.id);
    assert.ok(before.source.rawLine<after.source.rawLine);
    assert.equal(before.frame.observationSources.program.rawLine,before.source.rawLine);
    assert.equal(after.frame.observationSources.program.rawLine,after.source.rawLine);
    assert.equal(before.frame.receiver.armed,false);
    assert.equal(after.frame.receiver.armed,false);
  }
  assert.throws(()=>provider.getEventSnapshot('connected','missing-event'),/Unknown retained event/);
});

test('missing event snapshots and same-cycle later-row substitutions are rejected',()=>{
  const review=data.cases[0].events.find(event=>event.title==='Crew switch review');
  const later=data.cases[0].events.find(event=>event.title==='Recorded hardware input · channel 030');
  for(const mutate of [
    value=>{delete value.cases[0].eventSnapshots[review.id];},
    value=>{value.cases[0].eventSnapshots[review.id]=structuredClone(value.cases[0].eventSnapshots[later.id]);},
    value=>{value.cases[0].eventSnapshots[review.id].crewDiscretes['030']=structuredClone(value.cases[0].eventSnapshots[later.id].crewDiscretes['030']);},
    value=>{value.cases[0].eventSnapshots[review.id].observationSources.program.rawLine=review.source.rawLine+1;},
  ])assert.throws(()=>validatePropulsion(changed(mutate)),/Invalid propulsion recording/);
  for(const rawLine of [NaN,-1,0,1.5,'43378'])assert.throws(()=>provider.trajectoryThrough('connected',review.t,{rawLine}),/Invalid source row/);
});
