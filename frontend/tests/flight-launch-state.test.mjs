import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareFlightLaunch} from '../dist/flight-launch-state.mjs';
const roles=['commander','lunar-module-pilot','command-module-pilot'];
const modes=(kind='fallback')=>Object.fromEntries(roles.map(id=>[id,kind]));
const caps={schemaVersion:1,capabilities:{physicsLab:true,deterministicCrew:true,llmConfigured:false},scenarios:[{id:'training'},{id:'low-fuel'}]};
test('human commander plus assistants maps exactly to implemented mission-create contract',()=>{
  const crewModes={...modes(),commander:'human'},before=JSON.stringify(crewModes);
  const result=prepareFlightLaunch({crewModes},caps);
  assert.equal(result.canStart,true);assert.deepEqual(result.request,{scenarioId:'training',name:'Flight commander',role:'commander',crewModes});assert.equal(JSON.stringify(crewModes),before);assert.ok(Object.isFrozen(result.request.crewModes));
});
test('observer can host exactly three deterministic seats without a fourth crew member',()=>{
  const result=prepareFlightLaunch({role:null,crewModes:modes()},caps);assert.equal(result.canStart,true);assert.equal(result.request.role,null);assert.equal(Object.keys(result.request.crewModes).length,3);
});
test('all-human lab permits separate browser joins and assigns creator to selected seat',()=>{
  const result=prepareFlightLaunch({role:'lunar-module-pilot',crewModes:modes('human')},caps);assert.equal(result.canStart,true);assert.equal(result.request.role,'lunar-module-pilot');
});
test('LLM choices require actual provider flag; fallback is never counted as model AI',()=>{
  const data={role:null,crewModes:modes('llm')};assert.equal(prepareFlightLaunch(data,caps).canStart,false);assert.equal(prepareFlightLaunch(data,{...caps,capabilities:{...caps.capabilities,llmConfigured:true}}).canStart,true);assert.equal(prepareFlightLaunch({role:null,crewModes:modes()},caps).canStart,true);
});
test('missing native plant, missing assist support and unknown scenarios block creation',()=>{
  const data={role:null,crewModes:modes()};for(const capabilities of [{...caps.capabilities,physicsLab:false},{...caps.capabilities,deterministicCrew:false}])assert.equal(prepareFlightLaunch(data,{...caps,capabilities}).canStart,false);assert.equal(prepareFlightLaunch({...data,scenarioId:'apollo-11-history'},caps).canStart,false);
});
test('unknown and additional crew seats, unsupported modes and nonhuman creator are rejected',()=>{
  for(const crewModes of [{...modes(),observer:'human'},{commander:'human'},modes('AI'),modes()])assert.equal(prepareFlightLaunch({crewModes},caps).canStart,false);assert.equal(prepareFlightLaunch({role:'Eagle',crewModes:modes('human')},caps).canStart,false);
});
