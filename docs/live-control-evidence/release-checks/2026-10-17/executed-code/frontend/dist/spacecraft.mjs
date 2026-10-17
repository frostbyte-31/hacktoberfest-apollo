import { rotateVector } from './replay.mjs';

// Stylized illustrative geometry, deliberately separate from physical thruster mapping.
const body = (height, x, z) => [height, x, z];
const facets = [];
const lines = [];
const face = (vertices, color, outline = '#7d826655') => facets.push({ vertices, color, outline });
const strut = (a, b, color = '#a1a386', width = 1.3) => lines.push({ a, b, color, width });
const ring = (height, radius, n = 8, offset = Math.PI / 8) => Array.from({ length: n }, (_, i) => body(height, Math.cos(i * Math.PI * 2 / n + offset) * radius, Math.sin(i * Math.PI * 2 / n + offset) * radius));
const lower = ring(-0.66, 1.05);
const upper = ring(0.16, 1.05);
const gold = ['#8f7035', '#b18a43', '#c3a05b', '#a47c38', '#967238', '#c9a461', '#b4934e', '#92733f'];
for (let i = 0; i < 8; i++) {
  const n = (i + 1) % 8;
  face([lower[i], lower[n], upper[n], upper[i]], gold[i], '#d7b66c77');
  const center = lower[i].map((v, j) => (v + upper[n][j]) / 2);
  strut(lower[i], center, '#e4c47855', .7);
  strut(upper[i], center, '#f4d99c44', .7);
  strut(upper[n], center, '#5b492a88', .7);
}
face(upper, '#c1a16c');
face(lower, '#393c2d');
const cabinLow = ring(.3, .69);
const cabinHigh = ring(1.24, .63);
const roof = ring(1.57, .31);
const grey = ['#71786b', '#4e5950', '#28362f', '#354139', '#728071', '#93988a', '#646e5f', '#8d9384'];
for (let i = 0; i < 8; i++) {
  const n = (i + 1) % 8;
  face([cabinLow[i], cabinLow[n], cabinHigh[n], cabinHigh[i]], grey[i], '#c5cbb06b');
  face([cabinHigh[i], cabinHigh[n], roof[n], roof[i]], i % 2 ? '#8e9584' : '#b0b29b', '#d5d4b177');
  strut(upper[i], cabinLow[i], '#c5c9a9', 1.2);
}
face(roof, '#b4b6a0');
// Windows and hatch are visual model details, not a validated physical reconstruction.
face([body(1.12,-.48,.49),body(.78,-.48,.49),body(.84,-.15,.69)],'#0c1b1b','#abb8a2');
face([body(1.12,.48,.49),body(.84,.15,.69),body(.78,.48,.49)],'#102322','#b7bda4');
face([body(.72,-.19,.69),body(.34,-.19,.69),body(.34,.19,.69),body(.72,.19,.69)],'#566153','#aeb699');
strut(body(.48,-.08,.697),body(.48,.08,.697),'#dbdcc0',1.5);
for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
  const foot = body(-1.5, sx * 1.62, sz * 1.62);
  const hip = body(-.17, sx * .69, sz * .69);
  const knee = body(-.9, sx * 1.22, sz * 1.22);
  strut(hip, foot, '#c7b880', 2.4);
  strut(body(-.6, sx * .75, sz * .55), knee, '#9d9875', 1.1);
  strut(body(-.6, sx * .55, sz * .75), knee, '#9d9875', 1.1);
  strut(body(-.6, sx * .7, -sz * .3), foot, '#867c55', .9);
  const pad = Array.from({ length: 12 }, (_, i) => body(-1.52, sx * 1.62 + Math.cos(i * Math.PI / 6) * .22, sz * 1.62 + Math.sin(i * Math.PI / 6) * .22));
  face(pad, '#9c8c59', '#d2bd7d');
}
// Engine bell is inert illustrative geometry. No descent thrust is depicted.
const bellTop = ring(-.66, .18, 10, 0);
const bellBottom = ring(-1.14, .34, 10, 0);
for (let i = 0; i < 10; i++) face([bellTop[i], bellTop[(i+1)%10], bellBottom[(i+1)%10], bellBottom[i]],'#374039','#6d775d77');
face(bellBottom, '#111b16', '#7d8768');
strut(body(1.53,0,0),body(2.02,0,0),'#c6cbb1',1.2);
strut(body(1.97,-.26,0),body(1.97,.26,0),'#b6bfa1',1);
strut(body(1.82,0,0),body(1.96,.26,0),'#8b987c',.6);
for(let i=0;i<5;i++) strut(body(.13-i*.13,-.11,1.0+i*.045),body(.13-i*.13,.11,1.0+i*.045),'#c4c3a1',1.2);
strut(body(.19,-.12,.98),body(-.46,-.12,1.25),'#9eae8b',1.2);
strut(body(.19,.12,.98),body(-.46,.12,1.25),'#9eae8b',1.2);

export function createSpacecraftRenderer(canvas) {
  const ctx = canvas.getContext('2d');
  let azimuth = -.58;
  let elevation = .23;
  let axes = true;
  let width = 1, height = 1, dpr = 1;
  function resize() {
    width = canvas.clientWidth; height = canvas.clientHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  }
  function project(v, quaternion, scale = height * .17) {
    const world = rotateVector(quaternion, v);
    const x = Math.cos(azimuth)*world[1] - Math.sin(azimuth)*world[2];
    const z = Math.sin(azimuth)*world[1] + Math.cos(azimuth)*world[2];
    const y = Math.cos(elevation)*world[0] - Math.sin(elevation)*z;
    const depth = Math.sin(elevation)*world[0] + Math.cos(elevation)*z;
    const factor = 7.5 / (7.5 - depth);
    return [width * .50 + x * scale * factor, height * .53 - y * scale * factor, depth];
  }
  function path(vertices) {
    ctx.beginPath();vertices.forEach((v,i)=>i?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1]));ctx.closePath();
  }
  function draw(q, time, feedbackConnected) {
    if (width !== canvas.clientWidth || height !== canvas.clientHeight) resize();
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
    const gradient=ctx.createRadialGradient(width*.5,height*.49,20,width*.5,height*.49,width*.65);
    gradient.addColorStop(0,'#263021');gradient.addColorStop(.65,'#172017');gradient.addColorStop(1,'#121813');ctx.fillStyle=gradient;ctx.fillRect(0,0,width,height);
    // Stable-frame reference grid; no surface, trajectory, altitude or vehicle translation.
    ctx.lineWidth=.5;
    for(let i=-6;i<=6;i++){
      const a=project(body(-1.9,i*.65,-4),[1,0,0,0]);const b=project(body(-1.9,i*.65,4),[1,0,0,0]);
      ctx.strokeStyle=i===0?'#62705249':'#526d4930';ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();
      const c=project(body(-1.9,-4,i*.65),[1,0,0,0]);const d=project(body(-1.9,4,i*.65),[1,0,0,0]);ctx.beginPath();ctx.moveTo(c[0],c[1]);ctx.lineTo(d[0],d[1]);ctx.stroke();
    }
    ctx.strokeStyle='#78946712';ctx.lineWidth=.5;
    for(let r=1;r<4;r++){ctx.beginPath();ctx.ellipse(width*.5,height*.53,r*height*.21,r*height*.10,-.13,0,Math.PI*2);ctx.stroke();}
    // Sparse deterministic reference points, fixed in the display rather than fictitious motion.
    for(let i=0;i<55;i++){const x=((i*173+43)%997)/997*width;const y=((i*229+71)%991)/991*height;ctx.fillStyle=i%5?'#869c6f36':'#b8c7a36b';ctx.fillRect(x,y,1,1);}
    ctx.strokeStyle='#8c9c6b28';ctx.setLineDash([2,5]);ctx.beginPath();ctx.moveTo(width*.5,40);ctx.lineTo(width*.5,height-35);ctx.stroke();ctx.setLineDash([]);
    const projected=facets.map(f=>({...f,points:f.vertices.map(v=>project(v,q))}));
    projected.sort((a,b)=>a.points.reduce((s,v)=>s+v[2],0)/a.points.length-b.points.reduce((s,v)=>s+v[2],0)/b.points.length);
    for(const f of projected){path(f.points);ctx.fillStyle=f.color;ctx.fill();ctx.strokeStyle=f.outline;ctx.lineWidth=.7;ctx.stroke();}
    const sortedLines=lines.map(l=>({...l,a:project(l.a,q),b:project(l.b,q)})).sort((a,b)=>(a.a[2]+a.b[2])-(b.a[2]+b.b[2]));
    for(const l of sortedLines){ctx.strokeStyle=l.color;ctx.lineWidth=l.width;ctx.beginPath();ctx.moveTo(l.a[0],l.a[1]);ctx.lineTo(l.b[0],l.b[1]);ctx.stroke();}
    if(axes){
      const origin=project([0,0,0],q);
      const labels=[['P / YAW',[1.9,0,0],'#d5ae75'],['Q / PITCH',[0,1.95,0],'#94bfb0'],['R / ROLL',[0,0,1.95],'#899bb4']];
      for(const[label,v,color]of labels){const end=project(v,q);ctx.strokeStyle=color;ctx.globalAlpha=.7;ctx.lineWidth=.8;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(origin[0],origin[1]);ctx.lineTo(end[0],end[1]);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;ctx.fillStyle=color;ctx.beginPath();ctx.arc(end[0],end[1],2,0,Math.PI*2);ctx.fill();ctx.font='7px monospace';ctx.fillText(label,end[0]+7,end[1]+2);}
    }
    // A display locator only. It never changes the recorded quaternion.
    const center=project([0,0,0],q);ctx.strokeStyle=feedbackConnected?'#abbf7555':'#c3946355';ctx.lineWidth=.7;
    for(const[x,y,sx,sy]of [[-11,-11,1,1],[11,-11,-1,1],[-11,11,1,-1],[11,11,-1,-1]]){ctx.beginPath();ctx.moveTo(center[0]+x+sx*4,center[1]+y);ctx.lineTo(center[0]+x,center[1]+y);ctx.lineTo(center[0]+x,center[1]+y+sy*4);ctx.stroke();}
  }
  resize();
  return { draw, orbit(dx,dy){azimuth+=dx*.006;elevation=Math.max(-.6,Math.min(.8,elevation+dy*.004));}, reset(){azimuth=-.58;elevation=.23;}, setAxes(value){axes=value;} };
}
