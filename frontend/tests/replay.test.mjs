import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activeJets, frameAt, lastAt, octal, formatTime, originalReadiness, presentationQuaternion, rcsAt, rotateVector, slerp, validateReplay, wrappedDegrees } from '../dist/replay.mjs';

const data = JSON.parse(readFileSync(new URL('../dist/data/replay.json', import.meta.url)));
const combined = data.cases.find(c => c.id === 'combined');
const near = (a,b,tolerance=1e-12) => assert.ok(Math.abs(a-b) < tolerance, `${a} ≠ ${b}`);

test('exported real data satisfies the presentation contract',()=>{
  assert.equal(validateReplay(data),data);
  assert.equal(combined.durationSeconds,37.5);
  assert.equal(data.cases.length,5);
});
test('seeking holds the last real sample and never selects future telemetry',()=>{
  const frames=[{t:1},{t:2},{t:3}];
  assert.equal(lastAt(frames,.9),null);
  assert.equal(lastAt(frames,2),frames[1]);
  assert.equal(lastAt(frames,2.5),frames[1]);
  assert.equal(lastAt(frames,4),frames[2]);
});
test('RCS words follow interleaved actual event edges without looking ahead',()=>{
  const fixture={rcsEvents:[{t:1,channel:5,value:4},{t:2,channel:6,value:170},{t:3,channel:5,value:0}]};
  assert.deepEqual(rcsAt(fixture,.5),{5:null,6:null});
  assert.deepEqual(rcsAt(fixture,1),{5:4,6:null});
  assert.deepEqual(rcsAt(fixture,2.5),{5:4,6:170});
  assert.deepEqual(rcsAt(fixture,3),{5:0,6:170});
});
test('source-derived jet names and bit positions remain distinct from axes',()=>{
  const jets=activeJets({5:0o204,6:0o252});
  assert.deepEqual(jets.filter(j=>j.active).map(j=>j.name),['Q3U','Q1D','Q4F','Q2A','Q3R','Q1L']);
  assert.ok(activeJets({5:null,6:null}).every(j=>j.active===null));
});
test('scalar-first active body-to-stable quaternion has the right handed sign',()=>{
  const q=[Math.SQRT1_2,Math.SQRT1_2,0,0];
  const v=rotateVector(q,[0,1,0]);
  near(v[0],0);near(v[1],0);near(v[2],1);
});
test('render rotation preserves vector lengths for actual compound attitude',()=>{
  const q=combined.frames.at(-1).q;
  const v=rotateVector(q,[2,-3,4]);
  near(Math.hypot(...v),Math.sqrt(29));
});
test('SLERP follows the short quaternion arc and normalizes presentation',()=>{
  const a=[1,0,0,0],b=[-Math.SQRT1_2,0,0,-Math.SQRT1_2];
  const half=slerp(a,b,.5);
  near(Math.hypot(...half),1);
  const v=rotateVector(half,[1,0,0]);
  near(v[0],Math.SQRT1_2);near(v[1],Math.SQRT1_2);
});
test('rendering freezes at the actual horizon without extrapolating residual rate',()=>{
  const q=combined.frames.at(-1).q;
  assert.deepEqual(presentationQuaternion(combined,37.5),q);
  assert.deepEqual(presentationQuaternion(combined,1000),q);
  assert.deepEqual(frameAt(combined,1000),combined.frames.at(-1));
  assert.ok(Math.abs(combined.frames.at(-1).omega[1])>1);
});
test('interpolated drawing does not mutate held actual samples',()=>{
  const before=JSON.stringify(combined.frames);
  const frame=frameAt(combined,32.123);
  assert.ok(frame.t<=32.123);
  near(Math.hypot(...presentationQuaternion(combined,32.123)),1);
  assert.equal(JSON.stringify(combined.frames),before);
});
test('gimbal wrapping and octal register presentation preserve values',()=>{
  near(wrappedDegrees(346.1046272649544),-13.8953727350456);
  assert.equal(octal(170),'00252');
  assert.equal(octal(null),'— — — — —');
  assert.equal(formatTime(59.9996),'01:00.000');
});
test('physical freeze is distinct from the one-count settlement tail',()=>{
  assert.equal(combined.frames.at(-1).cdu[1],1476);
  assert.equal(combined.finalCdu[1],1477);
  assert.ok(combined.settledCycle>combined.horizonCycle);
});
test('original readiness requires actual P00 and both original inhibition gates',()=>{
  const early = combined.frames.find(f => f.readiness?.modreg === 32767 && (f.readiness.imodes33 & 32));
  assert.ok(early);
  assert.equal(originalReadiness(early.readiness),false);
  const ready = combined.frames.find(f => originalReadiness(f.readiness));
  assert.ok(ready);
  assert.ok(ready.readiness.cycle > early.readiness.cycle);
  for (const gate of ['imodes30','imodes33']) assert.equal(originalReadiness({...ready.readiness,[gate]:ready.readiness[gate]|32}),false);
  assert.equal(originalReadiness({...ready.readiness,modreg:32767}),false);
  assert.equal(originalReadiness({...ready.readiness,failreg:[0,0,1]}),false);
  assert.equal(originalReadiness(null),false);
});
test('malformed quaternion and command chronology fail rather than fabricate',()=>{
  const bad=structuredClone(data);bad.cases[0].frames[0].q=[0,0,0,0];
  assert.throws(()=>validateReplay(bad),/orientation/);
  const reversed=structuredClone(data);reversed.cases[0].rcsEvents.reverse();
  assert.throws(()=>validateReplay(reversed),/command/);
});
test('non-numeric times and out-of-range authentic words are rejected',()=>{
  const badTime=structuredClone(data);badTime.cases[0].frames[0].t='unknown';
  assert.throws(()=>validateReplay(badTime),/chronology/);
  const badWord=structuredClone(data);badWord.cases[0].rcsEvents[0].value=32768;
  assert.throws(()=>validateReplay(badWord),/command/);
});
