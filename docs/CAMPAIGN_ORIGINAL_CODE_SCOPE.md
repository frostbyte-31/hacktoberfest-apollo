# Campaign original-code scope

This is a source navigation and integration index for all 16 chapters in
`frontend/dist/data/apollo-campaign.json`. The machine-readable companion is
`frontend/dist/data/campaign-programs.json`. It identifies real program files,
symbols and source lines. It does **not** implement or enable those programs.

## What is executable today

The existing Earth-parking P52 task runs original Comanche software with a
stationary external IMU/optics fixture. The undocking trainer validates a selected
28-action checklist and a discrete modeled release. Retained Luminary recordings
demonstrate bounded synthetic guidance and propulsion experiments. These are
separate experiences; none proves a continuous Earth–Moon–Earth flight.

The current original P47 native probe reaches alarm **01204**. Its cause is
unresolved, so the monitor remains unavailable. This index locates the source;
it does not turn a failed probe into a playable burn or monitor.

## How to interpret source metadata

- `line` is the **original include-file source line**, not a printed listing page
  or the global assembler counter.
- Comanche snippets come directly from members of the retained corresponding-source
  archive. `sourceSha256` hashes the raw member bytes.
- Luminary snippets come from source fields in the retained assembly listing;
  assembler address and object-code columns are omitted. The second number before
  the colon identifies the include-file source line. `sourceSha256` is the raw
  source hash recorded by the existing pinned-source manifest, rather than a hash
  of the reformatted snippet. The listing's own hash is recorded separately.
- `listingUrl` opens the Virtual AGC transcription/scans navigation. `pinnedSourceUrl`
  fixes the repository revision used by the retained sources. A URL is not a claim
  that a program executes in this product.
- `localSource.path` is project-relative. An archive member is not a separately
  checked-out file; an assembly listing is not a complete source directory.
- Every snippet is at most eight lines. No historical source or evidence was edited.

The index is deliberately separate from backend capability discovery. Its
`requiredCapability` values name the catalog's complete-operation requirements.
`completeFlightAvailable` remains false for every chapter. `availability` only
describes an existing bounded task, recording, procedure, or source location.

## Correct computers and responsibilities

Saturn's nominal TLI belongs to the LVDC/LVDA and analog flight-control system.
An original Comanche P47 thrust monitor can monitor acceleration but cannot replace
that guidance stack. Comanche 055 has no Artemis P15; no P15 task is proposed.

Comanche P40 controls the CSM SPS. Luminary P40 controls the LM DPS. Likewise,
**Comanche P63/P64 are atmospheric-entry programs; Luminary P63/P64 are lunar-landing
programs**. They cannot be substituted because their display numbers coincide.

The docking probe, guarded separation switches, staging, ECS, EVA and parachute
systems have their own hardware and crew authority. Not every Apollo action goes
through an AGC. The separate AGS must not be presented as an executing simulation
merely because a selector or crew report mentions it.

Archived Luminary 099/0 is authentic original Apollo-era source, but the source
archive distinguishes it from the flown 099/1 release. Directory names and an old
header alone do not establish exact rope-image identity. Preserve the narrower
version claim. See [Luminary provenance](https://www.ibiblio.org/apollo/Luminary.html).

## Chapter source map and next integration

| Chapter | Original source entry points | Honest next integration |
| --- | --- | --- |
| Earth parking orbit | comanche055: P52 `P51-P53.agc` / `PROG52` L148; comanche055: P11 `P11.agc` / `P11` L167 | Preserve the completed original P52 task; add historical instrument/spacecraft initialization before extending flight. |
| Translunar injection | comanche055: P47 `P40-P47.agc` / `P47CSM` L392; comanche055: P11 `P11.agc` / `P11` L167 | Validate original P47 monitoring against acceleration inputs. It must not stand in for Saturn guidance or report TLI completion. |
| Retrieve Eagle | comanche055: RCS DAP `AUTOMATIC_MANEUVERS.agc` / `AUTOCONT` L59 | Connect the CSM DAP to documented handcontroller inputs and a separate backend docking mechanism/relative-motion model. |
| Navigate to the Moon | comanche055: P23 `P20-P25.agc` / `P23` L2769; comanche055: P30 `P30,P37.agc` / `P30` L127; comanche055: P40 `P40-P47.agc` / `P40CSM` L55 | Prove one original P23 sighting with external optics measurements; do not turn canceled maneuver opportunities into mandatory burns. |
| Brake into lunar orbit | comanche055: P30 `P30,P37.agc` / `P30` L127; comanche055: P40 `P40-P47.agc` / `P40CSM` L55 | Execute original CSM P30/P40 through a source-backed SPS fixture and verify cutoff before enabling a physical LOI outcome. |
| Establish the lunar parking orbit | comanche055: P30 `P30,P37.agc` / `P30` L127; comanche055: P40 `P40-P47.agc` / `P40CSM` L55 | Reuse a validated SPS integration with the LOI-2 configuration. Do not copy the second-bank operation from long LOI-1/TEI burns. |
| Activate Eagle and prepare guidance | luminary099: P51 `P51-P53.agc` / `P51` L1019; luminary099: P27 / V71 `UPDATE_PROGRAM.agc` / `V71UPDAT` L170; luminary099: P63 `THE_LUNAR_LANDING.agc` / `P63LM` L47 | Expose retained P51/P27/P63 calculations with their synthetic classification, then validate one live LM instrument task. |
| Undock and inspect Eagle | comanche055: P47 `P40-P47.agc` / `P47CSM` L392; luminary099: P47 `P40-P47.agc` / `P47LM` L364 | Keep the validated 28-action discrete trainer; add original computer bookkeeping and measured relative motion as separate verified increments. |
| Lower Eagle's orbit | luminary099: P52 `P51-P53.agc` / `PROG52` L135; luminary099: P40 `P40-P47.agc` / `P40LM` L121 | Verify original LM P40 with source-backed DOI inputs and backend propulsion/counter feedback before claiming the orbit is lowered. |
| Descend and land Eagle | luminary099: P63 `THE_LUNAR_LANDING.agc` / `P63LM` L47; luminary099: P64 `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc` / `STARTP64` L269; luminary099: P66 `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc` / `STARTP66` L152 | Extend the retained bounded original propulsion loop incrementally; prove radar, descent guidance, final control and contact separately. |
| Tranquility Base | luminary099: P57 `P51-P53.agc` / `P57` L2051 | Build a measured original P57 alignment task. Keep manual surface work separate from AGC program execution. |
| Launch from the Moon | luminary099: P12 `P12.agc` / `P12LM` L42 | Start with original P12 preparation in a source-backed ascent fixture; require measured engine/staging outcomes before awarding liftoff or orbit. |
| Rejoin Columbia | luminary099: P20 / P22 `P20-P25.agc` / `PROG20` L110; luminary099: P32 `P32-P35,_P72-P75.agc` / `P32` L213; comanche055: P20 `P20-P25.agc` / `PROG20` L106 | Validate two-vehicle navigation and one targeting maneuver before final docking; the actual Apollo 11 retract upset must not become a fabricated perfect flight. |
| Depart lunar orbit | comanche055: P30 `P30,P37.agc` / `P30` L127; comanche055: P40 `P40-P47.agc` / `P40CSM` L55 | Reuse a proven CSM SPS integration with TEI-specific initialization and checklist; Eagle does not perform this burn. |
| Navigate home | comanche055: P52 `P51-P53.agc` / `PROG52` L148; comanche055: P23 `P20-P25.agc` / `P23` L2769; comanche055: P61 `P61-P67.agc` / `P61` L79 | Connect return alignment and entry preparation to a verified return state; do not invent an Earth-orbit insertion or require canceled MCC-7. |
| Enter Earth's atmosphere and splash down | comanche055: P61 `P61-P67.agc` / `P61` L79; comanche055: P63 `P61-P67.agc` / `P63` L309; comanche055: P64 `P61-P67.agc` / `P64` L375 | Execute original Comanche entry guidance with measured atmospheric response. Keep automatic parachute sequencing separate from invented DSKY actions. |

## Historical control and chronology constraints

- TLI source-backed panel preparation is documented in
  `EARTH_DEPARTURE_PROCEDURE_RESEARCH.md`. It is not a validated Saturn burn.
- TDE uses CM/LV separation, RCS piloting and probe capture/retraction. Later lunar
  undocking uses EXTD/REL then OFF; do not interchange the mechanisms.
- LOI-2 used the A valve bank only. Do not copy the manual second-bank action from
  the long LOI-1 and TEI burns into every SPS task.
- Undocking/inspection precedes the CSM separation maneuver, LM alignment, DOI,
  and then PDI. DOI is not powered-descent ignition.
- The existing undocking trainer's source and prior-setup assumptions remain in
  `FRONTEND_UNDOCKING_RESEARCH.md`. Acknowledgments are not new sensor readbacks.
- Real P66 landing inputs require validated ACA/ROD mapping, radar, engine response
  and contact. A retained synthetic propulsion fixture is not the historical landing.
- Surface operations and EVA require crew/hardware models. P57 only addresses
  surface alignment.
- Eagle's ascent stage rejoins Columbia; crew/cargo transfer and LM discard precede
  TEI. The descent stage stays on the Moon. Collins remains in Columbia during landing.
- Some planned corrections were canceled, including MCC-1 and MCC-7. The campaign
  must not turn every planned opportunity into a required engine burn.
- Return ends in direct atmospheric entry and splashdown, not Earth-orbit insertion.

The primary documents/transcript links and locators remain in the campaign source
catalog and `APOLLO11_CHRONOLOGY.md`. Source comments or retrospective commentary
must be reconciled against program/manual/checklist evidence where they conflict.

## Before enabling any new flight task

Retain a provenance-checked initial state with units, frames and epoch. Map crew
controls and interlocks to the correct hardware authority. Run the original program
through actual inputs and outputs with the external vehicle/instrument model. Prove
causality using omitted/disconnected feedback and rejected/incorrect inputs. Only
then expose a backend capability and award a measured operation outcome. Source
availability, a successful key sequence and an animated model are insufficient.

The complete per-chapter missing-system lists are in the JSON. No proposed endpoint
is presented as implemented by this document.
