import test from 'node:test';
import assert from 'node:assert/strict';
import {projectAlignmentStar} from '../dist/earth-alignment-panel.mjs';

const near=(actual,expected,tolerance=1e-8)=>assert.ok(Math.abs(actual-expected)<tolerance,`${actual} differs from ${expected}`);
const projectedRadius=angle=>84*Math.tan(angle*Math.PI/180)/Math.tan(Math.PI/6);

test('a star on the measured optical axis projects onto the reticle for arbitrary encoder angles',()=>{
  for(const [shaftDeg,trunnionDeg]of [[0,40],[104.275,40],[359.5,65],[182,0],[50,90]]) {
    const point=projectAlignmentStar({shaftDeg,trunnionDeg},{shaftDeg,trunnionDeg});
    assert.equal(point.visible,true);near(point.x,0);near(point.y,0);
  }
});

test('a known angular separation follows perspective geometry rather than an arbitrary screen offset',()=>{
  const positive=projectAlignmentStar({shaftDeg:0,trunnionDeg:90},{shaftDeg:10,trunnionDeg:90});
  assert.equal(positive.visible,true);near(positive.x,projectedRadius(10));near(positive.y,0);
  const trunnion=projectAlignmentStar({shaftDeg:0,trunnionDeg:40},{shaftDeg:0,trunnionDeg:50});
  assert.equal(trunnion.visible,true);near(trunnion.x,0);near(trunnion.y,-projectedRadius(10));
});

test('changing measured encoders changes the sight picture while a fixed star remains fixed',()=>{
  const star=Object.freeze({shaftDeg:0,trunnionDeg:40});
  const before=projectAlignmentStar({shaftDeg:0,trunnionDeg:40},star);
  const after=projectAlignmentStar({shaftDeg:0,trunnionDeg:45},star);
  near(before.x,0);near(before.y,0);near(after.x,0);near(after.y,projectedRadius(5));
  assert.notEqual(after.y,before.y);assert.deepEqual(star,{shaftDeg:0,trunnionDeg:40});
});

test('targets beyond the declared 30-degree field radius are excluded',()=>{
  const inside=projectAlignmentStar({shaftDeg:0,trunnionDeg:90},{shaftDeg:29.9,trunnionDeg:90});
  const outside=projectAlignmentStar({shaftDeg:0,trunnionDeg:90},{shaftDeg:30.1,trunnionDeg:90});
  assert.equal(inside.visible,true);assert.equal(outside.visible,false);
  assert.ok(Math.hypot(inside.x,inside.y)<84);assert.ok(Math.hypot(outside.x,outside.y)>84);
});

test('behind-axis stars stay off field with a finite direction, including the exact antipode',()=>{
  for(const star of [{shaftDeg:180,trunnionDeg:90},{shaftDeg:120,trunnionDeg:90},{shaftDeg:0,trunnionDeg:-90}]) {
    const point=projectAlignmentStar({shaftDeg:0,trunnionDeg:90},star);
    assert.equal(point.visible,false);assert.ok(Number.isFinite(point.x));assert.ok(Number.isFinite(point.y));
    assert.ok(Math.hypot(point.x,point.y)>0);
  }
});

test('shaft wraparound represents the same direction and remains continuous near zero',()=>{
  const model={shaftDeg:359,trunnionDeg:90};
  const first=projectAlignmentStar(model,{shaftDeg:1,trunnionDeg:90});
  const equivalent=projectAlignmentStar(model,{shaftDeg:361,trunnionDeg:90});
  near(first.x,projectedRadius(2));near(first.x,equivalent.x);near(first.y,equivalent.y);
  assert.equal(first.visible,true);assert.equal(equivalent.visible,true);
});
