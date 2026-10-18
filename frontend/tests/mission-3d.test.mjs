import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildSpacecraftMesh } from '../dist/spacecraft-mesh.mjs';
import { buildMissionPresentation, buildDockedCsmMesh, createMissionRenderer, validVector } from '../dist/mission-3d.mjs';
import { transformPoint } from '../dist/spacecraft-3d.mjs';

const input={available:true,mode:'verified-recorded-execution',lunarRadiusM:1738090,
  positionM:[1624406.1420843122,0,-659263.5080425026],velocityMps:[628.8888231542522,0,1549.563875894808],
  quaternion:[0.9999999999295781,-1.0915100573724746e-5,2.3469328878657304e-7,-4.652887582451265e-6],
  trajectoryM:[[1624406.1420843122,0,-659263.5080425026],[1676154.7724413767,-.003194045,-514761.6734110943]]};

const close=(a,b,tolerance=1e-8)=>assert.ok(Math.abs(a-b)<tolerance,`${a} != ${b}`);

test('retained state is preserved exactly while vehicle view changes presentation units',()=>{
  const scene=buildMissionPresentation(input);
  assert.equal(scene.mode,'verified-telemetry');
  assert.deepEqual(scene.positionM,input.positionM);assert.deepEqual(scene.velocityMps,input.velocityMps);assert.deepEqual(scene.quaternion,input.quaternion);
  assert.deepEqual(scene.spacecraftPosition,[0,0,0]);
  close(Math.hypot(...scene.moonCenter)*scene.metresPerUnit,Math.hypot(...input.positionM));
  assert.deepEqual(scene.trajectoryM,input.trajectoryM);
  assert.notEqual(scene.positionM,input.positionM);
});

test('global overview preserves supplied position ratios and only enlarges the visual LM',()=>{
  const scene=buildMissionPresentation(input,'orbit');
  scene.spacecraftPosition.forEach((value,i)=>close(value*scene.metresPerUnit,input.positionM[i]));
  assert.deepEqual(scene.moonCenter,[0,0,0]);assert.equal(scene.moonRadius,1);
  assert.ok(scene.metadata.spacecraftMetresPerModelUnit>1000);
  assert.match(scene.metadata.scale,/enlarged/);
});

test('body-to-REF quaternion controls mesh axes without introducing an attitude transform',()=>{
  const scene=buildMissionPresentation({...input,positionM:[1738090,0,0],quaternion:[Math.SQRT1_2,0,0,Math.SQRT1_2]});
  const x=transformPoint(scene.craftModel,[1,0,0]);
  close(x[0],0);close(x[1],.45);close(x[2],0);
});

test('missing or invalid authoritative state never substitutes an illustrated orbit',()=>{
  for(const state of[{},{...input,available:false},{...input,positionM:[NaN,0,0]},{...input,quaternion:[0,0,0,0]},{...input,positionM:[0,0,0]}]){
    const scene=buildMissionPresentation(state);assert.equal(scene.mode,'unavailable');assert.equal(scene.craftModel,null);assert.equal(scene.positionM,null);assert.equal(scene.velocityArrow,null);assert.deepEqual(scene.path,[]);
  }
});

test('historical docked composition requires explicit illustration mode and exposes no telemetry',()=>{
  const scene=buildMissionPresentation({...input,mode:'historical-illustration'});
  assert.equal(scene.mode,'historical-illustration');assert.equal(scene.velocityMps,null);assert.equal(scene.velocityArrow,null);assert.deepEqual(scene.path,[]);
  assert.match(scene.metadata.geometry,/schematic docked/);assert.match(scene.metadata.illustration,/no historical position/);
  assert.notDeepEqual(scene.positionM,input.positionM);
});

test('trajectory contains retained samples only and direction arrow cannot invent a speed',()=>{
  const scene=buildMissionPresentation(input);
  assert.equal(scene.path.length,input.trajectoryM.length);
  scene.path.forEach((point,j)=>point.forEach((value,i)=>close(value*scene.metresPerUnit+scene.origin[i],input.trajectoryM[j][i])));
  assert.match(scene.metadata.velocity,/does not encode speed/);
  assert.equal(buildMissionPresentation({...input,velocityMps:null}).velocityArrow,null);
  assert.equal(buildMissionPresentation({...input,velocityMps:[0,0,0]}).velocityArrow,null);
});

test('radial velocity and polar position retain a finite camera basis',()=>{
  for(const [positionM,velocityMps] of [[[0,0,1738090],null],[[0,1738090,0],[0,10,0]],[[1738090,0,0],[10,0,0]]]){
    const scene=buildMissionPresentation({...input,positionM,velocityMps});
    for(const basis of[scene.radial,scene.tangent,scene.normal]){assert.ok(validVector(basis));close(Math.hypot(...basis),1);}
  }
});


test('enlarged vehicle model stays above the Moon throughout all retained physical cases',()=>{
  const data=JSON.parse(readFileSync(new URL('../dist/data/propulsion.json',import.meta.url),'utf8'));
  const positions=buildSpacecraftMesh().positions;
  let modelRadius=0;
  for(let i=0;i<positions.length;i+=3)modelRadius=Math.max(modelRadius,Math.hypot(positions[i],positions[i+1],positions[i+2]));
  let examined=0;
  for(const item of data.cases){
    const seen=new Set();
    for(const frame of item.frames){
      const craft=frame.spacecraft;
      if(!craft||seen.has(craft.source.cycle))continue;
      seen.add(craft.source.cycle);
      const scene=buildMissionPresentation({...craft,available:true,lunarRadiusM:item.initialGeometry.lunarRadiusM},'vehicle');
      const altitude=Math.hypot(...craft.positionM)-item.initialGeometry.lunarRadiusM;
      const visualRadius=modelRadius*scene.metadata.spacecraftMetresPerModelUnit;
      assert.ok(altitude>visualRadius,`${item.id} cycle ${craft.source.cycle}: illustrative mesh would enter the Moon`);
      examined++;
    }
  }
  assert.ok(examined>1000,'Test must cover retained physical samples from all causal cases');
});


test('docked Columbia diagram has distinct capsule, service equipment, roof collar and dark open engine',()=>{
  const asset=buildDockedCsmMesh();
  for(const name of ['roof-docking-collar','command-module','command-windows-and-hatch','service-module','radiator-panels','service-rcs-pods','inert-service-engine'])assert.ok(asset.components[name].vertexCount>0,`${name} must be distinguishable`);
  assert.equal(asset.positions.length,asset.normals.length);assert.equal(asset.positions.length,asset.colors.length);
  assert.ok([...asset.positions,...asset.normals,...asset.colors].every(Number.isFinite));
  const collar=asset.components['roof-docking-collar'];
  const firstX=asset.positions[collar.firstVertex*3];
  close(firstX,1.58,1e-6); // LM roof, rather than the old antenna tip.
  const cm=asset.components['command-module'],bell=asset.components['inert-service-engine'];
  assert.ok(bell.firstVertex>cm.firstVertex,'Engine is opposite the nose-to-roof docking connection');
  const bellColors=asset.colors.slice(bell.firstVertex*3,(bell.firstVertex+bell.vertexCount)*3);
  assert.ok(Math.min(...bellColors)<.04,'Engine interior must be dark and distinct from silver CM/SM');
  assert.match(asset.reference.scope,/not a measured physical/);
});

test('interactive procedure illustration exposes no orbital or separation telemetry',()=>{
  const scene=buildMissionPresentation({...input,mode:'procedure-illustration',dockingState:'released'});
  assert.equal(scene.mode,'procedure-illustration');assert.equal(scene.dockingState,'released');
  assert.equal(scene.positionM,null);assert.equal(scene.velocityMps,null);assert.equal(scene.quaternion,null);
  assert.equal(scene.velocityArrow,null);assert.deepEqual(scene.path,[]);assert.deepEqual(scene.trajectoryM,[]);
  assert.equal(scene.metadata.spacecraftMetresPerModelUnit,null);
  assert.match(scene.metadata.frame,/no observed coordinate frame/);
  assert.match(scene.metadata.scale,/no physical separation scale/);
  assert.match(scene.metadata.docking,/Connection released/);
  assert.match(scene.metadata.docking,/diagram spacing/);
  assert.match(scene.metadata.illustration,/no historical position, velocity, attitude or separation motion/);
});

test('release changes only the CSM exploded-diagram placement and requires the explicit procedure state',()=>{
  const request={mode:'procedure-illustration',dockingState:'docked'};
  const before=JSON.stringify(request),secured=buildMissionPresentation(request);
  assert.equal(JSON.stringify(request),before,'Presentation must not change the procedure state');
  const released=buildMissionPresentation({...request,dockingState:'released'});
  assert.deepEqual(released.craftModel,secured.craftModel,'The LM diagram stays fixed');
  assert.notDeepEqual(released.csmModel,secured.csmModel,'The released connection is visible in the assembly diagram');
  const csmPoint=transformPoint(released.csmModel,[1.58,0,0]);
  const lmPoint=transformPoint(released.craftModel,[1.58,0,0]);
  assert.ok(csmPoint[0]>lmPoint[0]);close(csmPoint[1],lmPoint[1]);close(csmPoint[2],lmPoint[2]);
  for(const dockingState of[undefined,'approaching','separated',true])assert.equal(buildMissionPresentation({...request,dockingState}).dockingState,'docked','Unknown states must not show a released connection');
  const physical=buildMissionPresentation({...input,dockingState:'released'});
  assert.equal(physical.csmModel,null);assert.equal(physical.dockingState,null,'Procedure controls must not alter retained physics');
});

test('procedure assembly spacing is a static two-state view with no clock-based motion',()=>{
  const state={mode:'procedure-illustration',dockingState:'released'},first=buildMissionPresentation(state);
  for(const t of[0,.5,10000]){
    const next=buildMissionPresentation({...input,...state,t,elapsedSeconds:t,separationVelocityMps:100});
    assert.deepEqual(next.craftModel,first.craftModel);assert.deepEqual(next.csmModel,first.csmModel);
    assert.deepEqual(next.csmDiagramOffset,first.csmDiagramOffset);assert.deepEqual(next.path,[]);
  }
});

test('Canvas fallback presents both procedure connection states without requiring a physical quaternion',()=>{
  let faces=0;const coordinates=[],listeners=new Map();
  const context={setTransform(){},fillRect(){},createRadialGradient(){return{addColorStop(){}};},beginPath(){},arc(x,y,r){coordinates.push(x,y,r);},closePath(){},fill(){faces++;},stroke(){},moveTo(x,y){coordinates.push(x,y);},lineTo(x,y){coordinates.push(x,y);}};
  const canvas={clientWidth:800,clientHeight:600,width:0,height:0,getContext(kind){return kind==='2d'?context:null;},addEventListener(name,listener){listeners.set(name,listener);},removeEventListener(name){listeners.delete(name);}};
  const renderer=createMissionRenderer(canvas);
  assert.equal(renderer.kind,'Canvas 3D projection');
  for(const dockingState of['docked','released']){
    const count=faces;renderer.draw({mode:'procedure-illustration',dockingState});
    assert.ok(faces-count>500,'Both the LM and CSM must have projected geometry');
    assert.match(renderer.status.presentation.docking,dockingState==='released'?/Connection released/:/secured/);
  }
  assert.ok(coordinates.every(Number.isFinite),'The procedure diagram needs finite fallback projections');
  renderer.dispose();assert.equal(listeners.size,0);
});

test('default docked framing fits the complete Eagle and Columbia assembly with viewport margins',()=>{
  for(const [width,height] of [[845,600],[450,600],[350,440],[1600,800]]){
    for(const mode of['historical-illustration','procedure-illustration']){
      let points=[];const vertices=[];
      const context={setTransform(){},fillRect(){},createRadialGradient(){return{addColorStop(){}};},beginPath(){points=[];},arc(){},closePath(){},fill(){if(points.length===3)vertices.push(...points);},stroke(){},moveTo(x,y){points.push([x,y]);},lineTo(x,y){points.push([x,y]);}};
      const canvas={clientWidth:width,clientHeight:height,width:0,height:0,getContext(kind){return kind==='2d'?context:null;},addEventListener(){},removeEventListener(){}};
      const renderer=createMissionRenderer(canvas);renderer.draw({mode,dockingState:'docked'});
      assert.ok(vertices.length>1000,'The fit check must cover the complete projected spacecraft meshes');
      for(const [x,y] of vertices){
        assert.ok(x>=width*.12&&x<=width*.88,`${mode} ${width}x${height}: spacecraft exceeds horizontal margin (${x})`);
        assert.ok(y>=height*.12&&y<=height*.88,`${mode} ${width}x${height}: spacecraft exceeds vertical margin (${y})`);
      }
      renderer.dispose();
    }
  }
});
