# Frontend integration contract

This document distinguishes implemented application interfaces from future
integration needs. It describes a recorded Phase 10 guidance UI and a separate
existing live attitude service. There is no implemented live P63 mission API,
WebSocket stream, descent plant, multiplayer server or AI crew endpoint.

## Implemented sources

| Source | Consumer | What it establishes |
|---|---|---|
| `frontend/dist/data/guidance.json` | RecordedTraceProvider | Verified recorded synthetic pre-ignition observations and initialized geometry |
| `GET /api/bootstrap` | LiveBackendProvider discovery; existing LiveClient | Whether this loopback server enables its bounded live attitude service |
| `GET /api/status` | Read-only discovery/status; existing LiveClient polling | Latest actual session state, possibly idle with no sample |
| `GET /api/record` | Existing live lab download | Token-protected current live gateway record and provenance |
| Existing POST routes below | Existing live attitude lab only | Start, bounded pilot deflection, stop |

Static files are served from `frontend/dist/` by `frontend/serve.py`. The
guidance provider does not need a native process or remote service. The original
exporter verifies evidence before the normal launcher serves the data; browser
schema validation is an additional boundary check, not a substitute for running
the integrity-checking launcher.

## Recorded artifact contract

`guidance.json` has `schemaVersion: 1` and exact mode
`RECORDED AUTHENTIC EXECUTION REPLAY`. It contains exactly the expected cases
`nominal`, `altitude-16km` and `missing-site`. Each case has ordered `frames` and
`events`, source fingerprints, initial state, observed final result and a
bounded duration. No frame after that duration is extrapolated.

| Field | Meaning and units | Missing/held behavior |
|---|---|---|
| `cycle` | Native CPU-call index | Not a wall timestamp |
| `t` | Recorded CPU elapsed seconds, `cycle × 12/1024000` | Replay cursor selects preceding observation |
| `dsky.PROG/VERB/NOUN/R1/R2/R3` | Strings decoded from retained output `010` relays | Preserve blanks and asynchronous partial updates |
| `observedClockSeconds` | Observed AGC mission clock, seconds | `null` before observation; then held |
| `signedTimeToGoSeconds` | Original signed guidance quantity, seconds | `null` until observed; preserve negative sign |
| `ignitionTimeSeconds` | Absolute AGC-computed ignition epoch, seconds GET | Not a remaining-time countdown |
| `ignitionLeadSeconds` | TIG minus mission clock at that solution observation | Held diagnostic, not continuous countdown |
| `rootCount` | Number of observed root-result checkpoints | Does not by itself prove completed guidance |
| `alarms` | Retained alarm-register history, octal strings | Not an annunciator decoding |
| `stage` | Source-event description of recorded execution | May differ momentarily from the asynchronous DSKY digits |
| `observationSources` | Per-quantity retained source pointers | Preserve older pointer for a held value |
| `source.rawLine` | One-based line in decompressed source JSONL | A trace pointer, not a browser-generated measurement |

Case fingerprints include compressed/raw trace and configuration/observer-map
SHA-256 values. Source paths are repository-relative. Root observations and
ignition values are produced by the original Luminary instructions; derived
metadata never replaces those calculations.

Geometry is an explicitly different data category:

| Field | Unit/frame/epoch |
|---|---|
| `positionM[3]` | Metres, Moon-centered basic REF inertial, epoch `epochSeconds` = 120 s |
| `velocityMps[3]` | Metres/second, same frame and epoch |
| `landingSiteMoonFixedM[3]` | Metres, initialized Moon-fixed site; `null` for missing-site control |
| `landingSiteBasicRefAtTlandM[3]` | Independent transpose-matrix illustration in basic REF at TLAND 784.4 s; not a propagated observation |
| `lunarRadiusM` | Documented synthetic lunar reference radius, metres |
| `altitudeM`, `speedMps` | Independent magnitude diagnostics of the supplied state |

The viewer displays `x = REF X / lunarRadius` and `y = −REF Z / lunarRadius`.
The initial velocity arrow uses only its X–Z direction. No spacecraft motion is
computed, and spacecraft/site epochs must remain visible. The screenshot is a
static educational illustration even while recorded AGC observations replay.

## Typed frontend domain boundary

The frontend's mission-domain types carry execution mode, source, time,
availability, units and coordinate frame where applicable. They are frontend
adapters, not claims that these models are serialized by the Python service.
The runtime remains ES modules; JSDoc imports and `.d.ts` declarations allow
TypeScript checking as a development step without requiring a browser compiler.

`frontend/dist/mission-types.d.ts` declares the adapter models and
`frontend/dist/mission-provider.mjs` implements them. Mode values are
`VERIFIED_RECORDED_EXECUTION`, `LIVE_AGC_EXECUTION`,
`STATIC_EDUCATIONAL_ILLUSTRATION` and `LIVE_BACKEND_STATUS`; availability is
`AVAILABLE`, `UNAVAILABLE` or `PLANNED`. Availability of a service is not proof
that an active native mission exists.

| Model | Contract |
|---|---|
| `Observation<T>` | `value: T or null`, `unit`, `availability`, nullable evidence `source`, plain-language `description` |
| `EvidenceSource` | Retained `tracePath`, raw trace `sha256`, native `cycle`, one-based `rawLine`, classification `AGC_RECORDED`, `INITIALIZED_MISSION_INPUT` or `INDEPENDENT_PROJECTION` |
| `MissionSnapshot` | Scenario identity, recorded mode, source, bounded `replayElapsedSeconds`, `observedFrameSeconds`, exact held `frame`, mission clock, geometry, guidance, DSKY, elapsed events and capabilities |
| `SpacecraftState` | Source/epoch/frame-stamped position, velocity and site observations; synthetic lunar radius; `propagation: 'NONE'` |
| `DSKYState` | Exact retained digit strings and source; indicator/sign lights explicitly `UNAVAILABLE` |
| `MissionEvent` | Actual retained event/cycle/time/source plus recorded mode and evidence pointer |
| `LiveBackendState` | `LIVE_BACKEND_STATUS`, actual session status/id, availability/message and optional unchanged `attitudeFrame`; no fabricated Phase 10 guidance fields |
| `CommandResult` | `accepted: false`, `status: 'UNSUPPORTED'`, reason for the read-only provider |

RecordedTraceProvider loads and validates the retained artifact, selects an
existing scenario, returns the preceding actual observation for a replay time
and supplies completed recorded outcomes for comparison. It does not accept
arbitrary mission values or send commands. LiveBackendProvider reads the actual
bootstrap/status routes and reports capability availability. It is read-only:
its presence does not provide a second control implementation.

The concrete public API is:

```js
const recorded = await RecordedTraceProvider.load();
const scenario = recorded.getScenario('nominal');
const snapshot = recorded.getSnapshot('nominal', 220); // recorded elapsed seconds
const outcomes = recorded.compareScenarios();         // completed runs, not cursor state

const backend = new LiveBackendProvider();
const discovery = await backend.discover(); // GET bootstrap/status only
const status = await backend.getStatus();  // GET status only
```

The constructor validates, defensively copies and freezes recording data.
Snapshot observations preserve per-quantity sources, including the earlier
source for a held clock or ignition solution. Geometry carries its own initial
epoch, not the replay cursor. `discover()` does not publish the bootstrap token,
POST a start or acquire a control session. `command()` returns UNSUPPORTED
without any request. There is no automatic live-status polling stream in this
provider; callers can explicitly refresh the existing status route.

Absence remains absence. A missing clock, engine value, lamp state, landing-site
input or live sample must not become numeric zero, a nominal value, an unlit
lamp or a silently selected recording. A disconnected backend leaves recorded
playback usable with an explicit availability message. A corrupt or missing
recording produces an error/retry state rather than invented telemetry.

## Existing loopback HTTP API

These routes are verified in `frontend/serve.py` and
`backend/control_service.py`. They bind to `127.0.0.1`, not a public multiplayer
address. Accepted Host values are `127.0.0.1:<actual-port>` and
`localhost:<actual-port>`. If an Origin header exists it must exactly match
`http://<Host>`; mutating requests require it. Cross-site fetch metadata is
rejected. No cross-origin OPTIONS permission is provided.

### Read routes

| Route | Response | Access |
|---|---|---|
| `GET /api/bootstrap` | `liveEnabled`, per-process `token` when enabled, `axes: ['yaw','pitch']`, `deflectionCounts: 20`, `pulseLeaseSeconds: 0.5`, bounded-attitude `scope` | Local Host/same-origin rules |
| `GET /api/status` | `status`, `sessionId`, `message`, `frame`, `appliedSequence`, `summary` | Local Host/same-origin rules; token not required |
| `GET /api/record` | `session`, `pilotRequests`, `provenance`, `requestLog`, `scope` | Valid `X-Apollo-Token`; 409 if no session exists |

`status` can be `idle`, `initializing`, `ready`, `running`, `stopping`, `stopped`
or `fault`. Initially `frame` is `null`; that is not a zero-valued spacecraft.
Status is a copied sample from the single native-owner worker. A browser
connection state such as disconnected is presentation metadata, not an AGC
program state.

The live frame includes distinct CPU `cycle`/`sim_time`, `model_cycle`/
`physical_time`, readiness/execution observations, quaternion/model vectors,
CDU counts, actual output latches, applied jet latches, sensor queues, recent
events and optional errors. Physics can freeze while CPU/sensor queues settle;
these timestamps must not be collapsed into one clock. The existing
`frontend/dist/live.mjs` and `backend/native_session.py` define that older
attitude adapter. This milestone does not expose private raw frame internals as
a general mission API.

### Mutating routes retained for the existing attitude lab

All require a valid `X-Apollo-Token`, matching required Origin/Host,
`Content-Type: application/json`, a bounded 1–1024 byte Content-Length and no
transfer encoding. Duplicate JSON keys, nonfinite JSON numbers and extra or
missing fields are rejected. A replay-only server rejects mutation with 409.

| Route | Exact JSON request | Result |
|---|---|---|
| `POST /api/session/start` | `{}` | 202; new session starts source verification and authentic startup |
| `POST /api/input` | `{"sessionId":"…","sequence":1,"yaw":0,"pitch":1}` | 202; bounded pilot intent queued, not proof of AGC consumption |
| `POST /api/session/stop` | `{"sessionId":"…"}` | 202; neutralizes inputs, freezes model and drains sensor queues |

Only integer −1, 0 or +1 is accepted per yaw/pitch axis. Sequence is an integer
from 0 through 2³¹−1 and must strictly increase for the matching session.
Readiness must be established before control; stale identities/sequences are
rejected. Non-neutral inputs have queue/rate bounds. Neutral releases cancel
pending inputs. The native lease is 42,666 CPU calls (approximately 0.5 s),
with a separate 0.55 s wall freshness guard. API bootstrap rounds this intent
to 0.5 s; it is not an exact promise of network or consumption latency.

The worker maps deflections to documented RHC ports `0167` (yaw) and `0166`
(pitch), ±20 counts plus channel `031` switches. Original software reads them
through its channel `013` gate and computes actual RCS `005`/`006` outputs.
Modern external attitude/sensor models apply those outputs and return counter
operations. The UI cannot write flight memory, force readiness, set actuator
packets or assign authoritative attitude/rates.

Live readiness waits with the CPU paused until a first deflection. Subsequent
execution is bounded to approximately 11.7 s of interactive simulated time.
Stopping is not proof of stability: neutral is a controller input, and empty
sensor queues do not mean zero angular velocity. The existing live lab owns
keyboard/pointer release and lease-refresh behavior; new mission discovery
does not start a run or send a release request.

## Capability gating and future crew

Recorded Phase 10 guidance is available only after its artifact validates.
Static initialized geometry is labeled as an illustration. Live attitude
availability depends on actual bootstrap discovery and does not imply live
guidance. Complete DSKY keys/lamps, engine response, translational flight,
multiplayer and AI remain unavailable.

| Capability ID | Implemented availability/mode |
|---|---|
| `guidance-replay` | AVAILABLE / VERIFIED_RECORDED_EXECUTION after successful recording load |
| `initial-geometry` | AVAILABLE / STATIC_EDUCATIONAL_ILLUSTRATION |
| `live-attitude` | Discovered from the existing service; LIVE_AGC_EXECUTION describes its scope only when enabled |
| `live-guidance` | UNAVAILABLE |
| `propulsion` | UNAVAILABLE |
| `multiplayer` | PLANNED |
| `ai-crew` | PLANNED |

The planned crew domain contains exactly three roles:

| Role | Person | Future scope |
|---|---|---|
| Commander | Neil Armstrong | Lunar Module command |
| Lunar Module Pilot | Buzz Aldrin | Lunar Module guidance/instrument support |
| Command Module Pilot | Michael Collins | Command Module in lunar orbit |

No role has an active human or AI participant in this frontend milestone.
Planned roles do not grant command authority, create shared sessions or simulate
communications. The historical Command Module Pilot is not represented as a
third Lunar Module pilot.

## Missing integrations — proposed needs, not implemented routes

No URLs or live behavior are invented for these needs:

1. A live initialized P51/P27/P63 mission session with source-stamped guidance
   observations and bounded validated commands.
2. Complete DSKY output observations: digits, register signs, annunciators and
   flash timing, plus acknowledged validated key-input actions.
3. Authoritative 3D translational/propulsion state with frames, units, physical
   timestamps, validity and explicit synthetic/historical provenance.
4. Exactly three participant assignments, role permissions, communication and
   command acknowledgements for a real shared mission.

Polling currently reads existing HTTP samples. A future stream, if implemented,
must define order, reconnect and stale-sample behavior before the UI uses it.
No WebSocket fallback or replay-as-live mechanism exists. AR/3D assets are also
deferred and would be optional visual models, not flight simulation proof.

See [the architecture guide](FRONTEND_ARCHITECTURE.md) for launch commands and
the final frontend receipts under `docs/frontend-evidence/` for actual checks.
