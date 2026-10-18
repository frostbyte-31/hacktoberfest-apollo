/** Current historical-reference contracts. These types do not describe a flight API. */
export type CampaignMode = 'HISTORICAL MISSION REFERENCE';
export type CampaignGoalId = 'lunar-orbit' | 'lunar-landing' | 'earth-return';
export type CampaignStageId =
  | 'earth-parking' | 'tli' | 'transposition-extraction' | 'translunar-coast'
  | 'lunar-orbit-insertion' | 'lunar-orbit' | 'lm-preparation' | 'undocking-inspection'
  | 'descent-orbit-insertion' | 'powered-descent' | 'lunar-surface' | 'lunar-ascent'
  | 'rendezvous-docking' | 'transearth-injection' | 'transearth-coast' | 'entry-splashdown';
export type HistoricalMissionCapability =
  | 'historicalEarthParkingOrbit' | 'historicalSaturnTli'
  | 'historicalTranspositionExtraction' | 'historicalTranslunarCoast'
  | 'historicalLunarOrbitInsertion' | 'historicalLunarOrbit'
  | 'historicalLmActivation' | 'historicalOrbitalUndocking'
  | 'historicalDescentOrbitInsertion' | 'historicalAgcPoweredDescent'
  | 'historicalLunarSurfaceOperations' | 'historicalLunarAscent'
  | 'historicalRendezvousDocking' | 'historicalTransearthInjection'
  | 'historicalTransearthCoast' | 'historicalEarthEntryRecovery';
export type CampaignEvidenceId = 'guidance' | 'undocking-trainer' | 'propulsion';
export type CampaignConfiguration =
  | 'earth-stack' | 'docked-csm-lm' | 'docked-csm-lm-deployed'
  | 'lm' | 'ascent' | 'ascent-csm' | 'csm' | 'cm';
export type CampaignReferenceStatus = 'reference-reviewed' | 'reference-unreviewed';

export interface CampaignSource {
  readonly id: string;
  readonly title: string;
  /** Runtime validation requires HTTPS without embedded credentials. */
  readonly url: string;
  readonly locator: string;
}
export interface CampaignGoal {
  readonly id: CampaignGoalId;
  readonly title: string;
  readonly summary: string;
  readonly stageIds: readonly CampaignStageId[];
}
export interface CampaignStage {
  readonly id: CampaignStageId;
  readonly goalId: CampaignGoalId;
  readonly order: number;
  readonly title: string;
  /** Historical GET label; not an authoritative simulation timestamp. */
  readonly getLabel: string;
  readonly vehicle: string;
  /** Schematic spacecraft configuration; contains no physical state. */
  readonly configuration: CampaignConfiguration;
  readonly computer: string;
  readonly controlAuthority: string;
  readonly description: string;
  readonly historicalAction: string;
  /** Includes the explicit full-historical-flight capability for this stage. */
  readonly requiredCapabilities: readonly string[];
  /** Related partial evidence never satisfies a full historical flight capability. */
  readonly evidenceIds: readonly CampaignEvidenceId[];
  readonly sourceIds: readonly string[];
}
export interface CampaignCatalog {
  readonly schemaVersion: 1;
  /** Validated in lunar-orbit, lunar-landing, earth-return order. */
  readonly goals: readonly [CampaignGoal, CampaignGoal, CampaignGoal];
  /** Runtime validation requires exactly sixteen stages in the documented order. */
  readonly stages: readonly CampaignStage[];
  readonly sources: readonly CampaignSource[];
}
/** Deeply immutable navigation state created by campaign-state.mjs, never flight state. */
export interface CampaignReviewState {
  readonly schemaVersion: 1;
  readonly mode: CampaignMode;
  readonly catalog: CampaignCatalog;
  readonly cursor: number;
  readonly currentStageId: CampaignStageId;
  readonly currentGoalId: CampaignGoalId;
  readonly currentStage: CampaignStage;
  readonly reviewedStageIds: readonly CampaignStageId[];
  readonly stageStatuses: Readonly<Record<CampaignStageId, CampaignReferenceStatus>>;
  readonly goalStatuses: Readonly<Record<CampaignGoalId, 'unavailable'>>;
  readonly missionCompleted: false;
  readonly flightExecuted: false;
}
export interface CampaignStageAvailability {
  readonly id: CampaignStageId;
  readonly available: false;
  readonly referenceAvailable: true;
  readonly missingCapabilities: readonly string[];
  readonly partialEvidenceIds: readonly CampaignEvidenceId[];
  readonly reason: string;
}
export interface CampaignGoalAvailability {
  readonly id: CampaignGoalId;
  readonly available: false;
  readonly status: 'unavailable';
  readonly missingCapabilities: readonly string[];
}
export interface CampaignAvailabilityReport {
  readonly available: false;
  readonly fullMissionAvailable: false;
  readonly referenceAvailable: true;
  readonly mode: CampaignMode;
  readonly reason: string;
  readonly missingCapabilities: readonly string[];
  readonly stages: readonly CampaignStageAvailability[];
  readonly goals: readonly CampaignGoalAvailability[];
  readonly stageAvailability: Readonly<Record<CampaignStageId, CampaignStageAvailability>>;
  readonly goalAvailability: Readonly<Record<CampaignGoalId, CampaignGoalAvailability>>;
}
export type VerifiedHistoricalMissionCapabilities = Readonly<Record<HistoricalMissionCapability, false>>;

export type AgcShowcaseKind = 'guidance' | 'propulsion';
/** Public state of the implemented read-only agc-showcase.mjs component. */
export interface AgcShowcasePublicState {
  readonly available: boolean;
  readonly loading: boolean;
  readonly kind: AgcShowcaseKind;
  readonly playing: boolean;
  readonly index: number;
  readonly eventCount: number;
  readonly eventId: string | null;
  /** Reaching the last recorded observation is not completion of a maneuver. */
  readonly excerptComplete: boolean;
  readonly originalExecutionMode: 'VERIFIED RECORDED EXECUTION';
  readonly mode: 'RECORDED OBSERVATION STEPPING';
  readonly historicalFlightDemonstrated: false;
  readonly error: string | null;
  readonly graphicsError: string | null;
}
