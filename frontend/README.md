# Apollo 11 · Mission procedures and guidance

## Launch and choose the crew

From the repository root, with Python 3.9 or newer:

```sh
make play
# Or directly:
python3 -B tools/final_demo.py --port 4173
```

Open **http://127.0.0.1:4173/** for the launch screen. Choose **Apollo mission** → **Open Earth-orbit task** for live original CMC
operation in the Earth-orbit chapter, or the separate
educational landing laboratory. Every
experience identifies its execution source and available controls. The landing
lab does not continue the trainer's historical flight state.

Exactly three crew slots represent Armstrong, Commander in Eagle; Aldrin, Lunar
Module Pilot in Eagle; and Collins, Command Module Pilot in Columbia. Collins
remains in lunar orbit; his landing-lab communications/support role is a disclosed
gameplay adaptation.

### Playable P52 alignment

**/campaign.html?play=1** opens original Comanche P52 with modeled CSM instruments. Prepare the instruments, identify stars 30/37, use the OHC and MARK controls, review original N05/N93, approve gyro correction and return P00. See [the player checklist](../docs/P52_PLAYER_GUIDE.md), [implemented API](../docs/EARTH_ALIGNMENT_INTEGRATION.md) and [fresh native evidence](../docs/earth-departure-evidence/README.md). The setup computes its initial reference through original P51; no historical flight checkpoint or TLI is supplied.

### Retained cold-start Columbia diagnostic

**/campaign.html?play=1&task=diagnostic** opens a cold-start Comanche 055 console with all nineteen
real DSKY keys. Start the CMC and follow the server's five observed checkpoints:
display test, P00, original clock, P52 readiness alarm and P00 recovery. Native
packet acknowledgments and actual original output determine progress. This is
computer control practice, not a restored orbital state or successful alignment.
Python and `cc` are required; this CMC mode needs neither Tcl nor Node.

[Exact player to-do list](../docs/EARTH_ORBIT_PLAYABLE_GUIDE.md) ·
[implemented CMC contract](../docs/EARTH_ORBIT_INTEGRATION.md).

### Chronological historical mission

**/campaign.html** starts in Earth parking orbit with Eagle stowed in the closed
adapter above the S-IVB. Sixteen sourced chapters cover lunar arrival, Eagle's
landing, ascent/rendezvous and Columbia's direct entry/splashdown. All three crew
members begin in Columbia; only Armstrong and Aldrin later transfer to Eagle.

Choose **Guided tour** on the home screen, or open **/campaign.html?tour=1**.
The tour advances historical references every eight seconds and steps two genuine
original-AGC excerpts at the relevant lunar chapters. These excerpts come from
the same retained synthetic Phase 12 experiment. They are not a continuous
historical flight. Pausing and resuming keeps the current exact observation.

The historical models are static 3D configurations; dragging changes only the
camera. All full-flight commands and goals remain unavailable. Reviewing the
sixteen chapters never completes a flight goal. See the
[campaign contract](../docs/APOLLO11_CAMPAIGN_INTEGRATION.md) and
[chronological judge presentation plan](../docs/JUDGES_PRESENTATION_PLAN.md).

### Historical orbital procedures

The **/play.html** experience starts with Eagle docked to Columbia. One person
can take all three stations, or people can share one device and take assigned
turns. Begin the undocking checklist and complete **28 selected source-backed
actions**. Reports and cockpit switch positions are checked by the server for
crew, order, sequence and revision. Collins releases Columbia's **DOCKING PROBE
EXTD/REL**, then returns it to **OFF**. A labeled static 3D mechanical diagram
shows the release.

This is an **INTERACTIVE PROCEDURE TRAINER** with explicit entry assumptions,
including earlier tunnel, pressure, probe and computer preparation. Some LM
crew-station assignments are instructional. It does not execute the AGC/AGS,
generate physical flyaway or reconstruct the full flown checklist. The next
handoff is relative-motion management and Eagle inspection, before the later
CSM separation maneuver, LM preparation/alignment, DOI and powered descent.
Unsupported flight chapters remain gated.

### Shared educational landing laboratory

The **/mission.html** lab uses the new backend's authoritative spacecraft plant,
with synthetic initial conditions and modern throttle/pitch controls. Select
the training, braking or low-fuel scenario. Choose a human, **deterministic
fallback**, or configured model provider for each of the three seats; your own
seat is human. An observer host can instead watch three agent seats. Open human
seats can be joined from another local browser/private window with the mission
ID or invite. All three seats must be occupied and ready before start.

The Commander controls flight and optional modern training assist. The LM Pilot
reviews the lab checklist; joined crew can exchange messages. Pause, resume,
restart and the final measured debrief operate on one shared server state. Human
commands expire unless refreshed. Browser credentials are private to the tab;
invites carry a mission ID. This is a loopback demonstration, not an internet
deployment or a cross-device service.

The mode is **EDUCATIONAL_PHYSICS_LAB**, with `authenticAGC: false`. The plant has
3D position, velocity and attitude representations but only a bounded planar
pitch actuator. This is not an authentic Apollo hand-controller model, a
historical trajectory or an AGC-guided landing. Deterministic crew and training
assist are labeled separately from model AI. The model-provider adapter exists;
real LLM execution was **not run** in this delivery.

Server-side model configuration uses `APOLLO_AI_MODEL`, `APOLLO_AI_BASE_URL`,
`APOLLO_AI_PROTOCOL` (`responses` or `chat-completions`) and optional
`APOLLO_AI_API_KEY` for a local provider. Remote providers require HTTPS. No
ambient key is auto-discovered or exposed to the browser. Model seats are
available only with a valid explicit provider configuration. Models propose
role-permitted commands through the normal validator; they cannot write
spacecraft state. Failures use explicitly labeled deterministic fallback.

### Authentic recordings and native execution

**VERIFIED RECORDED EXECUTION** and **STATIC EDUCATIONAL ILLUSTRATION** remain
distinct from both playable modes. The separate propulsion recording includes
actual retained 3D position/velocity, original DSKY observations, engine commands,
thrust, fuel and PIPA/navigation feedback. Its retained causal cases are bounded
synthetic diagnostics, not the historical Apollo 11 landing trajectory. The
original guidance explorer and live bounded attitude laboratory are preserved.
Arbitrary live mission DSKY commands and a complete authentic AGC-guided landing
remain unavailable.

If port 4173 already serves the current application, reuse it. To start another
instance, use `make play PORT=4180` and open **http://127.0.0.1:4180/**. Restart an
old server after updating backend routes. Keep the terminal open; Ctrl-C stops
the server and its owned workers. Opening HTML directly from disk is unsupported.
No npm installation is needed.

The physical lab and live AGC attitude need a C compiler, make and the pinned Tcl
runtime. On first use, run `python3 -B tools/final_demo.py --bootstrap-runtime`
or prepare the runtime with `make runtime`, then `make play`. The launcher checks
the original source/evidence and prepares the existing native assets. If those
dependencies are unavailable, the launch screen reports the unavailable modes;
the undocking trainer and authentic recordings remain available. To skip native
preparation deliberately, use `python3 -B tools/final_demo.py --recorded-only`.
The older `frontend/serve.py --replay-only` launch disables interactive commands
and does not expose the new shared-mission service.

See [play instructions and procedure API](../docs/FRONTEND_UNDOCKING.md),
[historical sources](../docs/FRONTEND_UNDOCKING_RESEARCH.md),
[undocking verification](../docs/frontend-undocking-evidence/README.md), and
[submission guide](../docs/SUBMISSION_GUIDE.md). The new mission endpoints, crew
permissions, clocks, units and provider boundary are documented in
[the final integration contract](../docs/FINAL_INTEGRATION_CONTRACT.md).

The modern target exercise remains at **/attitude-lab.html**, separate from
mission procedures. Its illustrative hand controller uses existing live yaw/pitch
inputs. Keyboard steering requires an explicit opt-in; accessible direction
buttons remain available. The first live launch needs the pinned Tcl runtime,
C compiler and make; run `make runtime` to prepare it. `make demo` remains
replay-only. The original attitude recording console is preserved at
**/attitude-replay.html**.

The earlier [procedure architecture](../docs/FRONTEND_PROCEDURES.md) and
[verification](../docs/frontend-procedure-evidence/README.md), and the
[game contract](../docs/FRONTEND_GAME_CONTRACT.md) and its evidence describe the
previous preparation/target revisions; the target exercise remains a separate lab.

## Phase 10 mission control

The frontend now extends the existing recorded guidance experience with a
three-panel mission console, Apollo-inspired read-only DSKY, independent SVG
geometry viewer, scenario outcome comparison, ten engineering field notes,
capability status, and exactly three planned crew roles. All numerical results
still come from the unchanged retained export; no new flight capability is claimed.

See [frontend architecture and startup](../docs/FRONTEND_ARCHITECTURE.md),
[actual/missing integration contracts](../docs/FRONTEND_INTEGRATION_CONTRACT.md),
and [current test/screenshot evidence](../docs/frontend-phase10-evidence/README.md).

```sh
make frontend-check  # static artifact verification + ES-module syntax
make test-frontend  # Python provenance and all Node presentation tests
```

## Educational pre-ignition replay — Phase 10.5

From the repository root, with Python 3.9 or newer:

```sh
make demo
# Or without make:
python3 -B tools/demo/demo.py launch
```

Open **http://127.0.0.1:4173/guidance.html**. Use `make demo PORT=4180` if
4173 is already occupied. No Node, compiler, network service or dependency
installation is needed for this recorded demonstration. The launcher verifies
the sealed original-software artifacts and produces the browser data from
retained traces before starting the existing loopback server in replay-only
mode. It does not start an AGC process or enable live pilot inputs.

Explore the verified synthetic 15 km and 16 km cases and the missing-site
control. Replay, pause, restart, scrub or step through actual events. The DSKY
and numerical readouts hold real observations; they do not interpolate AGC
values. The orbit view is a **static projection of initialized 3D inputs**,
with the site shown at its nominal landing epoch. It does not animate a
descent or propagate spacecraft motion. Signed time-to-go, absolute ignition
epoch and the held ignition lead at the solution observation are labeled separately.

The screen is **RECORDED AUTHENTIC EXECUTION REPLAY**. Original Luminary
performed the calculations; the orbit, epoch and optical fixture are
synthetic. Engine ignition, powered descent and landing remain unproven.

```sh
make demo-verify       # offline artifact/data checks
make demo-reproduce    # separate fresh authentic native experiment
```

Fresh native reproduction needs Git history containing the original baseline,
a C compiler and make. Its first run obtains and verifies pinned source, or
accepts `--archive` through `python3 -B tools/demo/demo.py reproduce`. It runs
the unchanged Phase 10 harness in an isolated verified baseline, preserving
its original application-source hash checks while allowing this new UI.
Read [the Phase 10.5 report](../docs/PHASE10_5_MVP.md) for exact commands,
provenance, tests and the unresolved historical log gaps.

## Existing attitude lab and live control

A repository-local console for verified Phase 7 recordings and fresh native Luminary 099 attitude sessions. Both modes show actual AGC RCS outputs alongside the external simulated vehicle response and returned sensor measurements. Live mode sends bounded, authentic rotational hand-controller inputs. No landing is simulated.

## Open the demo

From the repository root, with Python 3.9 or newer:

```sh
python3 -B frontend/serve.py
```

Open **http://127.0.0.1:4173/attitude-replay.html** for this laboratory. Choose
another local port with `--port 4174` and use the same path. The server serves
only `frontend/dist/` and binds to loopback. No AGC starts until you select
**Live AGC → Start live AGC**. Stop the server with Ctrl-C. No npm installation,
external assets, fonts, CDN or external service is needed. Opening the HTML
directly from disk is unsupported.

Live mode also requires a C compiler (`cc`) and the locked Tcl runtime. Run `make runtime` first; its initial download is integrity checked. Select `python3 -B frontend/serve.py --replay-only` to disable the native API and use recordings without those dependencies.

## Pilot a live session

Start the original software, wait for P00, ACCSOKAY, clear original IMU inhibition and alarm readbacks, then hold **A/D for yaw** or **W/S for pitch**. Mouse, touch and keyboard button holds are supported. Both axes can be held together; opposing directions on one axis cancel. The CPU pauses at readiness until the first deflection. It then advances fixed native steps, paced by wall time, for at most **11.7 simulated seconds**.

The browser sends directions only. The worker maps them to ±20 RHC counts on original input ports `0167` (yaw), `0166` (pitch), and the active-low channel `031` switches. Original channel `013` gates the analog read. Luminary chooses the actual channel `005`/`006` RCS commands. The existing Phase 7 model applies them and returns real CDU counter-operation packets. No flight memory, actuator, orientation or rate write is exposed to the UI.

Releasing a control, losing focus, hiding the page or opening details sends neutral. Unrefreshed input also expires within 0.5 simulated seconds, with a separate wall-clock freshness check. Neutral is a controller input, not an instantaneous brake. **Stop run** freezes the model, drains generated sensor operations and records the result. A new run uses a fresh native library instance and original startup.

Live graphics hold actual backend quaternion samples between polls. The display separates physical model time from CPU time, which can continue during sensor settlement. Source latches and actual counters stay distinct from model sampling. A network error disables pilot controls and preserves the last sample with a disconnected status; it never substitutes replay data.

Each session writes new traces and source/runtime hashes under `.build/live/sessions/`; HTTP intent and acknowledgement records are under `.build/live/http/`. Download the current gateway record using the toolbar or provenance dialog. An acknowledgement identifies queued/applied interface input, not proof that Luminary read it; native traces separately observe the original RHC gate. The API requires a per-process token, exact local Host/Origin and bounded schemas. It is a local development service, not a multiplayer server.

The live fixture uses ideal identity alignment, synthetic mass properties and the retained Phase 7 integration cadence. It rejects unsupported alignment, engine commands, excessive rates and sensor queues. Arbitrary attitudes, sustained stability and independent roll are unverified. See [live experiment evidence](../docs/live-control-evidence/README.md).

## Explore

- Switch between combined yaw/pitch, yaw and independent pitch.
- Play, pause, change playback speed, scrub the full startup/control timeline, or restart.
- Switch connected/disconnected recordings for pitch and combined cases. Yaw has only the exported connected baseline; unavailable controls are disabled.
- Compare feedback conditions on the rate chart. Toggle the chart between the control window and full run.
- Orbit the illustrative spacecraft camera by dragging, toggle body axes, or reset the view.
- Inspect actual octal channel words, source-mapped jet activity, original readiness, sampled body rates and measured CDU values.
- Open the mission brief, coordinate explanation, help and provenance. Download the selected experiment record with its source hashes.

Keyboard shortcuts, when focus is outside a control: Space plays/pauses; left/right arrows move 0.5 seconds; R restarts; Escape closes details. Controls remain available on phone layouts. Camera movement changes presentation only.

## Data boundary

`dist/data/replay.json` contains five exported native cases from the final verified Phase 7 run:

| Case | Physics horizon | Feedback |
|---|---|---|
| Yaw | 46.875 s | Connected |
| Pitch / pitch control | 46.875 s | Connected / omitted |
| Combined / combined control | 37.5 s | Connected / omitted |

`tools/export_replay.py` checks the pinned final retention/summary hashes, then each compressed and uncompressed source trace before exporting. No historical evidence is changed. Rebuild the deterministic browser data with:

```sh
python3 -B frontend/tools/export_replay.py
```

Frames are actual model samples at approximately 10 Hz, including physical endpoints. Numeric readouts hold the preceding recorded sample. Genuine RCS packet edges retain their original timestamps and are applied independently of sample thinning. Scalar-first body-to-stable quaternions are interpolated only to smooth the drawing; no interpolated number is presented as captured telemetry.

Body X/P, Y/Q and Z/R correspond to yaw, pitch and roll. O/I/M are the outer, inner and middle IMU gimbals, not body Euler angles. Gimbal values wrap to ±180° for display; actual counter values remain unsigned decimal. Original channel words use octal. The spacecraft silhouette is illustrative; it is not validated jet geometry. Jets light only from real source-mapped output bits; pilot controls are available only in the separate live mode.

Readiness requires recorded P00, clear original IMODES30/33 inhibition bits, ACCSOKAY and three zero FAILREG words. Unknown program/counter/command data remain unknown, including the invalid startup MODREG sentinel. There is no fabricated DSKY, altitude, position, orbit, terrain, descent thrust or landing.

Playback freezes at the physical horizon. In the combined connected recording, the last frame's CDU Y is **1476**; the later drained result is **1477**. That final operation belongs to the recorded settlement tail, not the frozen vehicle frame. The download retains both values. Empty queues do not establish attitude equilibrium; the combined cutoff still has approximately +1.324°/s pitch rate.

## Validation

Python data/provenance tests need only the standard library. Presentation tests use Node 20 or newer without dependencies:

```sh
python3 -B -m unittest discover -s frontend/tests -p test_replay.py -v
node --test frontend/tests/replay.test.mjs frontend/tests/live.test.mjs
make test-live
make validate-live
make test-phase7
```

The tests check real source checksums and endpoints, exact RCS event sequences, deterministic export, honest missing fields and the sensor tail, right-handed quaternion rendering, non-extrapolation after cutoff, interpolation without mutating samples, wrapping, source jet bits, readiness gates and malformed-data rejection. Browser checks additionally cover desktop/phone layouts, real control interactions, original startup state and the evidence dialog/download.

The previous [Phase 7 report](../docs/PHASE7_MULTIAXIS_VALIDATION.md) remains the scientific record for its captured experiments. The new [live-control evidence](../docs/live-control-evidence/README.md) records fresh input-driven executions. Full independent three-axis control and sustained stability remain unverified. This attitude fixture does not establish mission initialization or powered descent. The separate Phase 10 experiment establishes bounded synthetic pre-ignition numerical guidance, exposed by the Phase 10.5 replay above.
