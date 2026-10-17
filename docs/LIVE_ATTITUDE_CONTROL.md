# Live native AGC attitude controls

**VERIFIED — bounded local yaw/pitch pilot control.** The frontend now sends
authentic rotational hand-controller inputs to fresh Luminary 099 executions.
Actual original RCS outputs drive the existing external Phase 7 spacecraft and
IMU/CDU model. Browser rendering consumes authoritative backend samples.
Powered descent was neither implemented nor run.

## Run

```sh
make runtime
python3 -B frontend/serve.py
```

Open `http://127.0.0.1:4173/`, choose **Live AGC**, then **Start live AGC**.
Wait for original readiness. Hold **A/D for yaw**, **W/S for pitch**, or the
on-screen buttons. Independent axes can be held together; opposite directions
on one axis cancel. Release returns the controller to neutral. Neutral does not
instantaneously stop a rotating vehicle. Stop freezes physical integration and
drains already generated sensor operations. Each new run genuinely restarts the
native fixture. Recorded replay remains a separate mode; `--replay-only`
disables live control entirely.

## Authentic input and execution boundary

Base repository revision is `e8197c8d5227b5a425c5f6529147ba918c0fc67f` on `main`.
The pinned Virtual AGC revision remains
`f577e3fd917866c59334e6cdd32504f09df76f60`; Luminary binary SHA-256 remains
`1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
Native execution uses the original engine and ringbuffer backend. Original
Luminary instructions and emulator instruction semantics were unchanged.

The mappings reuse the source investigation in
`phase7-evidence/source/mappings.json` and the pinned source extracts. Yaw uses
normal analog input port `0167`; pitch uses `0166`. Signed 20-count inputs are
`20` and one's-complement `32747`. Active-low channel `031` selects source-mapped
controller switches and out-of-detent; neutral is octal `067777`. Original
channel `013` gates the RHC read into counters `0043`/`0042`. New traces observe
those original gated copies rather than treating an HTTP acknowledgement as
flight-software consumption.

`backend/native_session.py` verifies earlier evidence, extracts the retained
24-file corresponding-source bundle, validates the locked Tcl 8.6.16 runtime,
and builds the unchanged Phase 7 native observer and bridge. It reuses the
retained integration `Engine`, Tcl wire server, physics overlay, quaternion
integration, source-derived RCS decoding and counter queues. It contains no new
guidance or vehicle controller. A unique, hash-checked native library copy per
session isolates original C static/FIFO state without altering reset semantics.

The original startup sequence includes V36, delayed V37/P00 and V77 selection.
At CPU call 2,200,000 the adapter requires P00, clear original IMODES30/33
inhibition, ACCSOKAY and three zero alarm registers. The CPU then pauses until
the first nonzero pilot input. This is an identity-aligned, operate-only
synthetic test fixture, **not** complete mission initialization or validated
flight IMU alignment. Earlier power-on alarm evidence remains preserved.

## Architecture and timing

`frontend/dist/live.mjs` sends only bounded directions and sequence numbers.
`frontend/serve.py` accepts exact-schema requests on loopback with matching
Host/Origin, a process-specific token and no cross-origin control grant.
`backend/control_service.py` queues intent; one owning worker performs all
native calls. HTTP readers receive deep copies of cached state and never advance
the engine. There is no API for flight-memory, sensor, RCS, torque, orientation
or rate writes.

The worker advances fixed 4,265-call steps, paced at approximately 50 ms wall
intervals. Physics retains the Phase 7 cadence of 853 calls (about 10 ms maximum
coupling latency), semi-implicit principal-rate integration including
`omega × (I omega)`, and normalized scalar-first body-to-stable quaternions.
Body X/P is yaw, Y/Q pitch, Z/R roll. IMU gimbals follow
`C = Ry(I) Rz(M) Rx(O)` and are not body Euler angles. All three derived sensor
increments pass through the actual native CDU counter-operation queues.

Input refreshes are at most 150 ms apart in the client. Each native deflection
expires after at most 42,666 calls (under 0.5 simulated seconds); a separate
0.55-second receipt-based wall lease rejects stale queued deflections. Neutral
can overtake pending deflections. Release, blur, hidden page and pointer
cancellation clear held controls. A disconnected client disables controls and
holds its last actual sample while the backend lease neutralizes inputs.

Physical integration ends no later than call 3,200,000: **11.71875 simulated
seconds after readiness**. Stop may end it earlier. The adapter freezes physical
production, drains real input/FIFO operations and checks 1,000 quiet CPU calls.
The UI displays frozen physical time separately from advancing CPU time, actual
latest output latches separately from the applied model latch, and actual CDU
counter readbacks. The live drawing holds sampled quaternions; it does not
integrate or extrapolate a replacement vehicle. Queue settlement is not
attitude equilibrium.

## Actual results

The final six-case native batch exercised both signs on each axis, combined
negative yaw/positive pitch, and an identical repeated combined execution:

| Input | Maximum signed body response during initial lease | Generated X/Y/Z CDU operations |
|---|---|---|
| Yaw + | +4.111°/s | 906 / 0 / 0 |
| Yaw − | −4.111°/s | 910 / 0 / 0 |
| Pitch + | +4.037°/s | 0 / 1175 / 1 |
| Pitch − | −4.038°/s | 0 / 1175 / 0 |
| Yaw −, pitch + | −4.113, +4.045°/s | 903 / 1201 / 134 |

**VERIFIED:** original gated RHC readings, genuine RCS outputs, signed vehicle
response, quaternion-derived gimbals, lossless generated/delivered/consumed/
enqueued/applied sensor identities, neutral input and quiet queue settlement.
The repeated combined raw trace was byte-identical. Native adapter SHA-256:
`154a8706c7922f194e75e514055a19913cb468040f4c12bac212133d8c25506c`.

The real HTTP experiment started its first deflection at the actual UI-ready
call **2,200,000**, held yaw +/pitch − with heartbeats, explicitly released,
then abandoned a negative-yaw deflection to test expiry. It observed genuine
signed RHC copies, 655 RCS packets, 36 RHC-gate observations, signed initial
responses of +1.866/−1.855°/s, automatic neutral at its native deadline, and
settled sensor queues. An unauthenticated start returned 403.

Browser checks exercised D then S keyboard holds and negative-yaw then
positive-pitch button holds. Both produced live RCS, rates and CDU changes.
The first run ended at the bounded horizon; the second stopped early using
**Stop run**. Downloaded browser records matched the finalized gateway records.
Desktop and 390-pixel phone layouts were inspected. No browser warnings/errors
were observed during these checks. Touch hardware itself was **NOT RUN**.

## Reproduction and regression checks

```sh
make check
make test-live                         # Python 3.9+, Node 20+, local socket permission
python3 -B -m unittest discover -s docs/live-control-evidence -p 'test_*.py' -v
make validate-live                     # new actual native and HTTP runs
python3 -B docs/live-control-evidence/verify_package.py
```

The captured executions used macOS arm64, Python 3.9.6, Apple clang 21.0.0,
locked Tcl 8.6.16, and the recorded bundled Node executable. Exact commands,
versions, file hashes, stdout/stderr and exit codes are retained. Linux and
other host toolchains remain **NOT RUN** for this integration.

| Final check | Actual result |
|---|---|
| Historical Phase 2–6 suites | 35 passed, **3 known missing-log errors** |
| Packaging tests | 55 passed |
| Milestone 2 tests | 47 passed |
| Milestone 3 tests | 34 passed |
| Phase 7 tests | 39 passed |
| Backend/native/worker/HTTP contracts | 32 passed |
| Frontend Python provenance/export | 12 passed |
| Frontend Node replay/live contracts | 22 passed |
| New captured live-trace tests | 9 passed |

Total: **285 passed, 3 historical errors**. No existing assertions or reference
comparisons were weakened. `make check` also freshly reproduced Phase 6 and
ran Milestone 2, Milestone 3 and Phase 7 native validations. Its classified exit
zero does not convert the three historical errors into passes.

An initial restricted final-check attempt encountered 11 HTTP socket-bind
permission errors. A separately recorded run with loopback permission passed
all 32 backend tests. The actual HTTP experiment likewise retains its restricted
bind attempt separately from its successful permitted run. Neither is hidden
or classified as an authentic-control failure/pass without execution.

## Evidence and limits

All **2,572 protected prior documentation/evidence/tooling files** matched
their starting SHA-256 hashes. Existing phase evidence and replay data remain
unchanged. New results live only under `live-control-evidence/`:

- `runs/2026-10-17-verified/validation/`: six actual native traces, plans,
  analysis, source/runtime/build provenance and exact replay comparison.
- `runs/2026-10-17-http-verified/`: real HTTP requests, execution source,
  gateway record, raw native trace and expiry/settlement analysis.
- `release-checks/2026-10-17/`: both final-check attempts, fresh regression
  runs, browser gateway/native traces, downloads, screenshots and executed code.
- Development attempts are retained with their actual failures and stated
  preservation gaps. Missing original logs or old adapter text were not
  reconstructed.

**ASSUMED:** the Phase 7 synthetic inertia, torque arms and ideal alignment
remain adequate for this bounded demonstrator. They are not calibrated Apollo
mass properties or validated jet geometry. Conservative guards reject alignment
activity, main-engine commands, high component rates, large middle gimbal angles,
unsupported slow CDU rates and excessive queues rather than bypassing readiness.

**NOT RUN / unverified:** arbitrary attitudes, unrestricted manual operation,
sustained stability, independent roll, mobile touch hardware, mission padload,
PIPA navigation, landing radar, descent propulsion, orbital translation and a
complete landing. No frontend physics, multiplayer, networking service or AI
crew was added. The new server is a bounded local control gateway.
