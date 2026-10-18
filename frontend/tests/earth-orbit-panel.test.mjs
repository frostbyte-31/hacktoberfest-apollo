import test from 'node:test';
import assert from 'node:assert/strict';
import {createEarthOrbitPanel} from '../dist/earth-orbit-panel.mjs';
import {DSKY_KEYS,EARTH_ORBIT_MODE} from '../dist/earth-orbit-client.mjs';

/** Minimal DOM surface: interactions stay on the public panel API and actual controls. */
class Element {
  constructor(tag,doc){this.tagName=tag;this.ownerDocument=doc;this.children=[];this.attributes={};this.dataset={};this.style={};this.listeners={};this.className='';this._text='';this.disabled=false;this.hidden=false;this.classList={add:(name)=>{this.className=[...new Set([...this.className.split(' ').filter(Boolean),name])].join(' ');},toggle:(name,enabled)=>{const set=new Set(this.className.split(' ').filter(Boolean));if(enabled)set.add(name);else set.delete(name);this.className=[...set].join(' ');}};}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  setAttribute(name,value){this.attributes[name]=String(value);if(name.startsWith('data-'))this.dataset[name.slice(5).replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase())]=String(value);}
  addEventListener(name,listener){(this.listeners[name]??=[]).push(listener);}
  click(){if(!this.disabled)for(const listener of this.listeners.click??[])listener({target:this});}
}
class Document {
  constructor(){this.hidden=false;this.listeners={};}
  createElement(tag){return new Element(tag,this);}
  addEventListener(name,fn){this.listeners[name]=fn;}
  removeEventListener(name,fn){if(this.listeners[name]===fn)delete this.listeners[name];}
}
const all=root=>[root,...root.children.flatMap(all)];
const button=(root,label)=>all(root).find(el=>el.tagName==='button'&&el.textContent===label);
const key=(root,label)=>all(root).find(el=>el.dataset.cmcKey===label);
const output=(root,field)=>all(root).find(el=>el.dataset.cmcDisplay===field);
const response=value=>({ok:true,status:200,json:async()=>structuredClone(value)});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const frame=()=>({schemaVersion:1,mode:EARTH_ORBIT_MODE,available:true,status:'ready',sessionId:'panel-session',revision:0,nextSequence:0,error:null,inputs:[],
  computer:{software:'Comanche055',cycle:1024000,cpuSeconds:12,dsky:{PROG:'00',VERB:'16',NOUN:'36',R1:'00000',R2:'00000',R3:'01200'},dskySource:{channel:8,cycle:1000000},lastKey:null,provenance:{ropeSha256:'a'.repeat(64),engineSha256:'b'.repeat(64),sourceUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html'}},
  task:{id:'diagnostic',title:'Server-owned diagnostic',complete:false,nextInstruction:'A server-only instruction: request the real display.',scope:'Original cold-start computer. No flight or alignment completed.',flightExecuted:false,alignmentCompleted:false,steps:[{id:'clock',title:'Original clock',description:'Read the actual clock display.',active:true,complete:false}]}});
const capabilities=()=>({available:true,mode:EARTH_ORBIT_MODE,software:'Comanche055',scope:'Cold-start computer only; no spacecraft motion or TLI.',unavailableReason:null,supportedKeys:[...DSKY_KEYS],token:'panel-private-token'});

test('panel starts with unknown digits and disabled keys, then shows only observed output and server instructions',async()=>{
  const doc=new Document(),root=doc.createElement('section'),calls=[],panel=createEarthOrbitPanel({root,fetchImpl:async(path,options)=>{calls.push([path,options.method]);return response(path.endsWith('/capabilities')?capabilities():frame());}});
  try {
    assert.equal(output(root,'PROG').textContent,'??');assert.equal(key(root,'VERB').disabled,true);panel.setVisible(true);await panel.load();
    assert.equal(output(root,'PROG').textContent,'00');assert.equal(output(root,'R3').textContent,'01200');assert.match(root.textContent,/A server-only instruction/);assert.match(root.textContent,/CPU time/);assert.match(root.textContent,/other lamps remain unknown/);
    assert.equal(key(root,'VERB').disabled,false);assert.equal(calls.every(([,method])=>method==='GET'),true);
    panel.setVisible(false);assert.equal(key(root,'VERB').disabled,true);assert.equal(output(root,'R3').textContent,'01200');assert.equal(calls.every(([,method])=>method==='GET'),true,'Leaving the chapter does not synthesize a stop or key');
  }finally {panel.dispose();}
});

test('observation polling leaves the acknowledged controls usable and never sends a key',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});const doc=new Document(),root=doc.createElement('section'),calls=[];
  const panel=createEarthOrbitPanel({root,fetchImpl:async(path,options)=>{calls.push([path,options.method]);return response(path.endsWith('/capabilities')?capabilities():frame());}});
  try {panel.setVisible(true);await panel.load();assert.equal(key(root,'VERB').disabled,false);context.mock.timers.tick(1001);await flush();assert.equal(key(root,'VERB').disabled,false);assert.equal(panel.state.busy,false);assert.equal(calls.length,3);assert.equal(calls.every(([,method])=>method==='GET'),true);panel.setVisible(false);context.mock.timers.tick(5000);await flush();assert.equal(calls.length,3);}
  finally {panel.dispose();}
});

test('actual key buttons wait for acknowledgement and preserve last display on an unavailable response',async()=>{
  const doc=new Document(),root=doc.createElement('section'),calls=[];let finish;
  const panel=createEarthOrbitPanel({root,fetchImpl:async(path,options)=>{
    calls.push([path,options.method,options.body]);if(path.endsWith('/capabilities'))return response(capabilities());if(path.endsWith('/status'))return response(frame());
    return new Promise((resolve,reject)=>{finish=()=>reject(new TypeError('Disconnected after key'));});
  }});
  try {panel.setVisible(true);await panel.load();key(root,'VERB').click();assert.equal(key(root,'VERB').disabled,true);assert.equal(output(root,'R3').textContent,'01200');assert.deepEqual(JSON.parse(calls.at(-1)[2]),{sessionId:'panel-session',sequence:0,key:'VERB'});finish();await flush();assert.equal(panel.state.error,'Disconnected after key');assert.equal(key(root,'VERB').disabled,true);assert.equal(output(root,'R3').textContent,'01200');assert.match(root.textContent,/No key was automatically retried/);assert.equal(calls.filter(([,method])=>method==='POST').length,1);assert.equal(button(root,'Refresh observation').disabled,false);}
  finally {panel.dispose();}
});

test('unavailable native assets retain unknown displays and offer reconnect without a fake start',async()=>{
  const doc=new Document(),root=doc.createElement('section'),calls=[];const panel=createEarthOrbitPanel({root,fetchImpl:async(path,options)=>{calls.push(options.method);return response({...capabilities(),available:false,token:null,supportedKeys:[],unavailableReason:'Pinned CMC assets missing.'});}});
  try {panel.setVisible(true);await panel.load();assert.equal(panel.state.available,false);assert.equal(button(root,'Start Columbia’s CMC').disabled,true);assert.equal(key(root,'ENTR').disabled,true);assert.equal(output(root,'PROG').textContent,'??');assert.match(root.textContent,/Pinned CMC assets missing/);assert.deepEqual(calls,['GET']);}
  finally {panel.dispose();}
});

test('observed signs and indicator bits render while unmapped lamps remain unknown',async()=>{
  const doc=new Document(),root=doc.createElement('section'),observed=frame();observed.computer.dsky.signs={R1:'+',R2:'-',R3:' '};observed.computer.dsky.lamps={keyRelease:true,operatorError:false,computerActivity:true,verbNounFlash:true};
  const panel=createEarthOrbitPanel({root,fetchImpl:async path=>response(path.endsWith('/capabilities')?capabilities():observed)});
  try {panel.setVisible(true);await panel.load();for(const [field,sign] of Object.entries(observed.computer.dsky.signs))assert.equal(all(root).find(el=>el.dataset.cmcSign===field).textContent,sign);assert.equal(all(root).find(el=>el.dataset.cmcLamp==='keyRelease').attributes['aria-label'],'KEY REL: observed on');assert.equal(all(root).find(el=>el.dataset.cmcLamp==='operatorError').attributes['aria-label'],'OPR ERR: observed off');assert.ok(all(root).some(el=>el.attributes['aria-label']==='Computer activity: observed on'));assert.match(root.textContent,/UPLINK ACTY\?/);assert.match(root.textContent,/flash request: active/);assert.match(root.textContent,/channel 011/);}
  finally {panel.dispose();}
});

test('only human console actions notify the campaign; loading and polling cannot stop a reference tour',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});const doc=new Document(),root=doc.createElement('section');let actions=0;
  const panel=createEarthOrbitPanel({root,onAction:()=>actions++,fetchImpl:async path=>response(path.endsWith('/capabilities')?capabilities():frame())});
  try {panel.setVisible(true);await panel.load();assert.equal(actions,0);context.mock.timers.tick(1001);await flush();assert.equal(actions,0);button(root,'Refresh observation').click();await flush();assert.equal(actions,1);context.mock.timers.tick(1001);await flush();assert.equal(actions,1);}
  finally {panel.dispose();}
});
