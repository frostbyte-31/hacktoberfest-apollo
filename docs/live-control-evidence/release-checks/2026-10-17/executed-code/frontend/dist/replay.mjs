/** Read-only presentation utilities. No guidance, actuator or physics simulation. */
export const JETS = Object.freeze({
  5: ['Q4U', 'Q4D', 'Q3U', 'Q3D', 'Q2U', 'Q2D', 'Q1U', 'Q1D'],
  6: ['Q3A', 'Q4F', 'Q1F', 'Q2A', 'Q2L', 'Q3R', 'Q4R', 'Q1L'],
});

export function lastAt(items, time, key = 't') {
  let low = 0;
  let high = items.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (items[mid][key] <= time) low = mid + 1;
    else high = mid;
  }
  return low ? items[low - 1] : null;
}

export function frameAt(experiment, time) {
  return lastAt(experiment.frames, Math.min(time, experiment.durationSeconds));
}

export function rcsAt(experiment, time) {
  const words = { 5: null, 6: null };
  for (const event of experiment.rcsEvents) {
    if (event.t > time) break;
    if (event.channel === 5 || event.channel === 6) words[event.channel] = event.value;
  }
  return words;
}

export function activeJets(words) {
  return Object.entries(JETS).flatMap(([channel, names]) => names.map((name, bit) => ({
    name,
    channel: Number(channel),
    bit: bit + 1,
    active: words[channel] === null ? null : Boolean(words[channel] & (1 << bit)),
  })));
}

export function rotateVector(q, v) {
  const [w, x, y, z] = q;
  const tx = 2 * (y * v[2] - z * v[1]);
  const ty = 2 * (z * v[0] - x * v[2]);
  const tz = 2 * (x * v[1] - y * v[0]);
  return [v[0] + w * tx + y * tz - z * ty,
    v[1] + w * ty + z * tx - x * tz,
    v[2] + w * tz + x * ty - y * tx];
}

export function slerp(a, b, fraction) {
  let end = b;
  let dot = a.reduce((s, n, i) => s + n * b[i], 0);
  if (dot < 0) { end = b.map(n => -n); dot = -dot; }
  let result;
  if (dot > 0.9995) result = a.map((n, i) => n + fraction * (end[i] - n));
  else {
    const angle = Math.acos(Math.min(1, dot));
    const denom = Math.sin(angle);
    result = a.map((n, i) => (n * Math.sin((1 - fraction) * angle) + end[i] * Math.sin(fraction * angle)) / denom);
  }
  const norm = Math.hypot(...result);
  return result.map(n => n / norm);
}

/** Smooth rendering only; all numeric readouts remain actual sampled values. */
export function presentationQuaternion(experiment, time) {
  const frame = frameAt(experiment, time);
  if (!frame) return [1, 0, 0, 0];
  const i = experiment.frames.indexOf(frame);
  const next = experiment.frames[i + 1];
  if (!next || next.t === frame.t || time >= experiment.durationSeconds) return frame.q;
  return slerp(frame.q, next.q, Math.max(0, Math.min(1, (time - frame.t) / (next.t - frame.t))));
}

export const wrappedDegrees = value => ((value + 180) % 360 + 360) % 360 - 180;
export const octal = value => value == null ? '— — — — —' : value.toString(8).padStart(5, '0');
export function originalReadiness(checkpoint) {
  return Boolean(checkpoint && checkpoint.modreg === 0
    && Number.isInteger(checkpoint.imodes30) && !(checkpoint.imodes30 & 32)
    && Number.isInteger(checkpoint.imodes33) && !(checkpoint.imodes33 & 32)
    && (checkpoint.dapbools & 4)
    && Array.isArray(checkpoint.failreg) && checkpoint.failreg.length === 3
    && checkpoint.failreg.every(word => word === 0));
}
export function formatTime(value) {
  const millis = Math.round(Math.max(0, value) * 1000);
  return `${String(Math.floor(millis / 60000)).padStart(2, '0')}:${String(Math.floor(millis / 1000) % 60).padStart(2, '0')}.${String(millis % 1000).padStart(3, '0')}`;
}

export function validateReplay(data) {
  if (data.schemaVersion !== 1 || !Array.isArray(data.cases)) throw new Error('Unsupported replay format.');
  for (const id of ['yaw', 'pitch', 'pitch_off', 'combined', 'combined_off']) {
    const c = data.cases.find(item => item.id === id);
    if (!c || !c.frames.length || c.durationSeconds <= 0) throw new Error(`Missing experiment: ${id}.`);
    if (!/^[a-f0-9]{64}$/.test(c.source.rawSha256)) throw new Error(`Missing provenance for ${id}.`);
    let previous = -1;
    for (const frame of c.frames) {
      if (!Number.isFinite(frame.t) || !Number.isInteger(frame.cycle) || frame.t < previous || frame.t > c.durationSeconds + 0.01) throw new Error('Invalid frame chronology.');
      if (!Array.isArray(frame.q) || frame.q.length !== 4 || !frame.q.every(Number.isFinite) || Math.abs(Math.hypot(...frame.q) - 1) > 1e-6) throw new Error('Invalid recorded orientation.');
      if (![frame.omega, frame.gimbals, frame.torque].every(v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite))) throw new Error('Invalid recorded model sample.');
      previous = frame.t;
    }
    previous = -1;
    for (const event of c.rcsEvents) {
      if (!Number.isFinite(event.t) || event.t < previous || ![5, 6].includes(event.channel) || !Number.isInteger(event.value) || event.value < 0 || event.value > 32767) throw new Error('Invalid recorded command.');
      previous = event.t;
    }
  }
  return data;
}
