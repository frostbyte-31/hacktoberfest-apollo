/** A campaign task never advances a spacecraft or substitutes for the original computer. */
export function createCampaignTaskPanel({root,onOperate=()=>{},onContinue=()=>{},onReset=()=>{},onEvidence=()=>{},onSourceError=()=>{}}={}){
  if(!root?.ownerDocument)throw new TypeError('A campaign task root is required.');
  const doc=root.ownerDocument;
  const make=(tag,text,className)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  const top=make('div',undefined,'campaign-task-top'),mode=make('span','ORIGINAL SOFTWARE / CHECKING CONNECTION','campaign-task-mode'),progress=make('span','No verified task result yet.','campaign-task-progress');top.append(mode,progress);
  const layout=make('div',undefined,'campaign-task-layout'),copy=make('div'),label=make('p','YOUR TASK','eyebrow'),title=make('h2','Connect to the original computer.'),objective=make('p','','campaign-task-objective'),next=make('p','','campaign-task-next');next.setAttribute('role','status');next.setAttribute('aria-live','polite');copy.append(label,title,objective,next);
  const actions=make('div',undefined,'campaign-task-actions'),operate=make('button','Operate original DSKY','primary'),advance=make('button','Continue to next task'),evidence=make('button','Inspect original recording'),inspect=make('button','Inspect original software');for(const button of[operate,advance,evidence,inspect])button.type='button';actions.append(operate,advance,evidence,inspect);copy.append(actions);
  const result=make('p','','campaign-task-result');copy.append(result);
  const sourcePanel=make('details',undefined,'campaign-task-source'),summary=make('summary','The original code behind this chapter'),sourceCopy=make('p'),sources=make('ul'),missing=make('p','','campaign-task-missing');sourcePanel.append(summary,sourceCopy,sources,missing);layout.append(copy,sourcePanel);
  const foot=make('div',undefined,'campaign-task-foot'),scope=make('p'),reset=make('button','Clear saved task history');reset.type='button';foot.append(scope,reset);root.replaceChildren(top,layout,foot);
  operate.hidden=true;advance.hidden=true;evidence.hidden=true;reset.disabled=true;
  let current=null,lastPrograms=null,lastSourceStage=null,sourceFailure=null;
  operate.addEventListener('click',()=>{if(current?.stage.id==='earth-parking'&&current?.observation?.available===true)onOperate();});advance.addEventListener('click',()=>{if(current?.currentComplete&&current?.stage.id==='earth-parking')onContinue();});evidence.addEventListener('click',()=>{if(current?.recorded)onEvidence();});reset.addEventListener('click',()=>onReset());
  inspect.addEventListener('click',()=>{sourcePanel.open=true;sourcePanel.scrollIntoView?.({block:'nearest'});});
  function update({stage,status,observation,programs=null,savedCount=0,storageAvailable=true}){
    const p52=stage.id==='earth-parking',p47=stage.id==='tli',recorded=stage.evidenceIds.some(id=>id==='guidance'||id==='propulsion'),computer=observation?.snapshot?.computer,live=observation?.available===true&&observation?.snapshot?.status==='ready'&&!observation?.error;
    const currentComplete=status.complete===true&&status.currentRun===true&&live;
    current={stage,status,observation,currentComplete,recorded};
    mode.textContent=p52?(live?'LIVE ORIGINAL CMC / MODELED INSTRUMENTS':computer?'ORIGINAL CMC / LAST OBSERVATION':observation?.available?'ORIGINAL CMC / READY TO START':'ORIGINAL CMC / NOT CONNECTED'):recorded?'VERIFIED RECORDING / SEPARATE EXPERIMENT':'ORIGINAL SOURCE / FLIGHT SYSTEMS REQUIRED';
    root.dataset.taskStatus=currentComplete?'complete':status.status;
    label.textContent=`${p52?'YOUR TASK':'MISSION STAGE'}${programs?.station?` / ${programs.station.toUpperCase()}`:''}`;
    progress.textContent=`${savedCount} task result${savedCount===1?'':'s'} saved${storageAvailable?' as local history':' · saving unavailable'}`;
    title.textContent=p52?'Align Columbia’s guidance platform.':stage.title;
    objective.textContent=p52?'Use the DSKY and manual sextant to identify two stars. Review the original computer’s alignment error, approve its gyro correction, then return to P00.':stage.historicalAction;
    const serverTask=observation?.snapshot?.task;
    next.textContent=currentComplete?'Verified: the original program reached its required completion checkpoints in this run.':p52?(observation?.error?'Connection interrupted. Reconnect or refresh the computer below; no input has been retried.':observation?.snapshot?.status==='stopped'?'Computer stopped. Restart the alignment setup at the station below to begin a new attempt. Your previous result remains saved as local history.':!computer?'Open the alignment station, then choose Prepare alignment instruments. This starts the original CMC and its disclosed instrument setup.':serverTask?.nextInstruction??'Follow the actual DSKY prompt at the station below.'):p47?status.reason:recorded?'Inspect the retained original-computer outputs below. This recording is a separate experiment; watching it does not fly this mission stage.':status.reason;
    operate.hidden=!p52;operate.disabled=observation?.available!==true;operate.textContent=live?'Go to DSKY and optics':'Open alignment station';
    advance.hidden=!p52||!currentComplete;advance.textContent='Inspect departure requirements →';
    evidence.hidden=!recorded;
    const receipt=status.receipt;
    result.textContent=currentComplete?`Current run: ${receipt?.sessionId??observation?.snapshot?.sessionId??'observed'} · original program completion verified. Historical flight achieved: no.`:receipt?'A previous computer-task result is saved. It does not restore a live computer, vehicle state or flight completion.':!p52?'Flight integration for this stage remains unavailable. Its source and any related recording can be inspected independently.':computer?`Original Comanche 055 ${live?'running':'last observation'} · CPU call ${computer.cycle.toLocaleString('en-US')}. No mission maneuver is inferred from this clock.`:'A completed task requires original-computer observations. Chapter navigation and the tour cannot complete it.';
    sourceCopy.textContent=programs?'These source locations describe the program logic. A source listing alone does not provide the spacecraft hardware or a flight state.':sourceFailure?`Original source index unavailable: ${sourceFailure}`:'Original source index loading. Computer controls remain independent of this reference.';
    if(lastPrograms!==programs||lastSourceStage!==stage.id){
      sources.replaceChildren();
      for(const program of programs?.originalPrograms??[]){const li=make('li'),link=make('a',`${program.softwareId} · ${program.program??program.label} · ${program.symbol}`);link.href=program.listingUrl;link.target='_blank';link.rel='noopener';li.append(link,make('small',`${program.file}${program.line?`:${program.line}`:''} · ${program.scope}`));if(program.excerpt){const code=make('details'),codeTitle=make('summary','Read source excerpt'),pre=make('pre',program.excerpt);code.append(codeTitle,pre,make('small',`Read-only source excerpt · not an execution trace · SHA-256 ${program.sourceSha256}`));li.append(code);}sources.append(li);}
      if(programs&&!programs.originalPrograms.length)sources.append(make('li','This crew or spacecraft hardware action is not an AGC program.'));
      lastPrograms=programs;lastSourceStage=stage.id;
    }
    missing.textContent=(programs?.missingSystems??status.missingDependencies??[]).join(' · ');
    scope.textContent='Task completion, recorded evidence and historical flight are tracked separately. The 3D spacecraft shows configuration only; it does not move without authoritative flight state.';
    reset.disabled=savedCount===0;
  }
  return {update,sourceError(message){sourceFailure=message;sourceCopy.textContent=`Original source index unavailable: ${message}`;onSourceError(message);},get stageId(){return current?.stage.id??null;},dispose(){root.replaceChildren();}};
}
