# Apollo 11 chronological campaign: integration boundary

The mission reference now begins in **Earth parking orbit** and follows three
historical goals: reach lunar orbit, descend to the Moon, and return to Earth.
The return ends with atmospheric entry and splashdown. Apollo 11 did not perform
Earth orbital capture on its return. The source-reviewed sequence, historical
control authority and citations are in [the chronology report](APOLLO11_CHRONOLOGY.md)
and `frontend/dist/data/apollo-campaign.json`.

The chronological campaign is **historical reference navigation**. Its tutorial
can review the chapters and inspect retained original-computer observations.
It does not execute an Earth-to-Moon-to-Earth flight, issue hidden spacecraft
commands, or turn a reference chapter into a completed maneuver. A perfect
original-AGC-controlled whole-mission game is not supported by the current
backend. Existing interactive training and the separate educational landing
laboratory remain available with their own source labels.

## Start and presentation

From the repository root:

```sh
make play
```

Open `http://127.0.0.1:4173/campaign.html`. For the chronological guided tour,
open `http://127.0.0.1:4173/campaign.html?tour=1`. Keep the server terminal open.
These pages are served from the existing `frontend/dist` application; no bundler
or npm installation is required to run them. Do not open HTML directly from disk.

`make play` invokes `python3 -B tools/final_demo.py --port 4173`. On a first
installation, prepare the pinned runtime with:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime --port 4173
```

If only the historical reference, recordings and Python checklist trainer are
needed, native preparation can be skipped:

```sh
python3 -B tools/final_demo.py --recorded-only --port 4173
```

The native attitude service and physical landing lab require their verified
dependencies. The reference pages and recording playback do not. If the port
is occupied by the current application, reuse it; otherwise select another
port explicitly with `make play PORT=4180`. The service binds to loopback.

## What each source establishes

| Source | Actual capability | Boundary |
| --- | --- | --- |
| `apollo-campaign.json` | Sixteen source-backed historical chapters, three goals, vehicles, configurations and control authorities | Historical reference; no flight telemetry or completed maneuvers |
| `guidance.json` | Original Luminary P51/P27/P63 execution, roots, ignition-time calculations and recorded DSKY digits | Synthetic initialization; no propagated descent or landing |
| `propulsion.json` | Exact original-execution events, crew-input transactions, engine output, retained physical samples and inertial feedback | Bounded synthetic fixed-attitude experiment; no achieved historical burn attitude, calibrated descent or landing |
| `/api/procedure/*` | Server-owned progress through 28 selected undocking checks and modeled switch/release actions | Interactive procedure training; no original AGC/AGS execution, sensor readback or physical separation |
| Existing native attitude routes | Fresh original Luminary yaw/pitch input, RCS output and bounded external attitude/sensor feedback | Bounded attitude fixture; no translational flight or arbitrary DSKY commands |
| Versioned shared mission routes | Three crew seats, messages, readiness, lab controls, measured outcomes and optional assistants | Educational landing lab with `authenticAGC:false`; not original Apollo guidance |

The campaign does not combine these separate states into an apparently
continuous flight. A successful educational landing does not complete the
historical lunar-landing goal. A reviewed historical chapter does not initialize
or advance the native emulator. Crew/AI configuration belongs to the supported
training experience; it does not create an original-AGC whole-mission service.

Historically, vehicle switches, docking mechanisms, crew decisions, launch
vehicle guidance and spacecraft computers had different authorities. Preserving
those authorities is more accurate than attributing every Apollo action to one
AGC. The catalog identifies the relevant crew, computer and control system for
each chapter. A fresh original CMC DSKY console is now implemented as a separate readiness
diagnostic; see [the CMC contract](EARTH_ORBIT_INTEGRATION.md). It does not expose
initialized historical CSM flight or a Saturn LVDC interface.

## Implemented HTTP interfaces

These are verified routes in `backend/final_server.py` and the delegated
`frontend/serve.py`. The campaign introduces **no new flight endpoint** and no
WebSocket. All mutations retain the existing same-origin, token, schema and
sequence checks.

| Method and route | Meaning |
| --- | --- |
| `GET /api/bootstrap` | Bounded attitude and procedure capability discovery; local command token when enabled |
| `GET /api/status` | Current native attitude session, or idle with no frame |
| `GET /api/record` | Token-protected native session record |
| `POST /api/session/start` | Start a fresh bounded native attitude experiment |
| `POST /api/input` | Queue supported yaw/pitch input for that native session |
| `POST /api/session/stop` | Request neutral input and stop/settle the native experiment |
| `GET /api/procedure/status` | Current modeled undocking-checklist state without starting it |
| `POST /api/procedure/start` | Start a new independent procedure-trainer session |
| `POST /api/procedure/action` | Validate crew station, current action, value, sequence and revision |
| `GET /api/v1/capabilities` | Shared educational lab capabilities, scenarios and crew roles |
| `POST /api/v1/missions` | Create an educational lab lobby with three configured crew seats |
| `POST /api/v1/missions/{id}/join` | Join an available human seat before flight starts |
| `GET /api/v1/missions/{id}` | Read the authoritative educational lab snapshot |
| `POST /api/v1/missions/{id}/command` | Validate a role-permitted lab lifecycle, actuator, checklist or message command |

The shared mission service explicitly advertises `authenticLanding:false`.
Its snapshots identify `mode: EDUCATIONAL_PHYSICS_LAB`,
`authenticAGC:false` and `hasAGCNavigationFeedback:false`. The three lab scenarios
start 150 or 300 metres above a synthetic lunar landing site; they cannot serve
as an Earth parking orbit state.

The procedure service explicitly sets `originalAgc`, `flightPhysics`,
`sensorReadback` and `historicalMissionClock` to false. Its release confirmation
is a crew report and its 3D separation is a static mechanical diagram.

Full request schemas and authentication/lifecycle details remain in
[the shared-mission contract](FINAL_INTEGRATION_CONTRACT.md),
[the undocking contract](FRONTEND_UNDOCKING.md), and
[the original frontend integration contract](FRONTEND_INTEGRATION_CONTRACT.md).
Those older documents describe their specific providers and delivery dates;
capabilities should not be inferred across modes.

## Browser providers and reference state

`frontend/dist/campaign-types.d.ts` declares the current catalog, reference state,
availability report and recorded-inspector public state. Runtime validation
remains independent of those declarations.

`frontend/dist/campaign-state.mjs` validates the source catalog and owns
immutable navigation state:

```js
let state = createCampaignState(catalog); // Earth parking orbit, no flight run
state = nextCampaignStage(state);
state = selectCampaignStage(state, 'powered-descent');
state = reviewCampaignStage(state); // reference-reviewed, never flight-executed
const availability = assessMissionAvailability(catalog);
```

The state exposes `currentStage`, `currentStageId`, `currentGoalId`, `cursor`,
`reviewedStageIds`, `stageStatuses` and `goalStatuses`. Navigation and review
cannot set `flightExecuted` or `missionCompleted`; both remain false. All three
flight goals remain `unavailable`. Even reviewing all sixteen chapters records
only reference review. Caller-supplied capability booleans, including
`physicsLab`, `authenticLanding` or specific stage names, cannot upgrade this
reference state into verified execution.

The read-only authentic observation providers remain:

```js
const guidance = await RecordedTraceProvider.load('./data/guidance.json');
guidance.getEvents('nominal');
guidance.getSnapshot('nominal', recordedSeconds);

const propulsion = await PropulsionTraceProvider.load('./data/propulsion.json');
propulsion.getEventSnapshot('connected', eventId);
```

`frontend/dist/agc-showcase.mjs` selects exact retained event IDs through the
propulsion provider. Its preparation and propulsion excerpts are parts of the
same synthetic Phase 12 experiment, not successive historical Apollo flights.
The showcase preserves raw-row identity even when two observations share a CPU
timestamp. It displays original channel-010 digit fields, their held source
rows and source fingerprints. DSKY signs and indicator lamps remain unavailable.
Before the first physical observation, no substitute spacecraft position is
shown. Three-dimensional rendering consumes recorded position/quaternion and
only previously observed trajectory samples; it does not propagate physics.

Automatic observation stepping is presentation pacing. CPU elapsed time,
external physical time and historical mission GET remain distinct. The showcase
sends no DSKY input or AGC command. Its completed-excerpt state means the selected
observations were viewed, not that the original mission maneuver completed.

## Missing full historical execution capabilities

The following explicit capability names are all false in
`VERIFIED_MISSION_CAPABILITIES`. Partial evidence links provide context and do
not satisfy them.

| Historical chapter | Required capability |
| --- | --- |
| Earth parking orbit | `historicalEarthParkingOrbit` |
| Trans-lunar injection | `historicalSaturnTli` |
| Transposition, docking and LM extraction | `historicalTranspositionExtraction` |
| Translunar coast | `historicalTranslunarCoast` |
| Lunar orbit insertion | `historicalLunarOrbitInsertion` |
| Lunar orbit | `historicalLunarOrbit` |
| LM activation/preparation | `historicalLmActivation` |
| Undocking and inspection | `historicalOrbitalUndocking` |
| Descent orbit insertion | `historicalDescentOrbitInsertion` |
| Powered descent and landing | `historicalAgcPoweredDescent` |
| Lunar surface operations | `historicalLunarSurfaceOperations` |
| Lunar ascent | `historicalLunarAscent` |
| Rendezvous and docking | `historicalRendezvousDocking` |
| Trans-Earth injection | `historicalTransearthInjection` |
| Transearth coast | `historicalTransearthCoast` |
| Earth entry and recovery | `historicalEarthEntryRecovery` |

The new cold-start CMC console supports real DSKY interaction, without a flown
checkpoint or operating IMU. There are no implemented whole-mission initialization, TLI, LOI, DOI, lunar
ascent, rendezvous, TEI or Earth-entry services. CSM original software, Saturn
guidance, validated mission state transitions and their physical integration
cannot be replaced by relabeling the LM's original Luminary recordings.

## Future execution adapter

A future typed flight adapter must be separate from this review state. At
minimum its snapshots and outcomes need a run identity, scenario/source mode,
authoritative timestamps and clock domains, units, coordinate frames, explicit
availability and provenance. Commands need their actual owner/control authority,
validated input contract and an acknowledgment that distinguishes queued input
from observed original-computer consumption. Stage completion needs a measured,
run-bound outcome with the conditions and evidence that establish achievement.

Historical flight state must be initialized and progressed by the backend.
Reference navigation, browser storage, a tutorial timer, successful API delivery,
an educational lab's touchdown or a broad capability flag cannot set a future
historical flight outcome. Add a new validated execution contract when the
backend supports it; do not add a frontend physics engine or fabricate missing
AGC outputs to connect the chapters.

## Focused verification

```sh
node --test frontend/tests/campaign-state.test.mjs frontend/tests/agc-showcase.test.mjs
node --check frontend/dist/campaign-state.mjs
node --check frontend/dist/agc-showcase.mjs
```

The focused checks pass **16 campaign-state tests** and **7 authentic-showcase
tests**. They cover the shipped source catalog, fixed historical order and
three-goal mapping, safe citations, immutable review state, fail-closed flight
gates, exact recorded event identity, separate command/plant/sensor observations,
missing physical data and disabled playback when evidence cannot load. These
23 tests are a scoped presentation/integration result, not the whole project's
test total and not a new authentic flight validation. No fresh AGC experiment
or full-mission flight was run to create this campaign.

## Next authentic integration work

1. Establish a backend-owned Earth-parking-orbit start: source-defined vehicle
   configuration, reference frames and clocks, a runnable Columbia CMC program,
   and validated crew/DSKY inputs. Demonstrate original P52 alignment and actual
   readbacks before enabling a flight-start control.
2. Add the correct departure authority and physical model for TLI, followed by
   CSM transposition/docking/extraction. A Luminary P63 replay cannot substitute
   for Saturn guidance or CSM hardware. Then integrate CMC coast navigation,
   correction maneuvers and lunar orbit insertion to establish the first goal.
3. Connect a validated lunar-orbit LM state to the existing bounded LM evidence:
   activation, physical undocking/inspection, DOI, radar/inertial feedback and
   P63/P64/P66 descent. Crew controls and achieved physical conditions must be
   demonstrated before the second goal can become executable.
4. Integrate LM ascent/rendezvous, CSM docking/transfer, TEI, coast and entry with
   the appropriate original software and crew hardware. Only a verified complete
   return outcome can satisfy the final goal. Keep the historical reference tour
   usable while each provider is added.
