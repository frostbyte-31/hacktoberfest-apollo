import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spacecraftViewModel, renderSpacecraftView } from '../dist/spacecraft-view.mjs';

const data = JSON.parse(readFileSync(new URL('../dist/data/guidance.json', import.meta.url), 'utf8'));
const nominal = data.cases.find(item => item.id === 'nominal').initialState;
const missing = data.cases.find(item => item.id === 'missing-site').initialState;
const html = readFileSync(new URL('../dist/guidance.html', import.meta.url), 'utf8');

function fixture() {
  const node = () => ({
    attributes: {}, textContent: '', children: [],
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    replaceChildren(...values) { this.children = values; },
    append(value) { this.children.push(value); },
  });
  const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], node()]));
  const root = {
    ownerDocument: { createTextNode: value => ({ textContent: value }), createElement: node },
    querySelector: selector => elements.get(selector.slice(1)),
  };
  return { root, elements };
}

test('renderer keeps the initialized 3D state as a static X–Z projection', () => {
  const model = spacecraftViewModel(nominal);
  assert.equal(model.position.x, 400 + nominal.positionM[0] / nominal.lunarRadiusM * 151);
  assert.equal(model.position.y, 206 - nominal.positionM[2] / nominal.lunarRadiusM * 151);
  assert.equal(model.orbitRadiusPixels, 151 * Math.hypot(...nominal.positionM) / nominal.lunarRadiusM);
  assert.equal(model.mode, 'STATIC_EDUCATIONAL_ILLUSTRATION');
  assert.equal(model.moving, false);
});

test('planned landing site preserves its future TLAND epoch independently of spacecraft epoch', () => {
  const model = spacecraftViewModel(nominal);
  assert.equal(model.site.x, 400 + nominal.landingSiteBasicRefAtTlandM[0] / nominal.lunarRadiusM * 151);
  assert.equal(model.site.y, 206 - nominal.landingSiteBasicRefAtTlandM[2] / nominal.lunarRadiusM * 151);
  assert.notEqual(model.targetLandingTimeSeconds, model.epochSeconds);
  assert.equal(model.epochSeconds, nominal.epochSeconds);
  assert.equal(model.targetLandingTimeSeconds, nominal.targetLandingTimeSeconds);
});

test('velocity arrow conveys direction only and no motion is propagated', () => {
  const first = spacecraftViewModel(nominal);
  const second = spacecraftViewModel(nominal);
  assert.ok(Math.abs(Math.hypot(first.velocityDirection.x, first.velocityDirection.y) - 1) < 1e-12);
  assert.deepEqual(second, first);
  assert.equal(spacecraftViewModel({ ...nominal, velocityMps: [0, 0, 0] }).velocityDirection, null);
});

test('projection preserves dimensional inputs and leaves source state unchanged', () => {
  const before = JSON.stringify(nominal);
  const model = spacecraftViewModel(nominal);
  assert.equal(model.altitudeKm, nominal.altitudeM / 1000);
  assert.equal(model.speedMps, nominal.speedMps);
  assert.equal(JSON.stringify(nominal), before);
});

test('renderer uses only the supplied DOM root and writes source-based labels', () => {
  const { root, elements } = fixture();
  const model = renderSpacecraftView(root, nominal);
  assert.equal(elements.get('craft-icon').attributes.transform, `translate(${model.position.x},${model.position.y})`);
  assert.equal(elements.get('site-ring').attributes.cx, String(model.site.x));
  assert.match(elements.get('projection-epoch-note').textContent, /Separate epochs; static illustration/);
  assert.match(elements.get('craft-subtitle').textContent, /Navigation epoch 120.0 s/);
  assert.equal(elements.get('initial-altitude').children[0].textContent, (nominal.altitudeM / 1000).toFixed(2));
  assert.equal(elements.get('initial-altitude').children[1].textContent, 'km');
});

test('switching to missing-site scenario removes earlier marker rather than inventing a target', () => {
  const { root, elements } = fixture();
  renderSpacecraftView(root, nominal);
  assert.equal(elements.get('site-marker').attributes.hidden, undefined);
  const model = renderSpacecraftView(root, missing);
  assert.equal(model.site, null);
  assert.equal(elements.get('site-marker').attributes.hidden, '');
  assert.equal(elements.get('missing-site-note').attributes.hidden, undefined);
  assert.match(elements.get('projection-epoch-note').textContent, /no landing site initialized/);
});

test('a renderer missing required markup fails visibly instead of substituting data', () => {
  assert.throws(() => renderSpacecraftView(null, nominal), /requires a DOM root/);
  const { root, elements } = fixture();
  elements.delete('craft-icon');
  assert.throws(() => renderSpacecraftView(root, nominal), /missing #craft-icon/);
});
