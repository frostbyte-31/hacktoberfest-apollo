/** Server state → replaceable 3D presentation. No flight integration or interpolation. */
import { buildSpacecraftMesh } from './spacecraft-mesh.mjs';
import { validQuaternion, quaternionMatrix, multiplyMatrices, transformPoint, perspectiveMatrix, lookAtMatrix } from './spacecraft-3d.mjs';

const mesh = buildSpacecraftMesh();
const vector = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
const add = (a,b) => a.map((value,i)=>value+b[i]);
const mul = (a,k) => a.map(value=>value*k);
const dot = (a,b) => a.reduce((sum,value,i)=>sum+value*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit = a => mul(a,1/Math.hypot(...a));
const matrix = (position,scale=1) => [scale,0,0,0,0,scale,0,0,0,0,scale,0,...position,1];
// Proper rotation: REF +X (up) → display +Y, +Z (downrange) → +X.
const DISPLAY_BASIS = [0,1,0,0,0,0,1,0,1,0,0,0,0,0,0,1];
const meshMinimum=[Infinity,Infinity,Infinity],meshMaximum=[-Infinity,-Infinity,-Infinity];
for(let i=0;i<mesh.positions.length;i+=3)for(let axis=0;axis<3;axis++){
  meshMinimum[axis]=Math.min(meshMinimum[axis],mesh.positions[i+axis]);
  meshMaximum[axis]=Math.max(meshMaximum[axis],mesh.positions[i+axis]);
}
const lowestMeshX=meshMinimum[0];
const meshCorners=[];
for(const x of[meshMinimum[0],meshMaximum[0]])for(const y of[meshMinimum[1],meshMaximum[1]])for(const z of[meshMinimum[2],meshMaximum[2]])meshCorners.push([x,y,z]);

/**
 * Presentation units and camera framing only. The unmodified r/v/q are retained
 * separately from the enlarged visual model. Its lowest local +X extent is
 * registered to the measured reference point; mesh dimensions are not collision
 * geometry, and the flat plane is the landing site's tangent reference.
 */
export function flight3DViewModel(spacecraft,engine,bounds={}) {
  if(!spacecraft || !vector(spacecraft.positionM) || !vector(spacecraft.velocityMps)
    || !validQuaternion(spacecraft.quaternionBodyToRef) || !Number.isFinite(spacecraft.altitudeM)
    || !Number.isFinite(engine?.thrustN) || typeof engine.enabled!=='boolean') {
    throw new TypeError('3D flight view requires actual server position, velocity, unit quaternion and engine telemetry.');
  }
  const radiusM=Math.hypot(...spacecraft.positionM)-spacecraft.altitudeM;
  if(!(radiusM>1000)) throw new TypeError('A valid lunar reference radius is required.');
  const heightM=Number.isFinite(bounds.heightM)&&bounds.heightM>0?bounds.heightM:Math.max(100,Math.abs(spacecraft.altitudeM)*1.18);
  const metresPerUnit=Math.max(10,heightM/8),originM=[radiusM,0,0];
  const convert = point => [point[2]/metresPerUnit,(point[0]-radiusM)/metresPerUnit,point[1]/metresPerUnit];
  const position=convert(spacecraft.positionM),modelScale=.55;
  const rotation=multiplyMatrices(DISPLAY_BASIS,quaternionMatrix(spacecraft.quaternionBodyToRef));
  const craftModel=multiplyMatrices(multiplyMatrices(matrix(position),rotation),multiplyMatrices(matrix([0,0,0],modelScale),matrix([-lowestMeshX,0,0])));
  const velocityDirection=[spacecraft.velocityMps[2],spacecraft.velocityMps[0],spacecraft.velocityMps[1]];
  const speed=Math.hypot(...velocityDirection);
  const velocityArrow=speed>0?[position,add(position,mul(velocityDirection,1.8/speed))]:null;
  let velocityLines=[];
  if(velocityArrow){const direction=unit(velocityDirection),side=unit(cross(direction,Math.abs(direction[1])<.8?[0,1,0]:[1,0,0]));const tip=velocityArrow[1];velocityLines=[...velocityArrow,tip,add(tip,add(mul(direction,-.3),mul(side,.13))),tip,add(tip,add(mul(direction,-.3),mul(side,-.13)))];}
  const groundHalfWidth=Math.max(9,Math.abs(position[0])+4),groundHalfDepth=Math.max(6,Math.abs(position[2])+3);
  const ground=[[-groundHalfWidth,0,-groundHalfDepth],[groundHalfWidth,0,-groundHalfDepth],[groundHalfWidth,0,groundHalfDepth],[-groundHalfWidth,0,groundHalfDepth]];
  const lines=[];
  for(let i=-8;i<=8;i++) {
    const x=i*groundHalfWidth/8,z=i*groundHalfDepth/8;
    lines.push([x,.005,-groundHalfDepth],[x,.005,groundHalfDepth],[-groundHalfWidth,.005,z],[groundHalfWidth,.005,z]);
  }
  const target=[[-.85,.08,0],[.85,.08,0],[0,.08,-.85],[0,.08,.85]];
  // Filled bars remain readable in WebGL, where portable line width is 1 px.
  // This is a display marker centered on the reference, never a landing-zone
  // boundary or an illustration of the server's success-distance threshold.
  const targetBars=[
    [[-.85,.08,-.065],[.85,.08,-.065],[.85,.08,.065],[-.85,.08,.065]],
    [[-.065,.08,-.85],[.065,.08,-.85],[.065,.08,.85],[-.065,.08,.85]],
  ];
  // Frame the complete enlarged mesh as well as the measured position and
  // landing reference. Looking only at the foot anchor clips the cabin/antenna
  // at higher altitudes. These are render bounds, never a spacecraft boundary.
  const framePoints=[...meshCorners.map(point=>transformPoint(craftModel,point).slice(0,3)),...target,...velocityLines,position];
  if(engine.enabled&&engine.thrustN>0)framePoints.push(transformPoint(craftModel,[lowestMeshX-1.1,0,0]).slice(0,3));
  const minimum=[0,1,2].map(axis=>Math.min(...framePoints.map(point=>point[axis])));
  const maximum=[0,1,2].map(axis=>Math.max(...framePoints.map(point=>point[axis])));
  const focus=minimum.map((value,axis)=>(value+maximum[axis])/2);
  const frameRadius=Math.max(...framePoints.map(point=>Math.hypot(...point.map((value,axis)=>value-focus[axis]))));
  return {
    mode:'EDUCATIONAL_PHYSICS_LAB',classification:'EDUCATIONAL PHYSICS LAB',
    positionM:spacecraft.positionM.slice(),velocityMps:spacecraft.velocityMps.slice(),quaternionBodyToRef:spacecraft.quaternionBodyToRef.slice(),
    originM,metresPerUnit,spacecraftPosition:position,craftModel,rotation,velocityArrow,velocityLines,ground,gridLines:lines,target,targetBars,focus,
    frameRadius,cameraDistance:Math.max(7.3,frameRadius/Math.sin(Math.PI/8)*1.14),thrusting:engine.enabled&&engine.thrustN>0,
    metadata:{
      frame:'Server Moon-centered inertial REF; local display uses +X up and +Z downrange.',
      scale:`Reference positions: 1 scene unit = ${metresPerUnit} m. Spacecraft enlarged for visibility.`,
      geometry:'Flat landing-site tangent reference; illustrative Lunar Module anchored at the measured reference point. Mesh dimensions and landing gear are not collision geometry.',
      landingReference:'Amber cross marks the synthetic reference point. Marker width is visual emphasis, not a landing-zone or success threshold.',
      velocity:'Arrow shows measured velocity direction; its length does not encode speed.',
      source:'Live server educational physics; synthetic initial conditions and modern controls, not original AGC landing guidance.',
      motion:'Latest supplied sample only; no frontend physics, interpolation or predicted trajectory.',
    },
  };
}

/** Fit the presentation's complete bounds; no camera value changes physical state. */
export function flight3DCamera(scene,width,height,{azimuth=.36,elevation=.29,zoom=1}={}){
  if(![width,height,azimuth,elevation,zoom].every(Number.isFinite)||width<=0||height<=0||zoom<=0)throw new TypeError('Finite positive viewport and camera scale are required.');
  const distance=scene.cameraDistance*zoom*Math.max(1,1/(width/height));
  const eye=add(scene.focus,[Math.sin(azimuth)*Math.cos(elevation)*distance,Math.sin(elevation)*distance,Math.cos(azimuth)*Math.cos(elevation)*distance]);
  return {eye,distance,viewProjection:multiplyMatrices(perspectiveMatrix(Math.PI/4,width/height,.1,Math.max(500,distance*8)),lookAtMatrix(eye,scene.focus,[0,1,0]))};
}

const VERTEX=`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec3 aColor;uniform mat4 uModel;uniform mat4 uViewProjection;varying vec3 vNormal;varying vec3 vColor;void main(){vNormal=mat3(uModel)*aNormal;vColor=aColor;gl_Position=uViewProjection*uModel*vec4(aPosition,1.0);}`;
const FRAGMENT=`precision mediump float;varying vec3 vNormal;varying vec3 vColor;uniform float uUnlit;void main(){vec3 n=normalize(vNormal);if(!gl_FrontFacing)n=-n;float light=.34+max(dot(n,normalize(vec3(-.6,.9,.5))),0.0)*.8;gl_FragColor=vec4(mix(vColor*light,vColor,uUnlit),1.0);}`;

function webglBackend(gl) {
  const shaders=[gl.VERTEX_SHADER,gl.FRAGMENT_SHADER].map((type,index)=>{
    const shader=gl.createShader(type);gl.shaderSource(shader,index?FRAGMENT:VERTEX);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader)||'3D shader unavailable');
    return shader;
  });
  const program=gl.createProgram();shaders.forEach(shader=>gl.attachShader(program,shader));gl.linkProgram(program);shaders.forEach(shader=>gl.deleteShader(shader));
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program)||'3D program unavailable');
  const attributes=Object.fromEntries(['aPosition','aNormal','aColor'].map(name=>[name,gl.getAttribLocation(program,name)]));
  const uniforms=Object.fromEntries(['uModel','uViewProjection','uUnlit'].map(name=>[name,gl.getUniformLocation(program,name)]));
  const buffers=[];
  const buffer=data=>{const result=gl.createBuffer();buffers.push(result);gl.bindBuffer(gl.ARRAY_BUFFER,result);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);return result;};
  const asset={position:buffer(mesh.positions),normal:buffer(mesh.normals),color:buffer(mesh.colors),count:mesh.positions.length/3};
  const dynamic={position:buffer(new Float32Array()),normal:buffer(new Float32Array()),color:buffer(new Float32Array())};
  const draw=(geometry,primitive,model,unlit)=>{
    for(const [name,key] of [['aPosition','position'],['aNormal','normal'],['aColor','color']]){gl.bindBuffer(gl.ARRAY_BUFFER,geometry[key]);gl.enableVertexAttribArray(attributes[name]);gl.vertexAttribPointer(attributes[name],3,gl.FLOAT,false,0,0);}
    gl.uniformMatrix4fv(uniforms.uModel,false,model);gl.uniform1f(uniforms.uUnlit,unlit);gl.drawArrays(primitive,0,geometry.count);
  };
  const upload=(points,color)=>{
    const values={position:points.flat(),normal:points.flatMap(()=>[0,1,0]),color:points.flatMap(()=>color)};
    for(const key of Object.keys(values)){gl.bindBuffer(gl.ARRAY_BUFFER,dynamic[key]);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values[key]),gl.DYNAMIC_DRAW);}
    dynamic.count=points.length;
  };
  return {kind:'WebGL 3D',draw(scene,vp,width,height){
    gl.viewport(0,0,width,height);gl.clearColor(.025,.045,.046,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(program);gl.uniformMatrix4fv(uniforms.uViewProjection,false,vp);
    const[a,b,c,d]=scene.ground;upload([a,b,c,a,c,d],[.12,.17,.16]);draw(dynamic,gl.TRIANGLES,matrix([0,0,0]),1);
    upload(scene.gridLines,[.21,.29,.26]);draw(dynamic,gl.LINES,matrix([0,0,0]),1);
    upload(scene.targetBars.flatMap(([a,b,c,d])=>[a,b,c,a,c,d]),[1,.77,.32]);draw(dynamic,gl.TRIANGLES,matrix([0,0,0]),1);
    draw(asset,gl.TRIANGLES,scene.craftModel,0);
    if(scene.velocityArrow){upload(scene.velocityLines,[.36,.79,.82]);draw(dynamic,gl.LINES,matrix([0,0,0]),1);}
    if(scene.thrusting){upload([[lowestMeshX+.4,-.15,-.15],[lowestMeshX-1.1,0,0],[lowestMeshX+.4,.15,-.15],[lowestMeshX+.4,.15,-.15],[lowestMeshX-1.1,0,0],[lowestMeshX+.4,0,.18]],[.95,.66,.29]);draw(dynamic,gl.TRIANGLES,scene.craftModel,1);}
  },dispose(){buffers.forEach(item=>gl.deleteBuffer(item));gl.deleteProgram(program);}};
}

function canvasBackend(context) {
  return {kind:'Canvas 3D projection',draw(scene,vp,width,height,dpr){
    context.setTransform(dpr,0,0,dpr,0,0);context.fillStyle='#071111';context.fillRect(0,0,width/dpr,height/dpr);
    const w=width/dpr,h=height/dpr;
    const project=point=>{const p=transformPoint(vp,point);return p[3]>.001?[w*(p[0]/p[3]+1)/2,h*(1-p[1]/p[3])/2,p[2]/p[3]]:null;};
    const polygon=(points,color)=>{const p=points.map(project);if(p.some(value=>!value))return;context.fillStyle=color;context.beginPath();context.moveTo(p[0][0],p[0][1]);for(const point of p.slice(1))context.lineTo(point[0],point[1]);context.closePath();context.fill();};
    polygon(scene.ground,'#1e2c28');
    const lines=(points,color)=>{context.strokeStyle=color;context.lineWidth=1;context.beginPath();for(let i=0;i<points.length;i+=2){const a=project(points[i]),b=project(points[i+1]);if(a&&b){context.moveTo(a[0],a[1]);context.lineTo(b[0],b[1]);}}context.stroke();};
    lines(scene.gridLines,'#34483c');for(const bar of scene.targetBars)polygon(bar,'#ffc452');
    const triangles=[];
    for(let i=0;i<mesh.positions.length;i+=9){
      const vertices=[0,3,6].map(offset=>transformPoint(scene.craftModel,Array.from(mesh.positions.slice(i+offset,i+offset+3))).slice(0,3));
      const projected=vertices.map(project);if(projected.some(value=>!value))continue;
      const normal=transformPoint(scene.rotation,Array.from(mesh.normals.slice(i,i+3))).slice(0,3);
      const light=.34+Math.max(0,dot(normal,unit([-.6,.9,.5])))*.8;
      const color=`rgb(${Array.from(mesh.colors.slice(i,i+3)).map(value=>Math.round(Math.min(1,value*light)*255)).join(',')})`;
      triangles.push({vertices,color,depth:projected.reduce((sum,p)=>sum+p[2],0)});
    }
    triangles.sort((a,b)=>b.depth-a.depth);for(const triangle of triangles)polygon(triangle.vertices,triangle.color);
    if(scene.thrusting)polygon([[lowestMeshX+.4,-.18,0],[lowestMeshX-1.1,0,0],[lowestMeshX+.4,.18,0]].map(point=>transformPoint(scene.craftModel,point).slice(0,3)),'#e7ad58');
    if(scene.velocityArrow)lines(scene.velocityLines,'#6bc8d1');
  },dispose(){}};
}

/** The host owns sample cadence; pointer controls only orbit or zoom the camera. */
export function createFlight3DRenderer(canvas) {
  let backend,gl,fallback=null,last=null,azimuth=.36,elevation=.29,zoom=1,disposed=false;
  let width=1,height=1,dpr=1;
  try{gl=canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});if(gl)backend=webglBackend(gl);}catch{}
  if(!backend){
    let target=canvas;
    if(gl&&canvas.ownerDocument){fallback=canvas.ownerDocument.createElement('canvas');fallback.className=canvas.className;fallback.setAttribute('aria-label','3D flight projection fallback');canvas.hidden=true;canvas.insertAdjacentElement('afterend',fallback);target=fallback;}
    const context=target.getContext('2d');if(!context)throw new Error('3D graphics unavailable; use the 2D diagnostic.');backend=canvasBackend(context);
  }
  const surface=()=>fallback??canvas;
  function draw(scene=last){
    if(disposed||!scene)return;last=scene;
    const target=surface();width=Math.max(1,target.clientWidth||canvas.clientWidth||800);height=Math.max(1,target.clientHeight||canvas.clientHeight||440);dpr=Math.min(globalThis.devicePixelRatio||1,2);
    target.width=Math.round(width*dpr);target.height=Math.round(height*dpr);
    const camera=flight3DCamera(scene,width,height,{azimuth,elevation,zoom});
    backend.draw(scene,camera.viewProjection,target.width,target.height,dpr);
  }
  let dragging=null;
  const down=event=>{if(event.button!==0)return;dragging=[event.clientX,event.clientY];surface().setPointerCapture?.(event.pointerId);};
  const move=event=>{if(!dragging)return;azimuth-=(event.clientX-dragging[0])*.006;elevation=Math.max(.06,Math.min(1.3,elevation+(event.clientY-dragging[1])*.004));dragging=[event.clientX,event.clientY];draw();};
  const up=()=>{dragging=null;};
  const wheel=event=>{event.preventDefault();zoom=Math.max(.6,Math.min(2.5,zoom*Math.exp(event.deltaY*.001)));draw();};
  const target=surface();for(const[name,handler]of[['pointerdown',down],['pointermove',move],['pointerup',up],['pointercancel',up],['wheel',wheel]])target.addEventListener(name,handler,name==='wheel'?{passive:false}:undefined);
  return {draw,get kind(){return backend.kind;},get surface(){return surface();},reset(){azimuth=.36;elevation=.29;zoom=1;draw();},
    dispose(){if(disposed)return;disposed=true;for(const[name,handler]of[['pointerdown',down],['pointermove',move],['pointerup',up],['pointercancel',up],['wheel',wheel]])target.removeEventListener(name,handler);backend.dispose();if(fallback){fallback.remove();canvas.hidden=false;}}};
}
