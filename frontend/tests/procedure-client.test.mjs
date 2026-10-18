import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { ProcedureClient, validateProcedureSnapshot } from '../dist/procedure-client.mjs';

const MODE='INTERACTIVE PROCEDURE TRAINER',HASH='a'.repeat(64);
const capabilities={mode:MODE,crewReports:true,modeledSelectors:true,modeledMechanicalRelease:true,originalAgc:false,flightPhysics:false,sensorReadback:false,historicalMissionClock:false,definitionSha256:HASH};
const bootstrap=()=>({procedureEnabled:true,liveEnabled:true,token:'local-secret-token',procedureCapabilities:{...capabilities}});
const snapshot=(changes={})=>({schemaVersion:1,mode:MODE,classification:MODE,status:'active',available:true,
  sessionId:'test-session',revision:0,lastSequence:-1,currentStepIndex:0,currentStep:{id:'closeout',kind:'crew-report',role:'LMP'},
  completedStepIds:[],controls:{guidance:'UNKNOWN'},crewReports:{},controlEvidence:{},attachment:'docked',events:[],
  capabilities:{...capabilities},definitionSha256:HASH,message:'Await crew action.',...changes});
const response=(value,status=200)=>({ok:status>=200&&status<300,status,json:async()=>JSON.parse(JSON.stringify(value))});
const acknowledgement=(body,changes={})=>({accepted:true,advanced:true,meaning:'Crew report accepted.',snapshot:snapshot({
  sessionId:body.sessionId,revision:body.expectedRevision+1,lastSequence:body.sequence,currentStepIndex:1,
  currentStep:{id:'guidance',kind:'select',role:'CDR'},completedStepIds:[body.action],
  events:[{...body,revision:body.expectedRevision+1,advanced:true,evidenceKind:'crew-report'}],...changes,
})});

function service(handler,initial=snapshot()) {
  const calls=[];
  const fetchImpl=async(path,options)=>{
    const request={path,...options,body:options.body===undefined?undefined:JSON.parse(options.body)};calls.push(request);
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status')return response(initial);
    return handler(request,calls);
  };
  return {calls,fetchImpl};
}

test('the default browser fetch retains its global receiver instead of the client object',async()=>{
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async function(path){
    assert.equal(this,globalThis,'WebKit fetch rejects a client object as its receiver');calls++;
    return response(path==='/api/bootstrap'?bootstrap():snapshot());
  };
  try{
    const client=new ProcedureClient();await client.connect();
    assert.equal(calls,2);assert.equal(client.available,true);assert.equal(client.state.status,'active');
  }finally{globalThis.fetch=original;}
});

test('connect restores the authoritative existing session using GET only and never serializes its token',async()=>{
  const existing=snapshot({revision:5,lastSequence:4,currentStepIndex:2,completedStepIds:['earlier-report']});
  const server=service(()=>{throw new Error('Unexpected mutation');},existing),published=[];
  const client=new ProcedureClient({fetchImpl:server.fetchImpl,onState:value=>published.push(value)});
  const state=await client.connect();
  assert.deepEqual(state,existing);assert.equal(published.length,1);assert.equal(client.available,true);assert.equal(client.busy,false);
  assert.deepEqual(server.calls.map(call=>[call.method,call.path]),[['GET','/api/bootstrap'],['GET','/api/procedure/status']]);
  assert.equal(server.calls[0].headers['X-Apollo-Token'],undefined);assert.equal(server.calls[1].headers['X-Apollo-Token'],'local-secret-token');
  assert.equal(client.token,'local-secret-token');assert.equal(Object.hasOwn(client.capabilities,'token'),false);
  assert.equal(JSON.stringify(client).includes('local-secret-token'),false);
  assert.throws(()=>{client.state.revision=99;},TypeError);assert.throws(()=>{client.state.controls.guidance='PGNS';},TypeError);
});

test('old and replay-only servers remain read-only without attempting a procedure endpoint',async()=>{
  for(const boot of [{token:'old-live-token',liveEnabled:true},{...bootstrap(),procedureEnabled:false},{...bootstrap(),token:null}]){
    let requests=0;const client=new ProcedureClient({fetchImpl:async path=>{requests++;assert.equal(path,'/api/bootstrap');return response(boot);}});
    assert.equal(await client.connect(),null);assert.equal(client.available,false);assert.equal(client.token,null);
    assert.match(client.message,/unavailable/);assert.equal(client.state,null);
    await assert.rejects(client.start(),/unavailable/);await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/unavailable/);
    assert.equal(requests,1,'Disabled services must not receive status or control requests');
  }
});

test('an unavailable status overrides bootstrap permission and prevents a control request',async()=>{
  const initial=snapshot({available:false,status:'idle',sessionId:null,message:'Procedure definition unavailable.'});
  const server=service(()=>{throw new Error('Unexpected POST');},initial);
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();
  assert.equal(client.available,false);assert.equal(client.state.available,false);
  await assert.rejects(client.start(),/unavailable/);assert.equal(server.calls.length,2);
});

test('start posts only an empty object and presents only the returned server state',async()=>{
  const started=snapshot({sessionId:'new-session'});
  const server=service(request=>{assert.equal(request.path,'/api/procedure/start');assert.deepEqual(request.body,{});return response(started,202);},snapshot({status:'idle',sessionId:null}));
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();
  assert.deepEqual(await client.start(),started);assert.equal(client.state.sessionId,'new-session');
  assert.equal(server.calls.at(-1).headers['Content-Type'],'application/json');
});

test('an explicit action carries the exact current session, sequence and revision without optimistic advancement',async()=>{
  let finish;const server=service(request=>new Promise(resolve=>{finish=()=>resolve(response(acknowledgement(request.body)));}));
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();
  const before=client.state,pending=client.act('LMP','closeout','CONFIRMED');
  assert.equal(client.busy,true);assert.equal(client.state,before);assert.equal(client.state.currentStepIndex,0);
  const request=server.calls.at(-1);
  assert.equal(request.method,'POST');assert.equal(request.path,'/api/procedure/action');
  assert.deepEqual(request.body,{sessionId:'test-session',sequence:0,expectedRevision:0,role:'LMP',action:'closeout',value:'CONFIRMED'});
  await assert.rejects(client.act('LMP','closeout','CONFIRMED'),error=>error.code==='busy');
  await assert.rejects(client.refresh(),error=>error.code==='busy');
  assert.equal(server.calls.filter(call=>call.method==='POST').length,1);
  finish();const result=await pending;
  assert.equal(result.snapshot,client.state);assert.equal(client.state.revision,1);assert.equal(client.state.currentStepIndex,1);assert.equal(client.busy,false);
});

test('a wrong modeled selector setting can be acknowledged without the client completing its step',async()=>{
  const initial=snapshot({currentStep:{id:'guidance',kind:'select',role:'CDR'}});
  const server=service(request=>{
    const result=acknowledgement(request.body,{currentStepIndex:0,currentStep:initial.currentStep,completedStepIds:[],controls:{guidance:'PGNS'}});
    result.advanced=false;result.snapshot.events[0].advanced=false;result.meaning='Required setting not reached.';
    return response(result);
  },initial);
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();
  const result=await client.act('CDR','guidance','PGNS');
  assert.equal(result.advanced,false);assert.equal(client.state.controls.guidance,'PGNS');assert.equal(client.state.currentStepIndex,0);assert.deepEqual(client.state.completedStepIds,[]);
});

test('a revision conflict reads the actual changed state once and never retries the action',async()=>{
  let reads=0;const actual=snapshot({revision:1,lastSequence:0,currentStepIndex:1,currentStep:{id:'guidance'}}),calls=[],errors=[];
  const client=new ProcedureClient({onError:message=>errors.push(message),fetchImpl:async(path,options)=>{
    calls.push({path,method:options.method});
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status')return response(reads++?actual:snapshot());
    return response({error:'Procedure revision changed.'},409);
  }});
  await client.connect();await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/revision changed/);
  assert.deepEqual(client.state,actual);assert.equal(reads,2);assert.equal(calls.filter(call=>call.method==='POST').length,1);
  assert.equal(errors.length,1);assert.equal(client.busy,false);
});

test('a lost action response reconciles with one GET instead of sending the command twice',async()=>{
  let reads=0,posts=0;const actual=snapshot({revision:1,lastSequence:0,currentStepIndex:1,currentStep:{id:'guidance'}});
  const client=new ProcedureClient({fetchImpl:async(path)=>{
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status')return response(reads++?actual:snapshot());
    posts++;throw new TypeError('Connection lost after submission.');
  }});
  await client.connect();await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/Connection lost/);
  assert.equal(posts,1);assert.equal(reads,2);assert.deepEqual(client.state,actual);assert.equal(client.available,true);assert.equal(client.busy,false);
});

test('an unsuccessful uncertainty read locks further controls until reconnection',async()=>{
  let reads=0,posts=0;const client=new ProcedureClient({fetchImpl:async(path)=>{
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status'){if(reads++)throw new TypeError('Offline');return response(snapshot());}
    posts++;throw new TypeError('Lost submission acknowledgement');
  }});
  await client.connect();await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/reconnect before another action/);
  assert.equal(client.available,false);assert.equal(client.state.revision,0);assert.equal(client.busy,false);
  await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/reconnect/);assert.equal(posts,1);
});

test('a timed-out request aborts, reads status once, and releases the pending lock without retrying',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});
  let reads=0,posts=0;const client=new ProcedureClient({fetchImpl:async(path,options)=>{
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status'){reads++;return response(snapshot());}
    posts++;return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'})),{once:true}));
  }});
  await client.connect();const pending=client.act('LMP','closeout','CONFIRMED');
  assert.equal(client.busy,true);context.mock.timers.tick(5001);
  await assert.rejects(pending,/timed out/);assert.equal(posts,1);assert.equal(reads,2);assert.equal(client.busy,false);
});

test('stale or unrelated successful acknowledgements are rejected and replaced by one status read',async()=>{
  for(const change of ['revision','session','action','role','value','definition']){
    let reads=0,posts=0;const actual=snapshot({revision:1,lastSequence:0,currentStepIndex:1,currentStep:{id:'guidance'}});
    const client=new ProcedureClient({fetchImpl:async(path,options)=>{
      if(path==='/api/bootstrap')return response(bootstrap());
      if(path==='/api/procedure/status')return response(reads++?actual:snapshot());
      posts++;const result=acknowledgement(JSON.parse(options.body));
      if(change==='revision')result.snapshot.revision=3;
      if(change==='session')result.snapshot.sessionId='another-session';
      if(change==='definition')result.snapshot.definitionSha256='b'.repeat(64);
      if(['action','role','value'].includes(change))result.snapshot.events[0][change]='another-value';
      return response(result);
    }});
    await client.connect();await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/acknowledgement/);
    assert.equal(posts,1);assert.equal(reads,2);assert.deepEqual(client.state,actual);
  }
});

test('explicit HTTP rejection leaves the current state unchanged and does not resubmit or poll',async()=>{
  const server=service(()=>response({error:'This action belongs to the LMP station.'},403));
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();const before=client.state;
  await assert.rejects(client.act('CDR','closeout','CONFIRMED'),/LMP station/);
  assert.equal(client.state,before);assert.equal(server.calls.length,3);
});

test('a restarted server rejects the old token, locks commands, and restores only through explicit reconnection',async()=>{
  let restarted=false;const calls=[],idle=snapshot({status:'idle',sessionId:null,message:'Begin a new checklist training session.'});
  const client=new ProcedureClient({fetchImpl:async(path,options)=>{
    calls.push({path,method:options.method,token:options.headers['X-Apollo-Token']});
    if(path==='/api/bootstrap')return response({...bootstrap(),token:restarted?'new-server-token':'old-server-token'});
    if(path==='/api/procedure/status')return response(restarted?idle:snapshot());
    assert.equal(options.headers['X-Apollo-Token'],'old-server-token');
    return response({error:'Local control token is invalid.'},403);
  }});
  await client.connect();const acknowledged=client.state;restarted=true;
  await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/Reconnect.*review its current state/);
  assert.equal(client.available,false);assert.equal(client.token,null);assert.equal(client.state,acknowledged);
  await assert.rejects(client.act('LMP','closeout','CONFIRMED'),/Reconnect/);
  assert.equal(calls.length,3,'A forbidden response must not retry or automatically reconnect');
  await client.connect();assert.equal(client.available,true);assert.equal(client.token,'new-server-token');assert.deepEqual(client.state,idle);
  assert.deepEqual(calls.slice(3),[
    {path:'/api/bootstrap',method:'GET',token:undefined},
    {path:'/api/procedure/status',method:'GET',token:'new-server-token'},
  ]);
  assert.equal(calls.filter(call=>call.method==='POST').length,1);
});

test('source validation rejects flight or AGC claims instead of presenting them as checklist results',()=>{
  for(const changes of [{schemaVersion:2},{mode:'LIVE AGC EXECUTION'},{classification:'VERIFIED RECORDED EXECUTION'},
    {capabilities:{...capabilities,mode:'LIVE AGC EXECUTION'}},
    {capabilities:{...capabilities,originalAgc:true}},{capabilities:{...capabilities,flightPhysics:true}},
    {capabilities:{...capabilities,sensorReadback:true}},{capabilities:{...capabilities,historicalMissionClock:true}},
    {positionM:[1,2,3]},{quaternion:[1,0,0,0]},{lastSequence:-2},{revision:-1},{attachment:'landed'},{currentStep:[]}]){
    assert.throws(()=>validateProcedureSnapshot(snapshot(changes)),/Invalid procedure snapshot/);
  }
  assert.equal(validateProcedureSnapshot(snapshot({lastSequence:-1})).lastSequence,-1);
});

test('actual ProcedureService idle, start and action snapshots satisfy the browser contract',async()=>{
  const script="import json\nfrom backend.procedure_service import ProcedureService\nfrom backend.tests.test_procedure_service import definition\ns=ProcedureService(definition=definition())\nidle=s.snapshot()\nstarted=s.start()\na=s.action(started['sessionId'],0,0,'LMP','closeout','CONFIRMED')\nprint(json.dumps({'idle':idle,'started':started,'ack':a}))\n";
  const actual=JSON.parse(execFileSync('python3',['-B','-c',script],{cwd:fileURLToPath(new URL('../../',import.meta.url)),encoding:'utf8'}));
  assert.equal(validateProcedureSnapshot(actual.idle).lastSequence,-1);assert.equal(actual.idle.status,'idle');
  assert.equal(validateProcedureSnapshot(actual.started).lastSequence,-1);assert.equal(actual.started.status,'active');
  let reads=0;const client=new ProcedureClient({fetchImpl:async(path,options)=>{
    if(path==='/api/bootstrap')return response(bootstrap());
    if(path==='/api/procedure/status')return response(actual.idle);
    if(path==='/api/procedure/start')return response(actual.started,202);
    const body=JSON.parse(options.body);assert.equal(body.sequence,0);assert.equal(body.expectedRevision,0);reads++;return response(actual.ack);
  }});
  await client.connect();await client.start();const result=await client.act('LMP','closeout','CONFIRMED');
  assert.equal(reads,1);assert.equal(result.snapshot.currentStep.id,'guidance');assert.equal(client.state.revision,1);
});

test('refresh is a single explicit GET and a complete session cannot submit more actions',async()=>{
  const complete=snapshot({status:'complete',currentStep:null,completed:true});
  const server=service(()=>{throw new Error('Unexpected POST');},complete);
  const client=new ProcedureClient({fetchImpl:server.fetchImpl});await client.connect();
  await client.refresh();assert.equal(server.calls.at(-1).method,'GET');
  await assert.rejects(client.act('CMP','release','EXTD/REL'),/active procedure/);assert.equal(server.calls.length,3);
});
