import { boundedTime, nextEventTime, advanceReplay, seconds, clock } from './guidance-state.mjs';
import { RecordedTraceProvider, LiveBackendProvider } from './mission-provider.mjs';
import { renderSpacecraftView } from './spacecraft-view.mjs';
import { lastAt } from './replay.mjs';

const $ = id => document.getElementById(id);
const text = (id, value) => { $(id).textContent = value; };
let data = null;
let provider = null;
let liveDiscovery = null;
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
  scenario = provider.getScenario(id);
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
  renderSpacecraftView($('spacecraft-overview'), scenario.initialState);
  buildEvents();
  // Open at an actual P63 checkpoint. Restart retains access to the entire startup.
  time = scenario.events.find(event => event.id === 'p63')?.t ?? 0;
  render();
  announce(`${scenario.title}. Recorded replay paused at original P63 selection. Restart to inspect startup.`);
}

function render() {
  if (!scenario) return;
  const frame = provider.getSnapshot(scenario.id, time).frame;
  const event = lastAt(scenario.events, time);
  text('replay-time', clock(time).slice(3));
  if (!playing) $('guidance-play').lastElementChild.textContent = time >= scenario.durationSeconds ? 'Replay again' : 'Start replay';
  $('guidance-scrubber').value = time;
  $('guidance-scrubber').style.setProperty('--g-progress', `${time / scenario.durationSeconds * 100}%`);
  if (frame && frame !== lastFrame) {
    lastFrame = frame;
    for (const [key, id] of Object.entries({ PROG: 'dsky-program', VERB: 'dsky-verb', NOUN: 'dsky-noun', R1: 'dsky-r1', R2: 'dsky-r2', R3: 'dsky-r3' })) text(id, frame.dsky[key]);
    text('guidance-stage', frame.stage);
    text('top-mission-stage', frame.stage);
    text('top-mission-clock', clock(frame.observedClockSeconds));
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
  if (kind === 'compare') {
    text('guidance-dialog-title', 'One changed input. Original answers.');
    addParagraph(body, 'Completed recordings compared at their retained horizons. These are original AGC observations from separate synthetic experiments; changing a selection does not run a new guidance calculation.');
    const wrapper = document.createElement('div');
    wrapper.className = 'g-comparison-scroll';
    const table = document.createElement('table');
    table.className = 'g-comparison';
    const caption = document.createElement('caption');
    caption.textContent = 'Verified recorded execution · completed experiment outcomes';
    const head = document.createElement('thead');
    const labels = document.createElement('tr');
    for (const label of ['Scenario', 'Ignition time', 'Observed roots', 'Outcome']) {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; labels.append(th);
    }
    head.append(labels);
    const rows = document.createElement('tbody');
    for (const result of provider.compareScenarios()) {
      const row = document.createElement('tr');
      const title = document.createElement('th'); title.scope = 'row'; title.textContent = result.title; row.append(title);
      for (const value of [result.ignitionTimeSeconds === null ? 'Not calculated' : `${seconds(result.ignitionTimeSeconds)} s GET`, String(result.rootCount), result.reviewReached ? 'V06 N61 · pre-ignition review' : `${result.finalAlarms.join(' / ')} · guidance stopped`]) {
        const td = document.createElement('td'); td.textContent = value; row.append(td);
      }
      rows.append(row);
    }
    table.append(caption, head, rows); wrapper.append(table); body.append(wrapper);
    addParagraph(body, 'A root observation alone is not a completed ignition solution. The missing-site control reaches provisional root results before its genuine 01406 alarm; no ignition time is supplied. All absolute ignition times are mission elapsed seconds, not countdowns.');
  } else if (kind === 'capabilities') {
    text('guidance-dialog-title', 'What is available right now?');
    addParagraph(body, 'This screen reads verified recordings. Backend discovery only makes read-only status requests. It does not start an AGC, send key commands or control a vehicle.');
    addParagraph(body, liveDiscovery?.message ?? 'Backend discovery has not returned. Recorded playback remains independent of a backend.');
    const list = document.createElement('dl');
    for (const capability of liveDiscovery?.capabilities ?? []) {
      const dt = document.createElement('dt'); dt.textContent = `${capability.label} · ${capability.availability}`;
      const dd = document.createElement('dd'); dd.textContent = capability.description; list.append(dt, dd);
    }
    body.append(list);
    addParagraph(body, 'For bounded live yaw/pitch controls, open the existing attitude lab on a server launched with live execution enabled. Recorded Phase 10 pre-ignition guidance does not become live when that lab is available. Engine ignition, descent, multiplayer and AI crew are not available here.');
  } else if (kind === 'projection') {
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
      addParagraph(body, 'The display layout is Apollo-inspired. Program, verb, noun and register digits come from the verified relay decoder; lamp names follow Virtual AGC references. Indicator and sign-lamp states are unavailable here, so the panel is not a complete historical DSKY replica.');
      const dskyReference = document.createElement('a');
      dskyReference.href = 'https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/yaDSKY2/LM.ini';
      dskyReference.textContent = 'Pinned Virtual AGC Lunar Module DSKY reference ↗';
      dskyReference.target = '_blank';
      dskyReference.rel = 'noopener';
      body.append(dskyReference);
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

function clearUnavailableRecording() {
  setPlaying(false);
  provider = null;
  data = null;
  scenario = null;
  lastFrame = null;
  selectedEvent = null;
  time = 0;
  for (const id of ['dsky-program', 'dsky-verb', 'dsky-noun']) text(id, '??');
  for (const id of ['dsky-r1', 'dsky-r2', 'dsky-r3', 'mission-clock', 'top-mission-clock', 'guidance-ttf', 'guidance-tig', 'guidance-lead', 'initial-altitude', 'initial-speed', 'initial-epoch', 'replay-duration', 'moon-radius', 'orbit-altitude']) text(id, '—');
  text('guidance-stage', 'Recording unavailable');
  text('top-mission-stage', 'Recording unavailable');
  text('guidance-stage-detail', 'No substitute AGC values are displayed. Retry after restoring the verified dataset.');
  text('root-count', '—');
  text('observation-note', 'No verified observation loaded.');
  text('projection-epoch-note', 'Initialized geometry is unavailable. No substitute position is drawn.');
  text('event-count', 'NO VERIFIED RECORDING');
  text('replay-time', '00:00.00');
  text('replay-end-label', 'NO VERIFIED RECORDING');
  $('guidance-alarm').hidden = true;
  $('craft-marker').setAttribute('hidden', '');
  $('site-marker').setAttribute('hidden', '');
  $('missing-site-note').setAttribute('hidden', '');
  $('velocity-vector').setAttribute('d', '');
  $('orbit-outline').setAttribute('hidden', '');
  $('guidance-scrubber').value = 0;
  $('guidance-scrubber').style.setProperty('--g-progress', '0%');
  $('guidance-events').replaceChildren();
  $('guidance-timeline-marks').replaceChildren();
}

async function load() {
  setPlaying(false);
  $('guidance-loading').hidden = false;
  $('guidance-error').hidden = true;
  $('guidance-console').setAttribute('aria-busy', 'true');
  for (const control of document.querySelectorAll('[data-scenario], #guidance-compare, #guidance-outcome, #guidance-transport button, #guidance-transport select, #guidance-transport input')) control.disabled = true;
  try {
    provider = await RecordedTraceProvider.load({ url: './data/guidance.json' });
    data = provider.recording;
    for (const button of document.querySelectorAll('[data-scenario]')) button.disabled = false;
    for (const id of ['guidance-play', 'guidance-restart', 'guidance-previous', 'guidance-next', 'guidance-speed', 'guidance-scrubber', 'guidance-jump', 'guidance-compare', 'guidance-outcome']) $(id).disabled = false;
    $('guidance-console').setAttribute('aria-busy', 'false');
    selectScenario('nominal');
  } catch (error) {
    clearUnavailableRecording();
    text('guidance-error-detail', `${error.message} Start the documented demo server and verify the replay export.`);
    $('guidance-error').hidden = false;
    announce('Guidance recording unavailable. No replacement telemetry is displayed.');
  } finally { $('guidance-loading').hidden = true; $('guidance-console').setAttribute('aria-busy', 'false'); }
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
$('guidance-outcome').addEventListener('click', () => {
  if (!scenario) return;
  jump(scenario.durationSeconds);
  announce('Showing the selected experiment’s final retained observation. This is recorded execution, not a new guidance calculation.');
});
$('guidance-compare').addEventListener('click', () => openDetails('compare'));
$('capabilities-open').addEventListener('click', () => openDetails('capabilities'));
$('guidance-dialog-close').addEventListener('click', () => $('guidance-dialog').close());
document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
load();

// Read-only discovery never starts a session or changes this screen's recorded mode.
new LiveBackendProvider().discover().then(discovery => {
  liveDiscovery = discovery;
  text('backend-availability', discovery.available && discovery.liveEnabled ? 'Live attitude lab available separately' : discovery.available ? 'Recorded demo server · live controls disabled' : 'No live backend connected');
}).catch(() => {
  text('backend-availability', 'Live backend unavailable · recordings separate');
});
