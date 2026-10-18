import {createEarthOrbitPanel} from './earth-orbit-panel.mjs?v=p52-1';
import {EarthAlignmentClient,EARTH_ALIGNMENT_MODE} from './earth-alignment-client.mjs?v=p52-2';

const radians=value=>value*Math.PI/180;
const vector=(shaft,trunnion)=>[Math.sin(radians(trunnion))*Math.cos(radians(shaft)),Math.sin(radians(trunnion))*Math.sin(radians(shaft)),Math.cos(radians(trunnion))];
const dot=(a,b)=>a.reduce((sum,value,index)=>sum+value*b[index],0);

/** Perspective projection only. The backend owns all instrument angles and star geometry. */
export function projectAlignmentStar(instruments,star){
  const s=radians(instruments.shaftDeg),t=radians(instruments.trunnionDeg),point=vector(star.shaftDeg,star.trunnionDeg),center=vector(instruments.shaftDeg,instruments.trunnionDeg);
  const right=[-Math.sin(s),Math.cos(s),0],up=[Math.cos(t)*Math.cos(s),Math.cos(t)*Math.sin(s),-Math.sin(t)],depth=dot(point,center),scale=84/Math.tan(radians(30));
  if(depth<=0){const x=dot(point,right)*84,y=-dot(point,up)*84;return {visible:false,x:Math.hypot(x,y)<1e-8?84:x,y};}
  const x=dot(point,right)/depth*scale,y=-dot(point,up)/depth*scale;
  return {visible:Math.hypot(x,y)<=84,x,y};
}

/** Prompts explain observed original output; no input or display response is generated. */
export function alignmentInstruction(snapshot,targetCode='30'){
  const d=snapshot?.computer?.dsky;if(!d)return 'Start the alignment instruments. The setup runs original P51 through measured optical inputs, then leaves P00 for you.';
  if(snapshot.task.complete)return 'Original P52 and gyro feedback observed. You have recovered to P00. The full historical flight remains unavailable.';
  if(d.PROG==='00')return 'Select P52: VERB 3 7 ENTR 5 2 ENTR. Use the original DSKY below.';
  if(d.PROG!=='52')return 'Follow the actual DSKY display. P52 is the alignment program; VERB 3 7 ENTR 5 2 ENTR selects it.';
  if(d.NOUN==='06')return 'Choose REFSMMAT option 3: VERB 2 2 ENTR 0 0 0 0 3 ENTR, then PRO. Wait for the original acquisition request.';
  if(d.NOUN==='25'&&d.R1==='00015')return 'Press ENTR for manual star selection. Wait for NOUN 70 before entering a star code.';
  if(d.NOUN==='25'&&d.R1==='00016')return 'A MARK was captured. Press PRO to review its stored star identity.';
  if(d.NOUN==='25'&&d.R1==='00014')return 'Original P52 has finished. Return to P00: VERB 3 7 ENTR 0 0 ENTR.';
  if(d.NOUN==='71')return 'Verify the stored star identity. PRO confirms this sighting; then wait for the next star request or separation review.';
  if(d.NOUN==='05'&&d.VERB==='06')return 'Review the original star-angle difference in R1 (0.01° units). PRO accepts; ENTR recycles the sightings. This is measured software output.';
  if(d.NOUN==='93'&&d.VERB==='06')return 'Review the original gyro torque angles. PRO authorizes the CMC to correct the modeled platform. Wait for actual pulse feedback and code 00014.';
  if(d.VERB==='51')return 'Use the optics hand controller to center your chosen star, then press MARK. The first sighting is 30 Menkent; the second is 37 Nunki.';
  if(d.NOUN==='70')return `Enter star ${targetCode}: VERB 2 1 ENTR 0 0 0 ${targetCode[0]} ${targetCode[1]} ENTR, then PRO. Wait for VERB 51. Use 30 first, then 37.`;
  return 'The original computer is processing. Wait for a stable prompt; no next command is sent automatically.';
}

export function createEarthAlignmentPanel({root,onState=()=>{},onAction=()=>{},fetchImpl=globalThis.fetch}={}){
  const doc=root.ownerDocument,make=(tag,text,className)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  let visible=false,lastState=null,targetCode='30',rate='HIGH',duration=1;
  const consolePanel=createEarthOrbitPanel({root,fetchImpl,onAction,clientFactory:options=>new EarthAlignmentClient(options),labels:{
    mode:EARTH_ALIGNMENT_MODE,title:'Align Columbia’s platform.',start:'Prepare alignment instruments',restart:'Restart alignment setup',
    intro:'Perform P52 with original Comanche 055 and manual navigation controls. An automatic P51 setup runs fresh original code through modeled instrument inputs to establish a training reference. You then identify two stars, take sextant marks, review the computed error and approve the CMC’s gyro correction. The instruments use a fixed modeled star field; they are not recovered Apollo 11 flight measurements.'
  },onState:state=>{lastState=state;render();onState(state);}});
  root.classList.add('earth-alignment');
  const navigation=make('section',undefined,'alignment-navigation');navigation.setAttribute('aria-label','Columbia navigation station');
  navigation.append(make('span','NAVIGATION STATION / MANUAL OPTICS','eyebrow'),make('h3','Find. Mark. Confirm.'));
  const next=make('p',alignmentInstruction(null),'alignment-next');next.setAttribute('aria-live','polite');
  const source=make('p','MODELED INSTRUMENTS · ORIGINAL CMC COMPUTATION','alignment-source');navigation.append(source,next);
  const targets=make('div',undefined,'alignment-targets');targets.role='group';targets.setAttribute('aria-label','Acquisition guide target');
  const targetButtons=new Map();for(const [code,name]of [['30','Menkent'],['37','Nunki']]){const button=make('button',`${code} ${name}`);button.type='button';button.addEventListener('click',()=>{targetCode=code;render();});targets.append(button);targetButtons.set(code,button);}
  navigation.append(make('label','Acquisition guide target'),targets,make('p','Selecting a guide changes the reference overlay. Enter the star identity separately through the DSKY.','alignment-note'));
  const svg=doc.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','-100 -100 200 200');svg.setAttribute('role','img');svg.setAttribute('aria-label','Modeled star acquisition diagram');svg.classList.add('alignment-scope');
  const svgNode=(tag,attrs)=>{const node=doc.createElementNS('http://www.w3.org/2000/svg',tag);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,String(value));return node;};
  svg.append(svgNode('circle',{cx:0,cy:0,r:84,class:'alignment-field'}),svgNode('path',{d:'M -96 0 H 96 M 0 -96 V 96 M -5 0 H 5 M 0 -5 V 5',class:'alignment-crosshair'}));
  const starLayer=svgNode('g',{});svg.append(starLayer);navigation.append(svg,make('p','Acquisition diagram · 30° radius · ideal perspective, not a replica optical image. Off-field targets are shown at the rim.','alignment-note'));
  const angles=make('p','Instrument angles unavailable.','alignment-angles'),targetInfo=make('p','Star direction unavailable.','alignment-target-info');navigation.append(angles,targetInfo);
  const modes=make('div',undefined,'alignment-modes');modes.role='group';modes.setAttribute('aria-label','OPTICS MODE');const modeButtons=new Map();
  for(const mode of ['ZERO','MANUAL','CMC']){const button=make('button',mode);button.type='button';button.setAttribute('aria-label',`OPTICS MODE ${mode}`);button.addEventListener('click',()=>consolePanel.instrument('optics_mode',mode));if(mode==='CMC')button.title='Automatic optics motor drive is unavailable in this bounded fixture.';modes.append(button);modeButtons.set(mode,button);}
  navigation.append(make('span','OPTICS MODE','eyebrow'),modes);
  const options=make('div',undefined,'alignment-jog-options'),rateLabel=make('label','OHC gain'),rateSelect=make('select');rateSelect.setAttribute('aria-label','OHC modeled gain');
  for(const[value,label]of [['HIGH','HIGH · direct limit'],['LOW','LOW · model fine rate']]){const option=make('option',label);option.value=value;rateSelect.append(option);}rateSelect.addEventListener('change',()=>{rate=rateSelect.value;render();});rateLabel.append(rateSelect);
  const durationLabel=make('label','Deflection duration'),durationSelect=make('select');durationSelect.setAttribute('aria-label','OHC deflection duration');
  for(const[value,label]of [['1','1 CPU second'],['0.1','0.1 CPU second'],['0.01','0.01 CPU second']]){const option=make('option',label);option.value=value;durationSelect.append(option);}durationSelect.addEventListener('change',()=>{duration=Number(durationSelect.value);render();});durationLabel.append(durationSelect);options.append(rateLabel,durationLabel);navigation.append(options);
  const ohc=make('div',undefined,'alignment-ohc');ohc.role='group';ohc.setAttribute('aria-label','Optics hand controller');const jogButtons=[];
  for(const[label,shaft,trunnion,area]of [['TRUNNION +',0,1,'up'],['SHAFT −',-1,0,'left'],['SHAFT +',1,0,'right'],['TRUNNION −',0,-1,'down']]){const button=make('button',label);button.type='button';button.style.gridArea=area;button.setAttribute('aria-label',`OHC ${label}`);button.addEventListener('click',()=>consolePanel.instrument('optics_slew',{shaft,trunnion,rate,seconds:duration}));ohc.append(button);jogButtons.push(button);}
  ohc.append(make('span','OHC','alignment-ohc-center'));const movement=make('p','','alignment-note');navigation.append(ohc,movement);
  const markButtons=make('div',undefined,'alignment-mark-controls'),mark=make('button','MARK','primary'),reject=make('button','MARK REJECT');for(const button of[mark,reject])button.type='button';mark.setAttribute('aria-label','Optics MARK');reject.setAttribute('aria-label','Optics MARK REJECT');mark.addEventListener('click',()=>consolePanel.instrument('mark','MARK'));reject.addEventListener('click',()=>consolePanel.instrument('mark','REJECT'));markButtons.append(mark,reject);navigation.append(markButtons);
  const measurements=make('p','No instrument observation yet.','alignment-measurements');navigation.append(measurements);
  const fixture=make('details',undefined,'alignment-fixture'),fixtureSummary=make('summary','Instrument setup and limits'),fixtureCopy=make('p','The original P51 establishes this fixture’s reference before you start P52. The stationary star geometry, instrument response and bounded rates are modeled; no historical orbital state is loaded.'),power=make('button','IMU OPERATE input: unavailable');power.type='button';power.addEventListener('click',()=>consolePanel.instrument('power_imu',!lastState?.snapshot?.computer?.instruments?.imuPowered));fixture.append(fixtureSummary,fixtureCopy,power);navigation.append(fixture);
  navigation.id='alignment-optics';root.querySelector('.earth-instrument').id='alignment-dsky';
  const stationNav=make('nav',undefined,'alignment-station-nav');stationNav.setAttribute('aria-label','Navigation station shortcuts');
  for(const[label,target]of[['DSKY controls','alignment-dsky'],['Optics controls','alignment-optics']]){const link=make('a',label);link.href=`#${target}`;link.addEventListener('click',onAction);stationNav.append(link);}
  root.insertBefore(stationNav,root.querySelector('.earth-grid'));
  root.querySelector('.earth-grid').insertBefore(navigation,root.querySelector('.earth-objective'));
  function render(){
    if(!navigation)return;
    const state=lastState,snapshot=state?.snapshot,model=snapshot?.computer?.instruments,ready=visible&&state?.available&&!state.busy&&!state.loading&&!state.error&&snapshot?.status==='ready';
    next.textContent=alignmentInstruction(snapshot,targetCode);
    for(const[code,button]of targetButtons)button.setAttribute('aria-pressed',String(code===targetCode));
    for(const[mode,button]of modeButtons){button.disabled=!ready||mode==='CMC';button.setAttribute('aria-pressed',String(model?.opticsMode===mode));}
    for(const button of jogButtons)button.disabled=!ready||model?.opticsMode!=='MANUAL';
    mark.disabled=!ready||!model?.imuPowered;reject.disabled=!ready;power.disabled=!ready;rateSelect.disabled=!ready;durationSelect.disabled=!ready;
    power.textContent=`IMU OPERATE input: ${model?(model.imuPowered?'ON':'OFF'):'unavailable'}`;
    movement.textContent=`Each tap applies a bounded OHC deflection for ${duration} CPU seconds. ${rate==='HIGH'?'Direct limits: shaft 20°/s, trunnion 10°/s.':'Assumed fine rates: shaft 0.2°/s, trunnion 0.1°/s.'} This is an on-screen jog interface to modeled motors.`;
    starLayer.replaceChildren();
    if(!model){angles.textContent='Instrument angles unavailable.';targetInfo.textContent='Prepare the instruments to inspect the star field.';return;}
    const star=model.stars.find(item=>item.code===targetCode);
    angles.textContent=`Shaft ${model.shaftDeg.toFixed(4)}° · optical LOS ${model.trunnionDeg.toFixed(4)}° · mechanical trunnion ${model.mechanicalTrunnionDeg.toFixed(4)}°`;
    targetInfo.textContent=star?`${star.code} ${star.name}: target shaft ${star.shaftDeg.toFixed(4)}°, LOS ${star.trunnionDeg.toFixed(4)}° · sighting offset ${star.errorDeg.toFixed(4)}°`:'Target unavailable.';
    svg.setAttribute('aria-label',star?`Modeled acquisition guide: ${star.name}, offset ${star.errorDeg.toFixed(4)} degrees`:'Modeled star acquisition diagram');
    for(const item of model.stars){const point=projectAlignmentStar(model,item),norm=Math.hypot(point.x,point.y),rim=norm>0?84/norm:0,x=point.visible?point.x:point.x*rim,y=point.visible?point.y:point.y*rim;if(!Number.isFinite(x)||!Number.isFinite(y))continue;const circle=svgNode('circle',{cx:x,cy:y,r:item.code===targetCode?3:2,class:item.code===targetCode?'alignment-selected-star':'alignment-star'}),label=svgNode('text',{x:Math.max(-75,Math.min(65,x+5)),y:Math.max(-75,Math.min(75,y-6))});label.textContent=item.code+(point.visible?'':' ↗');starLayer.append(circle,label);}
    measurements.textContent=`Marks captured: ${model.markCount} (includes P51 setup). P52 marks: ${model.alignment.p52Marks}. Original gyro outputs: ${model.alignment.torqueOutputCount}. Sensor counter operations: ${model.sensorOperations??'unavailable'}.`;
    fixtureCopy.textContent=`${model.scope} ${model.ohcRateScope??''} Automatic CMC optics drive is unavailable; use MANUAL. This task never supplies a state vector or launch-vehicle control.`;
  }
  render();
  return {load:()=>consolePanel.load(),setVisible(value){visible=value===true;consolePanel.setVisible(visible);render();},get state(){return consolePanel.state;},dispose(){consolePanel.dispose();}};
}
