/**
 * Original-computer task progress, separate from historical chapter review.
 * This module never issues commands and never records a flown mission stage.
 * Browser storage is local history, not proof of a live computer session.
 */
import {CAMPAIGN_STAGE_IDS} from './campaign-state.mjs';
import {validateEarthAlignmentSnapshot, EARTH_ALIGNMENT_MODE} from './earth-alignment-client.mjs';

export const CAMPAIGN_TASK_REVISION = 'apollo11-original-tasks-1';
export const CAMPAIGN_TASK_STORAGE_KEY = 'apollo11.original-task-history.v1';
export const PINNED_COMANCHE_ROPE_SHA256 = '2ba31de9291cd10fb351a64d261bae8514a1cb75b4651bfa6a135dfa821a2d79';
export const CAMPAIGN_TASK_SOURCE_REVISION = `Comanche055:${PINNED_COMANCHE_ROPE_SHA256}`;
const P52_STEPS = Object.freeze(['select-p52', 'star-marks', 'star-angle', 'gyro-review', 'alignment-return']);
const P52_CHECKPOINTS = Object.freeze(['select-p52', 'star-marks', 'star-angle', 'gyro-review', 'completion-display', 'alignment-return']);
const states = new WeakSet();
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.trim().length > 0;
const counter = value => Number.isSafeInteger(value) && value >= 0;
const sha = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const clone = value => structuredClone(value);
const freeze = value => {if (value && typeof value === 'object' && !Object.isFrozen(value)) {Object.values(value).forEach(freeze);Object.freeze(value);} return value;};
const invalid = reason => {throw new Error(`Invalid campaign task progress: ${reason}.`);};
const sameList = (a,b) => Array.isArray(a) && a.length === b.length && a.every((value,index) => value === b[index]);
const exactKeys = (value,keys) => object(value) && sameList(Object.keys(value).sort(), [...keys].sort());

const entries = [
  ['earth-parking', 'original-p52-alignment', 'live-original-computer', 'Align Columbia’s navigation platform', 'Original P52 with modeled stationary IMU and optics. Completion includes two star marks, original correction outputs, sensor feedback and P00.', []],
  ['tli', 'original-p47-thrust-monitor', 'pending-original-computer', 'Monitor velocity change with original P47', 'A bounded original-CMC monitoring task, if qualified. It cannot command Saturn’s engine or demonstrate departure.', ['Original P47 timing/navigation initialization: the present fixture reaches alarm 01204', 'Original AS-506 LVDC flight program and validated S-IVB dynamics for actual TLI']],
  ['transposition-extraction', 'retrieve-eagle', 'unavailable', 'Retrieve Eagle', 'Original CMC attitude and translation commands plus docking hardware are required.', ['Validated CMC attitude/translation controls', 'Docking and extraction mechanism state', 'Authoritative relative spacecraft dynamics']],
  ['translunar-coast', 'navigate-to-moon', 'unavailable', 'Navigate to the Moon', 'Original navigation computations need a coherent mission state and measured inputs.', ['Validated translunar state vector', 'Optical navigation and ground-update contracts', 'Authoritative coast and correction dynamics']],
  ['lunar-orbit-insertion', 'lunar-capture', 'unavailable', 'Brake into lunar orbit', 'Original CMC maneuver guidance must operate an integrated SPS and vehicle model.', ['Validated CMC maneuver initial state', 'SPS engine and valve command/readback', 'Lunar capture dynamics and achieved-orbit check']],
  ['lunar-orbit', 'lunar-circularization', 'unavailable', 'Establish lunar parking orbit', 'Circularization requires an original-guidance maneuver and a measured resulting orbit.', ['Verified lunar-orbit checkpoint', 'Integrated SPS maneuver guidance', 'Authoritative orbit solution']],
  ['lm-preparation', 'activate-eagle', 'unavailable', 'Activate Eagle and prepare guidance', 'The retained guidance recording is a separate synthetic experiment, not live activation.', ['Validated live LM activation inputs/readbacks', 'Original LGC alignment and mission-state service', 'Independent AGS readiness contract']],
  ['undocking-inspection', 'undock-and-inspect', 'unavailable', 'Undock and inspect Eagle', 'The separate 28-action undocking trainer does not supply original AGC execution or separation dynamics.', ['Integrated CMC/LGC controls and readbacks', 'Relative vehicle dynamics and inspection state']],
  ['descent-orbit-insertion', 'lower-eagle-orbit', 'unavailable', 'Lower Eagle’s orbit', 'DOI is a separate descent-engine maneuver before powered descent.', ['Verified LM alignment and DOI maneuver state', 'Live original engine controls and sensor returns', 'Integrated DOI dynamics and orbit validation']],
  ['powered-descent', 'original-guidance-landing', 'unavailable', 'Descend and land Eagle', 'Recorded fixed-attitude propulsion evidence does not establish a live original-guidance landing.', ['Coupled original P63/P64/P66 guidance', 'Validated ACA, ROD and engine control paths', 'Radar/inertial sensor feedback', 'Full attitude/translational dynamics and touchdown validation']],
  ['lunar-surface', 'surface-and-ascent-preparation', 'unavailable', 'Secure Eagle and prepare ascent', 'Surface and EVA actions include human and hardware procedures outside the AGC.', ['Surface hardware and life-support readbacks', 'Verified original guidance surface checkpoint', 'Validated ascent preparation controls']],
  ['lunar-ascent', 'launch-eagle-ascent-stage', 'unavailable', 'Launch from the Moon', 'Original ascent guidance needs staging, propulsion, inertial feedback and authoritative vehicle state.', ['Validated LGC ascent checkpoint', 'Stage-separation and ascent-engine controls', 'Integrated ascent dynamics and orbital insertion validation']],
  ['rendezvous-docking', 'rejoin-columbia', 'unavailable', 'Rejoin Columbia', 'Rendezvous guidance, two-vehicle dynamics and docking hardware must be integrated.', ['Original rendezvous navigation and radar inputs', 'Authoritative two-vehicle dynamics', 'Validated RCS, docking and crew-transfer controls']],
  ['transearth-injection', 'depart-lunar-orbit', 'unavailable', 'Depart lunar orbit', 'Original CMC SPS guidance must produce a validated Earth-return trajectory.', ['Validated return maneuver checkpoint', 'SPS enable, valve and cutoff feedback', 'Integrated lunar-departure dynamics']],
  ['transearth-coast', 'navigate-home', 'unavailable', 'Navigate home', 'Original navigation and correction guidance require an authoritative return state.', ['Verified trans-Earth state and navigation inputs', 'Original correction maneuver execution', 'Entry-corridor validation']],
  ['entry-splashdown', 'entry-and-recovery', 'unavailable', 'Enter Earth’s atmosphere and splash down', 'Original entry guidance needs separation, aerodynamic/RCS dynamics and recovery systems.', ['Validated original CMC entry state', 'Service-module separation and entry configuration', 'Atmosphere, aerodynamic and RCS feedback', 'Parachute/recovery model and splashdown validation']],
];
export const CAMPAIGN_TASK_CATALOG = freeze(entries.map(([stageId,taskId,kind,title,scope,missingDependencies]) => ({stageId,taskId,kind,title,scope,missingDependencies,flightExecuted:false})));
if (!sameList(CAMPAIGN_TASK_CATALOG.map(item => item.stageId), CAMPAIGN_STAGE_IDS)) throw new Error('Task catalog must match campaign chronology.');
const taskFor = stageId => {const task = CAMPAIGN_TASK_CATALOG.find(item => item.stageId === stageId);if (!task) invalid('unknown stage');return task;};

function makeState({campaignRevision=CAMPAIGN_TASK_REVISION,sourceRevision=CAMPAIGN_TASK_SOURCE_REVISION,receipts=[],activeSession=null,seenSessionIds=[]}={}) {
  const state=freeze({schemaVersion:1,campaignRevision,sourceRevision,receipts,receiptCount:receipts.length,activeSession,seenSessionIds,flightExecuted:false,missionCompleted:false});states.add(state);return state;
}
function assertState(state) {if (!states.has(state)) invalid('use a created task state');}
/** New progress owns no computer and makes no HTTP requests. */
export function createCampaignTaskState() {return makeState();}
/** A reset clears local task receipts only. It does not reset a live computer. */
export function resetCampaignTaskProgress() {return createCampaignTaskState();}
/** Clear a stale observation after provider failure without issuing a command. */
export function invalidateCampaignTaskSession(state) {assertState(state);return state.activeSession?makeState({...state,activeSession:null}):state;}

function sourceOf(snapshot) {
  const source=snapshot.computer?.provenance;
  if (!source || source.ropeSha256 !== PINNED_COMANCHE_ROPE_SHA256 || !sha(source.engineSha256)) invalid('unexpected original software source');
  return {software:'Comanche055',ropeSha256:source.ropeSha256,engineSha256:source.engineSha256};
}
function validateP52Completion(snapshot) {
  if (snapshot.task.id !== 'original-p52-alignment' || snapshot.task.complete !== true) return false;
  const computer=snapshot.computer,alignment=computer.instruments.alignment;
  if (snapshot.status !== 'ready' || snapshot.error !== null || snapshot.task.alignmentCompleted !== true || snapshot.task.flightExecuted !== false
      || computer.dsky.PROG !== '00' || !sameList(snapshot.task.steps.map(step => step.id),P52_STEPS)
      || snapshot.task.steps.some(step => step.complete !== true || step.active !== false)
      || alignment.referenceInitialized !== true || alignment.p52Complete !== true || alignment.p52Marks < 2
      || alignment.torqueApproved !== true || alignment.torqueOutputCount < 1 || !counter(alignment.gyroSensorFeedbackOperations)
      || alignment.gyroSensorFeedbackOperations < 1 || !counter(alignment.completionCycle) || alignment.completionCycle > computer.cycle) invalid('incomplete P52 completion');
  const checkpoints=snapshot.task.checkpoints;
  if (!sameList(checkpoints?.map(item => item?.id),P52_CHECKPOINTS)) invalid('P52 checkpoint identity or order');
  let previous=-1;
  for (const point of checkpoints) {
    if (!counter(point.cycle) || point.cycle < previous || point.cycle > computer.cycle || !object(point.dsky)
        || !object(point.dskySource) || point.dskySource.channel !== 8 || !counter(point.dskySource.cycle)
        || point.dskySource.cycle > point.cycle) invalid('P52 checkpoint source or clock');
    previous=point.cycle;
  }
  const [selected,marked,angle,torque,complete,returned]=checkpoints;
  if (selected.dsky.PROG !== '52' || marked.dsky.PROG !== '52'
      || angle.dsky.PROG !== '52' || angle.dsky.VERB !== '06' || angle.dsky.NOUN !== '05'
      || !/^\d{5}$/.test(angle.dsky.R1) || Number(angle.dsky.R1)>5
      || torque.dsky.PROG !== '52' || torque.dsky.VERB !== '06' || torque.dsky.NOUN !== '93'
      || !['R1','R2','R3'].every(field => /^\d{5}$/.test(torque.dsky[field]))
      || complete.dsky.VERB !== '50' || complete.dsky.NOUN !== '25' || complete.dsky.R1 !== '00014'
      || returned.dsky.PROG !== '00' || returned.cycle < alignment.completionCycle) invalid('P52 original display checkpoints');
  return true;
}
/**
 * Accept only a validated observation from the existing CMC service. No caller
 * supplied receipt, navigation state, replay-complete flag or capability boolean
 * can complete a task. HTTP transport/authentication remains the provider’s job.
 */
export function observeCampaignTaskSnapshot(state,snapshot) {
  assertState(state);validateEarthAlignmentSnapshot(snapshot);
  if (snapshot.mode !== EARTH_ALIGNMENT_MODE || snapshot.computer === null || snapshot.sessionId === null || snapshot.available !== true
      || snapshot.status !== 'ready' || snapshot.error !== null) return invalidateCampaignTaskSession(state);
  const source=sourceOf(snapshot),previous=state.activeSession,sameSession=previous?.sessionId===snapshot.sessionId;
  if (previous && !sameSession && state.seenSessionIds.includes(snapshot.sessionId)) invalid('stale session after a newer run');
  if (sameSession && (previous.ropeSha256!==source.ropeSha256 || previous.engineSha256!==source.engineSha256)) invalid('source changed inside a live session');
  if (sameSession && (snapshot.revision < previous.revision || snapshot.nextSequence < previous.nextSequence || snapshot.computer.cycle < previous.cycle)) invalid('stale live observation');
  const activeSession={sessionId:snapshot.sessionId,...source,revision:snapshot.revision,nextSequence:snapshot.nextSequence,cycle:snapshot.computer.cycle};
  const completed=validateP52Completion(snapshot),completionCycle=completed?snapshot.computer.instruments.alignment.completionCycle:null;
  activeSession.completedTaskId=completed?'original-p52-alignment':null;activeSession.completionCycle=completionCycle;
  const sameCompletion=receipt => receipt.stageId==='earth-parking' && receipt.sessionId===snapshot.sessionId && receipt.completionCycle===completionCycle;
  const existing=completed?state.receipts.find(receipt => sameCompletion(receipt) && receipt.verification==='service-observed'):null;
  const receipts=completed?state.receipts.filter(receipt => !sameCompletion(receipt)):[...state.receipts];
  if (completed) receipts.push(existing??{schemaVersion:1,stageId:'earth-parking',taskId:'original-p52-alignment',kind:'ORIGINAL CMC TASK RECEIPT',verification:'service-observed',sessionId:snapshot.sessionId,...source,revision:snapshot.revision,sequence:snapshot.nextSequence,cycle:snapshot.computer.cycle,completionCycle:snapshot.computer.instruments.alignment.completionCycle,checkpointIds:[...P52_CHECKPOINTS],flightExecuted:false,scope:'P52 instrument training; not Earth orbit flight'});
  const seenSessionIds=state.seenSessionIds.includes(snapshot.sessionId)?state.seenSessionIds:[...state.seenSessionIds,snapshot.sessionId];
  return makeState({...state,receipts:receipts.slice(-32),activeSession,seenSessionIds});
}

/** Availability describes the narrow task, never its historical maneuver. */
export function campaignTaskStatus(state,stageId,capabilities={}) {
  assertState(state);const task=taskFor(stageId),receipt=[...state.receipts].reverse().find(item => item.stageId===stageId)??null;
  const canOperate=stageId==='earth-parking' && capabilities?.alignmentAvailable===true;
  const currentRun=Boolean(canOperate && receipt && receipt.verification==='service-observed' && state.activeSession?.sessionId===receipt.sessionId && state.activeSession.ropeSha256===receipt.ropeSha256 && state.activeSession.engineSha256===receipt.engineSha256 && state.activeSession.completedTaskId===receipt.taskId && state.activeSession.completionCycle===receipt.completionCycle);
  const complete=Boolean(receipt),status=currentRun?'completed-current-run':complete?'completed-previous-run':canOperate?(state.activeSession?'in-progress':'ready'):'unavailable';
  return freeze({...task,status,canOperate,complete,currentRun,receipt,
    reason:currentRun?'Original P52 task completion observed in the current computer run.':complete?'A previous task result is saved locally. Reconnect and inspect the service before claiming a live run.':canOperate?'Operate original P52 using the on-screen DSKY and modeled instruments.':task.missingDependencies.length?task.missingDependencies.join('; '):'Original CMC alignment service is unavailable.'});
}

const RECEIPT_KEYS=['schemaVersion','stageId','taskId','kind','verification','sessionId','software','ropeSha256','engineSha256','revision','sequence','cycle','completionCycle','checkpointIds','flightExecuted','scope'];
function restoredReceipt(value) {
  if (!exactKeys(value,RECEIPT_KEYS) || value.schemaVersion!==1 || value.stageId!=='earth-parking' || value.taskId!=='original-p52-alignment'
      || value.kind!=='ORIGINAL CMC TASK RECEIPT' || !['service-observed','local-history-unverified'].includes(value.verification)
      || !text(value.sessionId) || value.sessionId.length>128 || value.software!=='Comanche055' || value.ropeSha256!==PINNED_COMANCHE_ROPE_SHA256 || !sha(value.engineSha256)
      || !['revision','sequence','cycle','completionCycle'].every(key => counter(value[key])) || value.completionCycle>value.cycle
      || !sameList(value.checkpointIds,P52_CHECKPOINTS) || value.flightExecuted!==false || value.scope!=='P52 instrument training; not Earth orbit flight') invalid('invalid saved task receipt');
  return {...clone(value),verification:'local-history-unverified'};
}
/** Serialize history only. No token, live session, pending command or capability is stored. */
export function serializeCampaignTaskProgress(state) {
  assertState(state);return JSON.stringify({schemaVersion:1,campaignRevision:state.campaignRevision,sourceRevision:state.sourceRevision,receipts:state.receipts});
}
/** Local data cannot restore a verified live run, even if it is structurally valid. */
export function restoreCampaignTaskProgress(serialized) {
  if (typeof serialized!=='string' || serialized.length>65536) invalid('bounded serialized history required');
  let value;try {value=JSON.parse(serialized);} catch {invalid('unreadable saved history');}
  if (!exactKeys(value,['schemaVersion','campaignRevision','sourceRevision','receipts']) || value.schemaVersion!==1 || value.campaignRevision!==CAMPAIGN_TASK_REVISION
      || value.sourceRevision!==CAMPAIGN_TASK_SOURCE_REVISION || !Array.isArray(value.receipts) || value.receipts.length>32) invalid('saved campaign/source revision');
  const receipts=value.receipts.map(restoredReceipt),identities=new Set();
  for (const receipt of receipts) {const key=`${receipt.taskId}:${receipt.sessionId}:${receipt.completionCycle}`;if (identities.has(key)) invalid('duplicate saved task receipt');identities.add(key);}
  return makeState({receipts});
}
/** Unavailable, corrupted or old browser storage never prevents starting over. */
export function readCampaignTaskProgress(storage) {
  try {const raw=storage?.getItem(CAMPAIGN_TASK_STORAGE_KEY);return raw?restoreCampaignTaskProgress(raw):createCampaignTaskState();} catch {return createCampaignTaskState();}
}
export function saveCampaignTaskProgress(storage,state) {
  assertState(state);try {storage.setItem(CAMPAIGN_TASK_STORAGE_KEY,serializeCampaignTaskProgress(state));return true;} catch {return false;}
}
