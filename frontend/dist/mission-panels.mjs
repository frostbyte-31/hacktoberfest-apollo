import { CREW_ROLES } from './mission-provider.mjs';
import { seconds } from './guidance-state.mjs';

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}

/** Compare independently recorded end results; this panel never tracks the replay cursor. */
export function renderScenarioComparison(root, scenarios, onExplore) {
  const body = root.querySelector('#scenario-comparison');
  body.replaceChildren();
  scenarios.forEach((scenario, index) => {
    const result = scenario.result;
    const row = element('tr');
    row.dataset.comparison = scenario.id;
    const name = element('td', `${String.fromCharCode(65 + index)} / ${scenario.id === 'missing-site' ? 'Missing landing site' : scenario.id === 'nominal' ? '15 km orbit' : '16 km orbit'}`);
    name.append(element('small', 'Synthetic mission inputs'));
    const roots = element('td', String(result.rootCount));
    roots.append(element('small', result.reviewReached ? 'Normal returns' : 'Provisional results'));
    const ignition = element('td', result.ignitionTimeSeconds === null ? 'Unavailable' : seconds(result.ignitionTimeSeconds));
    const outcome = element('td', result.reviewReached ? 'V06 N61 · crew review' : '01406 · guidance stopped');
    const action = element('td');
    const button = element('button', 'Inspect result ↗');
    button.type = 'button';
    button.setAttribute('aria-label', `Inspect recorded result for ${scenario.title}`);
    button.addEventListener('click', () => onExplore(scenario.id));
    action.append(button);
    row.append(name, roots, ignition, outcome, action);
    body.append(row);
  });
}

/** These are planned positions, never online participants or synthesized AI activity. */
export function renderCrew(root) {
  const roster = root.querySelector('#crew-roster');
  roster.replaceChildren();
  CREW_ROLES.forEach((member, index) => {
    const card = element('article', undefined, 'g-crew-card');
    card.append(element('span', `0${index + 1}`, 'g-crew-number'), element('span', member.role, 'g-eyebrow'), element('h3', member.name), element('p', member.description), element('footer', `${member.vehicle.toUpperCase()} · HUMAN / AI PLANNED`));
    roster.append(card);
  });
}

/** Feature status comes from provider capabilities, never the appearance of a control. */
export function renderCapabilities(root, capabilities) {
  const list = root.querySelector('#mission-capabilities');
  list.replaceChildren();
  for (const capability of capabilities) {
    const item = element('span', undefined, 'g-capability');
    item.dataset.available = String(capability.available);
    item.title = capability.reason;
    const dot = element('i', undefined, 'g-dot green');
    dot.setAttribute('aria-hidden', 'true');
    item.append(dot, document.createTextNode(capability.label));
    if (!capability.available) item.append(element('small', 'UNAVAILABLE'));
    list.append(item);
  }
}
