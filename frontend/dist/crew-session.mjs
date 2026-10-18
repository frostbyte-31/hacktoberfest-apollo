import {createCrewSetup,validateCrewSetup} from './crew-setup.mjs';

const KEY='apollo11.crew.v1';
export const CURRENT_CREW_CAPABILITIES=Object.freeze({localHumanStations:true,aiCrew:false,networkHumanStations:false});

/** Public browser-local configuration only. This is not backend crew identity. */
export function readCrewSetup(storage){
  try{const raw=storage.getItem(KEY);if(raw){const value=JSON.parse(raw);if(validateCrewSetup(value,CURRENT_CREW_CAPABILITIES).canStart)return value;}}catch{/* A blocked or invalid browser store never prevents solo play. */}
  return createCrewSetup('solo');
}
export function saveCrewSetup(storage,setup){
  if(!validateCrewSetup(setup,CURRENT_CREW_CAPABILITIES).canStart)throw new Error('This crew configuration cannot be run by the current mission service.');
  try{storage.setItem(KEY,JSON.stringify(setup));return true;}catch{return false;}
}

/** Map only the implemented procedure service; future AI needs a real adapter. */
export function discoverCrewCapabilities(bootstrap){
  const service=bootstrap?.procedureCapabilities;
  const ready=bootstrap?.procedureEnabled===true&&service?.mode==='INTERACTIVE PROCEDURE TRAINER'&&service.originalAgc===false&&service.flightPhysics===false;
  return Object.freeze({localHumanStations:ready,aiCrew:false,networkHumanStations:false});
}
