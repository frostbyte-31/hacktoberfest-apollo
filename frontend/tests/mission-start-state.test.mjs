import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateOperations,replayMilestones,physicalStart,adjacentReplayEvent} from '../dist/mission-start-state.mjs';

const operations=JSON.parse(readFileSync(new URL('../dist/data/apollo-operations.json',import.meta.url),'utf8'));
const propulsion=JSON.parse(readFileSync(new URL('../dist/data/propulsion.json',import.meta.url),'utf8'));
const connected=propulsion.cases.find(item=>item.id==='connected');
const changed=mutate=>{const data=structuredClone(operations);mutate(data);return data;};

test('actual Apollo operations reference validates all fourteen ordered chapters and six controls',()=>{
  const before=JSON.stringify(operations);
  assert.equal(validateOperations(operations),operations);
  assert.equal(operations.timeline.length,14);
  assert.equal(operations.timeline[0].id,'docked-preparation');
  assert.deepEqual(operations.timeline.map(item=>item.order),Array.from({length:14},(_,i)=>i+1));
  assert.equal(operations.controls.length,6);
  assert.equal(JSON.stringify(operations),before);
});

test('source citations require HTTPS and referenced identifiers must exist',()=>{
  for(const mutate of [
    data=>{data.sources[0].url='http://example.org/checklist';},
    data=>{data.sources[0].url='javascript:alert(1)';},
    data=>{data.sources[0].url='https://user:secret@example.org/checklist';},
    data=>{data.timeline[0].sourceIds=['missing-source'];},
    data=>{data.controls[0].modes[0].sourceIds=['missing-source'];},
    data=>{data.chapter.startingConfiguration[0].sourceIds=[];},
    data=>{data.softwareEntry.files[0].sourceIds=['missing-source'];},
  ])assert.throws(()=>validateOperations(changed(mutate)),/Invalid Apollo operations reference/);
});

test('duplicate identities, missing chapters, reversed order, and a synthetic starting chapter are rejected',()=>{
  for(const mutate of [
    data=>{data.schemaVersion=2;},
    data=>{data.sources.push({...data.sources[0]});},
    data=>{data.timeline[1].id=data.timeline[0].id;},
    data=>{data.timeline.pop();},
    data=>{[data.timeline[1],data.timeline[2]]=[data.timeline[2],data.timeline[1]];},
    data=>{data.timeline[0].id='synthetic-yaw-challenge';},
    data=>{data.controls.pop();},
    data=>{data.controls[1].id=data.controls[0].id;},
    data=>{data.controls[0].modes.push({...data.controls[0].modes[0]});},
  ])assert.throws(()=>validateOperations(changed(mutate)),/Invalid Apollo operations reference/);
});

test('validation checks citation structure without rewriting historical prose or parsing approximate GET labels',()=>{
  const variant=changed(data=>{
    data.timeline[0].getLabel='Checklist reference; approximate time';
    data.sources[0].revisionScope='Updated editorial limitation from reviewed source.';
    data.controls[0].purpose='A source-reviewed explanation.';
  });
  assert.equal(validateOperations(variant),variant);
});

test('significant replay milestones begin at actual P63LM and omit individual recorded input transactions',()=>{
  for(const item of propulsion.cases){
    const events=replayMilestones(item);
    assert.match(events[0].id,/^p63lm-/);
    assert.equal(events[0].routine,'P63LM');
    assert.ok(events.every(event=>event.kind!=='dsky-input'&&event.kind!=='cockpit-input'));
    assert.ok(events.every(event=>event.cycle>=events[0].cycle));
    for(const title of ['V99 N62 · crew enable request','Original ENGINE ON output','Original FLATOUT','P00 · software shutdown','Crew disarm','Retained experiment ends'])assert.ok(events.some(event=>event.title===title));
    assert.ok(events.every(event=>item.events.includes(event)));
  }
});

test('full milestone review preserves every retained event and original raw-row order',()=>{
  for(const item of propulsion.cases){
    const events=replayMilestones(item,true);
    assert.deepEqual(events,item.events);
    assert.notEqual(events,item.events);
    assert.ok(events.some(event=>event.kind==='dsky-input'));
    assert.ok(events.some(event=>event.kind==='cockpit-input'));
    events.pop();
    assert.equal(replayMilestones(item,true).length,item.events.length);
  }
  assert.deepEqual(replayMilestones({events:[]}),[]);
  assert.deepEqual(replayMilestones({events:[{id:'preparation',kind:'execution'}]}),[]);
});

test('physical replay start is the first real spacecraft frame rather than CPU or historical mission zero',()=>{
  for(const item of propulsion.cases){
    const first=item.frames.find(frame=>frame.spacecraft);
    assert.equal(physicalStart(item),first.t);
    assert.ok(physicalStart(item)>0);
    assert.notEqual(physicalStart(item),first.spacecraft.physicalTimeSeconds);
    assert.notEqual(physicalStart(item),item.initialGeometry.initializedEpochSeconds);
    assert.ok(item.frames.filter(frame=>frame.t<physicalStart(item)).every(frame=>frame.spacecraft===null));
  }
  assert.equal(physicalStart({frames:[{t:0,spacecraft:null}]}),null);
  assert.equal(physicalStart({frames:[]}),null);
});

test('next and previous selection step through distinct actual raw rows sharing one CPU cycle',()=>{
  const events=replayMilestones(connected,true);
  const index=events.findIndex((event,i)=>i>0&&event.t===events[i-1].t&&event.source.rawLine!==events[i-1].source.rawLine);
  const first=events[index-1],second=events[index];
  assert.equal(first.cycle,second.cycle);
  assert.notEqual(first.source.rawLine,second.source.rawLine);
  assert.equal(adjacentReplayEvent(events,first.t,1,first.id),second);
  assert.equal(adjacentReplayEvent(events,second.t,-1,second.id),first);
});

test('all milestones remain individually reachable in both directions including tied final disarm and finish',()=>{
  const events=replayMilestones(connected);
  let event=events[0];
  for(let index=1;index<events.length;index++){
    event=adjacentReplayEvent(events,event.t,1,event.id);
    assert.equal(event,events[index]);
  }
  assert.equal(adjacentReplayEvent(events,event.t,1,event.id),null);
  for(let index=events.length-2;index>=0;index--){
    event=adjacentReplayEvent(events,event.t,-1,event.id);
    assert.equal(event,events[index]);
  }
  assert.equal(adjacentReplayEvent(events,event.t,-1,event.id),null);
  assert.equal(events.at(-1).cycle,events.at(-2).cycle);
  assert.notEqual(events.at(-1).source.rawLine,events.at(-2).source.rawLine);
});

test('clock-based selection uses strict direction and bounds when no event identity is selected',()=>{
  const events=replayMilestones(connected);
  assert.equal(adjacentReplayEvent(events,-1,1),events[0]);
  assert.equal(adjacentReplayEvent(events,-1,-1),null);
  assert.equal(adjacentReplayEvent(events,connected.durationSeconds+1,1),null);
  assert.equal(adjacentReplayEvent(events,connected.durationSeconds+1,-1),events.at(-1));
  const seconds=(events[0].t+events[1].t)/2;
  assert.equal(adjacentReplayEvent(events,seconds,1),events[1]);
  assert.equal(adjacentReplayEvent(events,seconds,-1),events[0]);
  assert.equal(adjacentReplayEvent(events,seconds,1,'missing-event'),events[1]);
  assert.equal(adjacentReplayEvent(events,events[0].t,1),events[1]);
  assert.equal(adjacentReplayEvent(events,events[0].t,-1),null);
  assert.equal(adjacentReplayEvent([],0,1),null);
});

test('invalid replay clock and direction cannot accidentally expose a future event',()=>{
  const events=replayMilestones(connected);
  for(const value of [NaN,Infinity,-Infinity,'200',undefined])assert.throws(()=>adjacentReplayEvent(events,value,1),/Invalid execution time/);
  for(const value of [0,2,'next',undefined])assert.throws(()=>adjacentReplayEvent(events,0,value),/direction/);
});
