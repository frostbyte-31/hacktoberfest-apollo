import {createCampaignState,selectCampaignStage,nextCampaignStage,previousCampaignStage,reviewCampaignStage,assessMissionAvailability} from './campaign-state.mjs';
import {createCampaignViewer,buildCampaignConfiguration} from './campaign-view.mjs';
import {createAgcShowcase} from './agc-showcase.mjs';
import {createEarthOrbitPanel} from './earth-orbit-panel.mjs?v=p52-1';
import {createEarthAlignmentPanel} from './earth-alignment-panel.mjs?v=p52-2';
import {createCampaignTaskPanel} from './campaign-task-panel.mjs';
import {campaignTaskStatus,observeCampaignTaskSnapshot,invalidateCampaignTaskSession,readCampaignTaskProgress,saveCampaignTaskProgress,resetCampaignTaskProgress,serializeCampaignTaskProgress} from './campaign-task-state.mjs';
import {validateCampaignProgramIndex} from './campaign-programs.mjs';

const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const diagnostic=params.get('task')==='diagnostic';
let state=null,availability=null,viewer=null,showcase=null,touring=false,timer=null,waitingForEvidence=false,finished=false,loadController=null,earthPanel=null,cmcAvailable=false;
let alignmentObserved=false;
let taskPanel=null,observation=null,programIndex=null,taskProgress,taskStorage=null,storageAvailable=true,lastSavedHistory=null,historyClearedSessionId=null;
try{taskStorage=globalThis.localStorage;}catch{storageAvailable=false;}
taskProgress=readCampaignTaskProgress(taskStorage);
const computerCapability=()=>`${diagnostic?'LIVE CMC TASK / AVAILABLE':alignmentObserved?'P52 OBSERVED / MODELED INSTRUMENTS':'LIVE P52 / AVAILABLE'} · FULL FLIGHT / UNAVAILABLE`;
const stageButtons=new Map(),goalNodes=new Map();
const make=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
function clearTimer(){if(timer!==null){clearTimeout(timer);timer=null;}}
function pauseTour(){touring=false;waitingForEvidence=false;clearTimer();showcase?.pause();renderTransport();}
function evidenceKind(){return state?.currentStage.evidenceIds.find(id=>id==='guidance'||id==='propulsion')??null;}
function updateTask(){
  if(!state||!taskPanel)return;
  const status=campaignTaskStatus(taskProgress,state.currentStageId,{alignmentAvailable:cmcAvailable});
  $('campaign-task').hidden=diagnostic;
  taskPanel.update({stage:state.currentStage,status,observation,programs:programIndex?.stages.find(item=>item.stageId===state.currentStageId),savedCount:taskProgress.receipts.length,storageAvailable});
  for(const item of state.catalog.stages){
    const button=stageButtons.get(item.id);if(!button)continue;
    const task=campaignTaskStatus(taskProgress,item.id,{alignmentAvailable:cmcAvailable});
    button.dataset.taskStatus=task.status;
    button.querySelector('small').textContent=task.currentRun?'ORIGINAL TASK VERIFIED':task.complete?'SAVED TASK HISTORY':task.canOperate?'PLAY ORIGINAL CMC':item.evidenceIds.includes('undocking-trainer')?'SEPARATE CHECKLIST TRAINER':item.evidenceIds.length?'SEPARATE RECORDED EVIDENCE':'FLIGHT SYSTEMS REQUIRED';
  }
}
function observeTask(value){
  observation=value;cmcAvailable=value.available;alignmentObserved=value.snapshot?.task.complete===true;
  if(value.error||!value.available){taskProgress=invalidateCampaignTaskSession(taskProgress);}
  else if(!diagnostic&&value.snapshot&&(historyClearedSessionId===null||value.snapshot.sessionId!==historyClearedSessionId)){
    try{
      taskProgress=observeCampaignTaskSnapshot(taskProgress,value.snapshot);
      const saved=serializeCampaignTaskProgress(taskProgress);
      if(saved!==lastSavedHistory){storageAvailable=saveCampaignTaskProgress(taskStorage,taskProgress);lastSavedHistory=saved;}
    }catch(error){
      // Invalid/stale observations cannot retain a claim about a live run.
      taskProgress=readCampaignTaskProgress(taskStorage);
      observation={...value,error:`Task qualification needs a fresh observation: ${error.message}`};
    }
  }
  updateTask();const goal=goalNodes.get('lunar-orbit');if(goal)goal.querySelector('small').textContent=cmcAvailable?computerCapability():'FULL FLIGHT / UNAVAILABLE';
}
function renderTransport(){
  document.body.classList.toggle('earth-playing',Boolean(state?.currentStageId==='earth-parking'&&!touring));
  const ready=Boolean(state);$('tour-start').disabled=!ready||touring;$('tour-pause').disabled=!touring;$('tour-restart').disabled=!ready;
  $('tour-start').textContent=finished?'Replay guided tour':state?.cursor?'Resume guided tour':'Start guided tour';
  $('previous-chapter').disabled=!ready||state.cursor===0;$('next-chapter').disabled=!ready||state.cursor===state.catalog.stages.length-1;$('review-chapter').disabled=!ready||state.reviewedStageIds.includes(state.currentStageId);
  $('review-chapter').textContent=ready&&state.reviewedStageIds.includes(state.currentStageId)?'Reference reviewed':'Mark reference reviewed';
  $('tour-status').textContent=!ready?'Loading the sourced mission sequence…':finished?'Historical tour complete. No flight was executed.':touring?(waitingForEvidence?'Tour paused on a genuine recorded AGC excerpt. Exact observations advance every 2.5 seconds; the mission reference resumes afterward.':'Touring historical references in chronological order. Chapters advance after 8 seconds; no spacecraft is being flown.'):state?.currentStageId==='earth-parking'?'Play the original CMC task below. Historical chapter navigation and the optional tour remain separate from live computer input.':'Explore at your pace, or start the guided tour. Historical GET labels are references, not a running mission clock.';
}
function scheduleNext(delay=8000){clearTimer();if(!touring)return;timer=setTimeout(advanceTour,delay);}
function advanceTour(){
  if(!touring||!state)return;clearTimer();state=reviewCampaignStage(state);
  if(state.cursor===state.catalog.stages.length-1){touring=false;finished=true;render();$('tour-complete').scrollIntoView({block:'center'});return;}
  state=nextCampaignStage(state);render();paceTour();
}
function paceTour(resume=false){
  if(!touring)return;const kind=evidenceKind();
  if(kind){
    waitingForEvidence=true;renderTransport();
    $('evidence-insert').scrollIntoView({block:'start'});
    if(!showcase?.state.available){$('tour-status').textContent='Verified excerpt unavailable. Tour paused here; retry the recording, or use Next chapter to continue reviewing references.';touring=false;renderTransport();$('tour-status').textContent='Tour paused: verified recording unavailable. Retry the recording or continue with Next chapter.';return;}
    if(resume&&showcase.state.excerptComplete){waitingForEvidence=false;renderTransport();scheduleNext(5000);}
    else{if(!resume)showcase.restart();showcase.play();}
  }else{waitingForEvidence=false;renderTransport();document.querySelector('.campaign-scene').scrollIntoView({block:'start'});scheduleNext();}
}
function render(){
  if(!state)return;const stage=state.currentStage,goal=state.catalog.goals.find(item=>item.id===stage.goalId),goalIndex=state.catalog.goals.indexOf(goal);
  const configuration=stage.id==='lunar-ascent'?'ascent':['lm-preparation','undocking-inspection'].includes(stage.id)?'docked-csm-lm-deployed':stage.configuration,model=buildCampaignConfiguration(configuration);
  $('chapter-title').textContent=stage.title;$('historical-time').textContent=stage.getLabel;$('chapter-description').textContent=stage.description;$('historical-action').textContent=stage.historicalAction;
  $('stage-vehicle').textContent=stage.vehicle;$('stage-computer').textContent=stage.computer;$('stage-authority').textContent=stage.controlAuthority;
  $('current-goal').textContent=`GOAL ${String(goalIndex+1).padStart(2,'0')} / ${goal.title.toUpperCase()}`;$('chapter-number').textContent=`CHAPTER ${String(stage.order).padStart(2,'0')} / 16`;
  $('configuration-label').textContent=model.label;
  $('configuration-note').textContent=stage.id==='earth-parking'||stage.id==='tli'?'Eagle is stowed inside the closed SLA. The launch escape tower is already gone.':stage.id==='entry-splashdown'?'Only the Command Module enters the atmosphere. The Service Module has been discarded.':stage.id==='lunar-ascent'?'Only the ascent stage leaves the Moon. The descent stage and landing gear remain on the surface.':stage.vehicle;
  $('campaign-canvas').setAttribute('aria-label',`${model.label}. Schematic three-dimensional visual reference, not to scale. No flight is simulated.`);
  const moon=stage.order>=5&&stage.order<=14;$('reference-body').textContent=moon?'MOON REFERENCE':'EARTH REFERENCE';document.querySelector('.campaign-scene').classList.toggle('moon',moon);viewer?.draw(configuration);
  $('review-count').textContent=`${state.reviewedStageIds.length} / 16 REVIEWED`;
  for(const item of state.catalog.stages){const button=stageButtons.get(item.id);button.setAttribute('aria-current',item.id===stage.id?'step':'false');button.querySelector('small').textContent=state.reviewedStageIds.includes(item.id)?'REFERENCE REVIEWED':item.evidenceIds.length?'REFERENCE + SEPARATE EVIDENCE':'HISTORICAL REFERENCE';}
  for(const item of state.catalog.goals){const node=goalNodes.get(item.id);node.classList.toggle('active',item.id===goal.id);node.querySelector('small').textContent=item.id==='lunar-orbit'&&cmcAvailable?computerCapability():'FULL FLIGHT / UNAVAILABLE';}
  $('stage-sources').replaceChildren(...stage.sourceIds.map(id=>{const source=state.catalog.sources.find(item=>item.id===id),a=make('a',`${source.title} ↗`);a.href=source.url;a.target='_blank';a.rel='noopener';a.title=source.locator;return a;}));
  $('flight-gate').textContent=`This chapter can be explored as a historical reference. ${stage.evidenceIds.length?'Related evidence is identified separately below.':'No original-computer flight execution is connected for this stage.'}`;
  $('missing-capability').textContent=availability.stageAvailability[stage.id].missingCapabilities.join(', ');
  const earth=stage.id==='earth-parking';$('earth-console').hidden=!earth;$('earth-open').hidden=!earth;$('earth-task-links').hidden=!earth;earthPanel?.setVisible(earth);
  const kind=evidenceKind();$('evidence-insert').hidden=!kind;$('trainer-insert').hidden=!stage.evidenceIds.includes('undocking-trainer');
  if(kind){showcase?.show(kind);$('evidence-title').textContent=kind==='guidance'?'How the original computer prepares guidance.':'Original engine commands and sensor feedback.';}else showcase?.pause();
  $('tour-complete').hidden=!finished;
  updateTask();
  const url=new URL(location.href);url.searchParams.set('stage',stage.id);url.searchParams.delete('tour');history.replaceState(null,'',url);
  renderTransport();
}
function buildNavigation(){
  stageButtons.clear();goalNodes.clear();$('chapter-list').replaceChildren();$('goal-cards').replaceChildren();
  for(const goal of state.catalog.goals){const article=make('article',undefined,'campaign-goal');article.append(make('span',`GOAL ${String(state.catalog.goals.indexOf(goal)+1).padStart(2,'0')}`,'eyebrow'),make('h2',goal.title),make('p',goal.summary),make('small','FULL FLIGHT / UNAVAILABLE'));goalNodes.set(goal.id,article);$('goal-cards').append(article);}
  for(const stage of state.catalog.stages){const li=make('li'),button=make('button');button.type='button';const text=make('span',stage.title);text.append(make('small','HISTORICAL REFERENCE'));button.append(make('span',String(stage.order).padStart(2,'0')),text);button.addEventListener('click',()=>{pauseTour();finished=false;state=selectCampaignStage(state,stage.id);render();});stageButtons.set(stage.id,button);li.append(button);$('chapter-list').append(li);}
}
async function load(){
  loadController?.abort();loadController=new AbortController();const timeout=setTimeout(()=>loadController.abort(),10000);$('campaign-error').hidden=true;
  try{
    const response=await fetch('./data/apollo-campaign.json',{signal:loadController.signal,cache:'no-cache'});if(!response.ok)throw new Error(`Mission catalog returned HTTP ${response.status}.`);
    state=createCampaignState(await response.json());availability=assessMissionAvailability(state.catalog);
    if(params.has('stage')){try{state=selectCampaignStage(state,params.get('stage'));}catch{/* Unknown bookmarks safely start in Earth orbit. */}}
    buildNavigation();render();
    if(params.get('play')==='1')$(diagnostic?'earth-console':'campaign-task').scrollIntoView({block:'start'});
    if(params.get('tour')==='1'){state=createCampaignState(state.catalog);render();touring=true;finished=false;renderTransport();paceTour();}
  }catch(error){$('campaign-error').hidden=false;$('campaign-error-copy').textContent=error.message;}
  finally{clearTimeout(timeout);}
}
taskPanel=createCampaignTaskPanel({root:$('campaign-task'),onOperate:()=>{pauseTour();$('earth-console').scrollIntoView({block:'start'});},onContinue:()=>{pauseTour();state=nextCampaignStage(state);render();$('campaign-task').scrollIntoView({block:'start'});},onEvidence:()=>{pauseTour();$('evidence-insert').scrollIntoView({block:'start'});},onReset:()=>{historyClearedSessionId=observation?.snapshot?.sessionId??null;taskProgress=resetCampaignTaskProgress();storageAvailable=saveCampaignTaskProgress(taskStorage,taskProgress);lastSavedHistory=serializeCampaignTaskProgress(taskProgress);updateTask();}});
async function loadProgramIndex(){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
  try{const response=await fetch('./data/campaign-programs.json',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);programIndex=validateCampaignProgramIndex(await response.json());updateTask();}
  catch(error){taskPanel.sourceError(error.message);}
  finally{clearTimeout(timeout);}
}
try{viewer=createCampaignViewer($('campaign-canvas'));new ResizeObserver(()=>viewer?.draw()).observe($('campaign-canvas'));}catch(error){$('graphics-status').textContent=`3D configuration unavailable: ${error.message}. Historical text and sources remain accessible.`;}
try{showcase=createAgcShowcase({root:$('agc-showcase'),canvas:$('agc-canvas'),onState:record=>{
  $('retry-recording').hidden=!record.error;
  if(touring&&waitingForEvidence&&record.available&&!record.excerptComplete){renderTransport();if(!record.playing)$('tour-status').textContent='The recorded excerpt is paused. Use Play observations to continue, or Pause tour to explore.';}
  if(touring&&waitingForEvidence&&record.excerptComplete&&!record.playing){waitingForEvidence=false;renderTransport();$('tour-status').textContent='Verified excerpt complete. Resuming the historical reference in 5 seconds; no flight maneuver was completed.';scheduleNext(5000);}
}});showcase.load();}catch(error){$('agc-showcase').textContent=`Verified inspector unavailable: ${error.message}. No substitute telemetry is shown.`;}
try{earthPanel=(diagnostic?createEarthOrbitPanel:createEarthAlignmentPanel)({root:$('earth-console'),onAction:pauseTour,onState:observeTask});earthPanel.load();$('earth-open').textContent=diagnostic?'Play cold-start diagnostic':'Play P52 alignment';}catch(error){$('earth-console').textContent=`Original CMC console unavailable: ${error.message}`;}
$('earth-open').addEventListener('click',()=>{pauseTour();$('earth-console').scrollIntoView({block:'start'});});
$('tour-start').addEventListener('click',()=>{if(!state)return;const resume=!finished;if(finished){state=createCampaignState(state.catalog);finished=false;render();}touring=true;renderTransport();paceTour(resume);});
$('tour-pause').addEventListener('click',pauseTour);
$('tour-restart').addEventListener('click',()=>{pauseTour();finished=false;state=createCampaignState(state.catalog);render();});
$('previous-chapter').addEventListener('click',()=>{pauseTour();finished=false;state=previousCampaignStage(state);render();});
$('next-chapter').addEventListener('click',()=>{pauseTour();finished=false;state=nextCampaignStage(state);render();});
$('review-chapter').addEventListener('click',()=>{state=reviewCampaignStage(state);render();});
$('reset-configuration').addEventListener('click',()=>viewer?.reset());$('retry-campaign').addEventListener('click',load);$('retry-recording').addEventListener('click',()=>showcase?.load());
document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseTour();});window.addEventListener('pagehide',event=>{pauseTour();if(event.persisted)return;loadController?.abort();showcase?.dispose();earthPanel?.dispose();viewer?.dispose();taskPanel?.dispose();});
load();loadProgramIndex();
