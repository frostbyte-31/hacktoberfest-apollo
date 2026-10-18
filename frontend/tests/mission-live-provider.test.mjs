import test from 'node:test';
import assert from 'node:assert/strict';
import {MissionLiveProvider, ROLE_IDS, validateMission} from '../dist/mission-live-provider.mjs';
function state() {
  return {schemaVersion:1,id:'mission-1',runId:'run-1',title:'Synthetic training',mode:'EDUCATIONAL_PHYSICS_LAB',status:'lobby',revision:1,
    physics:{simTimeSeconds:0,tick:0,spacecraft:{positionM:[1753090,0,0],velocityMps:[0,0,0],accelerationMps2:[-1.6,0,0],angularVelocityRadps:[0,0,0],quaternionBodyToRef:[1,0,0,0],massKg:15000,fuelKg:8000,altitudeM:15000,verticalSpeedMps:0,horizontalSpeedMps:0,downrangeM:0,pitchDeg:0},engine:{enabled:false,throttle:0,thrustN:0,massFlowKgps:0,thrustVectorN:[0,0,0]}},
    crew:ROLE_IDS.map(id=>({id})),events:[],messages:[],you:{role:'commander',lastSequence:0,host:true}};
}
const storage = () => { const data=new Map();return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value)}; };
const response = (data,ok=true,status=200) => ({ok,status,json:async()=>data});
test('only actual versioned educational mission snapshots are accepted',()=>{
 assert.equal(validateMission(state()).mode,'EDUCATIONAL_PHYSICS_LAB');
 for (const change of [{schemaVersion:2},{mode:'LIVE_AGC_EXECUTION'},{status:'landed'},{revision:NaN}]) assert.throws(()=>validateMission({...state(),...change}));
});
test('missing or nonfinite physical state never becomes invented zero telemetry',()=>{
 for (const field of ['positionM','velocityMps','accelerationMps2']) {
  const invalid=state();invalid.physics.spacecraft[field]=[0,NaN,0];assert.throws(()=>validateMission(invalid));
 }
 const invalid=state();delete invalid.physics.spacecraft.fuelKg;assert.throws(()=>validateMission(invalid));
});
test('crew validation requires exactly the original three independent roles',()=>{
 const invalid=state();invalid.crew[2]={id:'commander'};assert.throws(()=>validateMission(invalid));
 const short=state();short.crew.pop();assert.throws(()=>validateMission(short));
});
test('capability discovery returns public capabilities without leaking bootstrap token',async()=>{
 const calls=[];const client=new MissionLiveProvider({storage:storage(),fetchImpl:async(path,init)=>{calls.push({path,init});return response({schemaVersion:1,token:'local-secret',capabilities:{physicsLab:true},scenarios:[],crewRoles:[]});}});
 const discovery=await client.discover();assert.equal(discovery.token,undefined);assert.equal(client.token,'local-secret');assert.equal(calls[0].path,'/api/v1/capabilities');assert.equal(calls[0].init.method,'GET');
});
test('creating a mission sends the specified crew modes and no spacecraft state',async()=>{
 const calls=[];const client=new MissionLiveProvider({storage:storage(),fetchImpl:async(path,init)=>{calls.push({path,init});return response({missionId:'mission-1',participantToken:'participant',snapshot:state()});}});client.token='local-secret';
 const payload={scenarioId:'training',name:'Pilot',role:'commander',crewModes:{commander:'human','lunar-module-pilot':'fallback','command-module-pilot':'fallback'}};
 await client.create(payload);assert.equal(calls[0].path,'/api/v1/missions');assert.deepEqual(JSON.parse(calls[0].init.body),payload);assert.equal(calls[0].init.headers['X-Apollo-Token'],'local-secret');assert.equal(calls[0].init.credentials,'same-origin');
});
test('joining encodes the mission identifier and stores participant identity',async()=>{
 const calls=[];const store=storage();const client=new MissionLiveProvider({storage:store,fetchImpl:async(path,init)=>{calls.push({path,init});return response({missionId:'mission-1',participantToken:'participant-secret',snapshot:state()});}});
 await client.join({missionId:'a/b',name:'Buzz',role:'lunar-module-pilot'});assert.equal(calls[0].path,'/api/v1/missions/a%2Fb/join');assert.equal(client.credentials.participantToken,'participant-secret');
 const restored=new MissionLiveProvider({storage:store});assert.deepEqual(restored.credentials,client.credentials);
});
test('commands are sequenced after the authoritative last sequence and carry current run identity',async()=>{
 const calls=[];const client=new MissionLiveProvider({storage:storage(),fetchImpl:async(path,init)=>{calls.push({path,init});const s=state();s.you.lastSequence=8;return response({accepted:true,sequence:8,revision:2,snapshot:s});}});
 client.remember({missionId:'mission-1',participantToken:'private',snapshot:state()});const latest=state();latest.you.lastSequence=7;latest.runId='run-2';client.accept(latest);
 await client.command('controls',{throttle:.4,pitch:-1});const body=JSON.parse(calls[0].init.body);assert.equal(body.sequence,8);assert.equal(body.runId,'run-2');assert.deepEqual(body.payload,{throttle:.4,pitch:-1});assert.equal(calls[0].init.headers['X-Apollo-Participant'],'private');
});
test('status polling uses the participant header without sending a command',async()=>{
 const calls=[];const client=new MissionLiveProvider({storage:storage(),fetchImpl:async(path,init)=>{calls.push({path,init});return response(state());}});client.remember({missionId:'mission-1',participantToken:'private',snapshot:state()});await client.snapshot();
 assert.equal(calls[0].init.method,'GET');assert.equal(calls[0].init.headers['X-Apollo-Participant'],'private');assert.equal(calls[0].init.body,undefined);
});
test('unavailable service and permission rejection propagate honestly',async()=>{
 const client=new MissionLiveProvider({storage:storage(),fetchImpl:async()=>response({error:'Commander permission required'},false,403)});
 await assert.rejects(()=>client.discover(),/Commander permission/);assert.equal(client.credentials,null);
 await assert.rejects(()=>client.snapshot(),/Create or join/);await assert.rejects(()=>client.command('start'),/Create or join/);
});
test('corrupt browser persistence does not create a fake participant',()=>{
 const client=new MissionLiveProvider({storage:{getItem:()=>'{broken'}});assert.equal(client.credentials,null);
});

import {readFile} from 'node:fs/promises';
import {RecordedPropulsionProvider} from '../dist/mission-live-provider.mjs';
const actualPropulsion = JSON.parse(await readFile(new URL('../dist/data/propulsion-lab.json', import.meta.url),'utf8'));
test('three real propulsion cases retain source fingerprints and original software outcomes',()=>{
 const recorded=new RecordedPropulsionProvider(actualPropulsion);
 assert.deepEqual(recorded.recording.cases.map(value=>value.id),['sink','connected','no-feedback']);
 const connected=recorded.scenario('connected');assert.equal(connected.result.originalChecksPass,true);assert.ok(connected.result.originalThrottleCalls>0);assert.equal(connected.result.landing,'NOT RUN');
});
test('propulsion replay holds preceding real frames rather than interpolating guidance values',()=>{
 const recorded=new RecordedPropulsionProvider(actualPropulsion);const scenario=recorded.scenario('connected');const a=scenario.frames[1],b=scenario.frames[2];
 assert.equal(recorded.frame('connected',(a.t+b.t)/2),a);assert.equal(recorded.frame('connected',1e9),scenario.frames.at(-1));assert.throws(()=>recorded.frame('connected',NaN));
});
test('a recorded experiment relabeled live or missing provenance is rejected',()=>{
 assert.throws(()=>new RecordedPropulsionProvider({...actualPropulsion,mode:'LIVE_AGC_EXECUTION'}));const bad=structuredClone(actualPropulsion);bad.cases[0].frames[1].source.traceSha256='0'.repeat(64);assert.throws(()=>new RecordedPropulsionProvider(bad));
});
test('recorded propulsion loading makes only its existing static GET request',async()=>{
 const calls=[];const recorded=await RecordedPropulsionProvider.load({fetchImpl:async(path,init)=>{calls.push({path,init});return response(actualPropulsion);}});assert.equal(calls[0].path,'./data/propulsion-lab.json');assert.equal(calls[0].init.method,undefined);assert.ok(recorded.scenario('sink'));
});
