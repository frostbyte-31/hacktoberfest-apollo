# Phase 4 — AGC-to-spacecraft control-path validation

2026-10-17 UTC. Bounded source audit, native readiness probe, and isolated existing-model checks only. **VERIFIED** means retained execution or source inspection, distinguished explicitly; **ASSUMED** means not demonstrated; **NOT RUN** means no execution. Channels, addresses and alarm numbers in prose are octal; schedules/JSON are decimal. No prior reports or evidence were changed.

## Verdict and acceptance disposition

**VERIFIED:** Phase 3 was IMU instrument alignment, not spacecraft propulsion. A separate RCS vehicle-response interface **does exist** in the pinned simulator. Its active yaw model and body-to-CDU transformation execute with opposite signs for opposite synthetic jet patterns.

**VERIFIED:** a new four-million-cycle Luminary099 probe accepted attitude-hold/PGNCS ownership, V36 reset, P00 selection, V77 and a yaw-controller deflection, but never reached `STARTDAP`. It emitted 942 RCS packets, all zero. The original software repeatedly took its IMU-unusable shutdown path. Identical fresh replay is byte-identical.

**NOT RUN:** an AGC-driven spacecraft feedback loop. The component check's jet flags were explicitly injected test inputs, **not AGC outputs**; it cannot satisfy the closed-loop acceptance alternative. Acceptance uses the **precise-blocker alternative**: the interface is present, but a usable, synchronized IMU startup fixture for this rope has not been established. No gimbal-to-thrust reinterpretation, readiness-flag write, invented guidance, or fabricated successful vehicle response was used.

## 1. Prior evidence reviewed and preserved — VERIFIED

Reviewed all three reports, Phase 3 harness, runner, seven-test definitions, retained results and five run transcripts; Phase 2 cycle-driver/interface findings provided the baseline. `prior_hashes.json` fingerprints **78** prior documentation/evidence files, including the three reports. `review.json` records inventories and verifies the Phase 3 preservation baseline has zero mismatches. Tests verify every prior file again.

`phase3_actuator_audit.json` is a new analysis of existing traces, not a repeated execution. All five Phase 3 runs have **zero nonzero channel005/006 packets**. Positive alignment still has the documented ten coarse-drive packets, 228 pulses, returned CDU=912, and IMUGOOD; disconnected runs retain 00211. These remain evidence of an instrument loop only.

## 2. Trace Phase 3's output — VERIFIED source and retained execution

`Luminary099/EXTENDED_VERBS.agc:235–317` routes V41N20 through desired-angle input to IMUCOARS/IMUSTALL. `IMU_MODE_SWITCHING_ROUTINES.agc:155–264` computes desired-minus-measured gimbal motion and checks the result. Phase 3's preserved report/excerpts establish the completion/error addresses and executed branches.

The emulator's CDU drive service emits convenience packets **0174/0175/0176** (`yaAGC/agc_engine.c:1630–1685,2412–2423`). The simulator dispatches them to `gyro_coarse_align` (`lm_simulator.tcl:795–800`). With channel012 bit4 enabled, they move **IMU X/Y/Z gimbals**; without that enable they change **error-needle accumulators** (`AGC_IMU.tcl:463–493`). `modify_gimbal_angle` can inhibit movement for zeroing/gimbal lock and returns CDU count operations (`:500–533`). Neither branch selects RCS jets or descent thrust.

**VERIFIED conclusion:** these drive pulses must not be applied as spacecraft torque, engine throttle, or thrust. An internal platform angle and a vehicle body rotation can both alter CDU readings through different mechanisms; sharing a sensor does not make the actuators interchangeable.

## 3. The actual active spacecraft path — VERIFIED source inspection

The main simulator selects **AGC_Simulation_Monitor_Control.tcl**, not the older **AGC_Attitude.tcl** (`lm_simulator.tcl:103–114,946–966`). This matters: a preliminary inspection found undefined `Transform_NB_SM`/`Moment_of_Inertia_Factor` in the older file. That is **not a blocker in the selected implementation**. `missing_dependency_search.txt` retains this rejected lead. Preliminary interpreter discovery found no system Tcl; `nix run nixpkgs#tcl` failed because its default executable name was wrong; the actual tests use `nix shell nixpkgs#tcl -c tclsh`, Tcl 8.6.16. No upstream files were patched.

| Interface | VERIFIED meaning / source |
|---|---|
| Channel005 bits1–8 | Q4U/Q4D/Q3U/Q3D/Q2U/Q2D/Q1U/Q1D (`lm_simulator.tcl:812–818`) |
| Channel006 bits1–8 | Q3A/Q4F/Q1F/Q2A/Q2L/Q3R/Q4R/Q1L (same) |
| Positive/negative yaw | Active model sums Q1F+Q2L+Q3A+Q4R minus Q1L+Q2A+Q3R+Q4F (`AGC_Simulation_Monitor_Control.tcl:237–242`) |
| Body angular-rate response | Yaw increment = Alpha_Yaw × interval × signed jet sum; pitch uses U−V, roll U+V (`:291–303`) |
| Model acceleration convention | Config/mass-dependent coefficient formula, with constants from main initialization (`:207–211`; `lm_simulator.tcl:164–240`) |
| Vehicle rotation → CDU | Body yaw/pitch/roll increments enter `Transform_BodyAxes_StableMember` (`:213–214`; `AGC_IMU.tcl:660–692`), then gimbal quantization/counter packets |
| Controller input | Fictitious0167 holds yaw input until the AGC requests channel013 bits8/9; then counter043 receives it (`ringbuffer_api.c:88–94,158–176`) |
| Crew discretes | Attitude-hold clears channel031 bit13, retains bit14; PGNCS ownership clears channel030 bit10 (`AGC_Crew_Inputs.tcl:115–124`) |

**VERIFIED bounded geometric interpretation:** with zero gimbals, pure body yaw reduces to an X-gimbal delta of the same sign in this implementation. General roll/pitch/yaw-to-CDU behavior couples axes; do not extend the zero-angle single-axis simplification to arbitrary attitude.

**VERIFIED limitation in dispatcher ordering:** jet variables are copied from `bo` before `bo` is updated from the newly received channel word (`lm_simulator.tcl:812–847`). A direct decoder would not automatically reproduce this stale-latch behavior. The component test bypasses socket decoding by setting documented jet flags; it does not validate dispatcher timing. The socket model also uses host elapsed time (`:716–733`), unlike the cycle-locked probe.

**ASSUMED:** the active coefficients are suitable synthetic vehicle-model conventions. Their presence/execution does not independently establish actual Apollo 11 inertia, jet calibration, or flight dynamics. The main defaults explicitly identify **LM-7**, not Apollo 11 (`:171–184`).

## 4. Smallest selected experiment and observed blocker

### Intended smallest loop — NOT RUN

A short yaw-controller deflection, followed by neutral, in a stationary synthetic vehicle with zero initial gimbals: original Luminary DAP selects RCS → actual005/006 packets change body angular rate → body-to-gimbal transform produces CDU counter operations → original DAP consumes the changed angles/rates and alters jet behavior. Keep plant outside the emulator, reject cross-axis commands, and compare normal, actuator-blocked and feedback-disconnected runs. This is attitude control, not landing guidance. A V49 maneuver is a larger alternative; its original entry is R62FLASH/N22/proceed/R60LEM (`R60,R62.agc:567–592`).

### Gate probe — VERIFIED new native execution

`control_probe.c` links unchanged upstream engine/reset/utilities/ringbuffer/wasm wrapper. It **only inspects erasable memory**, never writes readiness or flight state. Fresh process; same Phase 1 rope; cpu_reset defaults; no saved core, padload or initialized peripheral model. No plant is attached because the readiness probe never produces a nonzero spacecraft actuator word.

Exact schedule: `probe_inputs.txt`, **4,000,000 cpu_step(1) calls**, zero-based input indices, outputs drained after every cycle. Approximate duration **46.88 s** by upstream's 11.72 μs cycle convention, not hardware-time validation.

| Cycle(s), decimal | Input / synthetic meaning |
|---|---|
| 100000 | Channel031=28671: attitude hold, other reset bits retained |
| 100001 | Channel030=15871: PGNCS ownership, other reset bits retained |
| 426665 + j×21333 | V36E through015 |
| 1000000 + j×21333 | V37E00E through015 |
| 1600000 + j×21333 | V77E through015 |
| 2500000 | Channel031=12283: yaw-positive direction bit3 cleared, out-of-detent bit15 cleared, hold retained |
| 2500001 | Fictitious0167=20, synthetic positive controller command |
| 2700000 | Fictitious0167=0 |
| 2700001 | Channel031=28671: neutral/detent restored |

All **21** input packets accepted. These are reproducible diagnostic choices, **not a proven complete 099 startup procedure**. The IMU-operate/cage/turn-on/healthy peripheral sequence was not supplied or bypassed. Whole channel words retain unspecified reset bits; their appropriateness for a realistic startup is not established.

### Actual results and branch proof — VERIFIED

- 942 channel005/006 packets, **all zero**; `STARTDAP=16,2046` visits **0**; `SHUTDOWN=16,2163` visits **469**. Source-address resolution is retained from the existing assembly listing in `address_resolution.txt`, not inferred from display text.
- At cycle **2704239**, `CHEKBITS=16,2000` sees channel031=28671 (**067777**), channel030=15871 (**036777**), IMODES33=15392 (**036040**), DAPBOOLS=8910 (**021316**).
- The mode-off condition is false: channel031 bits13/14 are not both one. PGNCS ownership is selected. **ACCSOKAY bit3 is already set** (`FLAGWORD_ASSIGNMENTS.agc:1246`); this probe is not blocked simply by an absent acceleration-ready bit.
- **IMODES33 bit6 is set.** Original `CHEKBITS` complements IMODES33, masks bit6, and the zero path marks the IMU unusable and calls SHUTDOWN (`DAPIDLER_PROGRAM.agc:46–60`). SHUTDOWN explicitly writes zero to005/006 (`:182–194`). Repeated checkpoint visits and all-zero jet words match that path. No counter043 sampling of the nonzero yaw input is observed; packet acceptance/echo alone is not controller consumption.
- Final P00, CDU=[0,0,0], FAILREG=[0,0,0]. Early cycle10000 sample contains **01107**, but V36 later clears it. A clear final FAILREG does **not** establish correct startup or isolate the cold-start phase-table disagreement. The alarm's origin is source-identified (`FRESH_START_AND_RESTART.agc:299–311,350–360`); its exact initiating cause remains unresolved.
- Fresh replay transcript is **byte-identical**. Commands, stderr, input/source hashes and output are retained under `runs/`; build and both probe processes exit0. Exit0 means the harness completed, not that the spacecraft loop succeeded.

### Precise minimum prerequisite — NOT RUN

Establish a **Luminary099-compatible, repeatable IMU startup/peripheral fixture** that makes the software itself clear its unusable status and enter STARTDAP: model the actual external channel030 turn-on/operate/cage/failure signals and channel012 zeroing/enable handshake; return synchronized CDU counts; record the time-ordered switches, original initialization branches, and final usable state. `T4RUPT_PROGRAM.agc:250–290,340–445` contains the monitor/turn-on processing. Verify consistent revision-specific R03 mass/stage/DAP settings, rather than writing flags or importing tutorial defaults. Original R03 uses bit-masked **V01N46** (`EXTENDED_VERBS.agc:1310–1330`), unlike the older tutorial's decimal configuration description.

This is missing initialization, **not confirmed absence of an RCS actuator interface** and not proof the emulator cannot run attitude control. V41 coarse-alignment success does not alone meet the DAP usability gate. Scope stops here rather than improvising a readiness bypass or an extensive new initialization campaign.

## 5. Active-model component check — VERIFIED, not an AGC loop

`simulator_component.tcl` executes literal main-file constants/initial state, sources the two **active unmodified modules**, disables GUI/socket startup, and captures `write_socket` requests as evidence. Engine flags remain off. It initializes coefficient calculation with a synthetic26 ms update, then applies a100 ms jet interval and100 ms rotation update. Zero gimbals, unlocked, zeroing not asserted. No flight software runs in this component check.

| Injected component input | Body yaw rate (degrees/s) | X gimbal result | Counter requests |
|---|---:|---:|---|
| Q3A/Q1F/Q2L/Q4R on | +0.49312402726613486 | 0.04931240272661349° | 4 PCDU to032 |
| Q4F/Q2A/Q3R/Q1L on | −0.49312402726613486 | 359.9506875972734° (wrapped) | 4 MCDU to032 |
| All jet flags zero | 0 | 0 | 0 |

Y/Z remain zero. This verifies **existing-model sign, motion, wrap and sensor-request generation in these component conditions**. It does not verify historical calibration, AGC packet production/consumption, stable rate capture, braking, or feedback-dependent AGC response. The zero-jet case is a component control, not an end-to-end actuator-disconnect run. Slow CDU operations produced here were not delivered to the emulator; their queue/timing agreement is NOT RUN.

## 6. Reproduction, evidence and pass/fail criteria

Pinned source: `virtualagc/virtualagc` **f577e3fd917866c59334e6cdd32504f09df76f60**, reused `/tmp/apollo/va`. Archive SHA-256 **1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267**. Rope **73728 bytes**, SHA-256 **1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e**. Versions/date and actual hash commands: `00_environment.txt`. Full source restore commands remain in Phase 1/3 evidence; no refetch or binary comparison repeated.

From project root, use a **new** scratch directory:

```sh
python3 docs/phase4-evidence/run_validation.py /tmp/apollo/va /tmp/apollo/phase4-reproduction
cmp /tmp/apollo/phase4-reproduction/probe.stdout /tmp/apollo/phase4-reproduction/repeat.stdout
python3 -m unittest discover -s docs/phase4-evidence -p 'test_control_path.py' -v
```

Runner records exact argument arrays, working directory, exits/stdout/stderr. Native compile uses gcc-O2 and the seven same upstream files as Phase 2/3; see `runs/commands.json`. Tcl dependency is provided through Nix; on another environment Tcl8.6 may run the component script directly. The retained tests check the captured runs, not newly reproduced output; compare fresh logs and input/source identity explicitly. Six concrete tests cover preservation, Phase 3 non-RCS output, accepted probe inputs, readiness/shutdown evidence, replay, and component sign/sensor controls.

**VERIFIED acceptance checks:** source actuator meaning established; active implementation selected; gate failure reproducible; no fabricated actuator; prior evidence unchanged. **NOT RUN loop checks:** actual nonzero AGC jet → nonzero vehicle response → new CDU readback → changed original AGC output; disconnected-loop controls; sign reversal under original DAP; stable braking/hold. A future run must pass all these with no unexplained control-interval restarts and coherent initialization. Unit tests passing this report's negative findings does not turn those future checks into passes.

Evidence: `review.json`, `prior_hashes.json`, `phase3_actuator_audit.json`, `source_excerpts.txt`, `address_resolution.txt`, `probe_inputs.txt`, read-only native probe, active-model Tcl check, reproducible runner, `runs/`, `results.json`, `test_control_path.py`, `tests.log`, `sha256.json`, `preservation_check.json`. Emulator/tools are GPL-2.0-or-later; new instrumentation uses that license. Corresponding emulator source remains preserved in Phase 2. No product binary is delivered.

## 7. Stop decision

**VERIFIED:** the next connection is an RCS body-attitude/CDU path, not Phase 3 coarse gimbal drive. **NOT RUN:** a closed spacecraft loop, full powered descent, historical landing, frontend, multiplayer, AI crew, complete physics engine, browser/WASM extension of this experiment. The smallest prerequisite is usable/synchronized IMU startup under the original software, then a cycle-locked yaw-rate test using actual005/006 outputs and explicit disconnect controls. Historical descent additionally retains Phase 2's mission-data, throttle, radar and dynamics blockers. Phase 4 stops with the bounded evidence and this precise blocker; no additional development is authorized or underway.