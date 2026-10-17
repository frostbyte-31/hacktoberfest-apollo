# Phase 2 — Powered-descent feasibility and validation

Run date: **2026-10-17 UTC**, Lovable x86_64 Linux sandbox. This phase is investigation and validation only. Phase 1 report and evidence are preserved. No application, multiplayer, AI crew, or physics engine was built.

**VERIFIED** = observed in pinned source or executed with retained evidence (these are explicitly distinguished below). **ASSUMED** = interpretation not demonstrated. **NOT RUN** = execution not attempted. Numbered source excerpts and actual search output are retained in `phase2-evidence/10_source_inspection.txt`, `11_inventory_search.txt`, and `12_descent_source.txt`. All channels, AGC addresses, and alarm numbers in prose are **octal** unless stated otherwise; JSON transcript numbers and input schedule numbers are decimal.

## Executive verdict

**An authentic initialized powered descent has not been demonstrated.** The reproducible cold-start attempt routes into P63 but fails its IMU-readiness check. No authenticated Apollo 11 pre-PDI checkpoint or complete revision-specific padload was located in the pinned repository. The existing simulator supplies useful interfaces, but the automatic descent-engine and measured landing-radar loop remains incomplete in the inspected implementations.

**There is a technically credible integration path, not yet a validated landing capability:** retain Luminary099 Rev 1, source and validate mission initialization, implement the actual throttle counter protocol and radar measurement hook, synchronize vehicle/sensor state, then verify phase transitions and closed-loop response. No such integration was implemented here.

| Question / milestone | Result | Evidence |
|---|---|---|
| Inventory starting-data candidates | VERIFIED, source inspection; no ready-to-resume Apollo 11 descent state located | `10_`, `11_`, §1 |
| P63/P64/P66 prerequisites and transitions | VERIFIED in source; flight behavior NOT RUN | `12_`, §2 |
| Cold-start P63 dispatch and R02 check | VERIFIED execution; readiness failure, not guidance success | `41_native_p63.jsonl`, `47_`, §3 |
| Authenticated P63 initialization / ignition | NOT RUN; mission data and aligned sensor state missing | §1–3 |
| P64, P66, touchdown | NOT RUN | §2–3 |
| Throttle/radar implementation audit | VERIFIED bounded source findings; complete alternative loop not located | `10_`, `11_`, §4 |
| Cycle-locked native vs Node/WebAssembly | VERIFIED: byte-identical transcripts for two new schedules | `43_`, `45_`, §5 |
| Actual Chromium execution | VERIFIED: isolated browser transcripts byte-identical to native | `44_`, `46_`, screenshots, §5 |
| Historical accuracy or hardware cycle-exactness | NOT established by build agreement | §5–6 |

## 0. Identity, dependencies, and preservation

- Virtual AGC pinned commit: `f577e3fd917866c59334e6cdd32504f09df76f60`.
- Source archive fetched in Phase 1: `https://codeload.github.com/virtualagc/virtualagc/tar.gz/f577e3fd917866c59334e6cdd32504f09df76f60`.
- Archive SHA-256: `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267`; checked again, not refetched. Full extraction into `/tmp/apollo/va` supplied files omitted from Phase 1's partial extraction. This is a tar snapshot, not a Git checkout; commit provenance is the pinned URL/archive, not `git rev-parse`.
- Reused rope: `docs/phase1-evidence/artifacts/MAIN.agc.bin`, 73,728 bytes, SHA-256 `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
- Reused WASI module, now preserved at `phase2-evidence/artifacts/yaAGC.wasm`: SHA-256 `5409ecf3000493db731b8143a78855470688f058c5cb8460dff5e848aae00759`. This is Phase 1's tested module, not a new emulator implementation.
- gcc 14.3.0, Node v22.22.0, Python 3.13.12; Chromium **141.0.7390.37** through Python Playwright. WASI SDK 24.0 built the reused module. Exact environment in `00_environment.txt`; previous WASI build commands in Phase 1 `30_wasm_build.log`.
- AGC mission sources identify public-domain status. Emulator sources are GPL-2.0-or-later as their headers specify; license and corresponding relevant source are included in `artifacts/yaAGC-corresponding-source.tar.gz`. The full pinned archive is available from the URL above. New drivers are test instrumentation, not flight logic.
- No prior binary comparisons or wall-clock socket smoke tests were repeated. The new clock run removes host-timing differences; the P63 run tests a new finding. Runs were repeated only to add source-address checkpoints/final alarm inspection. All attempts and initial failures are retained.

## 1. Authentic mission starting data

### Candidate comparison — VERIFIED source observations

| Candidate | Provenance / phase | Directly loadable? | Recommendation |
|---|---|---|---|
| `Luminary099/MAIN.agc`, rope and listing | Header: LMY99 revision 001; July 14, 1969 is the hardcopy date, **not** revision/assembly date. GUI separately identifies Rev 1, Rev 0 and hypothetical Rev 2. | Fixed-memory program only; not a spacecraft-state checkpoint. | Keep this exact revision as the baseline. |
| `scenarios/LmQuickStart.txt` | Generic LM diagnostics; includes alarm/checksum/elapsed-time operations and readiness uncertainty, not a named flight epoch. | A keystroke/uplink script, not erasable or complete core state. | Diagnostic only; its full contents contain no position/velocity, REFSMMAT, landing target or full padload. |
| `scenarios/CmQuickStart.txt` | Generic **CM** diagnostics. These are the only two entries found in `scenarios/`. | Not an LM descent state. | Exclude from LM initialization. |
| `yaDSKY2/Apollo11-landing.canned`, `Apollo11-launch.canned` | Named playback files, time/channel/value records; exact historical GET, data origin and rope revision are not established by their contents. | **Display playback**, not emulator initialization. Playback code explicitly ignores AGC commands. | Never use as evidence of guidance execution or as mission starting data. |
| `Contributed/LM_Simulator/lm_simulator*.ini` | April 18, 2007; header explicitly says **LM 7**. Four OS/DSKY variants contain stage/propellant/thrust parameters. | Tcl configuration, not AGC memory. No spacecraft vectors, epoch, landing site or alignment in these complete files. | Do not relabel LM-7 values as Apollo 11. |
| `Contributed/LM_Simulator/lm_simulator.tcl` | Initializes angles/PIPA/velocities to zero, uses LM-7 parameters and `DESCENT` stage; UI references Luminary 131/1C. | External synthetic simulator start, not authenticated pre-PDI state. | Compatibility with 099 and historical phase not verified. Luminary131 references alone do not prove incompatibility. |
| `yaDSKY2/LM*.ini`, `yaDSKY/src/LM*.ini` | Panel graphics/channel/debug-command configurations. | No mission-state data. | Not initialization candidates. |
| `yaUniverse/` ephemerides | Apollo8/Test celestial-body data and numerical integrator. Normal simulation path says “Not implemented yet.” | Celestial-body state is not an LM state vector or padload. | No Apollo 11 LM/CSM initialization found. |
| `Luminary099/ERASABLE_ASSIGNMENTS.agc`, `UPDATE_PROGRAM.agc` | Revision-specific allocations and update protocol, not populated flight data. Permanent LM/CSM vectors at assignments lines 924–947; update/REFSMMAT documentation at update lines 116–156. | Mechanism for encoding **independently sourced** values, not values themselves. | Best starting point for a later verified loader. |

**Scope of absence:** searches across all filenames, including hidden entries, located no `.core` or `.scn`; `.pad` hits belonged to other/Block-I programs. The complete two scenario files and four LM configuration files lack a mission padload. A historical Luminary099 checkpoint, complete Apollo 11 padload or synchronized peripheral checkpoint was **not located**; this does not prove none exists in historical archives or under other names elsewhere. No additional historical mission-data source was fetched in this phase.

### Loader semantics — VERIFIED in source, not tested with a mission checkpoint

`yaAGC/agc_engine_init.c:245–325` clears erasable memory, sets Z=`04000`, resets CPU state and supplies default channel 030–033 values. Cold boot is **not** mission initialization. Luminary fresh-start code explicitly anticipates a later padload.

Core restore expects **ordered octal text**, with input channels preceding eight banks of erasable words, then selected CPU bookkeeping in full-restore mode (`agc_engine_init.c:330–425,441–495`). A raw 2,048-word RAM dump cannot simply be passed as a full core. Erasable-only mode preserves bank-0 addresses below `010`; full restore reads additional state and explicitly requests DOWNRUPT. Source comments intending precise continuation are not proof of synchronized spacecraft restart: the dump does not include rope or external simulator state.

Native CLI is `yaAGC [options] rope.bin`; Phase 1 verified this form. Some GUI code passes a `--core=...` **rope selector**, while `--resume=...` selects saved emulator state; neither means a historical hardware core dump. GUI `--pads` is explicitly Block-I-only and is not a Luminary099 padload interface. Use isolated scratch directories and `--no-resume` for clean boots; yaAGC can periodically write `LM.core`, `CM.core` or `core`.

### Recommended reproducible reconstruction — NOT RUN, blocked on data

1. Obtain authenticated **Rev-1-compatible** pre-PDI data: mission phase/GET, vector epochs, coordinate frames, units/scales, LM and relevant CSM vectors, landing-site vector `RLS`, landing time `TLAND`, REFSMMAT and physical IMU alignment, mass/propellant/DAP and guidance padloads, required flags/switch states.
2. Record provenance for every value and address. Do not substitute LMY99R0, LUM99R2 or Luminary131 data based on similar symbol names.
3. Encode using the revision-specific update protocol or separately validated address-specific initialization. Read back and decode the erasables before execution. Verify frame/time consistency with sensor state.
4. Capture rope hash, initializer/core hash, load order, CPU state, and synchronized external vehicle/peripheral state. Test save/restore agreement rather than assuming it.

**No historical values were invented or loaded here.** A documented synthetic internally consistent fixture could later test software mechanics, but would require separate labeling and would not establish an Apollo 11 historical descent.

## 2. P63, P64 and P66: conditions and observables

The following are **VERIFIED source observations**, not executed flight transitions; exact excerpts in `12_descent_source.txt`.

### Entry and prerequisites

- **P63:** V37 dispatch contains MM63 → `P63LM` (`FRESH_START_AND_RESTART.agc:748–794,1057–1141`). V37 can reject IMU initialization-in-progress or `NODOFLAG` with **01520**. `P63LM` immediately calls `R02BOTH` before landing initialization (`THE_LUNAR_LANDING.agc:47–80`).
- **R02:** checks `REFSMFLG` in `FLAGWRD3` (bit 13). Without the flag, `IMODES30` bit 9 selects **00210** or **00220**, calls `VARALARM`, then `GOTOPOOH` (`IMU_MODE_SWITCHING_ROUTINES.agc:917–935`). Setting this flag manually would not establish physical alignment.
- **Important correction:** `GOTOPOOH` requests a **flashing V37 program-change display**, not an immediate proven transition to P00. Its source description and `GOPOOFIX` loop confirm this (`FRESH_START_AND_RESTART.agc:625–679`). `VARALARM` lights the program alarm but does not display the number (`ALARM_AND_ABORT.agc:221–237`).
- After R02, P63 initializes ignition/guidance flags and consumes `RLS`, `TLAND`, `REFSMMAT`, integrated state/epochs and lunar parameters to compute ignition estimates **before** the first alignment-choice prompt (`THE_LUNAR_LANDING.agc:84–207`). Cold default switches alone are inadequate.
- **P64:** automatic phase-end/guidance transition; not a standalone V37 selection in these tables. Phase-end logic advances `WCHPHASE`, clears `FLPASS0`, dispatches `STARTP64`, sets mode 64 and enables redesignation (`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:50–63,251–277,702–719`).
- **P66:** running guidance's mode monitor enters rate-of-descent mode. Return from P67/manual throttle selects P66; otherwise attitude-hold logic also tests nonzero `RODCOUNT`. Attitude hold **alone** is not sufficient to infer P66. Entry captures current altitude rate into `VDGVERT` (`…GUIDANCE_EQUATIONS.agc:140–225`). P65 is another automatic vertical-phase destination; P66 is not inevitable after P64.

Required external conditions include valid IMU orientation/CDU and PIPA feedback, appropriate PGNCS/G+N AUTO and automatic-throttle conditions, landing-radar antenna/status and real measurement inputs, and consistent spacecraft state/target/mass data. Active-low channel bits must be interpreted through executable source, not switch names.

### Displays, crew actions and alarms

| Observation | Interpretation / action | Source |
|---|---|---|
| V50N25, `00014` | R51 alignment choice. PRO enters fine alignment; ENTER returns toward burn-attitude preparation. Not engine enable. | `THE_LUNAR_LANDING:218–240`, `P51-P53:724–731` |
| V50N18 | R60 attitude-maneuver request; not proof of actual attitude control. | `R60,R62:49–69,113–150` |
| V50N25, `00500` | LR antenna position-1 request. PRO rechecks; ENTER takes initialization path. Acknowledgment is not valid range/velocity. | `THE_LUNAR_LANDING:245–271` |
| V50N25, `00203` | PGNCS/AUTO/automatic-throttle checklist; PRO repeats switch check. | `BURN,…MASTER_IGNITION_ROUTINE:911–934` |
| V99N62 | Engine-enable request scheduled at TIG−5. PRO sets `ASTNFLAG`; ignition logic also checks TIG. **Do not PRO in the minimal test.** | `BURN,…:136–149,363–431,778–788,823–828` |
| V06N63 | Braking: velocity magnitude, altitude rate, computed altitude. | `…GUIDANCE_EQUATIONS:860–864`, noun table 319–321 |
| Flashing V06N64 | Approach/redesignation permission request. PRO sets `REDFLAG`; it does not start P64. | `…GUIDANCE_EQUATIONS:866–896` |
| V06N60 | Vertical display shared by P65/P66/P67: horizontal velocity, altitude rate, computed altitude. Read `MODREG` to distinguish programs. | `…GUIDANCE_EQUATIONS:899–909`, noun table 310–312 |

Alarm criteria: **01520** selection blocked; **00210** IMU not operating / **00220** no valid REFSMMAT; **01412** ignition-iteration exhaustion; **01406** time-to-go failure (abortive during ignition algorithm, different handling during flight); **01410** non-abortive guidance overflow, skipping normal steering/throttle path. Absence of alarms is not proof of guidance correctness.

Useful listing addresses: `P63LM=32,2776`, `R02BOTH=04,3254`, `R02ZERO=04,3270`, `R51P63=14,3135`; `MODREG=1011`, `IMODES30=1302`, `FLAGWRD3=0077`, `WCHPHASE=1351`; banked `TLAND=E5,1400`, `RLS=E4,1422`, `RODCOUNT=E7,1746`. Flag identifiers themselves are not addresses. Bank translation and full mission loading remain separate validation tasks.

## 3. Smallest reproducible descent-entry test — executed

### Inputs and stopping scope

Fresh, zero-initialized process; unmodified upstream `cpu_reset`, exact Phase 1 rope; no core, state-vector or alignment writes. `p63_inputs.txt` begins with **2,600,000 total cpu_step calls**, followed by decimal `cycle channel value` rows:

```text
426665 13 17
460798 13 3
494931 13 7
529064 13 28
563197 13 6
597330 13 3
631463 13 28
```

These encode `V37E63E` on octal channel 015. Timing is a deterministic test schedule, **not historical mission timing**. After the last ENTR no further crew inputs are given. The 2.6M-cycle horizon is a bounded observation, not a source-justified descent completion deadline. No PRO, engine-enable grant, sensor simulation or invented mission data is supplied.

### Actual result — VERIFIED

- Cycle **635782** reaches fixed-bank `32`, Z=`2776` (`P63LM`), with `MODREG=63` decimal.
- Cycle **635950** reaches `04,3254` (`R02BOTH`). `FLAGWRD3=02000`, `IMODES30=0`; REFSMMAT-valid bit 13 is absent.
- Cycle **635958** reaches `04,3261` (IMU-status mask); cycle **636002** reaches `04,3267` (`TC GOTOPOOH`). No observed `R02ZERO` or `R51P63` checkpoint.
- End memory: `MODREG=077` octal (=63 decimal), `FLAGWRD3=02000`, `IMODES30=0`, **`FAILREG=01107,00210,00000`**. Alarm **01107** is also present (listing describes phase-table failure); its exact cause/timing was **not isolated**, so this is **not** an alarm-free or clean single-alarm run.
- Last decoded channel-010 frame: PROG `63`, VERB `37`, blank NOUN/registers. A PROG 63 display alone would therefore be a misleading success criterion. The decoder does not reproduce sign/flash state; the V37 flashing request is supported by the executed source path, not a visual DSKY assertion.
- `VARALARM` does not display its number; 00210 is established by final erasable inspection, not by inventing a displayed alarm.

**Pass/fail disposition:** keyboard/P63 routing **PASS**; expected R02 no-IMU/readiness branch **PASS**; full P63 initialization **NOT ACHIEVED**; ignition, P64/P66 and powered descent **NOT RUN**. The additional 01107 remains a validation limitation requiring isolation before a stronger initialization claim. No conclusion of emulator defect follows from this uninitialized run.

### Criteria for a later initialized test — NOT RUN

1. Read back validated phase data, alignment, switches and sensor state; fail if values/frame/epoch/revision differ from the authenticated initializer.
2. Route to `P63LM`, pass R02 without falsifying flags, converge ignition estimates, reach `R51P63`/checklist 00014. Fail on inconsistent branch inputs, nonconvergence or unexplained alarms.
3. Stop at the prompt for the initialization-only milestone; do not blanket-PRO. A later ignition test must explicitly grant V99 and verify engine-on/throttle response.
4. For descent, correlate changing vehicle state, actuator commands and CDU/PIPA/radar measurements; verify automatic phase-end → mode 64 and appropriate vertical-phase/crew P66 selection using `MODREG` and `WCHPHASE`, not display labels alone.
5. Demonstrate measurable commanded thrust/attitude response and feedback read by AGC. Touchdown needs its own physical/contact criteria. None of these flight criteria were exercised here.

## 4. Missing hardware interfaces

### Existing exchange — VERIFIED source inspection, not executed coupling

- `SocketAPI.c:100–145,210–269` broadcasts 4-byte channel words, accepts masked writes and unprogrammed counter operations, sets keyboard interrupt 5 for channel 015 and uplink interrupt 7 for fictitious 0173. RHC 0166/0167/0170 transfers to counters 042–044 when channel 013 bits 8/9 request it.
- `LM_Simulator/lm_simulator.tcl:777–912` decodes RCS channels **005/006**, fine/coarse gyro alignment **0177/0174–0176**, and sends masked/counter packets.
- `modules/AGC_IMU.tcl:500–652` generates CDU counter operations **032–034**, PIPA PINC/MINC **037/040/041**. These are counter addresses carried in the counter-operation packet form, not ordinary sensor channel writes.
- `yaACA` supplies hand-controller packets/discretes, not vehicle dynamics. No-DSKY configs retain IMU/attitude/system windows at localhost port 19801.
- Generic `UnprogrammedIncrement` handles counter operations; its overflow-interrupt block is empty (`agc_engine.c:1565–1622`). Arbitrary injected overflow should not be assumed to produce appropriate device interrupts.

### Throttle — confirmed local gap

**THRUST=`055` is an erasable hardware counter, not an output channel.** Luminary assigns it next to `RNRAD=046` (`ERASABLE_ASSIGNMENTS:141–149`). `THROTTLE_CONTROL_ROUTINES:120–138` computes a command, writes `PSEUDO55` and `THRUST`, then sets **channel 014 bit 4**. Treating “channel 055” as a throttle output would be wrong.

No dedicated implementation of that THRUST-counter pulse/output sequence was located in the inspected engine/API. Its neighboring counter definitions label 055/056 as spares. This is **not located**, rather than proof of absence from every repository integration.

**Confirmed in the inspected Tcl engine routine:** descent thrust comes from a GUI slider, consumes propellant and supplies PIPA velocity changes; ascent uses configured fixed thrust (`AGC_Simulation_Monitor_Control.tcl:151–205`). It does not derive thrust from Luminary's THRUST/channel-014-bit-4 protocol. Existing RCS dynamics and inertial feedback do not close this gap.

### Landing radar — timing exists, measurements do not in these hooks

Luminary `P20-P25.agc:2733–2888` selects measurements using **values on channel 013**: RR range `011`, RR range-rate `012`, LR X/Y/Z velocity `014/015/016`, LR altitude `017`. These are request words, not six channels. It reads measurement counter **RNRAD=046**, status on **033**, and commands positioning on **012** (`…:3083–3127`).

`agc_engine.c:2168–2179,2220–2235` implements radar timing: channel 013 bit 4 enables activity; gate counter advances with TIME5; at the completion phase the engine clears activity, calls `RequestRadarData` and requests **interrupt 9/RADARUPT**.

**Confirmed absence inside the inspected functions:** `SocketAPI.c:508–516`, `ringbuffer_api.c:193–196` and `NullAPI.c` provide empty radar-data hooks. A completion interrupt therefore does **not** prove a fresh measurement was supplied.

Tcl system controls supply manual RR/LR status/data-good/scale/position discretes on **030/033** (`AGC_System_Inputs.tcl:88–113`); the inspected dispatcher has no radar-request-to-measurement generator. Their labels are not evidence of actual altitude/velocity production.

`yaUniverse` contains an integrator accepting thrust/mass-rate inputs, but its normal simulation path is unimplemented and no AGC socket bridge was located. `yaLEMAP` is an AGS assembler, not an environment simulator. Repository-wide discovery searches did not locate a complete alternative descent loop; this was not an exhaustive behavior audit of every unrelated simulator.

### Necessary later implementation — NOT RUN / not implemented

Expose/consume the actual throttle counter/enable protocol; decode radar selection/positioning and supply scaled measurements/status at the existing completion hook **before RADARUPT**; connect commands to an authoritative vehicle model and synchronized IMU/CDU/PIPA feedback. Validate sign, scaling, pulse semantics, update timing and active-low discretes independently. This phase implemented none of that glue or physics.

## 5. Deterministic native / WebAssembly / real-browser comparison

### Method — VERIFIED execution

The native driver compiles the **same unmodified upstream `wasm.c`, `agc_engine.c`, reset/load routines and ringbuffer API** used by the WASI module. This deliberately removes native socket host scheduling. It is **not** a new exact comparison of the socket executable versus WASM; Phase 1 established socket behavior separately.

Both start a fresh process/module, reset, load the identical rope, then receive the identical decimal input schedule at exact `cpu_step` indices. One `cpu_step(1)` per call; drain outputs every cycle, avoiding bulk-step ringbuffer loss. Source `wasm.c` specifies 11.72 μs per step; no wall-clock sleeps enter these tests. Default reset channel words are identical. Fresh instances avoid stale static ringbuffer/mask state.

Each transcript contains every input acceptance and emitted channel/value, source-address checkpoints, and every 10,000 cycles:

- cumulative FNV-1a digest of A/L/Q/EB/FB/Z/BB/ZERO registers after **every cycle**;
- digest of all 2,048 erasable words at the checkpoint;
- actual Z/FB/EB values.

This is a **cycle-indexed register/RAM trace digest**, not a full retained disassembly or all internal CPU bits. Hash collisions and unobserved internal differences are theoretical limitations. Outputs and sampled explicit addresses are compared directly. The native final-memory stderr inspection adds alarms but is not included in byte comparison.

| New schedule | Cycles | Trace checkpoints | Output packets | Native/Node/browser result |
|---|---:|---:|---:|---|
| V35 lamp-test then RSET/V16N36 clock | 2,300,000 | 230 | 3,902 | All complete transcripts byte-identical |
| Uninitialized V37E63E | 2,600,000 | 260 | 4,337 | All complete transcripts byte-identical |

Both native/Node runs exit 0; `cmp` exits 0 (`43_`). Isolated browser comparisons exit 0 (`46_`). Channel-010 decoding, including the clock, agrees exactly (`45_`). Clock final R3=`02643` is an observed AGC display, not a historical mission time. Unlike Phase 1, there is no clock offset because the stimuli and cycle counts are identical.

**Meaning:** strong evidence of agreement for these two initializations/sequences. It is not independent historical validation, proof of physical hardware timing, full ISA coverage, or descent guidance correctness. The two builds share the engine and can share its defects.

### Actual browser result and limitations

Python `browser_validate.py` temporarily served only a diagnostic page at localhost; no application was scaffolded. Playwright Chromium **141.0.7390.37** executed both full schedules; output read back through page JavaScript and matched native. Isolated page had `crossOriginIsolated=true`, SharedArrayBuffer constructor available, no page errors. `clock.png` and `p63.png` show completed test metadata, not a fabricated DSKY interface.

**Unexpected but VERIFIED:** on the same Chromium, without COOP/COEP, `crossOriginIsolated=false` and global `SharedArrayBuffer` was undefined, yet `WebAssembly.Memory({shared:true})` returned a SharedArrayBuffer-backed buffer and the synchronous single-page test ran. Initial script incorrectly assumed this must fail; the assertion failure is retained in `44_browser_initial_assertion_failure.log`, then replaced with observation rather than the assumption. It does **not** prove non-isolated worker transfer, SharedArrayBuffer APIs, other browser engines or production deployment will work.

Use COOP `same-origin` / COEP `require-corp` as the conservative path for later worker/shared-memory integration, subject to deployment verification; do not state that this specific non-isolated Chromium run failed. Safari, Firefox, workers, cross-origin media constraints, actual hosted headers and sustained real-time browser performance are **NOT RUN**.

Module imports include shared memory and seven WASI functions; proxies counted calls and **none were invoked in these tests**. No-op WASI stubs are adequate only for the observed path; filesystem/stdio/error paths require proper implementations. Exported ringbuffer I/O works in browser and Node. `packet_read` code packs channel in bits starting at **16**, despite a misleading bit-15 comment in `wasm.c`; this harness follows executable code. `get_erasable_ptr` is documented for inspection, not endorsed mutation. Current exports do not provide a complete peripheral/state-checkpoint API.

Synchronous millions-of-cycles loops validate correctness, not interactive usability: they block the browser main thread. Worker scheduling, pacing to real time, frame stalls, reset reuse and long-run drift remain untested.

## 6. Reproduction and evidence index

From project root, with the pinned source at `/tmp/apollo/va`:

```sh
mkdir -p /tmp/apollo/p2build
gcc -O2 -I/tmp/apollo/va/yaAGC docs/phase2-evidence/cycle_native.c \
  /tmp/apollo/va/yaAGC/{wasm.c,agc_engine.c,agc_engine_init.c,agc_utilities.c,ringbuffer_api.c,ringbuffer.c,rfopen.c} \
  -lm -o /tmp/apollo/p2build/cycle_native

for t in clock p63; do
  /tmp/apollo/p2build/cycle_native docs/phase1-evidence/artifacts/MAIN.agc.bin \
    docs/phase2-evidence/${t}_inputs.txt > /tmp/native_${t}.jsonl
  node docs/phase2-evidence/cycle_wasm.mjs docs/phase2-evidence/artifacts/yaAGC.wasm \
    docs/phase1-evidence/artifacts/MAIN.agc.bin docs/phase2-evidence/${t}_inputs.txt /tmp/wasm_${t}.jsonl
  python3 docs/phase2-evidence/analyze_cycles.py /tmp/native_${t}.jsonl /tmp/wasm_${t}.jsonl
done
mkdir -p /tmp/browser/phase2
python3 docs/phase2-evidence/browser_validate.py \
  docs/phase2-evidence/artifacts/yaAGC.wasm docs/phase2-evidence \
  docs/phase1-evidence/artifacts/MAIN.agc.bin
python3 -m unittest discover -s docs/phase2-evidence -p 'test_validation.py' -v
```

Browser script writes new browser transcripts in the supplied evidence directory; copy that directory to scratch first if preserving this exact run. It starts/stops its own temporary server and browser; no running application server is required.

To rebuild WASM without overwriting native objects, use a **separate source copy** and WASI SDK 24.0:

```sh
mkdir -p /tmp/apollo/wasi-rebuild
cp -a /tmp/apollo/va/yaAGC/. /tmp/apollo/wasi-rebuild/
# In /tmp/apollo/wasi-rebuild:
make clean
make WASI=yes WASI_SDK_PATH=/tmp/wasi-sdk-24.0-x86_64-linux yaAGC.wasm
```

Phase 1 retains the actual successful WASI build log; Phase 2 did not rebuild it. Reproduction can also extract the full pinned archive into a fresh scratch tree. GNU make and official SDK are required. Browser reproduction needs Python Playwright and Chromium; those were preinstalled here.

Evidence:

- `00_`: date/toolchain/archive identity.
- `10_`, `11_`, `12_`: numbered source excerpts, discovery commands/output/exit codes.
- `40_`: native compile attempts. First failed link omitted `rfopen.c`; corrected build succeeds. Failure is not hidden.
- `clock_inputs.txt`, `p63_inputs.txt`: exact deterministic stimulus schedules.
- `41_`, `42_`, `44_*.jsonl`: full native, Node and browser transcripts.
- `43_`, `44_browser_run.log`, `46_`: commands, execution/import results and comparisons.
- `45_`: complete decoded display evolution, lamp-channel records, hashes and counts.
- `47_`: final P63 memory/alarm observation and unchanged transcript comparison.
- `test_validation.py`, `48_tests.log`: concrete regression checks/results.
- `49_sha256.txt`: complete Phase 2 evidence hashes; `50_source_hashes.txt`: cited source hashes; `51_phase1_hashes.txt`: preserved Phase 1 files.
- `artifacts/`: tested WASM and GPL corresponding source; test drivers and browser procedure are alongside logs.

## 7. Stop decision

Phase 2 investigation/validation is delivered. **No full powered descent is claimed.** The next descent validation is blocked on authenticated revision-specific mission initialization plus the missing synchronized propulsion/radar interfaces; the observed 01107 also needs isolation. These are precisely identified prerequisites, not permission to fabricate a successful scenario. No application development begins after this report.