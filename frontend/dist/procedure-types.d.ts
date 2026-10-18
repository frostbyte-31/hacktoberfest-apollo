export type CrewStation='CDR'|'LMP'|'CMP';
export type ProcedureValue=string|number|boolean;
export interface ProcedureStep{
  id:string;kind:'crew-report'|'select'|'momentary';role:CrewStation;
  label:string;instructions:string;locator:string;sourceIds:string[];
  correctValue:ProcedureValue;controlId?:string;
  options?:Array<{value:ProcedureValue;label:string}>;effect?:'release';
}
export interface ProcedureEvent{
  sessionId:string;sequence:number;revision:number;action:string;role:CrewStation;
  kind:ProcedureStep['kind'];value:ProcedureValue;advanced:boolean;
  evidenceKind:'crew-report'|'trainer-control';wallUtc:string;
  sourceIds:string[];locator:string;meaning:string;
}
export interface ProcedureSnapshot{
  schemaVersion:1;mode:'INTERACTIVE PROCEDURE TRAINER';classification:'INTERACTIVE PROCEDURE TRAINER';
  available:boolean;status:'idle'|'active'|'complete';sessionId:string|null;
  revision:number;lastSequence:number;currentStepIndex:number;currentStep:ProcedureStep|null;
  completedStepIds:string[];completed:boolean;controls:Record<string,ProcedureValue>;
  crewReports:Record<string,unknown>;controlEvidence:Record<string,unknown>;
  attachment:'docked'|'released';attachmentEvidence:'initial-trainer-configuration'|'modeled-mechanical-release';
  chapterId:'docked-preparation'|'undocking';unlockedChapterIds:string[];
  events:ProcedureEvent[];definitionSha256:string;message:string;scope:string;
  capabilities:{mode:'INTERACTIVE PROCEDURE TRAINER';originalAgc:false;flightPhysics:false;sensorReadback:false;historicalMissionClock:false};
}
export interface ProcedureAction{
  sessionId:string;sequence:number;expectedRevision:number;role:CrewStation;
  action:string;value:ProcedureValue;
}
export interface ProcedureAcknowledgment{
  accepted:true;advanced:boolean;meaning:string;snapshot:ProcedureSnapshot;
}
