import { RecordedTraceProvider, EXECUTION_MODES } from './mission-provider.mjs';
import { renderDSKY } from './dsky-view.mjs';
import { createFlightRenderer } from './spacecraft-3d.mjs';
import { procedureSelection } from './procedure-state.mjs';

const $=id=>document.getElementById(id);
const text=(id,value)=>{$(id).textContent=value;};
let provider=null,scenario='nominal',index=-1,renderer=null;
const stepButtons=[];
const number=value=>Number.isFinite(value)?`${value.toFixed(2)} s`:'Unavailable';

function paintModel(){
  // Presentation pose only: Phase 10 supplies no attitude quaternion.
  renderer?.draw({quaternion:[1,0,0,0],targetQuaternion:null,available:true});
  text('procedure-renderer',renderer?.kind.toUpperCase() || 'MODEL UNAVAILABLE');
}
try{renderer=createFlightRenderer($('procedure-canvas'));paintModel();}
catch(error){text('procedure-renderer','MODEL UNAVAILABLE');$('procedure-canvas').setAttribute('aria-label',`3D model unavailable: ${error.message}`);}

function render(){
  if(!provider)return;
  const selected=procedureSelection(provider,scenario,index),{snapshot,step,steps}=selected;
  text('execution-mode',EXECUTION_MODES.recorded);
  $('current-task').setAttribute('aria-busy','false');
  $('procedure-scenario').disabled=false;
  text('step-count',`${steps.length} observations`);
  if(stepButtons.length!==steps.length){
    $('procedure-steps').replaceChildren();stepButtons.length=0;
    steps.forEach((item,position)=>{
      const li=document.createElement('li'),button=document.createElement('button'),ordinal=document.createElement('span');
      ordinal.textContent=String(position+1).padStart(2,'0');
      button.type='button';button.append(ordinal,document.createTextNode(item.title));
      button.addEventListener('click',()=>select(position));li.append(button);$('procedure-steps').append(li);stepButtons.push(button);
    });
  }
  stepButtons.forEach((button,position)=>{
    if(position===index)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');
    button.setAttribute('aria-label',`Inspect recorded checkpoint ${position+1}: ${steps[position].title}`);
  });
  text('task-number',index<0?'YOUR CURRENT TASK':`OBSERVATION ${index+1} OF ${steps.length} · RECORDED EVIDENCE`);
  text('task-title',step?.title ?? 'Review the guidance preparation.');
  text('task-focus',step?.focus ?? 'You are not aiming the spacecraft at a landing point in this recording. Inspect alignment, mission inputs and P63, then read the recorded crew-review display.');
  text('step-why',step?.why ?? 'The computer needs a reference orientation and coherent navigation and target inputs before calculating when a burn should begin.');
  text('step-control',step?.control ?? 'Recorded execution only');
  text('step-expect',step?.expect ?? 'Begin at the startup checkpoint. No flight or control action is implied by reviewing it.');
  $('procedure-back').disabled=index<0;
  $('procedure-next').disabled=selected.atBoundary;
  text('procedure-next',selected.atBoundary?'Recorded boundary reached':index<0?'Inspect recorded startup →':`Next: ${steps[index+1].title} →`);
  renderDSKY(document,snapshot.dsky);
  const dskySource=snapshot.dsky.source;
  text('dsky-source',dskySource?`Display observation: trace line ${dskySource.rawLine} · CPU call ${dskySource.cpuCycle}.`:'No display observation yet. Unknown digits are not filled in.');
  text('procedure-roots',snapshot.guidance.rootCount);
  text('procedure-tig',number(snapshot.guidance.ignitionTime.value));
  text('procedure-alarms',snapshot.guidance.alarms.join(' · ') || 'None observed');
  text('step-source',step?`Event: ${step.event.title} · ${step.event.t.toFixed(3)} s CPU-call time · trace line ${step.event.source.rawLine}. Not historical mission elapsed time.`:'No checkpoint selected.');
  $('mission-limit').hidden=!selected.atBoundary;
  text('limit-title',snapshot.guidance.alarms.includes('01406')?'This run ends on the recorded alarm.':'Crew continuation is not connected.');
  text('limit-copy',snapshot.guidance.alarms.includes('01406')?'The missing-site experiment recorded alarm 01406. No crew review or engine ignition is invented after that failure.':'The nominal recording reaches V06 N61, then ends without crew continuation or ignition. Engine arming, PROCEED and powered descent need verified live support.');
}
function select(position){
  index=position;render();
  text('procedure-announcement',index<0?'Recording briefing. No AGC command sent.':`Viewing recorded checkpoint ${index+1}. ${procedureSelection(provider,scenario,index).step.title}. No AGC command sent.`);
}
async function load(){
  provider=null;index=-1;stepButtons.length=0;
  $('procedure-steps').replaceChildren();$('procedure-error').hidden=true;
  renderDSKY(document,null);$('mission-limit').hidden=true;
  for(const id of ['procedure-roots','procedure-tig','procedure-alarms'])text(id,'—');
  text('dsky-source','Awaiting a recorded display observation.');text('step-source','Loading verified evidence.');
  $('procedure-next').disabled=true;$('procedure-back').disabled=true;$('procedure-scenario').disabled=true;
  $('current-task').setAttribute('aria-busy','true');
  text('execution-mode','LOADING VERIFIED RECORDING');
  try{provider=await RecordedTraceProvider.load();render();}
  catch(error){provider=null;text('execution-mode','RECORDING UNAVAILABLE');$('procedure-error').hidden=false;text('procedure-error-copy',error.message);$('current-task').setAttribute('aria-busy','false');}
}
$('procedure-next').addEventListener('click',()=>{if(provider&&index<procedureSelection(provider,scenario,index).steps.length-1)select(index+1);});
$('procedure-back').addEventListener('click',()=>{if(provider&&index>=0)select(index-1);});
$('procedure-scenario').addEventListener('change',event=>{scenario=event.target.value;select(-1);});
$('procedure-retry').addEventListener('click',load);
const canvas=$('procedure-canvas'),surface=canvas.parentElement;let pointer=null;
surface.addEventListener('pointerdown',event=>{if(event.button!==0||event.target.closest('button,a'))return;surface.setPointerCapture(event.pointerId);pointer={id:event.pointerId,x:event.clientX,y:event.clientY};});
surface.addEventListener('pointermove',event=>{if(pointer?.id!==event.pointerId)return;renderer?.orbit(event.clientX-pointer.x,event.clientY-pointer.y);pointer={...pointer,x:event.clientX,y:event.clientY};paintModel();});
for(const type of ['pointerup','pointercancel','lostpointercapture'])surface.addEventListener(type,()=>{pointer=null;});
surface.addEventListener('wheel',event=>{if(event.target.closest('button,a'))return;event.preventDefault();renderer?.zoom(event.deltaY);paintModel();},{passive:false});
$('procedure-camera-reset').addEventListener('click',()=>{renderer?.reset();paintModel();});
$('procedure-camera-in').addEventListener('click',()=>{renderer?.zoom(-140);paintModel();});
$('procedure-camera-out').addEventListener('click',()=>{renderer?.zoom(140);paintModel();});
canvas.addEventListener('flight-renderer-status',event=>text('procedure-renderer',event.detail.available?renderer.kind.toUpperCase():'MODEL UNAVAILABLE'));
window.addEventListener('resize',paintModel);
load();
