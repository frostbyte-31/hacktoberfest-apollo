/**
 * Replaceable 3D presentation of retained, authoritative mission samples.
 * No state integration, interpolation, trajectory generation or actuator logic.
 * REF coordinates and scalar-first body-to-REF orientation remain unchanged.
 */
import { buildSpacecraftMesh } from './spacecraft-mesh.mjs';
import { validQuaternion, quaternionMatrix, multiplyMatrices, transformPoint, perspectiveMatrix, lookAtMatrix } from './spacecraft-3d.mjs';

const IDENTITY = [1,0,0,0];
const REFERENCE_RADIUS_M = 1738090;
const mesh = buildSpacecraftMesh();
const dot = (a,b) => a.reduce((sum,v,i)=>sum+v*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const add = (a,b) => a.map((v,i)=>v+b[i]);
const mul = (a,k) => a.map(v=>v*k);
const unit = a => mul(a,1/Math.hypot(...a));
export const validVector = value => Array.isArray(value)&&value.length===3&&value.every(Number.isFinite);
const translated = (position,scale=1) => [scale,0,0,0,0,scale,0,0,0,0,scale,0,...position,1];

/** Pure scene conversion. Physical samples are copied; only rendering units change. */
export function buildMissionPresentation(state={},view='vehicle') {
  const illustration=state.mode==='historical-illustration';
  const usable=state.available===true&&validVector(state.positionM)&&Math.hypot(...state.positionM)>0&&validQuaternion(state.quaternion);
  const mode=illustration?'historical-illustration':usable?'verified-telemetry':'unavailable';
  const radiusM=Number.isFinite(state.lunarRadiusM)&&state.lunarRadiusM>0?state.lunarRadiusM:REFERENCE_RADIUS_M;
  const positionM=illustration?[radiusM*1.12,0,0]:usable?state.positionM.slice():null;
  const quaternion=illustration?IDENTITY.slice():usable?state.quaternion.slice():null;
  const velocityMps=usable&&!illustration&&validVector(state.velocityMps)?state.velocityMps.slice():null;
  const trajectoryM=usable&&!illustration&&Array.isArray(state.trajectoryM)?state.trajectoryM.filter(validVector).map(point=>point.slice()):[];
  const radial=positionM?unit(positionM):[1,0,0];
  const along=velocityMps||[0,0,1];
  const tangentCandidate=add(along,mul(radial,-dot(along,radial)));
  const tangent=Math.hypot(...tangentCandidate)>1e-8?unit(tangentCandidate):unit(cross(Math.abs(radial[1])<.8?[0,1,0]:[0,0,1],radial));
  const normal=unit(cross(radial,tangent));
  const orbit=view==='orbit'||!positionM;
  // Global view is uniform in distance. Vehicle view uses metres/5000 and an
  // enlarged display model so the LM remains readable above a real-radius sphere.
  const metresPerUnit=orbit?radiusM:5000;
  const origin=orbit||!positionM?[0,0,0]:positionM;
  const displayPoint=point=>point.map((value,i)=>(value-origin[i])/metresPerUnit);
  const spacecraftPosition=positionM?displayPoint(positionM):null;
  // Keep the enlarged diagnostic model clear of the real-radius Moon. The
  // separate historical docked composition retains its own illustration scale.
  const modelScale=orbit?.035:illustration?1:.45;
  const craftModel=quaternion?multiplyMatrices(translated(spacecraftPosition,modelScale),quaternionMatrix(quaternion)):null;
  const velocityDirection=velocityMps&&Math.hypot(...velocityMps)>0?unit(velocityMps):null;
  const velocityArrow=spacecraftPosition&&velocityDirection?[spacecraftPosition,add(spacecraftPosition,mul(velocityDirection,orbit?.22:3.25))]:null;
  return {mode,view:orbit?'orbit':'vehicle',positionM,velocityMps,quaternion,trajectoryM,
    radiusM,metresPerUnit,origin:origin.slice(),radial,tangent,normal,
    spacecraftPosition,craftModel,moonCenter:displayPoint([0,0,0]),moonRadius:radiusM/metresPerUnit,
    path:trajectoryM.map(displayPoint),velocityArrow,
    metadata:{
      mode,frame:'Moon-centered basic REF; supplied body-to-REF quaternion',
      geometry:illustration?'Spherical Moon reference; schematic docked LM and CSM; geometry and position are illustrative':'Spherical Moon reference; illustrative Lunar Module mesh',
      scale:`1 scene unit = ${metresPerUnit} m; Lunar Module enlarged for visibility`,
      spacecraftMetresPerModelUnit:modelScale*metresPerUnit,
      trajectory:'Retained sample positions only; no interpolation or propagation',
      velocity:'Arrow shows direction only; its display length does not encode speed',
      interaction:'Camera orbit and zoom only; these do not control the spacecraft',
      illustration:illustration?'Static orbital composition; no historical position, velocity or attitude is asserted':null,
    }};
}

const VERTEX=`
attribute vec3 aPosition;attribute vec3 aNormal;attribute vec3 aColor;
uniform mat4 uModel;uniform mat4 uViewProjection;
varying vec3 vNormal;varying vec3 vColor;varying vec3 vLocal;
void main(){vNormal=mat3(uModel)*aNormal;vColor=aColor;vLocal=aPosition;gl_Position=uViewProjection*uModel*vec4(aPosition,1.0);}
`;
const FRAGMENT=`
precision mediump float;
varying vec3 vNormal;varying vec3 vColor;varying vec3 vLocal;
uniform float uUnlit;uniform float uMoon;uniform float uOpacity;
void main(){
 vec3 n=normalize(vNormal);if(!gl_FrontFacing)n=-n;
 float light=max(dot(n,normalize(vec3(0.45,-0.65,0.60))),0.0);
 float fill=max(dot(n,normalize(vec3(0.55,-0.12,-0.8))),0.0);
 vec3 surface=vColor;
 // Abstract albedo variation only. The reference sphere has no terrain relief.
 float marks=sin(vLocal.x*41.0+sin(vLocal.y*17.0))*sin(vLocal.z*37.0-vLocal.y*11.0);
 surface*=mix(1.0,0.90+marks*0.065,uMoon);
 vec3 lit=surface*(0.34+light*0.80+fill*0.18);
 gl_FragColor=vec4(mix(lit,surface,uUnlit),uOpacity);
}
`;
function compileProgram(gl) {
  const shaders=[gl.VERTEX_SHADER,gl.FRAGMENT_SHADER].map((type,i)=>{
    const shader=gl.createShader(type);gl.shaderSource(shader,i?FRAGMENT:VERTEX);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw new Error(message||'Mission graphics shader failed.');}return shader;
  });
  const program=gl.createProgram();shaders.forEach(shader=>gl.attachShader(program,shader));gl.linkProgram(program);shaders.forEach(shader=>gl.deleteShader(shader));
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)){const message=gl.getProgramInfoLog(program);gl.deleteProgram(program);throw new Error(message||'Mission graphics program failed.');}return program;
}
function sphereGeometry(rows=80,columns=128) {
  const positions=[],normals=[],colors=[];
  const point=(row,column)=>{const latitude=Math.PI*(row/rows-.5),longitude=2*Math.PI*column/columns;return[Math.cos(latitude)*Math.cos(longitude),Math.sin(latitude),Math.cos(latitude)*Math.sin(longitude)];};
  for(let row=0;row<rows;row++)for(let column=0;column<columns;column++){
    const a=point(row,column),b=point(row+1,column),c=point(row+1,column+1),d=point(row,column+1);
    for(const vertex of[a,b,c,a,c,d]){positions.push(...vertex);normals.push(...vertex);colors.push(.43,.45,.44);}
  }
  return{positions:new Float32Array(positions),normals:new Float32Array(normals),colors:new Float32Array(colors)};
}
/**
 * Docked Columbia diagram only; never retained CSM state or vehicle dynamics.
 * Approximate silhouette follows Apollo 11 press-kit pages 86/88 (PDF 89/91):
 * https://solarsystem.nasa.gov/system/downloadable_items/2920_Apollo_11.pdf
 * CM 11 ft 5 in high / 12 ft 10 in diameter; SM 24 ft 7 in overall.
 * Two metres per model unit guides relative proportions, not a CAD-scale claim.
 */
export function buildDockedCsmMesh() {
  const positions=[],normals=[],colors=[],components={};let part='';
  const begin=name=>{part=name;components[name]={firstVertex:positions.length/3,vertexCount:0};};
  const triangle=(a,b,c,color)=>{const delta=cross(add(b,mul(a,-1)),add(c,mul(a,-1)));if(Math.hypot(...delta)<1e-10)return;const normal=unit(delta);for(const vertex of[a,b,c]){positions.push(...vertex);normals.push(...normal);colors.push(...color);}components[part].vertexCount+=3;};
  const quad=(a,b,c,d,color)=>{triangle(a,b,c,color);triangle(a,c,d,color);};
  const polar=(x,r,angle)=>[x,Math.cos(angle)*r,Math.sin(angle)*r];
  const section=(x0,r0,x1,r1,color)=>{for(let i=0;i<48;i++){const a=i*Math.PI/24,b=(i+1)*Math.PI/24;quad(polar(x0,r0,a),polar(x1,r1,a),polar(x1,r1,b),polar(x0,r0,b),color);}};
  const annulus=(x,inside,outside,color)=>{for(let i=0;i<48;i++){const a=i*Math.PI/24,b=(i+1)*Math.PI/24;quad(polar(x,inside,a),polar(x,outside,a),polar(x,outside,b),polar(x,inside,b),color);}};
  const patch=(x0,x1,radiusAt,angle,halfWidth,color)=>quad(polar(x0,radiusAt(x0),angle-halfWidth),polar(x1,radiusAt(x1),angle-halfWidth),polar(x1,radiusAt(x1),angle+halfWidth),polar(x0,radiusAt(x0),angle+halfWidth),color);
  const box=(center,size,color)=>{
    const p=(x,y,z)=>add(center,[x*size[0]/2,y*size[1]/2,z*size[2]/2]);
    quad(p(-1,-1,-1),p(-1,-1,1),p(-1,1,1),p(-1,1,-1),color);quad(p(1,-1,-1),p(1,1,-1),p(1,1,1),p(1,-1,1),color);
    quad(p(-1,-1,-1),p(1,-1,-1),p(1,-1,1),p(-1,-1,1),color);quad(p(-1,1,-1),p(-1,1,1),p(1,1,1),p(1,1,-1),color);
    quad(p(-1,-1,-1),p(-1,1,-1),p(1,1,-1),p(1,-1,-1),color);quad(p(-1,-1,1),p(1,-1,1),p(1,1,1),p(-1,1,1),color);
  };
  begin('roof-docking-collar');
  section(1.58,.34,1.77,.34,[.60,.64,.61]);annulus(1.59,.23,.36,[.74,.76,.69]);section(1.77,.24,1.94,.24,[.43,.48,.47]);
  begin('command-module');
  const cmRadius=x=>.24+(x-1.94)/1.74*(.978-.24);
  section(1.94,.24,3.68,.978,[.78,.80,.77]);section(3.68,.978,3.76,.978,[.25,.29,.30]);
  begin('command-windows-and-hatch');
  for(const angle of[Math.PI-.34,Math.PI+.34]){patch(2.89,3.18,x=>cmRadius(x)+.009,angle,.105,[.05,.12,.15]);patch(2.88,2.92,x=>cmRadius(x)+.012,angle,.12,[.52,.61,.61]);}
  patch(2.51,3.29,x=>cmRadius(x)+.006,Math.PI,.17,[.36,.41,.41]);patch(2.72,2.96,x=>cmRadius(x)+.014,Math.PI,.095,[.03,.08,.11]);
  begin('service-module');
  section(3.76,.978,6.45,.978,[.64,.68,.67]);section(3.76,.982,3.86,.982,[.37,.42,.41]);section(6.34,.985,6.48,.985,[.35,.40,.40]);
  begin('radiator-panels');
  for(const angle of[0,Math.PI/2,Math.PI,3*Math.PI/2]){
    patch(4.04,6.14,()=>.984,angle,.30,[.84,.86,.81]);
    for(let i=0;i<6;i++)patch(4.09+i*.34,4.12+i*.34,()=>.987,angle,.285,[.57,.62,.60]);
    patch(4.04,6.14,()=>.988,angle-.29,.008,[.34,.40,.39]);patch(4.04,6.14,()=>.988,angle+.29,.008,[.34,.40,.39]);
  }
  begin('service-rcs-pods');
  for(const sy of[-1,1])for(const sz of[-1,1]){
    box([6.04,sy*.75,sz*.75],[.25,.20,.20],[.43,.49,.48]);
    box([6.04,sy*.91,sz*.75],[.15,.13,.13],[.10,.15,.16]);box([6.04,sy*.75,sz*.91],[.15,.13,.13],[.10,.15,.16]);
  }
  begin('inert-service-engine');
  annulus(6.48,.20,.96,[.26,.31,.31]);section(6.48,.23,6.65,.29,[.17,.22,.23]);section(6.65,.29,7.40,.66,[.13,.16,.17]);
  // The dark open bell is visually distinct from the silver service cylinder.
  section(7.40,.66,7.44,.66,[.40,.43,.41]);section(6.82,.20,7.435,.60,[.025,.035,.04]);annulus(6.83,0,.20,[.015,.022,.027]);
  return{positions:new Float32Array(positions),normals:new Float32Array(normals),colors:new Float32Array(colors),components,
    reference:{metresPerModelUnit:2,commandModuleHeightM:3.48,maxDiameterM:3.912,serviceModuleOverallM:7.49,scope:'Approximate illustrative proportions; not a measured physical spacecraft model'}};
}
const csm=buildDockedCsmMesh();
// In the separate docked illustration the center roof tunnel replaces the
// illustrative center antenna. Other antennas and the ladder remain visible.
const dockedLm=(()=>{
  const positions=[],normals=[],colors=[],antenna=mesh.components['antennae-and-ladder'];
  for(let i=0;i<mesh.positions.length;i+=9){
    const central=i/3>=antenna.firstVertex&&[0,3,6].every(j=>mesh.positions[i+j]>1.50&&Math.abs(mesh.positions[i+j+1])<.36&&Math.abs(mesh.positions[i+j+2])<.2);
    if(central)continue;positions.push(...mesh.positions.slice(i,i+9));normals.push(...mesh.normals.slice(i,i+9));colors.push(...mesh.colors.slice(i,i+9));
  }
  return{positions:new Float32Array(positions),normals:new Float32Array(normals),colors:new Float32Array(colors)};
})();
function createWebGLBackend(gl) {
  const program=compileProgram(gl),buffers=[];
  const location={};
  for(const name of ['aPosition','aNormal','aColor'])location[name]=gl.getAttribLocation(program,name);
  for(const name of ['uModel','uViewProjection','uUnlit','uMoon','uOpacity'])location[name]=gl.getUniformLocation(program,name);
  const buffer=data=>{const item=gl.createBuffer();buffers.push(item);gl.bindBuffer(gl.ARRAY_BUFFER,item);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);return item;};
  const geometry=(positions,normals,colors)=>({positions:buffer(positions),normals:buffer(normals||new Float32Array(positions.length).fill(.577)),colors:buffer(colors||new Float32Array(positions.length).fill(1)),count:positions.length/3});
  const solid=geometry(mesh.positions,mesh.normals,mesh.colors),edges=geometry(mesh.lines,null,mesh.lineColors),dockedCsm=geometry(csm.positions,csm.normals,csm.colors),dockedLunar=geometry(dockedLm.positions,dockedLm.normals,dockedLm.colors),sphere=sphereGeometry(),moon=geometry(sphere.positions,sphere.normals,sphere.colors);
  const moving=geometry(new Float32Array(0));
  const updateLines=(points,color)=>{
    const positions=new Float32Array(points.flat()),colors=new Float32Array(points.flatMap(()=>color));
    gl.bindBuffer(gl.ARRAY_BUFFER,moving.positions);gl.bufferData(gl.ARRAY_BUFFER,positions,gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER,moving.normals);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(positions.length).fill(.577),gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER,moving.colors);gl.bufferData(gl.ARRAY_BUFFER,colors,gl.DYNAMIC_DRAW);moving.count=points.length;
  };
  const attribute=(name,value)=>{gl.bindBuffer(gl.ARRAY_BUFFER,value);gl.enableVertexAttribArray(location[name]);gl.vertexAttribPointer(location[name],3,gl.FLOAT,false,0,0);};
  const drawGeometry=(object,mode,model,unlit=0,isMoon=0,opacity=1)=>{
    attribute('aPosition',object.positions);attribute('aNormal',object.normals);attribute('aColor',object.colors);
    gl.uniformMatrix4fv(location.uModel,false,model);gl.uniform1f(location.uUnlit,unlit);gl.uniform1f(location.uMoon,isMoon);gl.uniform1f(location.uOpacity,opacity);gl.drawArrays(mode,0,object.count);
  };
  const identity=translated([0,0,0]);
  return{kind:'WebGL 3D',draw({scene,viewProjection,width,height,dpr}){
    gl.viewport(0,0,Math.round(width*dpr),Math.round(height*dpr));gl.clearColor(.019,.029,.038,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.useProgram(program);gl.uniformMatrix4fv(location.uViewProjection,false,viewProjection);
    drawGeometry(moon,gl.TRIANGLES,translated(scene.moonCenter,scene.moonRadius),0,1);
    if(scene.path.length>1){updateLines(scene.path,[.32,.65,.63]);drawGeometry(moving,gl.LINE_STRIP,identity,1,0,.8);}
    if(scene.craftModel){gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);drawGeometry(scene.mode==='historical-illustration'?dockedLunar:solid,gl.TRIANGLES,scene.craftModel);if(scene.mode==='historical-illustration')drawGeometry(dockedCsm,gl.TRIANGLES,scene.craftModel);gl.disable(gl.POLYGON_OFFSET_FILL);drawGeometry(edges,gl.LINES,scene.craftModel,1,0,.5);}
    if(scene.velocityArrow){
      const[a,b]=scene.velocityArrow,dir=unit(add(b,mul(a,-1))),side=unit(cross(dir,Math.abs(dir[1])<.8?[0,1,0]:[0,0,1])),length=scene.view==='orbit'?.035:.35;
      const wings=[add(b,add(mul(dir,-length),mul(side,length*.45))),add(b,add(mul(dir,-length),mul(side,-length*.45)))];
      updateLines([a,b,b,wings[0],b,wings[1]],[.70,.80,.64]);drawGeometry(moving,gl.LINES,identity,1);
    }
  },dispose(){buffers.forEach(item=>gl.deleteBuffer(item));gl.deleteProgram(program);}};
}

function createCanvasBackend(ctx) {
  const polygons=[];
  for(const [asset,dockedOnly,standaloneOnly] of [[mesh,false,true],[dockedLm,true,false],[csm,true,false]])for(let i=0;i<asset.positions.length;i+=9)polygons.push({vertices:[asset.positions.slice(i,i+3),asset.positions.slice(i+3,i+6),asset.positions.slice(i+6,i+9)],index:i,asset,dockedOnly,standaloneOnly});
  return{kind:'Canvas 3D projection',draw({scene,viewProjection,width,height,dpr,eye}){
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#05080b';ctx.fillRect(0,0,width,height);
    const project=(point,matrix=viewProjection)=>{const p=transformPoint(matrix,point);return p[3]>.001?[width*(p[0]/p[3]+1)/2,height*(1-p[1]/p[3])/2,p[2]/p[3]]:null;};
    const center=project(scene.moonCenter);
    if(center){
      const toMoon=add(scene.moonCenter,mul(eye,-1)),distance=Math.hypot(...toMoon),right=unit(cross(unit(toMoon),scene.radial));
      const edge=project(add(scene.moonCenter,mul(right,scene.moonRadius)));
      let radius=edge?Math.hypot(edge[0]-center[0],edge[1]-center[1]):Math.max(width,height)*3;
      if(distance<scene.moonRadius)radius=Math.max(width,height)*3;
      const gradient=ctx.createRadialGradient(center[0]-radius*.32,center[1]-radius*.32,0,center[0],center[1],radius);gradient.addColorStop(0,'#858b86');gradient.addColorStop(.65,'#454d4b');gradient.addColorStop(1,'#141d21');ctx.fillStyle=gradient;ctx.beginPath();ctx.arc(center[0],center[1],radius,0,Math.PI*2);ctx.fill();
    }
    ctx.strokeStyle='#609d97';ctx.lineWidth=1.2;ctx.beginPath();let started=false;
    for(const point of scene.path){const p=project(point);if(!p){started=false;continue;}if(started)ctx.lineTo(p[0],p[1]);else ctx.moveTo(p[0],p[1]);started=true;}ctx.stroke();
    if(scene.craftModel){
      const matrix=multiplyMatrices(viewProjection,scene.craftModel);
      const faces=polygons.filter(polygon=>(!polygon.dockedOnly||scene.mode==='historical-illustration')&&(!polygon.standaloneOnly||scene.mode!=='historical-illustration')).map(polygon=>({...polygon,points:polygon.vertices.map(vertex=>project(vertex,matrix))})).filter(polygon=>polygon.points.every(Boolean)).sort((a,b)=>b.points.reduce((sum,p)=>sum+p[2],0)-a.points.reduce((sum,p)=>sum+p[2],0));
      for(const face of faces){
        const normal=transformPoint(quaternionMatrix(scene.quaternion),Array.from(face.asset.normals.slice(face.index,face.index+3))).slice(0,3),light=.35+Math.max(0,dot(normal,unit([.45,-.65,.60])))*.8;
        ctx.fillStyle=`rgb(${Array.from(face.asset.colors.slice(face.index,face.index+3)).map(value=>Math.round(Math.min(1,value*light)*255)).join(',')})`;ctx.beginPath();face.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fill();
      }
    }
    if(scene.velocityArrow){const points=scene.velocityArrow.map(point=>project(point));if(points.every(Boolean)){ctx.strokeStyle='#b6cca2';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(points[0][0],points[0][1]);ctx.lineTo(points[1][0],points[1][1]);ctx.stroke();}}
  },dispose(){}};
}

/** Camera movement changes presentation only. The host supplies every sample. */
export function createMissionRenderer(canvas) {
  let azimuth=.45,elevation=.24,distance=8.1,view='vehicle',width=1,height=1,dpr=1,disposed=false,contextLost=false,problem=null,last={available:false},scene=buildMissionPresentation(last,view),fallback=null,backend=null,gl=null,overviewBasis=null,previousMode=null;
  try{gl=canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});if(gl)backend=createWebGLBackend(gl);}catch(error){problem=error.message;}
  if(!backend){
    let target=canvas;
    if(gl&&canvas.ownerDocument){fallback=canvas.ownerDocument.createElement('canvas');fallback.className=canvas.className;fallback.setAttribute('aria-label','Mission geometry projected 3D fallback');Object.assign(fallback.style,{width:'100%',height:'100%',display:'block'});canvas.hidden=true;canvas.insertAdjacentElement('afterend',fallback);target=fallback;}
    const context=target.getContext('2d');if(!context)throw new Error(problem||'No graphics context is available.');backend=createCanvasBackend(context);problem=problem||'WebGL unavailable; using a projected 3D presentation.';
  }
  const surface=()=>fallback||canvas;
  function resize(){if(disposed)return;const target=surface();width=Math.max(1,target.clientWidth||canvas.clientWidth||640);height=Math.max(1,target.clientHeight||canvas.clientHeight||480);dpr=Math.min(globalThis.devicePixelRatio||1,2);const w=Math.round(width*dpr),h=Math.round(height*dpr);if(target.width!==w)target.width=w;if(target.height!==h)target.height=h;}
  function draw(state=last){
    if(disposed)return;last=state;scene=buildMissionPresentation(state,view);resize();if(contextLost)return;
    const orbit=scene.view==='orbit',cameraDistance=orbit?distance*.46:distance*(scene.mode==='historical-illustration'?2.0:1);
    if(previousMode!==scene.mode){overviewBasis=null;previousMode=scene.mode;}
    // Freeze overview camera axes at the first sample. Advancing telemetry must
    // move the vehicle in REF, rather than quietly orbit the camera with it.
    if(orbit&&!overviewBasis)overviewBasis={radial:scene.radial.slice(),tangent:scene.tangent.slice(),normal:scene.normal.slice()};
    const basis=orbit?overviewBasis:scene;
    const focus=orbit?[0,0,0]:scene.mode==='historical-illustration'?add(scene.spacecraftPosition,mul(scene.radial,2.5)):scene.spacecraftPosition||[0,0,0];
    const angle=orbit?Math.max(-1.35,Math.min(1.35,.55+elevation*.5)):elevation;
    const offset=add(add(mul(basis.tangent,Math.sin(azimuth)*Math.cos(angle)*cameraDistance),mul(basis.normal,Math.cos(azimuth)*Math.cos(angle)*cameraDistance)),mul(basis.radial,Math.sin(angle)*cameraDistance));
    const eye=add(focus,offset),far=orbit?20:scene.moonRadius*4+cameraDistance;
    const viewProjection=multiplyMatrices(perspectiveMatrix(Math.PI/4,width/height,orbit?.002:.08,far),lookAtMatrix(eye,focus,basis.radial));
    backend.draw({scene,viewProjection,width,height,dpr,eye});
  }
  const lost=event=>{event.preventDefault();contextLost=true;problem='Mission graphics context lost. Restore the tab or reload.';canvas.dispatchEvent(new CustomEvent('mission-renderer-status',{detail:{available:false,message:problem}}));};
  const restored=()=>{try{backend.dispose();backend=createWebGLBackend(gl);contextLost=false;problem=null;draw();canvas.dispatchEvent(new CustomEvent('mission-renderer-status',{detail:{available:true,message:'Mission graphics restored.'}}));}catch(error){problem=error.message;}};
  canvas.addEventListener('webglcontextlost',lost,false);canvas.addEventListener('webglcontextrestored',restored,false);resize();
  return{draw,resize,
    orbit(dx,dy){if(disposed||![dx,dy].every(Number.isFinite))return;azimuth-=dx*.006;elevation=Math.max(-1.35,Math.min(1.35,elevation+dy*.004));},
    zoom(delta){if(disposed||!Number.isFinite(delta))return;distance=Math.max(4.7,Math.min(15,distance*Math.exp(delta*.001)));},
    reset(){azimuth=.45;elevation=.24;distance=8.1;overviewBasis=null;},
    setView(next){if(next!=='vehicle'&&next!=='orbit')throw new TypeError('Mission view must be vehicle or orbit.');view=next;},
    get kind(){return backend.kind;},get surface(){return surface();},get status(){return{available:!disposed&&!contextLost,message:problem,presentation:scene.metadata};},
    dispose(){if(disposed)return;disposed=true;backend.dispose();canvas.removeEventListener('webglcontextlost',lost);canvas.removeEventListener('webglcontextrestored',restored);if(fallback){fallback.remove();canvas.hidden=false;}},
  };
}
