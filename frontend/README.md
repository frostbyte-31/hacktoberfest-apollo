# Apollo 11 · Attitude Lab

A repository-local visual demo of verified Phase 7 attitude-control evidence. It presents actual captured Luminary 099 RCS outputs alongside the simulated vehicle response and returned sensor measurements. It is a recording viewer, not a running AGC, flight simulator or landing demonstration.

## Open the demo

From the repository root, with Python 3.9 or newer:

```sh
python3 -B frontend/serve.py
```

Open **http://127.0.0.1:4173/**. Choose another local port with `--port 4174`. The server serves only `frontend/dist/`, binds to loopback, and starts no AGC or spacecraft process. Stop it with Ctrl-C. No npm installation, external assets, fonts, CDN, authentication or network service is needed. Opening `index.html` directly from disk is unsupported because the replay loads through HTTP.

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

Body X/P, Y/Q and Z/R correspond to yaw, pitch and roll. O/I/M are the outer, inner and middle IMU gimbals, not body Euler angles. Gimbal values wrap to ±180° for display; actual counter values remain unsigned decimal. Original channel words use octal. The spacecraft silhouette is illustrative; it is not validated jet geometry. Jets light only from real source-mapped output bits; the page generates no actuator commands.

Readiness requires recorded P00, clear original IMODES30/33 inhibition bits, ACCSOKAY and three zero FAILREG words. Unknown program/counter/command data remain unknown, including the invalid startup MODREG sentinel. There is no fabricated DSKY, altitude, position, orbit, terrain, descent thrust or landing.

Playback freezes at the physical horizon. In the combined connected recording, the last frame's CDU Y is **1476**; the later drained result is **1477**. That final operation belongs to the recorded settlement tail, not the frozen vehicle frame. The download retains both values. Empty queues do not establish attitude equilibrium; the combined cutoff still has approximately +1.324°/s pitch rate.

## Validation

Python data/provenance tests need only the standard library. Presentation tests use Node 20 or newer without dependencies:

```sh
python3 -B -m unittest discover -s frontend/tests -p test_replay.py -v
node --test frontend/tests/replay.test.mjs
make test-phase7
```

The tests check real source checksums and endpoints, exact RCS event sequences, deterministic export, honest missing fields and the sensor tail, right-handed quaternion rendering, non-extrapolation after cutoff, interpolation without mutating samples, wrapping, source jet bits, readiness gates and malformed-data rejection. Browser checks additionally cover desktop/phone layouts, real control interactions, original startup state and the evidence dialog/download.

The previous [Phase 7 report](../docs/PHASE7_MULTIAXIS_VALIDATION.md) remains the scientific record. This frontend adds presentation only. Full independent three-axis control, sustained stability, mission initialization and powered descent remain unverified.
