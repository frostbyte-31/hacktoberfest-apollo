/** Frontend-domain contract for presentation observations, independent of AGC memory layout. */
export type ExecutionMode = 'VERIFIED RECORDED EXECUTION' | 'LIVE AGC EXECUTION' | 'STATIC EDUCATIONAL ILLUSTRATION';
export type Availability = 'available' | 'partial' | 'unavailable';
export type Validity = 'recorded-observation' | 'initialized-input' | 'derived-reference' | 'unavailable';
export type Vector3 = readonly [number, number, number];

export interface TraceObservation {
  readonly rawLine: number;
  readonly cycle: number;
  readonly [key: string]: unknown;
}
export interface SourceReference {
  readonly kind: 'retained-trace';
  readonly path: string;
  readonly rawSha256: string;
  readonly rawLine: number;
  readonly cpuCycle: number;
  readonly transform?: { readonly configurationPath: string; readonly field: string };
}
export interface DataTimestamp {
  readonly clock: 'cpu-call-time' | 'initialized-navigation-epoch' | 'target-landing-time';
  readonly seconds: number;
  readonly units: 's';
  readonly cpuCycle?: number;
}
export interface StateMetadata {
  readonly mode: ExecutionMode;
  readonly availability: Availability;
  readonly validity: Validity;
  readonly source: SourceReference | null;
  readonly timestamp: DataTimestamp | null;
}
export interface ObservedQuantity extends StateMetadata {
  readonly value: number | null;
  readonly units: 's';
  readonly coordinateFrame: string;
  readonly label: string;
}
export interface DSKYDigits {
  readonly PROG: string;
  readonly VERB: string;
  readonly NOUN: string;
  readonly R1: string;
  readonly R2: string;
  readonly R3: string;
}
export interface DSKYState extends DSKYDigits, StateMetadata {
  readonly units: 'display digit fields';
  readonly coordinateFrame: null;
  /** These are unavailable in the retained digit-field export, never assumed off. */
  readonly signs: null;
  readonly indicators: null;
  readonly lampAvailability: 'unavailable';
  readonly note: string;
}
export interface GuidanceState extends StateMetadata {
  readonly units: { readonly rootCount: 'count'; readonly alarms: 'octal code' };
  readonly coordinateFrame: null;
  readonly stage: string;
  readonly rootCount: number;
  readonly alarms: readonly string[];
  readonly observedClock: ObservedQuantity;
  readonly signedTimeToGo: ObservedQuantity;
  readonly ignitionTime: ObservedQuantity;
  readonly ignitionLead: ObservedQuantity;
}
export interface LandingSiteReference extends StateMetadata {
  readonly units: 'm';
  readonly coordinateFrame: string;
  readonly positionM: Vector3 | null;
}
export interface SpacecraftState extends StateMetadata {
  readonly mode: 'STATIC EDUCATIONAL ILLUSTRATION';
  readonly units: { readonly position: 'm'; readonly velocity: 'm/s'; readonly altitude: 'm'; readonly speed: 'm/s'; readonly lunarRadius: 'm' };
  readonly coordinateFrame: string;
  readonly velocityFrame: string;
  readonly positionM: Vector3;
  readonly velocityMps: Vector3;
  readonly altitudeM: number | null;
  readonly speedMps: number;
  readonly lunarRadiusM: number;
  readonly landingSite: LandingSiteReference;
  readonly initialState: InitialState;
  readonly note: string;
}
export interface MissionCapability {
  readonly id: 'recorded-guidance' | 'trace-dsky' | 'static-geometry' | 'scenario-comparison' | 'live-guidance' | 'live-dsky-input' | 'powered-descent' | 'multiplayer' | 'ai-crew';
  readonly label: string;
  readonly available: boolean;
  readonly reason: string;
}
export interface CrewMember {
  readonly id: 'commander' | 'lunar-module-pilot' | 'command-module-pilot';
  readonly role: 'COMMANDER' | 'LUNAR MODULE PILOT' | 'COMMAND MODULE PILOT';
  readonly name: 'Neil Armstrong' | 'Buzz Aldrin' | 'Michael Collins';
  readonly vehicle: 'Lunar Module' | 'Command Module';
  readonly status: 'planned';
  /** Future supported seat types, not currently operational participants. */
  readonly participantTypes: readonly ('human' | 'ai')[];
  readonly description: string;
}
export interface RecordedEvent {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  /** CPU-call replay time in seconds; not mission clock or navigation epoch. */
  readonly t: number;
  readonly cycle: number;
  readonly source: TraceObservation;
}
export interface MissionEvent extends Omit<RecordedEvent, 'source'>, StateMetadata {
  readonly units: { readonly t: 's'; readonly cycle: 'CPU calls' };
  readonly coordinateFrame: null;
  readonly observation: TraceObservation;
}
export interface CommandResult {
  readonly accepted: false;
  readonly status: 'unavailable';
  readonly mode: ExecutionMode;
  readonly reason: string;
}
export interface InitialState {
  readonly classification: string;
  readonly positionM: Vector3;
  readonly velocityMps: Vector3;
  readonly landingSiteMoonFixedM: Vector3 | null;
  readonly landingSiteBasicRefAtTlandM: Vector3 | null;
  readonly epochSeconds: number;
  readonly targetLandingTimeSeconds: number;
  readonly lunarRadiusM: number;
  readonly altitudeM: number | null;
  readonly speedMps: number;
  readonly positionFrame: string;
  readonly velocityFrame: string;
  readonly siteFrame: string;
  readonly projection: string;
  readonly source: TraceObservation;
  readonly siteSource: TraceObservation | null;
  readonly transformSource: { readonly configurationPath: string; readonly field: string };
}
export interface RecordedFrame {
  readonly cycle: number;
  readonly t: number;
  readonly dsky: DSKYDigits;
  readonly stage: string;
  readonly observedClockSeconds: number | null;
  readonly signedTimeToGoSeconds: number | null;
  readonly ignitionTimeSeconds: number | null;
  readonly ignitionLeadSeconds: number | null;
  readonly rootCount: number;
  readonly alarms: readonly string[];
  readonly observationSources: Readonly<Record<'dsky' | 'clock' | 'timeToGo' | 'ignitionTime' | 'ignitionLead' | 'alarms', TraceObservation | null>>;
  readonly source: TraceObservation;
}
export interface ScenarioResult {
  readonly rootCount: number;
  readonly ignitionTimeSeconds: number | null;
  readonly observedClockSeconds: number | null;
  readonly ignitionLeadSeconds: number | null;
  readonly finalAlarms: readonly string[];
  readonly reviewReached: boolean;
  readonly finalDsky: DSKYDigits;
  readonly allOriginalChecksPass: boolean;
}
export interface ScenarioSummary {
  readonly id: string;
  readonly title: string;
  readonly outcome: string;
  readonly durationSeconds: number;
  readonly initialState: InitialState;
  readonly result: ScenarioResult;
  readonly sources: Readonly<Record<string, string>> & { readonly tracePath: string; readonly rawSha256: string };
}
export interface RecordedScenario extends ScenarioSummary {
  readonly frames: readonly RecordedFrame[];
  readonly events: readonly RecordedEvent[];
  readonly assumptions: readonly string[];
  readonly horizonCycle: number;
}
export interface RecordedGuidance {
  readonly schemaVersion: 1;
  readonly mode: 'RECORDED AUTHENTIC EXECUTION REPLAY';
  readonly clock: { readonly secondsPerCpuCall: number; readonly sampling: string };
  readonly provenance: Readonly<Record<string, string>> & { readonly evidenceRoot: string };
  readonly labels: Readonly<Record<string, string>>;
  readonly cases: readonly RecordedScenario[];
}
export interface MissionSnapshot extends StateMetadata {
  readonly units: { readonly replay: 's'; readonly cpuCycle: 'CPU calls' };
  readonly coordinateFrame: null;
  readonly replay: { readonly seconds: number; readonly units: 's'; readonly durationSeconds: number; readonly clock: 'cpu-call-time' };
  readonly scenario: ScenarioSummary;
  readonly frame: RecordedFrame;
  readonly dsky: DSKYState;
  readonly guidance: GuidanceState;
  readonly spacecraft: SpacecraftState;
  readonly capabilities: readonly MissionCapability[];
  readonly crew: readonly CrewMember[];
}
/** A future live provider must return real authoritative observations, never synthetic substitutes. */
export interface MissionProvider {
  readonly mode: ExecutionMode;
  getCapabilities(): readonly MissionCapability[];
  getSnapshot(scenarioId: string, replaySeconds: number): MissionSnapshot | null;
  command(command?: unknown): Promise<CommandResult>;
}
