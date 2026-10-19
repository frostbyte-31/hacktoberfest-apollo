import type {CampaignStageId} from './campaign-types.d.ts';
import type {AlignmentSnapshot} from './earth-alignment-types.d.ts';
export type CampaignTaskKind='live-original-computer'|'pending-original-computer'|'unavailable';
export interface CampaignTaskDefinition {
 readonly stageId:CampaignStageId; readonly taskId:string; readonly kind:CampaignTaskKind;
 readonly title:string; readonly scope:string; readonly missingDependencies:readonly string[];
 readonly flightExecuted:false;
}
export interface CampaignTaskReceipt {
 readonly schemaVersion:1; readonly stageId:'earth-parking'; readonly taskId:'original-p52-alignment';
 readonly kind:'ORIGINAL CMC TASK RECEIPT'; readonly verification:'service-observed'|'local-history-unverified';
 readonly sessionId:string; readonly software:'Comanche055'; readonly ropeSha256:string; readonly engineSha256:string;
 readonly revision:number; readonly sequence:number; readonly cycle:number; readonly completionCycle:number;
 readonly checkpointIds:readonly string[]; readonly flightExecuted:false; readonly scope:string;
}
export interface CampaignTaskRun {
 readonly sessionId:string; readonly software:'Comanche055'; readonly ropeSha256:string; readonly engineSha256:string;
 readonly revision:number; readonly nextSequence:number; readonly cycle:number;
 readonly completedTaskId:'original-p52-alignment'|null; readonly completionCycle:number|null;
}
export interface CampaignTaskProgress {
 readonly schemaVersion:1; readonly campaignRevision:string; readonly sourceRevision:string;
 readonly receipts:readonly CampaignTaskReceipt[]; readonly receiptCount:number;
 /** A runtime observation only. Never serialized or restored. */
 readonly activeSession:CampaignTaskRun|null; readonly seenSessionIds:readonly string[];
 readonly flightExecuted:false; readonly missionCompleted:false;
}
export interface CampaignTaskCapabilities {readonly alignmentAvailable?:boolean; readonly thrustMonitorAvailable?:boolean;}
export interface CampaignTaskStatus extends CampaignTaskDefinition {
 readonly status:'completed-current-run'|'completed-previous-run'|'in-progress'|'ready'|'unavailable';
 readonly canOperate:boolean; readonly complete:boolean; readonly currentRun:boolean;
 readonly reason:string; readonly receipt:CampaignTaskReceipt|null;
}
export interface CampaignTaskStorage {getItem(key:string):string|null;setItem(key:string,value:string):void;}
export declare const CAMPAIGN_TASK_REVISION:string;
export declare const CAMPAIGN_TASK_STORAGE_KEY:string;
export declare const PINNED_COMANCHE_ROPE_SHA256:string;
export declare const CAMPAIGN_TASK_SOURCE_REVISION:string;
export declare const CAMPAIGN_TASK_CATALOG:readonly CampaignTaskDefinition[];
export declare function createCampaignTaskState():CampaignTaskProgress;
export declare function resetCampaignTaskProgress():CampaignTaskProgress;
export declare function invalidateCampaignTaskSession(state:CampaignTaskProgress):CampaignTaskProgress;
/** Consumes a source-validated snapshot; does not issue any HTTP request or input. */
export declare function observeCampaignTaskSnapshot(state:CampaignTaskProgress,snapshot:AlignmentSnapshot):CampaignTaskProgress;
export declare function campaignTaskStatus(state:CampaignTaskProgress,stageId:CampaignStageId,capabilities?:CampaignTaskCapabilities|null):CampaignTaskStatus;
export declare function serializeCampaignTaskProgress(state:CampaignTaskProgress):string;
export declare function restoreCampaignTaskProgress(serialized:string):CampaignTaskProgress;
export declare function readCampaignTaskProgress(storage:CampaignTaskStorage|null|undefined):CampaignTaskProgress;
export declare function saveCampaignTaskProgress(storage:CampaignTaskStorage|null|undefined,state:CampaignTaskProgress):boolean;
