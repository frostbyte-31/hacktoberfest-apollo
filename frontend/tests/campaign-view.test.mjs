import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCampaignConfiguration, createCampaignViewer} from '../dist/campaign-view.mjs';

const configurations = ['earth-stack', 'docked-csm-lm', 'docked-csm-lm-deployed', 'lm', 'ascent', 'ascent-csm', 'csm', 'cm'];
const has = (model, name) => model.parts.includes(name);

test('Earth parking-orbit stack keeps Eagle inside a closed SLA and has no launch escape tower', () => {
  const model = buildCampaignConfiguration('earth-stack');
  for (const name of ['s-ivb-engine', 's-ivb', 'instrument-unit', 'closed-sla', 'service-module', 'command-module']) assert.ok(has(model, name));
  for (const name of ['descent-stage', 'ascent-cabin', 'landing-gear', 'inert-descent-engine']) assert.equal(has(model, name), false);
  assert.equal(model.parts.some(name => /escape|tower|les/i.test(name)), false);
  assert.match(model.label, /Eagle stowed/);
  const extent = model.triangles.flatMap(triangle => triangle.vertices).map(vertex => vertex[1]);
  assert.ok(Math.min(...extent) < 0 && Math.max(...extent) > 10, 'Complete upper-stage/CSM composition should be retained');
});

test('translunar docked configuration removes the launch stage and joins the CSM nose to the LM roof', () => {
  const model = buildCampaignConfiguration('docked-csm-lm');
  for (const name of ['descent-stage', 'ascent-cabin', 'roof-docking-collar', 'command-module', 'service-module']) assert.ok(has(model, name));
  assert.equal(has(model, 's-ivb'), false);
  assert.equal(has(model, 'closed-sla'), false);
  assert.equal(has(model, 'landing-gear'), false, 'The generic extracted-stack reference shows stowed landing gear');
});

test('pre-undocking lunar-orbit reference deploys Eagle landing gear while retaining the docked CSM', () => {
  const transit = buildCampaignConfiguration('docked-csm-lm');
  const prepared = buildCampaignConfiguration('docked-csm-lm-deployed');
  assert.equal(has(transit, 'landing-gear'), false);
  assert.equal(has(prepared, 'landing-gear'), true);
  for (const name of ['descent-stage', 'ascent-cabin', 'inert-descent-engine', 'roof-docking-collar', 'command-module', 'service-module']) assert.ok(has(prepared, name));
  assert.deepEqual(prepared.parts.filter(name => name !== 'landing-gear'), transit.parts);
  assert.ok(prepared.triangles.length > transit.triangles.length + 500, 'The prepared reference must add actual 3D gear geometry');
  assert.match(prepared.label, /landing gear deployed/);
  assert.equal(prepared.metadata.flightState, null, 'Deployment is a static configuration reference, not an executed command');
});

test('descent-stage model includes landing gear while the standalone ascent stage leaves it on the Moon', () => {
  const full = buildCampaignConfiguration('lm'), ascent = buildCampaignConfiguration('ascent');
  for (const name of ['descent-stage', 'landing-gear', 'inert-descent-engine', 'ascent-cabin', 'rcs-clusters']) assert.ok(has(full, name));
  for (const name of ['ascent-cabin', 'windows-and-hatch', 'rcs-clusters']) assert.ok(has(ascent, name));
  for (const name of ['descent-stage', 'landing-gear', 'inert-descent-engine', 'antennae-and-ladder']) assert.equal(has(ascent, name), false);
  assert.ok(ascent.triangles.length < full.triangles.length);
  assert.match(ascent.label, /descent stage left on Moon/);
});

test('rendezvous reference pairs Columbia with only the Eagle ascent stage', () => {
  const model = buildCampaignConfiguration('ascent-csm');
  for (const name of ['ascent-cabin', 'command-module', 'service-module', 'docking-probe']) assert.ok(has(model, name));
  for (const name of ['descent-stage', 'landing-gear', 'inert-descent-engine']) assert.equal(has(model, name), false);
  assert.match(model.label, /rendezvous reference/);
});

test('Earth-return Columbia omits the discarded docking probe and entry uses the Command Module alone', () => {
  // Apollo 11 Mission Report p.4-19: final probe and drogue were stowed in the LM before jettison.
  const returning = buildCampaignConfiguration('csm'), entry = buildCampaignConfiguration('cm');
  for (const name of ['service-module', 'service-engine', 'command-module', 'heat-shield']) assert.ok(has(returning, name));
  for (const name of ['service-module', 'service-engine', 's-ivb', 'ascent-cabin', 'descent-stage', 'landing-gear', 'docking-probe']) assert.equal(has(entry, name), false);
  assert.equal(has(returning, 'docking-probe'), false);
  assert.deepEqual(entry.parts, ['heat-shield', 'command-module']);
  assert.match(entry.label, /Service Module discarded/);
});

test('all configuration triangles have finite 3D geometry, bounded color and unit normals', () => {
  for (const configuration of configurations) {
    const model = buildCampaignConfiguration(configuration);
    assert.ok(model.triangles.length > 100);
    for (const triangle of model.triangles) {
      assert.equal(triangle.vertices.length, 3);
      for (const point of triangle.vertices) assert.ok(point.length === 3 && point.every(Number.isFinite));
      assert.ok(triangle.color.length === 3 && triangle.color.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
      assert.ok(triangle.normal.length === 3 && triangle.normal.every(Number.isFinite));
      assert.ok(Math.abs(Math.hypot(...triangle.normal) - 1) < 1e-8, configuration);
    }
  }
});

test('historical visual metadata exposes no authoritative spacecraft state, clock or actuator control', () => {
  for (const configuration of configurations) {
    const model = buildCampaignConfiguration(configuration);
    assert.equal(model.metadata.mode, 'STATIC HISTORICAL CONFIGURATION');
    for (const key of ['flightState', 'positionM', 'velocityMps', 'simulationTime']) assert.equal(model.metadata[key], null);
    assert.match(model.metadata.geometry, /not to scale/);
    assert.match(model.metadata.interaction, /Camera only; no actuator or spacecraft command/);
  }
  for (const value of ['landing-complete', '__proto__', null, true]) assert.throws(() => buildCampaignConfiguration(value), /Unknown/);
});

function canvasFixture(width, height) {
  const points = [], listeners = new Map();
  const context = {setTransform(){},clearRect(){points.length = 0;},beginPath(){},closePath(){},fill(){},moveTo(x,y){points.push([x,y]);},lineTo(x,y){points.push([x,y]);}};
  const canvas = {clientWidth: width, clientHeight: height, width: 0, height: 0,
    getContext: type => type === '2d' ? context : null,
    addEventListener(name, callback){listeners.set(name, callback);}, removeEventListener(name){listeners.delete(name);},setPointerCapture(){}};
  return {canvas, points, listeners};
}

test('camera projection fits complete model configurations on desktop and mobile and releases event handlers', () => {
  for (const [width, height] of [[920,600], [390,420]]) {
    const {canvas, points, listeners} = canvasFixture(width, height);
    const viewer = createCampaignViewer(canvas);
    for (const configuration of configurations) {
      viewer.draw(configuration);
      assert.ok(points.length > 100);
      for (const [x,y] of points) {
        assert.ok(Number.isFinite(x) && x >= 0 && x <= width, `${configuration} at ${width}px exceeded width: ${x}`);
        assert.ok(Number.isFinite(y) && y >= 0 && y <= height, `${configuration} at ${width}px exceeded height: ${y}`);
      }
    }
    const before = points.map(point => point.slice());
    listeners.get('pointerdown')({button: 0, clientX: 100, clientY: 100, pointerId: 1});
    listeners.get('pointermove')({clientX: 130, clientY: 115});
    assert.notDeepEqual(points, before, 'Dragging should rotate the camera');
    listeners.get('lostpointercapture')();
    const released = points.map(point => point.slice());
    listeners.get('pointermove')({clientX: 200, clientY: 200});
    assert.deepEqual(points, released, 'Lost capture must stop camera dragging');
    assert.equal(viewer.metadata.flightState, null);
    viewer.dispose();assert.equal(listeners.size, 0);
  }
});
