import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CREW_ROLES, CREW_PRESETS, createCrewSetup, updateCrewAssignment,
  updateHumanParticipation, getCrewRoster, validateCrewSetup,
} from '../dist/crew-setup.mjs';

test('the crew contains exactly the historical three seats with Collins aboard Columbia', () => {
  assert.deepEqual(CREW_ROLES.map(({role,name,vehicle}) => ({role,name,vehicle})), [
    {role:'CDR',name:'Neil Armstrong',vehicle:'Eagle'},
    {role:'LMP',name:'Buzz Aldrin',vehicle:'Eagle'},
    {role:'CMP',name:'Michael Collins',vehicle:'Columbia'},
  ]);
  assert.ok(Object.isFrozen(CREW_ROLES));
  assert.ok(CREW_ROLES.every(Object.isFrozen));
});

test('solo is a playable local configuration with no AI or network claim', () => {
  const result = validateCrewSetup(createCrewSetup());
  assert.equal(result.valid, true); assert.equal(result.canStart, true);
  assert.equal(result.humanCount, 3); assert.equal(result.aiCount, 0);
  assert.equal(result.networkMultiplayer, false);
  assert.match(result.description, /One person switches/);
  assert.deepEqual(result.issues, []);
});

test('the human crew preset explicitly shares one device rather than inventing multiplayer', () => {
  const setup = createCrewSetup('human-crew');
  const result = validateCrewSetup(setup);
  assert.equal(setup.humanParticipation, 'shared-device');
  assert.equal(result.canStart, true); assert.equal(result.networkMultiplayer, false);
  assert.match(result.description, /share this device/);
});

test('an AI preset configures seats but stays blocked without verified AI support', () => {
  const setup = createCrewSetup('commander-ai');
  assert.equal(setup.assignments.CDR, 'human');
  assert.deepEqual(getCrewRoster(setup).map(seat => seat.participant), ['human','ai','ai']);
  const result = validateCrewSetup(setup);
  assert.equal(result.valid, true); assert.equal(result.canStart, false);
  assert.equal(result.aiCount, 2);
  assert.deepEqual(result.issues.map(issue => issue.code), ['ai-unavailable']);
  assert.equal(validateCrewSetup(setup, {aiCrew:true}).canStart, true);
});

test('all AI is rejected by current capabilities and requires explicit service support', () => {
  const setup = updateCrewAssignment(createCrewSetup('commander-ai'), 'CDR', 'ai');
  assert.equal(validateCrewSetup(setup).canStart, false);
  assert.equal(validateCrewSetup(setup, {aiCrew:'true'}).canStart, false);
  const result = validateCrewSetup(setup, {aiCrew:true,localHumanStations:false});
  assert.equal(result.canStart, true); assert.equal(result.humanCount, 0);
  assert.equal(result.aiCount, 3); assert.equal(result.networkMultiplayer, false);
});

test('network humans are gated separately from same-device humans and AI', () => {
  const setup = updateHumanParticipation(createCrewSetup(), 'network');
  assert.equal(validateCrewSetup(setup).canStart, false);
  assert.equal(validateCrewSetup(setup, {networkHumanStations:1}).canStart, false);
  const ready = validateCrewSetup(setup, {networkHumanStations:true,localHumanStations:false});
  assert.equal(ready.canStart, true); assert.equal(ready.networkMultiplayer, true);
  const mixed = updateCrewAssignment(setup, 'LMP', 'ai');
  assert.deepEqual(validateCrewSetup(mixed).issues.map(issue => issue.code), ['network-human-unavailable','ai-unavailable']);
});

test('disabled local station capability prevents local play without disabling a verified network mode', () => {
  assert.equal(validateCrewSetup(createCrewSetup(), {localHumanStations:false}).canStart, false);
  assert.equal(validateCrewSetup(createCrewSetup(), {localHumanStations:'true'}).canStart, false);
  assert.equal(validateCrewSetup(createCrewSetup(), {localHumanStations:true}).canStart, true);
});

test('assignments are immutable and updates cannot mutate preset or previous configuration', () => {
  const original = createCrewSetup();
  const changed = updateCrewAssignment(original, 'CMP', 'ai');
  assert.equal(original.assignments.CMP, 'human'); assert.equal(changed.assignments.CMP, 'ai');
  assert.equal(CREW_PRESETS[0].setup.assignments.CMP, 'human');
  assert.ok(Object.isFrozen(changed)); assert.ok(Object.isFrozen(changed.assignments));
  assert.throws(() => { changed.assignments.CMP = 'human'; }, TypeError);
  assert.ok(Object.isFrozen(validateCrewSetup(changed).roster[0]));
});

test('missing, extra, inherited and malformed role assignments fail closed', () => {
  const valid = createCrewSetup();
  const malformed = [
    null, [], {}, { ...valid, schemaVersion:2 }, { ...valid, humanParticipation:'online' },
    { ...valid, assignments:{ CDR:'human',LMP:'human' } },
    { ...valid, assignments:{ ...valid.assignments, CAPCOM:'human' } },
    { ...valid, assignments:{ ...valid.assignments, CMP:'bot' } },
    { ...valid, assignments:Object.create(valid.assignments) },
    { ...valid, endpoint:'/pretend-ai' },
  ];
  for (const setup of malformed) {
    const result = validateCrewSetup(setup, {aiCrew:true,networkHumanStations:true});
    assert.equal(result.valid, false); assert.equal(result.canStart, false);
    assert.deepEqual(result.roster, []);
    assert.equal(result.issues[0].code, 'invalid-configuration');
  }
});

test('unknown presets, role names and participant values cannot create extra seats', () => {
  const setup = createCrewSetup();
  assert.throws(() => createCrewSetup('__proto__'), /Unknown crew preset/);
  assert.throws(() => updateCrewAssignment(setup, 'CAPCOM', 'human'), /Invalid crew seat/);
  assert.throws(() => updateCrewAssignment(setup, '__proto__', 'human'), /Invalid crew seat/);
  assert.throws(() => updateCrewAssignment(setup, 'CDR', 'AI'), /Invalid crew seat/);
  assert.throws(() => updateHumanParticipation(setup, 'remote'), /Invalid human participation/);
  assert.throws(() => getCrewRoster({}), /Invalid crew configuration/);
});

test('round-tripped public configuration preserves exactly three stable role identities', () => {
  const setup = JSON.parse(JSON.stringify(updateCrewAssignment(createCrewSetup(), 'LMP', 'ai')));
  assert.equal(validateCrewSetup(setup).valid, true);
  assert.deepEqual(getCrewRoster(setup).map(seat => seat.role), ['CDR','LMP','CMP']);
  assert.equal(Object.keys(setup.assignments).length, 3);
});
