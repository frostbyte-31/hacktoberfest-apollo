import test from 'node:test';
import assert from 'node:assert/strict';
import {
 CAMPAIGN_TASK_CATALOG,CAMPAIGN_TASK_REVISION,CAMPAIGN_TASK_SOURCE_REVISION,CAMPAIGN_TASK_STORAGE_KEY,
 PINNED_COMANCHE_ROPE_SHA256,createCampaignTaskState,resetCampaignTaskProgress,invalidateCampaignTaskSession,
 observeCampaignTaskSnapshot,campaignTaskStatus,serializeCampaignTaskProgress,restoreCampaignTaskProgress,
 readCampaignTaskProgress,saveCampaignTaskProgress,
} from '../dist/campaign-task-state.mjs';
import {CAMPAIGN_STAGE_IDS} from '../dist/campaign-state.mjs';

// Contract fixtures only. These are not retained execution evidence or invented flight output.
const steps=['select-p52','star-marks','star-angle','gyro-review','alignment-return'];
const checkpoints=['select-p52','star-marks','star-angle','gyro-review','completion-display','alignment-return'];
const capability={alignmentAvailable:true};
function observation({complete=false,sessionId='unit-cmc-run',cycle=1024000,revision=0}={}) {
 const dsky={PROG:'00',VERB:'  ',NOUN:'  ',R1:'00000',R2:'00000',R3:'00000'};
 const checkpointDisplays=[
  {...dsky,PROG:'52'}, {...dsky,PROG:'52'},
  {...dsky,PROG:'52',VERB:'06',NOUN:'05',R1:'00001'},
  {...dsky,PROG:'52',VERB:'06',NOUN:'93',R1:'00002',R2:'00010',R3:'00009'},
  {...dsky,PROG:'52',VERB:'50',NOUN:'25',R1:'00014'}, dsky,
 ];
 return {schemaVersion:1,mode:'LIVE ORIGINAL CMC / MODELED INSTRUMENTS',available:true,status:'ready',sessionId,revision,nextSequence:revision,
  computer:{software:'Comanche055',mode:'LIVE AGC EXECUTION',cycle,cpuSeconds:cycle*12/1024000,dsky,
   dskySource:{channel:8,cycle:cycle-1},lastKey:null,
   provenance:{ropeSha256:PINNED_COMANCHE_ROPE_SHA256,engineSha256:'a'.repeat(64),sourceUrl:'https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html',hostFlightMemoryWrites:false},
   historicalCheckpointLoaded:false,flightState:null,
   instruments:{mode:'MODELED CSM INSTRUMENTS',imuPowered:true,opticsMode:'MANUAL',shaftDeg:0,trunnionDeg:40,mechanicalTrunnionDeg:20,
    scope:'Unit instrument fixture; not a flight state.',markCount:complete?4:2,
    stars:[{code:'30',name:'Unit star A',shaftDeg:0,trunnionDeg:40,errorDeg:0},{code:'37',name:'Unit star B',shaftDeg:104,trunnionDeg:40,errorDeg:0}],
    alignment:{referenceInitialized:true,p52Complete:complete,p52Marks:complete?2:0,torqueApproved:complete,torqueOutputCount:complete?3:0,gyroSensorFeedbackOperations:complete?6:0,completionCycle:complete?600:null}}},
  task:{id:'original-p52-alignment',title:'Original P52 unit contract',complete,alignmentCompleted:complete,flightExecuted:false,
   scope:'Instrument task only.',nextInstruction:complete?'Return observed.':'Select P52.',
   steps:steps.map((id,index)=>({id,title:id,description:'Source-observed checkpoint required.',complete,active:!complete&&index===0})),
   checkpoints:complete?checkpoints.map((id,index)=>({id,cycle:(index+1)*100,dsky:checkpointDisplays[index],dskySource:{channel:8,cycle:(index+1)*100-1}})):[]},inputs:[],error:null};
}
const completedState=()=>observeCampaignTaskSnapshot(createCampaignTaskState(),observation({complete:true}));

test('sixteen scoped tasks preserve chronology and never assert flown stages',()=>{
 assert.deepEqual(CAMPAIGN_TASK_CATALOG.map(item=>item.stageId),CAMPAIGN_STAGE_IDS);
 assert.equal(CAMPAIGN_TASK_CATALOG.filter(item=>item.kind==='live-original-computer').length,1);
 assert.ok(CAMPAIGN_TASK_CATALOG.every(item=>item.flightExecuted===false));
 const state=createCampaignTaskState();assert.equal(state.receiptCount,0);assert.equal(state.missionCompleted,false);
 for(const stageId of CAMPAIGN_STAGE_IDS.slice(1)) {
  const status=campaignTaskStatus(state,stageId,{alignmentAvailable:true,thrustMonitorAvailable:true,authenticLanding:true});
  assert.equal(status.canOperate,false);assert.equal(status.complete,false);assert.ok(status.missingDependencies.length);
 }
 assert.match(campaignTaskStatus(state,'tli').reason,/01204/);
});

test('capability availability enables controls but cannot complete original work',()=>{
 const state=createCampaignTaskState();assert.equal(campaignTaskStatus(state,'earth-parking').status,'unavailable');
 assert.equal(campaignTaskStatus(state,'earth-parking',capability).status,'ready');
 assert.equal(campaignTaskStatus(state,'earth-parking',{alignmentAvailable:'true'}).canOperate,false);
 assert.equal(campaignTaskStatus(state,'earth-parking',null).canOperate,false);
 assert.equal(campaignTaskStatus(state,'earth-parking',capability).complete,false);
});

test('P52 requires actual original completion including final P00 and gyro feedback',()=>{
 let state=observeCampaignTaskSnapshot(createCampaignTaskState(),observation());
 assert.equal(campaignTaskStatus(state,'earth-parking',capability).status,'in-progress');assert.equal(state.receiptCount,0);
 state=observeCampaignTaskSnapshot(state,observation({complete:true,revision:64}));
 const result=campaignTaskStatus(state,'earth-parking',capability);
 assert.equal(result.status,'completed-current-run');assert.equal(result.currentRun,true);assert.equal(state.receiptCount,1);
 assert.equal(result.receipt.verification,'service-observed');assert.deepEqual(result.receipt.checkpointIds,checkpoints);
 assert.equal(state.flightExecuted,false);assert.equal(state.missionCompleted,false);
});

test('incomplete, forged, excessive-error and unsourced checkpoint claims are rejected',()=>{
 const reject=mutate=>{const value=observation({complete:true});mutate(value);assert.throws(()=>observeCampaignTaskSnapshot(createCampaignTaskState(),value),/Invalid/);};
 for(const mutate of [
  value=>{value.task.flightExecuted=true;},
  value=>{value.computer.dsky.PROG='52';},
  value=>{value.task.steps[0].complete=false;},
  value=>{value.task.steps[0].active=true;},
  value=>{value.task.checkpoints.pop();},
  value=>{value.task.checkpoints[2].dsky.R1='00006';},
  value=>{value.task.checkpoints[3].dsky.NOUN='05';},
  value=>{value.task.checkpoints[4].dsky.R1='00016';},
  value=>{value.task.checkpoints[5].dsky.PROG='47';},
  value=>{value.task.checkpoints[0].dskySource=null;},
  value=>{value.task.checkpoints[0].dskySource.cycle=100000000;},
  value=>{value.task.checkpoints[2].cycle=50;},
  value=>{value.computer.instruments.alignment.gyroSensorFeedbackOperations=0;},
  value=>{value.computer.instruments.alignment.torqueOutputCount=0;},
  value=>{value.computer.provenance.ropeSha256='b'.repeat(64);},
  value=>{value.computer.provenance.hostFlightMemoryWrites=true;},
 ]) reject(mutate);
});

test('entered keys, P47 zero displays and replay completion cannot issue receipts',()=>{
 for(const mode of ['VERIFIED RECORDED EXECUTION','INTERACTIVE PROCEDURE TRAINER','STATIC HISTORICAL CONFIGURATION']) {
  const value=observation({complete:true});value.mode=mode;
  assert.throws(()=>observeCampaignTaskSnapshot(createCampaignTaskState(),value),/Invalid/);
 }
 const value=observation();value.computer.dsky={...value.computer.dsky,PROG:'47',VERB:'16',NOUN:'83'};
 value.task.id='original-p47-thrust-monitor';value.inputs=[{key:'VERB'},{key:'4'},{key:'7'},{key:'ENTR'}];
 assert.equal(observeCampaignTaskSnapshot(createCampaignTaskState(),value).receiptCount,0);
});

test('source changes and backwards run clocks/counters are rejected',()=>{
 const state=observeCampaignTaskSnapshot(createCampaignTaskState(),observation({revision:5}));
 for(const value of [observation({revision:4}),observation({revision:6,cycle:900000})]) assert.throws(()=>observeCampaignTaskSnapshot(state,value),/stale live/);
 const changed=observation({revision:6});changed.computer.provenance.engineSha256='c'.repeat(64);
 assert.throws(()=>observeCampaignTaskSnapshot(state,changed),/source changed/);
});

test('a newer computer run demotes old completion and late old-run snapshots are rejected',()=>{
 const first=completedState(),next=observeCampaignTaskSnapshot(first,observation({sessionId:'new-unit-run'}));
 assert.equal(campaignTaskStatus(next,'earth-parking',capability).currentRun,false);
 assert.equal(campaignTaskStatus(next,'earth-parking',capability).status,'completed-previous-run');
 assert.throws(()=>observeCampaignTaskSnapshot(next,observation({complete:true,revision:1})),/stale session/);
});

test('repeating P52 in the same run preserves history but clears current qualification',()=>{
 const state=observeCampaignTaskSnapshot(completedState(),observation({revision:1}));
 assert.equal(state.receiptCount,1);assert.equal(campaignTaskStatus(state,'earth-parking',capability).complete,true);
 assert.equal(campaignTaskStatus(state,'earth-parking',capability).currentRun,false);
 assert.equal(campaignTaskStatus(state,'earth-parking',capability).status,'completed-previous-run');
});

test('polling retains the first qualified immutable receipt and stable serialization',()=>{
 const state=completedState(),before=serializeCampaignTaskProgress(state);
 const poll=observeCampaignTaskSnapshot(state,observation({complete:true,revision:1,cycle:1100000}));
 assert.equal(poll.receiptCount,1);assert.equal(serializeCampaignTaskProgress(poll),before);
 assert.equal(poll.receipts[0],state.receipts[0]);assert.equal(poll.activeSession.cycle,1100000);
});

test('missing, idle, stopped, unavailable and failed provider observations clear live bindings',()=>{
 const state=completedState();
 for(const status of ['idle','stopped','error']) {
  const snapshot=observation({complete:true});snapshot.status=status;
  if(status==='idle'){snapshot.computer=null;snapshot.sessionId=null;snapshot.task.complete=false;snapshot.task.alignmentCompleted=false;}
  if(status==='error')snapshot.error='Unit transport failure';
  const cleared=observeCampaignTaskSnapshot(state,snapshot);
  assert.equal(cleared.activeSession,null);assert.equal(cleared.receiptCount,1);
  assert.equal(campaignTaskStatus(cleared,'earth-parking',capability).currentRun,false);
 }
 const unavailable=observation({complete:true});unavailable.status='stopped';unavailable.available=false;
 assert.equal(observeCampaignTaskSnapshot(state,unavailable).activeSession,null);
 assert.equal(invalidateCampaignTaskSession(state).activeSession,null);
 assert.equal(campaignTaskStatus(state,'earth-parking',{}).currentRun,false);
});

test('saving and restoring preserve history without restoring live authority or commands',()=>{
 const saved=serializeCampaignTaskProgress(completedState()),parsed=JSON.parse(saved);
 assert.equal(parsed.campaignRevision,CAMPAIGN_TASK_REVISION);assert.equal(parsed.sourceRevision,CAMPAIGN_TASK_SOURCE_REVISION);
 for(const field of ['activeSession','seenSessionIds','token','capabilities','pendingCommand']) assert.equal(Object.hasOwn(parsed,field),false);
 const restored=restoreCampaignTaskProgress(saved),status=campaignTaskStatus(restored,'earth-parking',capability);
 assert.equal(restored.activeSession,null);assert.equal(status.currentRun,false);assert.equal(status.status,'completed-previous-run');
 assert.equal(status.receipt.verification,'local-history-unverified');
 const refreshed=observeCampaignTaskSnapshot(restored,observation({complete:true}));
 assert.equal(campaignTaskStatus(refreshed,'earth-parking',capability).currentRun,true);
 assert.equal(refreshed.receiptCount,1);
});

test('altered source/revision, invented receipts and oversized saved history fail closed',()=>{
 const valid=JSON.parse(serializeCampaignTaskProgress(completedState()));
 const reject=mutate=>{const value=structuredClone(valid);mutate(value);assert.throws(()=>restoreCampaignTaskProgress(JSON.stringify(value)),/Invalid/);};
 for(const mutate of [
  value=>{value.campaignRevision='old';},value=>{value.sourceRevision='invented';},
  value=>{value.activeSession={sessionId:'forged'};},value=>{value.receipts[0].flightExecuted=true;},
  value=>{value.receipts[0].stageId='powered-descent';},value=>{value.receipts[0].ropeSha256='c'.repeat(64);},
  value=>{value.receipts[0].checkpointIds.pop();},value=>{value.receipts.push(value.receipts[0]);},
  value=>{value.receipts[0].token='secret';},
 ]) reject(mutate);
 assert.throws(()=>restoreCampaignTaskProgress('x'.repeat(65537)),/bounded/);
 assert.throws(()=>restoreCampaignTaskProgress('not json'),/unreadable/);
});

test('blocked storage and resets do not prevent play or mutate an existing computer',()=>{
 const blocked={getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}};
 for(const storage of [null,undefined,blocked,{getItem:()=>'{bad json'}]) assert.equal(readCampaignTaskProgress(storage).receiptCount,0);
 assert.equal(saveCampaignTaskProgress(null,completedState()),false);assert.equal(saveCampaignTaskProgress(blocked,completedState()),false);
 const values=new Map(),storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
 assert.equal(saveCampaignTaskProgress(storage,completedState()),true);assert.ok(values.has(CAMPAIGN_TASK_STORAGE_KEY));
 assert.equal(readCampaignTaskProgress(storage).receiptCount,1);assert.equal(resetCampaignTaskProgress().receiptCount,0);
});

test('states, definitions and receipts are immutable and cannot be substituted by objects',()=>{
 const state=completedState();assert.throws(()=>{state.receipts[0].flightExecuted=true;},TypeError);
 assert.throws(()=>{CAMPAIGN_TASK_CATALOG[0].title='invented';},TypeError);
 assert.throws(()=>campaignTaskStatus({...state},'earth-parking'),/created task state/);
 assert.throws(()=>campaignTaskStatus(state,'__proto__'),/unknown stage/);
});


test('a separately completed P52 attempt in one session retains both cycle-scoped receipts',()=>{
 const first=completedState(),second=observation({complete:true,revision:2,cycle:1100000});
 second.computer.instruments.alignment.completionCycle=1200;
 second.task.checkpoints.forEach(point=>{point.cycle+=600;point.dskySource.cycle+=600;});
 const next=observeCampaignTaskSnapshot(first,second);
 assert.equal(next.receiptCount,2);assert.equal(next.receipts[0],first.receipts[0]);
 assert.equal(campaignTaskStatus(next,'earth-parking',capability).currentRun,true);
 assert.equal(campaignTaskStatus(next,'earth-parking',capability).receipt.completionCycle,1200);
 const restored=restoreCampaignTaskProgress(serializeCampaignTaskProgress(next));assert.equal(restored.receiptCount,2);
});

test('historical receipts remain bounded across many separate native runs',()=>{
 let state=createCampaignTaskState();
 for(let index=0;index<40;index++)state=observeCampaignTaskSnapshot(state,observation({complete:true,sessionId:`bounded-unit-run-${index}`}));
 assert.equal(state.receiptCount,32);assert.equal(state.receipts.at(-1).sessionId,'bounded-unit-run-39');
 assert.equal(restoreCampaignTaskProgress(serializeCampaignTaskProgress(state)).receiptCount,32);
});
