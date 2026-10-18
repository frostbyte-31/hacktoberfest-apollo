// @ts-check
/** Read-only adapters. The original exporter verifies evidence; this module validates its display contract. */
import { validateGuidance, frameAt, boundedTime, SCENARIOS } from './guidance-state.mjs';

/** @typedef {import('./mission-types.js').GuidanceRecording} GuidanceRecording */
/** @typedef {import('./mission-types.js').RecordedScenario} RecordedScenario */
/** @typedef {import('./mission-types.js').RawSource} RawSource */
/** @typedef {import('./mission-types.js').EvidenceSource} EvidenceSource */
/** @typedef {import('./mission-types.js').MissionCapability} MissionCapability */
/** @typedef {import('./mission-types.js').FetchFunction} FetchFunction */

/** Preserve the native Window.fetch receiver; injected transports are called independently. @type {FetchFunction} */
const browserFetch = (input, init) => {
  if (typeof globalThis.fetch !== 'function') throw new Error('No browser data transport is available.');
  return globalThis.fetch(input, init);
};

/** @template T @param {T} value @returns {Readonly<T>} */
function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}

/** Exactly the historical three crew positions; no simulated participant or AI is active. */
export const CREW_ROLES = freeze(/** @type {import('./mission-types.js').CrewMember[]} */ ([
  { id: 'commander', name: 'Neil Armstrong', role: 'Commander', location: 'Lunar Module', participantTypes: ['HUMAN', 'AI'], availability: 'PLANNED' },
  { id: 'lunar-module-pilot', name: 'Buzz Aldrin', role: 'Lunar Module Pilot', location: 'Lunar Module', participantTypes: ['HUMAN', 'AI'], availability: 'PLANNED' },
  { id: 'command-module-pilot', name: 'Michael Collins', role: 'Command Module Pilot', location: 'Command Module in lunar orbit', participantTypes: ['HUMAN', 'AI'], availability: 'PLANNED' },
]));

export const MISSION_CAPABILITIES = freeze(/** @type {MissionCapability[]} */ ([
  { id: 'guidance-replay', label: 'Phase 10 guidance replay', availability: 'AVAILABLE', mode: 'VERIFIED_RECORDED_EXECUTION', description: 'Three retained original Luminary experiments; sample and hold without interpolation.' },
  { id: 'initial-geometry', label: 'Synthetic mission geometry', availability: 'AVAILABLE', mode: 'STATIC_EDUCATIONAL_ILLUSTRATION', description: 'Static projection of initialized 3D state; spacecraft and planned site have explicitly separate epochs.' },
  { id: 'live-guidance', label: 'Live pre-ignition guidance', availability: 'UNAVAILABLE', mode: null, description: 'The existing live service exposes bounded attitude only, not live Phase 10 mission initialization or P63 guidance.' },
  { id: 'propulsion', label: 'Descent propulsion', availability: 'UNAVAILABLE', mode: null, description: 'No verified engine/throttle-to-thrust plant is connected.' },
  { id: 'multiplayer', label: 'Three-person crew operations', availability: 'PLANNED', mode: null, description: 'Crew roles are interface metadata; participant sessions and communications are unavailable.' },
  { id: 'ai-crew', label: 'AI crew', availability: 'PLANNED', mode: null, description: 'No operational AI participants or recommendations.' },
]));

/** @param {unknown} value @returns {value is RawSource} */
function validSource(value) {
  if (!value || typeof value !== 'object') return false;
  const source = /** @type {Record<string, unknown>} */ (value);
  return Number.isInteger(source.rawLine) && Number(source.rawLine) > 0 && Number.isInteger(source.cycle) && Number(source.cycle) >= 0;
}

/** @param {RecordedScenario} scenario @param {RawSource} source @param {EvidenceSource['classification']} [classification] @returns {EvidenceSource} */
function evidence(scenario, source, classification = 'AGC_RECORDED') {
  return { tracePath: scenario.sources.tracePath, sha256: scenario.sources.rawSha256, cycle: source.cycle, rawLine: source.rawLine, classification };
}

/** @template T @param {RecordedScenario} scenario @param {T | null} value @param {RawSource | null} source @param {string} unit @param {string} description @returns {import('./mission-types.js').Observation<T>} */
function observation(scenario, value, source, unit, description) {
  return { value, unit, availability: value === null ? 'UNAVAILABLE' : 'AVAILABLE', source: source === null ? null : evidence(scenario, source), description };
}

/** Validate provenance in addition to the retained existing chronology/DSKY validator. @param {unknown} input @returns {GuidanceRecording} */
function recordingContract(input) {
  const data = /** @type {GuidanceRecording} */ (validateGuidance(input));
  if (data.cases.length !== SCENARIOS.length) throw new Error('Expected exactly three verified scenarios.');
  for (const scenario of data.cases) {
    if (typeof scenario.sources.tracePath !== 'string' || !scenario.sources.tracePath.startsWith('docs/phase10-evidence/') || !scenario.sources.tracePath.endsWith('/trace.jsonl.gz')) throw new Error('Missing retained trace path.');
    const initial = scenario.initialState;
    if (![initial.epochSeconds, initial.targetLandingTimeSeconds].every(Number.isFinite) || !validSource(initial.source) || (initial.landingSiteBasicRefAtTlandM !== null && !validSource(initial.siteSource))) throw new Error('Missing initialization provenance or epoch.');
    if (![initial.positionFrame, initial.velocityFrame, initial.siteFrame].every(value => typeof value === 'string' && value.length)) throw new Error('Missing coordinate-frame convention.');
    for (const frame of scenario.frames) {
      if (!validSource(frame.source) || frame.source.cycle !== frame.cycle || !frame.observationSources || typeof frame.stage !== 'string') throw new Error('Invalid frame provenance.');
      const pairs = /** @type {const} */ ([['observedClockSeconds', 'clock'], ['signedTimeToGoSeconds', 'timeToGo'], ['ignitionTimeSeconds', 'ignitionTime'], ['ignitionLeadSeconds', 'ignitionLead']]);
      for (const [valueKey, sourceKey] of pairs) {
        const source = frame.observationSources[sourceKey];
        if ((frame[valueKey] !== null && !validSource(source)) || (source !== null && (!validSource(source) || source.cycle > frame.cycle))) throw new Error(`Missing or future observation source: ${valueKey}.`);
      }
      for (const source of Object.values(frame.observationSources)) {
        if (source !== null && (!validSource(source) || source.cycle > frame.cycle)) throw new Error('Invalid observation source.');
      }
    }
    if (scenario.events.some(event => !validSource(event.source) || event.source.cycle !== event.cycle)) throw new Error('Missing event provenance.');
    const final = scenario.frames[scenario.frames.length - 1];
    if (!scenario.result || scenario.result.rootCount !== final.rootCount || scenario.result.ignitionTimeSeconds !== final.ignitionTimeSeconds || scenario.result.ignitionLeadSeconds !== final.ignitionLeadSeconds || scenario.result.observedClockSeconds !== final.observedClockSeconds || JSON.stringify(scenario.result.finalAlarms) !== JSON.stringify(final.alarms) || JSON.stringify(scenario.result.finalDsky) !== JSON.stringify(final.dsky)) throw new Error('Final outcome disagrees with recorded observations.');
  }
  return data;
}

export class RecordedTraceProvider {
  /** @param {unknown} recording */
  constructor(recording) {
    // Defensive copy prevents a caller from modifying already validated observations later.
    const copy = JSON.parse(JSON.stringify(recording));
    const data = recordingContract(copy);
    /** @readonly @type {GuidanceRecording} */
    this.recording = freeze(data);
    Object.freeze(this);
  }

  /** @param {{url?: string, fetchImpl?: FetchFunction}} [options] */
  static async load({ url = './data/guidance.json', fetchImpl = browserFetch } = {}) {
    if (typeof fetchImpl !== 'function') throw new Error('No browser data transport is available.');
    const response = await fetchImpl(url, { method: 'GET', cache: 'no-cache' });
    if (!response.ok) throw new Error(`Guidance recording is unavailable (HTTP ${response.status}).`);
    return new RecordedTraceProvider(await response.json());
  }

  /** @param {string} id @returns {RecordedScenario} */
  getScenario(id) {
    const scenario = this.recording.cases.find(item => item.id === id);
    if (!scenario) throw new Error(`Unknown recorded scenario: ${id}.`);
    return scenario;
  }

  /** @param {string} id @param {number} time @returns {import('./mission-types.js').MissionSnapshot} */
  getSnapshot(id, time) {
    const scenario = this.getScenario(id);
    const replayElapsedSeconds = boundedTime(time, scenario.durationSeconds);
    const frame = /** @type {import('./mission-types.js').GuidanceFrame} */ (frameAt(scenario, replayElapsedSeconds));
    const initial = scenario.initialState;
    /** @param {import('./mission-types.js').Vector3 | null} value @param {string} unit @param {string} coordinateFrame @param {number} epochSeconds @param {RawSource | null} source @param {string} description @param {EvidenceSource['classification']} [classification] @returns {import('./mission-types.js').VectorObservation} */
    const vector = (value, unit, coordinateFrame, epochSeconds, source, description, classification = 'INITIALIZED_MISSION_INPUT') => ({
      value, unit, coordinateFrame, epochSeconds, mode: 'STATIC_EDUCATIONAL_ILLUSTRATION', availability: value === null ? 'UNAVAILABLE' : 'AVAILABLE',
      source: source === null ? null : evidence(scenario, source, classification), description,
    });
    const snapshot = {
      scenarioId: id, title: scenario.title, mode: /** @type {const} */ ('VERIFIED_RECORDED_EXECUTION'),
      source: evidence(scenario, frame.source), replayElapsedSeconds, observedFrameSeconds: frame.t, frame,
      missionClock: observation(scenario, frame.observedClockSeconds, frame.observationSources.clock, 's GET', 'Last observed AGC mission clock; held between actual measurements, independent of replay elapsed time.'),
      spacecraft: {
        position: vector(initial.positionM, 'm', initial.positionFrame, initial.epochSeconds, initial.source, 'Initialized spacecraft position, not current telemetry.'),
        velocity: vector(initial.velocityMps, 'm/s', initial.velocityFrame, initial.epochSeconds, initial.source, 'Initialized spacecraft velocity; no browser propagation.'),
        landingSite: vector(initial.landingSiteBasicRefAtTlandM, 'm', initial.siteFrame, initial.targetLandingTimeSeconds, initial.siteSource, 'Independent transformation of the supplied target into basic REF at TLAND; a different epoch from spacecraft state.', 'INDEPENDENT_PROJECTION'),
        lunarRadius: { value: initial.lunarRadiusM, unit: /** @type {const} */ ('m'), classification: /** @type {const} */ ('SYNTHETIC_ASSUMPTION') },
        propagation: /** @type {const} */ ('NONE'), assumptions: scenario.assumptions,
      },
      guidance: {
        stage: frame.stage, observedRootCount: frame.rootCount,
        timeToGo: observation(scenario, frame.signedTimeToGoSeconds, frame.observationSources.timeToGo, 's', 'Signed original guidance time-to-go value; not a wall-clock countdown.'),
        ignitionTime: observation(scenario, frame.ignitionTimeSeconds, frame.observationSources.ignitionTime, 's GET', 'Absolute calculated ignition time from synthetic mission epoch, not remaining time.'),
        ignitionLeadAtSolution: observation(scenario, frame.ignitionLeadSeconds, frame.observationSources.ignitionLead, 's', 'Ignition time minus AGC clock at the retained solution observation; not continuously updated remaining time.'),
        alarms: frame.alarms,
      },
      dsky: { digits: frame.dsky, mode: /** @type {const} */ ('VERIFIED_RECORDED_EXECUTION'), source: frame.observationSources.dsky === null ? null : evidence(scenario, frame.observationSources.dsky),
        indicatorLights: { availability: /** @type {const} */ ('UNAVAILABLE'), reason: 'Indicator-light states are not decoded by the verified Phase 10 display exporter.' },
        signLights: { availability: /** @type {const} */ ('UNAVAILABLE'), reason: 'Register sign lamps are not decoded; retained digit strings are displayed unchanged.' } },
      events: scenario.events.filter(event => event.t <= replayElapsedSeconds).map(event => ({ ...event, mode: /** @type {const} */ ('VERIFIED_RECORDED_EXECUTION'), evidence: evidence(scenario, event.source) })),
      capabilities: MISSION_CAPABILITIES,
    };
    return freeze(snapshot);
  }

  /** Final retained outcomes for comparison, never presented as the selected replay instant. @returns {readonly import('./mission-types.js').ScenarioComparison[]} */
  compareScenarios() {
    return freeze(this.recording.cases.map(scenario => ({
      id: scenario.id, title: scenario.title, outcome: scenario.outcome, durationSeconds: scenario.durationSeconds,
      mode: /** @type {const} */ ('VERIFIED_RECORDED_EXECUTION'), rootCount: scenario.result.rootCount,
      reviewReached: scenario.result.reviewReached, ignitionTimeSeconds: scenario.result.ignitionTimeSeconds,
      ignitionLeadSeconds: scenario.result.ignitionLeadSeconds, finalAlarms: scenario.result.finalAlarms,
      source: evidence(scenario, scenario.frames[scenario.frames.length - 1].source),
    })));
  }
}

/** Capability discovery only. Actual piloting stays in the existing, separately gated attitude application. */
export class LiveBackendProvider {
  /** @param {{fetchImpl?: FetchFunction}} [options] */
  constructor({ fetchImpl = browserFetch } = {}) { this.fetchImpl = fetchImpl; }

  /** @param {'/api/bootstrap' | '/api/status'} path @returns {Promise<Record<string, unknown>>} */
  async read(path) {
    if (path !== '/api/bootstrap' && path !== '/api/status') throw new Error('Unsupported read-only backend endpoint.');
    if (typeof this.fetchImpl !== 'function') throw new Error('No browser data transport is available.');
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 3000);
    try {
      const fetchImpl = this.fetchImpl;
      const response = await fetchImpl(path, { method: 'GET', cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error(`Existing backend is unavailable (HTTP ${response.status}).`);
      const value = await response.json();
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid existing-backend response.');
      return value;
    } finally { clearTimeout(deadline); }
  }

  /** @returns {Promise<import('./mission-types.js').BackendDiscovery>} */
  async discover() {
    try {
      const bootstrap = await this.read('/api/bootstrap');
      if (typeof bootstrap.liveEnabled !== 'boolean' || !Array.isArray(bootstrap.axes) || bootstrap.axes.length !== 2 || new Set(bootstrap.axes).size !== 2 || !bootstrap.axes.every(axis => axis === 'yaw' || axis === 'pitch')) throw new Error('Unsupported backend capabilities.');
      const state = await this.getStatus();
      const enabled = bootstrap.liveEnabled;
      const usable = enabled && state.availability === 'AVAILABLE';
      const attitude = /** @type {MissionCapability} */ ({ id: 'live-attitude', label: 'Bounded live AGC attitude', availability: usable ? 'AVAILABLE' : 'UNAVAILABLE', mode: usable ? 'LIVE_AGC_EXECUTION' : null, description: enabled ? 'Existing yaw/pitch RHC service is enabled. Startup and piloting require the separate attitude screen; no live guidance service is implied.' : 'This server is replay-only; native attitude startup is disabled.' });
      return freeze({ available: state.availability === 'AVAILABLE', liveEnabled: enabled, status: state.status, message: state.availability === 'AVAILABLE' ? attitude.description : state.message, capabilities: [attitude, ...MISSION_CAPABILITIES] });
    } catch (error) {
      return freeze({ available: false, liveEnabled: false, status: 'unavailable', message: error instanceof Error ? error.message : 'Existing backend is unavailable.', capabilities: [unavailableAttitude(), ...MISSION_CAPABILITIES] });
    }
  }

  /** @returns {Promise<import('./mission-types.js').LiveBackendState>} */
  async getStatus() {
    try {
      const state = await this.read('/api/status');
      if (typeof state.status !== 'string' || (state.sessionId !== null && typeof state.sessionId !== 'string')) throw new Error('Invalid backend status.');
      const frame = state.frame;
      if (frame !== null && frame !== undefined && (typeof frame !== 'object' || Array.isArray(frame))) throw new Error('Invalid attitude sample.');
      return freeze({ mode: /** @type {const} */ ('LIVE_BACKEND_STATUS'), availability: /** @type {const} */ ('AVAILABLE'), status: state.status, sessionId: state.sessionId, message: typeof state.message === 'string' ? state.message : 'Existing attitude service status.', attitudeFrame: frame ? /** @type {Record<string, unknown>} */ (frame) : null });
    } catch (error) {
      return freeze({ mode: /** @type {const} */ ('LIVE_BACKEND_STATUS'), availability: /** @type {const} */ ('UNAVAILABLE'), status: 'unavailable', sessionId: null, message: error instanceof Error ? error.message : 'Existing backend is unavailable.', attitudeFrame: null });
    }
  }

  /** Never POST a fabricated or unsupported guidance command. @param {unknown} _command @returns {import('./mission-types.js').CommandResult} */
  command(_command) { return freeze({ accepted: false, status: 'UNSUPPORTED', reason: 'This mission provider is read-only. Use the existing attitude screen for its validated, bounded yaw/pitch inputs.' }); }
}

/** @returns {MissionCapability} */
function unavailableAttitude() { return { id: 'live-attitude', label: 'Bounded live AGC attitude', availability: 'UNAVAILABLE', mode: null, description: 'Existing local attitude backend could not be discovered; recorded guidance remains available.' }; }
