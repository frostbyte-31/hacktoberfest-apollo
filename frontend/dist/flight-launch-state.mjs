import {ROLE_IDS} from './mission-live-provider.mjs';

export const FLIGHT_CREW_MODES=Object.freeze(['human','fallback','llm']);
/** The real /api/v1/missions contract. No mission or participant is invented here. */
export function prepareFlightLaunch({role='commander',crewModes,scenarioId='training'},discovery){
  const issues=[];
  if(!discovery||discovery.schemaVersion!==1||discovery.capabilities?.physicsLab!==true)issues.push('The physical flight laboratory is unavailable. Run make play with the verified native assets.');
  if(role!==null&&!ROLE_IDS.includes(role))issues.push('Select one of the three Apollo crew positions, or observe.');
  if(!crewModes||Object.keys(crewModes).length!==3||!ROLE_IDS.every(id=>Object.hasOwn(crewModes,id)&&FLIGHT_CREW_MODES.includes(crewModes[id])))issues.push('Choose Human, Assistant or Model AI for exactly three crew seats.');
  if(!discovery?.scenarios?.some(item=>item.id===scenarioId))issues.push('Select an available laboratory scenario.');
  if(crewModes&&Object.values(crewModes).includes('llm')&&discovery?.capabilities?.llmConfigured!==true)issues.push('Model AI requires a configured server provider. Choose a deterministic Assistant to play without an AI service.');
  if(crewModes&&Object.values(crewModes).includes('fallback')&&discovery?.capabilities?.deterministicCrew!==true)issues.push('Deterministic crew assistance is unavailable.');
  if(role&&crewModes?.[role]!=='human')issues.push('Your selected crew position must be Human.');
  return Object.freeze({canStart:issues.length===0,issues:Object.freeze(issues),request:issues.length?null:Object.freeze({scenarioId,name:role===null?'Mission observer':role==='commander'?'Flight commander':role==='lunar-module-pilot'?'LM pilot':'CM pilot',role,crewModes:Object.freeze({...crewModes})})});
}
