# Paced single-axis negative yaw feedback

**VERIFIED:** real Luminary099 generates yaw RCS output, the retained external Tcl LM-7 model responds, and its signed CDU X pulses reach actual engine counter memory with reconciled delivery, consumption, FIFO enqueue and application. The corrected modern model selects fast mode at negative rates whose magnitude reaches 4 degrees/second. All connected finite workloads settle without rejected or silently lost pulses; a disconnected control changes genuine AGC commands. **ASSUMED:** the synthetic LM-7 dynamics and zero-state hardware fixture are suitable for this bounded experiment. This is simulated telemetry, not historical flight data.

## Reproduction and implementation boundaries

```sh
python3 docs/milestone3-evidence/feedback/run_validation.py \
  --source .build/milestone3/pinned-source \
  --tcl .build/reproducibility/runtime/bin/tclsh8.6 \
  --output .build/milestone3/new-feedback-run
python3 -m unittest discover -s docs/milestone3-evidence/feedback -p 'test_*.py' -v
```

The source directory must be an unchanged extraction of the retained 24-file Phase 6 archive. The CLI checks all 24 hashes, the authentic rope hash and earlier evidence preservation. It validates the Tcl source/build/runtime manifest and version, inferring the canonical manifest beside the runtime or accepting `--runtime-manifest`. `--cc` selects the recorded host compiler. The output must be a new scratch directory; retained destinations, existing outputs and symlink escapes are rejected. Every command records its actual exit, UTC times, arguments and PID. Workers inherit the runner's process group; interruption cleanup and an outer harness timeout can terminate the experiment without a detached worker.

This adds orchestration because the retained Phase 5 launcher cannot observe FIFO application, pace generated sensor bursts or distinguish settlement from acceptance. It does not introduce another emulator, flight algorithm or vehicle model:

- The library compiles the retained Milestone 2 `inspect_bridge.c` and Phase 5 `plant_bridge.c` together with the same unchanged pinned engine compilation units. The first includes upstream `agc_engine.c` once and exposes read-only FIFO state; the second preserves actual AGC output packets and their CPU-call indices. No flight RAM writes, readiness bypasses, absolute counter writes or injected actuator commands are present.
- Each fresh Tcl process executes the retained `plant_server.tcl` initialization and original `dynamic_simulation`/`update_RCS` routines. Original-selector mode runs that server unchanged. Corrected mode inserts one `source` after initialization to load `model/fix_selector.py`'s complete source-locked module. Its numerical change is only `abs($Omega_Yaw) < 4` at original X-selector line 527; its public wrapper rejects unsupported Y/Z increments before entering the original body. The generated source, exact diff and hashes are scratch artifacts with an audit record; the pinned original remains unchanged.
- Physics integrates each actual jet/zero-latch interval and fixed boundaries at most 853 CPU calls apart. Queue inspection steps the CPU one call at a time while a request is outstanding; this does not subdivide every physical integration step. The existing semi-implicit integration and LM-7 parameters remain assumptions. Ch005 nonzero, Ch006 bits outside its eight documented yaw jets, cross-axis CDU requests and nonzero Y/Z rates or gimbals fail closed.

## Initialization, time and sensor transport

Each case resets a fresh CPU process and Tcl model with zero rates/gimbals, using authentic Luminary099 rope SHA-256 `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e` and engine revision `f577e3fd917866c59334e6cdd32504f09df76f60`. It reuses the Phase 5 packet fixture, moves the complete V37E00E sequence to 1,600,000–1,727,998 calls and the complete V77E sequence to 2,000,000–2,063,999. These sequences do not collide. The checkpoint at 2,200,000 must observe P00 (`MODREG=0`), all three FAILREG words zero, both recorded IMU inhibition bits clear and zero cross-axis counters before motion.

This is a clean bounded operate-only startup checkpoint, not full alignment, calibration, valid REFSMMAT or mission initialization. V77's complete key sequence is delivered; a preexisting clear PULSES bit alone is not presented as proof that V77 changed it.

At 2,500,000, the synthetic active-low negative yaw controller discrete is channel031 decimal value 12279 (`027767` octal); channel0167 receives decimal 32747, the one's-complement encoding of −20. Neutral returns at 2,700,000–2,700,001. Source justification remains in Phase 4's RHC excerpts and the retained Phase 5 negative fixture; reading its echo alone is not claimed to establish DAP use. Actual original AGC Ch006 jet outputs establish actuator use.

Time uses the exact source convention of `12/1024000` seconds per CPU call (11.71875 µs), not the rounded earlier wrapper convention. The primary production interval ends at 4,000,000 calls (46.875 s). The maximum physical coupling interval is 853 calls (9.99609375 ms).

The modern pacing policy permits one outstanding accepted CDU X request until its **observed application**, and requires at least 214 calls between slow deliveries or 14 before a fast delivery. CPU execution continues throughout. Generated pulses retain their actual sign/rate and FIFO order. The host queue may accumulate; the policy is deliberately conservative and is not a claim about authentic hardware's minimum event spacing. Packet acceptance is never treated as immediate counter application.

Raw records distinguish `simulated_vehicle`, `simulated_sensor`, `agc_output`, `agc_diagnostic_readback` and diagnostic transport. A sensor's `origin` is the **end of the integrated discrete model interval**, not an observed continuous angle-quantum crossing. `available` is the CPU boundary at which that model result is processed, `delivery` is host ringbuffer insertion, `consumption` shows actual FIFO enqueue, and `application` records the actual FIFO head sign/rate, deadline and modular memory transition. Actual per-event times and complete request IDs permit independent reconciliation.

At the declared stop, plant evolution and new sensor production freeze explicitly. Existing queued requests continue through the genuine running CPU, with all genuine actuator output still recorded as a **diagnostic frozen tail**. Empty host/ringbuffer/FIFO queues and a further 1,000 quiet CPU calls establish transport settlement. No physical equilibrium is inferred from this frozen tail.

## Observed bounded results

| Case | Generated / delivered / consumed / enqueued / applied | Negative fast pulses | Peak absolute yaw °/s | Peak host queue | Final model yaw °/s |
|---|---|---:|---:|---:|---:|
| Original selector, negative RHC | 1439 / 1439 / 1439 / 1439 / 1439 | 0 | 5.646113 | 128 | +0.238274 |
| Corrected selector, negative RHC | 1582 / 1582 / 1582 / 1582 / 1582 | 691 | 4.858000 | 5 | −0.036645 |
| Corrected, feedback disconnected | 16169 / 0 / 0 / 0 / 0 | 16021 generated, none applied | 11.339958 | 0 | −10.843403 |
| Fresh corrected replay | Exact raw byte agreement with corrected case | 691 | 4.858000 | 5 | −0.036645 |
| Corrected short production cutoff | 501 / 501 / 501 / 501 / 501 | 338 | 4.858000 | 5 | −4.858000 at freeze |

All connected runs have zero explicit ringbuffer rejections and zero silent FIFO losses. Native FIFO occupancy never exceeds one entry/pulse under this pacing policy. Original-selector mode generates 825 slow negative pulses while model yaw is at most −4°/s; corrected mode generates none in that category. Correction is exercised by natural response to the same authentic controller fixture; no angular rate or state is forced.

Measured maxima in CPU calls, derived from actual raw records:

| Case | Origin→availability | Origin→delivery | Delivery→application | Origin→application |
|---|---:|---:|---:|---:|
| Original selector | 636 | 27351 | 219 | 27565 |
| Corrected selector | 710 | 710 | 220 | 925 |
| Corrected short cutoff | 593 | 648 | 217 | 862 |

The 853-call coupling bound is separate from transport latency. Original slow-mode backlog makes its observed origin-to-application maximum about 0.323 s; corrected mode's maximum is about 10.840 ms. These times begin at the discrete interval endpoint and do not establish total hardware feedback latency.

The corrected trace's first actual CDU application is at 2,514,859 and first actual negative fast application at 2,582,909. Its genuine Ch006 commands change while the same negative RHC input is still held: `0252` reduces to `0012` at 2,568,700 and later `0240` at 2,602,959; the disconnected control continues full `0252` during that held interval. After neutral, connected full positive word `0125` appears at 2,705,309, while disconnected mode emits `0120` at 2,705,353 and never emits full `0125`. Both modes can respond to controller release; braking-word timing alone is not presented as causal proof. The controlled sensor-disconnected comparison establishes feedback-dependent bounded command sequences, and model rates show the resulting finite response. It does not certify attitude stability.

The four primary runs have already emptied queues by 4,000,000. The separately declared short cutoff at 2,650,000 calls (before controller neutral) observes **three real host-queued requests** at freeze, applies all three during a 47-call frozen diagnostic drain, then completes 1,000 quiet CPU calls. The model remains frozen at −4.858°/s, so that probe establishes queue settlement rather than vehicle stabilization.

Twenty tests reconcile the retained actual five-case traces and reject altered counts, missing applications, wrong actual FIFO head/rate/deadline, wrong counter deltas, false settlement, recorded startup alarms, provenance mislabeling, latency violations, unsupported motion/packets/jet bits, non-finite data and unsafe output destinations. They require no Tcl cache or network; the full CLI performs fresh coupled execution with the locked runtime, and existing Milestone 2 tests rebuild the native FIFO observer independently.

## Captures and limitations

`runs/attempt-01` preserves an incomplete first implementation that mistakenly advanced Tcl on every one-call observer step. It was interrupted for excessive integration/trace volume; the top runner exited 130. A scoped SIGTERM request then stopped its detached worker; that worker's exit status was not captured. The 33,994,632-byte partial raw stream is retained losslessly as gzip with its uncompressed hash, actual termination command/result and executed source snapshot. It is not a passed experiment.

`runs/attempt-02` preserves four completed cases before the short drain probe, stricter reconciliation and final runtime/summary additions. `runs/attempt-03` preserves all five completed cases, actual commands and executed harness snapshot. Gzip files preserve original JSONL bytes; `raw-trace-hashes.json` checks their uncompressed hashes. Tests replay reconciliation against these genuine captured events. Later final-code validation may add further capture directories; earlier attempts are never overwritten or backfilled. Source revision, original fixture, source/rope/model/binary hashes, commands, versions and actual stdout/stderr are retained; build binaries and extracted upstream/runtime sources stay scratch.

**NOT RUN:** another supported axis, Phase 7, full physical IMU alignment/REFSMMAT, historically calibrated dynamics, DAP filter acceptance for every pulse, hardware clock validation, positive-sign full coupled comparison, a coupled WebAssembly replay, descent-engine/radar/PIPA integration, powered descent or landing. No frontend, multiplayer or AI crew work is included.
