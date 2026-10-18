import type {EarthOrbitSnapshot,EarthOrbitPanelState,EarthOrbitPanel,DskyKey} from './earth-orbit-types.d.ts';
export type AlignmentMode='LIVE ORIGINAL CMC / MODELED INSTRUMENTS';
export type OpticsMode='MANUAL'|'ZERO'|'CMC';
export interface OpticsDeflection {shaft:number;trunnion:number;rate:'LOW'|'HIGH';seconds:number;}
export interface AlignmentStar {code:string;name:string;shaftDeg:number;trunnionDeg:number;errorDeg:number;}
export interface AlignmentEvidence {referenceInitialized:boolean;p52Complete:boolean;p52Marks:number;torqueApproved:boolean;torqueOutputCount:number;completionCycle:number|null;gyroSensorFeedbackOperations?:number;}
export interface CsmInstruments {mode:'MODELED CSM INSTRUMENTS';imuPowered:boolean;opticsMode:OpticsMode;shaftDeg:number;trunnionDeg:number;mechanicalTrunnionDeg:number;stars:AlignmentStar[];markCount:number;alignment:AlignmentEvidence;scope:string;}
export interface AlignmentSnapshot extends Omit<EarthOrbitSnapshot,'mode'|'computer'|'task'|'ack'> {mode:AlignmentMode;computer:(NonNullable<EarthOrbitSnapshot['computer']>&{instruments:CsmInstruments})|null;task:Omit<EarthOrbitSnapshot['task'],'alignmentCompleted'>&{alignmentCompleted:boolean};ack?:{sessionId:string;sequence:number;queuedAtCycle:number;afterCycle:number;key?:DskyKey;control?:string;value?:unknown};}
export interface AlignmentPanelState extends Omit<EarthOrbitPanelState,'snapshot'> {snapshot:AlignmentSnapshot|null;}
export interface AlignmentPanel extends Omit<EarthOrbitPanel,'state'> {readonly state:AlignmentPanelState;}
