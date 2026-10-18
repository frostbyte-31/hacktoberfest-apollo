import {createCampaignViewer} from './campaign-view.mjs';
import {CREW_ROLES,createCrewSetup} from './crew-setup.mjs';
import {readCrewSetup,saveCrewSetup} from './crew-session.mjs';
import {MissionLiveProvider,ROLE_IDS} from './mission-live-provider.mjs';
import {prepareFlightLaunch} from './flight-launch-state.mjs';
const $=id=>document.getElementById(id),roleIds={CDR:'commander',LMP:'lunar-module-pilot',CMP:'command-module-pilot'};
let storage;try{storage=sessionStorage;}catch{storage={getItem:()=>null,setItem:()=>{throw new Error('Storage unavailable');}};}
let setup=readCrewSetup(storage),experience='procedures',preset=setup.humanParticipation==='shared-device'?'human-crew':'solo',discovery=null,pending=false,launching=false,message='Connecting to the local mission service…';
let modes={commander:'human','lunar-module-pilot':'fallback','command-module-pilot':'fallback'};
const provider=new MissionLiveProvider({storage});
let renderer=null;try{renderer=createCampaignViewer($('launch-canvas'));}catch{$('launch-graphics-note').textContent='3D preview is unavailable. Crew setup remains accessible.';}
const draw=()=>renderer?.draw('earth-stack');draw();new ResizeObserver(draw).observe($('launch-canvas'));window.addEventListener('pagehide',event=>{if(!event.persisted)renderer?.dispose();});
function render(){
  const lab=experience==='lab',role=$('launch-role').value||null;
  const result=lab?prepareFlightLaunch({role,crewModes:modes,scenarioId:$('launch-scenario').value},discovery):{canStart:true,issues:[],description:preset==='watch'?'A guided historical tour, with verified AGC evidence inserts. No flight or AI crew commands run.':setup.humanParticipation==='shared-device'?'Your crew configuration carries to the selected undocking trainer. Historical chapters are a shared reference.':'Explore the chronological mission, then work all three stations in the undocking trainer.'};
  for(const seat of CREW_ROLES){const select=$(`crew-${seat.role}`);select.value=lab?modes[roleIds[seat.role]]:'human';select.disabled=launching||(!lab)||(roleIds[seat.role]===role);for(const option of select.options){if(option.value==='llm')option.disabled=discovery?.capabilities.llmConfigured!==true;}}
  document.querySelectorAll('[data-crew-preset]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.crewPreset===preset));button.disabled=launching||(button.dataset.crewPreset==='commander-ai'&&discovery?.capabilities.llmConfigured!==true);button.title=button.dataset.crewPreset==='commander-ai'&&discovery?.capabilities.llmConfigured!==true?'Configure a server model provider to enable Model AI.':'';});
  $('ai-provider-status').textContent=discovery?.capabilities.llmConfigured===true?'Model provider configured. AI commands use the server validator.':'Model AI is not configured. Deterministic Assistants are available in the 3D lab.';
  document.querySelectorAll('[data-experience]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.experience===experience));button.disabled=launching;});
  $('lab-options').hidden=!lab;
  $('preset-description').textContent=lab?'Humans join in separate tabs on this local server. Assistants are deterministic; Model AI uses a configured provider.':result.description;
  $('experience-description').textContent=lab?'Server-owned educational flight from synthetic initial conditions. This is separate from Apollo flight procedures.':'Earth parking orbit → lunar orbit → landing → direct Earth return. Sourced historical references and separate verified AGC recordings.';
  $('launch-mission').disabled=(lab&&pending)||launching||!result.canStart;
  $('launch-reconnect').hidden=!lab||pending||Boolean(discovery?.capabilities.physicsLab);
  $('launch-connection').textContent=lab&&pending?'CHECKING LOCAL MISSION SERVICE':launching?'CREATING SHARED MISSION':result.canStart?(lab?'READY / EDUCATIONAL PHYSICS LAB':'READY / HISTORICAL MISSION TOUR'):'CONFIGURATION NEEDS ATTENTION';
  const issues=result.issues.map(item=>typeof item==='string'?item:item.message);
  $('launch-issues').textContent=lab&&pending?message:result.canStart?(lab?(Object.values(modes).includes('llm')?'Model AI proposals use the server command validator. Real provider behavior depends on your configured service.':Object.values(modes).includes('fallback')?'Assistants use modern deterministic training logic. They are independent of original Apollo guidance.':'Invite the other human players after creating the mission. All three crew seats must be ready.'):'The historical tour runs without a live execution service. Full original-computer flight is unavailable.'):issues.join(' ');
  $('launch-connection').closest('.launch-availability').classList.toggle('blocked',!result.canStart);
  $('launch-mission').replaceChildren(document.createTextNode(launching?'Creating mission…':lab?'Create 3D flight laboratory':preset==='watch'?'Start guided historical tour':'Begin in Earth orbit'),Object.assign(document.createElement('span'),{textContent:'↗'}));
  $('launch-start-note').textContent=lab?'Launch creates a shared lobby. Set human seats ready, then Start flight. No original AGC-controlled landing is claimed.':'Start with the spacecraft in Earth parking orbit. The tour explains what happened, who controlled it, and which integrations are still missing.';
}
async function connect(){
  if(pending)return;pending=true;render();
  try{const data=await provider.discover();discovery=data;$('launch-scenario').replaceChildren(...data.scenarios.map(s=>{const option=document.createElement('option');option.value=s.id;option.textContent=s.title;return option;}));}
  catch(error){message=error.message;}
  finally{pending=false;render();}
}
for(const button of document.querySelectorAll('[data-experience]'))button.addEventListener('click',()=>{experience=button.dataset.experience;render();});
for(const button of document.querySelectorAll('[data-crew-preset]'))button.addEventListener('click',()=>{
  preset=button.dataset.crewPreset;
  if(preset==='watch'){experience='procedures';}
  else if(preset==='commander-ai'){experience='lab';$('launch-role').value='commander';modes={commander:'human','lunar-module-pilot':'llm','command-module-pilot':'llm'};}
  else if(experience==='lab'){const role=$('launch-role').value||null;modes=Object.fromEntries(ROLE_IDS.map(id=>[id,preset==='human-crew'||id===role?'human':'fallback']));}
  else setup=createCrewSetup(preset);
  render();
});
for(const select of document.querySelectorAll('[data-crew-select]'))select.addEventListener('change',()=>{modes={...modes,[roleIds[select.dataset.crewSelect]]:select.value};preset='custom';render();});
$('launch-role').addEventListener('change',()=>{const role=$('launch-role').value;if(role)modes={...modes,[role]:'human'};else modes=Object.fromEntries(ROLE_IDS.map(id=>[id,'fallback']));preset='custom';render();});
$('launch-scenario').addEventListener('change',render);$('launch-reconnect').addEventListener('click',connect);
$('launch-mission').addEventListener('click',async()=>{
  if(launching||(experience==='lab'&&pending))return;
  if(experience==='procedures'){
    // Historical reference navigation needs no persistent crew session.
    if(preset!=='watch')saveCrewSetup(storage,setup);
    location.assign(preset==='watch'?'./campaign.html?tour=1':'./campaign.html');return;
  }
  const result=prepareFlightLaunch({role:$('launch-role').value||null,crewModes:modes,scenarioId:$('launch-scenario').value},discovery);if(!result.canStart)return;
  launching=true;render();try{await provider.create(result.request);location.assign('./mission.html');}catch(error){launching=false;render();$('launch-issues').textContent=error.message;}
});
render();connect();
