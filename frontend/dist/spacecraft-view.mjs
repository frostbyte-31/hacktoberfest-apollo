/**
 * Static rendering of supplied three-dimensional initial conditions.
 * This module never advances a state, integrates an orbit, or generates a flight path.
 */
import { projectInitialState, seconds } from './guidance-state.mjs';

/** @typedef {[number, number, number]} Vector3 */
/**
 * @typedef {object} InitialSpacecraftState
 * @property {Vector3} positionM Moon-centered basic REF inertial position, metres.
 * @property {Vector3} velocityMps Moon-centered basic REF inertial velocity, metres/second.
 * @property {Vector3|null} landingSiteBasicRefAtTlandM Independently transformed site at TLAND.
 * @property {number} epochSeconds Supplied navigation epoch in the synthetic mission clock.
 * @property {number|null} targetLandingTimeSeconds Declared TLAND, not a propagated arrival.
 * @property {number} lunarRadiusM Supplied lunar reference radius, metres.
 * @property {number|null} altitudeM Supplied altitude, metres; null means unavailable.
 * @property {number|null} speedMps Supplied speed, metres/second; null means unavailable.
 */

const vector = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
const optionalNumber = value => value === null || value === undefined || Number.isFinite(value);
const quantity = (value, divisor = 1) => Number.isFinite(value) ? (value / divisor).toFixed(2) : '—';
const components = (value, unit) => `[${value.map(component => seconds(component, { precision: 2 })).join(', ')}] ${unit}`;

/**
 * Validate the rendering boundary independently from an execution provider.
 * Missing optional values remain unavailable; invalid geometry rejects the entire view.
 * Numeric vectors retain all three supplied axes even though the graphic projects X–Z.
 *
 * @param {InitialSpacecraftState|null|undefined} initialState
 * @returns {{projection: ReturnType<typeof projectInitialState>, position: string, velocity: string}|null}
 */
export function spacecraftViewModel(initialState) {
  const state = initialState;
  if (!state || !vector(state.positionM) || !vector(state.velocityMps)
    || !Number.isFinite(state.lunarRadiusM) || state.lunarRadiusM <= 0
    || !Number.isFinite(state.epochSeconds)
    || !optionalNumber(state.altitudeM) || (state.altitudeM ?? 0) < 0
    || !optionalNumber(state.speedMps) || (state.speedMps ?? 0) < 0
    || !optionalNumber(state.targetLandingTimeSeconds)) return null;
  const radius = Math.hypot(...state.positionM);
  if (!Number.isFinite(radius) || radius <= state.lunarRadiusM
    || !Number.isFinite(Math.hypot(...state.velocityMps))) return null;
  const site = state.landingSiteBasicRefAtTlandM ?? null;
  if (site !== null && (!vector(site) || !Number.isFinite(Math.hypot(...site))
    || Math.hypot(...site) === 0 || !Number.isFinite(state.targetLandingTimeSeconds))) return null;
  const projection = projectInitialState({ ...state, landingSiteBasicRefAtTlandM: site });
  if (!Number.isFinite(projection.orbitRadius)
    || ![projection.position.x, projection.position.y].every(Number.isFinite)
    || (projection.site && ![projection.site.x, projection.site.y].every(Number.isFinite))) return null;
  return {
    projection,
    position: components(state.positionM, 'm'),
    velocity: components(state.velocityMps, 'm/s'),
  };
}

/**
 * Render a static state using the existing orbital SVG's IDs. Optional readouts may
 * be omitted by a host layout. Call again only when the selected initial state changes;
 * replay elapsed time deliberately is not an input to the renderer.
 *
 * @param {Document|Element|DocumentFragment} root Scope containing the orbital SVG/readouts.
 * @param {InitialSpacecraftState|null|undefined} initialState
 * @returns {boolean} Whether supplied geometry was available and valid.
 */
export function renderSpacecraftView(root, initialState) {
  const find = id => root.querySelector(`#${id}`);
  const text = (id, value) => { const element = find(id); if (element) element.textContent = value; };
  const attributes = (id, values) => {
    const element = find(id);
    if (element) for (const [name, value] of Object.entries(values)) element.setAttribute(name, String(value));
  };
  const visible = (id, value) => {
    const element = find(id);
    if (element) {
      if (value) element.removeAttribute('hidden');
      else element.setAttribute('hidden', '');
    }
  };
  const setValue = (id, value, unit) => {
    const element = find(id);
    if (!element) return;
    element.textContent = value;
    if (unit) {
      const small = element.ownerDocument.createElement('small');
      small.textContent = unit;
      element.append(small);
    }
  };
  const missingNote = (title, description) => {
    const labels = find('missing-site-note')?.querySelectorAll('text');
    if (labels?.[0]) labels[0].textContent = title;
    if (labels?.[1]) labels[1].textContent = description;
  };
  const model = spacecraftViewModel(initialState);
  if (!model) {
    visible('craft-marker', false);
    visible('site-marker', false);
    visible('orbit-outline', false);
    visible('missing-site-note', true);
    attributes('velocity-vector', { d: '' });
    missingNote('INITIAL STATE UNAVAILABLE', 'No geometry has been substituted');
    text('moon-radius', 'Reference radius · unavailable');
    text('orbit-altitude', 'INITIAL ORBIT · UNAVAILABLE');
    text('projection-epoch-note', 'Supplied initial geometry is missing or invalid. No spacecraft position, velocity, or trajectory is inferred.');
    text('state-position', '—');
    text('state-velocity', '—');
    setValue('initial-altitude', '—', 'km');
    setValue('initial-speed', '—', 'm/s');
    setValue('initial-epoch', '—', 's');
    return false;
  }

  const initial = initialState;
  const projection = model.projection;
  const x = point => 400 + point.x * 151;
  const y = point => 206 + point.y * 151;
  const p = projection.position;
  visible('orbit-outline', true);
  attributes('orbit-outline', { r: 151 * projection.orbitRadius });
  visible('craft-marker', true);
  attributes('craft-icon', { transform: `translate(${x(p)},${y(p)})` });
  attributes('craft-guide', { d: `M${x(p) - 10} ${y(p) + 7} L${x(p) - 43} ${y(p) + 40} H${x(p) - 150}` });
  attributes('craft-title', { x: x(p) - 150, y: y(p) + 54 });
  attributes('craft-subtitle', { x: x(p) - 150, y: y(p) + 69 });
  text('craft-title', 'LM · INITIAL STATE');
  text('craft-subtitle', `Navigation epoch ${seconds(initial.epochSeconds, { precision: 1 })} s · supplied state`);
  if (projection.velocity) {
    const v = projection.velocity;
    attributes('velocity-vector', { d: `M${x(p) + v.x * 13} ${y(p) + v.y * 13} L${x(p) + v.x * 65} ${y(p) + v.y * 65}` });
  } else attributes('velocity-vector', { d: '' });
  if (projection.site) {
    const site = projection.site;
    visible('site-marker', true);
    attributes('site-ring', { cx: x(site), cy: y(site) });
    attributes('site-point', { cx: x(site), cy: y(site) });
    attributes('site-guide', { d: `M${x(site) + 7} ${y(site)} H${x(site) + 27} V${y(site) - 30} H${x(site) + 42}` });
    attributes('site-title', { x: x(site) + 46, y: y(site) - 32 });
    attributes('site-subtitle', { x: x(site) + 46, y: y(site) - 16 });
    text('site-title', 'PLANNED LANDING SITE');
    text('site-subtitle', `At TLAND ${seconds(initial.targetLandingTimeSeconds, { precision: 1 })} s`);
    visible('missing-site-note', false);
  } else {
    visible('site-marker', false);
    visible('missing-site-note', true);
    missingNote('NO SITE SUPPLIED', 'Landing target unavailable');
  }
  text('moon-radius', `Reference radius · ${(initial.lunarRadiusM / 1000).toFixed(2)} km`);
  text('orbit-altitude', `CIRCULAR INITIAL ORBIT · ${quantity(initial.altitudeM, 1000)} km`);
  text('projection-epoch-note', projection.site
    ? `Spacecraft at ${seconds(initial.epochSeconds, { precision: 0 })} s · planned site at TLAND ${seconds(initial.targetLandingTimeSeconds, { precision: 1 })} s. Separate epochs; static illustration. Vehicle symbol and velocity-arrow length are not to scale.`
    : `Spacecraft at ${seconds(initial.epochSeconds, { precision: 0 })} s · no landing site initialized. Static illustration; no motion is simulated. Vehicle symbol and velocity-arrow length are not to scale.`);
  text('state-position', model.position);
  text('state-velocity', model.velocity);
  setValue('initial-altitude', quantity(initial.altitudeM, 1000), 'km');
  setValue('initial-speed', quantity(initial.speedMps), 'm/s');
  setValue('initial-epoch', seconds(initial.epochSeconds, { precision: 0 }), 's');
  return true;
}
