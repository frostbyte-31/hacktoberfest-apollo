# Phases 13–16: final hackathon integration

## Status and actual capability

**PARTIALLY COMPLETE** against the full authentic lunar-landing objective.
The integrated hackathon application is implemented and tested. Its strongest
authentic capability is **Level B: a bounded original-AGC control experiment**,
now inspectable alongside the preserved live attitude and guidance applications.
It also provides **Level C: an independent educational physics landing lab**.
There is no verified full original-AGC-guided landing, calibrated descent
trajectory, terrain or later P64/P66 mission reproduction.

Users can create a physical flight, manually command thrust and pitch, pause,
resume, restart, share one spacecraft between three crew clients, communicate,
review measurements and receive a measured success/failure debrief. They can
select deterministic crew or teaching assistance, inspect recorded authentic
engine experiments, compare the three original guidance scenarios, and open
the preserved live AGC attitude controls. Optional model-provider integration
is implemented and tested with stubs; a real model was **NOT RUN**.

## Repository integration and preservation

Work is isolated on `codex/final-integration`, based on verified Backend Phase 12
commit `22bd3c24c524334973beb6f9b3d168f21ca93e71`. No commit, main merge or push
was performed. The original `codex/backend-phase12` and
`codex/frontend-mission-control` worktrees remain unchanged, including the
frontend developer's uncommitted work.

Before integration, 7,348 backend and 5,607 frontend files were fingerprinted.
Only 79 frontend modified/new paths were copied. For the three modified tracked
frontend files, the destination was verified against their common base first.
No old backend file was copied over the newer backend. The final preservation
check verifies both original worktrees, their Git states, and all 7,348 original
backend files in the integrated checkout. Exactly four declared application
differences exist: `Makefile`, `frontend/README.md`, `guidance.html` and
`guidance.mjs`; the last three are the preserved frontend developer's changes.
Historical phase reports, evidence, Apollo source and emulator semantics are
unchanged. See `final-integration-evidence/preservation-before.json`,
`frontend-integration-copy.json` and `preservation-after.json`.

The historical Phase 10.5 package checker also seals application bytes. It
correctly rejects those four new application versions in this checkout. Its
unchanged script passes in the original backend checkout. This result is
retained, not hidden or repaired by changing its manifest. The independent
frontend preservation check verifies all 5,509 protected prior files unchanged.

## Authenticity acceptance gate

Fresh native Phase 12 sink, connected, disconnected-PIPA and repeat runs were
executed in the original clean backend checkout, with the ringbuffer backend
and all old integrity checks. All four decompressed traces match retained
fingerprints exactly; connected and repeat match each other. The new gate
contains actual execution metadata and source verification, not a test-total
inference. Its 16 native and 23 physical-model tests passed.

**VERIFIED within the bounded synthetic fixture:** original ignition and
FLATOUT output, physical thrust, three-component translational integration,
specific-force PIPA events, original navigation consumption and navigation
calculations, and changed subsequent original throttle execution/output.
Connected feedback produced four original THROTTLE calls; the no-feedback
control produced none. Both connected physical engines saturated at maximum
thrust, so this is not evidence of calibrated trajectory regulation.

**UNRESOLVED prerequisites for authentic braking:** achieved and calibrated
burn attitude, missing LOWCRIT/HIGHCRIT throttle padloads, physical DPS
calibration/transients, and later sensor/procedure requirements. The fixed
Phase 12 orientation initially thrusts roughly along REF +X while velocity X
is positive: measured first-thrust F·v is approximately **+2.49 MW**. This
experiment does not establish retrograde braking. Extending it into a claimed
landing would be unjustified; the app uses the prompt's explicit Level C
fallback without attributing its controller to Luminary.

| Provenance | Verified value |
|---|---|
| Virtual AGC revision | `f577e3fd917866c59334e6cdd32504f09df76f60` |
| Original rope SHA-256 | `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e` |
| Source archive SHA-256 | `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267` |
| Connected/repeat raw SHA-256 | `8fcc5ecb31bcf8c0158f71657c04dd1cbb8eca1455bae5d3db48f37bd6d37b53` |

## Architecture and implemented files

Original Luminary → unchanged native emulator/hardware → retained scientific
traces → read-only recording exporter/provider → existing guidance screen and
new engine inspector. The original live native attitude service remains a
separate real execution path. New lab clients → versioned command validator →
one server-owned educational plant → shared snapshots, event log and debrief.
There is no connection from educational landing controls to AGC output or
navigation memory.

| Files | Responsibility |
|---|---|
| `backend/final_assets.py`, `tools/final_demo.py` | Verify original rope/sealed evidence/exports, reuse locked native builder, one launch and owned shutdown |
| `backend/physics_lab.py` | Reuse Phase 12 Tcl engine and translational plant; add disclosed pitch actuator and physical outcome classification |
| `backend/mission_service.py`, `final_server.py` | Shared missions, validated roles, fixed-step pacing, leases, lifecycle, logs, capabilities and HTTP guards |
| `backend/crew_ai.py` | Optional server-side provider with role tools, bounded requests and labeled fallback |
| `backend/propulsion_recording.py` | Source-linked sample-and-hold export from sealed raw Phase 12 traces |
| `frontend/dist/mission.html`, `mission-app.mjs`, `mission.css` | New flight workspace alongside existing applications |
| `flight-view.mjs`, `mission-live-provider.mjs`, `mission-live-types.d.ts` | Replaceable read-only SVG projection and separate typed live-lab data access |
| New backend/frontend tests, `Makefile`, `frontend/tsconfig.json` | Repeatable application checks and integration typing |

The safely copied frontend includes its existing mission provider, spacecraft
viewer, styling, tests and architecture/evidence documents. It was not rebuilt.
The exact changed/untracked file list and final hashes are retained with the
new sprint evidence. See `FINAL_INTEGRATION_CONTRACT.md` for actual endpoints,
commands, role permissions, units, frames, timestamps and unavailable APIs.

## Physical model and outcomes

**ASSUMED synthetic scenario:** training starts 150 m above a spherical Moon,
radial velocity −5 m/s, tangential velocity +1 m/s, wet mass 8,000 kg and 500 kg
propellant. Other scenarios start at 300 m with −15/+3 m/s, or with 15 kg fuel.
These are teaching conditions, not Apollo 11 mission measurements.

The unchanged Phase 12 plant uses central lunar gravity, velocity-Verlet
translation, thrust acceleration **F/m** and mass flow **F/3050** kg/s. Thrust
range is the existing ideal engine model's 4,560–45,040 N; zero command is OFF.
The scalar control interpolates that modeled range, not an authentic throttle
counter calibration. Body +X thrust is rotated through the existing Phase 7
quaternion matrix into 3D Moon-centered REF. The lab adds only a synthetic
single-axis pitch actuator: I=12,000 kg·m², torque=±2,400 N·m and damping=2/s.
It does not claim general attitude fidelity, gimbal calibration or RCS fuel flow.

Physics uses 10 ms steps; the server paces batches of five. Attitude is held at
its integrated endpoint over each interval. Tests independently check free-fall
acceleration (within 0.002 m/s over one second), displacement (within 0.01 m),
force/mass flow, signs, rotated thrust, fuel exhaustion and repeatability. These
are bounded numerical checks, not a global error bound for a real spacecraft.
The 2D viewer renders measured altitude/downrange and vectors without propagating
motion or inventing a future trajectory.

Surface contact is the actual first integrated endpoint at or below the
reference radius, with up to one 10 ms step of penetration; state is not snapped.
Synthetic safe limits are |vertical speed|≤2 m/s, horizontal speed≤1.5 m/s,
|tilt|≤8° and site distance≤75 m. Fuel exhaustion, >70° tilt and the 180 s
horizon terminate the experiment. Terminal state freezes and reports engine OFF.
All limits are explicitly teaching assumptions.

Two full deterministic fallback flights produced identical physics and 178
identical validated command values each. They landed at **33.74 s**, vertical
**−0.731057 m/s**, horizontal **0.044670 m/s**, downrange **3.77653 m**, with
**346.57889 kg fuel**. A browser run independently reached the same debrief.
Ballistic/no-thrust and low-fuel tests produced measured failure states.
The initial fallback controller genuinely crashed; its failed development run
is retained. The controller was corrected without changing touchdown thresholds
or the physical plant.

## Collaboration, agents and education

**VERIFIED:** three real browser tabs created/joined one shared mission, saw
shared telemetry/messages, required all three ready seats, and enforced
commander flight controls and Aldrin checklist permissions. Collins stays in
lunar orbit and provides a disclosed simplified communication/support role.
All 0/1/2/3-human compositions were also tested with deterministic fallback crew.
The service is local/loopback; remote hosting, internet authentication and a
cross-device session deployment are **NOT RUN**.

Model tools operate through the same validator, never through direct state
writes. Both supported wire formats, all human/stub-model compositions,
malformed commands, timeouts/failures, stale replies, control expiry and
nonblocking physics were tested. No real API key or model was used. Real LLM
crew remains **NOT RUN**; deterministic assistance is always labeled separately.

The app explains velocity versus acceleration, thrust orientation, orbital
state, PIPA specific force, authentic guidance prerequisites and measured impact
outcomes. The original screen retains P51/P27/P63/root-solving/ignition-time
lessons and three evidence-backed scenario comparisons. A final polish labels
debrief values as frozen endpoint measurements rather than ongoing descent.

## Actual verification

**526 passed, 0 final assertion failures, 3 historical missing-evidence errors,
0 skipped** across disjoint executed groups. Repeat diagnostic runs are not
added to this total.

| Group / command | Passed | Failed | Error | Skip |
|---|---:|---:|---:|---:|
| Fresh unchanged Phase 12 validator (native 16 + model 23) | 39 | 0 | 0 | 0 |
| Original clean checkout `make check` | 210 | 0 | 3 | 0 |
| Original staged Phase 10 `run_tests.py` (Phases 8–10) | 57 | 0 | 0 | 0 |
| Current `unittest discover -s backend/tests -v` | 98 | 0 | 0 | 0 |
| Current frontend Python tests | 26 | 0 | 0 | 0 |
| Current demo guard tests | 6 | 0 | 0 | 0 |
| Current retained live-control evidence tests | 9 | 0 | 0 | 0 |
| Current `node --test frontend/tests/*.test.mjs` | 81 | 0 | 0 | 0 |

The current application groups run together with **`make test-final`**. Exact
expanded commands, runtimes, environment and stdout/stderr are retained in
`final-integration-evidence/final-checks/`. The final Node rerun verifies the
last endpoint-description edit; strict TypeScript contracts and JS syntax pass.
Original/new evidence seals, guidance export, propulsion export, native MVP
retention, original frontend preservation and `git diff --check` pass.

The three errors are unchanged preservation tests unable to read historical
`docs/phase3-evidence/build.log`. They are neither passing tests nor new errors.
The old `make check` exits zero despite recording them; this report preserves
the actual counts. Earlier failed HEAD Host-guard and controller-development
checks are retained separately; their corrections passed the final suite.
No existing assertion or original behavior was weakened. The earlier native
HTTP watchdog-neutralization assertion was not independently rerun in this
sprint and was not changed; actual live browser controls were tested separately.

Actual desktop Chrome checks include manual 45,040 N thrust with physical
velocity/fuel changes, three human clients, record case selection/replay,
preserved 15 km/16 km/missing-site results, and genuine native yaw/pitch input.
The latter produced +3.330°/s yaw and +2.829°/s pitch in the captured run.
A same-origin 390×844 CSS-pixel frame verifies responsive layout. Actual mobile
hardware, touch and mobile browser emulation are **NOT RUN**. Screenshots,
request logs, raw audits, debrief and limitations are in the new frontend evidence.

## Launch and judge walkthrough

From this integrated checkout, use one recommended command:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime --port 0
```

Open the **`/mission.html` URL printed by the launcher**. `--port 0` asks the
operating system for a free local port. Python 3.9+, a C compiler and `make`
are needed for native/physical modes. The launcher verifies the pinned software,
reuses an existing verified cache or builds the locked Tcl runtime and native
adapter. Fresh dependency downloads require network access. No Node/bundler is
required to run the application. `make demo-final PORT=0` uses an already
established runtime. Ports 4173 and 4180 were occupied during the final launch;
neither service was stopped. Use an explicit free port for a fixed demo URL;
`--recorded-only` serves authentic recordings without native dependencies.
Unavailable physical modes are explicitly disabled, never filled with mock data.

Suggested three-minute demonstration:

1. Open Original guidance replay. Compare 15 km and 16 km ignition times
   (360.29 versus 360.44 s GET), then the missing-site alarm 01406. Explain that
   these are retained original calculations, not live flight or countdowns.
2. Return to the flight lab and inspect the recorded engine experiment. Compare
   connected and disconnected PIPA feedback, scrub to original ignition/throttle
   events, and show source cycle/hash and the NOT RUN landing limitation.
3. Create Final approach as commander with two fallback seats. Mark ready,
   enable Training assist and start. Show decreasing altitude, thrust, fuel,
   signed velocity and the measured soft-contact debrief after about 34 s.
   Explicitly call this independent modern educational assistance.
4. Restart, disable assistance and try manual thrust/pitch. An upward thrust can
   brake downward velocity before reversal; an uncontrolled flight can fail.
5. For collaboration, create three human seats and use the invite in two other
   tabs/windows. Join as Aldrin/Collins, ready all three, exchange callouts and
   show role permissions. This is one local authoritative spacecraft.
6. Optionally open Live AGC attitude, start and hold yaw/pitch briefly. This is
   genuine live Luminary control; it does not command the educational landing.

Ctrl+C closes only this server's workers, model requests and physical processes.
`check_launch.py` verified actual offline startup, all three documents, truthful
disabled capabilities, occupied-port handling and clean owned shutdown.

## Evidence, reproduction and remaining work

All new captures are in `docs/final-integration-evidence/`:
`baseline-gate/`, `prior-regressions/`, `final-checks/`, `frontend/`, `physics/`,
`crew-service/`, `crew-development/`, `controller-development/` and `launch/`.
The sprint fingerprint manifest records new evidence and application source.
It does not relabel generated diagnostics as historical Apollo telemetry.

Run the current checks with `make test-final NODE=/path/to/node`. Optional strict
types use `node /path/to/typescript/lib/tsc.js -p frontend/tsconfig.json`;
`npm ci` in `frontend/` installs its pinned development compiler if needed.
Run `python3 -B -m backend.propulsion_recording --check` to verify the raw-trace
export. The new preservation checker accepts `--output /new/result.json`.
Scientific baseline reruns use the original clean 22bd3c2 checkout; exact
commands and dependencies are recorded in the gate/regression directories,
preserving original whole-application checks rather than bypassing them.

The three most valuable remaining improvements are:

1. Establish physically calibrated achieved burn attitude, then validate a bounded
   retrograde engine/PIPA experiment with independent F·v and navigation checks.
2. Source and load legitimate DPS throttle limits/calibration, then show changed
   physical force in response to original variable thrust demand before extending
   the descent horizon.
3. Validate an explicitly chosen real model provider and deployed three-client
   session lifecycle, including latency/failure/mobile checks. Keep these product
   improvements separate from claims about original Apollo landing capability.

No further phase was started automatically. All implementation remains reviewable
and uncommitted on the dedicated integration branch.
