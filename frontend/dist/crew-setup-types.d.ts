/** Frontend configuration contract; these fields do not assert backend API support. */
export type ApolloCrewRole = 'CDR' | 'LMP' | 'CMP';
export type CrewParticipant = 'human' | 'ai';
export type HumanParticipation = 'solo' | 'shared-device' | 'network';
export type CrewPresetId = 'solo' | 'human-crew' | 'commander-ai';

export interface ApolloCrewSeat {
  readonly role: ApolloCrewRole;
  readonly title: string;
  readonly name: string;
  readonly vehicle: 'Eagle' | 'Columbia';
}

export interface CrewSetup {
  readonly schemaVersion: 1;
  readonly humanParticipation: HumanParticipation;
  readonly assignments: Readonly<Record<ApolloCrewRole, CrewParticipant>>;
}

export interface CrewPreset {
  readonly id: CrewPresetId;
  readonly label: string;
  readonly description: string;
  readonly setup: CrewSetup;
}

/**
 * A verified adapter supplies these capabilities. Merely selecting AI or network
 * participants never creates an AI service, shared session, or permission grant.
 */
export interface CrewSetupCapabilities {
  readonly localHumanStations?: boolean;
  readonly networkHumanStations?: boolean;
  readonly aiCrew?: boolean;
}

export interface CrewRosterSeat extends ApolloCrewSeat {
  readonly participant: CrewParticipant;
}

export interface CrewSetupIssue {
  readonly code: 'invalid-configuration' | 'local-human-unavailable' | 'network-human-unavailable' | 'ai-unavailable';
  readonly message: string;
}

export interface CrewSetupValidation {
  readonly valid: boolean;
  readonly canStart: boolean;
  readonly classification: 'LOCAL CREW CONFIGURATION';
  readonly humanCount: number;
  readonly aiCount: number;
  readonly roster: readonly CrewRosterSeat[];
  readonly issues: readonly CrewSetupIssue[];
  readonly description: string;
  readonly networkMultiplayer: boolean;
}
