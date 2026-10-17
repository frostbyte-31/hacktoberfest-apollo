import { validateGuidance, frameAt, boundedTime, nextEventTime, advanceReplay, seconds, clock, projectInitialState } from './guidance-state.mjs';
import { lastAt } from './replay.mjs';

const $ = id => document.getElementById(id);
const text = (id, value) => { $(id).textContent = value; };
let data = null;
let scenario = null;
let time = 0;
let playing = false;
let lastTimestamp = null;
let lastFrame = null;
let selectedEvent = null;
let animation = null;

function announce(value) { text('guidance-announcement', value); }
function setValue(id, value, unit = '') {
  const element = $(id);
  element.replaceChildren(document.createTextNode(value));
  if (unit) {
    const small = document.createElement('small');
    small.textContent = unit;
    element.append(small);
  }
}

function setPlaying(value) {
  playing = Boolean(value && scenario && time < scenario.durationSeconds);
  lastTimestamp = null;
  const children = $('guidance-play').children;
  children[0].textContent = playing ? 'Ⅱ' : '▶';
  children[1].textContent = playing ? 'Pause replay' : time >= (scenario?.durationSeconds ?? Infinity) ? 'Replay again' : 'Start replay';
  text('guidance-play-state', playing ? 'RECORDED · PLAYING' : 'RECORDED · PAUSED');
  if (playing && animation === null) animation = requestAnimationFrame(tick);
}

function tick(timestamp) {
  animation = null;
  if (!playing) return;
  if (lastTimestamp !== null) {
    const result = advanceReplay(scenario, time, (timestamp - lastTimestamp) / 1000, Number($('guidance-speed').value));
    time = result.time;
    render();
    if (!result.playing) {
      setPlaying(false);
      announce('Recorded experiment complete. No further AGC execution or spacecraft motion is shown.');
      return;
    }
  }
  lastTimestamp = timestamp;
  animation = requestAnimationFrame(tick);
}

function jump(target) {
  if (!scenario) return;
  setPlaying(false);
  time = boundedTime(target, scenario.durationSeconds);
  render();
}

function svgAttributes(id, values) {
  for (const [name, value] of Object.entries(values)) $(id).setAttribute(name, String(value));
}

function drawInitialState() {
  const initial = scenario.initialState;
  const projection = projectInitialState(initial);
  const x = p => 400 + p.x * 151;
  const y = p => 206 + p.y * 151;
  const p = projection.position;
  svgAttributes('orbit-outline', { r: 151 * projection.orbitRadius });
  $('craft-marker').hidden = false;
  $('craft-marker').removeAttribute('hidden');
  svgAttributes('craft-icon', { transform: `translate(${x(p)},${y(p)})` });
  svgAttributes('craft-guide', { d: `M${x(p) - 10} ${y(p) + 7} L${x(p) - 43} ${y(p) + 40} H${x(p) - 150}` });
  svgAttributes('craft-title', { x: x(p) - 150, y: y(p) + 54 });
  svgAttributes('craft-subtitle', { x: x(p) - 150, y: y(p) + 69 });
  text('craft-subtitle', `Navigation epoch ${seconds(initial.epochSeconds, { precision: 1 })} s · supplied state`);
  if (projection.velocity) {
    const v = projection.velocity;
    svgAttributes('velocity-vector', { d: `M${x(p) + v.x * 13} ${y(p) + v.y * 13} L${x(p) + v.x * 65} ${y(p) + v.y * 65}` });
  } else svgAttributes('velocity-vector', { d: '' });
  if (projection.site) {
    const site = projection.site;
    $('site-marker').removeAttribute('hidden');
    svgAttributes('site-ring', { cx: x(site), cy: y(site) });
    svgAttributes('site-point', { cx: x(site), cy: y(site) });
    svgAttributes('site-guide', { d: `M${x(site) + 7} ${y(site)} H${x(site) + 27} V${y(site) - 30} H${x(site) + 42}` });
    svgAttributes('site-title', { x: x(site) + 46, y: y(site) - 32 });
    svgAttributes('site-subtitle', { x: x(site) + 46, y: y(site) - 16 });
    text('site-title', 'PLANNED LANDING SITE');
    text('site-subtitle', `At TLAND ${seconds(initial.targetLandingTimeSeconds, { precision: 1 })} s`);
    $('missing-site-note').setAttribute('hidden', '');
  } else {
    $('site-marker').setAttribute('hidden', '');
    $('missing-site-note').removeAttribute('hidden');
  }
  text('moon-radius', `Reference radius · ${(initial.lunarRadiusM / 1000).toFixed(2)} km`);
  text('orbit-altitude', `CIRCULAR INITIAL ORBIT · ${(initial.altitudeM / 1000).toFixed(2)} km`);
  text('projection-epoch-note', projection.site
    ? `Spacecraft at ${seconds(initial.epochSeconds, { precision: 0 })} s · planned site at TLAND ${seconds(initial.targetLandingTimeSeconds, { precision: 1 })} s. Separate epochs; static illustration.`
    : `Spacecraft at ${seconds(initial.epochSeconds, { precision: 0 })} s · no landing site initialized. Static illustration; no motion is simulated.`);
  setValue('initial-altitude', (initial.altitudeM / 1000).toFixed(2), 'km');
  setValue('initial-speed', initial.speedMps.toFixed(2), 'm/s');
  setValue('initial-epoch', seconds(initial.epochSeconds, { precision: 0 }), 's');
}

function buildEvents() {
  const list = $('guidance-events');
  const marks = $('guidance-timeline-marks');
  list.replaceChildren();
  marks.replaceChildren();
  for (const event of scenario.events) {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.event = event.id;
    const timestamp = document.createElement('time');
    timestamp.textContent = clock(event.t).slice(3);
    const copy = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = event.title;
    const description = document.createElement('p');
    description.textContent = event.description;
    copy.append(title, description);
    button.append(timestamp, copy);
    button.addEventListener('click', () => {
      jump(event.t);
      announce(`${event.title}. Recorded execution elapsed ${clock(event.t)}.`);
    });
    li.append(button);
    list.append(li);
    const mark = document.createElement('i');
    mark.style.left = `${event.t / scenario.durationSeconds * 100}%`;
    marks.append(mark);
  }
  text('event-count', `${scenario.events.length} RETAINED EVENTS`);
}

function selectScenario(id) {
  scenario = data.cases.find(item => item.id === id);
  if (!scenario) return;
  setPlaying(false);
  lastFrame = null;
  selectedEvent = null;
  for (const button of document.querySelectorAll('[data-scenario]')) {
    const selected = button.dataset.scenario === id;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  }
  $('guidance-scrubber').max = scenario.durationSeconds;
  text('replay-duration', clock(scenario.durationSeconds).slice(3));
  text('replay-end-label', scenario.result.reviewReached ? 'V06 N61 · CREW REVIEW' : '01406 · NUMERICAL FAILURE');
  drawInitialState();
  buildEvents();
  // Open at an actual P63 checkpoint. Restart retains access to the entire startup.
  time = scenario.events.find(event => event.id === 'p63')?.t ?? 0;
  render();
  announce(`${scenario.title}. Recorded replay paused at original P63 selection. Restart to inspect startup.`);
}

function render() {
  if (!scenario) return;
  const frame = frameAt(scenario, time);
  const event = lastAt(scenario.events, time);
  text('replay-time', clock(time).slice(3));
  if (!playing) $('guidance-play').lastElementChild.textContent = time >= scenario.durationSeconds ? 'Replay again' : 'Start replay';
  $('guidance-scrubber').value = time;
  $('guidance-scrubber').style.setProperty('--g-progress', `${time / scenario.durationSeconds * 100}%`);
  if (frame && frame !== lastFrame) {
    lastFrame = frame;
    for (const [key, id] of Object.entries({ PROG: 'dsky-program', VERB: 'dsky-verb', NOUN: 'dsky-noun', R1: 'dsky-r1', R2: 'dsky-r2', R3: 'dsky-r3' })) text(id, frame.dsky[key]);
    text('guidance-stage', frame.stage);
    text('mission-clock', clock(frame.observedClockSeconds));
    setValue('guidance-ttf', seconds(frame.signedTimeToGoSeconds, { signed: true }), 's');
    setValue('guidance-tig', seconds(frame.ignitionTimeSeconds), 's GET');
    setValue('guidance-lead', seconds(frame.ignitionLeadSeconds), 's');
    text('root-count', frame.rootCount);
    text('observation-note', `Observation at ${clock(frame.t).slice(3)} elapsed · source line ${frame.source.rawLine.toLocaleString('en-US')}`);
    $('guidance-alarm').hidden = frame.alarms.length === 0;
    if (frame.alarms.length) {
      text('guidance-alarm-value', frame.alarms.join(' / '));
      text('guidance-alarm-description', frame.alarms.includes('01406')
        ? 'Original numerical guidance failed. The missing-site control retains its authentic alarm.'
        : frame.alarms.includes('01520')
          ? '01520 is retained from the original startup sequence. This is alarm-register history, not a new guidance failure.'
          : 'Original software recorded this alarm during startup or at the displayed checkpoint; see the event log.');
    }
  }
  text('guidance-stage-detail', event?.description ?? 'Awaiting the first recorded event.');
  if (event?.id !== selectedEvent) {
    selectedEvent = event?.id ?? null;
    for (const button of document.querySelectorAll('[data-event]')) {
      const item = scenario.events.find(e => e.id === button.dataset.event);
      button.classList.toggle('past', item.t <= time);
      button.classList.toggle('current', item.id === selectedEvent);
      if (item.id === selectedEvent) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    }
  }
  $('guidance-previous').disabled = time <= 0;
  $('guidance-next').disabled = time >= scenario.durationSeconds;
}

function addParagraph(parent, value, className = '') {
  const element = document.createElement('p');
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
}

function openDetails(kind) {
  const body = $('guidance-dialog-body');
  body.replaceChildren();
  body.className = 'g-provenance';
  if (kind === 'projection') {
    text('guidance-dialog-title', 'A starting point, not a flight path.');
    addParagraph(body, data?.labels.projection ?? 'A static illustration of supplied initialization data.');
    addParagraph(body, 'The circle uses the magnitude of the supplied three-dimensional position and the documented lunar reference radius. The arrow shows the initial velocity projected into X–Z. Lunar-surface texture and the vehicle symbol are illustrative. No position changes when the replay runs.');
    for (const assumption of scenario?.assumptions ?? []) addParagraph(body, assumption);
  } else {
    text('guidance-dialog-title', 'Every observation has a source.');
    if (!data || !scenario) addParagraph(body, 'Verified recording is unavailable. No guidance values have been substituted.');
    else {
      addParagraph(body, data.labels.replay);
      addParagraph(body, data.labels.scenario);
      const list = document.createElement('dl');
      const fields = {
        'Scenario': scenario.title,
        'Original software': 'Luminary 099, unchanged rope',
        'Emulator revision': data.provenance.emulatorRevision,
        'Rope SHA-256': data.provenance.ropeSha256,
        'Raw trace': scenario.sources.tracePath,
        'Trace SHA-256': scenario.sources.rawSha256,
        'Evidence report': data.provenance.phase10Report,
      };
      for (const [name, value] of Object.entries(fields)) {
        const dt = document.createElement('dt'); dt.textContent = name;
        const dd = document.createElement('dd'); dd.textContent = value;
        list.append(dt, dd);
      }
      body.append(list);
      addParagraph(body, data.labels.scope, 'g-proof-note');
      addParagraph(body, 'The original regression suite still identifies three missing historical evidence errors. They are not passing tests and are not needed to manufacture this recording. The Phase 10.5 report documents the recovery investigation.');
      const link = document.createElement('a');
      link.href = './data/guidance.json';
      link.textContent = 'Open the evidence-derived replay dataset ↗';
      link.target = '_blank';
      link.rel = 'noopener';
      body.append(link);
    }
  }
  $('guidance-dialog').showModal();
}

async function load() {
  $('guidance-loading').hidden = false;
  $('guidance-error').hidden = true;
  $('guidance-console').setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('./data/guidance.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`Recording request returned HTTP ${response.status}.`);
    data = validateGuidance(await response.json());
    for (const button of document.querySelectorAll('[data-scenario]')) button.disabled = false;
    for (const id of ['guidance-play', 'guidance-restart', 'guidance-previous', 'guidance-next', 'guidance-speed', 'guidance-scrubber', 'guidance-jump']) $(id).disabled = false;
    $('guidance-console').setAttribute('aria-busy', 'false');
    selectScenario('nominal');
  } catch (error) {
    setPlaying(false);
    text('guidance-error-detail', `${error.message} Start the documented demo server and verify the replay export.`);
    $('guidance-error').hidden = false;
    announce('Guidance recording unavailable. No replacement telemetry is displayed.');
  } finally { $('guidance-loading').hidden = true; }
}

for (const button of document.querySelectorAll('[data-scenario]')) button.addEventListener('click', () => selectScenario(button.dataset.scenario));
$('guidance-play').addEventListener('click', () => {
  if (playing) setPlaying(false);
  else {
    if (time >= scenario.durationSeconds) { time = 0; render(); }
    setPlaying(true);
  }
});
$('guidance-restart').addEventListener('click', () => { jump(0); announce('Replay reset to original startup.'); });
$('guidance-previous').addEventListener('click', () => jump(nextEventTime(scenario, time, -1)));
$('guidance-next').addEventListener('click', () => jump(nextEventTime(scenario, time, 1)));
$('guidance-jump').addEventListener('click', () => { jump(scenario.events.find(e => e.id === 'p63')?.t ?? 0); announce('Jumped to original P63 selection.'); });
$('guidance-scrubber').addEventListener('input', event => jump(Number(event.target.value)));
$('guidance-retry').addEventListener('click', load);
$('provenance-open').addEventListener('click', () => openDetails('provenance'));
$('provenance-footer').addEventListener('click', () => openDetails('provenance'));
$('projection-explain').addEventListener('click', () => openDetails('projection'));
$('guidance-dialog-close').addEventListener('click', () => $('guidance-dialog').close());
document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
load();
