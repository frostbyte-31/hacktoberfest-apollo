import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EarthAlignmentClient, EARTH_ALIGNMENT_MODE, INSTRUMENT_CONTROLS,
  validateEarthAlignmentSnapshot, validateInstrumentControl,
} from '../dist/earth-alignment-client.mjs';
import {DSKY_KEYS} from '../dist/earth-orbit-client.mjs';

// Explicit transport unit fixtures, not captured CMC output or alignment evidence.
const digest = 'b'.repeat(64), token = 'alignment-unit-fixture-token';
const capabilities = (changes = {}) => ({
  available: true, mode: EARTH_ALIGNMENT_MODE, software: 'Comanche055',
  scope: 'Unit transport fixture: original-computer classification with modeled instruments.',
  supportedKeys: [...DSKY_KEYS], supportedControls: [...INSTRUMENT_CONTROLS], token,
  ...changes,
});
function observation() {
  return {
    schemaVersion: 1, mode: EARTH_ALIGNMENT_MODE, available: true, status: 'ready',
    sessionId: 'unit-alignment-session', revision: 0, nextSequence: 0,
    computer: {
      software: 'Comanche055', mode: 'LIVE AGC EXECUTION', cycle: 1024000, cpuSeconds: 12,
      dsky: {PROG:'00', VERB:'  ', NOUN:'  ', R1:'00000', R2:'00000', R3:'00000'},
      dskySource: {channel: 8, cycle: 1023990}, lastKey: null,
      provenance: {ropeSha256:digest, engineSha256:digest,
        sourceUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html',
        hostFlightMemoryWrites:false},
      historicalCheckpointLoaded: false, flightState: null,
      instruments: {
        mode: 'MODELED CSM INSTRUMENTS', imuPowered: true, opticsMode: 'MANUAL',
        shaftDeg: 0, trunnionDeg: 40, mechanicalTrunnionDeg: 20,
        scope: 'Fixed unit geometry; not historical observations or flight state.',
        markCount: 2,
        stars: [
          {code:'30', name:'Fixture star A', shaftDeg:0, trunnionDeg:40, errorDeg:0},
          {code:'37', name:'Fixture star B', shaftDeg:104, trunnionDeg:40, errorDeg:60},
        ],
        alignment: {referenceInitialized:true, p52Complete:false, p52Marks:0,
          torqueApproved:false, torqueOutputCount:0, completionCycle:null},
      },
    },
    task: {id:'unit-alignment-task', title:'Unit task', complete:false,
      steps:[{id:'p52',title:'P52',description:'An original output is required.',complete:false,active:true}],
      nextInstruction:'Await a source-classified observation.', scope:'No flight or historical checkpoint.',
      alignmentCompleted:false, flightExecuted:false},
    inputs: [], error: null,
  };
}
const reply = (value, status = 200) => ({ok:status >= 200 && status < 300, status, json:async()=>structuredClone(value)});
function acknowledged(before, body, route) {
  const value = structuredClone(before), cycle = before.computer.cycle + 51200;
  value.revision++; value.nextSequence = body.sequence + 1;
  value.computer.cycle = cycle; value.computer.cpuSeconds = cycle * 12 / 1024000;
  value.ack = {sessionId:body.sessionId, sequence:body.sequence,
    queuedAtCycle:before.computer.cycle, afterCycle:cycle};
  if (route === 'key') {
    const channel = body.key === 'PRO' ? 26 : 13, code = body.key === 'PRO' ? 0 : 17;
    value.ack = {...value.ack, key:body.key, channel, code};
    value.computer.lastKey = {key:body.key, sequence:body.sequence, channel, code, cycle:before.computer.cycle};
  } else value.ack = {...value.ack, control:body.control, value:structuredClone(body.value)};
  return value;
}
function transport({initial = observation(), handle, discovery = capabilities()} = {}) {
  let current = structuredClone(initial);
  const calls = [];
  const fetchImpl = async (path, options) => {
    const route = path.split('/').at(-1), call = {path, ...options,
      body:options.body === undefined ? undefined : JSON.parse(options.body)};
    calls.push(call);
    if (route === 'capabilities') return reply(discovery);
    if (route === 'status') return reply(current);
    if (handle) return handle(call, current, value => {current = value;});
    current = acknowledged(current, call.body, route); return reply(current);
  };
  return {calls, fetchImpl};
}

test('connection reads only and preserves the distinction between original execution and modeled instruments', async () => {
  const wire = transport(), client = new EarthAlignmentClient({fetchImpl:wire.fetchImpl});
  await client.connect();
  assert.deepEqual(wire.calls.map(({method,path})=>[method,path]), [
    ['GET','/api/earth-alignment/capabilities'], ['GET','/api/earth-alignment/status'],
  ]);
  assert.equal(client.state.mode, EARTH_ALIGNMENT_MODE);
  assert.equal(client.state.computer.instruments.mode, 'MODELED CSM INSTRUMENTS');
  assert.equal(client.state.task.flightExecuted, false);
  assert.equal(JSON.stringify(client).includes(token), false);
  assert.equal(wire.calls[0].headers['X-Apollo-Token'], undefined);
  assert.equal(wire.calls[1].headers['X-Apollo-Token'], token);
  assert.throws(()=>{client.state.computer.instruments.stars[0].shaftDeg = 90;}, TypeError);
});

test('an unavailable original computer cannot silently fall back to synthetic or recorded completion', async () => {
  const wire = transport({discovery:capabilities({available:false,token:null,unavailableReason:'Original engine unavailable.'})});
  const client = new EarthAlignmentClient({fetchImpl:wire.fetchImpl});
  assert.equal(await client.connect(), null);
  assert.equal(client.available, false); assert.equal(client.state, null);
  await assert.rejects(client.start(), /Original engine unavailable/);
  await assert.rejects(client.key('VERB'));
  await assert.rejects(client.instrument('mark','MARK'));
  assert.equal(wire.calls.length, 1);
});

test('source, clock, rope and modeled-instrument schema are checked before publication', () => {
  const reject = mutate => {const value = observation(); mutate(value); assert.throws(()=>validateEarthAlignmentSnapshot(value), /Invalid/);};
  for (const mode of ['LIVE ORIGINAL CMC EXECUTION','VERIFIED RECORDED EXECUTION','STATIC EDUCATIONAL ILLUSTRATION']) reject(value=>{value.mode=mode;});
  reject(value=>{value.computer.software='Luminary099';});
  reject(value=>{value.computer.mode='VERIFIED RECORDED EXECUTION';});
  reject(value=>{value.computer.cpuSeconds=1;});
  reject(value=>{value.computer.provenance.ropeSha256='not-a-hash';});
  reject(value=>{value.computer.provenance.sourceUrl='javascript:alert(1)';});
  reject(value=>{value.computer.provenance.hostFlightMemoryWrites=true;});
  reject(value=>{value.computer.historicalCheckpointLoaded=true;});
  reject(value=>{value.computer.flightState={positionM:[1,2,3]};});
  reject(value=>{value.task.flightExecuted=true;});
  reject(value=>{value.computer.instruments.mode='LIVE PHYSICAL SPACECRAFT';});
  reject(value=>{value.computer.instruments.imuPowered=1;});
  reject(value=>{value.computer.instruments.opticsMode='AUTO';});
  for (const field of ['shaftDeg','trunnionDeg','mechanicalTrunnionDeg']) {
    for (const number of [NaN,Infinity,-Infinity,361]) reject(value=>{value.computer.instruments[field]=number;});
  }
  assert.equal(validateEarthAlignmentSnapshot(observation()).task.complete, false);
});

test('star identities and geometry cannot be duplicated or non-finite', () => {
  const mutations = [
    value=>{value.stars=[];}, value=>{value.stars[1].code=value.stars[0].code;},
    value=>{value.stars[0].code='89';}, value=>{value.stars[0].name=' ';},
    value=>{value.stars[0].errorDeg=-1;}, value=>{value.stars[0].errorDeg=181;},
    value=>{value.stars[0].shaftDeg=Infinity;}, value=>{value.markCount=-1;},
  ];
  for (const mutate of mutations) {
    const value=observation(); mutate(value.computer.instruments);
    assert.throws(()=>validateEarthAlignmentSnapshot(value), /Invalid alignment observation/);
  }
});

test('P00 and entered keys do not manufacture P52 completion; completion requires classified original evidence', () => {
  const start = observation(); start.computer.dsky.PROG='00';
  start.inputs=[{key:'PRO'},{key:'VERB'},{key:'0'},{key:'0'},{key:'ENTR'}];
  assert.equal(validateEarthAlignmentSnapshot(start).task.alignmentCompleted, false);
  for (const mutate of [
    value=>{value.task.complete=true;}, value=>{value.task.alignmentCompleted=true;},
    value=>{value.computer=null;value.status='stopped';value.task.complete=true;},
    value=>{value.computer.instruments.alignment.p52Complete=true;},
    value=>{value.computer.instruments.alignment.completionCycle=value.computer.cycle+1;},
  ]) {const value=observation();mutate(value);assert.throws(()=>validateEarthAlignmentSnapshot(value), /Invalid/);}
  const complete=observation();
  complete.computer.instruments.alignment={referenceInitialized:true,p52Complete:true,p52Marks:2,
    torqueApproved:true,torqueOutputCount:56,completionCycle:complete.computer.cycle-10};
  complete.task.alignmentCompleted=true;complete.task.complete=true;
  assert.equal(validateEarthAlignmentSnapshot(complete).task.complete,true);
  for (const [field,value] of [['referenceInitialized',false],['p52Marks',1],['torqueApproved',false],['completionCycle',null],['torqueOutputCount',-1]]) {
    const invalid=structuredClone(complete);invalid.computer.instruments.alignment[field]=value;
    assert.throws(()=>validateEarthAlignmentSnapshot(invalid), /Invalid alignment observation/);
  }
});

test('DSKY and physical instruments share one monotonically acknowledged input sequence', async () => {
  const wire=transport(),client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  const initial=structuredClone(client.state.computer.dsky);
  await client.key('VERB'); await client.instrument('optics_mode','MANUAL');
  await client.instrument('optics_slew',{shaft:1,trunnion:0,rate:'HIGH',seconds:0.1});
  await client.key('PRO'); await client.instrument('mark','MARK');
  const posts=wire.calls.filter(call=>call.method==='POST');
  assert.deepEqual(posts.map(call=>call.body.sequence),[0,1,2,3,4]);
  assert.deepEqual(posts.map(call=>call.path.split('/').at(-1)),['key','instrument','instrument','key','instrument']);
  assert.ok(posts.every(call=>call.body.sessionId==='unit-alignment-session'));
  assert.equal(posts[3].body.key,'PRO');
  assert.equal(client.state.nextSequence,5);
  assert.deepEqual(client.state.computer.dsky,initial);
  assert.equal(client.state.task.complete,false);
});

test('an in-flight instrument input locks both input paths and changes no observation before the ACK', async () => {
  let finish;
  const wire=transport({handle:(call,before)=>new Promise(resolve=>{finish=()=>resolve(reply(acknowledged(before,call.body,'instrument')));})});
  const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  const before=client.state,pending=client.instrument('mark','MARK');
  assert.equal(client.state,before);assert.equal(client.busy,true);
  await assert.rejects(client.key('ENTR'),error=>error.code==='busy');
  await assert.rejects(client.instrument('mark','REJECT'),error=>error.code==='busy');
  assert.equal(wire.calls.filter(call=>call.method==='POST').length,1);
  finish();await pending;assert.equal(client.state.nextSequence,1);assert.equal(client.busy,false);
});

test('instrument bounds and unsupported keys fail before any POST', async () => {
  const wire=transport(),client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  const good={shaft:1,trunnion:0,rate:'HIGH',seconds:1};
  const invalidControls=[
    ['power_imu','ON'],['power_imu',1],['optics_mode','AUTO'],['mark','MARK ALL'],['thruster',true],
    ...[0,-0.1,1.00001,Infinity,NaN].map(seconds=>['optics_slew',{...good,seconds}]),
    ...[1.01,-1.01,Infinity,NaN].map(shaft=>['optics_slew',{...good,shaft}]),
    ['optics_slew',{...good,trunnion:-2}],['optics_slew',{...good,rate:'MEDIUM'}],
    ['optics_slew',{...good,teleport:true}],['optics_slew',{shaft:0,trunnion:0,rate:'LOW'}],
  ];
  for (const [control,value] of invalidControls) {
    assert.equal(validateInstrumentControl(control,value),false);
    await assert.rejects(client.instrument(control,value), /Unsupported or invalid/);
  }
  for (const key of ['V37E52E','P52',null,{},'__proto__']) await assert.rejects(client.key(key),/Unsupported/);
  assert.equal(wire.calls.filter(call=>call.method==='POST').length,0);
  assert.equal(validateInstrumentControl('optics_slew',{shaft:-1,trunnion:1,rate:'LOW',seconds:0.01}),true);
});

test('capability discovery restricts keys and instrument controls before input', async () => {
  const wire=transport({discovery:capabilities({supportedKeys:['PRO'],supportedControls:['mark']})});
  const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  await assert.rejects(client.key('VERB'),/Unsupported/);
  await assert.rejects(client.instrument('power_imu',true),/Unsupported/);
  assert.equal(wire.calls.filter(call=>call.method==='POST').length,0);
});

test('unrelated key or instrument ACKs are rejected and cause one GET resynchronization', async () => {
  const mutations=[
    ['key',value=>{value.ack.key='NOUN';}],['key',value=>{value.computer.lastKey.sequence=99;}],
    ['key',value=>{value.ack.sessionId='other';}],['key',value=>{value.ack.sequence=42;}],
    ['key',value=>{value.revision=99;}],['key',value=>{value.nextSequence=44;}],
    ['key',value=>{value.ack.queuedAtCycle=0;}],['key',value=>{value.ack.afterCycle--;}],
    ['instrument',value=>{value.ack.control='power_imu';}],['instrument',value=>{value.ack.value='REJECT';}],
  ];
  for (const [route,mutate] of mutations) {
    const wire=transport({handle:(call,before,save)=>{
      const actual=acknowledged(before,call.body,route);save(actual);
      const invalid=structuredClone(actual);mutate(invalid);return reply(invalid);
    }}),client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
    await assert.rejects(route==='key'?client.key('VERB'):client.instrument('mark','MARK'), error=>error.code==='invalid-acknowledgement');
    assert.equal(wire.calls.filter(call=>call.method==='POST').length,1);
    assert.equal(wire.calls.filter(call=>call.path.endsWith('/status')).length,2);
    assert.equal(client.state.nextSequence,1);
  }
});

test('key ACKs need hardware channel/code fields matching the reported last native key', async () => {
  for (const mutate of [
    value=>{value.ack.channel=14;},value=>{value.ack.code=999;},value=>{delete value.ack.channel;},
    value=>{value.ack.channel=-1;value.computer.lastKey.channel=-1;},
    value=>{value.ack.code=32768;value.computer.lastKey.code=32768;},
  ]) {
    const wire=transport({handle:(call,before,save)=>{const actual=acknowledged(before,call.body,'key');save(actual);const invalid=structuredClone(actual);mutate(invalid);return reply(invalid);}});
    const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
    await assert.rejects(client.key('VERB'),error=>['invalid-acknowledgement','invalid-snapshot'].includes(error.code));
  }
});

test('a semantically equal instrument ACK accepts reordered JSON fields without a spurious mutation failure', async () => {
  const wire=transport({handle:(call,before,save)=>{
    const actual=acknowledged(before,call.body,'instrument');
    const {shaft,trunnion,rate,seconds}=actual.ack.value;
    actual.ack.value={seconds,rate,trunnion,shaft};save(actual);return reply(actual);
  }}),client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  await client.instrument('optics_slew',{shaft:0.5,trunnion:-0.25,rate:'HIGH',seconds:0.1});
  assert.equal(client.state.nextSequence,1);
  assert.equal(wire.calls.filter(call=>call.method==='POST').length,1);
  assert.equal(wire.calls.filter(call=>call.path.endsWith('/status')).length,1);
});

test('a lost mutation response is never retried and is reconciled by one status GET', async () => {
  for (const route of ['key','instrument']) {
    const wire=transport({handle:(call,before,save)=>{save(acknowledged(before,call.body,route));throw new TypeError('Response lost after submission');}});
    const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
    await assert.rejects(route==='key'?client.key('PRO'):client.instrument('mark','MARK'),/Response lost/);
    assert.equal(wire.calls.filter(call=>call.method==='POST').length,1);
    assert.equal(wire.calls.filter(call=>call.path.endsWith('/status')).length,2);
    assert.equal(client.state.nextSequence,1);assert.equal(client.busy,false);
  }
});

test('an unreadable successful mutation response still resynchronizes once without repeating the action', async () => {
  const wire=transport({handle:(call,before,save)=>{
    save(acknowledged(before,call.body,'instrument'));
    return {ok:true,status:200,json:async()=>{throw new SyntaxError('Truncated JSON');}};
  }}),client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();
  await assert.rejects(client.instrument('mark','MARK'),error=>error.code==='invalid-response');
  assert.equal(wire.calls.filter(call=>call.method==='POST').length,1);
  assert.equal(wire.calls.filter(call=>call.path.endsWith('/status')).length,2);
  assert.equal(client.state.nextSequence,1);
});

test('failed resynchronization retains the last observation but locks further actions', async () => {
  let reads=0,posts=0;
  const client=new EarthAlignmentClient({fetchImpl:async path=>{
    if(path.endsWith('/capabilities'))return reply(capabilities());
    if(path.endsWith('/status')){if(reads++)throw new TypeError('Offline');return reply(observation());}
    posts++;throw new TypeError('Lost acknowledgement');
  }});await client.connect();const before=client.state;
  await assert.rejects(client.instrument('mark','MARK'),/could not be refreshed/);
  assert.equal(client.available,false);assert.equal(client.state,before);
  await assert.rejects(client.key('PRO'));await assert.rejects(client.instrument('mark','MARK'));
  assert.equal(posts,1);
});

test('403 invalidates the token, preserves the observation and requires explicit reconnect', async () => {
  const wire=transport({handle:()=>reply({error:'Token rejected'},403)});
  const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});await client.connect();const before=client.state;
  await assert.rejects(client.instrument('mark','MARK'),/Reconnect/);
  assert.equal(client.available,false);assert.equal(client.state,before);
  await assert.rejects(client.key('PRO'));await assert.rejects(client.instrument('mark','REJECT'));
  assert.equal(wire.calls.length,3);
  await client.connect();assert.equal(client.available,true);
  assert.equal(wire.calls.at(-1).headers['X-Apollo-Token'],token);
});

test('unknown or duplicate capability entries are rejected rather than expanding authority', async () => {
  for(const changes of [
    {supportedKeys:['VERB','VERB']},{supportedControls:['mark','mark']},
    {supportedKeys:['TELEPORT']},{supportedControls:['engine_ignite']},
  ]) {
    const wire=transport({discovery:capabilities(changes)});
    const client=new EarthAlignmentClient({fetchImpl:wire.fetchImpl});
    await assert.rejects(client.connect(),/Invalid alignment capabilities/);
    assert.equal(wire.calls.length,1);assert.equal(client.available,false);
  }
});
