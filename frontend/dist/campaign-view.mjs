/** Static 3D configuration references, never a propagated mission or flight state. */
import {buildSpacecraftMesh} from './spacecraft-mesh.mjs';
import {buildDockedCsmMesh} from './mission-3d.mjs';
import {perspectiveMatrix,lookAtMatrix,multiplyMatrices,transformPoint} from './spacecraft-3d.mjs';

const lm=buildSpacecraftMesh(),csm=buildDockedCsmMesh();
const sub=(a,b)=>a.map((v,i)=>v-b[i]),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=a=>{const n=Math.hypot(...a);return a.map(v=>v/n);},dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const configurationNames={'earth-stack':'CSM + closed SLA + S-IVB · Eagle stowed','docked-csm-lm':'Columbia and Eagle · docked configuration',
  'docked-csm-lm-deployed':'Columbia and Eagle · docked with landing gear deployed',lm:'Eagle · descent and ascent stages',ascent:'Eagle ascent stage · descent stage left on Moon','ascent-csm':'Eagle ascent stage and Columbia · rendezvous reference',csm:'Columbia · Command and Service Modules',cm:'Columbia Command Module · Service Module discarded'};

export function buildCampaignConfiguration(configuration='earth-stack'){
  if(!Object.hasOwn(configurationNames,configuration))throw new Error('Unknown historical spacecraft configuration.');
  const triangles=[],parts=[];
  const tri=(a,b,c,color)=>triangles.push({vertices:[a,b,c],color,normal:unit(cross(sub(b,a),sub(c,a)))});
  const frustum=(name,y0,y1,r0,r1,color)=>{
    parts.push(name);const n=32;
    for(let i=0;i<n;i++){const a=i*2*Math.PI/n,b=(i+1)*2*Math.PI/n,p=(y,r,t)=>[r*Math.cos(t),y,r*Math.sin(t)];const lo=p(y0,r0,a),hi=p(y1,r1,a),next=p(y0,r0,b),nextHi=p(y1,r1,b);tri(lo,hi,nextHi,color);tri(lo,nextHi,next,color);if(r0>0)tri([0,y0,0],lo,next,color);if(r1>0)tri([0,y1,0],nextHi,hi,color);}
  };
  const asset=(mesh,allowed,offset=[0,0,0],scale=1)=>{
    const ranges=Object.entries(mesh.components).filter(([name])=>!allowed||allowed(name));parts.push(...ranges.map(([name])=>name));
    for(const[,range]of ranges)for(let i=range.firstVertex*3;i<(range.firstVertex+range.vertexCount)*3;i+=9){const vertices=[0,3,6].map(j=>{const p=Array.from(mesh.positions.slice(i+j,i+j+3));return[-p[1]*scale+offset[0],p[0]*scale+offset[1],p[2]*scale+offset[2]];});tri(...vertices,Array.from(mesh.colors.slice(i,i+3)));}
  };
  const columbia=(base=0,commandOnly=false,hasProbe=true)=>{
    if(!commandOnly){frustum('service-engine',base-.65,base,.55,.23,[.23,.28,.29]);frustum('service-module',base,base+2.4,.72,.72,[.65,.70,.69]);for(let i=0;i<4;i++)frustum('service-band',base+.25+i*.56,base+.28+i*.56,.726,.726,[.4,.47,.47]);}
    const y=commandOnly?base:base+2.4;frustum('heat-shield',y-.08,y,.75,.75,[.22,.27,.28]);frustum('command-module',y,y+1.35,.75,.13,[.81,.83,.79]);if(hasProbe)frustum('docking-probe',y+1.35,y+1.56,.13,.10,[.55,.61,.59]);
  };
  if(configuration==='earth-stack'){
    frustum('s-ivb-engine',-.9,0,.82,.36,[.22,.27,.29]);frustum('s-ivb',0,4.5,1.28,1.28,[.82,.84,.80]);frustum('s-ivb-aft-band',.15,.45,1.285,1.285,[.18,.23,.25]);frustum('instrument-unit',4.32,4.5,1.30,1.30,[.18,.24,.24]);frustum('closed-sla',4.5,6.5,1.28,.72,[.65,.69,.66]);columbia(6.5);
  }else if(configuration==='docked-csm-lm'||configuration==='docked-csm-lm-deployed'){
    // Eagle's crew deployed the landing gear before undocking in lunar orbit:
    // https://www.nasa.gov/history/50-years-ago-one-small-step-one-giant-leap/
    const deployed=configuration==='docked-csm-lm-deployed';
    asset(lm,name=>name!=='antennae-and-ladder'&&(deployed||name!=='landing-gear'));asset(csm);
  }else if(configuration==='lm')asset(lm);
  else if(configuration==='ascent')asset(lm,name=>['ascent-cabin','windows-and-hatch','rcs-clusters'].includes(name));
  else if(configuration==='ascent-csm'){asset(lm,name=>['ascent-cabin','windows-and-hatch','rcs-clusters'].includes(name),[-1.7,0,0]);columbia(0);}
  // The final probe and drogue were stowed in Eagle before LM jettison.
  // Apollo 11 Mission Report, page 4-19:
  // https://sma.nasa.gov/SignificantIncidents/assets/apollo-11-mission-report.pdf
  else columbia(0,configuration==='cm',false);
  return{configuration,label:configurationNames[configuration],triangles,parts,metadata:{mode:'STATIC HISTORICAL CONFIGURATION',geometry:'Schematic 3D visual model; not to scale',flightState:null,positionM:null,velocityMps:null,simulationTime:null,interaction:'Camera only; no actuator or spacecraft command'}};
}

export function createCampaignViewer(canvas){
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Spacecraft reference graphics are unavailable.');
  let model=buildCampaignConfiguration(),angle=.55,elevation=.16,zoom=1,dragging=null,disposed=false;
  function draw(configuration){
    if(disposed)return;if(configuration)model=buildCampaignConfiguration(configuration);
    const w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight),dpr=Math.min(globalThis.devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const vertices=model.triangles.flatMap(t=>t.vertices),minimum=[0,1,2].map(axis=>Math.min(...vertices.map(p=>p[axis]))),maximum=[0,1,2].map(axis=>Math.max(...vertices.map(p=>p[axis]))),center=minimum.map((v,i)=>(v+maximum[i])/2),radius=Math.max(...vertices.map(p=>Math.hypot(...sub(p,center))));
    const distance=radius/Math.sin(Math.atan(Math.tan(Math.PI/8)*Math.min(1,w/h)))*1.22*zoom;
    const eye=[center[0]+Math.sin(angle)*Math.cos(elevation)*distance,center[1]+Math.sin(elevation)*distance,center[2]+Math.cos(angle)*Math.cos(elevation)*distance];
    const matrix=multiplyMatrices(perspectiveMatrix(Math.PI/4,w/h,.01,Math.max(100,distance*4)),lookAtMatrix(eye,center,[0,1,0]));
    const project=p=>{const v=transformPoint(matrix,p);return[(v[0]/v[3]+1)*w/2,(1-v[1]/v[3])*h/2,v[2]/v[3]];};
    const light=unit([-.6,.7,1]);
    for(const triangle of model.triangles.map(t=>({...t,points:t.vertices.map(project)})).sort((a,b)=>b.points.reduce((s,p)=>s+p[2],0)-a.points.reduce((s,p)=>s+p[2],0))){
      const shade=.35+Math.max(0,dot(triangle.normal,light))*.8;ctx.fillStyle=`rgb(${triangle.color.map(v=>Math.round(Math.min(1,v*shade)*255)).join(',')})`;ctx.beginPath();triangle.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fill();
    }
  }
  const down=e=>{if(e.button!==0)return;dragging=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};
  const move=e=>{if(!dragging)return;angle+=(e.clientX-dragging[0])*.008;elevation=Math.max(-1.1,Math.min(1.1,elevation+(e.clientY-dragging[1])*.005));dragging=[e.clientX,e.clientY];draw();};
  const up=()=>{dragging=null;};
  for(const[name,fn]of[['pointerdown',down],['pointermove',move],['pointerup',up],['pointercancel',up],['lostpointercapture',up]])canvas.addEventListener(name,fn);
  draw();return{draw,reset(){angle=.55;elevation=.16;zoom=1;draw();},get metadata(){return model.metadata;},dispose(){disposed=true;for(const[name,fn]of[['pointerdown',down],['pointermove',move],['pointerup',up],['pointercancel',up],['lostpointercapture',up]])canvas.removeEventListener(name,fn);}};
}
