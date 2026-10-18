/** Read-only domain adapter. Original computations and all physics stay outside the UI. */
import { lastAt } from './replay.mjs';

export const RECORDED_MODE='VERIFIED RECORDED EXECUTION';
const PERIOD=12/1024000;
const FIELDS=['PROG','VERB','NOUN','R1','R2','R3'];
const vector=value=>Array.isArray(value)&&value.length===3&&value.every(Number.isFinite);
const quaternion=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)&&Math.abs(Math.hypot(...value)-1)<1e-6;
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const evidencePath=value=>typeof value==='string'&&value.startsWith('docs/')&&!value.split('/').includes('..')&&!/[?#\\]/.test(value);
const freeze=value=>{
  if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.values(value).forEach(freeze);Object.freeze(value);}return value;
};
const source=(value,cycle,rawLine=Infinity)=>value&&Number.isInteger(value.rawLine)&&value.rawLine>0&&value.rawLine<=rawLine&&Number.isInteger(value.cycle)&&value.cycle>=0&&value.cycle<=cycle;
const fail=message=>{throw new Error(`Invalid propulsion recording: ${message}`);};

const validateHeldFrame=(frame,item,previous=-1,physical=-1)=>{
  if(!Number.isInteger(frame?.cycle)||frame.cycle<=previous||!Number.isFinite(frame.t)||Math.abs(frame.t-frame.cycle*PERIOD)>1e-8||frame.t>item.durationSeconds+1e-7||!source(frame.source,frame.cycle)||frame.source.cycle!==frame.cycle)fail('observation clock or chronology');
  const heldSource=value=>source(value,frame.cycle,frame.source.rawLine);
  if(!FIELDS.every(field=>typeof frame.dsky?.[field]==='string'))fail('recorded display');
  for(const name of ['dsky','program'])if(frame.observationSources?.[name]!==null&&!heldSource(frame.observationSources?.[name]))fail('held observation source');
  const craft=frame.spacecraft;
  if(craft!==null){
    if(!craft||!vector(craft.positionM)||!vector(craft.velocityMps)||!quaternion(craft.quaternion)||!heldSource(craft.source))fail('physical position, velocity, attitude or source');
    if(!['physicalTimeSeconds','elapsedPhysicalSeconds','massKg','fuelKg','deliveredThrustN','commandedThrustN'].every(key=>Number.isFinite(craft[key]))||craft.massKg<=0||craft.fuelKg<0||craft.fuelKg>craft.massKg||craft.elapsedPhysicalSeconds<0||craft.deliveredThrustN<0||craft.commandedThrustN<0||craft.physicalTimeSeconds<physical)fail('physical clocks or quantities');
    if(typeof craft.engineEnabled!=='boolean'||typeof craft.requestedEngineEnabled!=='boolean'||typeof craft.physicalEngineConnected!=='boolean')fail('physical engine state');
    physical=craft.physicalTimeSeconds;
  }
  if(frame.receiver!==null&&(!heldSource(frame.receiver?.source)||!['armed','autothrottle','requestedEngineOn','enabled'].every(key=>typeof frame.receiver[key]==='boolean')||!Number.isInteger(frame.receiver.automaticCount)||frame.receiver.automaticCount<0||!Number.isFinite(frame.receiver.commandedThrustN)||frame.receiver.commandedThrustN<0))fail('receiver source or state');
  if(!vector(frame.pipa?.generatedCounts)||!vector(frame.pipa?.deliveredCounts)||[...frame.pipa.generatedCounts,...frame.pipa.deliveredCounts].some(value=>!Number.isInteger(value)))fail('sensor counts');
  if(frame.pipa.source!==null&&!heldSource(frame.pipa.source))fail('sensor observation source');
  for(const discrete of Object.values(frame.crewDiscretes ?? {}))if(!Number.isInteger(discrete.value)||discrete.value<0||discrete.value>0o77777||!heldSource(discrete.source))fail('hardware discrete');
  return physical;
};

export function validatePropulsion(data){
  if(data?.schemaVersion!==1||data.mode!==RECORDED_MODE||!Array.isArray(data.cases)||typeof data.scope!=='string')fail('schema or source mode');
  if(!hash(data.provenance?.releaseSealSha256)||!hash(data.provenance?.ropeSha256)||!hash(data.provenance?.dskyDecoderSha256)||!/^[a-f0-9]{40}$/.test(data.provenance?.emulatorRevision ?? '')||!evidencePath(data.provenance?.releaseSealPath)||!Number.isInteger(data.provenance?.sealedFilesChecked)||data.provenance.sealedFilesChecked<=0)fail('release provenance');
  if(data.units?.position!=='m'||data.units?.velocity!=='m/s'||data.units?.mass!=='kg'||data.units?.thrust!=='N'||data.frames?.position!=='Moon-centered basic REF inertial'||data.frames?.velocity!=='Moon-centered basic REF inertial')fail('units or coordinate frame');
  const ids=new Set();
  for(const item of data.cases){
    if(typeof item.id!=='string'||ids.has(item.id)||typeof item.title!=='string'||!Array.isArray(item.frames)||!item.frames.length||!Array.isArray(item.events)||!Number.isFinite(item.durationSeconds))fail('case identity or duration');
    ids.add(item.id);
    if(!hash(item.sources?.rawSha256)||!hash(item.sources?.gzipSha256)||!evidencePath(item.sources?.tracePath)||!Number.isInteger(item.sources?.rawBytes)||item.sources.rawBytes<=0||!Number.isFinite(item.initialGeometry?.lunarRadiusM)||item.initialGeometry.lunarRadiusM<=0||item.outcome?.allOriginalChecksPass!==true)fail('case provenance or completion');
    if(item.initialGeometry.positionFrame!==data.frames.position||item.initialGeometry.velocityFrame!==data.frames.velocity||typeof item.initialGeometry.quaternionFrame!=='string'||!item.initialGeometry.quaternionFrame.includes('body-to-basic-REF')||!/scalar-first/i.test(item.initialGeometry.quaternionFrame))fail('physical coordinate frame');
    if(typeof item.physicalEngineConnected!=='boolean'||typeof item.sensorFeedbackConnected!=='boolean')fail('causal connection flags');
    let previous=-1,physical=-1;
    for(const frame of item.frames){
      physical=validateHeldFrame(frame,item,previous,physical);
      previous=frame.cycle;
    }
    if(item.frames[0].t!==0||Math.abs(item.frames.at(-1).t-item.durationSeconds)>1e-7)fail('recorded bounds');
    if(!item.eventSnapshots||Object.keys(item.eventSnapshots).length!==item.events.length)fail('exact event observations');
    previous=-1;physical=-1;let previousLine=-1;const events=new Set();
    for(const event of item.events){
      if(typeof event.id!=='string'||!event.id||events.has(event.id)||typeof event.title!=='string'||!Number.isInteger(event.cycle)||event.cycle<previous||!Number.isFinite(event.t)||Math.abs(event.t-event.cycle*PERIOD)>1e-8||!source(event.source,event.cycle)||event.source.cycle!==event.cycle||event.source.rawLine<previousLine||event.t>item.durationSeconds+1e-7)fail('event provenance or chronology');
      const frame=item.eventSnapshots[event.id];
      if(!frame||frame.cycle!==event.cycle||frame.t!==event.t||frame.source?.rawLine!==event.source.rawLine)fail('event raw-row identity');
      physical=validateHeldFrame(frame,item,-1,physical);
      previous=event.cycle;events.add(event.id);
      previousLine=event.source.rawLine;
    }
  }
  if(!['connected','sink','no-feedback','repeat'].every(id=>ids.has(id)))fail('missing causal controls');
  return data;
}

/** The service currently exposes no live propulsion or historical cockpit command capability. */
export const MISSION_CAPABILITIES=freeze({
  recordedPropulsion:true,recordedDsky:true,recordedCrewInputs:true,recordedNavigation:true,
  liveHistoricalInitialization:false,liveUndocking:false,liveDoi:false,liveDsky:false,
  liveCockpitSwitches:false,liveThreeAxisAca:false,liveTtca:false,liveRod:false,
  livePoweredDescent:false,liveLanding:false,
});

export class PropulsionTraceProvider{
  constructor(data){this.data=freeze(structuredClone(validatePropulsion(data)));this.mode=RECORDED_MODE;this.capabilities=MISSION_CAPABILITIES;Object.freeze(this);}
  static async load(url='./data/propulsion.json',{fetchImpl=globalThis.fetch,signal}={}){
    const response=await fetchImpl(url,{cache:'no-store',signal});
    if(!response.ok)throw new Error(`Propulsion evidence could not load (${response.status}).`);
    return new PropulsionTraceProvider(await response.json());
  }
  listCases(){return this.data.cases;}
  getCase(id){const item=this.data.cases.find(item=>item.id===id);if(!item)throw new Error(`Unknown retained execution: ${id}`);return item;}
  getSnapshot(id,seconds){
    const item=this.getCase(id);if(!Number.isFinite(seconds))throw new Error('Invalid execution time.');
    const t=Math.min(item.durationSeconds,Math.max(0,seconds)),frame=lastAt(item.frames,t);
    return this.snapshot(item,frame,t,lastAt(item.events,t));
  }
  getEventSnapshot(id,eventId){
    const item=this.getCase(id),event=item.events.find(event=>event.id===eventId);
    if(!event)throw new Error(`Unknown retained event: ${eventId}`);
    return this.snapshot(item,item.eventSnapshots[eventId],event.t,event);
  }
  snapshot(item,frame,t,event){
    return freeze({mode:this.mode,availability:'recorded-observation',replay:{seconds:t,durationSeconds:item.durationSeconds,units:'s',clock:'CPU-call elapsed; not historical GET'},
      caseId:item.id,classification:item.classification,frame,capabilities:this.capabilities,
      spacecraft:frame.spacecraft?{...frame.spacecraft,mode:this.mode,units:{position:'m',velocity:'m/s',mass:'kg',fuel:'kg',force:'N'},coordinateFrame:item.initialGeometry.positionFrame,quaternionFrame:item.initialGeometry.quaternionFrame}:null,
      event,source:{...frame.source,path:item.sources.tracePath,rawSha256:item.sources.rawSha256}});
  }
  trajectoryThrough(id,seconds,{rawLine=Infinity}={}){
    if(!Number.isFinite(seconds))throw new Error('Invalid execution time.');
    if(rawLine!==Infinity&&(!Number.isInteger(rawLine)||rawLine<=0))throw new Error('Invalid source row.');
    const item=this.getCase(id),t=Math.min(item.durationSeconds,Math.max(0,seconds)),result=[];let cycle=-1;
    for(const frame of item.frames){if(frame.t>t)break;if(frame.spacecraft&&frame.spacecraft.source.rawLine<=rawLine&&frame.spacecraft.source.cycle!==cycle){result.push(frame.spacecraft.positionM);cycle=frame.spacecraft.source.cycle;}}
    return result;
  }
  async command(){return {accepted:false,status:'unavailable',mode:this.mode,reason:'This provider replays original execution. No live cockpit command was sent.'};}
}

/** Decode signal assertion only; a missing AUTO signal cannot prove ATT HOLD vs OFF. */
export function observedCockpitSignals(frame){
  const bit=(channel,mask)=>{
    const value=frame?.crewDiscretes?.[channel];
    return value?{asserted:(value.value&mask)===0,source:value.source}:null;
  };
  return {pgns:bit('030',0o1000),autoThrottle:bit('030',0o20),engineArmed:bit('030',0o4),autoAttitude:bit('031',0o20000),radarPosition1:bit('033',0o40)};
}

export function missionGate(capabilities=MISSION_CAPABILITIES){
  return capabilities?.liveHistoricalInitialization===true&&capabilities?.liveUndocking===true
    ?{available:true,reason:'Historical mission initialization and undocking supported.'}
    :{available:false,reason:'A historical orbital state, AGS/PGNS and verified separation controls are not connected. Inspect the real controls or review the validated propulsion execution.'};
}
