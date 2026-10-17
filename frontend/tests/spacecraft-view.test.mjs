import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spacecraftViewModel, renderSpacecraftView } from '../dist/spacecraft-view.mjs';

const data = JSON.parse(readFileSync(new URL('../dist/data/guidance.json', import.meta.url), 'utf8'));
const state = data.cases[0].initialState;

test('all retained initial states pass the renderer boundary without modifying supplied data', () => {
  const before = JSON.stringify(data.cases.map(item => item.initialState));
  for (const item of data.cases) {
    const model = spacecraftViewModel(item.initialState);
    assert.ok(model, item.id);
    assert.ok(Number.isFinite(model.projection.orbitRadius));
  }
  assert.equal(JSON.stringify(data.cases.map(item => item.initialState)), before);
});

test('unavailable or malformed geometry is rejected instead of producing placeholder coordinates', () => {
  for (const value of [null, undefined, {}, { ...state, positionM: [0, 0, 0] },
    { ...state, velocityMps: [0, Number.NaN, 0] }, { ...state, lunarRadiusM: 0 },
    { ...state, epochSeconds: null }, { ...state, altitudeM: Infinity },
    { ...state, landingSiteBasicRefAtTlandM: [0, 0, 0] },
    { ...state, targetLandingTimeSeconds: null }]) {
    assert.equal(spacecraftViewModel(value), null);
  }
});

test('an absent target or optional scalar remains absent without deriving substitute telemetry', () => {
  const missing = data.cases.find(item => item.id === 'missing-site').initialState;
  assert.equal(spacecraftViewModel(missing).projection.site, null);
  assert.ok(spacecraftViewModel({ ...missing, altitudeM: null, speedMps: null }));
  assert.equal(spacecraftViewModel({ ...missing, velocityMps: [0, 1, 0] }).projection.velocity, null);
});

test('three-dimensional numerical values retain the Y axis that the X–Z picture omits', () => {
  const supplied = { ...state, positionM: [state.positionM[0], 123, state.positionM[2]], velocityMps: [1, 2, 3] };
  const model = spacecraftViewModel(supplied);
  assert.match(model.position, /, 123\.00, /);
  assert.equal(model.velocity, '[1.00, 2.00, 3.00] m/s');
  assert.equal(model.projection.position.x, supplied.positionM[0] / supplied.lunarRadiusM);
  assert.equal(model.projection.position.y, -supplied.positionM[2] / supplied.lunarRadiusM);
});

test('renderer can be mounted with optional readouts absent and reports missing geometry', () => {
  const emptyRoot = { querySelector() { return null; } };
  assert.equal(renderSpacecraftView(emptyRoot, state), true);
  assert.equal(renderSpacecraftView(emptyRoot, null), false);
});
