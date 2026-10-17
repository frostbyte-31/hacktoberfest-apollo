/** Evidence navigation only. These are experiment observations, not a flown checklist. */
const STEPS = Object.freeze([
  {event:'startup',title:'Inspect original startup',focus:'Observe the recorded startup checkpoint.',
    why:'The test fixture has completed startup. This does not establish the historical spacecraft switch configuration.',
    control:'Recorded startup observation',expect:'A retained startup checkpoint; no user command is sent.'},
  {event:'p51',title:'Follow P51 alignment',focus:'Observe the original alignment program starting.',
    why:'This experiment uses synthetic star sightings to exercise original P51. It is not a reconstruction of Apollo 11’s flown alignment procedure.',
    control:'P51 in the retained experiment',expect:'Original P51 entry, with actual DSKY relay digits held independently.'},
  {event:'alignment',title:'Check reference readiness',focus:'Inspect the completed alignment checkpoint.',
    why:'Guidance needs a reference orientation. Original software established REFSMMAT and REFSMFLG here; real vehicle calibration is not demonstrated.',
    control:'Original P51 completion',expect:'A recorded reference-matrix readiness result.'},
  {event:'mission-inputs',title:'Follow mission-data loading',focus:'Inspect P27 mission-state initialization.',
    why:'The fixture supplied documented synthetic navigation and target data through authentic V71 transactions. You are reviewing a recording, not uploading new values.',
    control:'Recorded V71 / P27 transactions',expect:'Mission-data loading begins. Individual stored blocks remain visible in the full evidence explorer.'},
  {event:'inputs-complete',title:'Review the initialized scenario',focus:'Check which mission inputs this run contains.',
    why:'Position, velocity, target and epoch belong together. These are synthetic experiment inputs; the missing-site variant intentionally omits its landing target.',
    control:'Recorded input-completion checkpoint',expect:'Input completion as retained by this scenario; no historical trajectory is inferred.'},
  {event:'p63',title:'Inspect P63 selection',focus:'Follow the recorded program-selection action.',
    why:'The retained run selected original P63 using V37 E 63 E. Live DSKY entry is not available, so this screen does not pretend that clicking a key executes it.',
    control:'Recorded sequence: VERB 3 7 ENTR 6 3 ENTR',expect:'Original P63 entry. Display relay updates can lag this software checkpoint.'},
  {event:'ignition-solution',fallback:'root-failure',title:'Inspect the guidance result',focus:'Read the actual calculation outcome.',
    why:'An ignition-time solution is a plan for a burn. A missing landing target can instead lead to the original alarm path. Neither outcome fires an engine.',
    control:'Original guidance calculation',expect:'A retained ignition solution, or the actual recorded calculation failure.'},
  {event:'crew-review',fallback:'alarm-01406',title:'Read the crew-review display',focus:'Inspect the recorded review or alarm boundary.',
    why:'The nominal recordings reach V06 N61; the negative control stops on 01406. Crew continuation, engine arming and descent were not executed.',
    control:'Read-only DSKY observation',expect:'The retained review checkpoint or alarm. There is no verified next flight step to execute here.'},
]);

export function buildProcedure(provider, scenarioId) {
  const events=provider.getEvents(scenarioId);
  const result=STEPS.map(step=>{
    const event=events.find(item=>item.id===step.event) || events.find(item=>item.id===step.fallback);
    if(!event)throw new Error(`Missing recorded procedure observation: ${step.event}`);
    return Object.freeze({...step,event,classification:'recorded experiment observation',commandAvailable:false});
  });
  if(result.some((step,index)=>index && step.event.t<result[index-1].event.t))throw new Error('Procedure observations are not chronological.');
  return Object.freeze(result);
}

export function procedureSelection(provider, scenarioId, index=-1) {
  const steps=buildProcedure(provider,scenarioId);
  if(!Number.isInteger(index)||index< -1||index>=steps.length)throw new Error('Invalid procedure selection.');
  const step=index<0?null:steps[index];
  return Object.freeze({steps,index,step,snapshot:provider.getSnapshot(scenarioId,step?.event.t ?? 0),
    atBoundary:index===steps.length-1,flightCompleted:false,commandSent:false});
}
