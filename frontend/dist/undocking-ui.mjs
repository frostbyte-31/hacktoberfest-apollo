import {ProcedureClient} from './procedure-client.mjs';

const CREW={CDR:{name:'Neil Armstrong',station:'Commander / Eagle'},LMP:{name:'Buzz Aldrin',station:'LM Pilot / Eagle'},CMP:{name:'Michael Collins',station:'CM Pilot / Columbia'}};
const el=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
const same=(a,b)=>typeof a===typeof b&&a===b;
const kinds={'crew-report':'MANUAL CREW REPORT','select':'MODELED COCKPIT SELECTOR','momentary':'MODELED HARDWARE COMMAND'};
const nonempty=value=>typeof value==='string'&&value.trim().length>0;
const scalar=value=>(typeof value==='string'&&value.length>0&&value.length<=160)||typeof value==='boolean'||(Number.isInteger(value)&&Math.abs(value)<=2**31-1);
const stable=value=>JSON.stringify(value&&typeof value==='object'?(Array.isArray(value)?value.map(item=>JSON.parse(stable(item))):Object.fromEntries(Object.keys(value).sort().map(key=>[key,JSON.parse(stable(value[key]))]))):value);

export function validateUndockingDefinition(data){
  if(data?.schemaVersion!==1||data.mode!=='INTERACTIVE PROCEDURE TRAINER'||!Array.isArray(data.steps)||!data.steps.length||!Array.isArray(data.sources)||!data.sources.length)throw new Error('Undocking checklist format is unavailable.');
  const ids=new Set(),sources=new Set();let releases=0;
  for(const source of data.sources){const url=new URL(source.url);if(!nonempty(source.id)||sources.has(source.id)||!nonempty(source.title)||!nonempty(source.locator)||url.protocol!=='https:'||!url.hostname||url.username||url.password)throw new Error('Invalid procedure source.');sources.add(source.id);}
  for(const step of data.steps){
    if(ids.has(step.id)||!nonempty(step.id)||!Object.hasOwn(CREW,step.role)||!Object.hasOwn(kinds,step.kind)||!nonempty(step.label)||!nonempty(step.locator)||!scalar(step.correctValue)||!Array.isArray(step.sourceIds)||!step.sourceIds.length||new Set(step.sourceIds).size!==step.sourceIds.length||step.sourceIds.some(id=>!sources.has(id)))throw new Error('Invalid undocking checklist action.');
    if(step.kind==='select'&&(!nonempty(step.controlId)||!Array.isArray(step.options)||step.options.length<2||step.options.some(option=>!scalar(option.value)||!nonempty(option.label))||new Set(step.options.map(option=>`${typeof option.value}:${option.value}`)).size!==step.options.length||!step.options.some(option=>same(option.value,step.correctValue))))throw new Error('Invalid cockpit selector.');
    if(step.effect!==undefined&&step.effect!==null&&step.effect!=='release')throw new Error('Invalid procedure effect.');
    if(step.effect==='release'){releases++;if(step.role!=='CMP'||step.kind!=='momentary')throw new Error('Invalid release control.');}
    ids.add(step.id);
  }
  if(releases!==1)throw new Error('One sourced docking-release control is required.');
  return data;
}

/** Source-linked controls are rendered here; only the server advances the checklist. */
export function createUndockingTrainer({root=document,onState=()=>{},onHandoff=()=>{},humanParticipation='solo'}={}){
  const $=id=>root.getElementById(id);
  const crewLabel=humanParticipation==='shared-device'?'SHARED DEVICE':'SOLO CREW';
  let definition=null,definitionHash=null,ready=false,visible=true,role='CDR',feedback='',failure=false,verifiedState=null;
  const client=new ProcedureClient({onState:()=>{render();if(ready)onState(client.state);},onError:message=>{feedback=message;failure=true;}});
  const put=(id,text)=>{$(id).textContent=text;};
  function sourceLinks(ids){
    $('procedure-step-sources').replaceChildren();
    for(const id of ids??[]){const source=definition.sources.find(item=>item.id===id);if(!source)continue;const a=el('a',`${source.title??source.id} ↗`);a.href=source.url;a.target='_blank';a.rel='noreferrer';a.title=source.locator??'';$('procedure-step-sources').append(a);}
  }
  function coherent(){
    const state=client.state;
    if(!definition||!state)return false;
    if(state.definitionSha256!==definitionHash)throw new Error('The server and browser have different checklists. Restart the updated local server, then reload before acting.');
    if(state.currentStepIndex>definition.steps.length||state.completedStepIds.some((id,index)=>definition.steps[index]?.id!==id)||state.currentStepIndex!==state.completedStepIds.length)throw new Error('The server returned inconsistent checklist progress.');
    const finished=state.currentStepIndex===definition.steps.length;
    if(Boolean(state.currentStep)===finished||state.completed!==finished||(state.status==='complete')!==finished)throw new Error('The checklist completion state is inconsistent.');
    const release=definition.steps.find(step=>step.effect==='release');
    if((state.attachment==='released')!==state.completedStepIds.includes(release.id))throw new Error('The docking state is not supported by an acknowledged release action.');
    if(state.currentStep&&stable(definition.steps[state.currentStepIndex])!==stable(state.currentStep))throw new Error('The current cockpit action does not match this checklist.');
    return true;
  }
  function selectedStation(step){
    root.querySelectorAll('[data-crew-role]').forEach(button=>{const chosen=button.dataset.crewRole===role;button.setAttribute('aria-pressed',String(chosen));button.classList.toggle('needed',button.dataset.crewRole===step?.role);button.disabled=client.busy;});
  }
  function renderChecklist(state){
    $('procedure-checklist').replaceChildren(...definition.steps.map((step,index)=>{
      const done=state.completedStepIds.includes(step.id),current=state.currentStep?.id===step.id,li=el('li',undefined,`procedure-checklist-row${done?' complete':''}${current?' current':''}`);
      li.append(el('span',done?'✓':String(index+1).padStart(2,'0')));const text=el('span',step.label);text.append(el('small',`${step.role} · ${step.locator}`));li.append(text);if(current)li.setAttribute('aria-current','step');return li;
    }));
    $('procedure-action-log').replaceChildren(...state.events.map(event=>el('li',`Revision ${event.revision} · ${event.role} · ${event.evidenceKind} · ${event.action}: ${String(event.value)} · ${event.advanced?'step accepted':'setting needs correction'}`)));
  }
  function renderCommand(step,state){
    const target=$('procedure-command');target.replaceChildren();
    if(!step)return;
    const permitted=role===step.role&&ready&&client.available&&!client.busy;
    const selector=step.kind==='select'?step:step.kind==='momentary'?definition.steps.find(item=>item.kind==='select'&&item.controlId===step.controlId):null;
    if(selector){
      const panel=el('div',undefined,'procedure-switch');panel.append(el('span',step.controlLabel??step.label));
      const positions=el('div',undefined,'switch-positions');positions.setAttribute('role','group');positions.setAttribute('aria-label',step.controlLabel??step.controlId??step.label);
      for(const option of selector.options){const button=el('button',option.label);button.type='button';button.dataset.procedureValue=String(option.value);button.disabled=!permitted;const selected=Object.hasOwn(state.controls,step.controlId)&&same(state.controls[step.controlId],option.value);button.setAttribute('aria-pressed',String(selected));button.classList.toggle('selected',selected);button.addEventListener('click',()=>act(step,option.value));positions.append(button);}
      panel.append(positions,el('small',step.kind==='momentary'?'Browser control proxy: one discrete command. Switch timing and probe transit are not modeled.':'Readback: procedure-model selection. No spacecraft sensor or AGC readback.'));target.append(panel);
    }else{
      const button=el('button',step.actionLabel??(step.kind==='crew-report'?'Report this check complete':`Operate ${step.controlLabel??step.label}`),step.kind==='momentary'?'procedure-momentary':'primary');button.type='button';button.disabled=!permitted;button.id='procedure-apply';button.addEventListener('click',()=>act(step,step.correctValue));target.append(button);
      target.append(el('p',step.kind==='crew-report'?'You are making a manual crew report. The server does not infer a sensor observation.':'This sends one discrete command to the docking procedure model. Electrical transit timing is not simulated.','boundary'));
    }
    $('procedure-wrong-station').hidden=role===step.role;
    put('procedure-wrong-station',`This trainer assigns this check to ${CREW[step.role].name} aboard ${step.role==='CMP'?'Columbia':'Eagle'}. Select that crew station above.`);
  }
  function render(){
    if(ready&&!client.available)ready=false;
    if(ready){try{coherent();verifiedState=client.state;}catch(error){ready=false;feedback=error.message;failure=true;}}
    const state=verifiedState??client.state,active=Boolean(verifiedState?.sessionId);
    $('historical-station').closest('aside').classList.toggle('procedure-active',active);
    root.body?.classList.toggle('procedure-available',ready);
    root.body?.classList.toggle('procedure-running',active);
    $('procedure-start').hidden=active;$('procedure-start').disabled=!ready||client.busy;
    $('procedure-jump').disabled=!ready||client.busy;
    put('procedure-jump',active?(state.completed?'Review the next step ↓':'Continue the checklist ↓'):'Begin undocking checklist ↓');
    put('procedure-start',client.busy?'Connecting…':'Begin undocking checklist');
    $('starting-reference').hidden=active;$('reference-boundary').hidden=active;
    $('procedure-live-controls').hidden=!active;$('undocking-trainer').hidden=!active||!visible;
    $('procedure-restart').disabled=!ready||client.busy;
    $('procedure-reconnect').hidden=ready;$('procedure-reconnect').disabled=client.busy;
    if(!ready){put('mission-gate',feedback||client.message||'Checking the local procedure service…');if(active){put('procedure-feedback',feedback||client.message);$('procedure-feedback').classList.add('error-feedback');root.querySelectorAll('#procedure-command button,.station-picker button').forEach(button=>{button.disabled=true;});}return;}
    put('mission-gate','Source-backed procedure model. Original AGC execution, physical sensors and orbital motion are not connected to this chapter.');
    if(!active){put('opening-role',`${crewLabel} / TWO SPACECRAFT`);put('opening-task-title','Prepare to undock.');put('opening-task-copy','Begin the sourced checklist, then take the indicated crew station at each step.');if(failure&&feedback)put('mission-gate',`${feedback} Begin a new checklist if the local server was restarted.`);return;}
    const step=state.currentStep;
    put('opening-role',`${CREW[role].station.toUpperCase()} / ${crewLabel}`);
    put('opening-task-title',state.attachment==='released'?'Docking connection released.':'Work the undocking checklist.');
    put('opening-task-copy',state.completed?'This procedure is complete. Review the next operation before any maneuver.':'Change crew station when the checklist calls for a different astronaut.');
    put('procedure-count',`${state.completedStepIds.length} / ${definition.steps.length} ACTIONS`);put('procedure-attachment',state.attachment==='released'?'RELEASED / MODEL':'DOCKED / MODEL');
    selectedStation(step);$('procedure-handoff').hidden=!state.completed;
    if(step){put('procedure-evidence-kind',kinds[step.kind]);put('procedure-control-title',step.label);const setting=step.kind==='select'?`Checklist setting: ${String(step.correctValue)}. `:step.kind==='momentary'?`Checklist position: ${String(step.correctValue)}. `:'';put('procedure-prompt',setting+(step.instructions||step.prompt||step.description||'Follow the cited checklist instruction.'));sourceLinks(step.sourceIds);renderCommand(step,state);if(step.referenceItems?.length){const refs=el('ul',undefined,'procedure-reference-items');for(const item of step.referenceItems)refs.append(el('li',item));$('procedure-command').prepend(refs);}if(step.id==='verify-entry'){const details=el('details'),summary=el('summary','Review the assumed entry setup');details.append(summary);const list=el('ul',undefined,'procedure-reference-items');for(const item of definition.entryPreconditions??[])list.append(el('li',item.label));details.append(list);$('procedure-command').prepend(details);}}
    else{put('procedure-evidence-kind','CHECKLIST TRAINING COMPLETE');put('procedure-control-title','Next: crew inspection and separation planning.');put('procedure-prompt',definition.completion?.description??'Undocking precedes Eagle inspection, Columbia’s later separation maneuver, LM alignment and descent-orbit insertion. Flight maneuvers remain unavailable.');$('procedure-command').replaceChildren();$('procedure-wrong-station').hidden=true;sourceLinks(definition.steps.at(-1).sourceIds);}
    put('procedure-feedback',client.busy?'Waiting for the server’s acknowledgment…':feedback||state.message);$('procedure-feedback').classList.toggle('error-feedback',failure);
    put('procedure-scope',definition.scope??state.scope);
    $('procedure-preconditions').replaceChildren(...(definition.entryPreconditions??definition.entryConditions??definition.preconditions??[]).map(item=>el('li',typeof item==='string'?item:item.description??item.label??item.title??'')));
    renderChecklist(state);
  }
  async function start(){
    if(!ready||!client.available||client.busy)return;feedback='';failure=false;
    const work=client.start();render();try{await work;}catch(error){feedback=error.message;failure=true;}finally{render();onState(client.state);root.querySelector('.station-picker button.needed')?.focus({preventScroll:true});}
  }
  async function act(step,value){
    if(!ready||!client.available||client.busy||role!==step.role)return;feedback='';failure=false;
    const work=client.act(role,step.id,value);render();
    try{const result=await work;feedback=result.meaning;failure=!result.advanced;}catch(error){feedback=error.message;failure=true;}
    finally{render();onState(client.state);const current=client.state?.currentStep;const focus=current?(current.role!==role?root.querySelector(`[data-crew-role="${current.role}"]`):root.querySelector('#procedure-command button:not(:disabled)')):$('procedure-handoff');focus?.focus({preventScroll:true});}
  }
  $('procedure-start').addEventListener('click',start);$('procedure-restart').addEventListener('click',start);
  $('procedure-jump').addEventListener('click',async()=>{if(!ready||client.busy)return;if(!verifiedState?.sessionId)await start();$('historical-station').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});});
  $('procedure-handoff').addEventListener('click',()=>onHandoff());
  $('procedure-reconnect').addEventListener('click',connect);
  root.querySelectorAll('[data-crew-role]').forEach(button=>button.addEventListener('click',()=>{role=button.dataset.crewRole;feedback='';failure=false;render();}));
  async function connect(){
    feedback='';failure=false;
    try{
      const loadDefinition=fetch('./data/undocking-procedure.json',{cache:'no-store'}).then(async response=>{if(!response.ok)throw new Error('Undocking checklist sources could not load.');const text=await response.text();definition=validateUndockingDefinition(JSON.parse(text));definitionHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(byte=>byte.toString(16).padStart(2,'0')).join('');});
      const connection=client.connect();render();await Promise.all([loadDefinition,connection]);ready=client.available&&coherent();
      if(!ready)feedback=client.message;else{feedback='';failure=false;}
    }catch(error){ready=false;feedback=error.message;failure=true;}
    render();onState(verifiedState);
  }
  render();
  return {connect,get state(){return verifiedState;},get definition(){return definition;},get ready(){return ready&&client.available;},setVisible(value){visible=value;render();},render};
}
