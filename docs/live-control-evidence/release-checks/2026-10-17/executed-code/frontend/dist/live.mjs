import { originalReadiness } from './replay.mjs';

export function heldDirection(held) {
  return {yaw:Number(held.has('yaw+'))-Number(held.has('yaw-')),
    pitch:Number(held.has('pitch+'))-Number(held.has('pitch-'))};
}

export function canPilot(session) {
  return ['ready','running'].includes(session?.status) && session?.frame?.ready === true
    && originalReadiness(session.frame.execution);
}

/** Actual backend samples only. Never integrate or extrapolate browser physics. */
export function liveSample(native) {
  if (!native?.model) return null;
  const model=native.model;
  for(const value of [model.quaternion,model.omega,model.gimbals]) {
    if(!Array.isArray(value)||!value.every(Number.isFinite))throw new Error('Invalid live telemetry.');
  }
  if(model.quaternion.length!==4||Math.abs(Math.hypot(...model.quaternion)-1)>1e-6)throw new Error('Invalid live orientation.');
  if(model.omega.length!==3||model.gimbals.length!==3)throw new Error('Invalid live rate/angle dimensions.');
  if(!Number.isFinite(native.physical_time))throw new Error('Missing authoritative model time.');
  return {cycle:native.model_cycle,t:native.physical_time,q:model.quaternion.slice(),omega:model.omega.slice(),
    gimbals:model.gimbals.slice(),torque:model.torque_Nm.slice(),alpha:model.alpha_rad_s2.slice(),
    cdu:native.cdu.slice(),readiness:{...native.execution},cpuCycle:native.cycle};
}

export class LiveClient {
  constructor(onState, onError) {
    this.onState=onState;this.onError=onError;this.token=null;this.capabilities=null;
    this.latest={status:'idle',sessionId:null,frame:null,message:'Start a fresh native AGC session.'};
    this.sequence=0;this.pendingInput=0;this.held=new Set();this.pointers=new Map();
    this.timer=null;this.generation=0;
    this.heartbeat=setInterval(()=>{if(this.held.size)this.sendInput();},150);
  }
  async api(path, body, keepalive=false) {
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),2000);
    try {
      const headers={};
      if(this.token)headers['X-Apollo-Token']=this.token;
      if(body!==undefined)headers['Content-Type']='application/json';
      const response=await fetch(path,{method:body===undefined?'GET':'POST',headers,
        body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:controller.signal,keepalive});
      const value=await response.json();
      if(!response.ok)throw new Error(value.error||`Local backend returned ${response.status}.`);
      return value;
    } finally {clearTimeout(timeout);}
  }
  async bootstrap() {
    this.capabilities=await this.api('/api/bootstrap');this.token=this.capabilities.token;
    if(!this.capabilities.liveEnabled)throw new Error('Live controls are disabled. Restart the local server without --replay-only.');
    return this.capabilities;
  }
  async start() {
    this.release(false);this.generation++;clearTimeout(this.timer);
    try {
      await this.bootstrap();this.sequence=0;this.pendingInput=0;
      this.latest=await this.api('/api/session/start',{});this.onState(this.latest,true);this.poll();
    } catch(error){this.onError(error.message);}
  }
  async poll() {
    const generation=this.generation;
    try {
      const state=await this.api('/api/status');
      if(generation!==this.generation)return;
      this.latest=state;
      if(!canPilot(state))this.release(false);
      this.onState(state,false);
      if(['initializing','ready','running','stopping'].includes(state.status))this.timer=setTimeout(()=>this.poll(),100);
    } catch(error) {
      if(generation!==this.generation)return;
      this.release(true);this.latest={...this.latest,status:'disconnected',message:'Connection lost. Controls released; the backend lease returns to neutral.'};
      this.onState(this.latest,false);this.onError(error.message);
    }
  }
  async sendInput(forceNeutral=false,keepalive=false) {
    if(!this.latest.sessionId||!this.token)return;
    if(!forceNeutral&&(!canPilot(this.latest)||this.pendingInput))return;
    const direction=forceNeutral?{yaw:0,pitch:0}:heldDirection(this.held);
    const sequence=++this.sequence;this.pendingInput=sequence;
    try {
      await this.api('/api/input',{sessionId:this.latest.sessionId,sequence,...direction},keepalive);
    } catch(error) {
      if(!forceNeutral){this.release(true);this.onError(error.message);}
    } finally {if(this.pendingInput===sequence)this.pendingInput=0;}
  }
  hold(key,source) {
    if(!canPilot(this.latest))return;
    this.held.add(`${source}:${key}`);
    this.refreshHeld();this.sendInput();
  }
  refreshHeld() {
    // Public direction keys are derived from independent key/pointer sources.
    const values=[...this.held].filter(k=>k.includes(':'));
    for(const key of ['yaw-','yaw+','pitch-','pitch+']) {
      this.held.delete(key);
      if(values.some(value=>value.endsWith(':'+key)))this.held.add(key);
    }
  }
  lift(source) {
    if(![...this.held].some(key=>key.startsWith(source+':')))return;
    for(const key of [...this.held])if(key.startsWith(source+':'))this.held.delete(key);
    this.refreshHeld();
    const direction=heldDirection(this.held);
    this.sendInput(direction.yaw===0&&direction.pitch===0,true);
  }
  release(send=true) {this.held.clear();this.pointers.clear();if(send)this.sendInput(true,true);}
  async stop() {
    this.release(false);
    if(!this.latest.sessionId)return;
    try{this.latest=await this.api('/api/session/stop',{sessionId:this.latest.sessionId});this.onState(this.latest,false);clearTimeout(this.timer);this.poll();}
    catch(error){this.release(true);this.onError(error.message);}
  }
  async download() {
    const record=await this.api('/api/record');
    const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`apollo-live-${record.session.sessionId}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
}
