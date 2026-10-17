import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSpacecraftMesh } from '../dist/spacecraft-mesh.mjs';
import { createFlightRenderer, lookAtMatrix, multiplyMatrices, perspectiveMatrix, quaternionMatrix, transformPoint, validQuaternion } from '../dist/spacecraft-3d.mjs';
import { rotateVector } from '../dist/replay.mjs';

const close=(actual,expected,epsilon=1e-7)=>{
  assert.equal(actual.length,expected.length);
  actual.forEach((value,i)=>assert.ok(Math.abs(value-expected[i])<epsilon,`${value} differs from ${expected[i]} at ${i}`));
};

test('GPU rotation respects the fixture scalar-first body-to-stable quaternion convention',()=>{
  const orientations=[[1,0,0,0],[Math.SQRT1_2,0,0,Math.SQRT1_2],[.5,.5,-.5,.5]];
  for(const q of orientations){
    for(const vector of [[1,0,0],[0,1,0],[0,0,1],[2,-3,4]]){
      const transformed=transformPoint(quaternionMatrix(q),vector);
      close(transformed.slice(0,3),rotateVector(q,vector));assert.equal(transformed[3],1);
      assert.ok(Math.abs(Math.hypot(...transformed.slice(0,3))-Math.hypot(...vector))<1e-7);
    }
  }
  close(transformPoint(quaternionMatrix(orientations[1]),[0,1,0]),[-1,0,0,1]);
});

test('unavailable, malformed or non-unit orientations do not become invented attitude',()=>{
  for(const q of [null,undefined,[],[0,0,0,0],[2,0,0,0],[1,NaN,0,0],[1,0,0,0,0]]){
    assert.equal(validQuaternion(q),false);
    assert.throws(()=>quaternionMatrix(q),/unit body-to-stable quaternion/);
  }
});

test('perspective camera separates front from back and matrix composition preserves world coordinates',()=>{
  const camera=lookAtMatrix([0,0,8],[0,0,0]);
  close(transformPoint(camera,[0,0,0]),[0,0,-8,1]);
  const projection=perspectiveMatrix(Math.PI/4,1,.1,100);
  const combined=multiplyMatrices(projection,camera);
  const front=transformPoint(combined,[0,0,1]),rear=transformPoint(combined,[0,0,-1]);
  assert.ok(front[3]>0 && rear[3]>0);
  assert.ok(front[2]/front[3]<rear[2]/rear[3],'closer surfaces have smaller depth-buffer values');
  const right=transformPoint(combined,[1,0,0]);assert.ok(right[0]>0);
  const up=transformPoint(combined,[0,1,0]);assert.ok(up[1]>0);
  close(transformPoint(combined,[2,-1,0]),transformPoint(projection,transformPoint(camera,[2,-1,0]).slice(0,3)));
});

test('LM mesh is finite depth geometry with normalized faces and distinct structural components',()=>{
  const model=buildSpacecraftMesh();
  assert.ok(model.positions.length>10000,'real mesh, not a flat spacecraft sprite');
  assert.equal(model.positions.length%9,0);
  assert.equal(model.positions.length,model.normals.length);assert.equal(model.positions.length,model.colors.length);
  assert.equal(model.lines.length,model.lineColors.length);
  for(const data of [model.positions,model.normals,model.colors,model.lines,model.ghostLines])assert.ok(data.every(Number.isFinite));
  for(let i=0;i<model.normals.length;i+=3)assert.ok(Math.abs(Math.hypot(...model.normals.slice(i,i+3))-1)<1e-5);
  for(let axis=0;axis<3;axis++){
    assert.ok(model.bounds.max[axis]-model.bounds.min[axis]>3,'model has depth in every body axis');
    assert.ok(model.bounds.min[axis]>-3 && model.bounds.max[axis]<3,'illustrative geometry stays in its camera bounds');
  }
  for(const name of ['descent-stage','ascent-cabin','windows-and-hatch','landing-gear','inert-descent-engine','rcs-clusters','antennae-and-ladder']){
    assert.ok(model.components[name].vertexCount>0,`${name} has actual triangles`);
  }
  assert.ok(model.ghostLines.length>100,'target outline is available independently from body state');
  assert.equal(model.units,'illustrative model units');
});

test('procedural visual model is deterministic and rebuilding does not accumulate geometry',()=>{
  const first=buildSpacecraftMesh(),second=buildSpacecraftMesh();
  assert.deepEqual(first.positions,second.positions);assert.deepEqual(first.normals,second.normals);
  assert.deepEqual(first.bounds,second.bounds);
});

test('3D fallback hides unavailable flight orientation and camera controls never mutate supplied state',()=>{
  let faces=0;const coordinates=[],listeners=new Map();
  const context={setTransform(){},clearRect(){},fillRect(){},createRadialGradient(){return{addColorStop(){}};},
    beginPath(){},closePath(){},fill(){faces++;},stroke(){},moveTo(x,y){coordinates.push(x,y);},lineTo(x,y){coordinates.push(x,y);}};
  const canvas={clientWidth:800,clientHeight:600,width:0,height:0,
    getContext(kind){return kind==='2d'?context:null;},
    addEventListener(name,listener){listeners.set(name,listener);},removeEventListener(name){listeners.delete(name);}};
  const renderer=createFlightRenderer(canvas);
  assert.equal(renderer.kind,'Canvas 3D');assert.match(renderer.status.message,/WebGL unavailable/);
  const input={quaternion:[1,0,0,0],targetQuaternion:null,available:false};
  renderer.draw(input);assert.equal(faces,0,'unavailable authoritative attitude does not reveal a placeholder vehicle');
  input.available=true;const original=JSON.stringify(input);
  renderer.draw(input);assert.ok(faces>1000,'fallback projects the real three-dimensional mesh');
  renderer.orbit(100,-50);renderer.zoom(-200);renderer.draw(input);renderer.reset();
  assert.equal(JSON.stringify(input),original);assert.ok(coordinates.every(Number.isFinite));
  renderer.dispose();assert.equal(renderer.status.available,false);assert.equal(listeners.size,0);
});
