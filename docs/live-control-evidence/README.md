# Live AGC control evidence

This directory records the new local frontend-to-native-AGC integration. It is
separate from the preserved Phase 1–7 and frontend recording evidence. All
spacecraft measurements here are generated simulation results, not Apollo 11
flight telemetry.

**VERIFIED:** four signed independent yaw/pitch inputs, simultaneous yaw/pitch,
and a byte-identical simultaneous replay executed original Luminary. A separate
real HTTP experiment applied its first positive-yaw/negative-pitch command at
the UI readiness boundary, call 2,200,000; original gated RHC reads, actual RCS
outputs, body response, returned CDU operations, explicit release, abandoned
input expiration and settled queues were observed. Browser controls were also
exercised against an actual native session. See the
[completion report](../LIVE_ATTITUDE_CONTROL.md).

`prior_hashes.json` freezes 2,572 tracked documentation, evidence, tooling and
instruction files from repository revision
`e8197c8d5227b5a425c5f6529147ba918c0fc67f` before this work. Existing evidence is
checked byte for byte before and after each validation batch.

## Reproduce the live experiments

From the repository root, after building or verifying the pinned runtime:

```sh
make runtime
python3 -B docs/live-control-evidence/run_validation.py
python3 -B docs/live-control-evidence/run_http_validation.py
python3 -B docs/live-control-evidence/run_tests.py
```

The validation creates a new `.build/live-control/validation/` directory. It
starts fresh original Luminary executions through the pinned native engine and
the retained external Phase 7 vehicle/sensor model. It does not read replay
frames or supply RCS packets. Fresh output is required; previous attempts are
never overwritten.

The predeclared input cases are yaw positive, yaw negative, pitch positive,
pitch negative, simultaneous negative yaw/positive pitch, and an identical
simultaneous replay. Each uses the same original startup, a fixed input call
boundary at 2,500,000, a bounded command lease, automatic neutral RHC input and
a physical cutoff at 3,200,000 calls. The raw trace, actual API requests and
responses, environment, commands, code/source/runtime hashes and preservation
checks identify what actually executed. Complete trace identity is required for
the repeated simultaneous case. The HTTP validator needs permission to bind a
loopback port; a restricted bind failure does not execute or validate the AGC.

## Actual results

The final six-case native batch ran 2026-10-17 17:07:46–17:08:16 UTC with adapter
SHA-256 `154a8706c7922f194e75e514055a19913cb468040f4c12bac212133d8c25506c`.
Each recorded generated/delivered/consumed/enqueued/applied operation count
agreed exactly:

| Native case | Applied CDU operations X/Y/Z | Signed response during hold, °/s |
|---|---|---|
| Yaw positive | 906 / 0 / 0 | +4.110662 yaw |
| Yaw negative | 910 / 0 / 0 | −4.110547 yaw |
| Pitch positive | 0 / 1175 / 1 | +4.037385 pitch |
| Pitch negative | 0 / 1175 / 0 | −4.037678 pitch |
| Simultaneous yaw negative / pitch positive | 903 / 1201 / 134 | −4.112598 yaw, +4.045156 pitch |

The simultaneous replay reproduced the complete raw bytes. Counts are total
signed operations, not net counter angles. All actual queues emptied, remained
quiet for 1,000 CPU calls, and settled actual CDU angles agreed with independently
quaternion-derived gimbals within one quantum (0.010986328125°). Largest native
case residual was 0.009835529°.

The separately retained HTTP experiment made seven pilot requests and six
non-neutral native commands. It observed 36 original RHC gated-read outputs and
655 genuine RCS packets, with signed initial yaw/pitch responses of
+1.865766/−1.855290°/s. All 612 sensor operations (287/316/9) applied. Its queues
settled at call 2,353,857 and remained quiet through 2,354,857. The maximum final
counter/gimbal residual was 0.010344899°, below one quantum. HTTP wall timing is
recorded rather than claimed deterministic; deterministic equivalence is the
separate cycle-scheduled native experiment.

Verify this sealed evidence package and its associated current source files:

```sh
python3 -B docs/live-control-evidence/verify_package.py
```

The 12 native adapter unit tests and nine captured-trace checks passed. The
final combined regression record contains **285 passes and three known
historical missing-log errors**; the [completion report](../LIVE_ATTITUDE_CONTROL.md)
separates exact commands and suite counts. Unit checks exercise modern interface
rejections, thread ownership, immutable telemetry, integrity failures and sensor
mode bounds; they do not independently establish authentic control.

## Retained records

- `runs/2026-10-17-verified/`: final native commands, six lossless raw traces,
  analysis, code snapshots, original source/rope/runtime/build provenance.
- `runs/2026-10-17-http-verified/`: actual loopback requests and downloaded
  record, exact executed code, native trace and neutral/expiry/settlement analysis.
- `release-checks/2026-10-17/`: full regressions, actual browser interactions,
  screenshots, downloads, source snapshots and preservation results.
- `runs/startup-channel014-guard-attempt/`: actual failed early startup, its
  genuine output/failure trace, configuration, build and original-source
  provenance. The old adapter source text was not captured and remains a stated
  preservation gap; only its original declared hash survives. It was not
  reconstructed. The later source-justified guard was tested in fresh runs.
- `runs/failed-import-attempt-01/`: actual harness import-name collision before
  native execution; the local helper was renamed and fresh runs followed.
- `runs/development-attempt-02/`: successful development executions preceding
  asset/lifecycle hardening, with their exact captured adapter source.
- `runs/http-restricted-bind-development-attempt/` and
  `runs/http-restricted-bind-attempt/`: actual sandbox socket-bind failures,
  retained separately from the successful permitted HTTP run.

`retention.json` in each run identifies exact copied bytes, raw and compressed
SHA-256 values and omitted rebuildable binaries/source extractions. JSONL uses
deterministic lossless gzip; decompression reproduces original trace bytes.
Nothing substitutes for a missing historical log or missing executed source.

The hardware input boundary is source-derived RHC normal input: channel `031`
active-low switches/out-of-detent, yaw analog port `0167` and pitch analog port
`0166`, with positive or one's-complement negative counts. These are emulator
hardware inputs, not direct writes to flight memory, force, attitude or output
channels. Original Luminary chooses channel `005`/`006` RCS output. The modern
fixture integrates those actual latches and returns all three derived gimbal
measurements through the real native CDU counter queues.

Stopping explicitly freezes physical evolution and new sensor production,
drains already generated requests through original engine service, then checks
1,000 quiet CPU calls. Empty queues establish transport settlement, not a
stationary or stable spacecraft.

## Scope

The model assumptions and source mappings remain those documented in the
[Phase 7 report](../PHASE7_MULTIAXIS_VALIDATION.md). Operate-only, identity-aligned
startup is a reproducible fixture; it is not a mission padload or calibrated
flight IMU alignment. Effective inertia, component torque arms, rate-mode
selection and integration accuracy remain documented approximations. Arbitrary
attitudes, sustained stability, full three-axis control, translation, PIPA,
descent engines, radar and powered descent are not established by this UI.

HTTP and browser validation establish that user controls reach the native
session and release/timeout send neutral inputs. Pure presentation tests and
physics component tests do not independently prove authentic AGC control. The
bounded session and queue settlement do not establish sustained stability.
