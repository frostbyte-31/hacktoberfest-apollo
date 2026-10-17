# 3D flight trainer integration contract

The playable milestone is a short **attitude acquisition game** backed by fresh
original Luminary 099 execution. The player rotates a 3D Lunar Module toward a
training target, reduces its rotation rate and holds the target. It reuses the
existing bounded live yaw/pitch fixture. It does not establish powered descent,
translation, engine operation or a lunar landing.

## Start and play

```sh
make play
```

Open <http://127.0.0.1:4173/play.html>. This target prepares the pinned Tcl runtime
and starts the existing live-capable server. The first runtime build needs the
locked source download, a C compiler and make. Python 3.9+ runs the server; the
browser renderer has no npm, CDN or external asset dependency. If port 4173 is
occupied, use `make play PORT=4180` and open that port's `/play.html`.

Equivalent explicit startup:

```sh
make runtime
python3 -B frontend/serve.py --port 4173
```

Select a challenge, arm a fresh AGC session and wait for original readiness.
Hold **D/A** for positive/negative yaw and **W/S** for positive/negative pitch, or
use the on-screen holds. Release returns the rotational hand controller to
neutral. Short inputs are useful: neutral does not instantly stop rotation.
Opposite input lets the player countersteer. Space releases all held controls.
Dragging and zooming change the viewing camera only.

The separate `make demo` entry starts a replay-only server. Its recorded guidance
explorer remains available, but its `liveEnabled: false` capability cannot run a
scored flight challenge. The game must show a clear unavailable state there.

## Actual backend boundary

No new endpoint or backend capability is introduced. The game reuses
`frontend/dist/live.mjs` and these implemented loopback HTTP routes:

| Route | Actual meaning |
| --- | --- |
| `GET /api/bootstrap` | Discover `liveEnabled`, yaw/pitch support and the process token |
| `POST /api/session/start` with `{}` | Start a fresh native library and the retained synthetic attitude model |
| `GET /api/status` | Read the worker's copied session and native frame; does not advance the AGC |
| `POST /api/input` | Queue `{sessionId, sequence, yaw, pitch}` directions, each integer −1/0/+1 |
| `POST /api/session/stop` | Neutralize input, freeze physical integration and settle actual native sensor queues |
| `GET /api/record` | Download the authoritative session, requests and provenance |

Mutation requests need the existing same-origin token and exact request schema.
An accepted controller request is queued intent, not proof of original AGC
consumption. The existing worker serializes native access, applies an expiring
input lease, and returns authoritative samples. The browser never writes AGC
memory, rates, torques, actuator outputs, sensor increments or orientation.

The source mapping is unchanged: yaw goes to normal analog input port `0167`,
pitch to `0166`, and source-mapped active-low controller switches to channel
`031`. Direction magnitude is the retained ±20 counts. Original Luminary's gated
read and actual RCS channel `005`/`006` outputs remain in the control path.

## Authoritative samples and clocks

`frame.model.quaternion` is a normalized, scalar-first `[w,x,y,z]`, right-handed
body-to-stable rotation. `frame.model.omega` is degrees/second. Body X is yaw,
body Y pitch and body Z roll in the retained fixture. IMU O/I/M gimbals are not
body Euler angles. Independent roll input is unavailable.

At readiness, CPU cycle **2,200,000** and CPU time **25.78125 s** are established
by the original startup. The most recent coupled physical sample is at model
cycle **2,199,887**, physical time **25.77992578125 s**: it lags that CPU boundary
by **1.32421875 ms**. This is actual retained coupling, not an inferred browser
state. Physical integration ends no later than
cycle **3,200,000**, at **37.5 s**, leaving **11.71875 s** of interactive time.
The ready CPU stays paused until the first nonzero controller deflection.
`physical_time` and `model_cycle` identify model samples. The final `cycle`,
`sim_time` and `interactive_time` may include later sensor settlement; use the
physical clock for observations, elapsed game time and scoring. The game takes
the actual first ready physical sample as its reference; the final measured
physical span can therefore be approximately **11.72007 s**, while the native
CPU input horizon remains **11.71875 s**. It does not replace the initial sample
with an invented state at the CPU boundary.

The worker advances 4,265-call steps, approximately 50 ms paced wall intervals.
The retained physical coupling cadence is at most 853 calls, approximately
10 ms. Physics remains the retained semi-implicit principal-rate integration,
including gyroscopic coupling and normalized quaternions. Browser display holds
actual samples between polls; it neither integrates nor extrapolates flight
motion. The existing 150 ms input refresh and 100 ms polling remain in use.

## Targets and scoring

Training targets are explicitly game objectives, not historical Apollo guidance
commands. They are defined relative to the actual initial ready quaternion:

| Challenge | Local target rotation | Total rate limit |
| --- | --- | --- |
| Yaw acquisition | +3° about body X | 1°/s |
| Pitch acquisition | +3° about body Y | 1°/s |
| Two-axis acquisition | +2° about body X followed by +2° about body Y | 1.3°/s |

`game-state.mjs` uses shortest quaternion rotation distance. A successful hold
requires an observed error at most **1°**, total angular rate at most the
challenge's displayed limit, and **0.4 s** of consecutive eligible physical
samples. The single-axis limit is **1°/s**; the beginner two-axis challenge uses
**1.3°/s** because its total rate combines the axes. These are adjustable game
objectives, not changes to the native model or controller. The total angular
rate includes all three measured axes. Missing samples, backwards clocks, malformed
telemetry, lost readiness or a sample gap above 0.3 s cannot establish a hold.
Repeated physical timestamps do not accumulate time. Only live, ready native
execution can earn success; stopping or the settlement tail cannot grant it.

The visible points are a game score based on observed angular accuracy and
steadiness. They do not rate flight fidelity or establish vehicle equilibrium.
The target quaternion affects the target wireframe and error computation only;
it is never sent to the native vehicle as a commanded attitude.

## Renderer boundary

`spacecraft-3d.mjs` consumes the observed quaternion and optional target
quaternion. Its procedural Lunar Module mesh is an illustrative visual model,
with browser WebGL depth testing and lighting. A Canvas projection fallback
keeps the same 3D model visible if WebGL is unavailable. The renderer owns camera
orbit, zoom and projection; it owns no spacecraft physics. Vehicle dimensions,
jet placement, starfield and attitude reference rings are presentation, not validated flight
geometry or translational telemetry.

## Fresh native calibration

The new `frontend-game-evidence/` directory is separate from protected phase
evidence. Its `native_smoke.py` harness calls the unchanged `prepare_assets` and
`NativeSession`, uses the pinned native engine/ringbuffer and retained external
model, and captures actual approximately 50 ms samples. It writes raw traces and
build provenance into a fresh `.build/game-ui/native/` directory. Retained JSON
summaries include input plans, source hashes, trace hashes and actual frames.
They are test evidence, not a substitute game provider.

Actual fresh execution results:

| Input from ready state, then automatic neutral | Observed target eligibility window after readiness |
| --- | --- |
| +yaw for 0.4 s | 3.998–8.247 s for the +3° target |
| +pitch for 0.4 s | 2.899–5.748 s for the +3° target |
| +yaw and +pitch for 0.4 s | 2.099–4.098 s for the +2°/+2° target |
| +yaw and +pitch for 0.2 s | No eligible target samples; original gated reads matter |

All six initial captured sessions completed the retained lossless sensor settlement and
native quiet checks. The 1 s single-axis cases demonstrate overshoot: yaw only
qualified for approximately 0.55 s and pitch had no eligible target samples.
These are observed input cases, not a formula mapping arbitrary hold durations
to resulting angles. These initial diagnostic windows use the stricter
**1°/s** total rate threshold, including the combined case. The game remains
interactive; the browser does not replay these cases as if they were the
player's live run.

A subsequent actual browser two-key hold is retained in
`native-chord-result.json`: yaw applied approximately 50 ms before pitch,
followed by approximately 400 ms of combined deflection. Its closest target
error was **0.439°**, but its total rate there was **1.255°/s**. It correctly
timed out under the earlier 1°/s combined rule. Shifting that target to 1.5°/1.5°
or 3°/3° did not solve the rate condition. Evaluating the same unchanged raw
trajectory against the final visible 1.3°/s combined game objective yields an
eligible interval from **1.579–3.009 s** after the initial physical sample,
approximately **1.429 s**. That analysis establishes a usable opportunity for a
0.4 s sampled hold; it does not retroactively turn the earlier browser loss
into a success.

The chord report preserves that old-rule loss alongside four additional
completed native pulse cases. A fifth additional pulse case was interrupted
when further calibration was stopped, so the extra batch is explicitly marked
**INCOMPLETE**. Its completed case summaries remain distinct from the partial
attempt. No model, emulator or backend parameter was changed during tuning;
only the visible combined game objective changed.

Reproduce the calibration without replacing retained results:

```sh
make runtime
python3 -B docs/frontend-game-evidence/native_smoke.py
```

The retained reports are `native-result.json` (four single-axis cases) and
`native-combined-result.json` (two combined cases). Their diagnostic
`interactiveTimeSeconds` values use the CPU readiness reference. The table above
uses elapsed physical time from the actual initial ready sample, as the game
does. `readiness-metadata.json` separately retains the actual native startup
register readbacks, exact raw trace line/hash and initial CPU/model clocks for
each case. These initial registers are not described as later per-frame
register readbacks. `extract_readiness.py` reproduces this extraction while the
new raw traces are present. Initial report timestamps are UTC; the project work
date was 18 October 2026 in Asia/Tbilisi.

## Future integration

Descent play needs authoritative backend position, velocity, frame and units,
engine/throttle state, fuel, contact detection and a validated longer physical
timeline. Those capabilities require a separate backend contract before the UI
enables them. A future 3D translation provider can feed the renderer without
replacing the live client or introducing a competing browser physics model.
Independent roll, multiplayer ownership and AI command proposals likewise need
explicit supported capabilities. The Phase 10 recorded pre-ignition guidance
experience remains a separate source; no coupled landing is implied.
