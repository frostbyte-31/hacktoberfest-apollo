import test from 'node:test';
import assert from 'node:assert/strict';
import { flight3DViewModel, flight3DCamera, createFlight3DRenderer } from '../dist/flight-view-3d.mjs';
import { transformPoint } from '../dist/spacecraft-3d.mjs';
import { buildSpacecraftMesh } from '../dist/spacecraft-mesh.mjs';

const R=1738090;
const craft={positionM:[R+150,0,30],velocityMps:[-5,0,1],quaternionBodyToRef:[1,0,0,0],altitudeM:Math.hypot(R+150,0,30)-R};
const engine={enabled:true,thrustN:12000};
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} differs from ${b}`);

test('the 3D laboratory preserves the supplied r/v/quaternion and identifies its educational source',()=>{
  const before=structuredClone(craft),view=flight3DViewModel(craft,engine,{heightM:200});
  assert.deepEqual(craft,before);
  assert.deepEqual(view.positionM,craft.positionM);assert.notEqual(view.positionM,craft.positionM);
  assert.deepEqual(view.velocityMps,craft.velocityMps);assert.deepEqual(view.quaternionBodyToRef,craft.quaternionBodyToRef);
  assert.equal(view.mode,'EDUCATIONAL_PHYSICS_LAB');assert.equal(view.classification,'EDUCATIONAL PHYSICS LAB');
  assert.match(view.metadata.source,/not original AGC landing guidance/);
  assert.match(view.metadata.motion,/no frontend physics, interpolation or predicted trajectory/);
});

test('local rendering is a proper basis rotation with uniform position scale and explicit origin',()=>{
  const view=flight3DViewModel(craft,engine,{heightM:200});
  assert.equal(view.metresPerUnit,25);
  close(view.originM[0],R);assert.deepEqual(view.originM.slice(1),[0,0]);
  close(view.spacecraftPosition[0]*view.metresPerUnit,craft.positionM[2]);
  close(view.spacecraftPosition[1]*view.metresPerUnit+R,craft.positionM[0]);
  close(view.spacecraftPosition[2]*view.metresPerUnit,craft.positionM[1]);
  const x=transformPoint(view.rotation,[1,0,0]).slice(0,3),y=transformPoint(view.rotation,[0,1,0]).slice(0,3),z=transformPoint(view.rotation,[0,0,1]).slice(0,3);
  assert.deepEqual(x,[0,1,0]);assert.deepEqual(y,[0,0,1]);assert.deepEqual(z,[1,0,0]);
});

test('positive backend pitch directs thrust toward negative downrange without deriving attitude from a display angle',()=>{
  const q=[Math.cos(Math.PI/8),0,Math.sin(Math.PI/8),0];
  const view=flight3DViewModel({...craft,quaternionBodyToRef:q,pitchDeg:-999},engine);
  const thrust=transformPoint(view.rotation,[1,0,0]);
  close(thrust[0],-Math.SQRT1_2);close(thrust[1],Math.SQRT1_2);
  assert.deepEqual(view.quaternionBodyToRef,q);
});

test('the enlarged illustrative mesh registers its lowest point at the measured reference without changing physical data',()=>{
  const grounded={...craft,positionM:[R,0,0],altitudeM:0};
  const view=flight3DViewModel(grounded,engine,{heightM:200}),mesh=buildSpacecraftMesh();
  let lowestY=Infinity;
  for(let i=0;i<mesh.positions.length;i+=3)lowestY=Math.min(lowestY,transformPoint(view.craftModel,Array.from(mesh.positions.slice(i,i+3)))[1]);
  close(lowestY,0);assert.deepEqual(view.positionM,grounded.positionM);
  assert.match(view.metadata.geometry,/not collision geometry/);assert.match(view.metadata.scale,/enlarged/);
});

test('velocity cue uses only measured direction and never predicts a future position',()=>{
  const a=flight3DViewModel(craft,engine),b=flight3DViewModel({...craft,velocityMps:craft.velocityMps.map(value=>value*10)},engine);
  a.velocityArrow.forEach((point,index)=>point.forEach((value,axis)=>close(value,b.velocityArrow[index][axis])));
  assert.equal(a.velocityLines.length,6);
  const zero=flight3DViewModel({...craft,velocityMps:[0,0,0]},engine);
  assert.equal(zero.velocityArrow,null);assert.deepEqual(zero.velocityLines,[]);
  assert.equal(Object.hasOwn(a,'trajectoryM'),false);
  assert.deepEqual(flight3DViewModel({...craft,elapsedSeconds:900},engine).craftModel,a.craftModel);
});

test('invalid authoritative spatial state is rejected instead of substituting a demonstration orbit',()=>{
  for(const change of [{positionM:null},{positionM:[NaN,0,0]},{velocityMps:null},{quaternionBodyToRef:null},{quaternionBodyToRef:[0,0,0,0]},{altitudeM:NaN},{positionM:[0,0,0],altitudeM:0}]){
    assert.throws(()=>flight3DViewModel({...craft,...change},engine),/requires actual server|valid lunar/);
  }
});

test('plume visualization requires delivered enabled thrust rather than a requested throttle',()=>{
  assert.equal(flight3DViewModel(craft,engine).thrusting,true);
  assert.equal(flight3DViewModel(craft,{enabled:false,thrustN:12000,throttle:1}).thrusting,false);
  assert.equal(flight3DViewModel(craft,{enabled:true,thrustN:0,throttle:1}).thrusting,false);
});

test('Canvas fallback draws a finite 3D mesh and camera input changes no supplied state',()=>{
  const coordinates=[],listeners=new Map();let faces=0;
  const context={setTransform(){},fillRect(){},beginPath(){},closePath(){},fill(){faces++;},stroke(){},moveTo(x,y){coordinates.push(x,y);},lineTo(x,y){coordinates.push(x,y);}};
  const canvas={clientWidth:800,clientHeight:440,width:0,height:0,getContext(kind){return kind==='2d'?context:null;},addEventListener(name,handler){listeners.set(name,handler);},removeEventListener(name){listeners.delete(name);},setPointerCapture(){}};
  const renderer=createFlight3DRenderer(canvas),scene=flight3DViewModel(craft,engine),before=structuredClone(scene);
  assert.equal(renderer.kind,'Canvas 3D projection');renderer.draw(scene);
  assert.ok(faces>500);assert.ok(coordinates.every(Number.isFinite));
  listeners.get('pointerdown')({button:0,clientX:100,clientY:100,pointerId:1});
  listeners.get('pointermove')({clientX:160,clientY:120});listeners.get('pointerup')({});
  listeners.get('wheel')({deltaY:30,preventDefault(){}});renderer.reset();
  assert.deepEqual(scene,before);assert.deepEqual(scene.positionM,craft.positionM);
  renderer.dispose();assert.equal(listeners.size,0);
});

test('default camera fits the complete LM and landing reference at all lab start heights on desktop and mobile',()=>{
  const mesh=buildSpacecraftMesh();
  for(const altitudeM of[0,150,300])for(const pitch of[0,-Math.PI/4,Math.PI/4]){
    const state={...craft,positionM:[R+altitudeM,0,0],altitudeM,quaternionBodyToRef:[Math.cos(pitch/2),0,Math.sin(pitch/2),0]};
    const scene=flight3DViewModel(state,engine,{heightM:Math.max(100,altitudeM*1.18)});
    for(const[width,height]of[[900,440],[600,440],[330,350],[280,350]]){
      const camera=flight3DCamera(scene,width,height),vertices=[];
      for(let i=0;i<mesh.positions.length;i+=3)vertices.push(transformPoint(scene.craftModel,Array.from(mesh.positions.slice(i,i+3))).slice(0,3));
      for(const point of[...vertices,...scene.target]){
        const clip=transformPoint(camera.viewProjection,point);
        assert.ok(clip[3]>0,'All visible geometry must be in front of the camera');
        const x=clip[0]/clip[3],y=clip[1]/clip[3];
        assert.ok(Math.abs(x)<=.9&&Math.abs(y)<=.9,`${altitudeM}m pitch${pitch}, ${width}x${height}: model/reference clipped at ${x},${y}`);
      }
    }
  }
});
