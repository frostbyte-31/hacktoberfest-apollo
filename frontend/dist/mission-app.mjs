import { MissionLiveProvider, RecordedPropulsionProvider, ROLE_IDS } from './mission-live-provider.mjs';
import { renderFlightView } from './flight-view.mjs';
const $ = id => document.getElementById(id);
const provider = new MissionLiveProvider();
let discovery = null, snapshot = null, bounds = null, stopped = false, pitch = 0, throttle = 0;
let queue = Promise.resolve(), polling = false, propulsion = null;
const number = (value, precision = 1) => Number.isFinite(value) ? value.toLocaleString('en-US', {minimumFractionDigits: precision, maximumFractionDigits: precision}) : '—';
const text = (id, value) => { $(id).textContent = value; };
function notice(message, error = false) { text('mission-notice', message); $('mission-notice').dataset.error = String(error); }
function pilot() { return snapshot?.you?.role === 'commander' && snapshot?.status === 'running'; }
function item(tag, value, className) { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; }
function render(state) {
  if (snapshot?.id === state.id && snapshot.revision > state.revision) return;
  const newRun = snapshot?.runId !== state.runId;
  snapshot = state;
  if (newRun || !bounds) {
    bounds = {heightM: Math.max(100, state.physics.spacecraft.altitudeM * 1.18), widthM: Math.max(500, Math.abs(state.physics.spacecraft.downrangeM) + 1200)};
    throttle = 0; pitch = 0; $('manual-throttle').value = '0';
  }
  const physical = state.physics, craft = physical.spacecraft, engine = physical.engine;
  renderFlightView(document, craft, engine, bounds);
  text('mission-title', state.title); text('mission-status', state.status.toUpperCase());
  text('simulation-clock', `T + ${number(physical.simTimeSeconds, 2)} s`);
  text('mission-identity', `Mission ${state.id} · sample ${physical.tick}`);
  text('flight-altitude', number(craft.altitudeM)); text('flight-vertical', number(craft.verticalSpeedMps));
  text('flight-horizontal', number(craft.horizontalSpeedMps)); text('flight-fuel', number(craft.fuelKg));
  text('flight-pitch', `${number(craft.pitchDeg)}°`); text('flight-thrust', `${number(engine.thrustN, 0)} N`);
  text('flight-mass', `Mass: ${number(craft.massKg, 0)} kg`);
  text('context-physics', state.status === 'completed'
    ? 'The flight has ended. These are frozen endpoint measurements, including the velocity at contact or termination. The engine is off and no further motion is propagated.'
    : `At this sample, ${number(engine.thrustN, 0)} N ÷ ${number(craft.massKg, 0)} kg gives ${number(engine.thrustN / craft.massKg, 2)} m/s² of thrust acceleration along the spacecraft’s pointing direction. Gravity acts separately. ${craft.verticalSpeedMps < 0 ? 'The spacecraft is still descending.' : 'The spacecraft is moving upward or stationary vertically.'}`);
  text('your-role', state.you ? `${state.you.name} · ${state.you.role ?? 'Observer / host'}` : 'Observer · no crew command authority');
  const members = state.crew.map(member => {
    const li = document.createElement('li');
    li.append(item('strong', `${member.name} · ${member.role}`), item('small', member.location), item('span', member.occupied ? `${member.displayName || member.kind} · ${member.kind === 'fallback' ? 'deterministic fallback' : member.kind} · ${member.ready ? 'READY' : 'NOT READY'}${member.agentStatus ? ' · '+member.agentStatus : ''}` : 'Open human position', 'crew-status'));
    return li;
  });
  $('mission-crew').replaceChildren(...members);
  const own = state.crew.find(member => member.id === state.you?.role);
  $('crew-ready').disabled = !own || state.status !== 'lobby'; $('crew-ready').checked = own?.ready ?? false;
  const manager = Boolean(state.you?.host || state.you?.role === 'commander');
  $('mission-start').disabled = !manager || state.status !== 'lobby' || !state.crew.every(member => member.ready && member.occupied);
  $('mission-pause').disabled = !manager || !['running','paused'].includes(state.status);
  text('mission-pause', state.status === 'paused' ? 'Resume' : 'Pause');
  $('mission-restart').disabled = !manager || state.status === 'running';
  $('copy-invite').disabled = false;
  const canPilot = pilot();
  for (const id of ['manual-throttle','pitch-negative','pitch-positive','engine-cutoff']) $(id).disabled = !canPilot || state.assistance;
  $('training-assist').disabled = state.you?.role !== 'commander' || !['lobby','running','paused'].includes(state.status); $('training-assist').checked = state.assistance;
  text('pilot-permission', state.assistance ? 'MODERN TRAINING ASSIST ACTIVE' : canPilot ? 'COMMANDER · MANUAL CONTROL' : 'COMMANDER’S CONTROLS · INACTIVE');
  for (const node of document.querySelectorAll('[data-check]')) {
    node.disabled = state.you?.role !== 'lunar-module-pilot'; node.checked = Boolean(state.checklist[node.dataset.check]?.done);
  }
  for (const id of ['crew-message','message-send']) $(id).disabled = !own;
  const messages = state.messages.slice(-20).map(message => {
    const li = document.createElement('li');
    li.append(item('strong', `${message.name} · ${message.source} · ${number(message.timeSeconds,0)} s`), document.createTextNode(message.text));
    return li;
  });
  $('crew-messages').replaceChildren(...(messages.length ? messages : [item('li','No mission communications yet.')]));
  const events = state.events.slice(-35).reverse().map(event => {
    const li = document.createElement('li'); li.append(item('time', `${number(event.timeSeconds,1)} s`), item('span', event.text)); return li;
  });
  $('flight-events').replaceChildren(...(events.length ? events : [item('li','No simulated events yet.')]));
  const outcome = physical.outcome;
  $('debrief-panel').hidden = !(outcome || state.debrief);
  if (outcome || state.debrief) {
    text('debrief-title', outcome?.success ? 'A measured soft landing.' : 'Review the measured outcome.');
    text('debrief-explanation', `This is an educational physics result, not an original AGC-controlled Apollo landing. Final vertical velocity: ${number(craft.verticalSpeedMps,2)} m/s. Horizontal speed: ${number(craft.horizontalSpeedMps,2)} m/s. Remaining propellant: ${number(craft.fuelKg,1)} kg.`);
    const values = [['Altitude',`${number(craft.altitudeM)} m`],['Downrange',`${number(craft.downrangeM)} m`],['Pitch',`${number(craft.pitchDeg)}°`],['Simulation time',`${number(physical.simTimeSeconds,2)} s`]];
    $('debrief-values').replaceChildren(...values.flatMap(([key,value]) => [item('dt',key),item('dd',value)]));
    text('debrief-raw', JSON.stringify({outcome, debrief: state.debrief, finalPositionM: craft.positionM, finalVelocityMps: craft.velocityMps},null,2));
  }
}
function command(action, payload = {}, {quiet = false} = {}) {
  const requestedRun = snapshot?.runId;
  const operation = queue.then(async () => {
    // A keepalive can already be queued when Pause/Restart completes. Recheck
    // authoritative state before sending it, rather than issuing a stale input.
    if (action === 'controls' && (!pilot() || snapshot.assistance || snapshot.runId !== requestedRun)) return null;
    const result = await provider.command(action, payload);
    render(result.snapshot);
    if (!result.accepted) throw new Error(result.reason ?? 'The mission did not accept that command.');
    if (!quiet) notice(`Mission command accepted: ${action}.`);
    return result;
  });
  queue = operation.catch(error => { notice(error.message, true); });
  return operation.catch(() => null);
}
function controls() {
  if (!pilot() || snapshot.assistance) return;
  return command('controls', {throttle, pitch}, {quiet: true});
}
function neutral() { pitch = 0; throttle = 0; $('manual-throttle').value = '0'; text('throttle-value','0%'); controls(); }
async function refresh() {
  if (stopped || !provider.credentials) return;
  try { render(await provider.snapshot()); }
  catch (error) { notice(`Connection interrupted: ${error.message} The display holds its last server sample.`, true); }
  setTimeout(refresh, 200);
}
function startPolling() { if (!polling) { polling = true; refresh(); } }
function entered(state) {
  snapshot = null; bounds = null; render(state); $('mission-setup').open = false;
  notice(`Connected to ${state.title}. Crew readiness and command permissions are enforced by the server.`); startPolling();
}
$('create-mission').addEventListener('submit', async event => {
  event.preventDefault(); $('create-button').disabled = true;
  try {
    const role = $('creator-role').value || null;
    const crewModes = Object.fromEntries(ROLE_IDS.map(id => [id,$(`crew-mode-${id}`).value]));
    if (role) crewModes[role] = 'human';
    entered(await provider.create({scenarioId:$('mission-scenario').value,name:$('crew-name').value.trim(),role,crewModes}));
  } catch (error) { notice(error.message,true); }
  finally { $('create-button').disabled = !discovery?.capabilities.physicsLab; }
});
$('join-mission').addEventListener('submit', async event => {
  event.preventDefault(); $('join-button').disabled = true;
  try { entered(await provider.join({missionId:$('join-id').value.trim(),name:$('join-name').value.trim(),role:$('join-role').value})); }
  catch (error) { notice(error.message,true); }
  finally { $('join-button').disabled = false; }
});
$('creator-role').addEventListener('change', () => {
  const role = $('creator-role').value;
  if (role) $(`crew-mode-${role}`).value = 'human';
  else for (const id of ROLE_IDS) $(`crew-mode-${id}`).value = 'fallback';
});
$('crew-ready').addEventListener('change',event => command('ready',{ready:event.target.checked}));
$('mission-start').addEventListener('click',() => command('start'));
$('mission-pause').addEventListener('click',() => { neutral(); command(snapshot.status === 'paused' ? 'resume' : 'pause'); });
$('mission-restart').addEventListener('click',() => { neutral(); command('restart'); });
$('training-assist').addEventListener('change',event => { neutral(); command('assist',{enabled:event.target.checked}); });
$('manual-throttle').addEventListener('input',event => { throttle=Number(event.target.value)/100; text('throttle-value',`${Math.round(throttle*100)}%`); controls(); });
$('engine-cutoff').addEventListener('click',neutral);
for (const [id,direction] of [['pitch-negative',-1],['pitch-positive',1]]) {
  const button=$(id);
  button.addEventListener('pointerdown',event => { if (button.disabled) return; event.preventDefault(); button.setPointerCapture(event.pointerId); pitch=direction; controls(); });
  for (const name of ['pointerup','pointercancel','lostpointercapture']) button.addEventListener(name,() => { pitch=0; controls(); });
}
document.addEventListener('keydown',event => {
  if (!pilot() || snapshot.assistance || event.repeat || ['INPUT','SELECT','TEXTAREA'].includes(document.activeElement?.tagName)) return;
  if (event.code==='KeyA' || event.code==='KeyD') { event.preventDefault(); pitch=event.code==='KeyA'?-1:1; controls(); }
  if (event.code==='ArrowUp' || event.code==='ArrowDown') { event.preventDefault(); throttle=Math.max(0,Math.min(1,throttle+(event.code === 'ArrowUp' ? .05 : -.05))); $('manual-throttle').value=String(Math.round(throttle*100)); text('throttle-value',`${Math.round(throttle*100)}%`); controls(); }
});
document.addEventListener('keyup',event => { if (event.code==='KeyA'||event.code==='KeyD') { pitch=0; controls(); } });
window.addEventListener('blur',neutral);
document.addEventListener('visibilitychange',() => { if (document.hidden) neutral(); });
window.addEventListener('pagehide',() => { neutral(); stopped=true; });
setInterval(() => { if (!document.hidden) controls(); },400);
$('send-message').addEventListener('submit',event => { event.preventDefault(); const value=$('crew-message').value.trim(); if (value) { command('message',{text:value}); $('crew-message').value=''; } });
for (const input of document.querySelectorAll('[data-check]')) input.addEventListener('change',() => command('checklist',{item:input.dataset.check}));
$('copy-invite').addEventListener('click',async () => {
  const link=new URL('./mission.html',location.href); link.searchParams.set('join',snapshot.id);
  $('join-id').value=snapshot.id;
  try { await navigator.clipboard.writeText(link.href); notice('Crew invite copied. Open it in another browser or private window to join an open human position.'); }
  catch { notice(`Crew invite: ${link.href}`); }
});
let recordingCase = 'connected', recordingTime = 0, recordingPlaying = false, recordingLast = null;
function drawRecordedPropulsion() {
  if (!propulsion) return;
  const scenario = propulsion.scenario(recordingCase), frame = propulsion.frame(recordingCase,recordingTime);
  const root=$('propulsion-content');
  root.querySelector('#recorded-case').value=recordingCase;
  root.querySelector('#recorded-time').value=String(recordingTime);
  root.querySelector('#recorded-time').max=String(scenario.durationSeconds);
  root.querySelector('#recorded-play').textContent=recordingPlaying?'Pause recorded replay':'Play recorded replay';
  root.querySelector('#recorded-observation').textContent=`Recorded elapsed ${number(frame.t,2)} s · raw line ${frame.source.rawLine} · cycle ${frame.cycle}`;
  const craft=frame.physics.spacecraft, engine=frame.physics.engine, dsky=frame.agc?.dsky;
  root.querySelector('#recorded-values').textContent=`Altitude ${number(craft.altitudeM)} m · speed ${number(Math.hypot(...craft.velocityMps))} m/s · delivered thrust ${number(engine.thrustN,0)} N · fuel ${number(craft.fuelKg)} kg`;
  root.querySelector('#recorded-dsky').textContent=dsky?`PROGRAM ${dsky.PROG}   VERB ${dsky.VERB}   NOUN ${dsky.NOUN}\nR1 ${dsky.R1}   R2 ${dsky.R2}   R3 ${dsky.R3}`:'No recorded DSKY observation available at this sample.';
  const initial=scenario.frames[0].physics.spacecraft;
  const radius=Math.hypot(...initial.positionM)-initial.altitudeM;
  const point=craft.positionM;
  const marker=root.querySelector('#recorded-craft');
  marker.setAttribute('cx',String(260+point[0]/radius*145));marker.setAttribute('cy',String(190-point[2]/radius*145));
  const events=scenario.events.filter(event => event.t<=frame.t).slice(-8).map(event=>item('li',`${number(event.t,1)} s · ${event.text ?? event.title ?? event.type}`));
  root.querySelector('#recorded-events').replaceChildren(...events);
  root.querySelector('#recorded-result').textContent=`Retained result: ${scenario.result.originalThrottleCalls} original throttle calls; ${scenario.result.originalLunarNavigationPasses} original lunar navigation passes. Landing: NOT RUN.`;
  root.querySelector('#recorded-fingerprint').textContent=`Raw trace SHA-256: ${scenario.traceSha256}`;
}
function replayTick(timestamp) {
  if (!recordingPlaying || !$('propulsion-dialog').open) {recordingLast=null;return;}
  if(recordingLast!==null) recordingTime=Math.min(propulsion.scenario(recordingCase).durationSeconds,recordingTime+(timestamp-recordingLast)/1000*5);
  recordingLast=timestamp;drawRecordedPropulsion();
  if(recordingTime>=propulsion.scenario(recordingCase).durationSeconds) {recordingPlaying=false;drawRecordedPropulsion();return;}
  requestAnimationFrame(replayTick);
}
$('propulsion-close').addEventListener('click',()=>{recordingPlaying=false;$('propulsion-dialog').close();});
$('propulsion-dialog').addEventListener('close',()=>{recordingPlaying=false;});
$('propulsion-open').addEventListener('click',()=>{
  if(!propulsion)return;
  const body=$('propulsion-content');body.replaceChildren(item('p','VERIFIED RECORDED AUTHENTIC AGC EXPERIMENT','flight-kicker'),item('h2','Original commands. Measured consequences.'),item('p','This sealed native experiment is recorded, not running live. Original Luminary commands drove the modeled engine; genuine PIPA pulses affected original navigation and later throttle calculations. It is not a complete descent or landing.'));
  const select=document.createElement('select');select.id='recorded-case';
  for(const scenario of propulsion.recording.cases) {const option=item('option',scenario.title);option.value=scenario.id;select.append(option);}body.append(select);
  const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 520 380');svg.classList.add('recorded-orbit');
  const moon=document.createElementNS(ns,'circle');moon.setAttribute('cx','260');moon.setAttribute('cy','190');moon.setAttribute('r','145');moon.classList.add('recorded-moon');
  const craft=document.createElementNS(ns,'circle');craft.id='recorded-craft';craft.setAttribute('r','4');svg.append(moon,craft);body.append(svg,item('p','Moon-centered REF X–Z projection of actual recorded positions. Vehicle symbol enlarged; no predicted trajectory.'));
  const observation=item('p','');observation.id='recorded-observation';const values=item('p','');values.id='recorded-values';body.append(observation,values);
  const dsky=item('pre','');dsky.id='recorded-dsky';body.append(dsky);
  const transport=document.createElement('div');transport.className='recorded-transport';
  const play=item('button','Play recorded replay','flight-secondary');play.id='recorded-play';
  const restart=item('button','Restart','flight-secondary');
  const range=document.createElement('input');range.id='recorded-time';range.type='range';range.min='0';range.step='.01';range.setAttribute('aria-label','Recorded propulsion elapsed time');transport.append(play,restart,range);body.append(transport,item('p','Playback at 5× speed · held recorded observations; no interpolated AGC values.'));
  const list=document.createElement('ol');list.id='recorded-events';body.append(list);
  for(const limitation of propulsion.recording.limitations) body.append(item('p',limitation,'flight-small'));
  const result=item('p','','flight-small');result.id='recorded-result';body.append(result);
  const fingerprint=item('pre','');fingerprint.id='recorded-fingerprint';body.append(fingerprint);
  select.addEventListener('change',()=>{recordingCase=select.value;recordingTime=0;recordingPlaying=false;drawRecordedPropulsion();});
  range.addEventListener('input',()=>{recordingPlaying=false;recordingTime=Number(range.value);drawRecordedPropulsion();});
  play.addEventListener('click',()=>{recordingPlaying=!recordingPlaying;recordingLast=null;if(recordingTime>=propulsion.scenario(recordingCase).durationSeconds)recordingTime=0;drawRecordedPropulsion();if(recordingPlaying)requestAnimationFrame(replayTick);});
  restart.addEventListener('click',()=>{recordingPlaying=false;recordingTime=0;drawRecordedPropulsion();});
  drawRecordedPropulsion();$('propulsion-dialog').showModal();
});
RecordedPropulsionProvider.load().then(provider=>{propulsion=provider;$('propulsion-open').disabled=false;$('propulsion-open').replaceChildren(document.createTextNode('Inspect the verified engine experiment '),item('span','RECORDED'));}).catch(error=>{$('propulsion-open').title=error.message;$('propulsion-open').replaceChildren(document.createTextNode('Recorded engine evidence unavailable'));});
const joinId=new URLSearchParams(location.search).get('join');
if (joinId) { $('join-id').value=joinId; $('join-name').focus(); }
async function initialize() {
  try {
    discovery=await provider.discover();
    $('mission-scenario').replaceChildren(...discovery.scenarios.map(scenario => { const option=item('option',scenario.title); option.value=scenario.id; return option; }));
    $('mission-scenario').disabled=!discovery.capabilities.physicsLab;
    $('crew-composition').replaceChildren(...discovery.crewRoles.map((role,index) => {
      const label=item('label',role.role); const select=document.createElement('select'); select.id=`crew-mode-${role.id}`;
      for (const [value,title] of [['human','Human'],['fallback','Fallback agent'],['llm','Model AI']]) { const option=item('option',title); option.value=value; if (value==='llm') option.disabled=!discovery.capabilities.llmConfigured; select.append(option); }
      select.value=index===0?'human':'fallback'; label.append(select); return label;
    }));
    $('create-button').disabled=!discovery.capabilities.physicsLab; $('join-button').disabled=!discovery.capabilities.multiplayer;
    text('mission-limitations',discovery.limitations.join(' · '));
    notice(discovery.capabilities.physicsLab ? 'Mission service ready. Create a synthetic flight, or join your crew. Original AGC experiences remain available through the links above.' : 'The educational physics service is unavailable. Verified recorded guidance remains available.');
    if (provider.credentials && !joinId) { try { entered(await provider.snapshot()); } catch (error) { notice(`Previous session cannot be resumed: ${error.message} Create or join a mission.`,true); } }
  } catch (error) { notice(`${error.message} Use the documented final-demo server. Original recordings remain available through the guidance link.`,true); text('mission-limitations','No live mission data received. No fallback telemetry is fabricated.'); }
}
initialize();
