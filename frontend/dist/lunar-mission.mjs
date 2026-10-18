import {createMissionRenderer} from './mission-3d.mjs';
import {PropulsionTraceProvider,observedCockpitSignals,missionGate} from './propulsion-provider.mjs';
import {validateOperations,replayMilestones,physicalStart,adjacentReplayEvent} from './mission-start-state.mjs';
import {renderDSKY} from './dsky-view.mjs';
import {lastAt,formatTime} from './replay.mjs';

const $=id=>document.getElementById(id);
const put=(id,value)=>{$(id).textContent=value;};
const element=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
const pair=(dl,label,value)=>dl.append(element('dt',label),element('dd',value));
const number=(value,digits=1)=>Number.isFinite(value)?value.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'—';
const vector=(values,digits=2)=>Array.isArray(values)?values.map(v=>number(v,digits)).join(' / '):'Unavailable';
let operations=null,provider=null,mode='historical',caseId='connected',time=0,playing=false,selectedEventId=null,lastPaint=0,disposed=false,renderedKey=null;
let renderer=null;
$('recorded-mode').disabled=true;
try{renderer=createMissionRenderer($('mission-canvas'));put('renderer-kind',renderer.kind.toUpperCase());}catch(error){showError(`The spacecraft viewer could not initialize: ${error.message}`);}

function showError(message){$('error').hidden=false;put('error-copy',message);}
function announce(message){put('announcement',message);}
function sources(container,ids){
  container.replaceChildren();
  for(const id of ids){const source=operations.sources.find(s=>s.id===id);if(!source)continue;const a=element('a',`${source.title} ↗`);a.href=source.url;a.target='_blank';a.rel='noreferrer';a.title=`${source.locator}. ${source.revisionScope}`;container.append(a);}
}
function renderOperations(){
  $('mission-sequence').replaceChildren(...operations.timeline.map((chapter,index)=>{
    const li=element('li'),button=element('button');button.type='button';button.dataset.chapter=chapter.id;
    button.append(element('span',String(index+1).padStart(2,'0')));const text=element('span',chapter.title);text.append(element('small',chapter.getLabel));button.append(text);button.addEventListener('click',()=>previewChapter(chapter.id));li.append(button);return li;
  }));
  const primary=['GUID CONT','MODE CONT · PGNS and AGS','ATTITUDE CONTROL · all three axes','TTCA · both','TTCA/TRANSL · CDR'];
  $('starting-config').replaceChildren();for(const label of primary){const item=operations.chapter.startingConfiguration.find(row=>row.label===label);if(item)pair($('starting-config'),label,item.referenceValue);}
  const details=element('details'),summary=element('summary','Full pre-undocking checklist reference');details.append(summary);const dl=element('dl');
  for(const row of operations.chapter.startingConfiguration)pair(dl,row.label,`${row.referenceValue} · ${row.locator}`);details.append(dl);$('starting-config').after(details);
  put('mission-gate',missionGate().reason);
  const labels={aca:'ACA / attitude',ttca:'TTCA / translation','pgns-mode':'PGNS mode','attitude-axis':'Axis switches',rod:'ROD / descent rate',dsky:'DSKY'};
  $('control-tabs').replaceChildren(...operations.controls.map(control=>{const button=element('button',labels[control.id]??control.label);button.type='button';button.dataset.control=control.id;button.addEventListener('click',()=>inspectControl(control.id));return button;}));
  put('software-summary',operations.softwareEntry.summary);
  $('software-entries').replaceChildren(...operations.softwareEntry.files.map(file=>{const div=element('div',undefined,'software-entry');div.append(element('strong',file.symbol),element('p',file.meaning));const link=element('a',`${file.path} ↗`);link.href=operations.sources.find(s=>s.id==='luminary-entry').url.split('/Luminary099/')[0]+'/'+file.path;link.target='_blank';link.rel='noreferrer';div.append(link);return div;}));
  previewChapter('docked-preparation');inspectControl('aca');
}
function previewChapter(id){
  const chapter=operations.timeline.find(item=>item.id===id);if(!chapter)return;
  document.querySelectorAll('[data-chapter]').forEach(button=>{const active=button.dataset.chapter===id;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  put('preview-get',chapter.getLabel);put('preview-title',chapter.title);put('preview-description',chapter.description);put('preview-crew',`${chapter.crewRole} · ${chapter.vehicle}`);sources($('preview-sources'),chapter.sourceIds);
  announce(`Historical reference: ${chapter.title}. The starting spacecraft configuration has not changed.`);
}
function inspectControl(id){
  const control=operations.controls.find(item=>item.id===id);if(!control)return;
  document.querySelectorAll('[data-control]').forEach(button=>{const active=button.dataset.control===id;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  put('control-title',control.label);put('control-location',control.location);put('control-hardware',control.hardware);put('control-purpose',control.purpose);put('control-limit',control.limitations);
  $('control-modes').replaceChildren(...control.modes.map(item=>{const div=element('div',undefined,'control-mode');div.append(element('strong',item.label),element('p',item.behavior));return div;}));sources($('control-sources'),control.sourceIds);
}
function setMode(next){
  mode=next;playing=false;selectedEventId=null;renderedKey=null;renderer?.reset();
  const recorded=mode==='recorded';
  renderer?.setView(recorded?'orbit':'vehicle');
  $('vehicle-view').setAttribute('aria-pressed',String(!recorded));$('orbit-view').setAttribute('aria-pressed',String(recorded));
  document.body.classList.toggle('recorded',recorded);
  $('mission-sequence').closest('aside').hidden=recorded;
  $('historical-mode').classList.toggle('active',!recorded);$('historical-mode').setAttribute('aria-pressed',String(!recorded));$('recorded-mode').classList.toggle('active',recorded);$('recorded-mode').setAttribute('aria-pressed',String(recorded));
  $('historical-station').hidden=recorded;$('historical-preview').hidden=recorded;$('recorded-station').hidden=!recorded;$('replay-console').hidden=!recorded;
  put('chapter-kicker',recorded?'ORIGINAL LUMINARY / BOUNDED PROPULSION':'CHAPTER 01 / LUNAR ORBIT');
  $('mission-title').replaceChildren(document.createTextNode(recorded?'From command to ':'Before the '),element('em',recorded?'motion.':'descent.'));
  put('mission-intro',recorded?'Inspect the original engine command, actual model response and feedback into original guidance. This is a retained synthetic experiment.':'Eagle is still docked to Columbia. Learn the actual controls, then follow the mission in the order the crew did.');
  put('clock-label',recorded?'RECORDED CPU ELAPSED / NOT GET':'HISTORICAL CHECKLIST REFERENCE');put('clock-note',recorded?'Playback seeks evidence; it does not run a live spacecraft.':'Ground elapsed time · reference, not a running simulation');
  put('execution-mode',recorded?'VERIFIED RECORDED EXECUTION':'STATIC EDUCATIONAL ILLUSTRATION');
  put('scope',recorded?'SYNTHETIC / FIXED ATTITUDE · no historical descent or landing':'Historical procedure reference · no live flight telemetry');
  put('station-title',recorded?'Original computer + cockpit':'Your starting point');put('station-mode',recorded?'RECORDING':'REFERENCE');
  put('scene-vehicle',recorded?'LUNAR MODULE / RETAINED REF STATE':'EAGLE + COLUMBIA / DOCKED');
  if(recorded&&provider){selectCase(caseId);}else{put('mission-clock','~100:05 GET');put('scene-state','HISTORICAL CONFIGURATION / SCHEMATIC');$('scene-caption').replaceChildren(document.createTextNode('Columbia docked'),element('br'),document.createTextNode('to Eagle.'));put('scene-detail','The white command/service assembly is Columbia. The gold spacecraft below is Eagle, the Lunar Module.');put('scene-disclosure','Illustrative docked arrangement · spacecraft enlarged · geometry not to scale · camera controls only');drawScene();}
  renderer?.resize();announce(recorded?'Verified synthetic propulsion recording selected.':'Historical lunar-orbit starting point selected.');
}
function events(){return provider?replayMilestones(provider.getCase(caseId),$('all-events').checked):[];}
function renderEventList(){
  renderedKey=null;
  $('recorded-events').replaceChildren(...events().map(event=>{const li=element('li'),button=element('button');button.type='button';button.dataset.event=event.id;const stamp=element('time',formatTime(event.t));button.append(stamp,element('span',event.title));button.addEventListener('click',()=>seek(event.t,event.id));li.append(button);return li;}));
}
function selectCase(id){
  if(!provider)return;caseId=id;time=physicalStart(provider.getCase(id));playing=false;selectedEventId=null;renderer?.reset();
  $('replay-time').max=String(provider.getCase(id).durationSeconds);$('execution-case').value=id;
  const item=provider.getCase(id);put('causal-description',`${item.description} Engine connected: ${item.physicalEngineConnected?'yes':'no'}. Accelerometer feedback delivered: ${item.sensorFeedbackConnected?'yes':'no'}. Cases are compared at their own recorded times; no numerical historical relationship is implied.`);
  renderEventList();renderRecorded();
}
function seek(seconds,id=null){time=Math.max(0,Math.min(provider.getCase(caseId).durationSeconds,seconds));playing=false;selectedEventId=id;renderRecorded();}
function drawScene(snapshot=null){
  if(!renderer)return;
  if(mode==='historical'){renderer.draw({mode:'historical-illustration'});return;}
  if(!snapshot&&provider)snapshot=selectedEventId?provider.getEventSnapshot(caseId,selectedEventId):provider.getSnapshot(caseId,time);
  const craft=snapshot?.spacecraft,item=provider?.getCase(caseId);
  renderer.draw({mode:'recorded',available:Boolean(craft),positionM:craft?.positionM,velocityMps:craft?.velocityMps,quaternion:craft?.quaternion,trajectoryM:craft?provider.trajectoryThrough(caseId,time,selectedEventId?{rawLine:snapshot.source.rawLine}:{}):[],lunarRadiusM:item?.initialGeometry.lunarRadiusM});
}
function renderRecorded(){
  if(mode!=='recorded'||!provider)return;
  const snapshot=selectedEventId?provider.getEventSnapshot(caseId,selectedEventId):provider.getSnapshot(caseId,time),frame=snapshot.frame,craft=snapshot.spacecraft,item=provider.getCase(caseId);
  put('mission-clock',`${formatTime(time)} CPU`);put('replay-time-value',`${formatTime(time)} / ${formatTime(item.durationSeconds)}`);$('replay-time').value=String(time);put('replay-play',playing?'Pause recording':'Play recording');
  const key=`${caseId}:${frame.source.rawLine}:${selectedEventId}`;if(key===renderedKey)return;renderedKey=key;
  renderDSKY(document,frame.dsky);
  const dskySource=frame.observationSources.dsky;
  put('dsky-source',dskySource?`Held digit observation · cycle ${dskySource.cycle} · raw line ${dskySource.rawLine}. Observed program checkpoint: ${frame.observedProgram??'unavailable'}.`:'No recorded DSKY digit observation yet.');
  $('cockpit-signals').replaceChildren();const signals=observedCockpitSignals(frame);
  for(const [name,key] of [['PGNS select signal','pgns'],['ATT AUTO signal','autoAttitude'],['Automatic throttle','autoThrottle'],['Engine ARM signal','engineArmed'],['Radar position 1','radarPosition1']])pair($('cockpit-signals'),name,signals[key]?(signals[key].asserted?'ASSERTED':'NOT ASSERTED'):'UNKNOWN');
  put('physical-time',craft?`${number(craft.physicalTimeSeconds,3)} s`:'Unavailable');put('thrust',craft?`${number(craft.deliveredThrustN/1000,2)} kN`:'—');put('engine-state',craft?(craft.engineEnabled?'Physical engine enabled':'Physical engine off'):'No physical sample');put('velocity',craft?`${number(Math.hypot(...craft.velocityMps),1)} m/s`:'—');put('fuel',craft?`${number(craft.fuelKg,1)} kg`:'—');put('pipa',frame.pipa.deliveredCounts.join(' / '));
  const list=events(),event=(selectedEventId?item.events.find(e=>e.id===selectedEventId):null)??lastAt(list,time)??snapshot.event;
  if(event){put('event-kind',`${event.kind.toUpperCase()} / RECORDED`);put('event-title',event.title);put('event-description',event.description);put('event-source',`CPU ${formatTime(event.t)} · cycle ${event.cycle} · raw line ${event.source.rawLine} · ${item.sources.tracePath}`);}
  document.querySelectorAll('[data-event]').forEach(button=>{const active=button.dataset.event===event?.id;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  $('state-vector').replaceChildren();pair($('state-vector'),'Physical r · basic REF · m',vector(craft?.positionM));pair($('state-vector'),'Physical v · basic REF · m/s',vector(craft?.velocityMps));pair($('state-vector'),'Body → REF quaternion · w/x/y/z',vector(craft?.quaternion,7));pair($('state-vector'),'Physical sample source',craft?`cycle ${craft.source.cycle} · line ${craft.source.rawLine}`:'Unavailable');
  const nav=lastAt(selectedEventId?item.navigationSamples.filter(row=>row.source.rawLine<=snapshot.source.rawLine):item.navigationSamples,time);pair($('state-vector'),'Original navigation r · IMU stable member · m',vector(nav?.positionM));pair($('state-vector'),'Original navigation v · IMU stable member · m/s',vector(nav?.velocityMps));pair($('state-vector'),'Original navigation time · PIPTIME / 100',nav?`${number(nav.timeSeconds,2)} s · cycle ${nav.source.cycle} · raw line ${nav.source.rawLine}`:'Unavailable');pair($('state-vector'),'Generated PIPA counts',frame.pipa.generatedCounts.join(' / '));
  put('scene-state',craft?'AUTHORITATIVE RETAINED PHYSICAL OBSERVATION':'NO PHYSICAL OBSERVATION AT THIS TIME');put('scene-caption',craft?(craft.engineEnabled?'Engine thrust observed.':'Original guidance. Physical feedback.'):'Computer preparation.');put('scene-detail',craft?'The 3D position, velocity arrow and fixed attitude come from the backend recording. Dragging only moves your camera.':'The computer runs before physical samples begin. No spacecraft trajectory is substituted.');put('scene-disclosure','Retained basic REF samples · velocity arrow indicates motion, not a target · LM enlarged / geometry not to scale · no attitude tracking demonstrated');drawScene(snapshot);
}
function tick(now){if(disposed)return;if(playing&&mode==='recorded'&&provider){time=Math.min(provider.getCase(caseId).durationSeconds,time+Math.min(.25,(now-lastPaint)/1000)*Number($('replay-speed').value));selectedEventId=null;if(time>=provider.getCase(caseId).durationSeconds)playing=false;renderRecorded();}lastPaint=now;requestAnimationFrame(tick);}

$('historical-mode').addEventListener('click',()=>setMode('historical'));
$('recorded-mode').addEventListener('click',()=>setMode('recorded'));
$('retry').addEventListener('click',()=>location.reload());
$('inspect-station').addEventListener('click',()=>{const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;$('flight-controls').scrollIntoView({behavior:reduced?'instant':'smooth',block:'start'});$('control-tabs').querySelector('button')?.focus({preventScroll:true});});
$('execution-case').addEventListener('change',event=>selectCase(event.target.value));
$('all-events').addEventListener('change',()=>{selectedEventId=null;renderEventList();renderRecorded();});
$('replay-time').addEventListener('input',event=>seek(Number(event.target.value)));
$('replay-restart').addEventListener('click',()=>{if(provider)seek(physicalStart(provider.getCase(caseId)));});
$('replay-play').addEventListener('click',()=>{if(!provider)return;if(time>=provider.getCase(caseId).durationSeconds)time=physicalStart(provider.getCase(caseId));playing=!playing;selectedEventId=null;renderRecorded();});
for(const [id,direction] of [['replay-previous',-1],['replay-next',1]])$(id).addEventListener('click',()=>{if(!provider)return;const event=adjacentReplayEvent(events(),time,direction,selectedEventId);if(event){seek(event.t,event.id);announce(`Recorded observation: ${event.title}`);}});
for(const [id,view] of [['vehicle-view','vehicle'],['orbit-view','orbit']])$(id).addEventListener('click',()=>{renderer?.setView(view);$('vehicle-view').setAttribute('aria-pressed',String(view==='vehicle'));$('orbit-view').setAttribute('aria-pressed',String(view==='orbit'));drawScene();});
$('camera-reset').addEventListener('click',()=>{renderer?.reset();drawScene();});$('camera-in').addEventListener('click',()=>{renderer?.zoom(-160);drawScene();});$('camera-out').addEventListener('click',()=>{renderer?.zoom(160);drawScene();});
let pointer=null;const canvas=renderer?.surface??$('mission-canvas');canvas.addEventListener('pointerdown',event=>{pointer={id:event.pointerId,x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);});canvas.addEventListener('pointermove',event=>{if(!pointer||event.pointerId!==pointer.id)return;renderer?.orbit(event.clientX-pointer.x,event.clientY-pointer.y);pointer.x=event.clientX;pointer.y=event.clientY;drawScene();});for(const name of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(name,()=>{pointer=null;});canvas.addEventListener('wheel',event=>{event.preventDefault();renderer?.zoom(event.deltaY);drawScene();},{passive:false});
$('mission-canvas').addEventListener('mission-renderer-status',event=>{put('renderer-kind',event.detail.available?renderer.kind.toUpperCase():'GRAPHICS UNAVAILABLE / VIEW HELD');if(!event.detail.available){playing=false;put('scene-disclosure',event.detail.message);put('replay-play','Play recording');}else drawScene();announce(event.detail.message);});
new ResizeObserver(()=>{renderer?.resize();drawScene();}).observe($('mission-scene'));
document.addEventListener('visibilitychange',()=>{if(document.hidden){playing=false;if(provider)renderRecorded();}});window.addEventListener('pagehide',()=>{playing=false;disposed=true;renderer?.dispose();});

drawScene();requestAnimationFrame(tick);
const loadResults=await Promise.allSettled([
  fetch('./data/apollo-operations.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`Historical references could not load (${response.status}).`);return response.json();}).then(validateOperations).then(data=>{operations=data;renderOperations();}),
  PropulsionTraceProvider.load().then(data=>{provider=data;for(const id of ['recorded-mode','execution-case','replay-time','replay-play'])$(id).disabled=false;if(mode==='recorded')selectCase(caseId);}),
]);
const errors=loadResults.filter(result=>result.status==='rejected').map(result=>result.reason.message);if(errors.length)showError(errors.join(' '));
