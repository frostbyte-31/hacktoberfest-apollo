/** Source-backed observation stepping. No instructions, inputs or physics run here. */
import {PropulsionTraceProvider, RECORDED_MODE} from './propulsion-provider.mjs';
import {createMissionRenderer} from './mission-3d.mjs';
import {formatTime} from './replay.mjs';

const PREPARATION = Object.freeze([
  'p51-2', 'aligned-21', 'initialization-23', 'original-DAP-config-review-134',
  'original-mass-load-complete-142', 'p63lm-144', 'p63_after_r02-145', 'phase10-V06N61-146',
]);
const PROPULSION = Object.freeze([
  'phase10-V06N61-146', 'physical-init-147', 'R51-checklist-149',
  'R60-crew-attitude-review-151', 'crew-switches-set-157',
  'original-engine-enable-request-161', 'ignition-163', 'engine-on-164',
  'physical-engine-166', 'pipa-generated-167', 'pipa-delivered-168',
  'navigation-feedback-169', 'p63zoom-170', 'flatout-171',
  'engine-off-175', 'original-shutdown-reset-requested-177', 'crew-disarmed-179', 'end-180',
]);
const KIND_IDS = Object.freeze(['guidance', 'propulsion']);
const DSKY_FIELDS = Object.freeze(['PROG', 'VERB', 'NOUN', 'R1', 'R2', 'R3']);
const number = (value, digits = 3) => Number.isFinite(value)
  ? value.toLocaleString('en-US', {maximumFractionDigits: digits}) : 'Unavailable';

/** Exact event identities, including distinct raw rows sharing a CPU timestamp. */
export function showcaseEvents(provider, kind) {
  if (!KIND_IDS.includes(kind)) throw new TypeError('Unknown AGC showcase section.');
  const item = provider.getCase('connected');
  const ids = kind === 'guidance' ? PREPARATION : PROPULSION;
  const result = ids.map(id => {
    const event = item.events.find(candidate => candidate.id === id);
    if (!event) throw new Error(`The verified recording is missing observation ${id}.`);
    return event;
  });
  for (let i = 1; i < result.length; i++) {
    if (result[i].source.rawLine <= result[i - 1].source.rawLine || result[i].t < result[i - 1].t) {
      throw new Error('Showcase observations are not in recorded source order.');
    }
  }
  return Object.freeze(result);
}

/** Preserve unavailable physical state; never substitute an illustrative orbit. */
export function showcaseObservation(provider, kind, index) {
  const events = showcaseEvents(provider, kind);
  if (!Number.isSafeInteger(index) || index < 0 || index >= events.length) throw new RangeError('Invalid showcase observation index.');
  const event = events[index], item = provider.getCase('connected');
  const snapshot = provider.getEventSnapshot('connected', event.id), craft = snapshot.spacecraft;
  return Object.freeze({event, snapshot, observationNumber: index + 1, observationCount: events.length,
    scene: Object.freeze({mode: 'recorded', available: Boolean(craft),
      positionM: craft?.positionM, velocityMps: craft?.velocityMps, quaternion: craft?.quaternion,
      trajectoryM: craft ? provider.trajectoryThrough('connected', event.t, {rawLine: snapshot.source.rawLine}) : [],
      lunarRadiusM: item.initialGeometry.lunarRadiusM}),
    source: Object.freeze({mode: RECORDED_MODE, classification: item.classification,
      clock: 'CPU-call elapsed; not historical GET', cpuSeconds: event.t,
      cycle: event.cycle, rawLine: event.source.rawLine, path: item.sources.tracePath,
      rawSha256: item.sources.rawSha256}),
  });
}

/**
 * Dedicated source-backed inspector. Guidance and propulsion are two excerpts
 * from the same retained Phase 12 experiment, never successive historical flight.
 * load() fetches verified data once; all playback is exact observation stepping.
 */
export function createAgcShowcase({root, canvas, onState = () => {}}) {
  if (!root?.ownerDocument || !canvas?.getContext || typeof onState !== 'function') {
    throw new TypeError('AGC showcase requires a root element, canvas and optional state callback.');
  }
  const doc = root.ownerDocument;
  const make = (tag, text, className) => {
    const node = doc.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  let provider = null, kind = 'guidance', index = 0, playing = false, timer = null;
  let disposed = false, loading = false, error = null, loadPromise = null, graphicsError = null;
  let renderer = null;
  const abort = new AbortController(), removers = [];
  const listen = (node, name, callback, options) => {
    node.addEventListener(name, callback, options);
    removers.push(() => node.removeEventListener(name, callback, options));
  };
  root.classList.add('agc-showcase');
  const band = make('p', 'VERIFIED RECORDED EXECUTION / SYNTHETIC FIXTURE', 'agc-source-band');
  const header = make('div', undefined, 'agc-header');
  const heading = make('h3', 'Original Luminary 099 observations');
  const progress = make('p', 'Loading source-backed observations…', 'agc-progress');
  header.append(heading, progress);
  const eventTitle = make('h4', 'Awaiting verified recording', 'agc-event-title');
  const eventDescription = make('p', undefined, 'agc-event-description');
  const dsky = make('div', undefined, 'agc-dsky');
  dsky.setAttribute('aria-label', 'Recorded DSKY digit fields');
  const fields = new Map();
  for (const field of DSKY_FIELDS) {
    const cell = make('div', undefined, 'agc-dsky-field');
    const value = make('output', field.startsWith('R') ? '?????' : '??');
    value.dataset.agcField = field;
    cell.append(make('span', field), value);dsky.append(cell);fields.set(field, value);
  }
  const dskyNote = make('p', 'Original channel 010 digit observations. Signs and indicator lamps are unavailable.', 'agc-dsky-note');
  const metrics = make('dl', undefined, 'agc-telemetry');
  const physicalNote = make('p', undefined, 'agc-physical-note');
  const provenance = make('p', undefined, 'agc-provenance');
  const controls = make('div', undefined, 'agc-controls');
  const previous = make('button', 'Previous observation');
  const play = make('button', 'Play observations');
  const next = make('button', 'Next observation');
  const restart = make('button', 'Restart excerpt');
  const vehicleView = make('button', '3D vehicle');
  const orbitView = make('button', 'Orbit overview');
  const resetCamera = make('button', 'Reset camera');
  for (const button of [previous, play, next, restart, vehicleView, orbitView, resetCamera]) {button.type = 'button';controls.append(button);}
  const status = make('p', 'Loading the verified recording.', 'agc-status');
  status.setAttribute('role', 'status');status.setAttribute('aria-live', 'polite');
  const scope = make('p', 'This is the retained Phase 12 synthetic fixed-attitude engine and inertial-feedback experiment. Observation stepping replays original execution; it sends no commands and performs no new simulation. It does not demonstrate a historical trajectory, descent or landing.', 'agc-scope');
  root.replaceChildren(band, header, eventTitle, eventDescription, controls, dsky, dskyNote, metrics, physicalNote, status, provenance, scope);
  try {renderer = createMissionRenderer(canvas);renderer.setView('vehicle');renderer.draw({mode: 'recorded', available: false});}
  catch (failure) {graphicsError = failure.message;}

  function publicState() {
    const events = provider ? showcaseEvents(provider, kind) : [];
    const event = events[index] ?? null;
    return Object.freeze({available: Boolean(provider) && !disposed, loading, kind, playing,
      index, eventCount: events.length, eventId: event?.id ?? null,
      excerptComplete: Boolean(events.length) && index === events.length - 1,
      originalExecutionMode: RECORDED_MODE, mode: 'RECORDED OBSERVATION STEPPING',
      historicalFlightDemonstrated: false, error, graphicsError});
  }
  function publish() {onState(publicState());}
  function metric(label, value) {metrics.append(make('dt', label), make('dd', value));}
  function draw() {
    if (!renderer || disposed) return;
    const observation = provider ? showcaseObservation(provider, kind, index) : null;
    renderer.draw(observation?.scene ?? {mode: 'recorded', available: false});
  }
  function render() {
    if (disposed) return;
    const state = publicState();
    previous.disabled = !state.available || index === 0;
    next.disabled = !state.available || state.excerptComplete;
    play.disabled = !state.available || state.excerptComplete;
    restart.disabled = !state.available;
    play.textContent = playing ? 'Pause observations' : 'Play observations';
    play.setAttribute('aria-pressed', String(playing));
    heading.textContent = kind === 'guidance' ? 'Original guidance preparation' : 'Original engine command → physical feedback';
    metrics.replaceChildren();
    if (!provider) {
      eventTitle.textContent = error ? 'Verified recording unavailable' : 'Awaiting verified recording';
      eventDescription.textContent = 'No substitute computer output or spacecraft state is shown.';
      progress.textContent = loading ? 'Loading verified source…' : 'Recording not loaded';
      status.textContent = error ?? 'Use the recorded inspector after its source has loaded.';
      physicalNote.textContent = graphicsError ? `3D viewer unavailable: ${graphicsError}. Source readouts remain available when loaded.` : 'No physical observation is available yet.';
      for (const [field, value] of fields) value.textContent = field.startsWith('R') ? '?????' : '??';
      provenance.textContent = '';
      draw();publish();return;
    }
    const observation = showcaseObservation(provider, kind, index), {event, snapshot, source} = observation;
    const frame = snapshot.frame, craft = snapshot.spacecraft;
    eventTitle.textContent = event.title;eventDescription.textContent = event.description;
    progress.textContent = `Observation ${observation.observationNumber} / ${observation.observationCount} · ${formatTime(source.cpuSeconds)} CPU elapsed · not mission GET`;
    for (const [field, value] of fields) value.textContent = frame.dsky[field];
    metric('Observation CPU call', String(source.cycle));
    metric('Physical thrust', craft ? `${number(craft.deliveredThrustN, 1)} N` : 'Unavailable before the first physical sample');
    metric('Engine state', craft ? craft.engineEnabled ? 'Enabled in retained physical plant' : 'Off in retained physical plant' : 'Unavailable');
    metric('Delivered PIPA counts', frame.pipa.deliveredCounts.join(' / '));
    metric('Physical mass', craft ? `${number(craft.massKg, 1)} kg` : 'Unavailable');
    metric('Physical speed', craft ? `${number(Math.hypot(...craft.velocityMps), 2)} m/s` : 'Unavailable');
    metric('Physical sample clock', craft ? `${number(craft.physicalTimeSeconds)} s · model clock, not GET` : 'Unavailable');
    physicalNote.textContent = graphicsError
      ? `3D viewer unavailable: ${graphicsError}. The retained numerical observations remain visible.`
      : craft ? '3D: retained basic REF position and fixed body-to-REF quaternion. LM enlarged; geometry not to scale. The arrow shows velocity direction. Camera movement does not steer the spacecraft.'
        : 'No physical sample exists at this observation. The 3D view shows no substitute spacecraft position.';
    status.textContent = playing
      ? 'Automatically stepping exact recorded observations every 2.5 seconds. This is presentation pacing, not real-time CPU or flight execution.'
      : state.excerptComplete ? 'Recorded excerpt complete. This is not completion of a flight maneuver or a lunar landing.'
        : 'Paused at an exact source observation. Step to inspect the original command and feedback chain.';
    provenance.textContent = `Phase 12 / connected case · CPU call ${source.cycle} · raw line ${source.rawLine} · ${source.path} · raw SHA-256 ${source.rawSha256}. DSKY observation: ${frame.observationSources.dsky ? `CPU ${frame.observationSources.dsky.cycle}, raw line ${frame.observationSources.dsky.rawLine}` : 'unavailable'}. Physical sample: ${craft ? `CPU ${craft.source.cycle}, raw line ${craft.source.rawLine}` : 'unavailable'}. PIPA observation: ${frame.pipa.source ? `CPU ${frame.pipa.source.cycle}, raw line ${frame.pipa.source.rawLine}` : 'unavailable'}. Held values retain their earlier source rows.`;
    draw();publish();
  }
  function stop() {playing = false;if (timer !== null) {clearTimeout(timer);timer = null;}}
  function schedule() {
    if (!playing || disposed) return;
    timer = setTimeout(() => {
      timer = null;
      if (!playing || disposed) return;
      const events = showcaseEvents(provider, kind);
      if (index < events.length - 1) index++;
      if (index === events.length - 1) playing = false;
      render();schedule();
    }, 2500);
  }
  const api = {
    async load() {
      if (disposed) throw new Error('This showcase has been disposed.');
      if (provider) return publicState();
      if (loadPromise) return loadPromise;
      loading = true;error = null;render();
      loadPromise = (async () => {
        try {
          const loaded = await PropulsionTraceProvider.load('./data/propulsion.json', {signal: abort.signal});
          // Both excerpts must exist before either can appear available.
          for (const value of KIND_IDS) showcaseEvents(loaded, value);
          if (disposed) return publicState();
          provider = loaded;error = null;
        } catch (failure) {if (!disposed) error = `The source-backed AGC recording could not load: ${failure.message}`;}
        finally {loading = false;loadPromise = null;render();}
        return publicState();
      })();
      return loadPromise;
    },
    show(nextKind) {
      if (!KIND_IDS.includes(nextKind)) throw new TypeError('Unknown AGC showcase section.');
      if (kind !== nextKind) {stop();kind = nextKind;index = 0;renderer?.reset();renderer?.setView('vehicle');}
      render();return publicState();
    },
    play() {
      if (!provider || disposed || index >= showcaseEvents(provider, kind).length - 1) return publicState();
      if (!playing) {playing = true;schedule();render();}
      return publicState();
    },
    pause() {stop();render();return publicState();},
    restart() {stop();index = 0;renderer?.reset();render();return publicState();},
    step(direction) {
      if (direction !== 1 && direction !== -1) throw new TypeError('Observation step must be 1 or -1.');
      stop();
      if (provider && !disposed) index = Math.max(0, Math.min(showcaseEvents(provider, kind).length - 1, index + direction));
      render();return publicState();
    },
    dispose() {
      if (disposed) return;stop();disposed = true;abort.abort();observer?.disconnect();
      for (const remove of removers) remove();renderer?.dispose();
    },
    get state() {return publicState();},
  };
  listen(previous, 'click', () => api.step(-1));listen(next, 'click', () => api.step(1));
  listen(play, 'click', () => playing ? api.pause() : api.play());listen(restart, 'click', () => api.restart());
  listen(vehicleView, 'click', () => {renderer?.setView('vehicle');draw();});
  listen(orbitView, 'click', () => {renderer?.setView('orbit');draw();});
  listen(resetCamera, 'click', () => {renderer?.reset();draw();});
  listen(doc, 'visibilitychange', () => {if (doc.hidden) api.pause();});
  const surface = renderer?.surface ?? canvas;
  let pointer = null;
  listen(surface, 'pointerdown', event => {
    pointer = {id: event.pointerId, x: event.clientX, y: event.clientY};surface.setPointerCapture(event.pointerId);
  });
  listen(surface, 'pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    renderer?.orbit(event.clientX - pointer.x, event.clientY - pointer.y);
    pointer.x = event.clientX;pointer.y = event.clientY;draw();
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) listen(surface, name, () => {pointer = null;});
  listen(surface, 'wheel', event => {event.preventDefault();renderer?.zoom(event.deltaY);draw();}, {passive: false});
  listen(canvas, 'mission-renderer-status', event => {graphicsError = event.detail.available ? null : event.detail.message;api.pause();});
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(() => {renderer?.resize();draw();}) : null;
  observer?.observe(canvas);render();
  return api;
}
