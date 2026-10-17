import { activeJets, frameAt, lastAt, octal, formatTime, originalReadiness, presentationQuaternion, rcsAt, validateReplay, wrappedDegrees } from './replay.mjs';
import { createSpacecraftRenderer } from './spacecraft.mjs';
import { LiveClient, canPilot, liveSample } from './live.mjs';

const $ = id => document.getElementById(id);
const renderer = createSpacecraftRenderer($('spacecraft'));
const state = { data: null, mode:'replay', axis: 'combined', feedback: true, time: 31, playing: false, speed: 1, compare: false, axes: true, fullChart: false };
const liveCase={id:'live',title:'Live native yaw/pitch session',frames:[],rcsEvents:[],checkpoints:[],durationSeconds:37.5,source:{rawSha256:null}};
let liveFrame=null, liveState={status:'idle',sessionId:null,frame:null}, replayTime=31;
const byId = id => state.data?.cases.find(item => item.id === id);
const current = () => state.mode==='live' ? liveCase : byId(`${state.axis}${state.feedback ? '' : '_off'}`);
const announce = text => { $('announcement').textContent = text; };
const signed = n => `${n < 0 ? '−' : n > 0 ? '+' : ''}${Math.abs(n).toFixed(3)}`;
let dragging = null;
const live = new LiveClient((update,reset)=>{
  liveState=update;
  if(reset){liveCase.frames=[];liveFrame=null;$('live-error').hidden=true;}
  try {
    liveFrame=liveSample(update.frame);
    if(liveFrame&&(!liveCase.frames.length||liveFrame.cycle>liveCase.frames.at(-1).cycle))liveCase.frames.push(liveFrame);
  } catch(error){live.release(true);showLiveError(error.message);}
  updateLiveControls();
  if(state.mode==='live'){state.time=liveFrame?.t||0;render();}
},showLiveError);

function showLiveError(message){$('live-error').textContent=message;$('live-error').hidden=false;}
function updateLiveControls(){
  const enabled=canPilot(liveState);
  document.querySelectorAll('[data-pilot]').forEach(button=>{button.disabled=!enabled;button.classList.toggle('pressed',live.held.has(button.dataset.pilot));});
  $('live-neutral').disabled=!enabled;
  $('live-start').disabled=['initializing','ready','running','stopping'].includes(liveState.status);
  $('live-stop').disabled=!['initializing','ready','running','disconnected'].includes(liveState.status);
  $('live-download').disabled=!liveState.sessionId;
  $('live-start').textContent=['stopped','fault'].includes(liveState.status)?'Start new run':'Start live AGC';
  $('live-status').textContent=liveState.message||'Start a fresh native AGC session.';
  $('live-remaining').textContent=liveState.frame?`${Math.max(0,liveState.frame.remaining_time).toFixed(1)} s remaining`:'11.7 s bounded run';
  const applied=liveState.frame?.control;
  $('live-input-state').textContent=applied?`RHC input: yaw ${applied.yaw*20}, pitch ${applied.pitch*20} counts · interface #${liveState.appliedSequence}`:'Only original AGC outputs drive the vehicle.';
  if(state.mode==='live')$('mode-badge').innerHTML=`<span class="status-dot"></span> LIVE · ${liveState.status==='ready'?'READY / PAUSED':liveState.status.toUpperCase()}`;
}
function setMode(mode){
  if(mode===state.mode)return;
  if(mode==='live'){replayTime=state.time;setPlaying(false);}
  else{live.stop();state.time=replayTime;}
  state.mode=mode;document.body.dataset.console=mode;
  document.querySelectorAll('[data-mode]').forEach(button=>{const active=button.dataset.mode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  $('live-controls').hidden=mode!=='live';$('replay-options').hidden=mode==='live';$('replay-transport').hidden=mode==='live';
  $('compare-button').hidden=mode==='live';$('comparison-key').hidden=mode==='live'||!state.compare;
  $('mode-description').textContent=mode==='live'?'Original Luminary · live backend · attitude only':'Verified Phase 7 recordings';
  $('mode-badge').classList.toggle('live',mode==='live');
  $('mode-badge').innerHTML=`<span class="status-dot"></span> ${mode==='live'?'LIVE NATIVE AGC':'RECORDED NATIVE RUN'}`;
  $('view-mode-label').textContent=mode==='live'?'LIVE ATTITUDE SESSION':'ATTITUDE REPLAY';
  $('spacecraft').setAttribute('aria-label',`Illustrative lunar module oriented by ${mode==='live'?'live backend':'recorded'} quaternion samples. No translation or descent is simulated.`);
  $('output-caption').textContent=mode==='live'?'Actual native output latches · sampled':'Recorded output words · read-only';
  $('footer-source').textContent=mode==='live'?'Simulated physics. Live original software.':'Simulated physics. Recorded evidence.';
  $('chart-window').textContent=state.fullChart?'FULL RUN ↔':mode==='live'?'LIVE WINDOW ↔':'CONTROL WINDOW ↔';
  if(mode==='live'){state.time=liveFrame?.t||0;updateLiveControls();}else if(state.data)selectExperiment(state.axis,state.feedback);
  render();announce(mode==='live'?'Live mode. Start a native session to enable pilot inputs.':'Recorded replay mode.');
}

function setPlaying(value) {
  if (!state.data) return;
  if (value && state.time >= current().durationSeconds) state.time = 0;
  state.playing = value;
  $('play-button').innerHTML = `<svg><use href="#i-${value ? 'pause' : 'play'}"/></svg><span>${value ? 'Pause' : 'Play replay'}</span>`;
  $('play-button').setAttribute('aria-label', value ? 'Pause replay' : 'Play replay');
}

function selectExperiment(axis, feedback = state.feedback) {
  state.axis = axis;
  state.feedback = axis === 'yaw' ? true : feedback;
  const c = current();
  state.time = Math.min(state.time, c.durationSeconds);
  if (axis === 'yaw') state.compare = false;
  document.querySelectorAll('[data-axis]').forEach(button => {
    const active = button.dataset.axis === axis;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  $('feedback-toggle').setAttribute('aria-checked', String(state.feedback));
  $('feedback-toggle').disabled = axis === 'yaw';
  $('feedback-toggle').title = axis === 'yaw' ? 'The exported yaw baseline has connected feedback only.' : 'Switch between actual connected and disconnected experiments';
  $('feedback-label').textContent = state.feedback ? 'Connected' : 'Disconnected';
  $('feedback-label').style.color = state.feedback ? 'var(--green)' : 'var(--gold)';
  $('compare-button').disabled = axis === 'yaw';
  $('compare-button').setAttribute('aria-pressed', String(state.compare));
  $('comparison-key').hidden = !state.compare;
  $('comparison-key').innerHTML = `<i class="comparison"></i>${state.feedback ? 'Disconnected' : 'Connected'}`;
  $('scrubber').max = c.durationSeconds;
  $('time-duration').textContent = formatTime(c.durationSeconds);
  $('timeline-end').textContent = `T + ${formatTime(c.durationSeconds).slice(0, 7)}`;
  document.querySelector('.input-marker').style.left = `${29.296875 / c.durationSeconds * 100}%`;
  document.querySelector('.neutral-marker').style.left = `${31.640625 / c.durationSeconds * 100}%`;
  $('sensor-dot').style.background = state.feedback ? 'var(--green)' : 'var(--gold)';
  $('sensor-message').textContent = state.feedback ? 'Measurements returned to the AGC' : 'Measurements recorded · feedback omitted';
  announce(`${c.title}. ${state.feedback ? 'Sensor feedback connected.' : 'Sensor feedback disconnected.'}`);
  render();
}

function render() {
  const c = current();
  if (!c) { renderer.draw([1,0,0,0], 0, true); return; }
  const isLive=state.mode==='live';
  const frame = isLive?liveFrame:frameAt(c, state.time);
  const words = isLive?(liveState.frame?.actual_output_jets||{5:null,6:null}):rcsAt(c, state.time);
  const jets = activeJets(words);
  renderer.draw(isLive?(frame?.q||[1,0,0,0]):presentationQuaternion(c, state.time), state.time, isLive||state.feedback);
  const rates = frame?.omega;
  for (const [i, id] of ['yaw-value', 'pitch-value', 'roll-value'].entries()) {
    $(id).innerHTML = `${rates ? signed(rates[i]) : '—'}<small>°/s</small>`;
  }
  const checkpoint = frame?.readiness || lastAt(c.checkpoints.filter(item => item.modreg != null), state.time);
  const modreg = checkpoint?.modreg;
  $('program-value').textContent = Number.isInteger(modreg) && modreg >= 0 && modreg <= 99 ? String(modreg).padStart(2, '0') : '— —';
  const readiness = originalReadiness(checkpoint);
  $('readiness-state').textContent = isLive?(!checkpoint?'Awaiting native startup':canPilot(liveState)?'Original readiness observed':`Session ${liveState.status}`):!checkpoint ? 'Awaiting recorded checkpoint' : readiness ? 'Original readiness observed' : 'Recorded startup checkpoint';
  $('channel5').textContent = octal(words[5]);
  $('channel6').textContent = octal(words[6]);
  $('jet-count').textContent = `${words[5] == null || words[6] == null ? '—' : jets.filter(j => j.active).length} / 16`;
  jets.forEach(jet => {
    const cell = $(`jet-${jet.name}`);
    cell.classList.toggle('active', Boolean(jet.active));
    cell.title = `${jet.name} · channel 00${jet.channel}, bit ${jet.bit} · ${jet.active == null ? 'not yet observed' : jet.active ? 'commanded on' : 'off'}`;
    cell.setAttribute('aria-label', cell.title);
  });
  for (const [i, id] of ['gimbal-o', 'gimbal-i', 'gimbal-m'].entries()) $(id).textContent = frame ? `${signed(wrappedDegrees(frame.gimbals[i]))}°` : '—';
  const counters = frame?.cdu;
  for (const [i, id] of ['cdu-x','cdu-y','cdu-z'].entries()) $(id).textContent = Array.isArray(counters) ? String(counters[i]).padStart(5, '0') : '—';
  $('sample-time').textContent = isLive?(frame?`Model ${formatTime(frame.t)} · CPU ${frame.cpuCycle}`:'Waiting for native telemetry'):frame ? `Recorded sample · ${formatTime(frame.t)}` : 'No model sample at this time';
  if(isLive){$('sensor-message').textContent='Actual CDU counters · live native CPU';$('sensor-dot').style.background='var(--green)';}
  $('time-current').textContent = formatTime(state.time);
  $('scrubber').value = state.time;
  $('scrubber').style.setProperty('--progress', `${state.time / c.durationSeconds * 100}%`);
  $('scrubber').setAttribute('aria-valuetext', `${state.time.toFixed(3)} seconds of ${c.durationSeconds} seconds`);
  $('replay-state').textContent = state.time >= c.durationSeconds ? 'PHYSICS CUTOFF' : state.playing ? 'REPLAYING RECORDING' : 'RECORDED REPLAY';
  drawChart(c);
}

function drawChart(c) {
  const canvas = $('rate-chart');
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  if (canvas.width !== Math.round(width*dpr) || canvas.height !== Math.round(height*dpr)) {canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
  const compare = state.mode==='replay'&&state.compare ? byId(`${state.axis}${state.feedback ? '_off' : ''}`) : null;
  let magnitude = 0.1;
  for (const source of [c,compare].filter(Boolean)) for (const frame of source.frames) magnitude = Math.max(magnitude,...frame.omega.map(Math.abs));
  const max = magnitude <= 5 ? 5 : Math.ceil(magnitude / 5) * 5;
  const left=33,right=12,top=7,bottom=22,w=width-left-right,h=height-top-bottom;
  const start = state.fullChart ? 0 : state.mode==='live'?25.78125:28;
  const x = t => left + (t-start)/(c.durationSeconds-start)*w;
  const y = n => top + (max-n)/(2*max)*h;
  ctx.font='7px monospace';ctx.textAlign='right';ctx.textBaseline='middle';
  for (const value of [-max,-max/2,0,max/2,max]) {
    ctx.strokeStyle=value===0?'#53654677':'#35432e88';ctx.lineWidth=.6;
    ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(width-right,y(value));ctx.stroke();
    ctx.fillStyle='#879a76';ctx.fillText(`${value>0?'+':''}${value}`,left-7,y(value));
  }
  ctx.textAlign='center';ctx.textBaseline='top';
  const tick = state.fullChart ? 10 : c.durationSeconds>40 ? 5 : 2;
  for(let t=Math.ceil(start/tick)*tick;t<c.durationSeconds-1;t+=tick){ctx.strokeStyle='#35432e66';ctx.beginPath();ctx.moveTo(x(t),top);ctx.lineTo(x(t),height-bottom);ctx.stroke();ctx.fillStyle='#748b63';ctx.fillText(`${t}s`,x(t),height-bottom+8);}
  ctx.fillStyle='#748b63';ctx.textAlign='right';ctx.fillText(`${c.durationSeconds.toFixed(1)}s`,width-right,height-bottom+8);
  const colors=['#d5ae75','#94bfb0','#899bb4'];
  function trace(source,dashed){
    ctx.save();ctx.beginPath();ctx.rect(left,top,w,h);ctx.clip();
    for(let axis=0;axis<3;axis++){
      ctx.strokeStyle=colors[axis];ctx.globalAlpha=dashed ? .4 : .95;ctx.lineWidth=dashed?1:1.4;ctx.setLineDash(dashed?[3,4]:[]);ctx.beginPath();
      source.frames.forEach((f,i)=>i?ctx.lineTo(x(f.t),y(f.omega[axis])):ctx.moveTo(x(f.t),y(f.omega[axis])));ctx.stroke();
    }ctx.restore();
  }
  if(compare)trace(compare,true);trace(c,false);
  const inputTimes=state.mode==='live'?(liveState.frame?.events||[]).filter(e=>e.ev==='pilot_command'||e.ev==='neutral').map(e=>e.cycle*12/1024000):[29.296875,31.640625];
  for(const time of inputTimes){ctx.strokeStyle='#909d6155';ctx.lineWidth=.6;ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(x(time),top);ctx.lineTo(x(time),height-bottom);ctx.stroke();ctx.setLineDash([]);}
  ctx.strokeStyle='#e5d5af88';ctx.lineWidth=.8;ctx.beginPath();if(state.time>=start){ctx.moveTo(x(state.time),top);ctx.lineTo(x(state.time),height-bottom);}ctx.stroke();
  const frame=frameAt(c,state.time);
  if(frame&&state.time>=start)frame.omega.forEach((value,i)=>{ctx.fillStyle=colors[i];ctx.beginPath();ctx.arc(x(state.time),y(value),2,0,Math.PI*2);ctx.fill();});
  canvas.setAttribute('aria-label',`${state.mode==='live'?'Live sampled':'Recorded'} angular rates from ${start} to ${c.durationSeconds} seconds${compare ? ', comparing connected and disconnected feedback' : ''}`);
}

function openDialog(kind) {
  const c = current();
  if(state.mode==='live')live.release(true);
  if(state.mode==='live'&&kind!=='frames'){
    const details={
      brief:['Pilot the original guidance software.', '<p>Start a fresh native session. The backend verifies pinned sources and runs the original startup until P00, clear IMU inhibition, ACCSOKAY and alarm readbacks agree. The CPU then pauses until your first deflection.</p><p>Hold yaw and pitch controls with the mouse, touch or <strong>A/D and W/S</strong>. The browser sends only bounded controller directions. The backend presents source-verified ±20 RHC counts through ports <code>0167 / 0166</code> and active-low channel <code>031</code>. Original channel <code>013</code> gating delivers those counts to Luminary.</p><p>Actual native RCS outputs drive the retained modern vehicle model; real counter-operation packets return the resulting IMU measurements. The browser never writes orientation, rates or actuator outputs.</p><p class="dialog-note">This is the bounded Phase 7 attitude fixture: about 11.7 seconds after readiness, synthetic mass properties and ideal alignment. Powered descent, a calibrated flight vehicle and a complete landing are unimplemented.</p>'],
      help:['Live controls and automatic neutral.', '<p>Hold <strong>A/D for yaw</strong>, <strong>W/S for pitch</strong>, or the on-screen buttons. Two different axes may be held together. Opposing inputs on the same axis cancel to neutral.</p><p>Release, blur, hidden tab and pointer cancellation clear the controls. The server expires unrefreshed deflections within 0.5 simulated seconds and also checks wall-clock freshness. An input queued too long is discarded.</p><p>The original software decides the RCS response. Neutralizing the controller does not instantly stop a rotating vehicle. Use <strong>Stop run</strong> to freeze the bounded experiment and drain queued sensors. Use <strong>Start new run</strong> for a genuine fresh initialization.</p><p>Live values are backend samples, not browser predictions. Model time and CPU time are shown separately because sensor service and the final drain can lag or outlive physical integration. Dragging the illustration changes the camera only.</p>'],
      evidence:['A new trace for each live session.', '<p>Each session creates new raw traces under <code>.build/live/sessions/</code>, with original AGC outputs, applied RHC inputs, source/runtime hashes, body dynamics and every generated, delivered, enqueued and applied CDU operation.</p><p>The gateway separately records HTTP intent, sequence acknowledgements, cancellations, expiry and actual input application. HTTP acceptance alone is not evidence that Luminary has sampled an input; the native trace observes the original RHC read gate.</p><p>Earlier Phase 1–7 and replay evidence stays unchanged. New validation includes both signs on each axis and exact repeated native runs.</p><p class="dialog-note">Stop and queue settlement are distinct from attitude equilibrium. Failed or unsupported sessions remain failed, retain their logs and cannot be presented as verified control.</p><button class="download-button" id="download-live-record"><svg><use href="#i-download"/></svg> Download current live record</button>']
    };
    const [title,html]=details[kind]||details.help;
    $('dialog-title').textContent=title;$('dialog-content').innerHTML=html;$('detail-dialog').showModal();
    $('download-live-record')?.addEventListener('click',()=>live.download().catch(error=>showLiveError(error.message)));
    return;
  }
  const contents = {
    brief: ['A real computer. A measurable response.', `<p>This demo replays the verified <strong>Phase 7 attitude-control experiments</strong>. Original Apollo Lunar Module software, Luminary 099, ran through the pinned Virtual AGC emulator and produced actual RCS channel outputs.</p><p>Those commands drove a modern rotational model. Simulated IMU/CDU measurements returned through real emulator counter operations, changing subsequent flight-software commands.</p><ol><li><strong>Yaw and pitch:</strong> independently verified, then demonstrated simultaneously.</li><li><strong>Feedback controls:</strong> switch the sensor connection or compare traces to see why the returned measurements matter.</li><li><strong>Exact replays:</strong> repeated pitch and combined runs reproduced their raw trace bytes.</li></ol><p class="dialog-note">Capability C: bounded simultaneous two-axis feedback. Full independent three-axis control and sustained stability remain unverified. Descent propulsion, altitude, trajectory and landing are not demonstrated.</p><p>The vehicle geometry is illustrative. Inertia and torque arms are synthetic. This is generated experimental telemetry, not historical Apollo 11 flight data.</p>`],
    help: ['Explore the experiment.', `<p>Choose an experiment, then play or scrub its recorded timeline. The default position starts during the rate-controller input, with the full startup sequence available to the left. The chart starts at 28 seconds; toggle its window to see the full run.</p><div class="keyboard-row"><kbd>Space</kbd> Play / pause</div><div class="keyboard-row"><kbd>← / →</kbd> Move by 0.5 seconds</div><div class="keyboard-row"><kbd>R</kbd> Restart from the beginning</div><div class="keyboard-row"><kbd>Esc</kbd> Close details</div><p><strong>Drag the spacecraft view</strong> to orbit the camera. This changes your viewpoint, never the recorded vehicle state. Use the grid button to toggle body axes.</p><p>Numeric readouts hold actual captured samples, around 10 Hz. Quaternion interpolation smooths the illustration only. RCS indicators use exact recorded output-event times.</p><p>Feedback switches between separate native experiments; it does not change a running AGC. The yaw export has no disconnected case. Playback ends at the documented physics cutoff.</p>`],
    frames: ['Body axes ≠ sensor gimbals.', `<p>The recorded quaternion is scalar-first <code>[w, x, y, z]</code>, rotating vectors from the body frame to the stable frame. The renderer applies that rotation before its camera projection.</p><ul><li><strong>P / body X = yaw</strong></li><li><strong>Q / body Y = pitch</strong></li><li><strong>R / body Z = roll</strong></li></ul><p>The IMU measurements describe <strong>outer O, inner I and middle M</strong> gimbals: <code>C = Ry(I) Rz(M) Rx(O)</code>. Their angles are distinct from body Euler angles after compound rotation.</p><p>CDUX/Y/Z counters are <code>032 / 033 / 034</code> octal. Displayed counters are actual recorded emulator values. Unknown values remain blank.</p><p>Jet names follow the pinned source. Channel 005 selections can affect both pitch and roll; channel 006 carries P/yaw selections. Illustrative nozzle locations are deliberately not used to imply validated thruster geometry.</p>`],
    evidence: ['A trace behind every readout.', `<p><strong>Source:</strong> recorded native Phase 7 runs with original Luminary 099, unchanged instruction semantics, and source-locked external physics. No guidance controller runs in this page.</p><p>Final validation: <strong>39 Phase 7 tests and 136 prior milestone tests passed.</strong> Historical suites separately retain 35 passes and 3 known missing-log errors. Earlier evidence was preserved.</p><div class="provenance-list"><p>Current experiment<br><code>${c?.title || 'Loading'}</code></p><p>Raw trace SHA-256<br><code>${c?.source.rawSha256 || 'Unavailable'}</code></p><p>Base repository revision<br><code>${state.data?.provenance.sourceRevision || 'Unavailable'}</code></p><p>Emulator revision<br><code>${state.data?.provenance.emulatorRevision || 'Unavailable'}</code></p></div><p class="dialog-note">Empty sensor queues establish transport settlement, not equilibrium. The combined run still has approximately +1.324°/s pitch rate at cutoff. The illustration freezes with the recorded physics.</p><button class="download-button" id="download-record"><svg><use href="#i-download"/></svg> Download experiment record</button><p>The download includes exported samples, authentic RCS edges, source hashes and scope notes. The complete raw traces and report remain in the repository under <code>docs/phase7-evidence/</code>.</p>`],
  };
  const [title, html] = contents[kind] || contents.help;
  $('dialog-title').textContent = title;
  $('dialog-content').innerHTML = html;
  $('detail-dialog').showModal();
  $('download-record')?.addEventListener('click', () => {
    const record = { provenance:state.data.provenance, labels:state.data.labels, experiment:c };
    const url = URL.createObjectURL(new Blob([JSON.stringify(record,null,2)], {type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`apollo11-${c.id}-record.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}

async function load() {
  $('load-error').hidden=true;$('loading').hidden=false;
  try {
    const response = await fetch('./data/replay.json');
    if(!response.ok)throw new Error(`Data request failed (${response.status}).`);
    state.data=validateReplay(await response.json());
    $('loading').hidden=true;$('play-button').disabled=false;$('scrubber').disabled=false;
    if(state.mode==='replay')selectExperiment('combined',true);
    announce('Verified Phase 7 replay loaded. Press Play replay to begin.');
  } catch(error) {
    $('loading').hidden=true;$('load-error').hidden=false;$('error-detail').textContent=error.message;
    $('play-button').disabled=true;$('scrubber').disabled=true;console.error(error);
  }
}

activeJets({5:0,6:0}).forEach(jet=>{
  const cell=document.createElement('span');cell.className='jet';cell.id=`jet-${jet.name}`;
  cell.innerHTML=`<span class="small-led"></span>${jet.name}`;$('jet-grid').append(cell);
});
document.querySelectorAll('[data-axis]').forEach(button=>button.addEventListener('click',()=>{if(state.data)selectExperiment(button.dataset.axis);}));
$('feedback-toggle').addEventListener('click',()=>{if(state.data)selectExperiment(state.axis,!state.feedback);});
$('compare-button').addEventListener('click',()=>{if(!state.data)return;state.compare=!state.compare;$('compare-button').setAttribute('aria-pressed',String(state.compare));$('comparison-key').hidden=!state.compare;render();});
$('chart-window').addEventListener('click',()=>{state.fullChart=!state.fullChart;$('chart-window').textContent=state.fullChart ? 'FULL RUN ↔' : 'CONTROL WINDOW ↔';$('chart-window').setAttribute('aria-pressed',String(state.fullChart));render();});
$('play-button').addEventListener('click',()=>{setPlaying(!state.playing);render();});
$('restart-button').addEventListener('click',()=>{state.time=0;setPlaying(false);render();announce('Replay returned to the start.');});
$('speed').addEventListener('change',event=>{state.speed=Number(event.target.value);});
$('scrubber').addEventListener('input',event=>{state.time=Number(event.target.value);render();});
$('axes-toggle').addEventListener('click',()=>{state.axes=!state.axes;renderer.setAxes(state.axes);$('axes-toggle').classList.toggle('active',state.axes);$('axes-toggle').setAttribute('aria-pressed',String(state.axes));render();});
$('camera-reset').addEventListener('click',()=>{renderer.reset();render();});
$('retry-button').addEventListener('click',load);
document.querySelectorAll('[data-dialog]').forEach(button=>button.addEventListener('click',()=>openDialog(button.dataset.dialog)));
document.querySelector('.rail-button.selected').addEventListener('click',()=>{$('main').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
$('close-dialog').addEventListener('click',()=>$('detail-dialog').close());
$('detail-dialog').addEventListener('click',event=>{if(event.target===$('detail-dialog')){const r=$('detail-dialog').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('detail-dialog').close();}});
$('viewport').addEventListener('pointerdown',event=>{if(event.target.closest('button'))return;dragging={x:event.clientX,y:event.clientY};$('viewport').setPointerCapture(event.pointerId);});
$('viewport').addEventListener('pointermove',event=>{if(!dragging)return;renderer.orbit(event.clientX-dragging.x,event.clientY-dragging.y);dragging={x:event.clientX,y:event.clientY};render();});
for(const type of ['pointerup','pointercancel'])$('viewport').addEventListener(type,()=>{dragging=null;});
document.addEventListener('keydown',event=>{
  if(state.mode==='live'||!state.data||$('detail-dialog').open||event.ctrlKey||event.metaKey||event.altKey||event.target.matches('input,select,textarea,button'))return;
  if(event.code==='Space'){event.preventDefault();setPlaying(!state.playing);render();}
  if(event.code==='ArrowLeft'||event.code==='ArrowRight'){event.preventDefault();state.time=Math.max(0,Math.min(current().durationSeconds,state.time+(event.code==='ArrowRight' ? .5 : -.5)));render();}
  if(event.code==='KeyR'){state.time=0;setPlaying(false);render();}
});
window.addEventListener('resize',render);
document.addEventListener('visibilitychange',()=>{if(document.hidden){setPlaying(false);render();}});
let previous=performance.now();
function tick(now){const delta=Math.min(.1,(now-previous)/1000);previous=now;if(state.playing&&state.data&&!$('detail-dialog').open){state.time=Math.min(current().durationSeconds,state.time+delta*state.speed);if(state.time>=current().durationSeconds)setPlaying(false);render();}requestAnimationFrame(tick);}
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.mode)));
$('live-start').addEventListener('click',()=>live.start());
$('live-stop').addEventListener('click',()=>live.stop());
$('live-neutral').addEventListener('click',()=>{live.release(true);updateLiveControls();});
$('live-download').addEventListener('click',()=>live.download().catch(error=>showLiveError(error.message)));
document.querySelectorAll('[data-pilot]').forEach(button=>{
  button.addEventListener('pointerdown',event=>{if(!canPilot(liveState))return;event.preventDefault();button.setPointerCapture(event.pointerId);live.hold(button.dataset.pilot,`pointer-${event.pointerId}`);updateLiveControls();});
  const release=event=>{live.lift(`pointer-${event.pointerId}`);updateLiveControls();};
  button.addEventListener('pointerup',release);button.addEventListener('pointercancel',release);button.addEventListener('lostpointercapture',release);
  button.addEventListener('keydown',event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();if(!event.repeat)live.hold(button.dataset.pilot,`button-${event.code}`);updateLiveControls();}});
  button.addEventListener('keyup',event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();live.lift(`button-${event.code}`);updateLiveControls();}});
});
const pilotKeys={KeyA:'yaw-',KeyD:'yaw+',KeyW:'pitch+',KeyS:'pitch-'};
document.addEventListener('keydown',event=>{if(state.mode!=='live'||$('detail-dialog').open||event.ctrlKey||event.metaKey||event.altKey||event.target.matches('input,select,textarea'))return;const key=pilotKeys[event.code];if(key){event.preventDefault();if(!event.repeat)live.hold(key,`key-${event.code}`);updateLiveControls();}});
document.addEventListener('keyup',event=>{if(state.mode==='live'&&pilotKeys[event.code]){live.lift(`key-${event.code}`);updateLiveControls();}});
window.addEventListener('blur',()=>{live.release(true);updateLiveControls();});
document.addEventListener('visibilitychange',()=>{if(document.hidden){live.release(true);updateLiveControls();}});
window.addEventListener('pagehide',()=>{live.release(true);});
render();requestAnimationFrame(tick);load();
