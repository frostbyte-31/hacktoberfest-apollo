import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CURRENT_CREW_CAPABILITIES, discoverCrewCapabilities, readCrewSetup, saveCrewSetup,
} from '../dist/crew-session.mjs';
import {
  createCrewSetup, updateCrewAssignment, updateHumanParticipation,
} from '../dist/crew-setup.mjs';

const KEY = 'apollo11.crew.v1';
const disabled = {localHumanStations:false,aiCrew:false,networkHumanStations:false};
const enabled = {localHumanStations:true,aiCrew:false,networkHumanStations:false};
const bootstrap = () => ({
  liveEnabled:true,
  procedureEnabled:true,
  procedureCapabilities:{
    mode:'INTERACTIVE PROCEDURE TRAINER',crewReports:true,modeledSelectors:true,
    modeledMechanicalRelease:true,originalAgc:false,flightPhysics:false,
    sensorReadback:false,historicalMissionClock:false,
  },
});
const store = initial => {
  const data = new Map(initial === undefined ? [] : [[KEY,initial]]);
  const reads = [], writes = [];
  return {
    data, reads, writes,
    getItem(key) { reads.push(key);return data.get(key) ?? null; },
    setItem(key,value) { writes.push([key,value]);data.set(key,value); },
  };
};

test('crew discovery recognizes the implemented local procedure classification without enabling AI or network sessions', () => {
  const caps = discoverCrewCapabilities(bootstrap());
  assert.deepEqual(caps,enabled);
  assert.equal(Object.isFrozen(caps),true);
  assert.throws(() => { caps.aiCrew = true; },TypeError);
  assert.deepEqual(CURRENT_CREW_CAPABILITIES,enabled);
  assert.equal(Object.isFrozen(CURRENT_CREW_CAPABILITIES),true);
});

test('native attitude availability and arbitrary AI flags never announce a crew adapter', () => {
  for (const value of [
    {liveEnabled:true},
    {liveEnabled:true,aiCrew:true,networkHumanStations:true},
    {procedureEnabled:true,aiCrew:true},
    {procedureEnabled:true,procedureCapabilities:{mode:'LIVE AGC EXECUTION',aiCrew:true}},
  ]) assert.deepEqual(discoverCrewCapabilities(value),disabled);
  const actual = bootstrap();
  Object.assign(actual,{aiCrew:true,networkHumanStations:true});
  Object.assign(actual.procedureCapabilities,{aiCrew:true,networkHumanStations:true});
  assert.deepEqual(discoverCrewCapabilities(actual),enabled);
});

test('replay-disabled and malformed discovery responses cannot enable local controls', () => {
  for (const value of [null,undefined,{},[],true,'INTERACTIVE PROCEDURE TRAINER']) {
    assert.deepEqual(discoverCrewCapabilities(value),disabled);
  }
  for (const procedureEnabled of [false,undefined,null,'true',1]) {
    assert.deepEqual(discoverCrewCapabilities({...bootstrap(),procedureEnabled}),disabled);
  }
  const replay = {...bootstrap(),liveEnabled:false,procedureEnabled:false,token:null};
  assert.deepEqual(discoverCrewCapabilities(replay),disabled);
});

test('only the explicit procedure mode and boolean scope flags satisfy discovery', () => {
  for (const mode of [undefined,'LIVE AGC EXECUTION','VERIFIED RECORDED EXECUTION','interactive procedure trainer']) {
    const value = bootstrap();value.procedureCapabilities.mode = mode;
    assert.deepEqual(discoverCrewCapabilities(value),disabled);
  }
  for (const field of ['originalAgc','flightPhysics']) {
    for (const invalid of [undefined,null,true,0,'false']) {
      const value = bootstrap();value.procedureCapabilities[field] = invalid;
      assert.deepEqual(discoverCrewCapabilities(value),disabled);
    }
  }
});

test('valid solo and same-device human configurations restore exactly the saved public seats', () => {
  for (const preset of ['solo','human-crew']) {
    const setup = createCrewSetup(preset), storage = store(JSON.stringify(setup));
    assert.deepEqual(readCrewSetup(storage),setup);
    assert.deepEqual(storage.reads,[KEY]);
    assert.deepEqual(storage.writes,[],'A read must not mutate persisted configuration or start a session.');
  }
});

test('missing or invalid JSON falls back to playable solo configuration without overwriting storage', () => {
  for (const raw of [undefined,'','{','null','[]','true','42','"solo"']) {
    const storage = store(raw);
    assert.deepEqual(readCrewSetup(storage),createCrewSetup('solo'));
    assert.deepEqual(storage.writes,[]);
  }
});

test('malformed, extra and obsolete saved configuration is rejected as a whole', () => {
  const setup = createCrewSetup('human-crew');
  for (const value of [
    {...setup,schemaVersion:2},
    {...setup,humanParticipation:'online'},
    {...setup,endpoint:'/pretend-ai'},
    {...setup,assignments:{CDR:'human',LMP:'human'}},
    {...setup,assignments:{...setup.assignments,CAPCOM:'human'}},
    {...setup,assignments:{...setup.assignments,CMP:'bot'}},
    {assignments:setup.assignments},
  ]) {
    const storage = store(JSON.stringify(value));
    assert.deepEqual(readCrewSetup(storage),createCrewSetup('solo'));
    assert.deepEqual(storage.writes,[]);
  }
});

test('stored AI and remote crew choices never reactivate unsupported execution modes', () => {
  const solo = createCrewSetup();
  for (const setup of [
    createCrewSetup('commander-ai'),
    updateCrewAssignment(solo,'CDR','ai'),
    updateCrewAssignment(createCrewSetup('commander-ai'),'CDR','ai'),
    updateHumanParticipation(solo,'network'),
  ]) assert.deepEqual(readCrewSetup(store(JSON.stringify(setup))),solo);
});

test('blocked, absent and broken browser storage never prevents solo play', () => {
  for (const storage of [
    undefined,null,{},
    {getItem() { throw new Error('Storage disabled'); }},
  ]) assert.deepEqual(readCrewSetup(storage),createCrewSetup('solo'));
});

test('saving uses only the versioned public crew key and round-trips the selected local mode', () => {
  const setup = createCrewSetup('human-crew'), storage = store();
  assert.equal(saveCrewSetup(storage,setup),true);
  assert.deepEqual(storage.writes,[[KEY,JSON.stringify(setup)]]);
  assert.deepEqual(JSON.parse(storage.data.get(KEY)),setup);
  assert.deepEqual(readCrewSetup(storage),setup);
});

test('unsupported or malformed saves fail before touching persisted configuration', () => {
  const storage = store(JSON.stringify(createCrewSetup()));
  for (const setup of [
    null,{},createCrewSetup('commander-ai'),
    updateHumanParticipation(createCrewSetup(),'network'),
    {...createCrewSetup(),token:'must-not-persist'},
  ]) assert.throws(() => saveCrewSetup(storage,setup),/cannot be run/);
  assert.deepEqual(storage.writes,[]);
  assert.deepEqual(readCrewSetup(storage),createCrewSetup());
});

test('a storage write failure is reported without changing the chosen setup or preventing an in-memory session', () => {
  const setup = createCrewSetup('human-crew'), before = JSON.stringify(setup);
  let attempted;
  const storage = {
    setItem(key,value) { attempted = [key,value];throw new Error('Quota exceeded'); },
  };
  assert.equal(saveCrewSetup(storage,setup),false);
  assert.deepEqual(attempted,[KEY,before]);
  assert.equal(JSON.stringify(setup),before);
  assert.equal(setup.humanParticipation,'shared-device');
  assert.equal(saveCrewSetup(undefined,setup),false);
  assert.equal(saveCrewSetup({},setup),false);
});
