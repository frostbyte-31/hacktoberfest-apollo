/** Independent, read-only SVG renderer. It never advances spacecraft state. */
import { projectInitialState, seconds } from './guidance-state.mjs';

/** Browser presentation coordinates only: Moon-centred basic-reference X–Z. */
export function spacecraftViewModel(initial) {
  const projected = projectInitialState(initial);
  const screen = p => ({ x: 400 + p.x * 151, y: 206 + p.y * 151 });
  return {
    position: screen(projected.position),
    site: projected.site ? screen(projected.site) : null,
    velocityDirection: projected.velocity,
    orbitRadiusPixels: 151 * projected.orbitRadius,
    altitudeKm: initial.altitudeM / 1000,
    speedMps: initial.speedMps,
    epochSeconds: initial.epochSeconds,
    targetLandingTimeSeconds: initial.targetLandingTimeSeconds,
    radiusKm: initial.lunarRadiusM / 1000,
    mode: 'STATIC_EDUCATIONAL_ILLUSTRATION',
    frame: 'Moon-centred basic-reference X–Z; screen-right +X, screen-up +Z',
    moving: false,
  };
}

/** Every lookup is scoped to the passed root, so a future renderer can coexist. */
export function renderSpacecraftView(root, initial) {
  if (!root?.querySelector) throw new Error('Spacecraft view requires a DOM root.');
  const view = spacecraftViewModel(initial);
  const element = id => {
    const node = root.querySelector(`#${id}`);
    if (!node) throw new Error(`Spacecraft view is missing #${id}.`);
    return node;
  };
  const attributes = (id, values) => {
    for (const [name, value] of Object.entries(values)) element(id).setAttribute(name, String(value));
  };
  const text = (id, value) => { element(id).textContent = value; };
  const quantity = (id, value, unit) => {
    const node = element(id);
    const document = root.ownerDocument;
    node.replaceChildren(document.createTextNode(value));
    const small = document.createElement('small');
    small.textContent = unit;
    node.append(small);
  };
  const p = view.position;
  attributes('orbit-outline', { r: view.orbitRadiusPixels });
  element('orbit-outline').removeAttribute('hidden');
  element('craft-marker').removeAttribute('hidden');
  attributes('craft-icon', { transform: `translate(${p.x},${p.y})` });
  attributes('craft-guide', { d: `M${p.x - 10} ${p.y + 7} L${p.x - 43} ${p.y + 40} H${p.x - 150}` });
  attributes('craft-title', { x: p.x - 150, y: p.y + 54 });
  attributes('craft-subtitle', { x: p.x - 150, y: p.y + 69 });
  text('craft-subtitle', `Navigation epoch ${seconds(view.epochSeconds, { precision: 1 })} s · supplied state`);
  const v = view.velocityDirection;
  attributes('velocity-vector', { d: v ? `M${p.x + v.x * 13} ${p.y + v.y * 13} L${p.x + v.x * 65} ${p.y + v.y * 65}` : '' });
  if (view.site) {
    const site = view.site;
    element('site-marker').removeAttribute('hidden');
    attributes('site-ring', { cx: site.x, cy: site.y });
    attributes('site-point', { cx: site.x, cy: site.y });
    attributes('site-guide', { d: `M${site.x + 7} ${site.y} H${site.x + 27} V${site.y - 30} H${site.x + 42}` });
    attributes('site-title', { x: site.x + 46, y: site.y - 32 });
    attributes('site-subtitle', { x: site.x + 46, y: site.y - 16 });
    text('site-title', 'PLANNED LANDING SITE');
    text('site-subtitle', `At TLAND ${seconds(view.targetLandingTimeSeconds, { precision: 1 })} s`);
    element('missing-site-note').setAttribute('hidden', '');
  } else {
    element('site-marker').setAttribute('hidden', '');
    element('missing-site-note').removeAttribute('hidden');
  }
  text('moon-radius', `Reference radius · ${view.radiusKm.toFixed(2)} km`);
  text('orbit-altitude', `CIRCULAR INITIAL ORBIT · ${view.altitudeKm.toFixed(2)} km`);
  text('projection-epoch-note', view.site
    ? `Spacecraft at ${seconds(view.epochSeconds, { precision: 0 })} s · planned site at TLAND ${seconds(view.targetLandingTimeSeconds, { precision: 1 })} s. Separate epochs; static illustration.`
    : `Spacecraft at ${seconds(view.epochSeconds, { precision: 0 })} s · no landing site initialized. Static illustration; no motion is simulated.`);
  quantity('initial-altitude', view.altitudeKm.toFixed(2), 'km');
  quantity('initial-speed', view.speedMps.toFixed(2), 'm/s');
  quantity('initial-epoch', seconds(view.epochSeconds, { precision: 0 }), 's');
  return view;
}
