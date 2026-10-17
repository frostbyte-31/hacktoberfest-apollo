/**
 * Procedural, illustrative Lunar Module geometry. Coordinates use the fixture's
 * body axes [up, lateral, lateral]; dimensions are visual model units, not metres.
 * This asset contains no vehicle model, state propagation, or actuator mapping.
 */
const add = (a, b) => a.map((n, i) => n + b[i]);
const sub = (a, b) => a.map((n, i) => n - b[i]);
const mul = (v, s) => v.map(n => n * s);
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = v => mul(v, 1 / Math.hypot(...v));
const color = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
const C = Object.freeze({ gold: '#bb8a3f', lightGold: '#d6b66d', darkGold: '#79602f', silver: '#aeb5ae', grey: '#5c686a', black: '#151d24', glass: '#082a39', strut: '#d0ba83', white: '#e4e1ce' });

export function buildSpacecraftMesh() {
  const positions = [], normals = [], colors = [], lines = [], lineColors = [], ghostLines = [];
  const components = {};
  let part = '';
  const begin = name => { part = name; components[name] = { firstVertex: positions.length / 3, vertexCount: 0 }; };
  const line = (a, b, shade = '#776d50', ghost = false) => {
    lines.push(...a, ...b); const rgb = color(shade); lineColors.push(...rgb, ...rgb);
    if (ghost) ghostLines.push(...a, ...b);
  };
  const tri = (a, b, c, shade) => {
    const normal = cross(sub(b, a), sub(c, a));
    if (Math.hypot(...normal) < 1e-9) return;
    const n = unit(normal), rgb = color(shade);
    positions.push(...a, ...b, ...c); normals.push(...n, ...n, ...n); colors.push(...rgb, ...rgb, ...rgb);
    components[part].vertexCount += 3;
  };
  const face = (vertices, shade, outlined = false) => {
    for (let i = 1; i < vertices.length - 1; i++) tri(vertices[0], vertices[i], vertices[i + 1], shade);
    if (outlined) vertices.forEach((p, i) => line(p, vertices[(i + 1) % vertices.length], '#706750', true));
  };
  const ring = (up, radius, n = 8, offset = Math.PI / 8) => Array.from({ length: n }, (_, i) => [up, Math.cos(i * Math.PI * 2 / n + offset) * radius, Math.sin(i * Math.PI * 2 / n + offset) * radius]);
  const tube = (a, b, radius, shade, segments = 7, endRadius = radius, caps = true) => {
    const axis = unit(sub(b, a));
    const u = unit(cross(axis, Math.abs(axis[0]) < .8 ? [1, 0, 0] : [0, 1, 0]));
    const v = cross(axis, u);
    const rim = (center, r) => Array.from({ length: segments }, (_, i) => add(center, add(mul(u, Math.cos(i * Math.PI * 2 / segments) * r), mul(v, Math.sin(i * Math.PI * 2 / segments) * r))));
    const lo = rim(a, radius), hi = rim(b, endRadius);
    for (let i = 0; i < segments; i++) face([lo[i], lo[(i + 1) % segments], hi[(i + 1) % segments], hi[i]], shade);
    if (caps) { face(lo.slice().reverse(), shade); face(hi, shade); }
  };
  const box = (center, size, shade, outlined = false) => {
    const p = (a, b, c) => add(center, [a * size[0] / 2, b * size[1] / 2, c * size[2] / 2]);
    face([p(-1,-1,-1),p(-1,-1,1),p(-1,1,1),p(-1,1,-1)], shade, outlined);
    face([p(1,-1,-1),p(1,1,-1),p(1,1,1),p(1,-1,1)], shade, outlined);
    for (const s of [-1, 1]) {
      face([p(-1,s,-1),p(1,s,-1),p(1,s,1),p(-1,s,1)], shade, outlined);
      face([p(-1,-1,s),p(-1,1,s),p(1,1,s),p(1,-1,s)], shade, outlined);
    }
  };

  begin('descent-stage');
  const low = ring(-.66, 1.08), high = ring(.15, 1.08);
  const shades = ['#bf9548','#c8a154','#a47a33','#c19a4c','#9b7939','#b88b40','#e0b869','#b9914c'];
  face(low.slice().reverse(), C.darkGold); face(high, C.lightGold, true);
  for (let i = 0; i < 8; i++) {
    const next = (i + 1) % 8;
    const center = mul(add(add(low[i], low[next]), add(high[i], high[next])), .25);
    // Slightly raised, faceted foil produces real lighting rather than a texture.
    const raised = add(center, [0, center[1] * .025, center[2] * .025]);
    const border = [low[i], low[next], high[next], high[i]];
    border.forEach((p, j) => { tri(p, border[(j + 1) % 4], raised, shades[(i + j % 2) % shades.length]); });
    border.forEach((p, j) => line(p, border[(j + 1) % 4], '#e0b66b', true));
    for (let seam = 1; seam <= 3; seam++) {
      const amount = seam / 4;
      const a = add(mul(low[i], 1 - amount), mul(low[next], amount));
      const b = add(mul(high[i], 1 - amount), mul(high[next], amount));
      const crease = add(raised, [Math.sin(i + seam) * .12, 0, 0]);
      line(a, crease, '#715d37'); line(b, crease, '#cfac62');
    }
  }
  // Dark equipment blankets break up the octagonal gold platform.
  box([-.18,.92,0], [.49,.12,.52], C.black, true);
  box([-.17,-.92,0], [.51,.12,.52], C.black, true);

  begin('ascent-cabin');
  const crossSection = [[.72,.31],[.40,.66],[-.40,.66],[-.72,.31],[-.72,-.31],[-.40,-.66],[.40,-.66],[.72,-.31]];
  const cabinLow = crossSection.map(([x,z]) => [.29,x,z]);
  const cabinHigh = crossSection.map(([x,z]) => [1.28,x*.94,z*.97]);
  const cabinRoof = crossSection.map(([x,z]) => [1.58,x*.48,z*.49]);
  const cabinColors = ['#8a9698','#aeb8b6','#8b9799','#4b5d63','#24333c','#65777b','#a9b0aa','#607275'];
  for (let i = 0; i < 8; i++) {
    const n = (i + 1) % 8;
    face([cabinLow[i],cabinLow[n],cabinHigh[n],cabinHigh[i]], cabinColors[i], true);
    face([cabinHigh[i],cabinHigh[n],cabinRoof[n],cabinRoof[i]], i % 2 ? '#c5c9bd' : '#838e89', true);
    tube(high[i],cabinLow[i],.024,C.silver,5);
  }
  face(cabinRoof, C.silver, true);
  box([.77,.73,-.05],[.61,.14,.47],C.black,true);
  box([.77,-.73,-.05],[.61,.14,.47],C.black,true);
  // Rear ascent propulsion/equipment shroud, with no active engine depiction.
  tube([.5,0,-.61],[1.17,0,-.61],.37,C.grey,12,.32);

  begin('windows-and-hatch');
  const windowTriangle = sign => [[1.25,sign*.36,.650],[.86,sign*.36,.663],[.91,sign*.035,.663]];
  for (const sign of [-1,1]) {
    const vertices = windowTriangle(sign);
    face(vertices, C.glass, true);
    vertices.forEach((p,i) => tube(p, vertices[(i+1)%3],.018,'#d2d7ca',5));
    line(add(vertices[0],[0,-sign*.045,.005]), add(vertices[2],[.045,sign*.02,.005]), '#376477');
  }
  box([.55,0,.67],[.41,.39,.035],'#7d8986',true);
  box([.56,0,.694],[.31,.29,.012],'#424f54',true);
  tube([.56,-.08,.713],[.56,.08,.713],.014,C.white,5);
  box([.79,0,.676],[.04,.08,.012],C.black);

  begin('landing-gear');
  for (const sx of [-1,1]) for (const sz of [-1,1]) {
    const hip = [-.13,sx*.70,sz*.70], knee = [-.88,sx*1.25,sz*1.25], foot = [-1.51,sx*1.69,sz*1.69];
    tube(hip,foot,.045,C.strut,8); tube(hip,knee,.072,C.lightGold,8,.055);
    tube([-.57,sx*.85,sz*.35],knee,.028,C.silver,6);
    tube([-.57,sx*.35,sz*.85],knee,.028,C.silver,6);
    tube([-.48,sx*.68,-sz*.36],foot,.019,C.grey,5);
    const pad = ring(-1.55,.26,16,0).map(p => [p[0], p[1]+foot[1], p[2]+foot[2]]);
    const padTop = pad.map(p => add(p,[.045,0,0]));
    face(pad,C.darkGold); face(padTop,C.lightGold,true);
    for(let i=0;i<16;i++) face([pad[i],pad[(i+1)%16],padTop[(i+1)%16],padTop[i]],C.gold);
    line(hip,foot,C.lightGold,true);
    if (!(sx === -1 && sz === -1)) tube(add(foot,[.04,0,0]), add(foot,[-.65,.11*sx,.11*sz]),.009,C.silver,4);
  }

  begin('inert-descent-engine');
  tube([-.64,0,0],[-1.16,0,0],.18,'#586066',18,.37,false);
  const nozzle = ring(-1.17,.37,18,0);
  face(nozzle,'#080f16',true);
  for(let i=0;i<18;i+=3) line([-.68,Math.cos(i*Math.PI/9)*.18,Math.sin(i*Math.PI/9)*.18],nozzle[i],'#a3997d');

  begin('rcs-clusters');
  for(const sx of [-1,1]) for(const sz of [-1,1]) {
    const pod=[.82,sx*.91,sz*.65];
    tube([.82,sx*.66,sz*.45],pod,.027,C.silver,6);
    box(pod,[.19,.20,.19],C.lightGold,true);
    // Four unlit visual nozzles per pod. No placement-to-AGC-jet mapping is implied.
    for(const direction of [[1,0,0],[-1,0,0],[0,sx,0],[0,0,sz]]) {
      const a=add(pod,mul(direction,.12)),b=add(pod,mul(direction,.27));
      tube(a,b,.037,C.grey,8,.072,false);
      tube(add(b,mul(direction,-.003)),add(b,mul(direction,.002)),.062,C.black,8);
    }
  }

  begin('antennae-and-ladder');
  tube([1.53,0,0],[2.02,0,0],.016,C.silver,6);
  tube([1.99,-.31,0],[1.99,.31,0],.011,C.silver,5);
  tube([1.82,0,0],[1.99,.31,0],.009,C.silver,5);
  tube([1.38,-.35,-.32],[1.89,-.65,-.50],.013,C.silver,5);
  // Small parabolic high-gain antenna, built as a shallow segmented dish.
  const dishCenter=[1.87,-.65,-.50];
  const dishRim=Array.from({length:16},(_,i)=>add(dishCenter,[Math.sin(i*Math.PI/8)*.21,Math.cos(i*Math.PI/8)*.21,-.065]));
  for(let i=0;i<16;i++) tri(add(dishCenter,[0,0,.025]),dishRim[i],dishRim[(i+1)%16],i%2?'#9ca7a2':'#7c8a89');
  for(let i=0;i<16;i++)line(dishRim[i],dishRim[(i+1)%16],'#c0c9bc');
  tube(dishCenter,add(dishCenter,[0,0,-.19]),.008,C.silver,5);
  for(const x of [-.14,.14]) tube([.30,x,.77],[-1.25,x,1.55],.018,C.silver,5);
  for(let i=0;i<9;i++) tube([.24-i*.16,-.14,.80+i*.081],[.24-i*.16,.14,.80+i*.081],.014,C.white,5);
  // Flag-like thermal marking is merely a graphic detail on the descent stage.
  box([-.18,-.32,1.011],[.14,.25,.012],'#d8d5bd');
  box([-.145,-.39,1.019],[.07,.11,.012],'#52647b');
  for(let i=0;i<4;i++)box([-.13-i*.03,-.27,1.019],[.012,.15,.012],'#a36550');

  const bounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};
  for(let i=0;i<positions.length;i++){
    const axis=i%3;bounds.min[axis]=Math.min(bounds.min[axis],positions[i]);bounds.max[axis]=Math.max(bounds.max[axis],positions[i]);
  }
  return { positions:new Float32Array(positions), normals:new Float32Array(normals), colors:new Float32Array(colors),
    lines:new Float32Array(lines), lineColors:new Float32Array(lineColors), ghostLines:new Float32Array(ghostLines),
    components, bounds, units:'illustrative model units', bodyAxes:'[up, lateral, lateral]' };
}
