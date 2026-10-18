import { LiveClient, canPilot, heldDirection } from './live.mjs';
import { activeJets } from './replay.mjs';
import { createFlightRenderer } from './spacecraft-3d.mjs';
import { CHALLENGES, createGameState, resetGame, updateGame, notePilotInput, finishGame } from './game-state.mjs';
import { labControlGuidance, stickDirections } from './control-guidance.mjs';

const $ = id => document.getElementById(id);
const text = (id, value) => { $(id).textContent = value; };
const finite = value => Number.isFinite(value);
const signed = value => finite(value) ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(2)}` : '—';
let game = createGameState({ challenge:'yaw' });
let session = { status:'idle', sessionId:null, frame:null };
let available = false, starting = false, controlError = false, stopRequested = false, lastResult = null;
let renderer = null, lastOrientation = null, lastTrustedFrame = null;
let drawPending = false;
let stickPointer=null;
const announce = value => text('flight-announcement', value);
const activeSession = () => ['initializing','ready','running','stopping'].includes(session.status);
const pilotEnabled = () => available && !controlError && canPilot(session) && ['await-input','running'].includes(game.phase);
const live = new LiveClient(receive, showError);

try { renderer = createFlightRenderer($('flight-canvas')); }
catch (error) { showError(`3D graphics unavailable: ${error.message}`); }

function quantity(id, value, unit, precision=2) {
  const node = $(id);
  node.replaceChildren(document.createTextNode(finite(value) ? value.toFixed(precision) : '—'));
  const small = document.createElement('small'); small.textContent = unit; node.append(small);
}
function draw() {
  drawPending = false;
  if (!renderer) return;
  // Before arming this is a clearly labeled visual model, not simulated state.
  renderer.draw({ quaternion:lastOrientation ?? [1,0,0,0],
    targetQuaternion:game.target?.q ?? null,
    available:true, aimErrorDeg:game.metrics?.errorDeg });
  text('render-mode', renderer.kind.toUpperCase());
}
function requestDraw() { if (!drawPending) { drawPending = true; requestAnimationFrame(draw); } }

function showError(message) {
  starting = false; controlError = true;
  text('flight-error-copy', message); $('flight-error').hidden = false;
  live?.release(true);
  if (['await-input','running'].includes(game.phase)) game = finishGame(game,'Control connection interrupted. No further training achievement is awarded.');
  render();
}
function receive(update, reset) {
  session = update; starting = false;
  if (reset) { stopRequested = false; lastResult = null; lastOrientation = null; lastTrustedFrame = null; }
  game = updateGame(game,{...update,mode:'live'});
  const q = update.frame?.model?.quaternion;
  if (game.phase!=='unavailable' && Array.isArray(q) && q.length === 4 && q.every(finite) && Math.abs(Math.hypot(...q)-1)<1e-6) { lastOrientation = q.slice(); lastTrustedFrame = update.frame; }
  if (game.phase==='unavailable' && !controlError) showError(game.message);
  if (['fault','disconnected'].includes(update.status)) {
    controlError = true; text('flight-error-copy',update.message || 'Live session unavailable.'); $('flight-error').hidden=false;
  }
  if (game.phase === 'result' && !lastResult) {
    lastResult = game.result;
    announce(game.result.outcome === 'success' ? 'Training target acquired in live samples. Run ending.' : 'Training run complete. Review your result.');
  }
  render();
  if (game.result?.outcome === 'success' && !stopRequested && ['ready','running'].includes(update.status)) {
    stopRequested = true; live.stop();
  }
}
function render() {
  const enabled = pilotEnabled();
  const status = starting ? 'initializing' : session.status;
  const m = game.metrics;
  const hasSample = Boolean(lastOrientation);
  const stale = controlError || game.phase==='unavailable' || ['fault','disconnected'].includes(status);
  const mode = available ? stale ? 'LIVE AGC · LAST SAMPLE' : activeSession() ? 'LIVE AGC EXECUTION' : hasSample ? 'LIVE RUN · ENDED' : 'LOCAL AGC · STANDBY' : 'LIVE SERVICE UNAVAILABLE';
  text('backend-mode',mode); $('source-dot').classList.toggle('live',available && !stale && hasSample);
  text('session-status',starting ? 'Verifying sources and starting original Luminary…' : session.message || (available ? 'Arm the AGC to begin a new training run.' : 'Start the live server to play. The model viewer remains available.'));
  text('observation-kind',hasSample ? stale ? 'LAST SAMPLE' : game.result ? 'SCORED SAMPLE' : 'BACKEND STATE' : 'NO LIVE SAMPLE');
  text('visual-source',hasSample ? stale ? 'LAST BACKEND QUATERNION · CONTROLS RELEASED' : activeSession() ? 'LIVE BACKEND ORIENTATION · POSITION FIXED' : 'FINAL BACKEND ORIENTATION · POSITION FIXED' : 'VISUAL MODEL · AWAITING LIVE STATE');
  $('stage-message').hidden = hasSample && game.phase !== 'await-input' && status !== 'initializing';
  if (!$('stage-message').hidden) {
    $('stage-message').querySelector('h2').textContent = !available ? 'Start the live service.' : status === 'initializing' ? 'Waking the computer.' : game.phase === 'await-input' ? 'You have the controls.' : 'Ready when you are.';
    $('stage-message').querySelector('p').textContent = !available ? 'Run make play from the repository root to enable the separate live lab. You can still explore the visual model.' : status === 'initializing' ? 'The pinned engine is executing original startup. Controls unlock only after the readiness checks pass.' : game.phase === 'await-input' ? 'The target marker shows relative rotation: right is positive yaw; up is positive pitch. Deflect the modern yaw/pitch lab pad briefly; it is not an Apollo ACA. Your first deflection starts the clock.' : 'Arm the separate synthetic lab. This exercise is not a historical mission procedure.';
  }
  quantity('time-remaining',m?.remainingSeconds,'s');
  quantity('angle-error',m?.errorDeg,'°'); quantity('rotation-rate',m?.rateDegS,'°/s');
  text('angle-rule',`Get within ${game.config.toleranceDeg}° of the target`);
  text('rate-rule',`Reduce total rate below ${game.config.maxRateDegS}°/s`);
  $('angle-error').closest('.instrument').classList.toggle('good',finite(m?.errorDeg) && m.errorDeg<=game.config.toleranceDeg);
  $('rotation-rate').closest('.instrument').classList.toggle('good',finite(m?.rateDegS) && m.rateDegS<=game.config.maxRateDegS);
  text('hold-label',`${Math.min(m?.holdSeconds ?? 0,game.config.holdSeconds).toFixed(1)} / ${game.config.holdSeconds.toFixed(1)} s`);
  $('hold-progress').style.width = `${Math.min(100,(m?.holdSeconds ?? 0)/game.config.holdSeconds*100)}%`;
  $('time-progress').style.width = `${Math.max(0,Math.min(100,(m?.remainingSeconds ?? 0)/11.71875*100))}%`;
  text('hold-hint',game.phase==='await-input' ? 'Waiting for your first input.' : game.result?.outcome==='success' ? 'Target hold observed in actual samples.' : game.insideTarget ? 'On target. Keep your rotation low.' : 'Match the attitude and slow down.');
  text('current-score',m && game.phase!=='await-input' ? String(m.score).padStart(3,'0') : '—');
  text('best-score',game.bestScore===null ? 'No completed target holds' : `Best acquired · ${game.bestScore}`);
  const frame = stale ? lastTrustedFrame : session.frame;
  text('agc-program',Number.isInteger(frame?.execution?.modreg) && frame.execution.modreg>=0 && frame.execution.modreg<100 ? String(frame.execution.modreg).padStart(2,'0') : '—');
  let jets = null;
  if (frame?.actual_output_jets) jets = activeJets(frame.actual_output_jets).filter(jet=>jet.active).length;
  text('jet-count',jets===null ? '—' : `${jets} / 16`);
  text('yaw-rate',`${signed(frame?.model?.omega?.[0])} °/s`);text('pitch-rate',`${signed(frame?.model?.omega?.[1])} °/s`);
  text('sample-time',finite(frame?.physical_time) ? `Physical sample ${frame.physical_time.toFixed(3)} s · source CPU call ${frame.model_cycle}` : 'Awaiting authoritative state.');
  const challenge = CHALLENGES[game.config.challenge];
  text('target-description',`${game.target ? 'Live reference' : 'Target preview'} · ${challenge.yawDeg ? `+${challenge.yawDeg}° yaw` : ''}${challenge.yawDeg && challenge.pitchDeg ? ' / ' : ''}${challenge.pitchDeg ? `+${challenge.pitchDeg}° pitch` : ''}`);
  text('objective-copy',`Reach the target within ${game.config.toleranceDeg}°, reduce total rotation below ${game.config.maxRateDegS}°/s, and hold for ${game.config.holdSeconds.toFixed(1)} s of observed model time.`);
  $('flight-start').disabled = !available || starting || activeSession() || !renderer?.status.available;
  text('start-label',starting || status==='initializing' ? 'Starting original AGC…' : status==='stopping' ? 'Ending run…' : enabled ? 'Armed · use controls' : game.result || hasSample ? 'Fly again' : 'Arm the AGC');
  $('flight-stop').disabled = !activeSession() || status==='stopping';
  document.querySelectorAll('[data-challenge]').forEach(button=>{button.disabled=starting||activeSession();button.classList.toggle('selected',button.dataset.challenge===game.config.challenge);button.setAttribute('aria-pressed',String(button.dataset.challenge===game.config.challenge));});
  document.querySelectorAll('[data-pilot]').forEach(button=>{button.disabled=!enabled;button.classList.toggle('pressed',live.held.has(button.dataset.pilot));});
  $('flight-neutral').disabled=!enabled;
  const errorVector = m?.errorVectorDeg;
  const direction = labControlGuidance(stale ? null : m,game.config);
  text('lab-direction',stale ? 'Last sample only. Steering assistance unavailable.' : game.result ? 'Lab run ended. The marker shows the scored relative error; controls are released. Return to mission procedures for the main experience.' : direction.text);
  document.querySelectorAll('[data-pilot]').forEach(button=>button.classList.toggle('suggested',enabled && direction.keys.includes(button.dataset.pilot)));
  $('rhc-pad').setAttribute('aria-disabled',String(!enabled));
  if(!enabled)resetStick();
  if (errorVector && !stale) {
    $('aim-marker').removeAttribute('hidden');
    const x = 70 + Math.max(-44,Math.min(44,errorVector[0]*12));
    const y = 70 - Math.max(-44,Math.min(44,errorVector[1]*12));
    $('aim-marker').setAttribute('transform',`translate(${x},${y})`);
  } else $('aim-marker').setAttribute('hidden','');
  $('flight-result').hidden = !game.result;
  if (game.result) {
    const success = game.result.outcome==='success';
    text('result-title',success ? 'Target acquired.' : game.result.outcome==='timeout' ? 'Time for another try.' : 'Run ended.');
    text('result-eyebrow',success ? 'TRAINING OBJECTIVE COMPLETE' : 'TRAINING DEBRIEF');
    text('result-copy',success ? 'You matched the attitude and held a low rotation rate in live backend samples. The session is ending; this is a training goal, not a landing.' : game.result.reason);
    text('final-score',game.result.score);
    text('result-detail',m ? `${m.errorDeg.toFixed(2)}° error · ${m.rateDegS.toFixed(2)}°/s\nScored at ${m.elapsedSeconds.toFixed(2)} s physical elapsed` : 'No scored live sample');
  }
  requestDraw();
}
async function checkService() {
  controlError=false; $('flight-error').hidden=true;
  try { await live.bootstrap(); available=true; if(!renderer?.status.available)showError('3D graphics are unavailable. Enable browser graphics and reload the page.'); }
  catch(error) { available=false; showError(error.message); }
  render();
}
async function start() {
  if (starting || activeSession() || !available) return;
  game=resetGame(game);lastResult=null;lastOrientation=null;lastTrustedFrame=null;controlError=false;stopRequested=false;
  $('flight-error').hidden=true; starting=true;render();
  announce('Starting original Luminary and checking native readiness.');
  await live.start();
}
function release(send=true) { resetStick();live.release(send); game=notePilotInput(game,{yaw:0,pitch:0});render(); }
function stop() { game=finishGame(game); stopRequested=true; live.stop(); render(); }
function hold(key,source) { if(!pilotEnabled())return;live.hold(key,source);game=notePilotInput(game,heldDirection(live.held));render(); }
function lift(source) { live.lift(source);game=notePilotInput(game,heldDirection(live.held));render(); }

$('flight-start').addEventListener('click',start);$('flight-stop').addEventListener('click',stop);
$('flight-neutral').addEventListener('click',()=>release(true));$('service-retry').addEventListener('click',checkService);
document.querySelectorAll('[data-challenge]').forEach(button=>button.addEventListener('click',()=>{
  if(activeSession()||starting)return;game=resetGame(game,{...game.config,challenge:button.dataset.challenge,maxRateDegS:button.dataset.challenge==='combined'?1.3:1});lastOrientation=null;lastTrustedFrame=null;lastResult=null;render();
}));
document.querySelectorAll('[data-pilot]').forEach(button=>{
  button.addEventListener('pointerdown',event=>{if(!pilotEnabled())return;event.preventDefault();button.setPointerCapture(event.pointerId);hold(button.dataset.pilot,`pointer-${event.pointerId}`);});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(type,event=>lift(`pointer-${event.pointerId}`));
  button.addEventListener('keydown',event=>{if(['Space','Enter'].includes(event.code)){event.preventDefault();if(!event.repeat)hold(button.dataset.pilot,`button-${event.code}`);}});
  button.addEventListener('keyup',event=>{if(['Space','Enter'].includes(event.code)){event.preventDefault();lift(`button-${event.code}`);}});
});
const keys={KeyA:'yaw-',KeyD:'yaw+',KeyS:'pitch-',KeyW:'pitch+'};
document.addEventListener('keydown',event=>{
  if($('flight-dialog').open||event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,select,textarea,[contenteditable]'))return;
  if(!$('keyboard-assist').checked)return;
  if(keys[event.code]){event.preventDefault();if(!event.repeat)hold(keys[event.code],`key-${event.code}`);}
  else if(event.code==='Space'&&!event.target.closest('button,a')){event.preventDefault();release(true);}
});
document.addEventListener('keyup',event=>{if(keys[event.code])lift(`key-${event.code}`);});
$('keyboard-assist').addEventListener('change',()=>release(true));
window.addEventListener('blur',()=>release(true));document.addEventListener('visibilitychange',()=>{if(document.hidden)release(true);});
window.addEventListener('pagehide',()=>release(true));

const stick=$('rhc-pad');
function resetStick(){stickPointer=null;$('rhc-handle').style.transform='translate(0px,0px)';}
function moveStick(event){
  const box=stick.getBoundingClientRect();
  const x=Math.max(-1,Math.min(1,(event.clientX-box.left-box.width/2)/(box.width*.34)));
  const y=Math.max(-1,Math.min(1,(event.clientY-box.top-box.height/2)/(box.height*.34)));
  const direction=stickDirections(x,y);
  for(const [axis,value] of Object.entries(direction)){
    const source=`stick-${axis}`,key=value?`${axis}${value>0?'+':'-'}`:null;
    const held=[...live.held].find(item=>item.startsWith(source+':'));
    if(held!== (key?`${source}:${key}`:undefined)){live.lift(source);if(key)live.hold(key,source);}
  }
  $('rhc-handle').style.transform=`translate(${x*25}px,${y*25}px)`;
  game=notePilotInput(game,heldDirection(live.held));render();
}
stick.addEventListener('pointerdown',event=>{if(!pilotEnabled()||event.button!==0)return;event.preventDefault();stick.setPointerCapture(event.pointerId);stickPointer=event.pointerId;moveStick(event);});
stick.addEventListener('pointermove',event=>{if(stickPointer===event.pointerId&&pilotEnabled())moveStick(event);});
for(const type of ['pointerup','pointercancel','lostpointercapture'])stick.addEventListener(type,event=>{if(stickPointer!==event.pointerId)return;live.lift('stick-yaw');live.lift('stick-pitch');resetStick();game=notePilotInput(game,heldDirection(live.held));render();});

const pointers=new Map(); let previousDistance=null;
const viewSurface=$('flight-canvas').parentElement;
viewSurface.addEventListener('pointerdown',event=>{if(event.button!==0 || event.target.closest('button,a'))return;viewSurface.setPointerCapture(event.pointerId);pointers.set(event.pointerId,[event.clientX,event.clientY]);});
viewSurface.addEventListener('pointermove',event=>{
  const old=pointers.get(event.pointerId);if(!old||!renderer)return;
  pointers.set(event.pointerId,[event.clientX,event.clientY]);
  if(pointers.size===1)renderer.orbit(event.clientX-old[0],event.clientY-old[1]);
  else {const [a,b]=[...pointers.values()];const distance=Math.hypot(a[0]-b[0],a[1]-b[1]);if(previousDistance)renderer.zoom((previousDistance-distance)*3);previousDistance=distance;}
  requestDraw();
});
for(const type of ['pointerup','pointercancel','lostpointercapture'])viewSurface.addEventListener(type,event=>{pointers.delete(event.pointerId);previousDistance=null;});
viewSurface.addEventListener('wheel',event=>{if(event.target.closest('button,a'))return;event.preventDefault();renderer?.zoom(event.deltaY);requestDraw();},{passive:false});
$('camera-reset').addEventListener('click',()=>{renderer?.reset();requestDraw();});
$('camera-zoom-in').addEventListener('click',()=>{renderer?.zoom(-140);requestDraw();});
$('camera-zoom-out').addEventListener('click',()=>{renderer?.zoom(140);requestDraw();});
$('flight-canvas').addEventListener('flight-renderer-status',event=>{if(!event.detail.available){release(true);showError(event.detail.message);}else render();});
window.addEventListener('resize',requestDraw);

function openHelp(kind='help') {
  release(true);
  const content={
    help:['A light touch. An opposite push.',`<ol><li><b>Choose a challenge and arm the AGC.</b> The local native engine verifies pinned sources, then executes original startup. Wait for “You have the controls.”</li><li><b>Use the modern two-axis lab pad.</b> In this lab only, drag right/left for positive/negative yaw or up/down for positive/negative pitch. The target is relative rotation, not a point to fly toward. Accessible direction buttons are also available. Keyboard shortcuts are off unless explicitly enabled.</li><li><b>Watch the angle and rotation rate.</b> Release returns the controller to neutral. Use the opposite input to reduce motion. Get inside the marked angle/rate limits and hold for the required observed interval.</li></ol><p>Drag the model to orbit the camera. Scroll or use + / − to zoom. Camera movement does not steer the spacecraft. The teal outline is an invented lab target orientation. The fixed reference instrument marks YOU at its center and TARGET at the required relative rotation. This is a synthetic experiment, not an Apollo 11 procedure.</p><p><b>The real Apollo Attitude Controller Assembly (ACA) has different axes:</b> fore/aft commands pitch, left/right commands roll, and twisting the grip commands yaw. This lab has no roll or twist input and does not reproduce the ACA, cockpit switches, control modes, or Thrust/Translation Controller Assembly (TTCA).</p><p>References: <a href="https://www.ibiblio.org/apollo/Documents/LMA790-3-LM-2.1.pdf" target="_blank" rel="noopener">LM systems handbook §2.1.1.3.1 / figure 2.1-9</a> (later LM revision; hardware geometry reference) and the <a href="https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf" target="_blank" rel="noopener">Apollo 11 activation checklist, ACT-51</a> (separate roll, pitch and yaw checks).</p><p class="scope-note">The 11.7-second model clock starts at the first deflection. It continues while help is open or controls are released. Closing or hiding the tab releases controls; no pause or instant brake is implied.</p>`],
    setup:['Start a real control session.',`<p>The game needs the existing live attitude service. The recorded demo launcher intentionally disables inputs. From the repository root:</p><pre><code>make play</code></pre><p>Then open <code>http://127.0.0.1:4173/attitude-lab.html</code>. For an occupied port use <code>make play PORT=4180</code> and open that port.</p><p>The first launch builds checksum-pinned Tcl 8.6.16 locally. Python 3.9+, a C compiler, make and initial download access are required. Later rounds reuse the prepared sources/runtime. No AGC starts until you arm it.</p>`],
    scope:['Original computer. Bounded game.',`<p><b>Live computation:</b> your yaw/pitch requests reach original Luminary 099 via the pinned native AGC and ringbuffer. Actual RCS outputs drive the retained external rotational model; generated sensor measurements return to the AGC.</p><p><b>Modern presentation:</b> WebGL draws an illustrative 3D Lunar Module from the actual scalar-first body-to-stable quaternion. The target ghost and score are frontend training rules, not flight-software goals or claims of mission success. The modern pad sends only the fixture’s supported discrete yaw/pitch directions. Its left/right yaw mapping is not the Apollo ACA mapping: real ACA fore/aft was pitch, left/right was roll, and twist was yaw. The actual ACA’s roll/twist axes, detents, breakout forces and control-mode behavior are not implemented here.</p><p><b>Numerical boundary:</b> the retained synthetic rigid-body/ideal-IMU fixture uses its existing semi-implicit integration, approximately 10 ms coupling cadence and quaternion attitude overlay. Its ideal alignment and synthetic mass properties are not a calibrated flight vehicle. Browser polling is coarser; missing intervals do not count toward a target hold.</p><p class="scope-note">Only bounded yaw/pitch control is supported. No independent roll input, translation, descent-engine thrust, radar, touchdown or landing is simulated by this game. Reference rings are attitude instruments, not a propagated orbit.</p><p>After a successful sampled target hold, the UI asks the backend to stop. The physical model freezes and finite sensor work settles. A short training hold does not demonstrate sustained spacecraft stability.</p>`]
  };
  const [title,html]=content[kind]||content.help;text('dialog-title',title);$('dialog-content').innerHTML=html;$('flight-dialog').showModal();
}
$('help-open').addEventListener('click',()=>openHelp());$('scope-open').addEventListener('click',()=>openHelp('scope'));$('setup-open').addEventListener('click',()=>openHelp('setup'));
$('dialog-close').addEventListener('click',()=>$('flight-dialog').close());
render();checkService();
