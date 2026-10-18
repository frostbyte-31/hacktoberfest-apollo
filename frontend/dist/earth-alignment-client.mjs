import {validateEarthOrbitSnapshot, EARTH_ORBIT_MODE, DSKY_KEYS, EarthOrbitClientError} from './earth-orbit-client.mjs';

export const EARTH_ALIGNMENT_MODE='LIVE ORIGINAL CMC / MODELED INSTRUMENTS';
export const INSTRUMENT_CONTROLS=Object.freeze(['power_imu','optics_mode','optics_slew','mark']);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const count=value=>Number.isSafeInteger(value)&&value>=0;
const text=value=>typeof value==='string'&&value.trim().length>0;
const angle=value=>Number.isFinite(value)&&Math.abs(value)<=360;
const copy=value=>JSON.parse(JSON.stringify(value));
const sameControl=(a,b)=>a===b||(object(a)&&object(b)&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(key=>Object.hasOwn(b,key)&&a[key]===b[key]));
function frozen(value){if(value&&typeof value==='object'){Object.values(value).forEach(frozen);Object.freeze(value);}return value;}
function invalid(reason){throw new EarthOrbitClientError(`Invalid alignment observation: ${reason}.`,{code:'invalid-snapshot'});}

/** Share the CMC clock/relay/provenance checks; validate alignment evidence separately. */
export function validateEarthAlignmentSnapshot(value){
  if(!object(value)||value.mode!==EARTH_ALIGNMENT_MODE||typeof value.task?.alignmentCompleted!=='boolean')invalid('source or task classification');
  validateEarthOrbitSnapshot({...value,mode:EARTH_ORBIT_MODE,task:{...value.task,alignmentCompleted:false}});
  if(value.computer===null){if(value.task.alignmentCompleted||value.task.complete)invalid('completion without an original computer');return value;}
  if(value.computer.mode!=='LIVE AGC EXECUTION')invalid('inner computer execution source');
  const model=value.computer.instruments;
  if(!object(model)||model.mode!=='MODELED CSM INSTRUMENTS'||typeof model.imuPowered!=='boolean'||!['MANUAL','ZERO','CMC'].includes(model.opticsMode)||!angle(model.shaftDeg)||!angle(model.trunnionDeg)||!angle(model.mechanicalTrunnionDeg)||!text(model.scope))invalid('instrument model');
  if(!count(model.markCount)||!Array.isArray(model.stars)||model.stars.length<2)invalid('optical observations');
  const codes=new Set();
  for(const star of model.stars){if(!object(star)||typeof star.code!=='string'||! /^[0-7]{2}$/.test(star.code)||codes.has(star.code)||!text(star.name)||!angle(star.shaftDeg)||!angle(star.trunnionDeg)||!Number.isFinite(star.errorDeg)||star.errorDeg<0||star.errorDeg>180)invalid('fixed star geometry');codes.add(star.code);}
  const evidence=model.alignment;
  if(!object(evidence)||!['referenceInitialized','p52Complete','torqueApproved'].every(name=>typeof evidence[name]==='boolean')||!count(evidence.p52Marks)||!count(evidence.torqueOutputCount)||!(evidence.completionCycle===null||(count(evidence.completionCycle)&&evidence.completionCycle<=value.computer.cycle)))invalid('original alignment evidence');
  if(evidence.p52Complete&&(!evidence.referenceInitialized||evidence.p52Marks<2||!evidence.torqueApproved||evidence.completionCycle===null))invalid('incomplete P52 evidence');
  if(value.task.alignmentCompleted&&!evidence.p52Complete)invalid('task and original completion disagree');
  if(value.task.complete&&!value.task.alignmentCompleted)invalid('completed task without alignment evidence');
  return value;
}

export function validateInstrumentControl(control,value){
  if(control==='power_imu')return typeof value==='boolean';
  if(control==='optics_mode')return ['MANUAL','ZERO','CMC'].includes(value);
  if(control==='mark')return ['MARK','REJECT'].includes(value);
  return control==='optics_slew'&&object(value)&&Object.keys(value).sort().join(',')==='rate,seconds,shaft,trunnion'&&['shaft','trunnion'].every(name=>Number.isFinite(value[name])&&Math.abs(value[name])<=1)&&Number.isFinite(value.seconds)&&value.seconds>0&&value.seconds<=1&&['LOW','HIGH'].includes(value.rate);
}

/** One acknowledged hardware action at a time; uncertain mutations are never retried. */
export class EarthAlignmentClient{
  #token=null;
  constructor({fetchImpl=globalThis.fetch,onState=()=>{},onError=()=>{}}={}){
    this.fetchImpl=fetchImpl;this.onState=onState;this.onError=onError;this.available=false;this.busy=false;this.state=null;this.capabilities=null;this.message='Connect to the original alignment computer.';
  }
  async #request(route,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000),headers={};
    if(this.#token)headers['X-Apollo-Token']=this.#token;
    if(body!==undefined)headers['Content-Type']='application/json';
    try{
      const response=await this.fetchImpl.call(globalThis,`/api/earth-alignment/${route}`,{method:body===undefined?'GET':'POST',headers,cache:'no-store',signal:controller.signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
      let value;try{value=await response.json();}catch{throw new EarthOrbitClientError('The alignment service returned unreadable data.',{status:response.status,code:'invalid-response'});}
      if(!response.ok)throw new EarthOrbitClientError(text(value?.error)?value.error:`Alignment service returned HTTP ${response.status}.`,{status:response.status});
      return value;
    }catch(error){if(controller.signal.aborted)throw new EarthOrbitClientError('Alignment request timed out. No input was retried; refresh the observation.',{code:'timeout'});throw error;}
    finally{clearTimeout(timer);}
  }
  #publish(value){validateEarthAlignmentSnapshot(value);this.state=frozen(copy(value));this.available=value.available&&this.#token!==null;this.message=value.error||value.task.nextInstruction;this.onState(this.state);return this.state;}
  async #run(operation){
    if(this.busy)throw new EarthOrbitClientError('Wait for the current instrument acknowledgement.',{code:'busy'});
    this.busy=true;try{return await operation();}catch(error){this.message=error.message;this.onError(error.message,error);throw error;}finally{this.busy=false;}
  }
  #require(){if(!this.available||!this.#token)throw new EarthOrbitClientError(this.message||'Alignment execution is unavailable.',{code:'unavailable'});}
  async #resync(){return this.#publish(await this.#request('status'));}
  async #post(route,body,accept=value=>this.#publish(value)){
    try{return accept(await this.#request(route,body));}catch(error){
      if(error.status===403){this.#token=null;this.available=false;error.message+=' Reconnect before sending another control.';}
      else if(error.status===409||error.status===null||error.status===undefined||error.status>=500||['invalid-snapshot','invalid-response','invalid-acknowledgement'].includes(error.code)){
        try{await this.#resync();}catch{this.available=false;error.message+=' The current observation could not be refreshed.';}
      }
      throw error;
    }
  }
  async connect(){return this.#run(async()=>{
    this.#token=null;this.available=false;
    const value=await this.#request('capabilities');
    if(!object(value)||typeof value.available!=='boolean'||value.mode!==EARTH_ALIGNMENT_MODE||value.software!=='Comanche055'||!text(value.scope)||!Array.isArray(value.supportedKeys)||!Array.isArray(value.supportedControls)||!value.supportedKeys.every(key=>DSKY_KEYS.includes(key))||!value.supportedControls.every(control=>INSTRUMENT_CONTROLS.includes(control))||new Set(value.supportedKeys).size!==value.supportedKeys.length||new Set(value.supportedControls).size!==value.supportedControls.length)throw new EarthOrbitClientError('Invalid alignment capabilities.',{code:'invalid-response'});
    const {token,...capabilities}=value;this.capabilities=frozen(copy(capabilities));
    if(!value.available||!text(token)){this.message=value.unavailableReason||'Original alignment execution is unavailable.';return null;}
    this.#token=token;this.available=true;try{return await this.#resync();}catch(error){this.available=false;throw error;}
  });}
  async refresh(){return this.#run(async()=>{this.#require();return this.#resync();});}
  async start(){return this.#run(async()=>{this.#require();return this.#post('start',{});});}
  async stop(){return this.#run(async()=>{this.#require();if(!text(this.state?.sessionId))throw new EarthOrbitClientError('No alignment session exists.');return this.#post('stop',{sessionId:this.state.sessionId});});}
  async #input(route,payload){
    this.#require();if(this.state?.status!=='ready')throw new EarthOrbitClientError('Start the alignment computer before operating it.');
    const body={sessionId:this.state.sessionId,sequence:this.state.nextSequence,...payload},before=this.state;
    return this.#post(route,body,value=>{
      validateEarthAlignmentSnapshot(value);const ack=value.ack;
      if(!object(ack)||ack.sessionId!==body.sessionId||ack.sequence!==body.sequence||value.sessionId!==body.sessionId||value.revision!==before.revision+1||value.nextSequence!==body.sequence+1||!count(ack.queuedAtCycle)||ack.queuedAtCycle<before.computer.cycle||!count(ack.afterCycle)||ack.afterCycle<ack.queuedAtCycle||value.computer.cycle!==ack.afterCycle)throw new EarthOrbitClientError('The alignment acknowledgement does not identify this action.',{code:'invalid-acknowledgement'});
      if(route==='key'&&(ack.key!==payload.key||!count(ack.channel)||ack.channel>511||!count(ack.code)||ack.code>32767||value.computer.lastKey?.key!==payload.key||value.computer.lastKey?.sequence!==body.sequence||value.computer.lastKey?.channel!==ack.channel||value.computer.lastKey?.code!==ack.code))throw new EarthOrbitClientError('The CMC did not acknowledge this DSKY key.',{code:'invalid-acknowledgement'});
      if(route==='instrument'&&(ack.control!==payload.control||!sameControl(ack.value,payload.value)))throw new EarthOrbitClientError('The instrument did not acknowledge this control.',{code:'invalid-acknowledgement'});
      return this.#publish(value);
    });
  }
  async key(key){return this.#run(async()=>{if(!DSKY_KEYS.includes(key)||!this.capabilities?.supportedKeys.includes(key))throw new EarthOrbitClientError('Unsupported DSKY key.');return this.#input('key',{key});});}
  async instrument(control,value){return this.#run(async()=>{if(!this.capabilities?.supportedControls.includes(control)||!validateInstrumentControl(control,value))throw new EarthOrbitClientError('Unsupported or invalid physical instrument control.');return this.#input('instrument',{control,value});});}
}
