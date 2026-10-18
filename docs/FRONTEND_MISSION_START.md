# Apollo 11 mission starting point and 3D integration

The starting chapter now includes a selected **interactive undocking procedure
trainer**, with 28 server-checked crew actions and modeled mechanical release.
Its command contract and source/physics boundary are documented in
[FRONTEND_UNDOCKING.md](FRONTEND_UNDOCKING.md). The historical flight remains
unavailable; the architectural description below still applies to the reference
and independent retained propulsion viewer.

The primary experience starts with **Eagle still docked to Columbia in lunar orbit, before undocking**. It combines a source-linked historical procedure reference with a separate inspection of the newly retained propulsion/navigation execution. **A player cannot yet execute the historical flight.** The historical chapter and the backend experiment have different initial conditions and must retain separate source and clock labels.

## Application entry points

| Page | Purpose | Data and interaction |
| --- | --- | --- |
| `/play.html` | Lunar-orbit mission starting chapter | Historical ACT-62–63 references, chronological mission chapters, Apollo hardware inspection, and separately labeled retained propulsion playback in 3D. |
| `/preparation.html` | Previous preparation evidence walkthrough | Retained synthetic P51/P27/P63 observations; reviewing a step does not execute it. |
| `/guidance.html` | Detailed pre-ignition evidence explorer | Three retained Phase 10 scenarios, original DSKY digit observations, guidance calculations, and static initial geometry. |
| `/attitude-lab.html` | Separate bounded attitude exercise | Existing live two-axis yaw/pitch input. Its modern control proxy does not reproduce the complete Apollo ACA or the historical mission. |

The main chapter is organized around **what the crew must do and why**, rather than target scores. Historical timeline navigation selects reference information; playback controls seek retained execution. Neither operation submits a cockpit command.

## Historical start and controls

The original [Apollo 11 LM Systems Activation Checklist](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf), ACT-62–63, places pre-undocking preparation at approximately 100:05 scheduled GET. It specifies **GUID CONT AGS**, both MODE CONT switches at **ATT HOLD**, all three ATTITUDE CONTROL switches at **PULSE**, and distinct enable settings for ACA/4 JET and TTCA/TRANSL. These are **historical checklist reference values**, not observed current backend switch positions.

The source-linked fourteen-step chronology proceeds through docked preparation, undocking, Columbia's separation maneuver, alignment, Eagle's DOI, P63 preparation, PDI, P64, P66, contact/shutdown, surface operations, ascent, rendezvous, and Earth return. Future chapters are marked as future information, not playable states. Selecting a chapter never teleports the physical model into it.

The controls inspection distinguishes:

- **ACA:** right-hand attitude controller; fore/aft is pitch, left/right is roll, and twist is yaw.
- **TTCA:** separate left-hand thrust/translation controller with a THROTTLE/JETS selector.
- **PGNS and AGS mode controls:** separate authority switches, distinct from the three per-axis MODE CONT/PULSE/DIR switches.
- **ROD switch:** commanded descent-rate increments in P66, with automatic engine throttle retained.
- **DSKY:** original program/data interface, distinct from attitude and engine hardware.

The sources, revision limitations, exact ACT references, and pinned Luminary software entry points are documented in [FRONTEND_APOLLO_OPERATIONS.md](FRONTEND_APOLLO_OPERATIONS.md). Historical metadata lives in `frontend/dist/data/apollo-operations.json`. It is not a backend capability announcement.

## What the new backend evidence establishes

The integrated source is the **sealed Phase 12 release evidence**, with Phase 11 PIPA/navigation work underneath it. It demonstrates bounded original P63 engine commands, external thrust/motion, real counter-operation feedback, original navigation consumption, and subsequent original throttle execution. It does **not** demonstrate an achieved burn attitude, calibrated LM-5 flight dynamics, the historical Apollo 11 trajectory, complete powered descent, P64/P66 flight, or landing. [Backend report](PHASE12_DESCENT_PROPULSION.md).

All four retained causal cases are available:

| Case ID | Physical engine | Sensor feedback | Meaning |
| --- | --- | --- | --- |
| `connected` | Connected | Connected | Original actuator outputs produce modeled force and motion; generated PIPA counts reach the AGC. |
| `sink` | Disconnected | Connected to a zero-thrust plant | Original commands remain visible, while delivered engine force and propellant consumption remain zero. |
| `no-feedback` | Connected | Disconnected | The physical plant moves, but generated PIPA counts are withheld from the AGC. |
| `repeat` | Connected | Connected | Separate native execution is byte-identical to `connected`. |

These are experimental controls. They are not four historical mission alternatives or new arcade objectives. The fixed-attitude plant, its assumed engine calibration, and its bounded horizon remain disclosed. An engine-enable request, an original ENGINE ON output, the external receiver's enabled state, commanded force, and delivered force are separate observations.

## Evidence adapter and presentation contract

`frontend/tools/export_propulsion.py` reads retained files without executing the AGC or modifying evidence. It verifies the release checksum inventory, individual trace fingerprints, observer identities, original rope identity, and passing retained analysis before writing the browser export at `frontend/dist/data/propulsion.json`. It decodes actual channel 010 DSKY output with the retained decoder. The release seal identifies 468 checked files; original evidence stays in `docs/phase12-release-evidence/`.

`frontend/dist/propulsion-provider.mjs` exposes `PropulsionTraceProvider`:

```js
const provider = await PropulsionTraceProvider.load('./data/propulsion.json');
const cases = provider.listCases();
const snapshot = provider.getSnapshot('connected', executionSeconds);
const path = provider.trajectoryThrough('connected', executionSeconds);
// Event inspection also respects raw-row order within a CPU cycle.
const eventState = provider.getEventSnapshot('connected', eventId);
const eventPath = provider.trajectoryThrough('connected', eventState.replay.seconds,
  {rawLine: eventState.source.rawLine});
```

`getSnapshot` returns the actual preceding observation at the requested CPU-call time. It does not interpolate telemetry, extrapolate state, or calculate motion. Its domain objects include:

Ordinary playback uses the retained state at the end of an observed CPU cycle.
Event stepping instead uses one of 715 exact `eventSnapshots`, captured at the
event's raw trace row. This preserves individual cockpit packets, engine outputs,
sensor operations and physical initialization even when several rows share a
timestamp. Trajectory and navigation inspection use the same raw-row ceiling.

| Field | Meaning |
| --- | --- |
| `mode` | `VERIFIED RECORDED EXECUTION` |
| `replay` | Cursor seconds, duration, units, and an explicit CPU-call clock label |
| `frame` | DSKY fields, observed program, stage, receiver observation, crew discretes, PIPA counts, and source references |
| `spacecraft` | Nullable retained position, velocity, scalar-first body-to-REF quaternion, physical clocks, mass, fuel, force, engine states, units, and frames |
| `source` | Raw trace line, cycle, trace path, and SHA256 |
| `capabilities` | Explicit recorded availability and unavailable live procedure/control features |

`command()` returns `accepted: false`, status `unavailable`, and a reason. It sends no command. `observedCockpitSignals()` decodes only retained hardware assertions; an absent AUTO assertion does not establish whether the physical toggle was in ATT HOLD or OFF. UI readbacks must preserve this distinction.

`frontend/dist/mission-flight-types.d.ts` documents the recorded cockpit/physical observation shape. The existing Phase 10 `RecordedTraceProvider` in `mission-provider.mjs` remains a separate adapter; its static geometry must not be confused with the new physical observations.

## Three clocks, different meanings

| Clock | Meaning | Must not imply |
| --- | --- | --- |
| Historical GET | Reference chapter timing in Apollo 11's chronology | The synthetic experiment has reached that historical flight time. |
| Execution time | Native CPU calls multiplied by `12 / 1024000` seconds | Wall time, complete flight duration, or historical GET. |
| Physical model time | Retained `physicalTimeSeconds`, with separately exported elapsed physical time | CPU time or historical mission time. |

The physical plant begins partway through native execution. Before its first observation, physical position, velocity, and attitude are unavailable. Holding a preceding observation must retain its source cycle rather than assigning the replay cursor as a new measurement time. Case-to-case durations are independently bounded by their own recordings.

## Replaceable 3D viewer

`frontend/dist/mission-3d.mjs` accepts supplied state through `createMissionRenderer(canvas).draw(state)`. Inputs include `available`, `positionM`, `velocityMps`, `quaternion`, `lunarRadiusM`, and `trajectoryM`. `setView('vehicle' | 'orbit')`, camera orbit, zoom, and reset affect presentation only. The renderer can be replaced without changing the provider or the backend.

The viewer presents Moon-centered basic REF coordinates and a scalar-first body-to-REF quaternion. It traces **retained sample positions only**, holds observations between samples, and contains no flight integration. The Moon is a reference sphere with abstract surface shading. The LM mesh is enlarged for visibility; model size and velocity-arrow length are presentation choices, with scale disclosures. The arrow indicates direction, not speed magnitude.

The docked historical composition is explicitly an illustration. It supplies neither a historical CSM state nor an attitude/position measurement. It must not be displayed as live telemetry. WebGL is the primary implementation, with a projected Canvas fallback and explicit graphics availability.

The white upper assembly is **Columbia's command and service modules**; the lower
gold vehicle is **Eagle**. The crew docked at the command module's forward tunnel
and Eagle's upper hatch. Columbia is a separate spacecraft, not an additional
stage of the LM. Its schematic cone, service cylinder, radiator panels, RCS pods,
engine bell and proportions are informed by the
[Apollo 11 press kit](https://solarsystem.nasa.gov/system/downloadable_items/2920_Apollo_11.pdf),
pages 86–88. This is a recognizable functional illustration, not an exact CAD
model or historical position/attitude measurement.

## Verified existing service routes

Inspection of `frontend/serve.py` verifies these HTTP routes. There is **no WebSocket endpoint** in this service and no newly exposed live propulsion service.

| Method / path | Actual scope |
| --- | --- |
| `GET /api/bootstrap` | Existing live-enabled flag, per-server token, supported axes `yaw` and `pitch`, fixed deflection counts, lease duration, and bounded-attitude scope. |
| `GET /api/status` | Existing control-service snapshot. |
| `GET /api/record` | Existing bounded-attitude session record; requires `X-Apollo-Token`. |
| `POST /api/session/start` | Empty JSON object starts the existing bounded attitude session. |
| `POST /api/input` | Exact fields `sessionId`, `sequence`, `yaw`, `pitch`; existing two-axis bounded controller input. |
| `POST /api/session/stop` | Exact `sessionId` field stops that session. |

Mutations require matching same-origin loopback requests and the token. Replay-only mode rejects them. Static `data/propulsion.json` is an evidence artifact, not a live API endpoint. `/api/input` must not be reused for TTCA, ROD, engine, undocking, or arbitrary DSKY commands.

## Missing integration contracts

These are **required capabilities to design**, not invented URL routes:

1. A validated historical orbital checkpoint with mission epoch, GET, physical and AGC state, alignment, landing reference, CSM state, and provenance.
2. Authoritative cockpit state, PGNS/AGS authority, switch interlocks, command acknowledgments, and actual readbacks.
3. Docking/undocking and separation mechanics, followed by an Apollo 11-specific DOI sequence.
4. Three independent ACA axes, calibrated ranges, detent, pulse/direct/hardover paths, supported-mode behavior, and limits.
5. TTCA translation/throttle authority and selector state, ROD edge commands, and validated engine start/stop/arm/abort paths.
6. Arbitrary live DSKY key delivery and release with original output readback, rather than scripted display responses.
7. Validated attitude, propulsion, inertial sensing, navigation, landing radar, and terrain/contact integration for each available flight chapter.

The frontend must discover these capabilities and enable each operation only when the service advertises and validates it. An attractive cockpit is not proof of its electrical behavior or flight fidelity.

**Columbia needs its own flight computer and vehicle systems.** Apollo 11's command module used **Comanche 055, also called Colossus 2A**, while Eagle used Luminary 099. The original [Comanche assembly listing](https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html) identifies the command-module software and its 055 revision; the [maintainer's mission/version inventory](https://www.ibiblio.org/apollo/Colossus.html) confirms that 55, rather than the earlier manufactured 51, flew on Apollo 11. Future CMP, CSM separation, rendezvous, Earth-return, and entry chapters therefore need a separately validated CSM computer state and CSM propulsion/control integration, with interactions between both vehicles where relevant. The current Luminary backend does not execute Columbia's flight software. Their presence in the chronology is a roadmap, not implemented CSM capability.

## Startup and checks

Run from the repository root:

```sh
make play
```

Open `http://127.0.0.1:4173/play.html`. This prepares the pinned native runtime for the existing optional live attitude lab; the main historical reference and propulsion playback read their retained exports.

If that port already has a server:

```sh
make play PORT=4180
```

Then open `http://127.0.0.1:4180/play.html`. Do not open the HTML through `file://`; ES modules and evidence loading need the local HTTP origin.

For historical inspection and retained replay without enabling live input:

```sh
python3 -B frontend/serve.py --replay-only --port 4180
```

No native run is required to inspect the checked-in exports. Relevant verification commands are:

```sh
python3 -B frontend/tools/export_propulsion.py --check
make frontend-check
make test-frontend
make test-live
```

The first command rebuilds the export in memory and compares it with the retained browser artifact. `frontend-check` checks the guidance export and module syntax; `test-frontend` runs Python evidence/presentation tests and browser-domain JavaScript tests. `test-live` covers the unchanged existing live service. Actual run results and visual evidence should be retained with this frontend milestone; these commands alone are not a claim that a historical landing has passed.

## Next increments

First establish the historical checkpoint and switch/DSKY contracts. Then implement one exact pre-undocking action with a native acknowledgment, a source-backed checklist transition, and before/after readback. Add validated separation and DOI before enabling PDI. Only then join the attitude and translational loops with the correct propulsion, sensor, and radar behavior for P63/P64/P66. Keep surface, ascent, rendezvous, and Earth return in chronology as future chapters until independently demonstrated.
