/** Pure reference/replay navigation. This module sends no spacecraft commands. */

const fail=message=>{throw new Error(`Invalid Apollo operations reference: ${message}`);};
const text=value=>typeof value==='string'&&value.trim().length>0;
const uniqueIds=(items,label)=>{
  if(!Array.isArray(items))fail(`${label} list`);
  const ids=new Set();
  for(const item of items){
    if(!text(item?.id)||ids.has(item.id))fail(`${label} identity`);
    ids.add(item.id);
  }
  return ids;
};

/** Validate presentation structure and citations, not the historical sources' truth. */
export function validateOperations(data){
  if(data?.schemaVersion!==1)fail('schema');
  const sourceIds=uniqueIds(data.sources,'source');
  if(!sourceIds.size)fail('missing sources');
  for(const item of data.sources){
    let url;
    try{url=new URL(item.url);}catch{fail('source HTTPS URL');}
    if(url.protocol!=='https:'||!url.hostname||url.username||url.password||!text(item.title)||!text(item.locator)||!text(item.revisionScope))fail('source HTTPS URL or citation');
  }
  const references=(value,label)=>{
    if(!Array.isArray(value)||!value.length||new Set(value).size!==value.length||value.some(id=>!sourceIds.has(id)))fail(`${label} source reference`);
  };
  const chapter=data.chapter;
  if(!chapter||!['id','title','startDescription','getLabel'].every(key=>text(chapter[key]))||!Array.isArray(chapter.startingConfiguration)||!chapter.startingConfiguration.length)fail('starting chapter');
  for(const setting of chapter.startingConfiguration){
    if(!['label','referenceValue','locator'].every(key=>text(setting?.[key])))fail('starting configuration');
    references(setting.sourceIds,'starting configuration');
  }
  uniqueIds(data.timeline,'timeline');
  if(data.timeline.length!==14||data.timeline[0].id!=='docked-preparation')fail('fourteen chronological chapters beginning docked');
  for(const [index,item] of data.timeline.entries()){
    if(item.order!==index+1||!['title','vehicle','crewRole','getLabel','description'].every(key=>text(item[key])))fail('chronological chapter order or description');
    references(item.sourceIds,'timeline');
  }
  uniqueIds(data.controls,'control');
  if(data.controls.length!==6)fail('six control references');
  for(const item of data.controls){
    if(!['label','hardware','location','purpose','limitations'].every(key=>text(item[key])))fail('control description');
    references(item.sourceIds,'control');
    uniqueIds(item.modes,'control mode');
    if(!item.modes.length)fail('control mode list');
    for(const mode of item.modes){
      if(!text(mode.label)||!text(mode.behavior))fail('control mode description');
      references(mode.sourceIds,'control mode');
    }
  }
  const software=data.softwareEntry;
  if(!text(software?.summary)||!Array.isArray(software.files)||!software.files.length)fail('software entry reference');
  references(software.sourceIds,'software entry');
  for(const file of software.files){
    if(!['path','symbol','meaning'].every(key=>text(file?.[key])))fail('software file reference');
    references(file.sourceIds,'software file');
  }
  return data;
}

/** Preserve actual event objects and raw-row order, including equal timestamps. */
export function replayMilestones(item,includeAll=false){
  const events=Array.isArray(item?.events)?item.events:[];
  if(includeAll)return events.slice();
  const start=events.findIndex(event=>event.routine==='P63LM'||/^p63lm(?:-|$)/.test(event.id));
  if(start<0)return [];
  return events.slice(start).filter(event=>event.kind!=='dsky-input'&&event.kind!=='cockpit-input');
}

/** No physical state is supplied before the first authoritative plant sample. */
export function physicalStart(item){
  const frame=item?.frames?.find(frame=>frame.spacecraft&&Number.isFinite(frame.t));
  return frame?.t ?? null;
}

/** selectedId distinguishes different recorded rows at one native CPU instant. */
export function adjacentReplayEvent(events,seconds,direction,selectedId=null){
  if(!Number.isFinite(seconds))throw new Error('Invalid execution time.');
  if(direction!==1&&direction!==-1)throw new Error('Replay event direction must be 1 or -1.');
  if(!Array.isArray(events)||!events.length)return null;
  const selected=selectedId===null?-1:events.findIndex(event=>event.id===selectedId);
  if(selected>=0)return events[selected+direction] ?? null;
  if(direction===1)return events.find(event=>event.t>seconds) ?? null;
  for(let index=events.length-1;index>=0;index--)if(events[index].t<seconds)return events[index];
  return null;
}
