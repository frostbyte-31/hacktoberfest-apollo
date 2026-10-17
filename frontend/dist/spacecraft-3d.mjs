/**
 * Browser-native 3D presentation only. Supplied scalar-first body-to-stable
 * quaternions orient an illustrative LM. Camera movement never changes flight
 * state, and this module never advances position, velocity, or attitude.
 */
import { buildSpacecraftMesh } from './spacecraft-mesh.mjs';

const IDENTITY = Object.freeze([1,0,0,0]);
const subtract = (a,b) => a.map((v,i)=>v-b[i]);
const dot = (a,b) => a.reduce((s,v,i)=>s+v*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const normalize = a => a.map(v=>v/Math.hypot(...a));
export const validQuaternion = q => Array.isArray(q) && q.length===4 && q.every(Number.isFinite) && Math.abs(Math.hypot(...q)-1)<1e-4;

/** Column-major active rotation, in the backend's unchanged body/stable basis. */
export function quaternionMatrix(q) {
  if(!validQuaternion(q)) throw new TypeError('A finite unit body-to-stable quaternion is required.');
  const [w,x,y,z]=q;
  return [1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y),0,
    2*(x*y-w*z),1-2*(x*x+z*z),2*(y*z+w*x),0,
    2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y),0,0,0,0,1];
}
export function multiplyMatrices(a,b) {
  const result=Array(16).fill(0);
  for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)result[c*4+r]+=a[k*4+r]*b[c*4+k];
  return result;
}
export function transformPoint(matrix,point) {
  const p=[...point,1];
  return Array.from({length:4},(_,r)=>p.reduce((s,v,c)=>s+matrix[c*4+r]*v,0));
}
export function perspectiveMatrix(fov,aspect,near,far) {
  const f=1/Math.tan(fov/2),range=1/(near-far);
  return [f/aspect,0,0,0,0,f,0,0,0,0,(near+far)*range,-1,0,0,2*near*far*range,0];
}
export function lookAtMatrix(eye,target,up=[0,1,0]) {
  const z=normalize(subtract(eye,target)),x=normalize(cross(up,z)),y=cross(z,x);
  return [x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1];
}
// Proper rotation (determinant +1), with the backend's up axis displayed upward.
const DISPLAY_BASIS=[0,1,0,0,1,0,0,0,0,0,-1,0,0,0,0,1];
const stableModel=q=>multiplyMatrices(DISPLAY_BASIS,quaternionMatrix(q));
const mesh=buildSpacecraftMesh();

const VERTEX=`
attribute vec3 aPosition; attribute vec3 aNormal; attribute vec3 aColor;
uniform mat4 uModel; uniform mat4 uViewProjection;
varying vec3 vNormal; varying vec3 vPosition; varying vec3 vColor;
void main(){vec4 world=uModel*vec4(aPosition,1.0);vNormal=mat3(uModel)*aNormal;vPosition=world.xyz;vColor=aColor;gl_Position=uViewProjection*world;}
`;
const FRAGMENT=`
precision mediump float;
varying vec3 vNormal; varying vec3 vPosition; varying vec3 vColor;
uniform vec3 uEye; uniform float uOpacity; uniform float uUnlit; uniform vec3 uTint;
void main(){
vec3 normal=normalize(vNormal);if(!gl_FrontFacing)normal=-normal;
vec3 key=normalize(vec3(-0.6,1.0,-0.8));vec3 fill=normalize(vec3(0.8,0.2,0.65));
float diffuse=max(dot(normal,key),0.0);float bounce=max(dot(normal,fill),0.0);
vec3 view=normalize(uEye-vPosition);vec3 halfway=normalize(key+view);
float spec=pow(max(dot(normal,halfway),0.0),28.0)*0.35;
float rim=pow(1.0-max(dot(normal,view),0.0),3.0)*0.18;
vec3 lit=vColor*(0.34+diffuse*0.82+bounce*0.22)+vec3(spec)+vec3(0.21,0.40,0.48)*rim;
gl_FragColor=vec4(mix(lit,vColor,uUnlit)*uTint,uOpacity);
}
`;
const POINT_VERTEX=`attribute vec3 aPosition;uniform mat4 uViewProjection;void main(){gl_Position=uViewProjection*vec4(aPosition,1.0);gl_PointSize=1.4;}`;
const POINT_FRAGMENT=`precision mediump float;void main(){float d=length(gl_PointCoord-vec2(0.5));gl_FragColor=vec4(0.69,0.80,0.88,(1.0-smoothstep(0.08,0.5,d))*0.5);}`;

function shader(gl,type,source) {
  const result=gl.createShader(type);gl.shaderSource(result,source);gl.compileShader(result);
  if(!gl.getShaderParameter(result,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(result);gl.deleteShader(result);throw new Error(`3D shader could not compile: ${message}`);}
  return result;
}
function program(gl,vertexSource,fragmentSource) {
  const vertex=shader(gl,gl.VERTEX_SHADER,vertexSource),fragment=shader(gl,gl.FRAGMENT_SHADER,fragmentSource),result=gl.createProgram();
  gl.attachShader(result,vertex);gl.attachShader(result,fragment);gl.linkProgram(result);gl.deleteShader(vertex);gl.deleteShader(fragment);
  if(!gl.getProgramParameter(result,gl.LINK_STATUS)){const message=gl.getProgramInfoLog(result);gl.deleteProgram(result);throw new Error(`3D shader could not link: ${message}`);}
  return result;
}

/** Returns a disposable camera/renderer; animation cadence belongs to the host. */
export function createFlightRenderer(canvas) {
  let azimuth=.48,elevation=.22,distance=7.4,width=1,height=1,dpr=1,disposed=false;
  let last={quaternion:null,targetQuaternion:null,available:false};
  let contextLost=false,problem=null,backend=null;
  let gl;
  try{gl=canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power',preserveDrawingBuffer:false});}catch(error){problem=error.message;}
  if(gl){
    try{backend=createWebGLBackend(gl);}catch(error){problem=error.message;}
  }
  // An already acquired WebGL context cannot become a 2D context. Overlay a
  // separate canvas only in the rare shader-initialization failure case.
  let fallbackCanvas=null;
  if(!backend){
    let fallbackTarget=canvas;
    if(gl && canvas.ownerDocument){
      fallbackCanvas=canvas.ownerDocument.createElement('canvas');fallbackCanvas.className=canvas.className;
      fallbackCanvas.setAttribute('aria-label','Three-dimensional spacecraft fallback');
      Object.assign(fallbackCanvas.style,{width:'100%',height:'100%',display:'block'});
      canvas.hidden=true;canvas.insertAdjacentElement('afterend',fallbackCanvas);fallbackTarget=fallbackCanvas;
    }
    const ctx=fallbackTarget.getContext('2d');
    if(!ctx)throw new Error(problem || 'This browser could not create a 3D or canvas context.');
    backend=createCanvasBackend(ctx);
    problem=problem || 'WebGL unavailable; using a projected 3D canvas model.';
  }
  const surface=()=>fallbackCanvas || canvas;
  function camera(){
    const eye=[Math.sin(azimuth)*Math.cos(elevation)*distance,Math.sin(elevation)*distance+.14,-Math.cos(azimuth)*Math.cos(elevation)*distance];
    return {eye,viewProjection:multiplyMatrices(perspectiveMatrix(Math.PI/4,width/height,.15,180),lookAtMatrix(eye,[0,.14,0]))};
  }
  function resize(){
    if(disposed)return;
    const target=surface();
    width=Math.max(1,target.clientWidth || canvas.clientWidth || 640);height=Math.max(1,target.clientHeight || canvas.clientHeight || 480);
    dpr=Math.min(globalThis.devicePixelRatio || 1,2);
    const pixelWidth=Math.round(width*dpr),pixelHeight=Math.round(height*dpr);
    if(target.width!==pixelWidth)target.width=pixelWidth;if(target.height!==pixelHeight)target.height=pixelHeight;
  }
  function draw(state=last){
    if(disposed)return;
    last={...state};
    resize();
    if(contextLost)return;
    const q=validQuaternion(state.quaternion) ? state.quaternion : null;
    const target=validQuaternion(state.targetQuaternion) ? state.targetQuaternion : null;
    // With no verified orientation the model remains hidden, while the stable
    // target may still be shown as a distinct wireframe training instruction.
    backend.draw({q:state.available===false ? null:q,target,width,height,dpr,...camera(),matched:Number.isFinite(state.aimErrorDeg)&&state.aimErrorDeg<2});
  }
  const lost=event=>{event.preventDefault();contextLost=true;problem='The 3D graphics context was lost. Restore the tab or reload to resume the model.';canvas.dispatchEvent(new CustomEvent('flight-renderer-status',{detail:{available:false,message:problem}}));};
  const restored=()=>{
    try{backend?.dispose();backend=createWebGLBackend(gl);contextLost=false;problem=null;draw(last);canvas.dispatchEvent(new CustomEvent('flight-renderer-status',{detail:{available:true,message:'3D graphics restored.'}}));}
    catch(error){problem=error.message;}
  };
  canvas.addEventListener('webglcontextlost',lost,false);canvas.addEventListener('webglcontextrestored',restored,false);
  resize();
  return {draw,resize,
    orbit(dx,dy){if(disposed || ![dx,dy].every(Number.isFinite))return;azimuth-=dx*.006;elevation=Math.max(-1.35,Math.min(1.35,elevation+dy*.004));},
    zoom(delta){if(disposed || !Number.isFinite(delta))return;distance=Math.max(4.9,Math.min(13,distance*Math.exp(delta*.001)));},
    reset(){azimuth=.48;elevation=.22;distance=7.4;},
    get kind(){return backend.kind;},get surface(){return surface();},get status(){return {available:!contextLost&&!disposed,message:problem};},
    dispose(){if(disposed)return;disposed=true;backend.dispose();canvas.removeEventListener('webglcontextlost',lost);canvas.removeEventListener('webglcontextrestored',restored);if(fallbackCanvas){fallbackCanvas.remove();canvas.hidden=false;}},
  };
}

function createWebGLBackend(gl) {
  const main=program(gl,VERTEX,FRAGMENT),points=program(gl,POINT_VERTEX,POINT_FRAGMENT),buffers=[];
  const locations={};
  for(const name of ['aPosition','aNormal','aColor'])locations[name]=gl.getAttribLocation(main,name);
  for(const name of ['uModel','uViewProjection','uEye','uOpacity','uUnlit','uTint'])locations[name]=gl.getUniformLocation(main,name);
  const buffer=data=>{const item=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,item);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);buffers.push(item);return item;};
  const geometry=(position,normal,color)=>({position:buffer(position),normal:buffer(normal || new Float32Array(position.length).fill(.577)),color:buffer(color || new Float32Array(position.length).fill(1)),count:position.length/3});
  const solid=geometry(mesh.positions,mesh.normals,mesh.colors),edges=geometry(mesh.lines,null,mesh.lineColors);
  const ghost=geometry(mesh.ghostLines);
  const frame=[],frameColors=[];
  const segment=(a,b,c)=>{frame.push(...a,...b);frameColors.push(...c,...c);};
  // Stable-frame orientation rings are a reference instrument, not an orbit.
  for(let axis=0;axis<3;axis++)for(let i=0;i<96;i++){
    const point=angle=>{const p=[0,0,0];p[(axis+1)%3]=Math.cos(angle)*2.72;p[(axis+2)%3]=Math.sin(angle)*2.72;return p;};
    if(i%3!==2)segment(point(i*Math.PI/48),point((i+1)*Math.PI/48),axis===0?[.19,.32,.37]:[.12,.22,.26]);
  }
  for(let axis=0;axis<3;axis++){
    const a=[0,0,0],b=[0,0,0];a[axis]=-3.15;b[axis]=3.15;
    segment(a,b,axis===0?[.31,.38,.42]:axis===1?[.33,.27,.17]:[.17,.35,.34]);
  }
  const stableFrame=geometry(new Float32Array(frame),null,new Float32Array(frameColors));
  const stars=[];
  for(let i=0;i<380;i++){
    const y=1-2*(i+.5)/380,angle=i*2.399963229728653,r=Math.sqrt(1-y*y);
    stars.push(Math.cos(angle)*r*80,y*80,Math.sin(angle)*r*80);
  }
  const starBuffer=buffer(new Float32Array(stars));
  const pointPosition=gl.getAttribLocation(points,'aPosition'),pointMatrix=gl.getUniformLocation(points,'uViewProjection');
  const attribute=(location,item)=>{gl.bindBuffer(gl.ARRAY_BUFFER,item);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,3,gl.FLOAT,false,0,0);};
  const drawGeometry=(geo,mode,model,opacity=1,unlit=0,tint=[1,1,1])=>{
    attribute(locations.aPosition,geo.position);attribute(locations.aNormal,geo.normal);attribute(locations.aColor,geo.color);
    gl.uniformMatrix4fv(locations.uModel,false,model);gl.uniform1f(locations.uOpacity,opacity);gl.uniform1f(locations.uUnlit,unlit);gl.uniform3fv(locations.uTint,tint);
    gl.drawArrays(mode,0,geo.count);
  };
  return {kind:'WebGL 3D',
    draw({q,target,width,height,dpr,viewProjection,eye,matched}){
      gl.viewport(0,0,Math.round(width*dpr),Math.round(height*dpr));
      gl.clearColor(.020,.035,.054,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      gl.disable(gl.DEPTH_TEST);gl.useProgram(points);attribute(pointPosition,starBuffer);gl.uniformMatrix4fv(pointMatrix,false,viewProjection);gl.drawArrays(gl.POINTS,0,stars.length/3);
      gl.useProgram(main);gl.uniformMatrix4fv(locations.uViewProjection,false,viewProjection);gl.uniform3fv(locations.uEye,eye);
      gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.depthMask(true);
      drawGeometry(stableFrame,gl.LINES,DISPLAY_BASIS,.8,1);
      if(q){
        gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);drawGeometry(solid,gl.TRIANGLES,stableModel(q));gl.disable(gl.POLYGON_OFFSET_FILL);
        drawGeometry(edges,gl.LINES,stableModel(q),.55,1);
      }
      if(target){
        gl.depthMask(false);gl.disable(gl.DEPTH_TEST);
        drawGeometry(ghost,gl.LINES,stableModel(target),q?.16:.35,1,matched?[.42,.91,.76]:[.38,.69,.76]);
        gl.depthMask(true);
      }
    },
    dispose(){buffers.forEach(item=>gl.deleteBuffer(item));gl.deleteProgram(main);gl.deleteProgram(points);},
  };
}

function createCanvasBackend(ctx) {
  const toRGB=(i,light=1)=>`rgb(${mesh.colors.slice(i,i+3).map(v=>Math.round(Math.min(1,v*light)*255)).join(',')})`;
  const polygons=[];
  for(let i=0;i<mesh.positions.length;i+=9)polygons.push({vertices:[...mesh.positions.slice(i,i+3),...mesh.positions.slice(i+3,i+6),...mesh.positions.slice(i+6,i+9)],i});
  return {kind:'Canvas 3D',
    draw({q,target,width,height,dpr,viewProjection,matched}){
      ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
      const gradient=ctx.createRadialGradient(width*.5,height*.45,10,width*.5,height*.45,width*.65);
      gradient.addColorStop(0,'#142836');gradient.addColorStop(1,'#050a11');ctx.fillStyle=gradient;ctx.fillRect(0,0,width,height);
      for(let i=0;i<100;i++){ctx.fillStyle=i%7?'#52717f66':'#c3d2d399';ctx.fillRect(((i*163+37)%997)/997*width,((i*239+83)%991)/991*height,1,1);}
      const project=(p,matrix)=>{const v=transformPoint(matrix,p);return [width*(v[0]/v[3]+1)/2,height*(1-v[1]/v[3])/2,v[2]/v[3]];};
      if(q){
        const model=stableModel(q),matrix=multiplyMatrices(viewProjection,model);
        const ordered=polygons.map(p=>{const points=[0,3,6].map(j=>project(p.vertices.slice(j,j+3),matrix));return{...p,points,depth:points.reduce((s,v)=>s+v[2],0)/3};}).sort((a,b)=>b.depth-a.depth);
        for(const p of ordered){
          const normal=transformPoint(model,[...mesh.normals.slice(p.i,p.i+3)]).slice(0,3);
          const light=.44+Math.max(0,dot(normal,normalize([-.6,1,-.8])))*.65;
          ctx.fillStyle=toRGB(p.i,light);ctx.beginPath();p.points.forEach((v,i)=>i?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1]));ctx.closePath();ctx.fill();
        }
        const edgeMatrix=multiplyMatrices(viewProjection,model);ctx.strokeStyle='#d3be8460';ctx.lineWidth=.6;
        ctx.beginPath();for(let i=0;i<mesh.lines.length;i+=6){const a=project(mesh.lines.slice(i,i+3),edgeMatrix),b=project(mesh.lines.slice(i+3,i+6),edgeMatrix);ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);}ctx.stroke();
      }
      if(target){
        const matrix=multiplyMatrices(viewProjection,stableModel(target));ctx.strokeStyle=matched?'#75d8ac40':'#75b3c440';ctx.lineWidth=.75;ctx.beginPath();
        for(let i=0;i<mesh.ghostLines.length;i+=6){const a=project(mesh.ghostLines.slice(i,i+3),matrix),b=project(mesh.ghostLines.slice(i+3,i+6),matrix);ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);}ctx.stroke();
      }
    },dispose(){},
  };
}
