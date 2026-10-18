import {createMissionRenderer} from './mission-3d.mjs';
import {CREW_ROLES,createCrewSetup,validateCrewSetup} from './crew-setup.mjs';
import {readCrewSetup,saveCrewSetup,discoverCrewCapabilities} from './crew-session.mjs';
import {MissionLiveProvider,ROLE_IDS} from './mission-live-provider.mjs';
import {prepareFlightLaunch} from './flight-launch-state.mjs';
const $=id=>document.getElementById(id),roleIds={CDR:'commander',LMP:'lunar-module-pilot',CMP:'command-module-pilot'};
let storage;try{storage=sessionStorage;}catch{storage={getItem:()=>null,setItem:()=>{throw new Error('Storage unavailable');}};}
let setup=readCrewSetup(storage),experience='procedures',preset=setup.humanParticipation==='shared-device'?'human-crew':'solo',capabilities={localHumanStations:false,aiCrew:false,networkHumanStations:false},discovery=null,pending=false,launching=false,message='Connecting to the local mission service…';
let modes={commander:'human','lunar-module-pilot':'fallback','command-module-pilot':'fallback'};
const provider=new MissionLiveProvider({storage});
let renderer=null;try{renderer=createMissionRenderer($('launch-canvas'));}catch{$('launch-graphics-note').textContent='3D preview is unavailable. Crew setup remains accessible.';}
const draw=()=>renderer?.draw({mode:'historical-illustration'});draw();new ResizeObserver(draw).observe($('launch-canvas'));window.addEventListener('pagehide',()=>renderer?.dispose());
function render(){
  const lab=experience==='lab',role=$('launch-role').value||null;
  const result=lab?prepareFlightLaunch({role,crewModes:modes,scenarioId:$('launch-scenario').value},discovery):validateCrewSetup(setup,capabilities);
  for(const seat of CREW_ROLES){const select=$(`crew-${seat.role}`);select.value=lab?modes[roleIds[seat.role]]:'human';select.disabled=launching||(!lab)||(roleIds[seat.role]===role);for(const option of select.options){if(option.value==='llm')option.disabled=discovery?.capabilities.llmConfigured!==true;}}
  document.querySelectorAll('[data-crew-preset]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.crewPreset===preset));button.disabled=launching||(button.dataset.crewPreset==='commander-ai'&&discovery?.capabilities.llmConfigured!==true);button.title=button.dataset.crewPreset==='commander-ai'&&discovery?.capabilities.llmConfigured!==true?'Configure a server model provider to enable Model AI.':'';});
  $('ai-provider-status').textContent=discovery?.capabilities.llmConfigured===true?'Model provider configured. AI commands use the server validator.':'Model AI is not configured. Deterministic Assistants are available in the 3D lab.';
  document.querySelectorAll('[data-experience]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.experience===experience));button.disabled=launching;});
  $('lab-options').hidden=!lab;
  $('preset-description').textContent=lab?'Humans join in separate tabs on this local server. Assistants are deterministic; Model AI uses a configured provider.':result.description;
  $('experience-description').textContent=lab?'Server-owned educational flight from synthetic initial conditions. This is separate from Apollo flight procedures.':'Historical lunar-orbit checklist training. Flight dynamics are not connected.';
  $('launch-mission').disabled=pending||launching||!result.canStart;
  $('launch-reconnect').hidden=pending||(lab?Boolean(discovery?.capabilities.physicsLab):capabilities.localHumanStations);
  $('launch-connection').textContent=pending?'CHECKING LOCAL MISSION SERVICE':launching?'CREATING SHARED MISSION':result.canStart?(lab?'READY / EDUCATIONAL PHYSICS LAB':'READY / CHECKLIST TRAINING'):'CONFIGURATION NEEDS ATTENTION';
  const issues=result.issues.map(item=>typeof item==='string'?item:item.message);
  $('launch-issues').textContent=pending?message:result.canStart?(lab?(Object.values(modes).includes('llm')?'Model AI proposals use the server command validator. Real provider behavior depends on your configured service.':Object.values(modes).includes('fallback')?'Assistants use modern deterministic training logic. They are independent of original Apollo guidance.':'Invite the other human players after creating the mission. All three crew seats must be ready.'):(setup.humanParticipation==='shared-device'?'Pass this device to the indicated astronaut’s player at each step.':'You work all three crew stations. The checklist indicates who acts next.')):issues.join(' ');
  $('launch-connection').closest('.launch-availability').classList.toggle('blocked',!result.canStart);
  $('launch-mission').replaceChildren(document.createTextNode(launching?'Creating mission…':lab?'Create 3D flight laboratory':'Enter lunar orbit'),Object.assign(document.createElement('span'),{textContent:'↗'}));
  $('launch-start-note').textContent=lab?'Launch creates a shared lobby. Set human seats ready, then Start flight. No original AGC-controlled landing is claimed.':'Your first task: prepare Eagle and command the docking release. Earlier vehicle setup is a declared assumption.';
}
async function connect(){
  if(pending)return;pending=true;render();
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),5000);
  const results=await Promise.allSettled([fetch('./api/bootstrap',{cache:'no-store',signal:abort.signal}).then(async response=>{if(!response.ok)throw new Error('Procedure service unavailable.');capabilities=discoverCrewCapabilities(await response.json());}),provider.discover().then(data=>{discovery=data;$('launch-scenario').replaceChildren(...data.scenarios.map(s=>{const option=document.createElement('option');option.value=s.id;option.textContent=s.title;return option;}));})]);
  clearTimeout(timer);pending=false;message=results.filter(item=>item.status==='rejected').map(item=>item.reason.message).join(' ');render();
}
for(const button of document.querySelectorAll('[data-experience]'))button.addEventListener('click',()=>{experience=button.dataset.experience;render();});
for(const button of document.querySelectorAll('[data-crew-preset]'))button.addEventListener('click',()=>{
  preset=button.dataset.crewPreset;
  if(preset==='watch'){experience='lab';$('launch-role').value='';modes=Object.fromEntries(ROLE_IDS.map(id=>[id,'fallback']));}
  else if(preset==='commander-ai'){experience='lab';$('launch-role').value='commander';modes={commander:'human','lunar-module-pilot':'llm','command-module-pilot':'llm'};}
  else if(experience==='lab'){const role=$('launch-role').value||null;modes=Object.fromEntries(ROLE_IDS.map(id=>[id,preset==='human-crew'||id===role?'human':'fallback']));}
  else setup=createCrewSetup(preset);
  render();
});
for(const select of document.querySelectorAll('[data-crew-select]'))select.addEventListener('change',()=>{modes={...modes,[roleIds[select.dataset.crewSelect]]:select.value};preset='custom';render();});
$('launch-role').addEventListener('change',()=>{const role=$('launch-role').value;if(role)modes={...modes,[role]:'human'};else modes=Object.fromEntries(ROLE_IDS.map(id=>[id,'fallback']));preset='custom';render();});
$('launch-scenario').addEventListener('change',render);$('launch-reconnect').addEventListener('click',connect);
$('launch-mission').addEventListener('click',async()=>{
  if(launching||pending)return;
  if(experience==='procedures'){
    if(!validateCrewSetup(setup,capabilities).canStart)return;
    if(!saveCrewSetup(storage,setup)&&setup.humanParticipation!=='solo'){$('launch-issues').textContent='Browser session storage is blocked. Use Solo or enable session storage to carry the shared-device configuration.';return;}
    location.assign('./play.html');return;
  }
  const result=prepareFlightLaunch({role:$('launch-role').value||null,crewModes:modes,scenarioId:$('launch-scenario').value},discovery);if(!result.canStart)return;
  launching=true;render();try{await provider.create(result.request);location.assign('./mission.html');}catch(error){launching=false;render();$('launch-issues').textContent=error.message;}
});
render();connect();
