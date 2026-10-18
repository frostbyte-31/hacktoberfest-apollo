/** New application API. Recorded AGC providers keep their independent contract. */
export type RoleId = 'commander' | 'lunar-module-pilot' | 'command-module-pilot';
export type Vector3 = readonly [number, number, number];
export interface LabMeasurements {
 massKg: number; fuelKg: number; altitudeM: number; verticalSpeedMps: number;
 horizontalSpeedMps: number; horizontalVelocityMps: number; downrangeM: number; pitchDeg: number;
}
export interface LabSpacecraft extends LabMeasurements {
 positionM: Vector3; velocityMps: Vector3; accelerationMps2: Vector3;
 specificForceMps2: Vector3; gravityMps2: Vector3;
 quaternionBodyToRef: readonly [number,number,number,number]; angularVelocityRadps: Vector3;
}
export interface LabThresholds {
 verticalSpeedMps:number;horizontalSpeedMps:number;pitchDeg:number;
 landingSiteDistanceM:number;lossOfControlPitchDeg:number;timeLimitSeconds:number;
}
export interface LabOutcome {
 success:boolean;reasons:readonly string[];measured:LabMeasurements;thresholds:LabThresholds;
}
export interface LabPhysicsState {
 mode:'EDUCATIONAL_PHYSICS_LAB';source:string;status:string;
 scenario:string;simTimeSeconds:number;tick:number;
 controls:{throttle:number;pitch:number};spacecraft:LabSpacecraft;
 engine:{enabled:boolean;throttle:number;thrustN:number;massFlowKgps:number;
 thrustVectorN:Vector3;lastStepAverageThrustN:number};
 outcome:LabOutcome|null;thresholds:LabThresholds;
 units:{position:'m';velocity:'m/s';acceleration:'m/s²';mass:'kg';time:'s';
 thrust:'N';angularVelocity:'rad/s';pitch:'degree'};
 frame:{name:string;origin:string;initialUp:'+X';downrange:'+Z';thrustBodyAxis:'+X';positivePitch:string};
 provenance:Record<string,unknown>;assumptions:readonly string[];
}
export interface LabSnapshot {
 schemaVersion: 1; id: string; runId: string; title: string;
 mode: 'EDUCATIONAL_PHYSICS_LAB'; status: 'lobby'|'running'|'paused'|'completed'|'fault';
 revision: number; capabilities: Record<string,boolean>;
 physics:LabPhysicsState;
 crew:readonly {id:RoleId;name:string;role:string;location:string;responsibility:string;
 kind:'human'|'fallback'|'llm';occupied:boolean;ready:boolean;displayName:string;
 connected:boolean;agentStatus:string|null}[];
 events:readonly {id:number;timeSeconds:number;type:string;text:string;actor:string}[];
 messages:readonly {id:number;timeSeconds:number;role:RoleId|null;name:string;text:string;source:string}[];
 checklist:Partial<Record<'state-vector'|'braking'|'propellant',{done:boolean;by:string;timeSeconds:number}>>;
 trajectory:readonly {t:number;altitudeM:number;downrangeM:number;positionM:Vector3}[];
 debrief:null|Record<string,unknown>;fault:string|null;
 you:null|{role:RoleId|null;name:string;lastSequence:number;host:boolean};assistance:boolean;
}
export interface LabCommandResult {accepted:boolean;sequence:number;revision:number;snapshot:LabSnapshot}
