const CLASSIFICATION = 'INTERACTIVE PROCEDURE TRAINER';
const ROLES = new Set(['CDR', 'LMP', 'CMP']);
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const nonempty = value => typeof value === 'string' && value.trim().length > 0;
const counter = value => Number.isSafeInteger(value) && value >= 0;
const copy = value => JSON.parse(JSON.stringify(value));
function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

export class ProcedureClientError extends Error {
  constructor(message, {status = null, code = 'procedure-error'} = {}) {
    super(message);this.name = 'ProcedureClientError';this.status = status;this.code = code;
  }
}

/** A checklist trainer acknowledgement must never masquerade as AGC or flight data. */
export function validateProcedureSnapshot(value) {
  const invalid = reason => {throw new ProcedureClientError(`Invalid procedure snapshot: ${reason}.`, {code:'invalid-snapshot'});};
  if (!isObject(value) || value.schemaVersion !== 1) invalid('unsupported schema');
  if (value.mode !== CLASSIFICATION || value.classification !== CLASSIFICATION) invalid('source must be an interactive procedure trainer');
  if (!['idle','active','complete'].includes(value.status)) invalid('unknown status');
  if (typeof value.available !== 'boolean') invalid('availability is missing');
  if (!(value.sessionId === null || nonempty(value.sessionId))) invalid('session identifier');
  if (value.status !== 'idle' && !nonempty(value.sessionId)) invalid('active session identifier is missing');
  for (const name of ['revision','currentStepIndex']) if (!counter(value[name])) invalid(name);
  if (!Number.isSafeInteger(value.lastSequence) || value.lastSequence < -1) invalid('lastSequence');
  if (!(value.currentStep === null || (isObject(value.currentStep) && nonempty(value.currentStep.id)))) invalid('current step');
  if (!Array.isArray(value.completedStepIds) || !value.completedStepIds.every(nonempty) || new Set(value.completedStepIds).size !== value.completedStepIds.length) invalid('completed steps');
  for (const name of ['controls','crewReports','controlEvidence']) if (!isObject(value[name])) invalid(name);
  if (!Array.isArray(value.events) || !value.events.every(isObject)) invalid('events');
  if (!['docked','released'].includes(value.attachment)) invalid('docking connection');
  if (!isObject(value.capabilities) || value.capabilities.mode !== CLASSIFICATION) invalid('procedure capabilities are missing or misclassified');
  for (const name of ['originalAgc','flightPhysics','sensorReadback','historicalMissionClock']) {
    if (value.capabilities[name] !== false) invalid(`unsupported ${name} capability`);
  }
  for (const name of ['positionM','velocityMps','quaternion','missionClock','missionGet','cycle','agcState','dskyState','dsky']) {
    if (Object.hasOwn(value,name) && value[name] !== null) invalid(`unexpected ${name} telemetry`);
  }
  return value;
}

/**
 * Explicit command/acknowledgement client. No polling, timers, optimistic
 * progression or automatic command retry. Every presented state is server data.
 */
export class ProcedureClient {
  #token = null;
  constructor({fetchImpl = globalThis.fetch, onState = () => {}, onError = () => {}} = {}) {
    if (typeof fetchImpl !== 'function') throw new TypeError('A fetch implementation is required.');
    this.fetchImpl=fetchImpl;this.onState=onState;this.onError=onError;
    this.state=null;this.capabilities=null;this.busy=false;this.available=false;
    this.message='Connect to the local procedure service.';
  }
  // A prototype getter keeps the local authorization token out of serialization.
  get token() {return this.#token;}

  async #request(path, body) {
    const headers={};
    if (this.#token) headers['X-Apollo-Token']=this.#token;
    if (body !== undefined) headers['Content-Type']='application/json';
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
    try {
      // Browser fetch is a Window-bound Web IDL operation (notably WebKit).
      // Calling the stored function as a client method supplies the wrong brand.
      const response=await this.fetchImpl.call(globalThis,path,{
        method:body===undefined?'GET':'POST',headers,cache:'no-store',signal:controller.signal,
        ...(body===undefined?{}:{body:JSON.stringify(body)}),
      });
      let value;
      try {value=await response.json();}
      catch {throw new ProcedureClientError('The procedure service returned unreadable data.',{status:response.status,code:'invalid-response'});}
      if (!response.ok) throw new ProcedureClientError(
        nonempty(value?.error)?value.error:`The procedure service returned HTTP ${response.status}.`,
        {status:response.status,code:'http-error'},
      );
      return value;
    } catch (error) {
      if (error.name==='AbortError' || controller.signal.aborted) throw new ProcedureClientError('The procedure service timed out. No command was retried.',{code:'timeout'});
      throw error;
    } finally {clearTimeout(timeout);}
  }

  #publish(value) {
    validateProcedureSnapshot(value);
    const next=freeze(copy(value));
    this.state=next;
    this.available=next.available && this.#token!==null;
    this.message=nonempty(next.message)?next.message:'Procedure state received.';
    this.onState(next);
    return next;
  }

  #requireService() {
    if (!this.available || !this.#token) throw new ProcedureClientError(this.message || 'The procedure service is unavailable.',{code:'unavailable'});
  }

  async #run(operation) {
    if (this.busy) throw new ProcedureClientError('A procedure request is already pending. Wait for its acknowledgement.',{code:'busy'});
    this.busy=true;
    try {return await operation();}
    catch (error) {
      this.message=error.message || 'The procedure request failed.';
      this.onError(this.message,error);
      throw error;
    } finally {this.busy=false;}
  }

  async #resync() {
    // One read resolves uncertainty. It never repeats or substitutes a command.
    return this.#publish(await this.#request('/api/procedure/status'));
  }

  async #post(path,body,readAcknowledgement) {
    try {return readAcknowledgement(await this.#request(path,body));}
    catch (error) {
      if (error.status===403) {
        // A restarted local service has a new token. A role rejection also
        // requires deliberate review; neither case authorizes another POST.
        this.#token=null;this.available=false;
        error.message+=' Reconnect to the local procedure service and review its current state before another action.';
        throw error;
      }
      const uncertain=error.status===null || error.status===undefined || error.status>=500 || error.code==='invalid-response' || error.code==='invalid-snapshot' || error.code==='invalid-acknowledgement';
      if (error.status===409 || uncertain) {
        try {await this.#resync();}
        catch (refreshError) {
          error.resyncError=refreshError;
          error.message+= ' Current status could not be refreshed; reconnect before another action.';
          this.available=false;
        }
      }
      throw error;
    }
  }

  async connect() {
    return this.#run(async()=>{
      // Bootstrap is the only source of an authorization token.
      this.#token=null;this.available=false;
      const bootstrap=await this.#request('/api/bootstrap');
      if (!isObject(bootstrap)) throw new ProcedureClientError('Invalid local service capabilities.',{code:'invalid-response'});
      const {token,...capabilities}=bootstrap;
      this.capabilities=freeze(copy(capabilities));
      if (bootstrap.procedureEnabled !== true || !nonempty(token)) {
        this.message='Interactive procedures are unavailable on this server. Start the current local application without --replay-only.';
        return null;
      }
      this.#token=token;this.available=true;
      try {return await this.#resync();}
      catch (error) {this.available=false;throw error;}
    });
  }

  async refresh() {
    return this.#run(async()=>{this.#requireService();return this.#resync();});
  }

  async start() {
    return this.#run(async()=>{
      this.#requireService();
      return this.#post('/api/procedure/start',{},value=>this.#publish(value));
    });
  }

  async act(role,action,value) {
    return this.#run(async()=>{
      this.#requireService();
      if (this.state?.status !== 'active' || !nonempty(this.state.sessionId)) throw new ProcedureClientError('Start or restore an active procedure session before operating a control.',{code:'inactive'});
      if (!ROLES.has(role) || !nonempty(action) || value===undefined || (value!==null && !['string','boolean','number'].includes(typeof value)) || (typeof value==='number'&&!Number.isFinite(value))) throw new ProcedureClientError('A valid crew role, action and explicit control value are required.',{code:'invalid-command'});
      const body={sessionId:this.state.sessionId,sequence:this.state.lastSequence+1,expectedRevision:this.state.revision,role,action,value};
      return this.#post('/api/procedure/action',body,response=>{
        if (!isObject(response) || response.accepted !== true || typeof response.advanced !== 'boolean' || !nonempty(response.meaning)) throw new ProcedureClientError('The procedure service did not acknowledge this action.',{code:'invalid-acknowledgement'});
        validateProcedureSnapshot(response.snapshot);
        const event=response.snapshot.events.at(-1);
        if (response.snapshot.sessionId !== body.sessionId || response.snapshot.revision !== body.expectedRevision+1 || response.snapshot.lastSequence !== body.sequence
          || response.snapshot.definitionSha256 !== this.state.definitionSha256
          || !isObject(event) || event.sessionId !== body.sessionId || event.sequence !== body.sequence || event.revision !== body.expectedRevision+1
          || event.action !== body.action || event.role !== body.role || !Object.is(event.value,body.value) || event.advanced !== response.advanced) throw new ProcedureClientError('The procedure acknowledgement is stale or does not identify this action.',{code:'invalid-acknowledgement'});
        return freeze({...response,snapshot:this.#publish(response.snapshot)});
      });
    });
  }
}
