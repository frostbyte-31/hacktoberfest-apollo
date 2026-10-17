import { originalReadiness } from './replay.mjs';

/** Training objectives only. These rotations never update the spacecraft state. */
export const CHALLENGES = Object.freeze({
  yaw: Object.freeze({ id:'yaw', title:'Yaw acquisition', yawDeg:3, pitchDeg:0 }),
  pitch: Object.freeze({ id:'pitch', title:'Pitch acquisition', yawDeg:0, pitchDeg:3 }),
  combined: Object.freeze({ id:'combined', title:'Two-axis acquisition', yawDeg:2, pitchDeg:2 }),
});
const RAD = Math.PI / 180;
const DEFAULTS = Object.freeze({ challenge:'combined', toleranceDeg:1,
  maxRateDegS:1, holdSeconds:.4, maxSampleGapSeconds:.3 });
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const multiply = (a,b) => [a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
  a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
  a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
  a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]];
const validQ = q => Array.isArray(q) && q.length === 4 && q.every(Number.isFinite)
  && Math.abs(Math.hypot(...q)-1) <= 1e-6;

/** Body-to-stable, scalar-first quaternion. Body X=yaw; body Y=pitch. */
export function targetQuaternion(initial, yawDeg, pitchDeg) {
  if (!validQ(initial) || !Number.isFinite(yawDeg) || !Number.isFinite(pitchDeg)) throw new Error('Invalid training target.');
  const yaw = yawDeg*RAD/2, pitch = pitchDeg*RAD/2;
  const result = multiply(multiply(initial, [Math.cos(yaw),Math.sin(yaw),0,0]),
    [Math.cos(pitch),0,Math.sin(pitch),0]);
  const norm = Math.hypot(...result);
  return result.map(value => value/norm);
}

/** Shortest relative rotation, expressed in current body axes; not Euler angles. */
export function quaternionErrorVectorDeg(current, target) {
  if (!validQ(current) || !validQ(target)) return null;
  let relative = multiply([current[0],-current[1],-current[2],-current[3]], target);
  if (relative[0] < 0) relative = relative.map(value => -value);
  const length = Math.hypot(...relative.slice(1));
  if (length < 1e-12) return [0,0,0];
  const angle = 2*Math.atan2(length, clamp(relative[0],0,1))/RAD;
  return relative.slice(1).map(value => value/length*angle);
}
export function quaternionErrorDeg(current, target) {
  const vector = quaternionErrorVectorDeg(current,target);
  return vector === null ? null : Math.hypot(...vector);
}

function configuration(input) {
  const value = {...DEFAULTS,...input};
  if (!Object.hasOwn(CHALLENGES,value.challenge)) throw new Error('Unsupported challenge. Only yaw and pitch are available.');
  for (const field of ['toleranceDeg','maxRateDegS','holdSeconds','maxSampleGapSeconds']) {
    if (!Number.isFinite(value[field]) || value[field] <= 0) throw new Error(`Invalid challenge ${field}.`);
  }
  return Object.freeze(value);
}

export function createGameState(config={}) {
  return { config:configuration(config), phase:'ready', sessionId:null, target:null,
    metrics:null, result:null, bestScore:null, input:{yaw:0,pitch:0},
    message:'Start a fresh live AGC session to attempt this challenge.',
    startTime:null, lastSample:null, insideTarget:false };
}
export function resetGame(state, config=state.config) {
  return {...createGameState(config),bestScore:state.bestScore};
}

/** Pilot intent is displayed separately. Only backend physical time starts a run. */
export function notePilotInput(state, input) {
  if (state.phase !== 'await-input' && state.phase !== 'running') return state;
  if (!input || ![-1,0,1].includes(input.yaw) || ![-1,0,1].includes(input.pitch)) return state;
  return {...state,input:{yaw:input.yaw,pitch:input.pitch}};
}

function unavailable(state, message) {
  return {...state,phase:'unavailable',insideTarget:false,input:{yaw:0,pitch:0},
    metrics:state.metrics ? {...state.metrics,holdSeconds:0} : null, result:null,message};
}

function result(state, outcome, reason) {
  const score = state.metrics?.score ?? 0;
  return {...state,phase:'result',insideTarget:false,input:{yaw:0,pitch:0},
    result:{outcome,score,reason},message:reason,
    bestScore:outcome==='success' ? Math.max(state.bestScore ?? 0,score) : state.bestScore};
}

/** Finishing by operator request cannot grant success, even with a near-target frame. */
export function finishGame(state, reason='Run stopped by the pilot.') {
  if (state.phase === 'result' || state.phase === 'unavailable') return state;
  return result(state,'aborted',reason);
}

function actualSample(frame) {
  const model = frame?.model;
  if (!model || !validQ(model.quaternion) || !Array.isArray(model.omega)
    || model.omega.length !== 3 || !model.omega.every(Number.isFinite)
    || !Number.isFinite(frame.physical_time) || frame.physical_time < 0
    || !Number.isFinite(frame.remaining_time) || frame.remaining_time < 0) return null;
  // Retained model output omega is degrees/second, already converted by Tcl.
  return {t:frame.physical_time,q:model.quaternion.slice(),omega:model.omega.slice(),
    remainingSeconds:frame.remaining_time};
}

function measurement(state, sample, scoring) {
  const previous = state.lastSample;
  if (sample.t < previous.t) return unavailable(state,'Backend physical time moved backwards. Start a fresh run.');
  if (sample.t === previous.t) {
    if (quaternionErrorDeg(previous.q,sample.q) > 1e-5
      || sample.omega.some((value,index)=>Math.abs(value-previous.omega[index]) > 1e-8)) {
      return unavailable(state,'Telemetry changed without advancing authoritative model time.');
    }
    return state;
  }
  const errorVectorDeg = quaternionErrorVectorDeg(sample.q,state.target.q);
  const errorDeg = Math.hypot(...errorVectorDeg), rateDegS = Math.hypot(...sample.omega);
  const insideTarget = errorDeg <= state.config.toleranceDeg && rateDegS <= state.config.maxRateDegS;
  const dt = sample.t-previous.t;
  const holdSeconds = scoring && insideTarget && state.insideTarget && dt <= state.config.maxSampleGapSeconds
    ? state.metrics.holdSeconds+dt : 0;
  const elapsedSeconds = sample.t-state.startTime;
  // A game score based on this observed sample; never a flight-fidelity rating.
  const accuracy = 1-clamp(errorDeg/Math.max(6,state.target.initialErrorDeg*2),0,1);
  const steadiness = 1-clamp(rateDegS/5,0,1);
  const score = Math.round(1000*(.7*accuracy+.3*steadiness));
  const next = {...state,phase:scoring?'running':state.phase,lastSample:sample,insideTarget,
    metrics:{errorDeg,errorVectorDeg,rateDegS,elapsedSeconds,
      remainingSeconds:sample.remainingSeconds,holdSeconds,score},
    message:insideTarget?'Target acquired. Hold orientation and keep rates low.':'Slew to the target, then release and settle.'};
  return scoring && holdSeconds+1e-9 >= state.config.holdSeconds
    ? result(next,'success','Target held in observed live backend samples.') : next;
}

/**
 * Consume LiveClient snapshots, not replay frames or presentation quaternions.
 * No wall clock, extrapolation, integration, generated telemetry or AGC writes.
 */
export function updateGame(state, update) {
  if (update?.mode !== 'live') return unavailable(state,'Challenges require live AGC execution. Recorded replay cannot earn a score.');
  if (!update.sessionId) {
    return update.status === 'idle' ? resetGame(state) : unavailable(state,'No authoritative live session is available.');
  }
  let next = state;
  if (update.sessionId !== state.sessionId) next = {...resetGame(state),sessionId:update.sessionId};
  if (['fault','disconnected'].includes(update.status)) return unavailable(next,update.message || 'Live execution unavailable.');
  if (next.phase === 'result' || next.phase === 'unavailable') return next;
  if (update.status === 'initializing') return {...next,message:'Original AGC startup is executing. Waiting for verified readiness.'};
  if (update.status === 'stopping') return finishGame(next,'Run stopped by the pilot; sensor queues are settling.');
  if (!['ready','running','stopped'].includes(update.status)) return unavailable(next,'Live execution state is unavailable.');
  const sample = actualSample(update.frame);
  if (!sample || !originalReadiness(update.frame.execution)) return unavailable(next,'Valid authoritative attitude telemetry and original readiness are required.');
  if (!next.target) {
    if (update.status !== 'ready' || !update.frame.ready) return unavailable(next,'Start a fresh session; its ready sample defines the target reference.');
    const challenge = CHALLENGES[next.config.challenge];
    const q = targetQuaternion(sample.q,challenge.yawDeg,challenge.pitchDeg);
    const initialErrorDeg = quaternionErrorDeg(sample.q,q);
    return {...next,phase:'await-input',target:{...challenge,q,initialErrorDeg,referenceQ:sample.q.slice()},
      startTime:sample.t,lastSample:sample,
      metrics:{errorDeg:initialErrorDeg,errorVectorDeg:quaternionErrorVectorDeg(sample.q,q),
        rateDegS:Math.hypot(...sample.omega),elapsedSeconds:0,
        remainingSeconds:sample.remainingSeconds,holdSeconds:0,score:0},
      message:'Ready. Your first yaw or pitch input starts the native clock.'};
  }
  if (update.status === 'ready') {
    if (sample.t !== next.lastSample.t) return unavailable(next,'Paused readiness unexpectedly advanced physical time.');
    return next;
  }
  if (update.status === 'running' && !update.frame.ready) return unavailable(next,'Native readiness changed; challenge stopped.');
  next = measurement(next,sample,update.status === 'running');
  if (update.status !== 'stopped' || next.phase === 'unavailable') return next;
  return result(next,sample.remainingSeconds <= .02 ? 'timeout':'aborted',
    sample.remainingSeconds <= .02 ? 'Bounded native run complete. Target hold was not observed.':'Run ended before the bounded horizon.');
}
