# Apollo 11 · Guidance Labs

## Procedure-led mission experience

```sh
make play
```

Open **http://127.0.0.1:4173/play.html**. The main experience explains the current
preparation task and steps through verified recorded software observations with
a read-only DSKY and an illustrative 3D Lunar Module. This is a walkthrough of
the synthetic experiment, not the full Apollo 11 flown checklist. Live DSKY,
cockpit switches, crew continuation and powered descent are explicitly unavailable.

The modern target exercise remains at **/attitude-lab.html**, separate from
mission procedures. Its illustrative hand controller uses existing live yaw/pitch
inputs. Keyboard steering requires an explicit opt-in; accessible direction
buttons remain available. The first live launch needs the pinned Tcl runtime,
C compiler and make. `make demo` remains replay-only.

See [procedure architecture and missing contracts](../docs/FRONTEND_PROCEDURES.md)
and [verification](../docs/frontend-procedure-evidence/README.md). The earlier
[game contract](../docs/FRONTEND_GAME_CONTRACT.md) and its evidence describe the
previous revision; the target exercise is now at the separate lab route.

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

Open **http://127.0.0.1:4173/**. Choose another local port with `--port 4174`. The server serves only `frontend/dist/` and binds to loopback. No AGC starts until you select **Live AGC → Start live AGC**. Stop the server with Ctrl-C. No npm installation, external assets, fonts, CDN or external service is needed. Opening `index.html` directly from disk is unsupported.

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
