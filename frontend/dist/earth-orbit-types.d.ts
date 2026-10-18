export type EarthOrbitMode = 'LIVE ORIGINAL CMC EXECUTION';
export type DskyKey = '0'|'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'|'+'|'-'|'VERB'|'NOUN'|'CLR'|'PRO'|'KEY REL'|'ENTR'|'RSET';
export interface EarthOrbitCapabilities {available:boolean;mode:EarthOrbitMode;software:'Comanche055';scope:string;unavailableReason:string|null;supportedKeys:DskyKey[];}
export interface EarthOrbitTaskStep {id:string;title:string;description:string;complete:boolean;active:boolean;}
export interface EarthOrbitTask {id:string;title:string;complete:boolean;steps:EarthOrbitTaskStep[];nextInstruction:string;scope:string;flightExecuted:false;alignmentCompleted:false;}
export interface CmcKeyObservation {key:DskyKey;code:number;channel:number;cycle:number;sequence:number;}
export interface EarthOrbitSnapshot {
  schemaVersion:1;mode:EarthOrbitMode;available:boolean;status:'idle'|'ready'|'error'|'stopped';sessionId:string|null;revision:number;nextSequence:number;
  computer:null|{software:'Comanche055';cycle:number;cpuSeconds:number;dsky:Record<'PROG'|'VERB'|'NOUN'|'R1'|'R2'|'R3',string>&{signs?:Record<'R1'|'R2'|'R3',null|'+'|'-'|' '>;lamps?:Record<'keyRelease'|'operatorError'|'computerActivity'|'verbNounFlash',null|boolean>};dskySource:null|{channel:8;cycle:number};lastKey:CmcKeyObservation|null;provenance:{ropeSha256:string;engineSha256:string;sourceUrl:string}};
  task:EarthOrbitTask;inputs:unknown[];error:string|null;
  ack?:{sessionId:string;sequence:number;key:DskyKey;channel:number;code:number;queuedAtCycle:number;afterCycle:number};
}
export interface EarthOrbitPanelState {available:boolean;loading:boolean;visible:boolean;busy:boolean;snapshot:EarthOrbitSnapshot|null;error:string|null;}
export interface EarthOrbitPanel {load():Promise<void>;setVisible(visible:boolean):void;dispose():void;readonly state:EarthOrbitPanelState;}
