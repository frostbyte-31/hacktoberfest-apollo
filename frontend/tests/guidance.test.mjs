import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateGuidance, frameAt, boundedTime, nextEventTime, advanceReplay, seconds, clock, projectInitialState } from '../dist/guidance-state.mjs';

const data = JSON.parse(readFileSync(new URL('../dist/data/guidance.json', import.meta.url), 'utf8'));
const nominal = data.cases.find(item => item.id === 'nominal');
const negative = data.cases.find(item => item.id === 'missing-site');
const clone = () => JSON.parse(JSON.stringify(data));

test('retained three-scenario guidance recording has required display and source data', () => {
  assert.equal(validateGuidance(data), data);
  assert.deepEqual(data.cases.map(item => item.id), ['nominal', 'altitude-16km', 'missing-site']);
});

test('a replay labelled live cannot be accepted as a recorded experiment', () => {
  const changed = clone();
  changed.mode = 'LIVE AUTHENTIC EXECUTION';
  assert.throws(() => validateGuidance(changed), /Unsupported/);
});

test('missing trace fingerprint or display field is rejected instead of substituted', () => {
  const fingerprint = clone();
  fingerprint.cases[0].sources.rawSha256 = '';
  assert.throws(() => validateGuidance(fingerprint), /fingerprint/);
  const display = clone();
  delete display.cases[0].frames[0].dsky.R1;
  assert.throws(() => validateGuidance(display), /display or source/);
});

test('malformed observed quantities and reversed chronology are rejected', () => {
  const quantity = clone();
  quantity.cases[0].frames[0].ignitionTimeSeconds = '360.29';
  assert.throws(() => validateGuidance(quantity), /quantity/);
  const chronology = clone();
  chronology.cases[0].frames[1].t = -1;
  assert.throws(() => validateGuidance(chronology), /chronology/);
});

test('frame lookup holds actual observations between samples without interpolation', () => {
  const index = nominal.frames.findIndex((frame, i) => i > 0 && frame.t > nominal.frames[i - 1].t + 0.001);
  const before = nominal.frames[index - 1];
  const after = nominal.frames[index];
  assert.equal(frameAt(nominal, (before.t + after.t) / 2), before);
  assert.equal(frameAt(nominal, after.t), after);
});

test('replay bounds keep observations within the retained execution horizon', () => {
  assert.equal(frameAt(nominal, -100), nominal.frames[0]);
  assert.equal(frameAt(nominal, 1e9), nominal.frames.at(-1));
  assert.equal(boundedTime(-5, nominal.durationSeconds), 0);
  assert.throws(() => boundedTime(Number.NaN, nominal.durationSeconds), /Invalid/);
});

test('event stepping selects real distinct event times and stops at bounds', () => {
  const event = nominal.events.find(item => item.id === 'p63');
  const next = nextEventTime(nominal, event.t);
  assert.ok(next > event.t);
  assert.ok(nominal.events.some(item => item.t === next));
  assert.ok(nextEventTime(nominal, event.t, -1) < event.t);
  assert.equal(nextEventTime(nominal, 0, -1), 0);
  assert.equal(nextEventTime(nominal, nominal.durationSeconds), nominal.durationSeconds);
});

test('paced replay stops at horizon and rejects a negative elapsed interval', () => {
  assert.deepEqual(advanceReplay(nominal, 0, 1, 4), { time: 4, playing: true });
  assert.deepEqual(advanceReplay(nominal, nominal.durationSeconds - 1, 1, 4), { time: nominal.durationSeconds, playing: false });
  assert.throws(() => advanceReplay(nominal, 0, -1), /Invalid/);
});

test('nominal and altered-state outcomes come from their own recorded scenarios', () => {
  const altered = data.cases.find(item => item.id === 'altitude-16km');
  assert.notEqual(nominal.result.ignitionTimeSeconds, altered.result.ignitionTimeSeconds);
  assert.equal(frameAt(nominal, nominal.durationSeconds).ignitionTimeSeconds, nominal.result.ignitionTimeSeconds);
  assert.equal(frameAt(altered, altered.durationSeconds).ignitionTimeSeconds, altered.result.ignitionTimeSeconds);
});

test('missing-site control never supplies a fabricated ignition result or site', () => {
  assert.ok(negative.frames.every(frame => frame.ignitionTimeSeconds === null && frame.ignitionLeadSeconds === null));
  assert.equal(projectInitialState(negative.initialState).site, null);
  assert.ok(negative.frames.at(-1).alarms.includes('01406'));
});

test('signed time-to-go is preserved independently from absolute TIG and solution lead', () => {
  const frame = nominal.frames.at(-1);
  assert.ok(frame.signedTimeToGoSeconds < 0);
  assert.match(seconds(frame.signedTimeToGoSeconds, { signed: true }), /^-/);
  assert.ok(frame.ignitionTimeSeconds > frame.observedClockSeconds);
  assert.ok(Math.abs(frame.ignitionTimeSeconds - frame.observedClockSeconds - frame.ignitionLeadSeconds) < 1e-10);
  assert.notEqual(frame.signedTimeToGoSeconds, frame.ignitionLeadSeconds);
});

test('clock and quantity formatters preserve unavailable values and signed zeros', () => {
  assert.equal(seconds(null), '—');
  assert.equal(clock(null), '—');
  assert.equal(seconds(-1.25, { signed: true }), '-1.25');
  assert.equal(seconds(0, { signed: true }), '+0.00');
  assert.equal(seconds(-0, { signed: true }), '-0.00');
  assert.equal(clock(360.29), '00:06:00.29');
});

test('static projection uses X–Z of supplied 3D state and actual lunar radius', () => {
  const state = nominal.initialState;
  const projection = projectInitialState(state);
  assert.equal(projection.position.x, state.positionM[0] / state.lunarRadiusM);
  assert.equal(projection.position.y, -state.positionM[2] / state.lunarRadiusM);
  assert.equal(projection.orbitRadius, Math.hypot(...state.positionM) / state.lunarRadiusM);
  assert.ok(Math.abs(Math.hypot(projection.velocity.x, projection.velocity.y) - 1) < 1e-12);
  assert.deepEqual(projectInitialState(state), projection);
});

test('landing marker uses documented future-epoch site rather than initial spacecraft position', () => {
  const state = nominal.initialState;
  const projected = projectInitialState(state);
  assert.equal(projected.site.x, state.landingSiteBasicRefAtTlandM[0] / state.lunarRadiusM);
  assert.equal(projected.site.y, -state.landingSiteBasicRefAtTlandM[2] / state.lunarRadiusM);
  assert.notDeepEqual(projected.site, projected.position);
  assert.notEqual(state.epochSeconds, state.targetLandingTimeSeconds);
});
