/** Presentation only: renders server-supplied surface-relative diagnostics. */
export function flightViewModel(spacecraft, engine, bounds = {heightM: 2000, widthM: 1800}) {
  const values = [spacecraft.altitudeM, spacecraft.downrangeM, spacecraft.pitchDeg, spacecraft.verticalSpeedMps, spacecraft.horizontalSpeedMps, engine.thrustN];
  if (!values.every(Number.isFinite)) throw new Error('Flight projection requires actual server measurements.');
  const heightM = Math.max(100, bounds.heightM);
  const widthM = Math.max(100, bounds.widthM);
  const x = 400 + spacecraft.downrangeM / widthM * 300;
  const y = 330 - Math.max(0, spacecraft.altitudeM) / heightM * 260;
  return {x, y, rotationDeg: spacecraft.pitchDeg, altitudeM: spacecraft.altitudeM,
    downrangeM: spacecraft.downrangeM, thrusting: engine.enabled && engine.thrustN > 0,
    mode: 'EDUCATIONAL_PHYSICS_LAB', frame: 'Server-derived downrange and altitude, metres',
    clipping: x < 25 || x > 775 || y < 25 || y > 340};
}
export function renderFlightView(root, spacecraft, engine, bounds) {
  const view = flightViewModel(spacecraft, engine, bounds);
  const craft = root.querySelector('#flight-craft');
  craft.removeAttribute('hidden');
  craft.setAttribute('transform', `translate(${Math.max(25,Math.min(775,view.x))},${Math.max(25,Math.min(330,view.y))}) rotate(${-view.rotationDeg})`);
  root.querySelector('#flight-plume').setAttribute('visibility', view.thrusting ? 'visible' : 'hidden');
  root.querySelector('#flight-empty').setAttribute('visibility', 'hidden');
  const arrow = root.querySelector('#flight-velocity');
  if (Number.isFinite(spacecraft.horizontalVelocityMps)) {
    arrow.removeAttribute('hidden');
    const horizontal = spacecraft.horizontalVelocityMps;
    const vertical = spacecraft.verticalSpeedMps;
    const speed = Math.hypot(horizontal, vertical);
    const length = Math.min(65, speed * 2);
    arrow.setAttribute('d', speed > 0 ? `M${view.x} ${view.y} l${horizontal/speed*length} ${-vertical/speed*length}` : '');
  } else arrow.setAttribute('hidden', '');
  root.querySelector('#flight-height-label').textContent = `${heightLabel(bounds?.heightM ?? 2000)} m`;
  root.querySelector('#flight-projection-note').textContent = view.clipping ? 'Vehicle is beyond this fixed view. Telemetry shows the measured state.' : 'Surface-relative projection · model and distances are diagrammatic';
  return view;
}
function heightLabel(value) { return Number(value).toLocaleString('en-US', {maximumFractionDigits: 0}); }
