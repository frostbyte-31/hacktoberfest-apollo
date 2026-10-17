# Phase 8 — P63 selection from unchanged Phase 5 startup

2026-10-17 UTC. Feasibility experiment, completed with a reproduced readiness
failure. **VERIFIED** refers to the retained source or native execution below.
**ASSUMED** describes the synthetic hardware fixture; **UNRESOLVED** identifies
an unvalidated physical behavior; **NOT RUN** means no such experiment occurred.
Addresses, channel numbers, alarm numbers and bit masks in prose are octal.
Schedules and JSON store decimal integers. In particular, MODREG integer **63**
(octal 00077) represents P63.

## Result

**VERIFIED:** authentic Luminary 099 accepts the additional normal DSKY
`V37E63E`, updates MODREG to P63, enters `P63LM`, and calls `R02BOTH`. The real
readiness check finds `REFSMFLG` clear and raises **00220**. Its success return
does not occur; the first landing setup instruction after R02 is not reached.
No powered descent has been demonstrated.

The original Phase 5 fixture is preserved literally, including its early
V37/P00 request and resulting **01520** alarm. The new alarm is retained in the
next FAILREG slot: final `[01520,00220,00000]`. This differs from a clean-start
fixture with only 00220, and is not hidden by substituting Milestone 2 startup
or clearing memory. MODREG remains P63 while `GOTOPOOH` requests a new major
mode through flashing V37; it does not prove that a descent program is running.

**VERIFIED:** the observed throttle counter update and channel014 bit4 output
come from the **engine-off/autothrottle reset during V37 program selection**,
before `P63LM`. They do not come from the guidance `THROTTLE` routine.
**UNRESOLVED:** the physical throttle/engine response, because this experiment
has no engine or throttle-to-thrust plant.

## Baseline and integrity

Repository baseline: `d8969a456cf59ae6873aea42bc2e480e84adae3a`, `main`.
Reviewed Phase 1–7 reports, Phase 5 startup/readiness probe, Phase 6 retained
source bundle, later startup validation and Phase 7/live native conventions.
The experiment depends on none of Phase 9's alignment code or outcomes.

Pinned Virtual AGC revision:
`f577e3fd917866c59334e6cdd32504f09df76f60`. Shared source preflight downloaded the
original revision archive (56,641,597 bytes), verified SHA-256
`1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267`, and assembled
unchanged Luminary 099. The assembled rope is byte-identical to the Phase 1
73,728-byte rope, SHA-256
`1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
The assembly has zero fatal errors, zero unresolved symbols and one original
possible-bank-overflow warning. `assembly-build-summary.json`, source hashes,
listing excerpts and rope opcode checks preserve the address resolution.

The Phase 8 runner verifies all 24 retained engine/model bundle input hashes,
ten relevant original source hashes and exact rope sequences before compiling.
The engine, rope and instruction semantics are unchanged. All native tests use
the pinned **ringbuffer** backend, fresh processes and CPU-call-indexed inputs.
No sockets, frontend, live adapter, vehicle controller or wall-clock pacing is
involved. The observer only reads flight memory.

`phase8-evidence/prior_hashes.json` fingerprints **3,268** previously tracked
documentation/evidence files before Phase 8 work. Its preservation check reports
zero mismatches. Earlier phase files, logs and assertions are unchanged. The
known historical missing-log errors are not repaired or relabeled as passes.

## Exact initialization and experiment

The baseline input file is byte-for-byte
`docs/phase5-evidence/operate_inputs.txt`, with a four-million CPU-call horizon:

| CPU call(s) | Original Phase 5 event |
|---|---|
| 0 | Fresh `cpu_reset`, unchanged rope; zeroed erasable; no loaded core or padload |
| 100000 | Channel031=067777: original control-mode discrete word |
| 100001 | Channel030=036377: original healthy operate-only IMU fixture |
| 426665–490664, spacing21333 | Normal DSKY `V36E` |
| 1000000–1127998, spacing21333 | Original early `V37E00E`, retained 01520 rejection |
| 1600000–1663999, spacing21333 | Original `V77E` |
| 2500000/2500001 | Original channel031=027773 and fictitious0167 yaw input20 |
| 2700000/2700001 | Original yaw-neutral and channel031=067777 |

The Phase 5 operate-only ISS initialization remains authentic, including its
software zeroing and settling delay. A separate fresh build/run of the
**unchanged Phase 5 readiness probe** produces a byte-identical copy of the
retained `phase5-evidence/runs/operate.stdout`, including ISSUP and DAP entry.
The new baseline and selected-program traces also match exactly before the
additional sequence begins.

The sole added stimuli are channel015 DSKY key packets:

| CPU call | Key | Decimal keycode |
|---:|---|---:|
| 2200000 | V | 17 |
| 2221333 | 3 | 3 |
| 2242666 | 7 | 7 |
| 2263999 | ENTER | 28 |
| 2285332 | 6 | 6 |
| 2306665 | 3 | 3 |
| 2327998 | ENTER | 28 |

Original `ringbuffer_api.c:143–147` treats channel015 as MNKEYIN and requests
interrupt5. Successful `packet_write` returns **four bytes**, not boolean1.
Every packet is accepted. The later original RHC pulse is retained to avoid
changing the Phase 5 schedule; the P63 readiness decision occurs before it.

**ASSUMED:** the Phase 5 zero-angle, stationary, operate-only IMU discretes are
an acceptable minimum instrument fixture. They do not supply a valid reference
matrix, calibrated orientation, mission state vector, lunar trajectory or fuel.
There is no vehicle integration or injected CDU/PIPA counter feedback here.
The existing RCS packets later in the trace are AGC outputs into an unconnected
plant, not spacecraft-response evidence.

## Actual execution and source explanation

Final run: `phase8-evidence/runs/attempt-03/`. A checkpoint is a snapshot before
a CPU call, not a count of distinct routine invocations. Repeated snapshots at
one PC reflect emulator instruction timing. Physical banks account for the
original superbank rule in `agc_engine.c:721–724`.

| Observation | CPU call |
|---|---:|
| `ENGINOF1`, bank36 Z3555 | 2331768 |
| `THRUST` becomes067777 | 2331816 |
| Actual channel014=070010, bit4 asserted | 2331821 |
| MODREG becomes decimal63 | 2333860 |
| `P63LM`, bank32 Z2776 | 2334707 |
| `R02BOTH`, bank04 Z3254 | 2335020 |
| Before `CCS A`, A=0 after REFSMBIT mask | 2335024 |
| Before `VARALARM`, bank04 Z3266, A=00220 | 2335034 |
| FAILREG becomes `[01520,00220,00000]` | 2335061 |
| `TC GOTOPOOH`, bank04 Z3267 | 2335070 |

`THE_LUNAR_LANDING.agc:47–53` calls R02 before setting WHICH or starting landing
initialization. `IMU_MODE_SWITCHING_ROUTINES.agc:917–935` masks FLAGWRD3 with
REFSMBIT and branches on the actual result. At entry, FLAGWRD3 is **02000**;
REFSMBIT is **10000**, so the result is zero. IMODES30 bit9 is clear, leaving
the valid-ISS/invalid-REFSMMAT alarm path: A becomes00220 and `VARALARM` executes.
The success entry `R02ZERO` at04,3270 and the caller continuation at32,3002
are both absent from the instrumented run.

`FLAGWORD_ASSIGNMENTS.agc:475–476` defines REFSMFLG as interpreter flag47,
FLAGWRD3 bit13. This is the actual missing readiness condition. The fixture's
earlier ISS/DAP enablement never established REFSMMAT validity. No memory write,
flag force, original-check bypass or Phase 9 work is used to alter the result.
`FRESH_START_AND_RESTART.agc:625–680` explains the subsequent flashing V37
major-mode request; the fixture sends no response to that request.

## Throttle signal: reset, not descent guidance

The V37 dispatch path `FRESH_START_AND_RESTART.agc:882–885` calls ENGINOF1
before dispatching the new major mode. `P40-P47.agc:466–494` clears ENGONFLG,
outputs engine-off, and explicitly **zeros autothrottle whenever the engine is
turned off**:

```text
36,3600  CS HIRTHROT    ; HIRTHROT = BIT13 = 4096
36,3601  TS THRUST     ; counter0055 receives one's-complement -4096 =067777
36,3602  CAF BIT4
36,3603  EXTEND
36,3604  WOR CHAN14
```

The read-only trace sees central accumulator **0167777** (16-bit sign extension)
before the store and THRUST **067777** (15-bit SP) afterward. The real output
at2331821 is070010: pre-existing CDU drive bits plus bit4. Source channel
descriptions identify014 bit4 as descent-engine **thrust-drive activity**.
This supplies documented hardware-reset intent, not a measured throttle or
thrust. The observer never writes this counter or signal.

The reset precedes `P63LM` by2,886 CPU calls. Neither guidance `THROTTLE`
(31,2216) nor its `DOIT` entry (31,2312) is observed. There is no engine-on
output after the new request. THRUST remains067777 at the horizon: no verified
throttle hardware model consumes it or produces thrust in this experiment.

## Reproduction, tests and evidence

Use Python3, a C compiler/libm and the unchanged pinned source tree. No Nix,
Tcl, browser or network connection is required after obtaining that tree.
From the repository root, choose a **new** scratch output directory:

```sh
python3 -B docs/phase8-evidence/run_validation.py \
  --source .build/phase89/source --output .build/phase8/reproduce-new
cmp .build/phase8/reproduce-new/p63.stdout .build/phase8/reproduce-new/repeat.stdout
cmp .build/phase8/reproduce-new/phase5-operate.stdout docs/phase5-evidence/runs/operate.stdout
python3 -B -m unittest discover -s docs/phase8-evidence -p 'test_feasibility.py' -v
```

The source URL and archive checksum are retained in `pinned-source.json`; the
runner accepts any matching restored tree, not a Phase 9 alignment artifact.
Existing scratch outputs are refused rather than overwritten. To compare fresh
results to retained logs, decompress `.stdout.gz`; gzip is only lossless storage,
not trace normalization.

**Actual results:** the final experiment built two probes and completed **four
fresh native executions**, all exit0: unchanged Phase 5 probe, new baseline,
P63 selection and P63 repeat. **15/15** execution/behavior checks pass.
The focused evidence suite ran **10 tests: 10 passed, zero failures/errors**.
Exact argv arrays, environment, actual compiler diagnostics, run stdout/stderr,
source/code/binary hashes and initial/input schedules accompany each attempt.

P63 and its fresh-process replay are byte-identical, raw SHA-256:
`93ba92511d8551c645ddd78987a1ff9b2b0b92de8cafd3cbfb8dac556975e80c`.
`retention.json` checks both raw and compressed bytes for each file. Native
binaries are omitted with hashes; unchanged corresponding engine sources are
already retained by Phase 6, and the new observer/build commands are included.
`sha256.json` fingerprints the Phase 8 package and this report (excluding itself).

**Driver mistakes, preserved separately:** attempt01's validation incorrectly
expected `packet_write==1` and its summary compared MODREG to octal63 rather
than decimal63; the raw AGC execution and replay were valid. Attempt02's
validation compared the 16-bit central accumulator directly to a 15-bit SP word.
Read-only PC attribution also initially omitted the documented superbank rule.
The final observer resolves physical banks and explicitly normalizes the store
assertion's SP15 representation. No native instruction behavior changed. Both
failed validations, exact executed code and real traces remain under `runs/`;
they are not AGC readiness failures or discarded attempts.

## Boundary and remaining blockers

**VERIFIED:** P63 selection; original invalid-REFSMMAT rejection00220; exact
baseline/replay; authentic engine-off throttle-reset output. Phase 8 completes
the feasibility experiment with a negative readiness result.

**NOT RUN:** alignment, ignition, descent guidance progression, engine response,
P64/P66, PIPA navigation, landing radar, translational flight or landing.
This run adds no multi-axis certification beyond earlier independently retained
evidence. The next legitimate experiment is to establish REFSMMAT through the
original alignment workflow and observe the next source-supported gate. A
powered-descent plant would still require validated mission initialization,
inertial navigation and engine/radar interfaces; it does not follow from this
program-selection signal.
