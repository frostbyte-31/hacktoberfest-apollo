/** @typedef {import('./mission-live-types.js').LabSnapshot} LabSnapshot */
/** Versioned server adapter; no frontend physics, AGC emulation or invented telemetry. */
export const ROLE_IDS = Object.freeze(['commander', 'lunar-module-pilot', 'command-module-pilot']);
const SESSION_KEY = 'apollo.final.mission.v1';
const finite = value => typeof value === 'number' && Number.isFinite(value);
const vector = (value, length = 3) => Array.isArray(value) && value.length === length && value.every(finite);
/** @param {unknown} input @returns {LabSnapshot} Runtime validation is the browser boundary. */
export function validateMission(input) {
  if (!input || input.schemaVersion !== 1 || input.mode !== 'EDUCATIONAL_PHYSICS_LAB'
      || typeof input.id !== 'string' || typeof input.runId !== 'string'
      || !Number.isInteger(input.revision) || input.revision < 0
      || !['lobby', 'running', 'paused', 'completed', 'fault'].includes(input.status)) throw new Error('Unsupported mission snapshot.');
  const physics = input.physics;
  const craft = physics?.spacecraft;
  if (!physics || !finite(physics.simTimeSeconds) || !Number.isInteger(physics.tick) || !craft
      || !['positionM', 'velocityMps', 'accelerationMps2', 'angularVelocityRadps'].every(key => vector(craft[key]))
      || !vector(craft.quaternionBodyToRef, 4)
      || !['massKg', 'fuelKg', 'altitudeM', 'verticalSpeedMps', 'horizontalSpeedMps', 'downrangeM', 'pitchDeg'].every(key => finite(craft[key]))
      || craft.massKg <= 0 || craft.fuelKg < 0) throw new Error('Mission physics data is unavailable or invalid.');
  const engine = physics.engine;
  if (!engine || typeof engine.enabled !== 'boolean' || !['throttle', 'thrustN', 'massFlowKgps'].every(key => finite(engine[key]))
      || !vector(engine.thrustVectorN)) throw new Error('Mission engine data is unavailable or invalid.');
  if (!Array.isArray(input.crew) || input.crew.length !== 3
      || new Set(input.crew.map(member => member.id)).size !== 3
      || !ROLE_IDS.every(id => input.crew.some(member => member.id === id))) throw new Error('Expected exactly three Apollo crew positions.');
  if (!Array.isArray(input.events) || !Array.isArray(input.messages)) throw new Error('Mission event data is unavailable.');
  return input;
}
export class MissionLiveProvider {
  constructor({fetchImpl = (url, init) => globalThis.fetch(url, init), storage = globalThis.sessionStorage, requestTimeoutMs = 5000} = {}) {
    if (!finite(requestTimeoutMs) || requestTimeoutMs <= 0 || requestTimeoutMs > 60000) throw new RangeError('Mission request timeout must be between 0 and 60000 milliseconds.');
    this.fetch = fetchImpl; this.storage = storage; this.token = null; this.credentials = null;
    this.requestTimeoutMs = requestTimeoutMs;
    try {
      const saved = JSON.parse(storage?.getItem(SESSION_KEY) ?? 'null');
      if (saved && typeof saved.missionId === 'string' && typeof saved.participantToken === 'string' && Number.isInteger(saved.sequence)) this.credentials = saved;
    } catch { /* An unavailable browser store never supplies a fake participant. */ }
  }
  persist() { try { if (this.credentials) this.storage?.setItem(SESSION_KEY, JSON.stringify(this.credentials)); } catch { /* Session can still run in memory. */ } }
  async request(path, {body, participant = false} = {}) {
    const headers = {'Accept': 'application/json'};
    if (body !== undefined) { headers['Content-Type'] = 'application/json'; headers['X-Apollo-Token'] = this.token ?? ''; }
    if (participant && this.credentials) headers['X-Apollo-Participant'] = this.credentials.participantToken;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.requestTimeoutMs);
    try {
      const response = await this.fetch(path, {method: body === undefined ? 'GET' : 'POST', headers, cache: 'no-store', credentials: 'same-origin', keepalive: body !== undefined, signal: controller.signal, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      let data;
      try { data = await response.json(); }
      catch (error) {
        if (controller.signal.aborted) throw error;
        throw new Error('The mission service returned an unreadable response.');
      }
      if (!response.ok) throw new Error(data.error ?? data.message ?? `Mission request failed (${response.status}).`);
      return data;
    } catch (error) {
      if (!controller.signal.aborted) throw error;
      const failure = Object.assign(new Error(body === undefined
        ? 'The mission request timed out. Check the local server and reconnect.'
        : 'The mission request timed out. Its outcome is unknown; refresh shared state before another command.'),
      {code: 'timeout', commandOutcomeUnknown: body !== undefined});
      throw failure;
    } finally {
      clearTimeout(timer);
    }
  }
  async discover() {
    const data = await this.request('/api/v1/capabilities');
    if (data.schemaVersion !== 1 || !Array.isArray(data.scenarios) || !Array.isArray(data.crewRoles) || typeof data.token !== 'string') throw new Error('The versioned mission service is unavailable.');
    this.token = data.token;
    const {token, ...publicData} = data;
    return publicData;
  }
  remember(reply) {
    if (typeof reply.missionId !== 'string' || typeof reply.participantToken !== 'string') throw new Error('Mission identity was not returned.');
    const snapshot = validateMission(reply.snapshot);
    this.credentials = {missionId: reply.missionId, participantToken: reply.participantToken, sequence: snapshot.you?.lastSequence ?? 0, runId: snapshot.runId};
    this.persist(); return snapshot;
  }
  async create({scenarioId, name, role, crewModes}) { return this.remember(await this.request('/api/v1/missions', {body: {scenarioId, name, role, crewModes}})); }
  async join({missionId, name, role}) { return this.remember(await this.request(`/api/v1/missions/${encodeURIComponent(missionId)}/join`, {body: {name, role}})); }
  accept(snapshot) {
    validateMission(snapshot);
    if (this.credentials && snapshot.id === this.credentials.missionId) {
      this.credentials.sequence = Math.max(this.credentials.sequence, snapshot.you?.lastSequence ?? 0);
      this.credentials.runId = snapshot.runId; this.persist();
    }
    return snapshot;
  }
  async snapshot() {
    if (!this.credentials) throw new Error('Create or join a mission first.');
    return this.accept(await this.request(`/api/v1/missions/${encodeURIComponent(this.credentials.missionId)}`, {participant: true}));
  }
  async command(action, payload = {}) {
    if (!this.credentials) throw new Error('Create or join a mission first.');
    const sequence = ++this.credentials.sequence;
    this.persist();
    const result = await this.request(`/api/v1/missions/${encodeURIComponent(this.credentials.missionId)}/command`, {participant: true, body: {sequence, runId: this.credentials.runId, action, payload}});
    this.accept(result.snapshot); return result;
  }
}

/** Independent read-only provider for sealed Phase12 evidence, never live execution. */
export class RecordedPropulsionProvider {
  constructor(recording) {
    if (!recording || recording.schemaVersion !== 1 || recording.mode !== 'RECORDED_AUTHENTIC_AGC_EXPERIMENT' || !Array.isArray(recording.cases) || recording.cases.length !== 3) throw new Error('Verified propulsion recording is unavailable.');
    if (new Set(recording.cases.map(value => value.id)).size !== 3 || !['sink','connected','no-feedback'].every(id => recording.cases.some(value => value.id === id))) throw new Error('Expected the three verified propulsion cases.');
    for (const scenario of recording.cases) {
      if (typeof scenario.id !== 'string' || !/^[a-f0-9]{64}$/.test(scenario.traceSha256) || !Array.isArray(scenario.frames) || !scenario.frames.length || !Array.isArray(scenario.events)) throw new Error('Propulsion evidence provenance is incomplete.');
      let previous = -Infinity;
      for (const frame of scenario.frames) {
        if (!finite(frame.t) || frame.t <= previous || !Number.isInteger(frame.cycle) || !Number.isInteger(frame.source?.rawLine)
            || frame.source.traceSha256 !== scenario.traceSha256 || !vector(frame.physics?.spacecraft?.positionM)
            || !finite(frame.physics?.engine?.thrustN)) throw new Error('Malformed recorded propulsion observation.');
        previous = frame.t;
      }
    }
    this.recording = recording;
  }
  static async load({fetchImpl = (url, init) => globalThis.fetch(url, init)} = {}) {
    const reply = await fetchImpl('./data/propulsion-lab.json', {cache:'no-store'});
    if (!reply.ok) throw new Error('Recorded engine evidence could not be loaded.');
    return new RecordedPropulsionProvider(await reply.json());
  }
  scenario(id) { const scenario=this.recording.cases.find(value=>value.id===id); if (!scenario) throw new Error('Unknown recorded propulsion case.'); return scenario; }
  frame(id, time) {
    const scenario=this.scenario(id);
    if (!finite(time)) throw new Error('Invalid recorded elapsed time.');
    let lower=0,upper=scenario.frames.length-1;
    while(lower<upper) { const middle=Math.ceil((lower+upper)/2);if(scenario.frames[middle].t<=time) lower=middle;else upper=middle-1; }
    return scenario.frames[lower];
  }
}
