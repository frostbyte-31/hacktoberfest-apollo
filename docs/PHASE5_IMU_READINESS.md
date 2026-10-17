# Phase 5 — IMU readiness and autopilot initialization

2026-10-17 UTC. Investigation and bounded native validation only. **VERIFIED** denotes source inspection or retained execution, identified below; **ASSUMED** denotes an unvalidated model or interpretation; **NOT RUN** denotes no execution. Channels, addresses, flags and alarms in prose are octal unless stated otherwise. JSON and schedules use decimal integers.

## Verdict

**VERIFIED — diagnosis:** the Phase 4 probe left the active-low **IMU OPERATE** input deasserted. Channel030 remained **036777**, whose bit9 is one: IMU off. Original Luminary099 legitimately kept the DAP disabled. This was an incomplete diagnostic integration fixture, not proof of a missing RCS interface or a defect in the flight software.

**VERIFIED — justified correction:** change only channel030 bit9, **036777 → 036377** (decimal15871 →15615). Original operate-only initialization executes, performs ICDU zeroing and its settling delay, then **ISSUP itself clears IMODES33 bit6**. No external readiness-memory write, fabricated sensor count, patched rope or substituted guidance is used. Original STARTDAP executes and actual channel006 RCS commands appear.

**VERIFIED — bounded feedback execution:** those actual RCS outputs drive the pinned simulator's active vehicle model, its body-to-gimbal transformation generates CDU operations, the emulator's CDU counters change, and original AGC commands differ when feedback is disconnected. Blocking actuators removes motion; opposite controller input reverses initial jet selection and body rotation. Exact fresh replay is byte-identical.

**ASSUMED — physical fidelity:** the vehicle is the existing model's **synthetic LM-7 defaults**, not authenticated Apollo11 dynamics, calibration or mission state. This demonstrates an AGC-to-model spacecraft-attitude feedback path, **not historical landing accuracy, complete alignment, general three-axis control certification or powered descent**.

## 1. Evidence reviewed and preserved — VERIFIED

Reviewed Phase4 report, diagnostic harness/schedule/runner, address resolution, recorded outputs and prior interface findings. Fingerprinted **109** Phase1–4 documentation/evidence files before new execution (`phase5-evidence/prior_hashes.json`); final preservation check has **zero mismatches**. Nothing under earlier phase directories or earlier reports was changed.

The new baseline's initial/input/output/sample records are exactly equal to Phase4's preserved probe records. Expanded read-only instrumentation adds instruction checkpoints without changing emulator behavior. It reproduces **469 SHUTDOWN visits, zero STARTDAP visits and 942 RCS packets, all zero**. This is the requested reproduction, not a newly invented failure.

## 2. Authentic readiness requirements — VERIFIED source inspection

### First DAP gate

`Luminary099/DAPIDLER_PROGRAM.agc:46–60` tests:

1. Channel031 bits13/14: both one means mode off. The probe selects attitude hold, so this is not its failed condition.
2. Complement IMODES33, mask bit6, CCS: if bit6 was set, take the IMU-unusable path, set the attitude-display initialization flag in RCSFLAGS and call SHUTDOWN.
3. Only after that usable gate does the control path check PGNCS ownership and further DAP conditions (`:62–105`).

`SHUTDOWN` writes zero to channels005/006 (`:182–194`). Therefore “PGNCS selected” or an accepted controller packet is insufficient; a cleared final alarm register also does not establish IMU readiness.

### Software-owned readiness flag and initialization chain

| Variable/interface | Source-supported requirement |
|---|---|
| IMODES33, erasable01303, bit6 | DAP unusable/inhibited state. Fresh start explicitly sets it (`FRESH_START_AND_RESTART.agc:152–154`). |
| IMODES30, erasable01302 | Last sampled channel030 IMU status plus internal initialization/inhibit flags. IMUMON detects changes every480ms (`T4RUPT_PROGRAM.agc:250–321`). |
| Channel030 bit9 | **Active low IMU OPERATE**. Zero invokes IMUOP2/ITURNON2; one invokes IMU-off DAP inhibition (`:832–876`). |
| Channel030 bit14 | Active-low turn-on request; absent for the operate-only path. Full cold turn-on has a separate90-second protocol (`:322–445,707–753`). |
| Channel030 bit11 | Active-low cage button; held high/released in this fixture. Caging disables DAP and changes platform mode (`:763–826`). |
| Channel030 bits12/13 | ICDU/IMU failure inputs; healthy/deasserted high here. SETISSW handles warning logic, not proof of historical calibration. |
| IMODES30 bits7/8 | One-monitor-sample pairing delay before PROCTNON processes operate/turn-on requests (`:340–390`). |
| OPONLY → CAGESUB2 → ISSZERO | Operate-only initialization unless already coarse/gimbal-locked or IMUSE is active. Sets initialization/inhibit flags, asserts channel012 bit5 and calls ZEROICDU (`:478–502,1037–1045`). |
| UNZ2 → ISSUP | After320ms, zero counters again, remove zero/coarse discretes, wait executable **10.24s** via BIT11/VARDELAY, then clear caging/failure inhibits and **clear IMODES33 bit6** (`:439–454`). Comments include rounded10s and a stale4s summary; the instructions and recorded execution are the authority. |
| CDU counters032/033/034 | Original ZEROICDU writes them to zero (`IMU_MODE_SWITCHING_ROUTINES.agc:53–58`). Subsequent movement is represented by counter operations, not absolute sensor-word writes. |

Other software-owned clear paths include IMUZERO3 and fine-alignment completion (`IMU_MODE_SWITCHING_ROUTINES.agc:127–134,330–332`). IMUZERO, SETCOARS, IMU-off and CAGESUB2 set inhibition; restart preserves its state. V41 coarse-alignment success alone is not a DAP-ready certificate. REFSMMAT validity and historical inertial alignment remain separate from this gate: this operate-only path does not establish an authenticated reference matrix or full guidance initialization.

### Software versus simulator assumptions

The pinned simulator explicitly supplies startup discretes, including IMU OPERATE (`Contributed/LM_Simulator/lm_simulator.tcl:565–599`, channel030 word036331). The Phase4 ringbuffer probe did **not** invoke that startup; it inherited emulator reset037777, then changed only PGNCS ownership to036777. Healthy failure lines and zero gimbals were diagnostic conditions, not a synchronized complete ISS startup.

**VERIFIED:** source and captured input words establish the missing operate input. **ASSUMED:** an already-operating, stationary, zero-angle synthetic IMU is an appropriate minimum boundary condition for this instrument/control experiment. No historical initial attitude, drift bias or readiness was inferred from it.

## 3. Captured first failure and correction — VERIFIED execution

Immediately before CHEKBITS's IMU test, baseline snapshot cycle**105853** sees bank16 Z02007, channel030=036777, channel031=067777, IMODES30=037411, IMODES33=036040, DAPBOOLS=021316, channel012=0 and CDU=[0,0,0]. The mode switch gate has passed; **IMODES33 bit6 is set**. The source-complement/mask/CCS branch takes shutdown. No IMUOP, OPONLY or ISSUP checkpoints occur in baseline.

`operate_inputs.txt` differs from `baseline_inputs.txt` at **one scheduled word only**, cycle100001, clearing channel030 bit9. Everything else, including V36E, V37E00E, V77E and the later controller pulse, is retained for causal comparison. No emulator or flight source is edited.

Observed corrected chronology (decimal cpu_step-call indices; checkpoint counts can include multiple calls spent at one instruction, not distinct routine invocations):

| Observation | Cycle |
|---|---:|
| First IMUOP checkpoint, bank06 Z02622 | 135167 |
| First PROCTNON / OPONLY | 176072 /176083 |
| Channel012 zero discrete first asserted | 176158 |
| First UNZ2 | 203609 |
| V36 initiates fresh-start initialization again; second zero interval | 578933–606398 |
| ISSUP entry | 1480197 |
| Before ISSUP's TS IMODES33, bank06 Z02326: A=036000, IMODES33=036040 | 1480208 |
| Next instruction Z02327: IMODES33=036000 | 1480209 |
| Original STARTDAP, bank16 Z02046 | 1484080 |
| First actual nonzero006 word0125 | 2509125 |

A late **IMU-off causal control**, channel030 bit9 restored at2200000 before the controller pulse, restores IMODES33 bit6 and yields **zero nonzero RCS outputs**. Operate-only probe emits25 nonzero RCS words; baseline emits none. Fresh corrected replay is byte-identical.

### Residual alarms and mode status

**VERIFIED:** early cold-start01107 remains at cycle10000 and is cleared by V36; its initiating cause has not been isolated. Corrected run additionally records **01520** after the attempted V37E00E, first present at sample1130000. IMODES30 still has its initialization/caging bit6 set at this time. `FRESH_START_AND_RESTART.agc:748–780` refuses V37 during initialization before accepting a new major mode. ALARM is non-abortive and returns to display processing; this code does not itself initiate a restart. The failed P00 request leaves final MODREG077777, **not P00**.

**VERIFIED:** the state/source are consistent with the initialization rejection; **NOT RUN:** a dedicated instruction-level V37 branch trace. Do not infer complete major-mode initialization from DAP entry. Both01107 and01520 are disclosed rather than hidden by rerouting the test or clearing final registers. These limitations do not negate the captured ISSUP clearing store, subsequent DAP entry, actual jet output or feedback dependence, but preclude a clean mission-readiness claim.

## 4. Actual RCS → spacecraft model → CDU → AGC — VERIFIED bounded execution

### Method and initial conditions

`plant_bridge.c` links the same unchanged pinned engine, reset, utilities, ringbuffer backend and wrapper. It steps original flight software, preserves every output with its CPU-call index and provides read-only inspection. Python transports actual packets to a separate Tcl process; Tcl loads the **active unmodified** AGC_Simulation_Monitor_Control and AGC_IMU modules with literal main-file initialization lines124–241. Fresh CPU/plant processes for each run; no restored core or padload.

Initial synthetic vehicle: upstream LM-7 defaults, zero body rates/gimbals, engines off, healthy operate-only IMU fixture. Channels005/006 are latched from actual emulator output, not injected test jets. Mapping follows pinned main dispatcher:006 bits1–8 are Q3A/Q4F/Q1F/Q2A/Q2L/Q3R/Q4R/Q1L. Positive yaw sum is Q1F+Q2L+Q3A+Q4R minus Q1L+Q2A+Q3R+Q4F (`AGC_Simulation_Monitor_Control.tcl:237–242,293–297`).

The active transform receives body yaw as its first argument (`:213–214`), which becomes same-sign X-gimbal motion for zeroY/Z (`AGC_IMU.tcl:660–692`). These are simulator axis names, not a general Euler-axis assertion. The final harness rejects nonzero005, cross-axis rates/gimbals or non-X CDU feedback. None occurred in retained runs.

**Timing disclosure:** advance in chunks of at most853 CPU calls (~9.998ms under the wrapper's11.72µs convention), splitting at scheduled inputs. Within each chunk, integrate the plant over actual time-stamped jet/zero-discrete latch intervals. Deliver generated sensor requests **at chunk end**, before the next CPU chunk, not at their exact origin interval boundary. This is deterministic bounded-latency coupling, not exact hardware-event-time equivalence. Logs preserve both timestamps. Rate update precedes angular update: **semi-implicit numerical integration**, inherited from the active model calls. No host wall-clock/socket scheduling controls dynamics.

**Zeroing/interface disclosure:** output channel decimal10 is **octal012**, value bit16 decimal is its bit5 zero inhibit. The plant honors the actual discrete. A stationary zero-angle IMU generates no movement pulses during initialization; the software itself performs counter zeroing. Moving feedback uses type bit0x80 plus counter032 and PCDU/MCDU codes001/003 or021/023, correctly parsing Tcl address text `32` as **octal**. The unchanged emulator queues these at400/6400Hz (`agc_engine.c:1363–1412`); they are not absolute angle writes.

### Results

All runs end at4000000 CPU calls (~46.88s convention). Controller pulse begins2500000, neutral restored2700001. Positive fixture006 first word0125; opposite fixture first word0252. Values below are actual recorded outputs of the existing synthetic model, not historical Apollo parameters.

| Run | Generated / delivered sensor operations | Peak abs yaw rate °/s | Final yaw rate °/s | Final X-gimbal ° | Final AGC CDU X |
|---|---:|---:|---:|---:|---:|
| Connected | 1539 /1539 | 4.859385265209125 | −0.027477428680504824 | 16.84156247751019 | 1533 |
| Feedback disconnected | 16173 /0 | 11.341167317374987 | 10.844530345898027 | 177.68649693043514 | 0 |
| Actuators blocked | 0 /0 | 0 | 0 | 0 | 0 |
| Opposite controller | 1468 /1468 | 5.620591215542955 | +0.2640469737156175 | 351.2199656435405 (wrapped negative angle) | 31968 |

Connected first nonzero CDU readback: cycle2515355, X=1. Negative readback at the same sampled cycle is077777 (two's-complement CDU wrap). Y/Z and their body rates remain zero.

**VERIFIED causal evidence:** connected AGC emits opposite-sign braking words0252 (seven nonzero packets), whereas feedback-disconnected run emits none of that word. Whole005/006 transcripts differ. Blocking application of actual AGC jets leaves the AGC issuing commands but yields no body motion or sensor operations. Disconnecting sensor delivery allows body motion but leaves original CDU counters at zero. This establishes feedback-dependent original-software behavior, not merely packet acceptance or an isolated injected-jet component test.

**VERIFIED replay:** connected fresh replay is byte-identical. After adding explicit single-axis rejection guards, all five fresh traces remain byte-identical to their earlier captures (`safety_guard_replay.json`).

**Limitations:** positive and negative response are not numerically symmetric; the unchanged upstream IMU uses `Omega_Yaw <4`, not absolute rate, for slow/fast selection (`AGC_IMU.tcl:527–530`). Negative rates therefore stay slow even above4°/s magnitude. This inherited behavior was **not corrected** or masked; counter queue lag and end-state differences prevent claims of equivalent sign performance or calibrated sensors. Generated counts need not equal settled final counters; queues are not explicitly drained after the final cycle. Brief reduced residual connected rate is an observation, **not long-duration stable-hold/braking certification**. Historical jet coefficients, inertia, gyro dynamics, accelerometer compensation and complete three-axis control remain unvalidated.

## 5. Reproduction and evidence

Pinned `virtualagc/virtualagc` revision **f577e3fd917866c59334e6cdd32504f09df76f60**; unchanged Phase1 rope73728bytes, SHA-256 **1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e**. Phase1/3 restore instructions remain valid. New source excerpts retain exact line references; source/input/binary hashes and process versions are under Phase5. GCC warnings, stdout/stderr and exact argument arrays with exit codes are preserved; native builds and executed probes/loop processes exit0. Exit0 alone is not a readiness assertion.

From project root, with pinned source restored and **new scratch output directories**:

```sh
python3 docs/phase5-evidence/run_validation.py /tmp/apollo/va /tmp/apollo/phase5-reproduce-readiness
python3 docs/phase5-evidence/run_loop_validation.py /tmp/apollo/va /tmp/apollo/phase5-reproduce-loop
cmp /tmp/apollo/phase5-reproduce-readiness/operate.stdout /tmp/apollo/phase5-reproduce-readiness/repeat.stdout
cmp /tmp/apollo/phase5-reproduce-loop/closed.jsonl /tmp/apollo/phase5-reproduce-loop/repeat.jsonl
python3 -m unittest discover -s docs/phase5-evidence -p 'test_readiness.py' -v
```

Requires Python3, GCC/libm and Tcl8.6 (runner provisions Tcl through Nix). Retained tests inspect saved observations; compare newly reproduced logs against retained logs separately. **12 tests pass**: unchanged prior evidence, baseline failure/exact outputs, one-bit correction, original ISSUP store/DAP entry, IMU-off rejection, motion/readback, feedback-dependent commands, actuator disconnect, sensor disconnect, opposite initial response, single-axis fixture and exact replays. These tests do not claim mission or historical fidelity.

Evidence directory includes `prior_hashes.json`, `source_excerpts.txt`, address resolution, four readiness transcripts, five plant transcripts, exact commands, process exits/stdout/stderr, hashes, final harnesses, `results.json`, `tests.log`, preservation check and evidence manifest. Executable binaries remain in scratch; their hashes are retained, and reproducible corresponding-source build commands are provided. Tools/harnesses are GPL-2.0-or-later; original flight computations are unchanged.

## 6. Stop decision and smallest justified next step

The Phase4 **DAP readiness blocker is resolved for this operate-only synthetic fixture** without substantial new hardware implementation. A bounded authentic RCS/body/CDU feedback path is now demonstrated. Phase5 stops with this report and retained evidence.

**NOT RUN:**90-second cold ISS turn-on/handshake, calibrated inertial alignment/REFSMMAT validation, clean mission major-mode initialization, isolated01107 cause, general three-axis validation, WebAssembly comparison of this new coupled test, powered descent, throttle/radar coupling, frontend, multiplayer or AI crew.

Smallest technically justified follow-on, **not authorized or underway**: establish a clean revision-specific startup schedule that waits for legitimate initialization before V37, trace01107's initiating cause, and validate symmetric signed CDU queue timing before strengthening attitude-control claims. Powered descent still separately needs authenticated mission initial state, throttle/radar interfaces and validated vehicle dynamics. No historically accurate landing claim follows from this result.