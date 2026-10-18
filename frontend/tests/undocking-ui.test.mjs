import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateUndockingDefinition } from '../dist/undocking-ui.mjs';

const actual=JSON.parse(readFileSync(new URL('../dist/data/undocking-procedure.json',import.meta.url),'utf8'));
const fresh=()=>structuredClone(actual);
const selector=data=>data.steps.find(step=>step.kind==='select');
const report=data=>data.steps.find(step=>step.kind==='crew-report');
const release=data=>data.steps.find(step=>step.effect==='release');
const rejectsMutation=mutate=>{const data=fresh();mutate(data);assert.throws(()=>validateUndockingDefinition(data));};

test('the retained source definition validates without a DOM or changing its content',()=>{
  const data=fresh(),before=JSON.stringify(data);
  assert.equal(validateUndockingDefinition(data),data);assert.equal(JSON.stringify(data),before);
  assert.equal(data.mode,'INTERACTIVE PROCEDURE TRAINER');assert.ok(data.steps.length>20);
  assert.deepEqual(new Set(data.steps.map(step=>step.role)),new Set(['CDR','LMP','CMP']));
  assert.ok(data.entryPreconditions.some(item=>/P47\/AGS/.test(item.label)),'The skipped original computer bookkeeping must remain an explicit entry boundary');
});

test('actual undocking uses the CMP probe release control and preserves later inspection ordering',()=>{
  const item=release(actual),index=actual.steps.indexOf(item);
  assert.equal(item.role,'CMP');assert.equal(item.kind,'momentary');assert.equal(item.correctValue,'EXTD/REL');
  assert.equal(item.controlId,'csm.dockingProbe');assert.match(item.locator,/panel 2/);
  assert.ok(index>0);assert.ok(index<actual.steps.findIndex(step=>step.id==='confirm-release'));
  assert.ok(actual.steps.findIndex(step=>step.id==='confirm-release')<actual.steps.findIndex(step=>step.id==='inspection-handoff'));
  assert.equal(actual.steps.filter(step=>step.effect==='release').length,1);
});

test('external source links reject executable, unencrypted and credential-bearing addresses',()=>{
  for(const url of['javascript:alert(1)','data:text/html,test','http://example.com/manual','https://user:secret@example.com/manual','file:///tmp/manual.pdf']){
    rejectsMutation(data=>{data.sources[0].url=url;});
  }
});

test('checklist source references must have unique nonempty identities and resolve for every action',()=>{
  rejectsMutation(data=>{data.sources.push({...data.sources[0]});});
  rejectsMutation(data=>{data.sources[0].id='';});
  rejectsMutation(data=>{data.sources[0].id=null;});
  rejectsMutation(data=>{data.steps[0].sourceIds=[];});
  rejectsMutation(data=>{data.steps[0].sourceIds=['missing-reference'];});
  rejectsMutation(data=>{data.steps[0].sourceIds=[data.steps[0].sourceIds[0],data.steps[0].sourceIds[0]];});
});

test('only named Apollo crew roles and explicit procedure action kinds are accepted',()=>{
  for(const role of[undefined,'PILOT','constructor','toString','__proto__'])rejectsMutation(data=>{data.steps[0].role=role;});
  for(const kind of[undefined,'live-engine-command','constructor','toString','__proto__'])rejectsMutation(data=>{data.steps[0].kind=kind;});
});

test('each checklist action needs a unique identity, readable instruction and source locator',()=>{
  rejectsMutation(data=>{data.steps[0].id=data.steps[1].id;});
  for(const field of['id','label','locator']){
    rejectsMutation(data=>{data.steps[0][field]='';});
    rejectsMutation(data=>{delete data.steps[0][field];});
  }
});

test('selector contracts require distinct labeled positions and an explicit supported setting',()=>{
  rejectsMutation(data=>{delete selector(data).controlId;});
  rejectsMutation(data=>{selector(data).controlId='';});
  rejectsMutation(data=>{selector(data).options=[selector(data).options.find(option=>option.value===selector(data).correctValue)];});
  rejectsMutation(data=>{const step=selector(data);step.options.push({...step.options[0]});});
  rejectsMutation(data=>{selector(data).options[0].label='';});
  rejectsMutation(data=>{selector(data).options[0].value={fake:'position'};});
  rejectsMutation(data=>{selector(data).correctValue='NOT A SWITCH POSITION';});
});

test('crew-report and momentary instructions require a scalar value without unsupported effects',()=>{
  for(const correctValue of[undefined,null,[],{},NaN])rejectsMutation(data=>{report(data).correctValue=correctValue;});
  rejectsMutation(data=>{report(data).effect='ignite-engine';});
  rejectsMutation(data=>{release(data).role='CDR';});
  rejectsMutation(data=>{release(data).kind='crew-report';});
  rejectsMutation(data=>{delete release(data).effect;});
  rejectsMutation(data=>{report(data).effect='release';});
});

test('a procedure source cannot claim live AGC execution or a flight simulation mode',()=>{
  for(const mode of[undefined,'LIVE AGC EXECUTION','VERIFIED RECORDED EXECUTION','LIVE FLIGHT SIMULATION'])rejectsMutation(data=>{data.mode=mode;});
});
