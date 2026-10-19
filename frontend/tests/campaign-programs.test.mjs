import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateCampaignProgramIndex} from '../dist/campaign-programs.mjs';
const index=JSON.parse(readFileSync(new URL('../dist/data/campaign-programs.json',import.meta.url),'utf8'));

test('all16chapters expose original sources without declaring historical flight available',()=>{
  const before=JSON.stringify(index);assert.equal(validateCampaignProgramIndex(index),index);assert.equal(index.stages.length,16);assert.equal(index.stages.every(stage=>stage.completeFlightAvailable===false),true);assert.equal(JSON.stringify(index),before);
});
test('source index cannot be relabeled live execution or reordered into an incorrect chronology',()=>{
  for(const mutate of[value=>{value.classification='LIVE AGC EXECUTION';},value=>{value.stages.reverse();},value=>{value.stages[0].completeFlightAvailable=true;}]){const changed=structuredClone(index);mutate(changed);assert.throws(()=>validateCampaignProgramIndex(changed),/Invalid Apollo source index/);}
});
test('unknown software and missing source identities are rejected before rendering',()=>{
  for(const mutate of[value=>{value.stages[0].originalPrograms[0].softwareId='invented';},value=>{value.stages[0].originalPrograms[0].sourceSha256='';},value=>{value.stages[0].originalPrograms[0].line=0;},value=>{value.stages[0].originalPrograms[0].excerptLineNumbers=[];}]){const changed=structuredClone(index);mutate(changed);assert.throws(()=>validateCampaignProgramIndex(changed),/Invalid Apollo source index/);}
});
test('source links cannot execute script or send readers to arbitrary sites',()=>{
  for(const url of['javascript:alert(1)','http://www.ibiblio.org/apollo/','https://example.org/fake','https://user:secret@github.com/virtualagc/virtualagc']){const changed=structuredClone(index);changed.stages[0].originalPrograms[0].listingUrl=url;assert.throws(()=>validateCampaignProgramIndex(changed),/Invalid Apollo source index/);}
});
