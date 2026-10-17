import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { RecordedTraceProvider, LiveBackendProvider, CREW_ROLES, EXECUTION_MODES } from '../dist/mission-provider.mjs';

const recording = JSON.parse(readFileSync(new URL('../dist/data/guidance.json', import.meta.url), 'utf8'));
const provider = new RecordedTraceProvider(recording);

test('provider retains independently sourced results for all three scenarios', () => {
  assert.deepEqual(provider.listScenarios().map(item => item.id), ['nominal', 'altitude-16km', 'missing-site']);
  assert.deepEqual(provider.listScenarios().map(item => item.result.ignitionTimeSeconds), [360.29, 360.44, null]);
  assert.equal(new Set(provider.listScenarios().map(item => item.sources.rawSha256)).size, 3);
  assert.throws(() => provider.getScenario('historical-landing'), /Unknown retained scenario/);
});

test('provider owns immutable evidence without freezing the caller data', () => {
  assert.notEqual(provider.recording, recording);
  assert.equal(Object.isFrozen(recording), false);
  assert.throws(() => { provider.getScenario('nominal').result.ignitionTimeSeconds = 0; }, TypeError);
  assert.throws(() => { provider.mode = EXECUTION_MODES.live; }, TypeError);
});

test('event navigation retains only actual milestones with explicit time and trace metadata', () => {
  const events = provider.getEvents('nominal');
  const retained = provider.getScenario('nominal').events;
  assert.equal(events.length, retained.length);
  assert.deepEqual(events.map(event => event.t), retained.map(event => event.t));
  assert.equal(events[0].mode, EXECUTION_MODES.recorded);
  assert.equal(events[0].units.t, 's');
  assert.equal(events[0].timestamp.cpuCycle, retained[0].cycle);
  assert.equal(events[0].source.rawLine, retained[0].source.rawLine);
  assert.ok(Object.isFrozen(events));
});

test('sample-and-hold preserves actual DSKY and per-quantity observation timestamps', () => {
  const scenario = provider.getScenario('nominal');
  const frame = scenario.frames.at(-1);
  const snapshot = provider.getSnapshot('nominal', scenario.durationSeconds);
  assert.equal(snapshot.frame, frame);
  assert.equal(snapshot.mode, EXECUTION_MODES.recorded);
  assert.equal(snapshot.dsky.PROG, frame.dsky.PROG);
  assert.equal(snapshot.dsky.R2, frame.dsky.R2);
  assert.equal(snapshot.guidance.signedTimeToGo.value, frame.signedTimeToGoSeconds);
  assert.ok(snapshot.guidance.signedTimeToGo.value < 0);
  assert.equal(snapshot.guidance.ignitionTime.value, 360.29);
  assert.equal(snapshot.guidance.ignitionTime.units, 's');
  assert.equal(snapshot.guidance.ignitionTime.source.rawLine, frame.observationSources.ignitionTime.rawLine);
  assert.equal(snapshot.guidance.ignitionTime.timestamp.cpuCycle, frame.observationSources.ignitionTime.cycle);
  assert.ok(snapshot.guidance.ignitionTime.timestamp.seconds < snapshot.replay.seconds);
  assert.equal(snapshot.dsky.indicators, null);
  assert.equal(snapshot.dsky.signs, null);
});

test('static geometry keeps its 3D state and separate epochs throughout replay', () => {
  const start = provider.getSnapshot('nominal', 0);
  const end = provider.getSnapshot('nominal', 1e9);
  assert.deepEqual(start.spacecraft, end.spacecraft);
  assert.equal(end.spacecraft.mode, EXECUTION_MODES.illustration);
  assert.equal(end.spacecraft.validity, 'initialized-input');
  assert.equal(end.spacecraft.timestamp.seconds, 120);
  assert.equal(end.spacecraft.landingSite.timestamp.seconds, 784.4);
  assert.notEqual(end.spacecraft.timestamp.clock, end.spacecraft.landingSite.timestamp.clock);
  assert.equal(end.spacecraft.positionM.length, 3);
  assert.match(end.spacecraft.coordinateFrame, /basic REF inertial/);
  assert.equal(end.spacecraft.units.velocity, 'm/s');
});

test('missing-site negative control and early unknown observations stay unavailable', () => {
  const unknown = provider.getSnapshot('nominal', 0);
  assert.equal(unknown.dsky.availability, 'unavailable');
  assert.equal(unknown.dsky.PROG, '??');
  assert.equal(unknown.guidance.ignitionTime.value, null);
  assert.equal(unknown.guidance.ignitionTime.source, null);
  const missing = provider.getSnapshot('missing-site', 1e9);
  assert.equal(missing.spacecraft.landingSite.availability, 'unavailable');
  assert.equal(missing.spacecraft.landingSite.positionM, null);
  assert.equal(missing.guidance.ignitionTime.value, null);
  assert.equal(missing.guidance.ignitionTime.availability, 'unavailable');
  assert.ok(missing.guidance.alarms.includes('01406'));
  assert.equal(missing.guidance.rootCount, 3);
});

test('mid-sample replay never interpolates numerical guidance', () => {
  const scenario = provider.getScenario('nominal');
  const index = scenario.frames.findIndex((frame, i) => i > 0 && frame.t > scenario.frames[i - 1].t + .001);
  const before = scenario.frames[index - 1];
  const after = scenario.frames[index];
  assert.equal(provider.getSnapshot('nominal', (before.t + after.t) / 2).frame, before);
  assert.equal(provider.getSnapshot('nominal', after.t).frame, after);
});

test('malformed and unsourced numerical values are rejected at the provider boundary', () => {
  const changed = structuredClone(recording);
  changed.cases[0].frames.at(-1).observationSources.ignitionTime = null;
  assert.throws(() => new RecordedTraceProvider(changed), /observation provenance/);
  const noClock = structuredClone(recording);
  delete noClock.clock;
  assert.throws(() => new RecordedTraceProvider(noClock), /provenance or clock/);
  assert.throws(() => provider.getSnapshot('nominal', Number.NaN), /Invalid replay time/);
});

test('incomplete or inconsistent summaries cannot become a fabricated comparison outcome', () => {
  const incomplete = structuredClone(recording);
  delete incomplete.cases[0].result.reviewReached;
  assert.throws(() => new RecordedTraceProvider(incomplete), /recorded result/);
  const inconsistent = structuredClone(recording);
  inconsistent.cases[1].result.ignitionTimeSeconds = 360.29;
  assert.throws(() => new RecordedTraceProvider(inconsistent), /recorded result/);
  const wrongDisplay = structuredClone(recording);
  wrongDisplay.cases[0].result.finalDsky.NOUN = '99';
  assert.throws(() => new RecordedTraceProvider(wrongDisplay), /recorded result/);
});

test('negative cycles and absent or duplicate event provenance fail before rendering', () => {
  const negativeCycle = structuredClone(recording);
  negativeCycle.cases[0].frames[0].cycle = -1;
  assert.throws(() => new RecordedTraceProvider(negativeCycle), /observation provenance/);
  const negativeSource = structuredClone(recording);
  negativeSource.cases[0].frames[0].source.cycle = -1;
  assert.throws(() => new RecordedTraceProvider(negativeSource), /observation provenance/);
  const noEventSource = structuredClone(recording);
  delete noEventSource.cases[0].events[0].source;
  assert.throws(() => new RecordedTraceProvider(noEventSource), /event provenance/);
  const duplicate = structuredClone(recording);
  duplicate.cases[0].events.splice(1, 0, duplicate.cases[0].events[0]);
  assert.throws(() => new RecordedTraceProvider(duplicate), /event provenance/);
});

test('loader uses a static retained export and surfaces missing or corrupt data', async () => {
  let request;
  const loaded = await RecordedTraceProvider.load(undefined, { fetchImpl: async (...args) => {
    request = args;
    return { ok: true, json: async () => recording };
  } });
  assert.equal(request[0], './data/guidance.json');
  assert.equal(request[1].cache, 'no-store');
  assert.equal(loaded.mode, EXECUTION_MODES.recorded);
  await assert.rejects(RecordedTraceProvider.load('/missing.json', { fetchImpl: async () => ({ ok: false, status: 404 }) }), /404/);
  await assert.rejects(RecordedTraceProvider.load('/corrupt.json', { fetchImpl: async () => ({ ok: true, json: async () => ({}) }) }), /Unsupported/);
});

test('guidance capabilities disable unsupported commands and live provider never requests a service', async () => {
  const available = provider.getCapabilities().filter(item => item.available).map(item => item.id);
  assert.deepEqual(available, ['recorded-guidance', 'trace-dsky', 'static-geometry', 'scenario-comparison']);
  assert.equal((await provider.command({ key: 'PRO' })).accepted, false);
  const live = new LiveBackendProvider();
  assert.equal(live.mode, EXECUTION_MODES.live);
  assert.equal(live.getSnapshot(), null);
  assert.ok(live.getCapabilities().every(item => item.available === false));
  assert.equal((await live.command({ key: 'ENTR' })).status, 'unavailable');
});

test('crew contract contains exactly the historical three planned roles and keeps Collins in orbit', () => {
  assert.equal(CREW_ROLES.length, 3);
  assert.deepEqual(CREW_ROLES.map(item => item.name), ['Neil Armstrong', 'Buzz Aldrin', 'Michael Collins']);
  assert.deepEqual(CREW_ROLES.map(item => item.vehicle), ['Lunar Module', 'Lunar Module', 'Command Module']);
  assert.ok(CREW_ROLES.every(item => item.status === 'planned'));
  assert.match(CREW_ROLES[2].description, /lunar orbit/);
  assert.ok(Object.isFrozen(CREW_ROLES));
});
