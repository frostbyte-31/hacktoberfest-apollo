/** Read-only presentation of recorded observations. No guidance or physical propagation. */
import { lastAt } from './replay.mjs';

export const SCENARIOS = Object.freeze(['nominal', 'altitude-16km', 'missing-site']);
const finiteOrNull = value => value === null || Number.isFinite(value);
const vector = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);

export function validateGuidance(data) {
  if (data?.schemaVersion !== 1 || data.mode !== 'RECORDED AUTHENTIC EXECUTION REPLAY' || !Array.isArray(data.cases)) {
    throw new Error('Unsupported guidance recording.');
  }
  for (const id of SCENARIOS) {
    const item = data.cases.find(c => c.id === id);
    if (!item || data.cases.filter(c => c.id === id).length !== 1 || !Number.isFinite(item.durationSeconds) || item.durationSeconds <= 0 || !item.frames?.length || !Array.isArray(item.events)) {
      throw new Error(`Missing or invalid scenario: ${id}.`);
    }
    const state = item.initialState;
    if (!state || !vector(state.positionM) || !vector(state.velocityMps) || !Number.isFinite(state.lunarRadiusM) || state.lunarRadiusM <= 0 || Math.hypot(...state.positionM) <= state.lunarRadiusM || !finiteOrNull(state.altitudeM) || !Number.isFinite(state.speedMps)) {
      throw new Error(`Invalid initial-state illustration: ${id}.`);
    }
    if (state.landingSiteBasicRefAtTlandM !== null && !vector(state.landingSiteBasicRefAtTlandM)) throw new Error('Invalid landing-site projection.');
    if (!/^[a-f0-9]{64}$/.test(item.sources?.rawSha256 ?? '')) throw new Error(`Missing trace fingerprint: ${id}.`);
    let previous = -1;
    for (const frame of item.frames) {
      if (!Number.isFinite(frame.t) || frame.t < previous || frame.t > item.durationSeconds + 1e-6 || !Number.isInteger(frame.cycle) || !frame.dsky || !Number.isInteger(frame.rootCount) || frame.rootCount < 0 || !Array.isArray(frame.alarms)) throw new Error('Invalid guidance observation chronology.');
      if (!['PROG', 'VERB', 'NOUN', 'R1', 'R2', 'R3'].every(key => typeof frame.dsky[key] === 'string') || !Number.isInteger(frame.source?.rawLine) || frame.source.rawLine <= 0) throw new Error('Invalid recorded display or source.');
      for (const field of ['observedClockSeconds', 'signedTimeToGoSeconds', 'ignitionTimeSeconds', 'ignitionLeadSeconds']) {
        if (!finiteOrNull(frame[field])) throw new Error(`Invalid observed quantity: ${field}.`);
      }
      previous = frame.t;
    }
    previous = -1;
    for (const event of item.events) {
      if (!Number.isFinite(event.t) || event.t < previous || event.t > item.durationSeconds + 1e-6 || !Number.isInteger(event.cycle) || typeof event.title !== 'string' || typeof event.id !== 'string') throw new Error('Invalid mission event chronology.');
      previous = event.t;
    }
  }
  return data;
}

export function frameAt(scenario, time) {
  return lastAt(scenario.frames, boundedTime(time, scenario.durationSeconds));
}

export function boundedTime(time, duration) {
  if (!Number.isFinite(time) || !Number.isFinite(duration) || duration < 0) throw new Error('Invalid replay time.');
  return Math.max(0, Math.min(time, duration));
}

export function nextEventTime(scenario, time, direction = 1) {
  const t = boundedTime(time, scenario.durationSeconds);
  if (direction < 0) return [...scenario.events].reverse().find(e => e.t < t - 1e-7)?.t ?? 0;
  return scenario.events.find(e => e.t > t + 1e-7)?.t ?? scenario.durationSeconds;
}

export function advanceReplay(scenario, time, elapsedSeconds, speed = 1) {
  if (!Number.isFinite(elapsedSeconds) || elapsedSeconds < 0 || !Number.isFinite(speed) || speed <= 0) throw new Error('Invalid playback interval.');
  const next = boundedTime(time + elapsedSeconds * speed, scenario.durationSeconds);
  return { time: next, playing: next < scenario.durationSeconds };
}

/** Preserve sign. This is formatting, not an AGC calculation. */
export function seconds(value, { signed = false, precision = 2 } = {}) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const negative = value < 0 || Object.is(value, -0);
  return `${negative ? '-' : signed ? '+' : ''}${Math.abs(value).toFixed(precision)}`;
}

export function clock(value) {
  if (!Number.isFinite(value)) return '—';
  const sign = value < 0 || Object.is(value, -0) ? '−' : '';
  const cs = Math.round(Math.abs(value) * 100);
  return `${sign}${String(Math.floor(cs / 360000)).padStart(2, '0')}:${String(Math.floor(cs / 6000) % 60).padStart(2, '0')}:${String(Math.floor(cs / 100) % 60).padStart(2, '0')}.${String(cs % 100).padStart(2, '0')}`;
}

/** Static X–Z projection of supplied state. No orbit integration or trajectory generation. */
export function projectInitialState(state) {
  const radius = state.lunarRadiusM;
  const orbitRadius = Math.hypot(...state.positionM) / radius;
  const point = value => ({ x: value[0] / radius, y: -value[2] / radius });
  const position = point(state.positionM);
  const projectedSpeed = Math.hypot(state.velocityMps[0], state.velocityMps[2]);
  return {
    position,
    site: state.landingSiteBasicRefAtTlandM === null ? null : point(state.landingSiteBasicRefAtTlandM),
    velocity: projectedSpeed ? { x: state.velocityMps[0] / projectedSpeed, y: -state.velocityMps[2] / projectedSpeed } : null,
    orbitRadius,
  };
}
