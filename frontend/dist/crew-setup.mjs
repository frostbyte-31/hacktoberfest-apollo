/** @typedef {import('./crew-setup-types.d.ts').ApolloCrewRole} ApolloCrewRole */
/** @typedef {import('./crew-setup-types.d.ts').CrewParticipant} CrewParticipant */
/** @typedef {import('./crew-setup-types.d.ts').HumanParticipation} HumanParticipation */
/** @typedef {import('./crew-setup-types.d.ts').CrewSetup} CrewSetup */
/** @typedef {import('./crew-setup-types.d.ts').CrewSetupCapabilities} CrewSetupCapabilities */
/** @typedef {import('./crew-setup-types.d.ts').CrewSetupValidation} CrewSetupValidation */

/** @template T @param {T} value @returns {T} */
const freeze = value => {
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
};

/** Exactly three historical seats. Collins remains aboard Columbia. */
/** @type {readonly import('./crew-setup-types.d.ts').ApolloCrewSeat[]} */
export const CREW_ROLES = freeze([
  { role: 'CDR', title: 'Commander', name: 'Neil Armstrong', vehicle: 'Eagle' },
  { role: 'LMP', title: 'Lunar Module Pilot', name: 'Buzz Aldrin', vehicle: 'Eagle' },
  { role: 'CMP', title: 'Command Module Pilot', name: 'Michael Collins', vehicle: 'Columbia' },
]);

/** @type {ApolloCrewRole[]} */
const roles = ['CDR', 'LMP', 'CMP'];
const participants = ['human', 'ai'];
const participationModes = ['solo', 'shared-device', 'network'];
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
/** @param {unknown} value @returns {value is Record<string, any>} */
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);

/** @param {HumanParticipation} humanParticipation @param {CrewSetup['assignments']} assignments @returns {CrewSetup} */
function makeSetup(humanParticipation, assignments) {
  return freeze({ schemaVersion: 1, humanParticipation, assignments: { ...assignments } });
}

/** Presets configure seats; they do not enable unavailable capabilities. */
/** @type {readonly import('./crew-setup-types.d.ts').CrewPreset[]} */
export const CREW_PRESETS = freeze([
  {
    id: 'solo', label: 'Solo astronaut',
    description: 'One person switches among all three human crew stations on this device.',
    setup: makeSetup('solo', { CDR: 'human', LMP: 'human', CMP: 'human' }),
  },
  {
    id: 'human-crew', label: 'Human crew',
    description: 'Share this device and take turns at the three human crew stations.',
    setup: makeSetup('shared-device', { CDR: 'human', LMP: 'human', CMP: 'human' }),
  },
  {
    id: 'commander-ai', label: 'Commander + AI crew',
    description: 'A human commander with two AI seats; requires a verified AI crew service.',
    setup: makeSetup('solo', { CDR: 'human', LMP: 'ai', CMP: 'ai' }),
  },
]);

/**
 * @param {unknown} value
 * @returns {asserts value is CrewSetup}
 */
function assertSetup(value) {
  if (!record(value) || Object.keys(value).length !== 3
    || !own(value, 'schemaVersion') || value.schemaVersion !== 1
    || !own(value, 'humanParticipation') || !participationModes.includes(value.humanParticipation)
    || !own(value, 'assignments') || !record(value.assignments)
    || Object.keys(value.assignments).length !== roles.length
    || roles.some(role => !own(value.assignments, role) || !participants.includes(value.assignments[role]))) {
    throw new TypeError('Invalid crew configuration: exactly CDR, LMP and CMP must be assigned human or AI.');
  }
}

/** @param {import('./crew-setup-types.d.ts').CrewPresetId} [presetId] @returns {CrewSetup} */
export function createCrewSetup(presetId = 'solo') {
  const preset = CREW_PRESETS.find(item => item.id === presetId);
  if (!preset) throw new TypeError('Unknown crew preset.');
  return makeSetup(preset.setup.humanParticipation, preset.setup.assignments);
}

/** @param {CrewSetup} setup @param {ApolloCrewRole} role @param {CrewParticipant} participant @returns {CrewSetup} */
export function updateCrewAssignment(setup, role, participant) {
  assertSetup(setup);
  if (!roles.includes(role) || !participants.includes(participant)) throw new TypeError('Invalid crew seat or participant.');
  return makeSetup(setup.humanParticipation, { ...setup.assignments, [role]: participant });
}

/** @param {CrewSetup} setup @param {HumanParticipation} humanParticipation @returns {CrewSetup} */
export function updateHumanParticipation(setup, humanParticipation) {
  assertSetup(setup);
  if (!participationModes.includes(humanParticipation)) throw new TypeError('Invalid human participation mode.');
  return makeSetup(humanParticipation, setup.assignments);
}

/** @param {CrewSetup} setup @returns {readonly import('./crew-setup-types.d.ts').CrewRosterSeat[]} */
export function getCrewRoster(setup) {
  assertSetup(setup);
  return freeze(CREW_ROLES.map(seat => ({ ...seat, participant: setup.assignments[seat.role] })));
}

/**
 * Local human station switching is the existing default. AI and network humans
 * require explicit boolean true from a verified adapter. This is configuration
 * validation, not a claim that a backend session or participant has been started.
 * @param {unknown} setup
 * @param {CrewSetupCapabilities} [capabilities]
 * @returns {CrewSetupValidation}
 */
export function validateCrewSetup(setup, capabilities = {}) {
  try { assertSetup(setup); }
  catch {
    return freeze({
      valid: false, canStart: false, classification: 'LOCAL CREW CONFIGURATION',
      humanCount: 0, aiCount: 0, roster: [], networkMultiplayer: false,
      description: 'Choose a valid assignment for each of the three Apollo 11 crew stations.',
      issues: [{ code: 'invalid-configuration', message: 'Exactly CDR, LMP and CMP must be assigned human or AI.' }],
    });
  }
  const roster = getCrewRoster(setup);
  const humanCount = roster.filter(seat => seat.participant === 'human').length;
  const aiCount = roster.length - humanCount;
  const caps = record(capabilities) ? capabilities : {};
  /** @type {import('./crew-setup-types.d.ts').CrewSetupIssue[]} */
  const issues = [];
  if (humanCount && setup.humanParticipation === 'network' && caps.networkHumanStations !== true) {
    issues.push({ code: 'network-human-unavailable', message: 'Network crew sessions are unavailable. Use this device to share or switch human stations.' });
  }
  if (humanCount && setup.humanParticipation !== 'network'
    && own(caps, 'localHumanStations') && caps.localHumanStations !== true) {
    issues.push({ code: 'local-human-unavailable', message: 'Local human crew controls are unavailable.' });
  }
  if (aiCount && caps.aiCrew !== true) {
    issues.push({ code: 'ai-unavailable', message: 'AI crew execution is unavailable. Assign these seats to humans to play locally.' });
  }
  const humanDescription = setup.humanParticipation === 'solo'
    ? 'One person switches among the human stations on this device.'
    : setup.humanParticipation === 'shared-device'
      ? 'Human crew members share this device and take turns at their stations.'
      : 'Separate-device human crew requires a verified network session.';
  return freeze({
    valid: true, canStart: issues.length === 0, classification: 'LOCAL CREW CONFIGURATION',
    humanCount, aiCount, roster, issues,
    networkMultiplayer: humanCount > 0 && setup.humanParticipation === 'network' && caps.networkHumanStations === true,
    description: `${humanCount ? humanDescription : 'All three seats are assigned to AI.'}${aiCount ? ` ${aiCount} AI ${aiCount === 1 ? 'seat requires' : 'seats require'} a verified AI crew service.` : ''}`,
  });
}
