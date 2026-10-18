import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {PropulsionTraceProvider, RECORDED_MODE} from '../dist/propulsion-provider.mjs';
import {showcaseEvents, showcaseObservation, createAgcShowcase} from '../dist/agc-showcase.mjs';

const data = JSON.parse(readFileSync(new URL('../dist/data/propulsion.json', import.meta.url), 'utf8'));
const provider = new PropulsionTraceProvider(data);

test('showcase excerpts use exact original event identities in retained raw-row order', () => {
  for (const kind of ['guidance', 'propulsion']) {
    const events = showcaseEvents(provider, kind);
    assert.ok(events.length >= 8);
    assert.equal(Object.isFrozen(events), true);
    for (let index = 0; index < events.length; index++) {
      const observation = showcaseObservation(provider, kind, index);
      assert.equal(observation.event, events[index]);
      assert.equal(observation.snapshot.frame.source.rawLine, events[index].source.rawLine);
      assert.equal(observation.snapshot.frame.cycle, events[index].cycle);
      assert.equal(observation.source.rawSha256, provider.getCase('connected').sources.rawSha256);
      assert.equal(observation.source.mode, RECORDED_MODE);
      assert.equal(observation.observationNumber, index + 1);
      assert.match(observation.source.clock, /not historical GET/);
      if (index) assert.ok(events[index].source.rawLine > events[index - 1].source.rawLine);
    }
  }
});

test('guidance excerpt shows no invented physical state even at a timestamp shared with physical initialization', () => {
  const guidance = showcaseEvents(provider, 'guidance');
  for (let index = 0; index < guidance.length; index++) {
    const observation = showcaseObservation(provider, 'guidance', index);
    assert.equal(observation.scene.available, false);
    assert.equal(observation.snapshot.spacecraft, null);
    assert.equal(observation.scene.positionM, undefined);
    assert.deepEqual(observation.scene.trajectoryM, []);
  }
  const review = showcaseObservation(provider, 'guidance', guidance.length - 1);
  const physical = showcaseObservation(provider, 'propulsion', 1);
  assert.equal(review.event.t, physical.event.t, 'The exact source row, rather than time alone, distinguishes these events');
  assert.equal(physical.scene.available, true);
  assert.ok(physical.event.source.rawLine > review.event.source.rawLine);
});

test('propulsion excerpts preserve actual engine command, physical response and inertial feedback as separate observations', () => {
  const events = showcaseEvents(provider, 'propulsion');
  const selected = id => showcaseObservation(provider, 'propulsion', events.findIndex(event => event.id === id));
  const request = selected('original-engine-enable-request-161');
  const originalOn = selected('engine-on-164');
  const physical = selected('physical-engine-166');
  const delivered = selected('pipa-delivered-168');
  const navigation = selected('navigation-feedback-169');
  assert.equal(request.snapshot.spacecraft.engineEnabled, false);
  assert.equal(originalOn.snapshot.spacecraft.engineEnabled, false, 'An AGC output row is not yet the physical plant response');
  assert.equal(physical.snapshot.spacecraft.engineEnabled, true);
  assert.ok(physical.snapshot.spacecraft.deliveredThrustN > 0);
  assert.ok(delivered.source.rawLine < navigation.source.rawLine);
  assert.ok(delivered.snapshot.frame.pipa.deliveredCounts.some(value => value > 0));
});

test('3D source preserves recorded vectors, fixed attitude and only prior observed trajectory samples', () => {
  const events = showcaseEvents(provider, 'propulsion');
  const observation = showcaseObservation(provider, 'propulsion', events.findIndex(event => event.id === 'navigation-feedback-169'));
  const craft = observation.snapshot.spacecraft;
  assert.deepEqual(observation.scene.positionM, craft.positionM);
  assert.deepEqual(observation.scene.velocityMps, craft.velocityMps);
  assert.deepEqual(observation.scene.quaternion, craft.quaternion);
  assert.deepEqual(observation.scene.trajectoryM, provider.trajectoryThrough('connected', observation.event.t, {rawLine: observation.source.rawLine}));
  assert.ok(observation.scene.trajectoryM.length < provider.trajectoryThrough('connected', provider.getCase('connected').durationSeconds).length);
  assert.match(observation.source.classification, /not a historical Apollo 11 flight/);
});

test('showcase rejects unknown sections, missing exact events and invalid indices rather than substituting observations', () => {
  assert.throws(() => showcaseEvents(provider, 'landing'), /Unknown/);
  for (const index of [-1, 99, NaN, 0.5, '0']) assert.throws(() => showcaseObservation(provider, 'guidance', index), /Invalid/);
  assert.throws(() => showcaseEvents({getCase: () => ({events: []})}, 'propulsion'), /missing observation/);
  assert.throws(() => showcaseEvents({getCase: () => ({events: [...provider.getCase('connected').events].map(event => ({...event, source: {rawLine: 1}}))})}, 'guidance'), /not in recorded source order/);
});

function fixture() {
  const context = {setTransform(){},fillRect(){},createRadialGradient(){return {addColorStop(){}};},beginPath(){},arc(){},closePath(){},fill(){},stroke(){},moveTo(){},lineTo(){}};
  const doc = {hidden: false, createElement(tag) {return node(tag);}, listeners: new Map(), addEventListener(name, cb) {this.listeners.set(name, cb);}, removeEventListener(name) {this.listeners.delete(name);}};
  function node(tag) {
    return {tag, ownerDocument: doc, children: [], dataset: {}, attributes: {}, listeners: new Map(), textContent: '',
      classList: {add(){}}, setAttribute(name, value) {this.attributes[name] = value;},
      append(...values) {this.children.push(...values);}, replaceChildren(...values) {this.children = values;},
      addEventListener(name, cb) {this.listeners.set(name, cb);}, removeEventListener(name) {this.listeners.delete(name);},
    };
  }
  const root = node('section'), canvas = node('canvas');
  Object.assign(canvas, {clientWidth: 800, clientHeight: 500, width: 0, height: 0, getContext: kind => kind === '2d' ? context : null});
  return {doc, root, canvas};
}

test('component only fetches retained data and exposes observation playback without any AGC commands or mission-complete claim', async t => {
  const requests = [], states = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    requests.push({url, init});return {ok: true, json: async () => data};
  });
  const {doc, root, canvas} = fixture();
  const component = createAgcShowcase({root, canvas, onState: value => states.push(value)});
  assert.equal(component.state.available, false);
  await component.load();
  assert.equal(component.state.available, true);
  assert.equal(component.state.kind, 'guidance');
  assert.equal(component.state.historicalFlightDemonstrated, false);
  component.step(1);assert.equal(component.state.eventId, 'aligned-21');
  component.play();assert.equal(component.state.playing, true);
  doc.hidden = true;doc.listeners.get('visibilitychange')();
  assert.equal(component.state.playing, false);
  component.show('propulsion');assert.equal(component.state.eventId, 'phase10-V06N61-146');
  for (let index = 0; index < 30; index++) component.step(1);
  assert.equal(component.state.eventId, 'end-180');
  assert.equal(component.state.excerptComplete, true);
  assert.equal(component.state.historicalFlightDemonstrated, false);
  component.play();assert.equal(component.state.playing, false);
  component.restart();assert.equal(component.state.index, 0);
  await component.load();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, './data/propulsion.json');
  assert.equal(requests[0].init.cache, 'no-store');
  assert.equal(requests[0].init.method, undefined);
  assert.ok(states.length > 10);
  component.dispose();
  assert.equal(component.state.available, false);
  assert.equal(canvas.listeners.size, 0);
  assert.equal(doc.listeners.size, 0);
});

test('missing recording disables playback and keeps unavailable DSKY instead of fabricated results', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({ok: false, status: 503}));
  const {root, canvas} = fixture();
  const component = createAgcShowcase({root, canvas});
  await component.load();
  assert.equal(component.state.available, false);
  assert.match(component.state.error, /could not load/);
  component.play();assert.equal(component.state.playing, false);
  component.step(1);assert.equal(component.state.index, 0);
  component.dispose();
  await assert.rejects(component.load(), /disposed/);
});
