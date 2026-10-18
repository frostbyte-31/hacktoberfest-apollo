# Frontend integration contract

The new primary `/play.html` adds a source-linked historical lunar-orbit reference
and sealed Phase 12 recorded propulsion adapter. Its exact fields, clocks, source
pointers, capability gates, four causal cases and missing cockpit/mission APIs
are specified in [the current mission integration contract](FRONTEND_MISSION_START.md).
The subsequent undocking increment adds three implemented **procedure-training**
routes: `GET /api/procedure/status`, `POST /api/procedure/start` and
`POST /api/procedure/action`. These own modeled checklist/release state and do
not expose AGC, sensor or flight capability. Their exact contract is in
[FRONTEND_UNDOCKING.md](FRONTEND_UNDOCKING.md). The Phase 10 and bounded-attitude
contracts below remain implemented and unchanged.

This contract distinguishes the **implemented interfaces** found in the repository from **proposed future integration work**. The Phase 10 mission experience consumes verified recordings. The separate existing live service supports bounded yaw/pitch attitude experiments; it does not expose live P63 mission guidance, descent, landing, multiplayer or an AI crew.

## Inspected implementation

The existing frontend is a dependency-free browser application: HTML, CSS, native JavaScript modules, SVG and an independent Canvas spacecraft renderer. There is no React, TypeScript build pipeline, npm application dependency graph or bundler to preserve. `frontend/serve.py` serves `frontend/dist/` on loopback using the Python standard library. `guidance.html` is the Phase 10 entry point; `index.html` retains the earlier attitude laboratory.

The relevant boundaries are:

| Boundary | Implemented source | Scope |
|---|---|---|
| Phase 10 recording exporter | `frontend/tools/export_guidance.py` | Read-only verification and transformation of sealed native execution evidence |
| Phase 10 recorded data | `frontend/dist/data/guidance.json` | Version 1 recording for exactly the three retained cases |
| Replay state functions | `frontend/dist/guidance-state.mjs` | Structural validation, held observations, bounded playback and static projection |
| Typed mission adapter | `frontend/dist/mission-provider.mjs`, `mission-types.d.ts` | Immutable normalized observations, capability discovery and planned crew metadata |
| Static spacecraft view | `frontend/dist/spacecraft-view.mjs` | Independent SVG rendering of initialized 3D state, with missing-geometry handling |
| Existing attitude replay | `frontend/dist/data/replay.json`, `replay.mjs` | Phase 7 recorded attitude/feedback experiments; a separate data schema |
| Existing live browser client | `frontend/dist/live.mjs` | Token bootstrap, HTTP polling, bounded rotational controller inputs |
| Existing local HTTP adapter | `frontend/serve.py` | Static files and the routes below |
| Existing live service | `backend/control_service.py`, `backend/native_session.py` | Serialized native execution and authoritative external attitude-model samples |

No WebSocket or Server-Sent Events interface is implemented in these application sources. The live client polls `/api/status` approximately every 100 ms while a session is active. Native ringbuffer transport and the retained harnesses are internal experiment infrastructure, not browser APIs.

## Verified HTTP routes

Paths are relative to the loopback server, normally `http://127.0.0.1:4173`. The server binds to `127.0.0.1`, checks local Host and same-origin access, and does not provide a remote or multiplayer service.

| Method / path | Request | Actual response and meaning |
|---|---|---|
| `GET /guidance.html` | None | Phase 10 recorded experience |
| `GET /data/guidance.json` | None | Static, generated Phase 10 recording; not a live mission snapshot |
| `GET /` | None | Existing attitude laboratory |
| `GET /data/replay.json` | None | Static Phase 7 attitude recordings |
| `GET /api/bootstrap` | None | `liveEnabled`, nullable `token`, `axes: ["yaw", "pitch"]`, `deflectionCounts: 20`, `pulseLeaseSeconds: 0.5`, and bounded-attitude `scope` |
| `GET /api/status` | None | Current local attitude session, or `idle` with no frame |
| `GET /api/record` | `X-Apollo-Token` header | Session snapshot, pilot requests, provenance and gateway log path; 409 if no session exists |
| `POST /api/session/start` | `{}` | 202 with session state; native preparation/startup begins asynchronously |
| `POST /api/input` | `{ "sessionId": string, "sequence": integer, "yaw": -1\|0\|1, "pitch": -1\|0\|1 }` | 202 acknowledgement: input is queued; this does not establish AGC consumption |
| `POST /api/session/stop` | `{ "sessionId": string }` | 202 with session state; requests neutral inputs, frozen physics and sensor-queue settlement |

All POST routes require the bootstrap token, matching Origin, `application/json`, an exact request schema and a bounded nonempty body of at most 1,024 bytes. `sequence` must increase for each input within a session and lie between 0 and 2³¹−1. Unsupported axes/fields are rejected. Nonneutral requests are rate/queue limited. Neutral releases cancel pending input. The interface returns JSON `{ "error": string }` for rejected requests; errors include 400 invalid schema/input, 403 origin/token failure, 409 disabled/conflicting/not-ready session, 429 busy controller queue and 404 unknown API route.

`python3 -B tools/demo/demo.py launch` starts this server with `--replay-only`. In that mode `liveEnabled` is false, the token is null and POST control operations are unavailable. Merely serving the existing API does not establish mission-guidance capability.

### Existing live attitude session shape

`GET /api/status` returns `{ status, sessionId, message, frame, appliedSequence, summary }`. Server statuses are `idle`, `initializing`, `ready`, `running`, `stopping`, `stopped` and `fault`; the browser additionally uses `disconnected` after a failed request. `frame` and `summary` can be null. Controls require both ready/running session status and original native readiness, including P00, ACCSOKAY, clear original inhibition bits and clear FAILREG words.

The native frame includes CPU `cycle`, CPU `sim_time` in seconds, `model_cycle`, authoritative model `physical_time` in seconds, `freeze_cycle`, `model`, `cdu`, source output words (`jets`, `actual_output_jets`), decoded `thrusters`, original `execution` readbacks, RHC readbacks, control intent, counters, queue lengths, events, errors and a trace path. `model.quaternion` is scalar-first, body-to-stable; `model.omega` is degrees/second and `model.gimbals` is degrees, as emitted by the retained attitude model. `torque_Nm` and `alpha_rad_s2` identify their SI units explicitly. Body X/P, Y/Q and Z/R correspond to yaw, pitch and roll; O/I/M are IMU gimbals, not body Euler angles.

CPU time may advance while the physical model is frozen to settle sensor operations. Keep physical and CPU timestamps distinct. A settled queue is not evidence of stability. No translational position, descent-engine thrust, fuel or landing state is provided by this live interface. The fixture supports bounded yaw/pitch inputs; independent roll, arbitrary alignment and sustained general flight remain unverified. A connection failure must release controls, mark the held sample stale/disconnected and retain its source mode.

## Phase 10 recorded data contract

The exporter checks the pinned Phase 10 seal and every file in its scope, original rope and DSKY decoder, compressed and raw trace fingerprints, observer addresses, execution/configuration dependencies and original analyzer assertions. The browser consumes the resulting derivative; playback does not execute the AGC. Browser schema validation is not a substitute for the exporter's evidence verification.

Sources are under `docs/phase10-evidence/runs/final-validation/`. These paths are provenance pointers in the JSON; the static server does not expose the whole repository. Original compressed/raw traces, source, emulator and historical experiment evidence remain unchanged.

### Document and scenario objects

| Field | Meaning |
|---|---|
| `schemaVersion` | Integer `1`; reject unsupported versions |
| `mode` | Exact retained value `RECORDED AUTHENTIC EXECUTION REPLAY` |
| `clock.secondsPerCpuCall` | `12 / 1024000` seconds per original native driver CPU call |
| `provenance` | Baseline/emulator revisions, rope and Phase 10 seal hashes, evidence/report pointers and verification description |
| `labels` | Source-specific explanations and limitations, retained with the recording |
| `cases` | Three scenario objects, selected by stable ID |
| `cases[].id` | `nominal`, `altitude-16km` or `missing-site` |
| `title`, `outcome`, `assumptions` | Human-readable classification; not new AGC memory values |
| `horizonCycle`, `durationSeconds` | Bounded native execution horizon and replay elapsed time |
| `initialState` | Documented 3D initialization plus an independent static site projection |
| `frames`, `events` | Chronological recorded observations and annotated native events |
| `result` | Final retained outcome summary; not telemetry for an earlier replay position |
| `sources` | Trace, map, configuration, analysis and execution paths plus available SHA-256 fingerprints |

### Observation objects

Every `frames[]` item has its own `cycle`, replay position `t`, triggering `source` and held values. `source.rawLine` is one-based in the **decompressed** JSONL trace. `observationSources` identifies the observation that supplied each held field and may point to an earlier cycle than the frame. Preserve that distinction when formatting provenance or age.

| Field | Units / encoding | Source and availability |
|---|---|---|
| `t` | Seconds, `cycle × 12 / 1024000` | Replay position, never a mission GET or host timestamp |
| `observedClockSeconds` | Synthetic AGC mission seconds | Original TIME2/TIME1 DP B28 centiseconds ÷ 100; null before a readback, then held |
| `dsky.PROG`, `.VERB`, `.NOUN` | Two digit-character positions | Original channel `010` relay digit decoder |
| `dsky.R1`, `.R2`, `.R3` | Five digit-character positions | Original relay digits; preserve spaces and unknown `?` characters |
| `signedTimeToGoSeconds` | Signed seconds | MPAC at original `ROOTSTOR_RESULT`: DP fraction × 2¹⁷ ÷ 100; null until observed |
| `ignitionTimeSeconds` | Absolute synthetic mission seconds | Original TIG at `IGNALGRT`, DP B28 centiseconds ÷ 100; null when unsolved |
| `ignitionLeadSeconds` | Seconds | TIG minus TIME2/TIME1 at the same solution checkpoint; held, not a ticking countdown |
| `rootCount` | Integer | Observed root results whose subsequent normal returns/TTF stores are separately verified |
| `alarms` | Array of five-character octal strings | Actual nonzero FAILREG words; startup history may persist |
| `stage` | Educational annotation | Based on recorded native events; not an invented AGC mode |
| `observationSources` | Nullable per-field pointers | Original cycle, raw line, symbol/routine and word/scale metadata where available |

Numeric fields never interpolate between observations. Unknown fields remain unknown; zero must not stand in for missing data. The DSKY can retain a preceding display while original software asynchronously updates relay packets. Program selection must not force the desired DSKY digits. Sign lamps and a complete authentic indicator-light state are not decoded by this recording adapter; a visual DSKY face must disclose unavailable lamps. FAILREG history is a separate observed quantity, not proof of a particular lamp state. Arbitrary DSKY key commands are unavailable.

DSKY visual/reference sources are [Virtual AGC's DSKY description and engineering-drawing links](https://www.ibiblio.org/apollo/yaDSKY.html) and [NASA's Apollo experience report: Crew station integration, Volume 2: Crew station displays and controls](https://ntrs.nasa.gov/citations/19750012347). They inform the Apollo-inspired panel layout; actual displayed digits still come exclusively from the retained decoder. A panel drawing or keyboard appearance does not establish a working live input interface.

`signedTimeToGoSeconds` preserves the original negative pre-target convention. It is not the ignition countdown. Startup 01107 and retained legacy 01520 must remain distinguishable from the missing-site control's actual 01406 guidance failure. Three provisional roots in the failed case do not establish a completed ignition solution.

### Initial geometry objects

`initialState` describes inputs accepted through original P27, rather than a continuously sampled navigation/physics stream.

| Field | Units / coordinate frame | Provenance / interpretation |
|---|---|---|
| `positionM` | Three metres, Moon-centered basic REF inertial | Actual P27-stored `RRECTLEM`, decoded at B27 |
| `velocityMps` | Three metres/second in the same frame | Actual P27-stored `VRECTLEM`, B5 metres/centisecond × 100 |
| `epochSeconds` | Synthetic mission seconds | P27 `TETLEM`; 120 s for retained cases |
| `landingSiteMoonFixedM` | Three metres, Moon-fixed | P27 `RLS`, or null when deliberately omitted |
| `landingSiteBasicRefAtTlandM` | Three metres, basic REF at nominal TLAND | Independent `M(TLAND)ᵀ × RLS` illustration; null if no site |
| `targetLandingTimeSeconds` | Synthetic mission seconds | Nominal supplied TLAND, 784.4 s; not an observed touchdown |
| `lunarRadiusM` | Metres | Documented spherical reference radius, 1,738,090 m |
| `altitudeM` | Metres | Independent `norm(positionM) − lunarRadiusM`; not a radar measurement |
| `speedMps` | Metres/second | Independent magnitude of the initialized velocity |
| `source`, `siteSource`, `transformSource` | Source pointers | Native P27 observation or documented independent transform configuration |

The 2D display projects X–Z from these 3D inputs. Spacecraft epoch 120 s and site epoch 784.4 s are different and must both be labeled. The circular orbit guide and vehicle/terrain artwork are educational illustrations; neither is a generated trajectory. Do not move the craft during guidance replay, infer a descent path, or treat screen coordinates as authoritative physics. Disclose any geometry exaggeration or diagram scaling.

### Retained scenario outcomes

These are independent actual runs, not a frontend approximation or general sensitivity model.

| Case | Initialized altitude / speed | Original result |
|---|---|---|
| `nominal` | 14,999.756 m / 1,672.319 m/s | Nine roots, TIG 360.29 s GET, held solution clock 221.26 s, lead 139.03 s; V06 N61 reached |
| `altitude-16km` | 16,000.158 m / 1,671.842 m/s | Nine roots, TIG 360.44 s GET, held solution clock 221.26 s, lead 139.18 s; V06 N61 reached |
| `missing-site` | Same initialized R/V as nominal, no RLS | Three provisional roots then original 01406; TIG/lead null; no V06 N61 review |

The 0.15 s TIG difference is a comparison of these two recorded cases only. A continuous altitude-to-ignition formula is not established. `allOriginalChecksPass` means the original checks passed for that experiment, including the expected failure in the negative control; it does not mean every scenario succeeded or a landing occurred.

## Frontend provider and capability boundary

The frontend-domain layer adapts available recordings and keeps raw AGC memory details inside evidence adapters. `frontend/dist/mission-types.d.ts` declares the browser-domain models; `mission-provider.mjs` supplies the runtime adapter without adding a TypeScript build requirement. The recording's provenance, units, source pointers and nulls survive normalization. `MissionSnapshot`, `SpacecraftState`, `GuidanceState`, `DSKYState`, `MissionEvent`, `MissionCapability`, `CrewMember` and `CommandResult` are browser-domain types, not asserted backend responses.

The implemented recorded-provider boundary is:

```js
const provider = await RecordedTraceProvider.load('./data/guidance.json');
provider.listScenarios();
provider.getScenario('nominal');
provider.getSnapshot('nominal', replaySeconds);
provider.getEvents('nominal');
provider.getCapabilities();
```

`provider.recording` exposes the validated version 1 recording for compatible presentation code. A snapshot normalizes source, mode, units, frame and availability while retaining the actual scenario/frame. `command()` returns unavailable for recorded execution. `LiveBackendProvider` explicitly represents unavailable Phase 10 live mission execution; it does not invent a mission API or connect the attitude-only routes as though they supplied guidance. Playback state remains in the presentation layer.

`frontend/dist/spacecraft-view.mjs` exports `renderSpacecraftView(root, initialState)`. It consumes initialized state through a narrow rendering boundary, without replay control, backend access or physical integration. A future 3D renderer can replace that view while keeping the mission provider unchanged.

The recorded provider supports case discovery/selection, held snapshots, bounded seek/play/pause/restart, event navigation and final-result comparison. Playback is local presentation. Its execution label is **VERIFIED RECORDED EXECUTION** and maps to the retained JSON mode above. Its geometry has the separate classification **STATIC EDUCATIONAL ILLUSTRATION**. A future live provider must label actual connected native execution **LIVE AGC EXECUTION**, identify its own validated capabilities and expose stale/disconnected state without silently substituting recordings.

Capabilities are enabled by verified support, not phase numbers or an attractive visible control. Current mission capabilities are recorded guidance, recorded DSKY digits, static initialization geometry, retained scenario comparison and educational content. Mission DSKY input, dynamic translational state, engine/throttle/fuel, powered descent, landing, crew communications and AI proposals remain unavailable. Existing bounded live attitude is its own explicitly scoped capability and screen; do not combine it with the Phase 10 initialization as though a coupled flight experiment had been run.

The current normalized metadata separates `availability` (`available`, `partial`, `unavailable`) from `validity` (`recorded-observation`, `initialized-input`, `derived-reference`, `unavailable`). Execution source and the timestamp's clock domain accompany each normalized state. Unknown DSKY characters produce a partial display; missing numerical observations are unavailable. A held value retains its original observation time. The future live contract additionally needs explicit stale/disconnected state and a session identity. Separate backend state from view state such as camera angle, selected explanation and replay cursor. A live command result must distinguish rejected, queued, applied at the interface, and observed by the original software when such evidence is available.

### Exactly three future crew roles

Prepare only these role slots: Commander Neil Armstrong (Lunar Module), Lunar Module Pilot Buzz Aldrin (Lunar Module), and Command Module Pilot Michael Collins (Command/Service Module in lunar orbit). Each may eventually support a human or AI occupant. Role labels and planned/unavailable state are metadata today; they do not create participants, permissions, messages or autonomous behavior. Collins must not appear as a third Lunar Module pilot. Future role-based commands need server-side permission checks and authoritative acknowledgements.

## Missing integration surfaces — proposals only

No routes in this section exist. Endpoint names are deliberately deferred until the backend owner agrees on transport, fidelity and lifecycle. The frontend must not issue speculative requests to them.

| Needed future capability | Contract to agree before enabling |
|---|---|
| Mission capability discovery | Supported modes/scenarios, command names, field validity, versions, authoritative time/frames and scope limits |
| Fresh initialized guidance runs | Validated synthetic input schema, immutable run identity, asynchronous execution/error lifecycle, evidence/provenance and result retrieval |
| Live mission snapshots/events | Sequenced samples, separate CPU/GET/physical clocks, bounded event history, reconnect/resume behavior and stale-data policy |
| Live DSKY keys and lamps | Supported keys, authentic press/release/handshake semantics, command acknowledgement, output channels and validated lamp/sign decoding |
| Dynamic spacecraft state | Authoritative position, velocity, attitude, rates and frame transforms with units, timestamps, integration method/coupling latency and supported axes |
| Descent propulsion | Actual engine discrete/throttle mapping, ignition status, mass/fuel, thrust/acceleration and validated physical coupling |
| Multiplayer crew | Exactly three authenticated role slots, server permissions, shared state sequence and communications/log persistence |
| AI crew assistance | Explicit proposal/review/execution lifecycle, role constraints, provenance and operational status; never fabricated agent activity |
| Contextual education | Source-linked explanations derived from available actual samples; educational experiments separated from verified runs |

For propulsion, rendering and education consume backend-owned dynamics. Do not create a competing frontend physics engine. A future optional 3D/AR model viewer can replace/supplement the independent renderer with clear visual-model labeling; it does not confer live simulation capability.

## Startup and verification

From the repository root:

```sh
python3 -B tools/demo/demo.py launch
# Open http://127.0.0.1:4173/guidance.html
# An occupied port is preserved; select another port explicitly:
python3 -B tools/demo/demo.py launch --port 4180
```

Python 3.9+ is sufficient for verified offline replay. The launcher verifies source artifacts and exports the deterministic JSON before starting replay-only serving. For exact launcher options use `python3 -B tools/demo/demo.py launch --help`. The existing optional attitude service is started separately with `python3 -B frontend/serve.py` and needs its documented native/runtime preparation; it is not needed for this mission replay.

```sh
python3 -B frontend/tools/export_guidance.py --check
python3 -B -m unittest discover -s frontend/tests -p test_guidance_data.py -v
node --test frontend/tests/guidance.test.mjs
```

Verification here concerns the evidence-derived presentation contract. Fresh original execution is a separate `make demo-reproduce` operation. Historical Phase 4–6 missing-evidence errors documented in `PHASE10_5_MVP.md` remain unresolved; do not count them as successful tests or replace missing files with new logs. Current implementation build/test commands and newly captured screenshots belong in the frontend architecture/report and its separate frontend evidence directory, without rewriting prior evidence.
