/** The browser sends hardware key requests; only the original CMC supplies display responses. */
export const EARTH_ORBIT_MODE = 'LIVE ORIGINAL CMC EXECUTION';
export const DSKY_KEYS = Object.freeze(['0','1','2','3','4','5','6','7','8','9','+','-','VERB','NOUN','CLR','PRO','KEY REL','ENTR','RSET']);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const counter = value => Number.isSafeInteger(value) && value >= 0;
const text = value => typeof value === 'string' && value.trim().length > 0;
const sha = value => typeof value === 'string' && /^[0-9a-f]{64}$/i.test(value);
const clone = value => JSON.parse(JSON.stringify(value));
function freeze(value) {if (value && typeof value === 'object') {Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
export class EarthOrbitClientError extends Error {
  constructor(message,{status=null,code='computer-error'}={}) {super(message);this.name='EarthOrbitClientError';this.status=status;this.code=code;}
}
function invalid(reason) {throw new EarthOrbitClientError(`Invalid CMC observation: ${reason}.`,{code:'invalid-snapshot'});}
function safeSource(value) {try {const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password;}catch {return false;}}

export function validateEarthOrbitSnapshot(value) {
  if (!object(value)||value.schemaVersion!==1||value.mode!==EARTH_ORBIT_MODE) invalid('source classification');
  if (typeof value.available!=='boolean'||!['idle','ready','error','stopped'].includes(value.status)) invalid('availability or status');
  if (!(value.sessionId===null||text(value.sessionId))||!counter(value.revision)||!counter(value.nextSequence)) invalid('session counters');
  if (value.status==='ready'&&(!value.available||!text(value.sessionId)||!object(value.computer))) invalid('ready computer');
  if (!(value.error===null||typeof value.error==='string')||!Array.isArray(value.inputs)) invalid('error or input history');
  const task=value.task;
  if (!object(task)||!text(task.id)||!text(task.title)||typeof task.complete!=='boolean'||!Array.isArray(task.steps)||!text(task.nextInstruction)||!text(task.scope)) invalid('server task');
  if (task.flightExecuted!==false||task.alignmentCompleted!==false) invalid('unsupported flight or completed alignment claim');
  const stepIds=new Set();
  for (const step of task.steps) {
    if (!object(step)||!text(step.id)||stepIds.has(step.id)||!text(step.title)||typeof step.description!=='string'||typeof step.complete!=='boolean'||typeof step.active!=='boolean') invalid('task step');
    stepIds.add(step.id);
  }
  const computer=value.computer;
  if (computer!==null) {
    if (!object(computer)||computer.software!=='Comanche055'||!counter(computer.cycle)||!Number.isFinite(computer.cpuSeconds)||computer.cpuSeconds<0) invalid('computer clock');
    if (Math.abs(computer.cpuSeconds-computer.cycle*12/1024000)>1e-5) invalid('CPU clock units');
    if (!object(computer.dsky)) invalid('DSKY observation');
    for (const [field,length] of Object.entries({PROG:2,VERB:2,NOUN:2,R1:5,R2:5,R3:5})) {
      if (typeof computer.dsky[field]!=='string'||computer.dsky[field].length!==length||!/^[0-9 ?]+$/.test(computer.dsky[field])) invalid(`DSKY ${field}`);
    }
    if (Object.hasOwn(computer.dsky,'signs')) {
      const signs=computer.dsky.signs;
      if (!object(signs)||Object.keys(signs).length!==3||!['R1','R2','R3'].every(field=>Object.hasOwn(signs,field)&&[null,'+','-',' '].includes(signs[field]))) invalid('DSKY register signs');
    }
    if (Object.hasOwn(computer.dsky,'lamps')) {
      const lamps=computer.dsky.lamps,names=['keyRelease','operatorError','computerActivity','verbNounFlash'];
      if (!object(lamps)||Object.keys(lamps).length!==4||!names.every(field=>Object.hasOwn(lamps,field)&&(lamps[field]===null||typeof lamps[field]==='boolean'))) invalid('DSKY indicator bits');
    }
    if (!(computer.dskySource===null||(object(computer.dskySource)&&computer.dskySource.channel===8&&counter(computer.dskySource.cycle)&&computer.dskySource.cycle<=computer.cycle))) invalid('DSKY source cycle/channel');
    if (computer.lastKey!==null) {
      const key=computer.lastKey;
      if (!object(key)||!DSKY_KEYS.includes(key.key)||!counter(key.code)||key.code>32767||!counter(key.channel)||key.channel>511||!counter(key.cycle)||key.cycle>computer.cycle||!counter(key.sequence)) invalid('last key source');
    }
    if (!object(computer.provenance)||!sha(computer.provenance.ropeSha256)||!sha(computer.provenance.engineSha256)||!safeSource(computer.provenance.sourceUrl)) invalid('original software provenance');
    if ((Object.hasOwn(computer,'flightState')&&computer.flightState!==null)||computer.historicalCheckpointLoaded===true||computer.provenance.flightMemoryWrites===true||computer.provenance.hostFlightMemoryWrites===true) invalid('unsupported reconstructed flight state or memory patch');
  }
  return value;
}

/** Explicit key acknowledgements. Failed POSTs are never automatically repeated. */
export class EarthOrbitClient {
  #token=null;
  constructor({fetchImpl=globalThis.fetch,onState=()=>{},onError=()=>{}}={}) {
    if (typeof fetchImpl!=='function') throw new TypeError('A fetch implementation is required.');
    this.fetchImpl=fetchImpl;this.onState=onState;this.onError=onError;this.state=null;this.capabilities=null;this.available=false;this.busy=false;this.message='Connect to Columbia’s computer.';
  }
  async #request(path,body) {
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000),headers={};
    if (this.#token) headers['X-Apollo-Token']=this.#token;
    if (body!==undefined) headers['Content-Type']='application/json';
    try {
      const response=await this.fetchImpl.call(globalThis,path,{method:body===undefined?'GET':'POST',headers,cache:'no-store',signal:controller.signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
      let value;try {value=await response.json();}catch {throw new EarthOrbitClientError('The CMC service returned unreadable data.',{status:response.status,code:'invalid-response'});}
      if (!response.ok) throw new EarthOrbitClientError(text(value?.error)?value.error:`The CMC service returned HTTP ${response.status}.`,{status:response.status,code:'http-error'});
      return value;
    }catch(error) {if (error.name==='AbortError'||controller.signal.aborted) throw new EarthOrbitClientError('The computer request timed out. No key was retried; refresh the current observation.',{code:'timeout'});throw error;}
    finally {clearTimeout(timeout);}
  }
  #publish(value) {validateEarthOrbitSnapshot(value);this.state=freeze(clone(value));this.available=value.available&&this.#token!==null;this.message=value.error||value.task.nextInstruction;this.onState(this.state);return this.state;}
  async #run(operation) {
    if (this.busy) throw new EarthOrbitClientError('Wait for the current computer request to be acknowledged.',{code:'busy'});
    this.busy=true;try {return await operation();}catch(error) {this.message=error.message;this.onError(error.message,error);throw error;}finally {this.busy=false;}
  }
  #require() {if (!this.available||!this.#token) throw new EarthOrbitClientError(this.message||'The CMC service is unavailable.',{code:'unavailable'});}
  async #resync() {return this.#publish(await this.#request('/api/earth-orbit/status'));}
  async #post(path,body,read=value=>this.#publish(value)) {
    try {return read(await this.#request(path,body));}catch(error) {
      if (error.status===403) {this.#token=null;this.available=false;error.message+=' Reconnect before operating another key.';}
      else if (error.status===409||error.status===null||error.status===undefined||error.status>=500||['invalid-snapshot','invalid-response','invalid-acknowledgement'].includes(error.code)) {
        try {await this.#resync();}catch {this.available=false;error.message+=' Current state could not be refreshed. Reconnect before another key.';}
      }
      throw error;
    }
  }
  async connect() {return this.#run(async()=>{
    this.#token=null;this.available=false;
    const value=await this.#request('/api/earth-orbit/capabilities');
    if (!object(value)||typeof value.available!=='boolean'||value.mode!==EARTH_ORBIT_MODE||value.software!=='Comanche055'||typeof value.scope!=='string'||!Array.isArray(value.supportedKeys)||!value.supportedKeys.every(key=>DSKY_KEYS.includes(key))||new Set(value.supportedKeys).size!==value.supportedKeys.length) throw new EarthOrbitClientError('Invalid CMC service capabilities.',{code:'invalid-response'});
    const {token,...capabilities}=value;this.capabilities=freeze(clone(capabilities));
    if (!value.available||!text(token)) {this.message=text(value.unavailableReason)?value.unavailableReason:'Original CMC execution is unavailable. Start the local application with its native assets.';return null;}
    this.#token=token;this.available=true;try {return await this.#resync();}catch(error) {this.available=false;throw error;}
  });}
  async refresh() {return this.#run(async()=>{this.#require();return this.#resync();});}
  async start() {return this.#run(async()=>{this.#require();return this.#post('/api/earth-orbit/start',{});});}
  async stop() {return this.#run(async()=>{this.#require();if (!text(this.state?.sessionId)) throw new EarthOrbitClientError('No computer session exists.',{code:'inactive'});return this.#post('/api/earth-orbit/stop',{sessionId:this.state.sessionId});});}
  async key(key) {return this.#run(async()=>{
    this.#require();if (this.state?.status!=='ready') throw new EarthOrbitClientError('Start a ready CMC session before pressing a key.',{code:'inactive'});
    if (!DSKY_KEYS.includes(key)||!this.capabilities.supportedKeys.includes(key)) throw new EarthOrbitClientError('This hardware key is unavailable.',{code:'invalid-key'});
    const body={sessionId:this.state.sessionId,sequence:this.state.nextSequence,key},beforeCycle=this.state.computer.cycle,beforeRevision=this.state.revision;
    return this.#post('/api/earth-orbit/key',body,value=>{
      validateEarthOrbitSnapshot(value);const ack=value.ack;
      if (!object(ack)||ack.sessionId!==body.sessionId||ack.sequence!==body.sequence||ack.key!==key||!counter(ack.channel)||ack.channel>511||!counter(ack.code)||ack.code>32767||!counter(ack.queuedAtCycle)||ack.queuedAtCycle<beforeCycle||!counter(ack.afterCycle)||ack.afterCycle<ack.queuedAtCycle||value.sessionId!==body.sessionId||value.revision!==beforeRevision+1||value.nextSequence!==body.sequence+1||value.computer?.cycle!==ack.afterCycle||value.computer?.lastKey?.sequence!==body.sequence||value.computer?.lastKey?.key!==key||value.computer?.lastKey?.code!==ack.code||value.computer?.lastKey?.channel!==ack.channel) throw new EarthOrbitClientError('The CMC acknowledgement does not identify this key and observation.',{code:'invalid-acknowledgement'});
      return this.#publish(value);
    });
  });}
}
