# Phase 3 — Minimum AGC-to-physics integration

Run date: 2026-10-17 UTC. **Investigation and one minimum instrument integration experiment only.** No frontend, multiplayer, AI crew, full vehicle model, or lunar physics engine was built. Phases 1 and 2 remain unchanged; `phase3-evidence/prior_hashes.json` fingerprints their reports and every retained evidence file before this phase.

**VERIFIED** means observed in cited source or actually executed, as distinguished below. **ASSUMED** means model interpretation not physically validated. **NOT RUN** means not executed. Prose channels, source addresses and alarms are octal; JSON numbers and schedule timing are decimal.

## Verdict

**VERIFIED execution: original Luminary099 generated coarse-alignment actuator commands, a synthetic IMU gimbal moved, changed angle measurements returned through the emulator's CDU interface, and Luminary checked those measurements and took its successful completion branch.** Suppressing sensor return—or suppressing actuator application—caused the original AGC to take the failure branch and record **00211**, the source-defined coarse-alignment error.

This establishes a **genuine instrument feedback loop**, not spacecraft attitude control or powered descent. The modeled moving object is an IMU gimbal inside a stationary synthetic LM. It does not establish descent-engine control, RCS vehicle response, a landing, or historical flight dynamics.

All runs contain the pre-existing cold-start **01107** alarm. The successful alignment is therefore **not an alarm-free initialization**; that alarm remains unexplained. No readiness flag was written to bypass software checks.

## 1. Prior evidence and choice of minimum loop

Reviewed `PHASE1_PROOF_PLAN.md`, `PHASE2_POWERED_DESCENT_FEASIBILITY.md`, the Phase 2 native driver and preserved rope/interface evidence. Phase 1 established machine-code execution and DSKY behavior. Phase 2 established agreement between builds and cold-start P63 dispatch, not initialized powered descent.

**VERIFIED source inspection:** the inspected throttle protocol still requires counter THRUST=055 plus channel014 bit4 handling; radar completion hooks supply no measurement in the inspected backends. Their closed descent paths were not implemented or rerun here. Using them would add more unverified hardware work and require unavailable descent initialization.

The existing alternative is **V41N20 IMU coarse alignment**:

1. Physical instrument state: synthetic X/Y/Z gimbal angles, initially zero; stationary vehicle.
2. Sensor: quantized angles returned as CDU counter increment/decrement packets.
3. CPU: unmodified pinned engine executes the original Luminary099 rope.
4. Actuator: consume actual emulator output 0174–0176 only while channel012 coarse-align enable is set and zeroing is not asserted.
5. Plant: signed pulse bursts move the corresponding gimbal; subsequent sensor packets reflect that movement.
6. Software response: Luminary compares measured CDU with requested THETAD after settling; success/failure differs when feedback is removed.

**VERIFIED source:** `Luminary099/EXTENDED_VERBS.agc:235–317` dispatches V41N20, requests V25N22, accepts desired angles, calls IMUCOARS then IMUSTALL. `IMU_MODE_SWITCHING_ROUTINES.agc:155–179` computes THETAD minus measured CDU; `185–264` issues a finite command train, waits, and checks the returned angles against approximately 2 degrees tolerance. Failure records 00211 (`235–244`). Successful final mode checks take IMUGOOD (`692–722`).

**Important:** this is not a continuously recomputed guidance servo. Commands are computed, applied in chunks, and the measured result is checked afterward. The disconnected controls establish that feedback affects original software behavior.

## 2. Verified interface contract

| Interface | Semantics | Source |
|---|---|---|
| 0174 / 0175 / 0176 | X / Y / Z CDU drive bursts | `yaAGC/agc_engine.c:1630–1685,2412–2423`; `AGC_IMU.tcl:463–492` |
| Burst value | Sign-magnitude: 040000 means negative, 037777 masks magnitude; maximum 24 decimal pulses per current smoothed burst | Same engine implementation; COARSE_SMOOTH=8 |
| Coarse gating | Channel012 bit4=1 permits gimbal movement; bit5=1 inhibits movement | `AGC_IMU.tcl:470–505` |
| Plant pulse scale | **0.043948 degrees/pulse**, literal existing simulator constant, not a historical calibration claim | `lm_simulator.tcl:142–144` |
| Sensor scale | **360/32768 degrees/count** | Same constants; `AGC_IMU.tcl:500–600` |
| Sensor addresses | Counter addresses 032 / 033 / 034; packet channel = 0200 OR address | `ringbuffer_api.c:134–139`; `AGC_IMU.tcl:520–595` |
| Sensor operations | 001 / 003 slow positive/negative; 021 / 023 fast positive/negative; one request per count, not an angle write | `lm_simulator.tcl:129–133`; `agc_engine.c:1570–1602` |
| Counter application | CDU FIFO applies slow/fast at nominal 400/6400 counts/s; 15-bit modulo-32768 arithmetic | `agc_engine.c:1246–1275,1363–1560` |
| Host output packing | packet_read returns channel shifted by **16**, value in low 15 bits | `wasm.c:170–179`, despite stale bit15 comment |

These outputs are emulator convenience channels for simulated hardware, **not claims that physical AGC hardware used channel0174 wires**. The host drains outputs every cpu_step; it supplies at most one sensor packet per cycle, then lets the upstream FIFO pace applied counts. Accepted packets are distinguished from read-back counters.

The model retains accumulated floating-point angle and truncates cumulative sensor counts toward zero. For these monotonic, away-from-boundary X fixtures this reproduces the pinned simulator's residual-count behavior; it is **not** a full implementation of its wrapped-angle, gimbal-lock, reversing-motion or coordinate-transform behavior. Fast CDU operations are deliberately selected for these short bursts; both operation codes and the downstream rate limiter are verified. Slow-mode equivalence is NOT RUN.

## 3. Exact synthetic conditions and executed procedure

Source revision: `virtualagc/virtualagc` **f577e3fd917866c59334e6cdd32504f09df76f60**. The prior `/tmp` source was absent in this sandbox, so the exact pinned codeload archive was restored to `/tmp/apollo/va`. Archive SHA-256 **1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267** matches Phase 1. Download log: `restore.log`.

Rope reused without changes: `docs/phase1-evidence/artifacts/MAIN.agc.bin`, 73,728 bytes, SHA-256 **1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e**. No mission data, RAM initializer, saved core, synthetic guidance, or actuator-output generator was substituted.

Each run is a fresh process. cpu_reset clears RAM and sets Z=04000; reset channel030=037777 and 031/032/033=077777 (`agc_engine_init.c:250–265`). No switch packets or direct RAM writes are made. These defaults and initially zero angles are **synthetic diagnostic conditions**, not historical aligned mission state or a realistic IMU power-up. The exact fixture works without the broader simulator's recommended V36/P00/startup sequence; that broader sequence was not exercised.

Schedule: **8,000,000 cpu_step(1) calls**, first key at cycle **426665**, subsequent keys every **21333** cycles, zero-based input indices. Positive sequence:

```text
V41N20E+01000E+00000E+00000E
```

Negative sequence changes +01000 to −01000. N22 inputs mean desired absolute X=±10.00°, Y=0°, Z=0° according to the pinned simulator documentation (`Documentation/readme.html:236–240`). `E` is ENTR. All 28 keystrokes go through channel015/KEYRUPT. No PRO or engine grant is sent. Eight million cycles is a bounded ~93.76 seconds using upstream's 11.72 microsecond step convention, not independently measured hardware time.

New test harness `gimbal_loop.c` only reads RAM for evidence; flight computation remains in the original rope. Native link uses unchanged upstream wasm.c, engine/reset/utilities and ringbuffer sources. Compilation/command exit records, environment and source fingerprints are in `runs/`.

## 4. Results — VERIFIED execution

| Run | Physical X angle | Sensor / final CDU X | Original software outcome | Final FAILREG |
|---|---:|---:|---|---|
| Positive closed | +10.020144° | +912 counts / 912 | IMUGOOD reached, target 910 | 01107,00000,00000 |
| Fresh positive repeat | Same | Same | Complete transcript byte-identical | Same |
| Sensor return disabled | +10.020144° | 0 sent / 0 | IMUBAD reached; 00211 recorded | 01107,00211,00000 |
| Actuator application blocked | 0° | 0 sent / 0 | IMUBAD reached; 00211 recorded | 01107,00211,00000 |
| Negative closed | −10.020144° | −912 counts / 31856 modulo 32768 | IMUGOOD reached, target 31858 | 01107,00000,00000 |

Each positive or negative command produced **10 nonzero X actuator packets**, total **228 signed pulses**, and **912 accepted counter-operation packets**. Y/Z remain zero. The 2-count target discrepancy is 0.02197265625°, within the source-defined coarse tolerance; no host guidance calculation corrected it.

Causal chain in positive transcript:

- Cycle **1013503**: actual 0174 packet value 24, coarse enabled; host angle becomes **1.054752°**, sensor position quantizes to 96 counts.
- Subsequent sensor packets request positive X CDU counts through packet channel0232, operation021. Sampled CDU counter changes after FIFO processing, not by direct RAM assignment.
- Final drive at **1071094** brings accumulated angle to **10.020144°** and quantized sensor to 912 counts.
- Cycle **1243824**: CHKCORS=07,3073 reached; sampled THETAD=[910,0,0], measured CDU=[912,0,0].
- Cycle **1243886**: **IMUGOOD=07,3636** reached after the tolerance/final status checks.
- Identical crew input with sensor return suppressed reaches **IMUBAD=07,3637 at 1243915**; 00211 appears by the cycle1250000 sample. Plant motion alone therefore does not satisfy AGC validation.

Checkpoint records are observed program-counter visits before the instruction at the address executes; later visits/alarms support the branch interpretation. COARSERR itself can be visited for a small acceptable nonzero error; **that label alone is not failure**. We distinguish the subsequent IMUGOOD versus IMUBAD branches and FAILREG.

**Acceptance:** intended sensors received/read back PASS; genuine actuator output PASS; output changes modeled physical instrument PASS; new readings reflect change PASS; original software responds to feedback PASS; reproduction PASS. Powered descent **NOT RUN**. Tests assert concrete packet values, physical deltas, counter values, branches, negative controls and byte-for-byte replay; no styling/snapshot tests.

## 5. Reproduce without overwriting captured evidence

From project root with the pinned source restored under /tmp/apollo/va:

```sh
python3 docs/phase3-evidence/run_experiment.py /tmp/apollo/va /tmp/apollo/phase3-reproduction
python3 -m unittest discover -s docs/phase3-evidence -p 'test_loop.py' -v
```

The runner requires a **new** output directory, compiles and runs five fresh processes, and preserves exact commands, stdout/stderr and exit codes. Its logged compile links:

```sh
gcc -O2 -I/tmp/apollo/va/yaAGC docs/phase3-evidence/gimbal_loop.c \
  /tmp/apollo/va/yaAGC/{wasm.c,agc_engine.c,agc_engine_init.c,agc_utilities.c,ringbuffer_api.c,ringbuffer.c,rfopen.c} \
  -lm -o /tmp/apollo/gimbal_loop
/tmp/apollo/gimbal_loop docs/phase1-evidence/artifacts/MAIN.agc.bin \
  docs/phase3-evidence/positive_inputs.txt closed
```

The unit tests validate the **retained** `runs/` evidence; newly reproduced outputs can additionally be compared against positive.stdout after confirming input/source identity. Five final runs and compilation exited 0. `tests.log` records actual test results.

Earlier exploratory logs are retained: `attempt01_closed.jsonl`, `attempt02_open.jsonl`, `attempt03_negative.jsonl`, with stderr. These used the exact rational drive approximation 360/8192° instead of the literal Tcl constant and lacked source-PC checkpoints. Their physical-angle reports must not be confused with final runs. Commands were the same build/input/mode form above, executable `/tmp/apollo/p3build/gimbal_loop`; all exited 0. The final driver corrected the scale to the pinned literal and added checkpoints. `symbol_build.log` records a fresh yaYUL build/assembly solely to resolve those new checkpoint/RAM addresses; prior evidence/binaries were not overwritten. Assembly succeeded with the known erasable warning.

## 6. Limitations, blockers and next milestone

**ASSUMED model interpretation:** instantaneous pulse-driven gimbal motion using the existing simulator calibration is adequate for this interface experiment. Real motor lag, gyro mechanics, calibration, gimbal coupling, noise and hardware timing are not validated. No measured Apollo flight values were used.

**NOT RUN:** RCS vehicle attitude loop, PIPA acceleration feedback, full three-axis instrument tests, reversal/FIFO stress, gimbal lock/wrap, slow-mode timing, fine torquing, long-term real-time pacing, or this new loop in WebAssembly/browser. Phase 2 browser agreement is not automatically extended to this new integration.

Remaining powered-descent blockers: authenticated Luminary099 Rev-1-compatible mission initialization and synchronized vehicle/peripheral state; unresolved cold-start 01107; verified throttle counter/enable interface; actual scaled radar measurements at the completion hook; authoritative vehicle dynamics and IMU/PIPA synchronization. None is bypassed by V41 alignment, and a gimbal alignment must not be relabeled a landing.

**Recommended next milestone, not implemented:** isolate 01107 and validate a minimum RCS-driven single-axis vehicle-attitude/CDU loop with recorded synthetic conditions and actuator/feedback disconnect controls. Keep vehicle rotation distinct from IMU platform torquing. Establish signs, scaling and initialization before expanding to descent. Historical descent must additionally wait for authenticated mission data and throttle/radar validation.

## Evidence and licenses

- `source_excerpts.txt`: numbered new mapping/completion source excerpts and SHA-256 identities.
- `prior_hashes.json`: prior reports/evidence preservation baseline.
- `gimbal_loop.c`, input fixtures, runner, tests: minimum integration instrumentation.
- `runs/`: actual final build, five transcripts, stderr, commands, environment and source/input hashes.
- `attempt*`, `build.log`, `symbol_build.log`, `restore.log`: exploratory/build provenance; no failures or preliminary evidence were replaced.
- `results.json`, `tests.log`, `sha256.json`: computed results, regression output and evidence manifest.

Flight assembly is public-domain source as previously documented. The linked emulator is GPL-2.0-or-later; this test harness uses that license. Corresponding emulator source/license files remain preserved in Phase 2's `artifacts/yaAGC-corresponding-source.tar.gz`; the full pinned archive is downloadable at `https://codeload.github.com/virtualagc/virtualagc/tar.gz/f577e3fd917866c59334e6cdd32504f09df76f60`. No new emulator binary is delivered as a product.