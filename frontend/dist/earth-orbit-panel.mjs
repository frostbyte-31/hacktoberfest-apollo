import {EarthOrbitClient,EARTH_ORBIT_MODE} from './earth-orbit-client.mjs';

/** Seven columns with the two outer function-key pairs vertically staggered. */
export const DSKY_KEY_LAYOUT=Object.freeze([
  ['VERB',1,2],['NOUN',1,4],['+',2,1],['-',2,3],['0',2,5],
  ['7',3,1],['4',3,3],['1',3,5],['8',4,1],['5',4,3],['2',4,5],
  ['9',5,1],['6',5,3],['3',5,5],['CLR',6,1],['PRO',6,3],['KEY REL',6,5],['ENTR',7,2],['RSET',7,4],
].map(row=>Object.freeze(row)));
const LAMPS=Object.freeze(['UPLINK ACTY','TEMP','NO ATT','GIMBAL LOCK','STBY','PROG','KEY REL','RESTART','OPR ERR','TRACKER']);
const FIELDS=Object.freeze({PROG:2,VERB:2,NOUN:2,R1:5,R2:5,R3:5});
const oct=value=>Number.isSafeInteger(value)?value.toString(8).padStart(3,'0'):'?';

/** A manually operated DSKY. Camera and historical navigation never issue computer keys. */
export function createEarthOrbitPanel({root,onState=()=>{},onAction=()=>{},fetchImpl=globalThis.fetch,clientFactory=options=>new EarthOrbitClient(options),labels={}}={}) {
  if (!root?.ownerDocument) throw new TypeError('A panel root element is required.');
  const doc=root.ownerDocument,make=(tag,text,className)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  let visible=false,loading=false,disposed=false,error=null,timer=null;
  const band=make('div','CONNECTING TO ORIGINAL CMC','earth-mode'),heading=make('div',undefined,'earth-heading');
  const headingCopy=make('div');headingCopy.append(make('span','EARTH PARKING ORBIT / COLUMBIA','eyebrow'),make('h2',labels.title??'Your first computer procedure.'));
  const clock=make('p','CPU clock unavailable','earth-clock');heading.append(headingCopy,clock);
  const intro=make('p',labels.intro??'Operate Columbia’s original Comanche 055 through the DSKY. This fresh computer startup is a readiness diagnostic: it has no reconstructed Apollo 11 orbital state, validated IMU alignment or star measurements. Each button sends a hardware input; the real computer supplies the display and any readiness alarm.','earth-intro');
  const errorNode=make('div',undefined,'earth-error');errorNode.role='alert';errorNode.hidden=true;
  const toolbar=make('div',undefined,'earth-toolbar'),start=make('button','Start Columbia’s CMC','primary'),stop=make('button','Stop computer'),refresh=make('button','Refresh observation'),connect=make('button','Reconnect');
  for (const button of [start,stop,refresh,connect]) button.type='button';toolbar.append(start,stop,refresh,connect);
  const status=make('p','Connecting to the local computer service…','earth-status');status.role='status';status.setAttribute('aria-live','polite');
  const grid=make('div',undefined,'earth-grid'),instrument=make('section',undefined,'earth-instrument');instrument.setAttribute('aria-label','Columbia Command Module DSKY');
  const face=make('div',undefined,'earth-dsky-face'),lamps=make('div',undefined,'earth-lamps'),lampNodes=new Map();lamps.setAttribute('aria-label','Observed KEY REL and OPR ERR indicators; other lamp states unavailable');
  for (const label of LAMPS) {const lamp=make('span',label),value=make('b','?');lamp.title='Lamp state is not decoded by this adapter.';lamp.append(value);lamps.append(lamp);lampNodes.set(label,{lamp,value});}
  const display=make('div',undefined,'earth-display'),outputs={},signs={},activity=make('div',undefined,'earth-dsky-acty'),activityValue=make('b','?');activity.append(make('span','COMP ACTY'),activityValue);display.append(activity);
  for (const [field,length] of Object.entries(FIELDS)) {
    const cell=make('div',undefined,`earth-dsky-${field.toLowerCase()}`),label=make('span',field==='PROG'?'PROG':field),output=make('output','?'.repeat(length));
    output.setAttribute('aria-label',`Live CMC ${field}`);output.setAttribute('data-cmc-display',field);outputs[field]=output;
    cell.append(label);if(field.startsWith('R')) {const sign=make('i','?');sign.title='Register sign unavailable';sign.setAttribute('data-cmc-sign',field);signs[field]=sign;cell.append(sign);}cell.append(output);display.append(cell);
  }
  face.append(lamps,display);
  const keypad=make('div',undefined,'earth-keypad');keypad.role='group';keypad.setAttribute('aria-label','Real DSKY hardware keys');const keys=new Map();
  for (const [key,column,row] of DSKY_KEY_LAYOUT) {
    const button=make('button',key,'earth-key');button.type='button';button.dataset.cmcKey=key;button.style.gridColumn=String(column);button.style.gridRow=`${row} / span 2`;button.setAttribute('aria-label',`DSKY ${key}`);button.disabled=true;
    button.addEventListener('click',()=>run(()=>client.key(key)));keys.set(key,button);keypad.append(button);
  }
  const displaySource=make('p','No original display observation yet.','earth-display-source');
  const flash=make('p','VERB / NOUN flash request: unavailable.','earth-flash'),unknown=make('p','“?” means unknown, not off. Register signs and KEY REL, OPR ERR and COMP ACTY use observed relay bits when available; other lamps remain unknown. The flash request is reported without timed blinking. Use the on-screen Apollo keys; no keyboard flight controls are attached.','earth-unknown');
  instrument.append(make('p','COMPUTER / DISPLAY & KEYBOARD','earth-instrument-label'),face,keypad,displaySource,flash,unknown);
  const objective=make('section',undefined,'earth-objective'),taskLabel=make('span','YOUR OBJECTIVE','eyebrow'),taskTitle=make('h3','Connect to the computer.'),instruction=make('p','The server will provide the next real procedure action.','earth-instruction'),steps=make('ol',undefined,'earth-steps'),boundary=make('p','No flight or alignment completion is inferred from pressing keys.','earth-boundary');
  instruction.setAttribute('aria-live','polite');objective.append(taskLabel,taskTitle,instruction,steps,boundary);
  const lastKey=make('p','No key has been sent.','earth-last-key'),scope=make('p','This is computer procedure practice. The 3D Earth-orbit configuration remains a visual reference; no orbit is propagated.','earth-scope');
  const provenance=make('details',undefined,'earth-provenance'),summary=make('summary','Original software and input provenance'),provenanceCopy=make('p','Start the original computer to inspect its source hashes.'),sourceLink=make('a','Comanche 055 source ↗');sourceLink.href='https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html';sourceLink.target='_blank';sourceLink.rel='noopener';
  const referenceLink=make('a','DSKY hardware layout reference ↗');referenceLink.href='https://www.ibiblio.org/apollo/yaDSKY.html';referenceLink.target='_blank';referenceLink.rel='noopener';
  provenance.append(summary,provenanceCopy,sourceLink,referenceLink);grid.append(instrument,objective);root.replaceChildren(band,heading,intro,toolbar,status,errorNode,grid,lastKey,scope,provenance);root.classList.add('earth-orbit-panel');
  const client=clientFactory({fetchImpl,onState:()=>{render();publish();},onError:message=>{error=message;render();publish();}});
  function publicState() {return Object.freeze({available:client.available,loading,visible,busy:client.busy,snapshot:client.state,error});}
  function publish() {if (!disposed) onState(publicState());}
  function render() {
    if (disposed) return;
    const snapshot=client.state,computer=snapshot?.computer,busy=loading||client.busy,ready=visible&&client.available&&!error&&!busy&&snapshot?.status==='ready';
    root.setAttribute('aria-busy',String(busy));band.textContent=loading?'CONNECTING TO ORIGINAL CMC':computer?(error||snapshot?.status==='stopped'||snapshot?.status==='error'?'ORIGINAL CMC / LAST OBSERVATION':labels.mode??EARTH_ORBIT_MODE):client.available?'ORIGINAL CMC / READY TO START':'ORIGINAL CMC / UNAVAILABLE';
    band.classList.toggle('earth-mode-stale',Boolean(error)||snapshot?.status==='error'||snapshot?.status==='stopped');
    clock.textContent=computer?`${computer.cpuSeconds.toFixed(3)} s CPU time · ${computer.cycle.toLocaleString('en-US')} calls`:'CPU clock unavailable';
    clock.title='Elapsed original computer execution. This is not historical mission elapsed time or a spacecraft clock.';
    start.disabled=!visible||!client.available||busy;start.textContent=computer?(labels.restart??'Restart Columbia’s CMC'):(labels.start??'Start Columbia’s CMC');
    stop.disabled=!visible||!client.available||busy||snapshot?.status!=='ready';refresh.disabled=!visible||!client.available||busy;connect.disabled=!visible||busy;
    for (const [key,button] of keys) button.disabled=!ready||!client.capabilities?.supportedKeys.includes(key);
    status.textContent=loading?'Connecting to the local original-computer service…':busy?'Executing original software. Wait for the computer acknowledgement…':error?'Observation needs review. No key was automatically retried. Refresh or reconnect before continuing.':snapshot?.status==='stopped'?'Computer stopped. Displays retain the last observed state.':snapshot?.status==='error'?'Original execution failed. No substitute display is shown.':snapshot?.status==='ready'?'Live original CMC · operate the DSKY keys one at a time.':client.message;
    errorNode.hidden=!error;errorNode.textContent=error??'';
    for (const [field,output] of Object.entries(outputs)) output.textContent=computer?.dsky[field]??'?'.repeat(FIELDS[field]);
    for (const [field,node] of Object.entries(signs)) {const sign=computer?.dsky.signs?.[field];node.textContent=sign===undefined||sign===null?'?':sign;node.title=sign==='+'?'Observed positive sign':sign==='-'?'Observed negative sign':sign===' '?'Observed unlit sign':'Register sign unavailable';}
    for (const [label,field] of [['KEY REL','keyRelease'],['OPR ERR','operatorError']]) {const value=computer?.dsky.lamps?.[field],node=lampNodes.get(label),known=typeof value==='boolean';node.value.textContent=known?(value?'ON':'OFF'):'?';node.lamp.classList.toggle('earth-lamp-on',value===true);node.lamp.classList.toggle('earth-lamp-off',value===false);node.lamp.setAttribute('data-cmc-lamp',field);node.lamp.setAttribute('aria-label',`${label}: ${known?(value?'observed on':'observed off'):'unavailable'}`);node.lamp.title=known?'Original channel 011 indicator bit':'Indicator bit unavailable';}
    const acty=computer?.dsky.lamps?.computerActivity;activityValue.textContent=typeof acty==='boolean'?(acty?'ON':'OFF'):'?';activity.classList.toggle('earth-activity-on',acty===true);activity.setAttribute('aria-label',`Computer activity: ${typeof acty==='boolean'?(acty?'observed on':'observed off'):'unavailable'}`);
    const flashRequest=computer?.dsky.lamps?.verbNounFlash;flash.textContent=`VERB / NOUN flash request: ${typeof flashRequest==='boolean'?(flashRequest?'active':'clear'):'unavailable'} · no timed blink animation.`;
    instrument.classList.toggle('earth-stale',Boolean(error)||snapshot?.status==='stopped'||snapshot?.status==='error');
    const source=computer?.dskySource;displaySource.textContent=source?`Original channel ${oct(source.channel)} relay digits/signs · last relay at CPU call ${source.cycle.toLocaleString('en-US')}. Decoded indicators use held original channel 011 bits${error||snapshot?.status==='stopped'||snapshot?.status==='error'?' · last observation / stale':''}.`:'No original DSKY channel observation is available. Unknown digits remain “?”.';
    const task=snapshot?.task;taskTitle.textContent=task?.title??'Connect to the computer.';instruction.textContent=task?.nextInstruction??client.message;
    steps.replaceChildren(...(task?.steps??[]).map(step=>{const li=make('li',undefined,step.complete?'complete':step.active?'active':'');li.append(make('span',step.complete?'OBSERVED':step.active?'NEXT':'PENDING','earth-step-state'),make('strong',step.title),make('p',step.description));if(step.active)li.setAttribute('aria-current','step');return li;}));
    taskLabel.textContent=task?.complete?'COMPUTER CHECKPOINT OBSERVED':'YOUR OBJECTIVE';boundary.textContent=task?.scope??'No flight or alignment completion is inferred from pressing keys.';
    const key=computer?.lastKey;lastKey.textContent=key?`Last applied key: ${key.key} · sequence ${key.sequence} · channel ${oct(key.channel)} · code ${oct(key.code)} octal · CPU call ${key.cycle.toLocaleString('en-US')}. This identifies the hardware input; the display above is the computer’s response.`:'No key has been sent from this session.';
    scope.textContent=client.capabilities?.scope??'Original execution is unavailable. The historical chapter remains a visual reference; no substitute computer is run.';
    if (computer) {provenanceCopy.textContent=`Software: ${computer.software}. Rope SHA-256: ${computer.provenance.ropeSha256}. Engine SHA-256: ${computer.provenance.engineSha256}. Session: ${snapshot.sessionId}. Original CPU clock: 12 / 1,024,000 seconds per call. Flight executed: no. Original P52 completion observed: ${task?.alignmentCompleted===true?'yes':'no'}.`;sourceLink.href=computer.provenance.sourceUrl;}
  }
  function clearPoll() {if(timer!==null){clearTimeout(timer);timer=null;}}
  function schedule() {clearPoll();if(disposed||!visible||doc.hidden||!client.available||client.state?.status!=='ready'||error)return;timer=setTimeout(async()=>{if(!client.busy){try{await client.refresh();}catch{/* The client publishes the explicit failure. */}finally{render();publish();}}schedule();},1000);}
  async function run(operation) {if(disposed||loading||client.busy)return;onAction();clearPoll();error=null;const promise=operation();render();publish();try {await promise;}catch(failure){error=failure.message;}finally {render();publish();schedule();}}
  async function load() {if(disposed||loading||client.busy)return;loading=true;error=null;clearPoll();render();publish();try {await client.connect();}catch(failure){error=failure.message;}finally {loading=false;render();publish();schedule();}}
  start.addEventListener('click',()=>run(()=>client.start()));stop.addEventListener('click',()=>run(()=>client.stop()));refresh.addEventListener('click',()=>run(()=>client.refresh()));connect.addEventListener('click',load);
  const visibility=()=>{if(doc.hidden)clearPoll();else schedule();};doc.addEventListener('visibilitychange',visibility);
  render();
  return {load,instrument(control,value){if(typeof client.instrument!=='function')throw new Error('This console has no instrument provider.');return run(()=>client.instrument(control,value));},setVisible(value){visible=value===true;render();publish();schedule();},get state(){return publicState();},dispose(){disposed=true;clearPoll();doc.removeEventListener('visibilitychange',visibility);root.replaceChildren();}};
}
