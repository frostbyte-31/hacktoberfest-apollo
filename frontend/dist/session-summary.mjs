import { validateProcedureSnapshot } from './procedure-client.mjs';
import { validateCrewSetup } from './crew-setup.mjs';

const MODE = 'INTERACTIVE PROCEDURE TRAINER';
const TOTAL_ACTIONS = 28;
const ROLES = new Set(['CDR', 'LMP', 'CMP']);
const KINDS = new Set(['crew-report', 'select', 'momentary']);
const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
const nonempty = value => typeof value === 'string' && value.trim().length > 0;
const invalid = reason => { throw new TypeError(`Invalid training summary: ${reason}.`); };

/**
 * Derive a modern training receipt from an already source-validated server
 * snapshot. This checks acknowledgement/progress coherence; it does not verify
 * the supplied source hash against a file or turn reports into flight evidence.
 * No session identity, authorization token, wall clock, score or telemetry is
 * copied into the portable report. Incomplete coherent sessions return null.
 * @param {import('./procedure-types.d.ts').ProcedureSnapshot} snapshot
 * @param {import('./crew-setup-types.d.ts').CrewSetup} setup
 */
export function buildSessionSummary(snapshot, setup) {
  validateProcedureSnapshot(snapshot);
  const crew = validateCrewSetup(setup, {
    localHumanStations: true, networkHumanStations: false, aiCrew: false,
  });
  if (!crew.valid || !crew.canStart) invalid('only valid local human crew configurations are supported');
  if (!/^[a-f0-9]{64}$/i.test(snapshot.definitionSha256)
    || snapshot.capabilities.definitionSha256 !== snapshot.definitionSha256) invalid('checklist source hash');
  const count = snapshot.completedStepIds.length;
  if (count > TOTAL_ACTIONS || snapshot.currentStepIndex !== count
    || typeof snapshot.completed !== 'boolean') invalid('checklist progress');
  const complete = count === TOTAL_ACTIONS;
  if (snapshot.completed !== complete || (snapshot.status === 'complete') !== complete
    || (snapshot.currentStep === null) !== complete) invalid('completion state');
  if (snapshot.status === 'idle' && count !== 0) invalid('idle session contains completed actions');
  if (snapshot.currentStep && snapshot.completedStepIds.includes(snapshot.currentStep.id)) invalid('current action is already complete');
  const released = snapshot.completedStepIds.includes('csm-release-probe');
  if ((snapshot.attachment === 'released') !== released
    || (released && snapshot.attachmentEvidence !== 'modeled-mechanical-release')) invalid('docking release evidence');
  if (!Array.isArray(snapshot.events) || snapshot.events.length > 4096
    || snapshot.revision !== snapshot.events.length) invalid('acknowledgement revisions');
  let advanced = 0, previousSequence = -1, wrongSelections = 0, crewReportCount = 0;
  for (const [index, event] of snapshot.events.entries()) {
    if (event.sessionId !== snapshot.sessionId || event.revision !== index + 1
      || !Number.isSafeInteger(event.sequence) || event.sequence <= previousSequence
      || !ROLES.has(event.role) || !KINDS.has(event.kind)
      || typeof event.advanced !== 'boolean' || !nonempty(event.action)
      || !Array.isArray(event.sourceIds) || !event.sourceIds.length || !event.sourceIds.every(nonempty)
      || !nonempty(event.locator)) invalid('action acknowledgement');
    const expectedAction = snapshot.completedStepIds[advanced] ?? snapshot.currentStep?.id;
    if (event.action !== expectedAction) invalid('action order does not match completed progress');
    const report = event.kind === 'crew-report';
    if (event.evidenceKind !== (report ? 'crew-report' : 'trainer-control')) invalid('action evidence classification');
    if (!event.advanced && event.kind !== 'select') invalid('only a selector can record a wrong setting');
    if (event.action === 'csm-release-probe'
      && (event.role !== 'CMP' || event.kind !== 'momentary' || event.value !== 'EXTD/REL' || !event.advanced)) invalid('release control');
    if (event.action === 'csm-probe-off' && event.advanced
      && (event.role !== 'CMP' || event.kind !== 'select' || event.value !== 'OFF')) invalid('probe power removal');
    if (event.advanced) advanced++;
    else wrongSelections++;
    if (report) crewReportCount++;
    previousSequence = event.sequence;
  }
  if (advanced !== count || snapshot.lastSequence !== previousSequence) invalid('acknowledged progress');
  if (!complete) return null;
  if (snapshot.completedStepIds[0] !== 'verify-entry'
    || snapshot.completedStepIds[24] !== 'csm-release-probe'
    || snapshot.completedStepIds[25] !== 'csm-probe-off'
    || snapshot.completedStepIds[26] !== 'confirm-release'
    || snapshot.completedStepIds[27] !== 'inspection-handoff') invalid('undocking handoff order');
  return freeze({
    schemaVersion: 1,
    reportType: 'APOLLO 11 UNDOCKING TRAINING SUMMARY',
    classification: MODE,
    crewRoster: crew.roster.map(seat => ({ ...seat })),
    humanParticipation: setup.humanParticipation,
    completedActionCount: count,
    eventCount: snapshot.events.length,
    wrongSelections,
    crewReportCount,
    controlCommandCount: snapshot.events.length - crewReportCount,
    sourceSha256: snapshot.definitionSha256,
    nextOperation: 'Relative-motion management and Eagle inspection',
    flightSimulationCompleted: false,
    originalAgcExecuted: false,
    scope: 'Selected crew reports and modeled cockpit controls. Docking release is a procedure-model state; physical separation, inspection and later flight maneuvers have not been simulated.',
  });
}
