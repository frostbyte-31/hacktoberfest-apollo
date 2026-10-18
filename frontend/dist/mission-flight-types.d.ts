export type Vector3=[number,number,number];
export type QuaternionWxyz=[number,number,number,number];
export interface TraceSource{rawLine:number;cycle:number}
export interface PhysicalObservation{
  positionM:Vector3;velocityMps:Vector3;quaternion:QuaternionWxyz;
  physicalTimeSeconds:number;elapsedPhysicalSeconds:number;
  massKg:number;fuelKg:number;deliveredThrustN:number;commandedThrustN:number;
  engineEnabled:boolean;requestedEngineEnabled:boolean;physicalEngineConnected:boolean;
  specificForceMps2:Vector3;gravityMps2:Vector3;totalAccelerationMps2:Vector3;
  source:TraceSource;
}
export interface RecordedCockpitFrame{
  cycle:number;t:number;source:TraceSource;
  dsky:Record<'PROG'|'VERB'|'NOUN'|'R1'|'R2'|'R3',string>;
  observedProgram:number|null;stage:string;spacecraft:PhysicalObservation|null;
  receiver:null|{armed:boolean;autothrottle:boolean;requestedEngineOn:boolean;enabled:boolean;automaticCount:number;commandedThrustN:number;source:TraceSource};
  crewDiscretes:Record<string,{value:number;valueOctal:string;source:TraceSource}>;
  observationSources:{dsky:TraceSource|null;program:TraceSource|null};
  pipa:{generatedCounts:Vector3;deliveredCounts:Vector3;source:TraceSource|null};
}
export interface HistoricalProcedureReference{
  id:string;title:string;vehicle:string;crewRole:string;getLabel:string;order:number;
  sourceIds:string[];description:string;
}
export interface MissionCommandResult{accepted:false;status:'unavailable';mode:'VERIFIED RECORDED EXECUTION';reason:string}
export interface RecordedMissionEvent{
  id:string;title:string;description:string;kind:string;cycle:number;t:number;
  source:TraceSource;keys?:string;routine?:string;
}
export interface PropulsionSnapshot{
  mode:'VERIFIED RECORDED EXECUTION';availability:'recorded-observation';caseId:string;
  replay:{seconds:number;durationSeconds:number;units:'s';clock:string};
  frame:RecordedCockpitFrame;event:RecordedMissionEvent|null;
  spacecraft:(PhysicalObservation&{mode:'VERIFIED RECORDED EXECUTION';coordinateFrame:string;quaternionFrame:string;units:{position:'m';velocity:'m/s';mass:'kg';fuel:'kg';force:'N'}})|null;
  source:TraceSource&{path:string;rawSha256:string};capabilities:Readonly<Record<string,boolean>>;
}
export interface PropulsionDataProvider{
  getSnapshot(caseId:string,seconds:number):PropulsionSnapshot;
  getEventSnapshot(caseId:string,eventId:string):PropulsionSnapshot;
  trajectoryThrough(caseId:string,seconds:number,bound?:{rawLine?:number}):ReadonlyArray<Readonly<Vector3>>;
  command():Promise<MissionCommandResult>;
}
