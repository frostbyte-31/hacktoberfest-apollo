/** Frontend-domain contracts. No command interface or flight dynamics lives here. */
export type ExecutionMode = 'VERIFIED_RECORDED_EXECUTION' | 'LIVE_AGC_EXECUTION' | 'STATIC_EDUCATIONAL_ILLUSTRATION' | 'LIVE_BACKEND_STATUS';
export type Availability = 'AVAILABLE' | 'UNAVAILABLE' | 'PLANNED';
export type Vector3 = readonly [number, number, number];
export interface RawSource { readonly rawLine: number; readonly cycle: number; readonly [key: string]: unknown }
export interface EvidenceSource {
  readonly tracePath: string;
  readonly sha256: string;
  readonly cycle: number;
  readonly rawLine: number;
  readonly classification: 'AGC_RECORDED' | 'INITIALIZED_MISSION_INPUT' | 'INDEPENDENT_PROJECTION';
}
export interface Observation<T> {
  readonly value: T | null;
  readonly unit: string;
  readonly availability: Availability;
  readonly source: EvidenceSource | null;
  readonly description: string;
}
export interface DSKYDigits { readonly PROG: string; readonly VERB: string; readonly NOUN: string; readonly R1: string; readonly R2: string; readonly R3: string }
export interface DSKYState {
  readonly digits: DSKYDigits;
  readonly mode: 'VERIFIED_RECORDED_EXECUTION';
  readonly source: EvidenceSource | null;
  readonly indicatorLights: { readonly availability: 'UNAVAILABLE'; readonly reason: string };
  readonly signLights: { readonly availability: 'UNAVAILABLE'; readonly reason: string };
}
export interface GuidanceFrame {
  readonly cycle: number; readonly t: number; readonly dsky: DSKYDigits; readonly stage: string;
  readonly observedClockSeconds: number | null; readonly signedTimeToGoSeconds: number | null;
  readonly ignitionTimeSeconds: number | null; readonly ignitionLeadSeconds: number | null;
  readonly rootCount: number; readonly alarms: readonly string[];
  readonly observationSources: Readonly<Record<'dsky' | 'clock' | 'timeToGo' | 'ignitionTime' | 'ignitionLead' | 'alarms', RawSource | null>>;
  readonly source: RawSource;
}
export interface RecordedEvent { readonly id: string; readonly title: string; readonly description: string; readonly cycle: number; readonly t: number; readonly source: RawSource }
export interface InitialState {
  readonly positionM: Vector3; readonly velocityMps: Vector3;
  readonly landingSiteMoonFixedM: Vector3 | null; readonly landingSiteBasicRefAtTlandM: Vector3 | null;
  readonly epochSeconds: number; readonly targetLandingTimeSeconds: number; readonly lunarRadiusM: number;
  readonly altitudeM: number; readonly speedMps: number;
  readonly positionFrame: string; readonly velocityFrame: string; readonly siteFrame: string; readonly projection: string;
  readonly source: RawSource; readonly siteSource: RawSource | null;
}
export interface RecordedScenario {
  readonly id: string; readonly title: string; readonly outcome: string;
  readonly durationSeconds: number; readonly horizonCycle: number;
  readonly initialState: InitialState; readonly assumptions: readonly string[];
  readonly frames: readonly GuidanceFrame[]; readonly events: readonly RecordedEvent[];
  readonly sources: { readonly tracePath: string; readonly rawSha256: string; readonly [key: string]: string };
  readonly result: { readonly rootCount: number; readonly ignitionTimeSeconds: number | null; readonly observedClockSeconds: number | null;
    readonly ignitionLeadSeconds: number | null; readonly finalAlarms: readonly string[]; readonly reviewReached: boolean; readonly finalDsky: DSKYDigits; readonly allOriginalChecksPass: boolean };
}
export interface GuidanceRecording {
  readonly schemaVersion: 1; readonly mode: 'RECORDED AUTHENTIC EXECUTION REPLAY';
  readonly cases: readonly RecordedScenario[]; readonly provenance: Readonly<Record<string, unknown>>;
  readonly clock: { readonly secondsPerCpuCall: number; readonly sampling: string };
  readonly [key: string]: unknown;
}
export interface VectorObservation extends Observation<Vector3> {
  readonly coordinateFrame: string; readonly epochSeconds: number;
  readonly mode: 'STATIC_EDUCATIONAL_ILLUSTRATION';
}
export interface SpacecraftState {
  readonly position: VectorObservation; readonly velocity: VectorObservation;
  readonly landingSite: VectorObservation;
  readonly lunarRadius: { readonly value: number; readonly unit: 'm'; readonly classification: 'SYNTHETIC_ASSUMPTION' };
  readonly propagation: 'NONE'; readonly assumptions: readonly string[];
}
export interface MissionEvent extends RecordedEvent { readonly mode: 'VERIFIED_RECORDED_EXECUTION'; readonly evidence: EvidenceSource }
export interface MissionSnapshot {
  readonly scenarioId: string; readonly title: string;
  readonly mode: 'VERIFIED_RECORDED_EXECUTION'; readonly source: EvidenceSource;
  readonly replayElapsedSeconds: number; readonly observedFrameSeconds: number;
  readonly frame: GuidanceFrame;
  readonly missionClock: Observation<number>; readonly spacecraft: SpacecraftState;
  readonly guidance: { readonly stage: string; readonly observedRootCount: number;
    readonly timeToGo: Observation<number>; readonly ignitionTime: Observation<number>; readonly ignitionLeadAtSolution: Observation<number>;
    readonly alarms: readonly string[] };
  readonly dsky: DSKYState; readonly events: readonly MissionEvent[];
  readonly capabilities: readonly MissionCapability[];
}
export interface ScenarioComparison {
  readonly id: string; readonly title: string; readonly outcome: string;
  readonly mode: 'VERIFIED_RECORDED_EXECUTION'; readonly durationSeconds: number;
  readonly rootCount: number; readonly reviewReached: boolean; readonly ignitionTimeSeconds: number | null;
  readonly ignitionLeadSeconds: number | null; readonly finalAlarms: readonly string[];
  readonly source: EvidenceSource;
}
export interface CrewMember {
  readonly id: 'commander' | 'lunar-module-pilot' | 'command-module-pilot';
  readonly name: string; readonly role: string; readonly location: string;
  readonly participantTypes: readonly ['HUMAN', 'AI']; readonly availability: 'PLANNED';
}
export interface MissionCapability {
  readonly id: string; readonly label: string; readonly availability: Availability;
  readonly mode: ExecutionMode | null; readonly description: string;
}
export interface BackendDiscovery {
  readonly available: boolean; readonly liveEnabled: boolean; readonly status: string; readonly message: string;
  readonly capabilities: readonly MissionCapability[];
}
export interface LiveBackendState {
  readonly mode: 'LIVE_BACKEND_STATUS'; readonly availability: Availability;
  readonly status: string; readonly sessionId: string | null; readonly message: string;
  /** An existing attitude sample is supplied without pretending it contains Phase 10 guidance. */
  readonly attitudeFrame: Readonly<Record<string, unknown>> | null;
}
export interface CommandResult { readonly accepted: false; readonly status: 'UNSUPPORTED'; readonly reason: string }
export type FetchFunction = (input: string, init?: RequestInit) => Promise<Pick<Response, 'ok' | 'status' | 'json'>>;
