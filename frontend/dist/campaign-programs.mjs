import {CAMPAIGN_STAGE_IDS} from './campaign-state.mjs';
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const text=value=>typeof value==='string'&&value.trim().length>0;
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const sourceUrl=value=>{try{const url=new URL(value);return url.protocol==='https:'&&['www.ibiblio.org','github.com'].includes(url.hostname)&&url.username===''&&url.password==='';}catch{return false;}};
/** This index is a source-reading aid. It can never announce an execution capability. */
export function validateCampaignProgramIndex(value){
  const invalid=reason=>{throw new Error(`Invalid Apollo source index: ${reason}.`);};
  if(!object(value)||value.schemaVersion!==1||value.classification!=='SOURCE_INDEX_ONLY'||!text(value.executionDisclaimer)||!Array.isArray(value.software)||!Array.isArray(value.stages)||value.stages.length!==CAMPAIGN_STAGE_IDS.length)invalid('classification or structure');
  const softwareIds=new Set(value.software.map(item=>item?.id));
  if(softwareIds.size!==value.software.length||softwareIds.size!==2||!softwareIds.has('comanche055')||!softwareIds.has('luminary099'))invalid('original software identities');
  for(const[index,stage]of value.stages.entries()){
    if(!object(stage)||stage.stageId!==CAMPAIGN_STAGE_IDS[index]||stage.completeFlightAvailable!==false||!text(stage.station)||!Array.isArray(stage.originalPrograms)||!Array.isArray(stage.missingSystems)||stage.missingSystems.some(item=>!text(item)))invalid('stage order, scope or dependencies');
    for(const program of stage.originalPrograms){
      if(!object(program)||!softwareIds.has(program.softwareId)||!text(program.program)||!text(program.file)||!text(program.symbol)||!Number.isSafeInteger(program.line)||program.line<1||!sourceUrl(program.listingUrl)||!sourceUrl(program.pinnedSourceUrl)||!sha(program.sourceSha256)||!text(program.excerpt)||!Array.isArray(program.excerptLineNumbers)||program.excerptLineNumbers[0]!==program.line||!text(program.scope))invalid('program source location');
    }
  }
  return value;
}
