import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  CAMPAIGN_MODE, CAMPAIGN_STAGE_IDS, CAMPAIGN_GOAL_IDS, STAGE_CAPABILITIES,
  VERIFIED_MISSION_CAPABILITIES, validateCampaignCatalog, assessMissionAvailability,
  createCampaignState, selectCampaignStage, nextCampaignStage, previousCampaignStage,
  reviewCampaignStage, campaignStageStatus,
} from '../dist/campaign-state.mjs';

function catalog() {
  const stages = CAMPAIGN_STAGE_IDS.map((id, index) => ({
    id, order: index + 1,
    goalId: index < 6 ? 'lunar-orbit' : index < 11 ? 'lunar-landing' : 'earth-return',
    title: id, getLabel: 'Historical GET reference', vehicle: 'Historical vehicle',
    configuration: 'Reference configuration', computer: 'Reference computer',
    controlAuthority: 'Crew and source-described control system',
    description: 'Historical chapter description.', historicalAction: 'Source-described crew action.',
    requiredCapabilities: [STAGE_CAPABILITIES[id]], evidenceIds: [], sourceIds: ['mission-report'],
  }));
  return {schemaVersion: 1, sources: [{id: 'mission-report', title: 'NASA Apollo 11 report',
    url: 'https://www.nasa.gov/apollo11/', locator: 'Mission sequence'}],
  goals: CAMPAIGN_GOAL_IDS.map(id => ({id, title: id, summary: 'Historical goal.',
    stageIds: stages.filter(stage => stage.goalId === id).map(stage => stage.id)})), stages};
}

test('the shipped source-backed catalog integrates with the strict navigation contract', () => {
  const shipped = JSON.parse(readFileSync(new URL('../dist/data/apollo-campaign.json', import.meta.url), 'utf8'));
  assert.equal(validateCampaignCatalog(shipped), shipped);
  const state = createCampaignState(shipped), report = assessMissionAvailability(shipped);
  assert.equal(state.currentStageId, 'earth-parking');
  assert.equal(shipped.stages.at(-1).id, 'entry-splashdown');
  assert.deepEqual(shipped.goals.map(goal => goal.stageIds.length), [6, 5, 5]);
  assert.equal(report.missingCapabilities.length, 16); assert.equal(report.available, false);
});

test('campaign starts in Earth parking orbit with three unachieved flight goals', () => {
  const state = createCampaignState(catalog());
  assert.equal(state.currentStageId, 'earth-parking'); assert.equal(state.cursor, 0);
  assert.equal(state.mode, CAMPAIGN_MODE); assert.deepEqual(state.reviewedStageIds, []);
  assert.deepEqual(Object.values(state.goalStatuses), ['unavailable', 'unavailable', 'unavailable']);
  assert.equal(state.flightExecuted, false); assert.equal(state.missionCompleted, false);
});

test('catalog requires the whole historical order, ending in entry and splashdown', () => {
  const value = catalog(); [value.stages[1], value.stages[2]] = [value.stages[2], value.stages[1]];
  assert.throws(() => validateCampaignCatalog(value), /chronology/);
  const incorrectReturn = catalog(); incorrectReturn.stages[15].id = 'earth-orbit-capture';
  assert.throws(() => validateCampaignCatalog(incorrectReturn), /chronology/);
});

test('a goal cannot omit, duplicate, reorder or borrow stages', () => {
  for (const transform of [ids => ids.slice(1), ids => [...ids, ids[0]], ids => ids.toReversed(), ids => [...ids.slice(0, -1), 'lunar-surface']]) {
    const value = catalog(); value.goals[0].stageIds = transform(value.goals[0].stageIds);
    assert.throws(() => validateCampaignCatalog(value), /goal/);
  }
});

test('catalog requires source locators, unique citations and safe HTTPS references', () => {
  for (const url of ['http://www.nasa.gov/report', 'javascript:alert(1)', 'https://user:secret@www.nasa.gov/report']) {
    const value = catalog(); value.sources[0].url = url;
    assert.throws(() => validateCampaignCatalog(value), /HTTPS/);
  }
  const duplicate = catalog(); duplicate.sources.push({...duplicate.sources[0]});
  assert.throws(() => validateCampaignCatalog(duplicate), /source identity/);
  const missing = catalog(); missing.sources[0].locator = '';
  assert.throws(() => validateCampaignCatalog(missing), /citation/);
});

test('every chapter cites a known source and names its real control authority', () => {
  for (const transform of [stage => { stage.sourceIds = ['unknown']; }, stage => { stage.controlAuthority = ''; }, stage => { stage.historicalAction = null; }]) {
    const value = catalog(); transform(value.stages[0]);
    assert.throws(() => validateCampaignCatalog(value), /source reference|control authority/);
  }
});

test('full historical capability cannot be replaced by a broad landing-lab flag', () => {
  const value = catalog(); value.stages[9].requiredCapabilities = ['physicsLab'];
  assert.throws(() => validateCampaignCatalog(value), /historical stage capability/);
  const claims = {physicsLab: true, authenticLanding: true, authenticAGC: true, multiplayer: true};
  const result = assessMissionAvailability(catalog(), claims);
  assert.equal(result.available, false); assert.equal(result.fullMissionAvailable, false);
  assert.equal(result.missingCapabilities.length, 16);
  assert.equal(result.stageAvailability['powered-descent'].available, false);
});

test('unproven specific booleans also cannot unlock a mission without an execution contract', () => {
  const claims = Object.fromEntries(Object.keys(VERIFIED_MISSION_CAPABILITIES).map(key => [key, true]));
  const result = assessMissionAvailability(catalog(), claims);
  assert.equal(result.available, false);
  assert.ok(result.goals.every(goal => goal.status === 'unavailable'));
  assert.ok(result.stages.every(stage => !stage.available && stage.missingCapabilities.length));
  assert.ok(Object.values(VERIFIED_MISSION_CAPABILITIES).every(value => value === false));
});

test('partial original-AGC evidence remains inspectable without completing a leg', () => {
  const value = catalog(); value.stages[9].evidenceIds = ['propulsion'];
  const result = assessMissionAvailability(value);
  assert.deepEqual(result.stageAvailability['powered-descent'].partialEvidenceIds, ['propulsion']);
  assert.equal(result.stageAvailability['powered-descent'].available, false);
  assert.equal(result.referenceAvailable, true);
});

test('next and previous navigate reference chapters without recording execution', () => {
  const initial = createCampaignState(catalog());
  const next = nextCampaignStage(initial);
  assert.equal(next.currentStageId, 'tli'); assert.equal(initial.currentStageId, 'earth-parking');
  assert.equal(previousCampaignStage(next).currentStageId, 'earth-parking');
  assert.equal(previousCampaignStage(initial), initial);
  assert.deepEqual(next.reviewedStageIds, []); assert.equal(next.flightExecuted, false);
});

test('selection and chapter boundaries do not auto-review or complete anything', () => {
  const state = selectCampaignStage(createCampaignState(catalog()), 'entry-splashdown');
  assert.equal(state.cursor, 15); assert.equal(nextCampaignStage(state), state);
  assert.deepEqual(state.reviewedStageIds, []); assert.equal(state.missionCompleted, false);
  assert.throws(() => selectCampaignStage(state, '__proto__'), /unknown/);
  assert.throws(() => selectCampaignStage(state, 1), /selection/);
});

test('review means reference-reviewed, is idempotent, and preserves the selected chapter', () => {
  const state = createCampaignState(catalog());
  const reviewed = reviewCampaignStage(state);
  assert.equal(campaignStageStatus(reviewed), 'reference-reviewed');
  assert.equal(campaignStageStatus(state), 'reference-unreviewed');
  assert.equal(reviewCampaignStage(reviewed), reviewed);
  const later = reviewCampaignStage(reviewed, 'lunar-ascent');
  assert.equal(later.currentStageId, 'earth-parking');
  assert.deepEqual(later.reviewedStageIds, ['earth-parking', 'lunar-ascent']);
});

test('a perfect reference walkthrough never records a landing or full mission achievement', () => {
  let state = createCampaignState(catalog());
  for (const id of [...CAMPAIGN_STAGE_IDS].reverse()) state = reviewCampaignStage(state, id);
  assert.deepEqual(state.reviewedStageIds, CAMPAIGN_STAGE_IDS);
  assert.ok(Object.values(state.stageStatuses).every(status => status === 'reference-reviewed'));
  assert.ok(Object.values(state.goalStatuses).every(status => status === 'unavailable'));
  assert.equal(state.missionCompleted, false); assert.equal(state.flightExecuted, false);
});

test('source copy, navigation and availability reports are deeply immutable', () => {
  const value = catalog(), state = createCampaignState(value), result = assessMissionAvailability(value);
  value.stages[0].title = 'Caller mutation';
  assert.equal(state.currentStage.title, 'earth-parking'); assert.equal(Object.isFrozen(value), false);
  assert.throws(() => { state.currentStage.title = 'Invented flight'; }, TypeError);
  assert.throws(() => { state.reviewedStageIds.push('tli'); }, TypeError);
  assert.throws(() => { result.stageAvailability.tli.available = true; }, TypeError);
});

test('arbitrary objects cannot masquerade as a trusted navigation state', () => {
  assert.throws(() => nextCampaignStage({cursor: 0}), /navigation state/);
  assert.throws(() => reviewCampaignStage(null), /navigation state/);
});

test('unsupported versions and absent source or capability data fail closed', () => {
  const value = catalog(); value.schemaVersion = 2;
  assert.throws(() => createCampaignState(value), /schema/);
  const noSource = catalog(); noSource.sources = [];
  assert.throws(() => createCampaignState(noSource), /source list/);
  const noCapability = catalog(); noCapability.stages[0].requiredCapabilities = [];
  assert.throws(() => createCampaignState(noCapability), /capability/);
});
