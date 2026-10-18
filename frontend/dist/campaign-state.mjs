/**
 * Historical chapter navigation, independent of spacecraft execution.
 * Reviewing a chapter or playing a tutorial never completes a flight goal.
 * Broad lab capability flags are not evidence for a historical mission leg.
 * @typedef {import('./campaign-types.js').CampaignCatalog} CampaignCatalog
 * @typedef {import('./campaign-types.js').CampaignReviewState} CampaignReviewState
 * @typedef {import('./campaign-types.js').CampaignAvailabilityReport} CampaignAvailabilityReport
 */
export const CAMPAIGN_MODE = 'HISTORICAL MISSION REFERENCE';
export const CAMPAIGN_GOAL_IDS = Object.freeze(['lunar-orbit', 'lunar-landing', 'earth-return']);
export const CAMPAIGN_STAGE_IDS = Object.freeze([
  'earth-parking', 'tli', 'transposition-extraction', 'translunar-coast',
  'lunar-orbit-insertion', 'lunar-orbit', 'lm-preparation', 'undocking-inspection',
  'descent-orbit-insertion', 'powered-descent', 'lunar-surface', 'lunar-ascent',
  'rendezvous-docking', 'transearth-injection', 'transearth-coast', 'entry-splashdown',
]);
export const STAGE_CAPABILITIES = Object.freeze({
  'earth-parking': 'historicalEarthParkingOrbit',
  tli: 'historicalSaturnTli',
  'transposition-extraction': 'historicalTranspositionExtraction',
  'translunar-coast': 'historicalTranslunarCoast',
  'lunar-orbit-insertion': 'historicalLunarOrbitInsertion',
  'lunar-orbit': 'historicalLunarOrbit',
  'lm-preparation': 'historicalLmActivation',
  'undocking-inspection': 'historicalOrbitalUndocking',
  'descent-orbit-insertion': 'historicalDescentOrbitInsertion',
  'powered-descent': 'historicalAgcPoweredDescent',
  'lunar-surface': 'historicalLunarSurfaceOperations',
  'lunar-ascent': 'historicalLunarAscent',
  'rendezvous-docking': 'historicalRendezvousDocking',
  'transearth-injection': 'historicalTransearthInjection',
  'transearth-coast': 'historicalTransearthCoast',
  'entry-splashdown': 'historicalEarthEntryRecovery',
});
/**
 * Verified adapter scope after inspecting the implemented services. These are
 * full historical leg capabilities, not the separate lab's physicsLab,
 * multiplayer, authenticLanding, or bounded liveAuthenticAttitude booleans.
 * No retained trace or current endpoint establishes any complete leg here.
 */
export const VERIFIED_MISSION_CAPABILITIES = Object.freeze(Object.fromEntries(
  Object.values(STAGE_CAPABILITIES).map(capability => [capability, false]),
));
const stageGoals = Object.freeze(CAMPAIGN_STAGE_IDS.map((_, index) =>
  index < 6 ? 'lunar-orbit' : index < 11 ? 'lunar-landing' : 'earth-return'));
const text = value => typeof value === 'string' && value.trim().length > 0;
const listOfIds = value => Array.isArray(value) && value.every(text) && new Set(value).size === value.length;
const fail = message => { throw new Error(`Invalid Apollo campaign: ${message}`); };
const freeze = value => {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value).forEach(freeze); Object.freeze(value);
  }
  return value;
};
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

/** Validate structure and source references; historical interpretation is source-reviewed separately.
 * @param {unknown} catalog @returns {CampaignCatalog}
 */
export function validateCampaignCatalog(catalog) {
  if (!catalog || catalog.schemaVersion !== 1) fail('schema version');
  if (!Array.isArray(catalog.sources) || !catalog.sources.length) fail('source list');
  const sourceIds = new Set();
  for (const source of catalog.sources) {
    if (!source || !['id', 'title', 'url', 'locator'].every(key => text(source[key]))
        || sourceIds.has(source.id)) fail('source identity or citation');
    let url; try { url = new URL(source.url); } catch { fail('source URL'); }
    if (url.protocol !== 'https:' || !url.hostname || url.username || url.password) fail('source HTTPS URL');
    sourceIds.add(source.id);
  }
  if (!Array.isArray(catalog.goals) || catalog.goals.length !== 3
      || !Array.isArray(catalog.stages) || catalog.stages.length !== 16) fail('three goals and sixteen chronological stages');
  const stageIds = new Set();
  for (const [index, stage] of catalog.stages.entries()) {
    if (!stage || stage.id !== CAMPAIGN_STAGE_IDS[index] || stage.order !== index + 1
        || stage.goalId !== stageGoals[index] || stageIds.has(stage.id)) fail('stage chronology or goal mapping');
    if (!['title', 'getLabel', 'vehicle', 'configuration', 'computer', 'controlAuthority',
      'description', 'historicalAction'].every(key => text(stage[key]))) fail('stage reference or control authority');
    if (!listOfIds(stage.requiredCapabilities) || !stage.requiredCapabilities.length
        || !stage.requiredCapabilities.includes(STAGE_CAPABILITIES[stage.id])) fail('explicit historical stage capability');
    if (!listOfIds(stage.evidenceIds)) fail('partial evidence identities');
    if (!listOfIds(stage.sourceIds) || !stage.sourceIds.length
        || stage.sourceIds.some(id => !sourceIds.has(id))) fail('stage source reference');
    stageIds.add(stage.id);
  }
  for (const [index, goal] of catalog.goals.entries()) {
    if (!goal || goal.id !== CAMPAIGN_GOAL_IDS[index] || !text(goal.title) || !text(goal.summary)
        || !listOfIds(goal.stageIds)) fail('goal identity or description');
    const expected = catalog.stages.filter(stage => stage.goalId === goal.id).map(stage => stage.id);
    if (goal.stageIds.length !== expected.length || goal.stageIds.some((id, position) => id !== expected[position])) fail('goal stage coverage or order');
  }
  return catalog;
}

/**
 * No caller-supplied boolean can upgrade reference chapters into verified flight.
 * A future flight provider needs run-bound provenance and achieved outcomes; it
 * must integrate a new execution contract rather than reuse this navigation state.
 * @param {CampaignCatalog} catalog
 * @param {unknown} [_untrustedCapabilityClaims]
 * @returns {CampaignAvailabilityReport}
 */
export function assessMissionAvailability(catalog, _untrustedCapabilityClaims = undefined) {
  validateCampaignCatalog(catalog);
  const stages = catalog.stages.map(stage => ({
    id: stage.id, available: false, referenceAvailable: true,
    missingCapabilities: [...stage.requiredCapabilities],
    partialEvidenceIds: [...stage.evidenceIds],
    reason: 'No verified full historical flight execution is connected for this chapter.',
  }));
  const goals = catalog.goals.map(goal => ({
    id: goal.id, available: false, status: 'unavailable',
    missingCapabilities: [...new Set(stages.filter(stage => goal.stageIds.includes(stage.id))
      .flatMap(stage => stage.missingCapabilities))],
  }));
  return freeze({
    available: false, fullMissionAvailable: false, referenceAvailable: true,
    mode: CAMPAIGN_MODE,
    reason: 'The current services provide bounded original-AGC experiments and separate training modes. They do not execute a complete historical mission.',
    missingCapabilities: [...new Set(stages.flatMap(stage => stage.missingCapabilities))],
    stages, goals,
    stageAvailability: Object.fromEntries(stages.map(stage => [stage.id, stage])),
    goalAvailability: Object.fromEntries(goals.map(goal => [goal.id, goal])),
  });
}

const states = new WeakSet();
function stateFrom(catalog, cursor, reviewedStageIds) {
  const reviewed = new Set(reviewedStageIds);
  const state = freeze({
    schemaVersion: 1, mode: CAMPAIGN_MODE, catalog, cursor,
    currentStageId: catalog.stages[cursor].id, currentGoalId: catalog.stages[cursor].goalId,
    currentStage: catalog.stages[cursor],
    reviewedStageIds: catalog.stages.filter(stage => reviewed.has(stage.id)).map(stage => stage.id),
    stageStatuses: Object.fromEntries(catalog.stages.map(stage =>
      [stage.id, reviewed.has(stage.id) ? 'reference-reviewed' : 'reference-unreviewed'])),
    goalStatuses: Object.fromEntries(catalog.goals.map(goal => [goal.id, 'unavailable'])),
    missionCompleted: false, flightExecuted: false,
  });
  states.add(state); return state;
}
const assertState = state => { if (!state || !states.has(state)) fail('use a campaign navigation state'); };
function indexFor(state, stageId) {
  if (!text(stageId)) fail('stage selection');
  const index = state.catalog.stages.findIndex(stage => stage.id === stageId);
  if (index < 0) fail('unknown stage selection');
  return index;
}
/** Own and freeze the source copy, leaving the caller's catalog untouched.
 * @param {CampaignCatalog} catalog @returns {CampaignReviewState}
 */
export function createCampaignState(catalog) {
  validateCampaignCatalog(catalog);
  return stateFrom(freeze(structuredClone(catalog)), 0, []);
}
/** @param {CampaignReviewState} state @param {import('./campaign-types.js').CampaignStageId} stageId @returns {CampaignReviewState} */
export function selectCampaignStage(state, stageId) {
  assertState(state);
  const cursor = indexFor(state, stageId);
  return cursor === state.cursor ? state : stateFrom(state.catalog, cursor, state.reviewedStageIds);
}
/** @param {CampaignReviewState} state @returns {CampaignReviewState} */
export function nextCampaignStage(state) {
  assertState(state);
  return state.cursor === state.catalog.stages.length - 1 ? state
    : stateFrom(state.catalog, state.cursor + 1, state.reviewedStageIds);
}
/** @param {CampaignReviewState} state @returns {CampaignReviewState} */
export function previousCampaignStage(state) {
  assertState(state);
  return state.cursor === 0 ? state : stateFrom(state.catalog, state.cursor - 1, state.reviewedStageIds);
}
/** Reading can be recorded; it never operates a vehicle or marks a mission goal achieved.
 * @param {CampaignReviewState} state
 * @param {import('./campaign-types.js').CampaignStageId} [stageId]
 * @returns {CampaignReviewState}
 */
export function reviewCampaignStage(state, stageId = state?.currentStageId) {
  assertState(state); indexFor(state, stageId);
  return state.reviewedStageIds.includes(stageId) ? state
    : stateFrom(state.catalog, state.cursor, [...state.reviewedStageIds, stageId]);
}

/** Safe accessor for presentation code without treating IDs as object prototypes.
 * @param {CampaignReviewState} state
 * @param {import('./campaign-types.js').CampaignStageId} [stageId]
 * @returns {import('./campaign-types.js').CampaignReferenceStatus}
 */
export function campaignStageStatus(state, stageId = state?.currentStageId) {
  assertState(state); indexFor(state, stageId);
  return own(state.stageStatuses, stageId) ? state.stageStatuses[stageId] : 'reference-unreviewed';
}
