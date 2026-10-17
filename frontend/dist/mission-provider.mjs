/**
 * Presentation boundary for the retained Phase 10 guidance export.
 * No AGC instruction, guidance, trajectory, or physical integration runs here.
 * @typedef {import('./mission-types.js').RecordedGuidance} RecordedGuidance
 * @typedef {import('./mission-types.js').MissionSnapshot} MissionSnapshot
 * @typedef {import('./mission-types.js').MissionCapability} MissionCapability
 * @typedef {import('./mission-types.js').CrewMember} CrewMember
 * @typedef {import('./mission-types.js').MissionProvider} MissionProvider
 */
import { validateGuidance, frameAt, boundedTime } from './guidance-state.mjs';

export const EXECUTION_MODES = Object.freeze({
  recorded: 'VERIFIED RECORDED EXECUTION',
  live: 'LIVE AGC EXECUTION',
  illustration: 'STATIC EDUCATIONAL ILLUSTRATION',
});

/** @template T @param {T} value @returns {Readonly<T>} */
const deepFreeze = value => {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
};

/** Planned seats only. This is historical role information, not active crew. @type {readonly CrewMember[]} */
export const CREW_ROLES = deepFreeze([
  { id: 'commander', role: 'COMMANDER', name: 'Neil Armstrong', vehicle: 'Lunar Module',
    status: 'planned', participantTypes: ['human', 'ai'],
    description: 'Future Lunar Module command position.' },
  { id: 'lunar-module-pilot', role: 'LUNAR MODULE PILOT', name: 'Buzz Aldrin', vehicle: 'Lunar Module',
    status: 'planned', participantTypes: ['human', 'ai'],
    description: 'Future Lunar Module systems and guidance position.' },
  { id: 'command-module-pilot', role: 'COMMAND MODULE PILOT', name: 'Michael Collins', vehicle: 'Command Module',
    status: 'planned', participantTypes: ['human', 'ai'],
    description: 'Future Command Module position in lunar orbit.' },
]);

/** Capability scope is the Phase 10 guidance experience, not the separate bounded-attitude lab. @type {readonly MissionCapability[]} */
const CAPABILITIES = deepFreeze([
  { id: 'recorded-guidance', label: 'Recorded guidance', available: true,
    reason: 'Retained original Luminary 099 execution observations.' },
  { id: 'trace-dsky', label: 'Recorded DSKY', available: true,
    reason: 'Channel 010 digit relay fields; signs and indicator lamps are unavailable.' },
  { id: 'static-geometry', label: 'Initial mission geometry', available: true,
    reason: 'Supplied synthetic 3D state and separately dated landing-site reference; no propagated motion.' },
  { id: 'scenario-comparison', label: 'Scenario comparison', available: true,
    reason: 'Three independently retained execution results.' },
  { id: 'live-guidance', label: 'Live mission guidance', available: false,
    reason: 'No live Phase 10 mission-guidance service is exposed. The existing live service supports bounded attitude only.' },
  { id: 'live-dsky-input', label: 'Live DSKY commands', available: false,
    reason: 'No arbitrary DSKY command endpoint is exposed.' },
  { id: 'powered-descent', label: 'Powered descent', available: false,
    reason: 'Engine ignition, translational integration, and landing are not demonstrated by this recording.' },
  { id: 'multiplayer', label: 'Crew collaboration', available: false,
    reason: 'Three role definitions are prepared; participant sessions and shared controls are planned.' },
  { id: 'ai-crew', label: 'AI crew', available: false,
    reason: 'AI participants and recommendations are planned.' },
]);

/** @param {RecordedGuidance} data @returns {RecordedGuidance} */
function validateProviderData(data) {
  validateGuidance(data);
  if (!Number.isFinite(data.clock?.secondsPerCpuCall) || data.clock.secondsPerCpuCall <= 0
      || typeof data.provenance?.evidenceRoot !== 'string'
      || !['clock', 'timeToGo', 'ignitionTime', 'ignitionLead', 'dsky', 'projection'].every(key => typeof data.labels?.[key] === 'string')) {
    throw new Error('The recording is missing provenance or clock metadata.');
  }
  const observationValid = (value, maxCycle) => Number.isInteger(value?.rawLine) && value.rawLine > 0
    && Number.isInteger(value.cycle) && value.cycle >= 0 && value.cycle <= maxCycle;
  const fields = ['PROG', 'VERB', 'NOUN', 'R1', 'R2', 'R3'];
  const finiteOrNull = value => value === null || Number.isFinite(value);
  for (const scenario of data.cases) {
    const initial = scenario.initialState;
    const final = scenario.frames.at(-1);
    const result = scenario.result;
    if (scenario.frames[0].t !== 0 || typeof scenario.sources.tracePath !== 'string'
        || !Number.isFinite(initial.epochSeconds) || !Number.isFinite(initial.targetLandingTimeSeconds)
        || !observationValid(initial.source, final.cycle) || typeof initial.positionFrame !== 'string'
        || typeof initial.velocityFrame !== 'string' || typeof initial.siteFrame !== 'string'
        || (initial.siteSource !== null && !observationValid(initial.siteSource, final.cycle))
        || (initial.landingSiteBasicRefAtTlandM !== null && !initial.siteSource)
        || typeof initial.transformSource?.configurationPath !== 'string' || typeof initial.transformSource?.field !== 'string') {
      throw new Error(`The recording is missing state provenance: ${scenario.id}.`);
    }
    if (!result || typeof scenario.title !== 'string' || typeof scenario.outcome !== 'string'
        || typeof result.reviewReached !== 'boolean' || result.allOriginalChecksPass !== true
        || !Number.isInteger(result.rootCount) || result.rootCount !== final.rootCount
        || !['ignitionTimeSeconds', 'observedClockSeconds', 'ignitionLeadSeconds'].every(key =>
          finiteOrNull(result[key]) && result[key] === final[key])
        || !Array.isArray(result.finalAlarms) || result.finalAlarms.length !== final.alarms.length
        || !result.finalAlarms.every((alarm, index) => alarm === final.alarms[index])
        || !fields.every(key => typeof result.finalDsky?.[key] === 'string' && result.finalDsky[key] === final.dsky[key])
        || result.reviewReached !== scenario.events.some(event => event.id === 'crew-review')) {
      throw new Error(`Missing or inconsistent recorded result: ${scenario.id}.`);
    }
    let previousCycle = -1;
    for (const frame of scenario.frames) {
      if (frame.cycle < 0 || frame.cycle < previousCycle || !observationValid(frame.source, frame.cycle)
          || !frame.observationSources || !['dsky', 'clock', 'timeToGo', 'ignitionTime', 'ignitionLead', 'alarms'].every(key =>
            frame.observationSources[key] === null || observationValid(frame.observationSources[key], frame.cycle))) {
        throw new Error('Missing or invalid observation provenance.');
      }
      previousCycle = frame.cycle;
      for (const [field, key] of Object.entries({ observedClockSeconds: 'clock', signedTimeToGoSeconds: 'timeToGo',
        ignitionTimeSeconds: 'ignitionTime', ignitionLeadSeconds: 'ignitionLead' })) {
        const observation = frame.observationSources[key];
        if (frame[field] !== null && !observationValid(observation, frame.cycle)) {
          throw new Error(`Missing or invalid observation provenance: ${field}.`);
        }
      }
      if (frame.alarms.length && !frame.observationSources.alarms) throw new Error('Missing alarm observation provenance.');
    }
    previousCycle = -1;
    const eventIds = new Set();
    for (const event of scenario.events) {
      if (event.t < 0 || event.cycle < 0 || event.cycle < previousCycle || event.cycle > final.cycle
          || !observationValid(event.source, event.cycle) || eventIds.has(event.id)) {
        throw new Error('Missing or invalid event provenance.');
      }
      eventIds.add(event.id);
      previousCycle = event.cycle;
    }
  }
  return data;
}

/** @param {import('./mission-types.js').RecordedScenario} scenario @returns {import('./mission-types.js').ScenarioSummary} */
function scenarioSummary(scenario) {
  return deepFreeze({ id: scenario.id, title: scenario.title, outcome: scenario.outcome,
    durationSeconds: scenario.durationSeconds, initialState: scenario.initialState, result: scenario.result,
    sources: scenario.sources });
}

/** Read-only source adapter; callers own replay transport and rendering. @implements {MissionProvider} */
export class RecordedTraceProvider {
  /** @param {RecordedGuidance} recording */
  constructor(recording) {
    // Own an immutable copy so UI code cannot accidentally rewrite the imported evidence.
    this.recording = deepFreeze(structuredClone(validateProviderData(recording)));
    this.mode = EXECUTION_MODES.recorded;
    this.scenarios = Object.freeze(this.recording.cases.map(scenarioSummary));
    Object.freeze(this);
  }

  /** @param {string | URL} [url] @param {{ fetchImpl?: typeof fetch, signal?: AbortSignal }} [options] */
  static async load(url = './data/guidance.json', { fetchImpl = globalThis.fetch, signal } = {}) {
    if (typeof fetchImpl !== 'function') throw new Error('A fetch implementation is required to load the recording.');
    const response = await fetchImpl(url, { cache: 'no-store', signal });
    if (!response.ok) throw new Error(`The verified guidance recording could not be loaded (${response.status}).`);
    return new RecordedTraceProvider(await response.json());
  }

  listScenarios() { return this.scenarios; }

  getScenario(id) {
    const scenario = this.recording.cases.find(item => item.id === id);
    if (!scenario) throw new Error(`Unknown retained scenario: ${id}.`);
    return scenario;
  }

  /** Annotate real event observations without inventing intermediate milestones. */
  /** @returns {readonly import('./mission-types.js').MissionEvent[]} */
  getEvents(id) {
    const scenario = this.getScenario(id);
    return deepFreeze(scenario.events.map(event => ({
      ...event, mode: this.mode, availability: 'available', validity: 'recorded-observation',
      units: { t: 's', cycle: 'CPU calls' }, coordinateFrame: null,
      timestamp: { clock: 'cpu-call-time', seconds: event.t, units: 's', cpuCycle: event.cycle },
      source: { kind: 'retained-trace', path: scenario.sources.tracePath, rawSha256: scenario.sources.rawSha256,
        rawLine: event.source.rawLine, cpuCycle: event.source.cycle },
      observation: event.source,
    })));
  }

  /** @returns {readonly MissionCapability[]} */
  getCapabilities() { return CAPABILITIES; }

  /**
   * Actual observations are held between samples. Replay time never changes geometry.
   * Per-value timestamps identify the earlier observation when a value is held.
   * @param {string} id @param {number} replaySeconds @returns {MissionSnapshot}
   */
  getSnapshot(id, replaySeconds) {
    const scenario = this.getScenario(id);
    const t = boundedTime(replaySeconds, scenario.durationSeconds);
    const frame = frameAt(scenario, t);
    /** @param {import('./mission-types.js').TraceObservation | null} observation @returns {import('./mission-types.js').SourceReference | null} */
    const source = observation => observation ? {
      kind: 'retained-trace', path: scenario.sources.tracePath, rawSha256: scenario.sources.rawSha256,
      rawLine: observation.rawLine, cpuCycle: observation.cycle,
    } : null;
    /** @param {import('./mission-types.js').TraceObservation | null} observation @returns {import('./mission-types.js').DataTimestamp | null} */
    const timestamp = observation => observation ? {
      clock: 'cpu-call-time', seconds: observation.cycle * this.recording.clock.secondsPerCpuCall,
      units: 's', cpuCycle: observation.cycle,
    } : null;
    /** @param {number | null} value @param {'clock' | 'timeToGo' | 'ignitionTime' | 'ignitionLead'} key @param {string} label @returns {import('./mission-types.js').ObservedQuantity} */
    const quantity = (value, key, label) => {
      const observation = frame.observationSources[key];
      return { value, units: 's', coordinateFrame: 'synthetic mission time convention',
        mode: this.mode, availability: value === null ? 'unavailable' : 'available',
        validity: value === null ? 'unavailable' : 'recorded-observation', label,
        source: source(observation), timestamp: timestamp(observation) };
    };
    const dskyObservation = frame.observationSources.dsky;
    const initial = scenario.initialState;
    const initialSource = source(initial.source);
    /** @type {import('./mission-types.js').DataTimestamp} */
    const navigationTimestamp = { clock: 'initialized-navigation-epoch', seconds: initial.epochSeconds, units: 's' };
    /** @type {MissionSnapshot} */
    const snapshot = {
      mode: this.mode, availability: 'available', validity: 'recorded-observation',
      source: source(frame.source), timestamp: timestamp(frame.source),
      units: { replay: 's', cpuCycle: 'CPU calls' }, coordinateFrame: null,
      replay: { seconds: t, units: 's', durationSeconds: scenario.durationSeconds, clock: 'cpu-call-time' },
      scenario: this.scenarios.find(item => item.id === id),
      // Exported presentation observations are retained for incremental integration with the existing UI.
      // They are not a direct emulator-memory interface.
      frame,
      dsky: {
        ...frame.dsky, units: 'display digit fields', coordinateFrame: null, mode: this.mode,
        availability: !dskyObservation ? 'unavailable' : Object.values(frame.dsky).some(value => value.includes('?')) ? 'partial' : 'available',
        validity: dskyObservation ? 'recorded-observation' : 'unavailable',
        source: source(dskyObservation), timestamp: timestamp(dskyObservation),
        signs: null, indicators: null, lampAvailability: 'unavailable',
        note: this.recording.labels.dsky,
      },
      guidance: {
        mode: this.mode, availability: 'available', validity: 'recorded-observation',
        source: source(frame.source), timestamp: timestamp(frame.source),
        units: { rootCount: 'count', alarms: 'octal code' }, coordinateFrame: null,
        stage: frame.stage, rootCount: frame.rootCount, alarms: frame.alarms,
        observedClock: quantity(frame.observedClockSeconds, 'clock', this.recording.labels.clock),
        signedTimeToGo: quantity(frame.signedTimeToGoSeconds, 'timeToGo', this.recording.labels.timeToGo),
        ignitionTime: quantity(frame.ignitionTimeSeconds, 'ignitionTime', this.recording.labels.ignitionTime),
        ignitionLead: quantity(frame.ignitionLeadSeconds, 'ignitionLead', this.recording.labels.ignitionLead),
      },
      spacecraft: {
        mode: EXECUTION_MODES.illustration, availability: 'available', validity: 'initialized-input',
        source: initialSource, timestamp: navigationTimestamp,
        units: { position: 'm', velocity: 'm/s', altitude: 'm', speed: 'm/s', lunarRadius: 'm' },
        coordinateFrame: initial.positionFrame, velocityFrame: initial.velocityFrame,
        positionM: initial.positionM, velocityMps: initial.velocityMps,
        altitudeM: initial.altitudeM, speedMps: initial.speedMps, lunarRadiusM: initial.lunarRadiusM,
        landingSite: {
          mode: EXECUTION_MODES.illustration,
          availability: initial.landingSiteBasicRefAtTlandM === null ? 'unavailable' : 'available',
          validity: initial.landingSiteBasicRefAtTlandM === null ? 'unavailable' : 'derived-reference',
          units: 'm', coordinateFrame: initial.siteFrame,
          positionM: initial.landingSiteBasicRefAtTlandM,
          timestamp: { clock: 'target-landing-time', seconds: initial.targetLandingTimeSeconds, units: 's' },
          source: initial.siteSource ? { ...source(initial.siteSource), transform: initial.transformSource } : null,
        },
        initialState: initial,
        note: this.recording.labels.projection,
      },
      capabilities: CAPABILITIES,
      crew: CREW_ROLES,
    };
    return deepFreeze(snapshot);
  }

  /** Replay interactions do not submit commands to the AGC. @returns {Promise<import('./mission-types.js').CommandResult>} */
  async command() {
    return { accepted: false, status: 'unavailable', mode: this.mode,
      reason: 'Recorded execution is read-only. No command was sent to an AGC.' };
  }
}

/**
 * Explicit unavailable boundary for a future mission-guidance service.
 * Existing /api/* routes serve the separate bounded-attitude experience. They
 * do not supply a Phase 10 MissionSnapshot, so this class makes no request.
 * @implements {MissionProvider}
 */
export class LiveBackendProvider {
  constructor() { this.mode = EXECUTION_MODES.live; Object.freeze(this); }
  getCapabilities() {
    return CAPABILITIES.map(capability => ({ ...capability, available: false,
      reason: 'A live Phase 10 mission-guidance integration contract is not implemented.' }));
  }
  getSnapshot() { return null; }
  /** @returns {Promise<import('./mission-types.js').CommandResult>} */
  async command() {
    return { accepted: false, status: 'unavailable', mode: this.mode,
      reason: 'No live Phase 10 guidance or arbitrary DSKY endpoint is implemented. No command was sent.' };
  }
}
