import test from 'node:test';
import assert from 'node:assert/strict';
import {EarthOrbitClient,validateEarthOrbitSnapshot,EARTH_ORBIT_MODE,DSKY_KEYS} from '../dist/earth-orbit-client.mjs';
import {DSKY_KEY_LAYOUT} from '../dist/earth-orbit-panel.mjs';

const hash='a'.repeat(64),token='local-cmc-token';
const capabilities=(changes={})=>({available:true,mode:EARTH_ORBIT_MODE,software:'Comanche055',scope:'Fresh computer readiness diagnostic; no flight dynamics.',unavailableReason:null,supportedKeys:[...DSKY_KEYS],token,...changes});
const snapshot=(changes={})=>({schemaVersion:1,mode:EARTH_ORBIT_MODE,available:true,status:'ready',sessionId:'cmc-session',revision:0,nextSequence:0,
  computer:{software:'Comanche055',cycle:1024000,cpuSeconds:12,dsky:{PROG:'00',VERB:'35',NOUN:'00',R1:'88888',R2:'88888',R3:'88888'},dskySource:{channel:8,cycle:1000000},lastKey:null,provenance:{ropeSha256:hash,engineSha256:hash,sourceUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html'}},
  task:{id:'cmc-checkout',title:'Computer readiness diagnostic',complete:false,steps:[{id:'p00',title:'Select P00',description:'Let the original computer acknowledge the program.',complete:false,active:true}],nextInstruction:'Press the source-backed keys shown here by the server.',scope:'No flight, orbital insertion or alignment completion.',flightExecuted:false,alignmentCompleted:false},inputs:[],error:null,...changes});
const response=(value,status=200)=>({ok:status>=200&&status<300,status,json:async()=>structuredClone(value)});
function ack(body,initial=snapshot()) {
  const cycle=initial.computer.cycle+51200,lastKey={key:body.key,code:body.key==='PRO'?8192:17,channel:body.key==='PRO'?26:13,cycle:initial.computer.cycle,sequence:body.sequence};
  return {...structuredClone(initial),revision:initial.revision+1,nextSequence:body.sequence+1,computer:{...structuredClone(initial.computer),cycle,cpuSeconds:cycle*12/1024000,lastKey},ack:{sessionId:body.sessionId,sequence:body.sequence,key:body.key,channel:lastKey.channel,code:lastKey.code,queuedAtCycle:lastKey.cycle,afterCycle:cycle}};
}
function server(handler,initial=snapshot()) {
  const calls=[];return {calls,fetchImpl:async(path,options)=>{const call={path,...options,body:options.body===undefined?undefined:JSON.parse(options.body)};calls.push(call);if(path.endsWith('/capabilities'))return response(capabilities());if(path.endsWith('/status'))return response(initial);return handler(call);}};
}

test('connect restores the actual observation using GET only and hides the bootstrap token',async()=>{
  const mock=server(()=>{throw new Error('Unexpected mutation');}),client=new EarthOrbitClient({fetchImpl:mock.fetchImpl});
  await client.connect();assert.equal(client.available,true);assert.deepEqual(client.state,snapshot());assert.equal(client.busy,false);
  assert.deepEqual(mock.calls.map(call=>[call.method,call.path]),[['GET','/api/earth-orbit/capabilities'],['GET','/api/earth-orbit/status']]);
  assert.equal(mock.calls[0].headers['X-Apollo-Token'],undefined);assert.equal(mock.calls[1].headers['X-Apollo-Token'],token);assert.equal(JSON.stringify(client).includes(token),false);
  assert.throws(()=>{client.state.computer.dsky.PROG='52';},TypeError);
});

test('a browser fetch receives its global receiver',async()=>{
  const original=globalThis.fetch;globalThis.fetch=async function(path){assert.equal(this,globalThis);return response(path.endsWith('/capabilities')?capabilities():snapshot());};
  try {const client=new EarthOrbitClient();await client.connect();assert.equal(client.available,true);}finally {globalThis.fetch=original;}
});

test('missing native capability disables input without issuing a status request or substituting a recording',async()=>{
  let requests=0;const client=new EarthOrbitClient({fetchImpl:async path=>{requests++;assert.equal(path,'/api/earth-orbit/capabilities');return response(capabilities({available:false,token:null,unavailableReason:'Original CMC rope unavailable.'}));}});
  assert.equal(await client.connect(),null);assert.equal(client.available,false);assert.equal(client.state,null);assert.match(client.message,/rope unavailable/);
  await assert.rejects(client.start(),/rope unavailable/);await assert.rejects(client.key('VERB'),/rope unavailable/);assert.equal(requests,1);
});

test('a key is sent exactly once and no DSKY digit or task advances before its original computer acknowledgement',async()=>{
  let finish;const mock=server(call=>new Promise(resolve=>{finish=()=>resolve(response(ack(call.body)));})),client=new EarthOrbitClient({fetchImpl:mock.fetchImpl});
  await client.connect();const before=client.state,pending=client.key('VERB');assert.equal(client.busy,true);assert.equal(client.state,before);
  assert.deepEqual(mock.calls.at(-1).body,{sessionId:'cmc-session',sequence:0,key:'VERB'});await assert.rejects(client.key('3'),error=>error.code==='busy');assert.equal(mock.calls.filter(call=>call.method==='POST').length,1);
  finish();await pending;assert.equal(client.state.nextSequence,1);assert.equal(client.state.computer.lastKey.key,'VERB');assert.deepEqual(client.state.computer.dsky,before.computer.dsky);assert.equal(client.state.task.complete,false);
});

test('physical PRO is sent as PRO and its own hardware channel is accepted, rather than substituted by V33E',async()=>{
  const mock=server(call=>response(ack(call.body))),client=new EarthOrbitClient({fetchImpl:mock.fetchImpl});await client.connect();await client.key('PRO');
  assert.equal(mock.calls.at(-1).body.key,'PRO');assert.equal(client.state.computer.lastKey.channel,26);assert.equal(client.state.task.alignmentCompleted,false);assert.equal(client.state.task.flightExecuted,false);
});

test('arbitrary strings and keys absent from capability discovery never reach the native computer',async()=>{
  const mock=server(call=>response(ack(call.body))),fetchImpl=async(path,options)=>path.endsWith('/capabilities')?response(capabilities({supportedKeys:['VERB']})):mock.fetchImpl(path,options);
  const client=new EarthOrbitClient({fetchImpl});await client.connect();for(const key of ['P52','V37E52E','0','PRO',null,{},'__proto__'])await assert.rejects(client.key(key),/unavailable/);
  assert.equal(mock.calls.filter(call=>call.method==='POST').length,0);
});

test('a lost response reconciles with one observation and never retries the key',async()=>{
  let reads=0,posts=0;const changed=ack({sessionId:'cmc-session',sequence:0,key:'VERB'}),client=new EarthOrbitClient({fetchImpl:async(path)=>{
    if(path.endsWith('/capabilities'))return response(capabilities());if(path.endsWith('/status'))return response(reads++?changed:snapshot());posts++;throw new TypeError('Connection lost after key submission');
  }});
  await client.connect();await assert.rejects(client.key('VERB'),/Connection lost/);assert.equal(posts,1);assert.equal(reads,2);assert.equal(client.state.nextSequence,1);assert.equal(client.busy,false);
});

test('a token rejection locks keys until an explicit connection, preserving the last actual observation',async()=>{
  const mock=server(()=>response({error:'Local token rejected'},403)),client=new EarthOrbitClient({fetchImpl:mock.fetchImpl});await client.connect();const before=client.state;
  await assert.rejects(client.key('VERB'),/Reconnect/);assert.equal(client.available,false);assert.equal(client.state,before);await assert.rejects(client.key('VERB'),/Reconnect/);assert.equal(mock.calls.length,3);
});

test('stale, unrelated and impossible key acknowledgements are rejected then resynchronized once',async()=>{
  for(const change of ['key','session','sequence','revision','channel','cycle']) {
    let reads=0,posts=0;const actual=ack({sessionId:'cmc-session',sequence:0,key:'VERB'});
    const client=new EarthOrbitClient({fetchImpl:async(path,options)=>{
      if(path.endsWith('/capabilities'))return response(capabilities());if(path.endsWith('/status'))return response(reads++?actual:snapshot());posts++;const value=ack(JSON.parse(options.body));
      if(change==='key')value.ack.key='NOUN';if(change==='session')value.ack.sessionId='other';if(change==='sequence')value.ack.sequence=42;if(change==='revision')value.revision=77;if(change==='channel')value.ack.channel=14;if(change==='cycle')value.ack.afterCycle--;
      return response(value);
    }});
    await client.connect();await assert.rejects(client.key('VERB'),/acknowledgement/);assert.equal(posts,1);assert.equal(reads,2);assert.deepEqual(client.state,actual);
  }
});

test('unresolved request uncertainty locks controls without erasing real prior values',async()=>{
  let reads=0,posts=0;const client=new EarthOrbitClient({fetchImpl:async(path)=>{
    if(path.endsWith('/capabilities'))return response(capabilities());if(path.endsWith('/status')){if(reads++)throw new TypeError('Offline');return response(snapshot());}posts++;throw new TypeError('Lost acknowledgement');
  }});
  await client.connect();await assert.rejects(client.key('VERB'),/Reconnect/);assert.equal(client.available,false);assert.deepEqual(client.state,snapshot());await assert.rejects(client.key('VERB'));assert.equal(posts,1);
});

test('clock, provenance and unavailable flight claims are validated before observations are published',()=>{
  const reject=mutate=>{const value=snapshot();mutate(value);assert.throws(()=>validateEarthOrbitSnapshot(value),/Invalid CMC observation/);};
  reject(value=>{value.mode='VERIFIED RECORDED EXECUTION';});reject(value=>{value.computer.software='Luminary099';});reject(value=>{value.computer.cpuSeconds=195*3600;});reject(value=>{value.computer.dsky.PROG='P52';});
  reject(value=>{value.computer.dskySource.channel=13;});reject(value=>{value.computer.dskySource.cycle=value.computer.cycle+1;});reject(value=>{value.computer.provenance.ropeSha256='unknown';});reject(value=>{value.computer.provenance.sourceUrl='javascript:alert(1)';});reject(value=>{value.computer.provenance.sourceUrl='https://user:password@example.com/';});
  reject(value=>{value.task.flightExecuted=true;});reject(value=>{value.task.alignmentCompleted=true;});reject(value=>{value.task.steps.push({...value.task.steps[0]});});assert.equal(validateEarthOrbitSnapshot(snapshot()).computer.cpuSeconds,12);
  reject(value=>{value.computer.flightState={positionM:[1,2,3]};});reject(value=>{value.computer.historicalCheckpointLoaded=true;});reject(value=>{value.computer.provenance.flightMemoryWrites=true;});reject(value=>{value.computer.provenance.hostFlightMemoryWrites=true;});
});

test('the DSKY offers all nineteen hardware keys once, with outer function-key pairs staggered',()=>{
  assert.equal(DSKY_KEY_LAYOUT.length,19);assert.deepEqual(new Set(DSKY_KEY_LAYOUT.map(row=>row[0])),new Set(DSKY_KEYS));
  const occupied=new Set();for(const [,column,row] of DSKY_KEY_LAYOUT){for(const offset of [0,1]){const position=`${column}:${row+offset}`;assert.equal(occupied.has(position),false);occupied.add(position);}}
  for(const [key,column,row] of [['VERB',1,2],['NOUN',1,4],['ENTR',7,2],['RSET',7,4],['PRO',6,3]])assert.deepEqual(DSKY_KEY_LAYOUT.find(item=>item[0]===key),[key,column,row]);
});

test('optional observed signs and decoded lamp bits accept only explicit hardware values',()=>{
  const value=snapshot();value.computer.dsky.signs={R1:'+',R2:'-',R3:' '};value.computer.dsky.lamps={keyRelease:true,operatorError:false,computerActivity:null,verbNounFlash:true};
  assert.equal(validateEarthOrbitSnapshot(value),value);
  for(const signs of [{R1:'positive',R2:null,R3:null},{R1:null,R2:null},null,{R1:null,R2:null,R3:null,other:'+'}]){const invalid=snapshot();invalid.computer.dsky.signs=signs;assert.throws(()=>validateEarthOrbitSnapshot(invalid),/register signs/);}
  for(const lamps of [{keyRelease:1,operatorError:false,computerActivity:null,verbNounFlash:true},{keyRelease:true},null,{keyRelease:true,operatorError:false,computerActivity:null,verbNounFlash:true,thrust:true}]){const invalid=snapshot();invalid.computer.dsky.lamps=lamps;assert.throws(()=>validateEarthOrbitSnapshot(invalid),/indicator bits/);}
});
