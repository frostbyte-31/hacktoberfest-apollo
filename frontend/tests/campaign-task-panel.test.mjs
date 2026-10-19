import test from 'node:test';
import assert from 'node:assert/strict';
import {createCampaignTaskPanel} from '../dist/campaign-task-panel.mjs';

class Element{
  constructor(tag,doc){this.tagName=tag;this.ownerDocument=doc;this.children=[];this.dataset={};this.listeners={};this.attributes={};this.hidden=false;this.disabled=false;this._text='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  setAttribute(name,value){this.attributes[name]=String(value);}
  addEventListener(name,listener){(this.listeners[name]??=[]).push(listener);}
  click(){if(!this.disabled&&!this.hidden)for(const listener of this.listeners.click??[])listener();}
}
const makeRoot=()=>{const doc={createElement(tag){return new Element(tag,this);}};return doc.createElement('section');};
const descendants=root=>[root,...root.children.flatMap(descendants)];
const button=(root,text)=>descendants(root).find(node=>node.tagName==='button'&&node.textContent===text);
const baseStatus={status:'ready',canOperate:true,complete:false,currentRun:false,reason:'Original P52 ready.',missingDependencies:[],receipt:null};
const stage=(id,evidenceIds=[])=>({id,title:id==='earth-parking'?'Earth parking orbit':'Historical stage',historicalAction:'Source-backed historical crew action.',evidenceIds});

test('task rendering and source inspection issue no computer commands or navigation',()=>{
  const root=makeRoot();let actions=0;
  const panel=createCampaignTaskPanel({root,onOperate:()=>actions++,onContinue:()=>actions++,onEvidence:()=>actions++});
  panel.update({stage:stage('earth-parking'),status:baseStatus,observation:{available:true},programs:{originalPrograms:[{softwareId:'Comanche055',program:'P52',symbol:'P52',file:'P51-P53.agc',line:120,listingUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html',scope:'Original alignment logic'}],missingSystems:[]}});
  assert.equal(actions,0);assert.match(root.textContent,/manual sextant/);assert.match(root.textContent,/No mission|requires original-computer observations/);assert.equal(button(root,'Open alignment station').disabled,false);assert.equal(button(root,'Inspect departure requirements →').hidden,true);
  assert.equal(descendants(root).find(node=>node.tagName==='a').rel,'noopener');
  button(root,'Open alignment station').click();assert.equal(actions,1);
});

test('saved local history cannot reveal a live-completion continuation',()=>{
  const root=makeRoot(),panel=createCampaignTaskPanel({root});
  panel.update({stage:stage('earth-parking'),status:{...baseStatus,complete:true,currentRun:false,receipt:{sessionId:'prior-session'}},observation:{available:true},savedCount:1});
  assert.equal(button(root,'Inspect departure requirements →').hidden,true);assert.match(root.textContent,/previous computer-task result/);assert.match(root.textContent,/local history/);assert.doesNotMatch(root.textContent,/Current run: prior-session/);
});

test('current verified P52 completion offers reference continuation, never departure ignition',()=>{
  const root=makeRoot();let continuations=0;const panel=createCampaignTaskPanel({root,onContinue:()=>continuations++});
  panel.update({stage:stage('earth-parking'),status:{...baseStatus,complete:true,currentRun:true,receipt:{sessionId:'live-1'}},observation:{available:true,snapshot:{status:'ready'}},savedCount:1});
  const next=button(root,'Inspect departure requirements →');assert.equal(next.hidden,false);assert.match(root.textContent,/Historical flight achieved: no/);assert.match(root.textContent,/required completion checkpoints/);next.click();assert.equal(continuations,1);
});

test('unavailable TLI never exposes original flight input or calls the crew exercise playable',()=>{
  const root=makeRoot(),panel=createCampaignTaskPanel({root});
  panel.update({stage:stage('tli'),status:{...baseStatus,status:'unavailable',canOperate:false,reason:'Original launch-vehicle execution is unavailable.'},observation:{available:true}});
  const controls=descendants(root).filter(node=>node.tagName==='button'&&!node.hidden&&!node.disabled);
  assert.deepEqual(controls.map(control=>control.textContent),['Inspect original software']);assert.match(root.textContent,/Original launch-vehicle execution is unavailable/);assert.match(root.textContent,/SOURCE \/ FLIGHT SYSTEMS REQUIRED/);
});

test('recorded original outputs open the evidence inspector without completing a maneuver',()=>{
  const root=makeRoot();let evidence=0;const panel=createCampaignTaskPanel({root,onEvidence:()=>evidence++});
  panel.update({stage:stage('powered-descent',['propulsion']),status:{...baseStatus,status:'unavailable',canOperate:false},observation:null});
  assert.match(root.textContent,/VERIFIED RECORDING \/ SEPARATE EXPERIMENT/);assert.match(root.textContent,/watching it does not fly/);assert.equal(button(root,'Open alignment station').hidden,true);button(root,'Inspect original recording').click();assert.equal(evidence,1);
});

test('missing source index and unavailable persistence remain explicit without substitute telemetry',()=>{
  const root=makeRoot(),panel=createCampaignTaskPanel({root});
  panel.update({stage:stage('earth-parking'),status:baseStatus,observation:null,storageAvailable:false});panel.sourceError('offline');
  assert.match(root.textContent,/source index unavailable: offline/);assert.match(root.textContent,/saving unavailable/);assert.doesNotMatch(root.textContent,/00000/);
});

test('a retained completion loses its live continuation when the provider disconnects',()=>{
  const root=makeRoot();let moves=0;const panel=createCampaignTaskPanel({root,onContinue:()=>moves++});
  panel.update({stage:stage('earth-parking'),status:{...baseStatus,complete:true,currentRun:true,receipt:{sessionId:'retained'}},observation:{available:true,error:'Connection lost',snapshot:{status:'ready'}},savedCount:1});
  assert.equal(button(root,'Inspect departure requirements →').hidden,true);button(root,'Inspect departure requirements →').click();assert.equal(moves,0);assert.doesNotMatch(root.textContent,/Current run: retained/);
});

test('polls preserve the reader’s expanded source excerpt rather than rebuilding it',()=>{
  const root=makeRoot(),panel=createCampaignTaskPanel({root}),programs={originalPrograms:[{softwareId:'comanche055',program:'P52',symbol:'PROG52',file:'P51-P53.agc',line:148,listingUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html',scope:'Original program',excerpt:'PROG52 TC PHASCHNG',sourceSha256:'a'.repeat(64)}],missingSystems:[]};
  const value={stage:stage('earth-parking'),status:baseStatus,observation:{available:true},programs};panel.update(value);const pre=descendants(root).find(node=>node.tagName==='pre');const details=descendants(root).find(node=>node.children.includes(pre));details.open=true;panel.update(value);assert.equal(descendants(root).find(node=>node.tagName==='pre'),pre);assert.equal(details.open,true);
});
