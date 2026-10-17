# Phase 7 — authentic multi-axis attitude validation

**Status: COMPLETE AND VERIFIED within the bounded capability C experiment.** Original Luminary 099 controls yaw and pitch separately and simultaneously through real RCS output packets, a modern rotational model and returned CDU operations. This is simulated experimental telemetry, never historical Apollo flight data. Full three-axis control, sustained attitude stability, powered descent and landing are **NOT RUN**.

| Capability | Classification | Evidence |
|---|---|---|
| A: existing one-axis feedback | VERIFIED | Unchanged Milestone 3 raw replay; compatible quaternion-model yaw |
| B: two independent axes separately | VERIFIED | Retained yaw plus new independent pitch, feedback control and replay |
| C: simultaneous two-axis feedback | VERIFIED | Concurrent authentic yaw/pitch torque and motion, all three sensor paths, disconnected control and exact replay |
| D: full three-axis control | NOT RUN | Incidental roll response does not establish independent roll control |

## Baseline, revisions and environment

The starting checkout was clean on `main`, HEAD `c10810700d875099d226384a37487376d0cf9460`, origin `git@github.com:frostbyte-31/hacktoberfest-apollo.git`. The focused [preflight](phase7-evidence/preflight/commands.json) actually ran the existing test runner, `make reproduce` and `make validate-milestone3`; all commands exited zero. Phase 6 raw traces matched retained traces exactly and the paced negative-yaw experiment reproduced. The earlier Nix obstacle has already been remedied by Milestone 1's source-locked Tcl launcher; no integrity checks were bypassed.

Virtual AGC remains pinned to `f577e3fd917866c59334e6cdd32504f09df76f60`. The unchanged 24-file Phase 6 corresponding-source archive has SHA-256 `6385d1a7abc4dec0ade1931cde2c29ac8801a56f1a0110a24265a2dde4c3a61d`; Luminary's unchanged rope is `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`. Original instructions and emulator semantics were not edited.

Execution used macOS 26.6.2 arm64, Python 3.9.6, Apple Clang 21.0.0 and Tcl 8.6.16 built from its pinned archive/options. [Environment and runtime hashes](phase7-evidence/runs/2026-10-17-verified-check/validation/environment.json) record the host toolchain; host compiler, Python and OS are recorded rather than pinned. Cross-platform binary identity is not claimed.

## Control path and source mappings

The retained Phase 5 `plant_bridge.c` captures actual native output packets. Original `P-AXIS_RCS_AUTOPILOT.agc` and `Q,R-AXES_RCS_AUTOPILOT.agc`, dispatched through `DAPIDLER_PROGRAM.agc`, generate the relevant commands. The original LM simulator decoder and `update_RCS` turn channel 005/006 latches into jet activity and model acceleration. Previously the experiment intentionally rejected other axes and integrated yaw only. The new external overlay retains decoding, thrust/fuel calculations and sensor quantization, adds rotational dynamics/orientation, then returns actual counter-operation packets through the unchanged ringbuffer engine. Subsequent original DAP execution receives those counters.

All following channel numbers/masks are octal; bit positions are one-based. [Pinned source mappings](phase7-evidence/source/mappings.json), [source excerpts and qualifications](phase7-evidence/source/README.md) and the executable source checker retain the derivation.

| Interface | Verified mapping |
|---|---|
| Channel 005 bits 1–8 | Q4U, Q4D, Q3U, Q3D, Q2U, Q2D, Q1U, Q1D |
| Channel 006 bits 1–8 | Q3A, Q4F, Q1F, Q2A, Q2L, Q3R, Q4R, Q1L |
| Original Q/R jet selections | −U `00110`, −V `00022`, +U `00204`, +V `00041`; Q response follows U−V, R follows U+V |
| Original P jet selections | −P `00252`, +P `00125` on channel 006 |
| Rate-controller inputs | Yaw fictitious channel `0167` → counter `0043`; pitch `0166` → `0042`; roll `0170` → `0044` |
| Sensor counters | `032` CDUX = outer O; `033` CDUY = inner I; `034` CDUZ = middle M |

A channel 005 selection can generate both pitch and roll torque. It cannot simply be named “the pitch channel.” Body X/P is the retained model's yaw, Y/Q its pitch, Z/R its roll. Gimbal X/Y/Z are O/I/M, not body Euler angles after compound rotation.

Original `T4GPMATRIX` specifies `OIM=XYZ`. With active right-handed body-to-stable rotation and scalar-first quaternion, the modern representation is

```
C = Ry(inner) Rz(middle) Rx(outer)
q_dot = 0.5 q ⊗ [0, omega_body]
P = O_dot + sin(M) I_dot
Q = cos(O) cos(M) I_dot + sin(O) M_dot
R = -sin(O) cos(M) I_dot + cos(O) M_dot
```

Independent matrix decomposition and the original gimbal differential agree in component tests. The external [Virtual AGC manual](https://www.ibiblio.org/apollo/assembly_language_manual.html) orders the listed gimbals differently, and a generic original IO heading calls channel 006 “ROLLJETS.” The fixture follows the pinned LM routines and explicit transformation, documenting both discrepancies. The [NASA/MIT GSOP](https://www.ibiblio.org/apollo/Documents/j2-80-MSC-69-FS-4_text.pdf), printed page 37, corroborates the jet table; its later Luminary 1B revision is supporting evidence, not authority over 099. The retained page image resolves an OCR error: channel 005 bit 5 is 2U, not 2D.

## Minimum model extension

[The physics adapter](phase7-evidence/physics/apply_physics.py) verifies original file hashes and derives an overlay without overwriting upstream files. [orientation.tcl](phase7-evidence/physics/orientation.tcl) owns three body rates and unit quaternion attitude independently of rendering. It reuses the retained jet mapping and acceleration coefficients, corrects all signed rate selectors to use magnitude, and derives O/I/M for the unchanged sensor quantizer.

**ASSUMED physical parameters:** original LM-7 defaults, 445 N per jet component and an effective one-metre torque arm. Effective principal inertias inferred from the retained acceleration coefficients are initially approximately `[20681.7113, 20381.2555, 20565.1021] kg m²`. These satisfy positive-inertia/triangle checks but are not validated Apollo 11 mass properties or reconstructed thruster geometry.

The model uses SI rotational dynamics:

```
I omega_dot + omega × (I omega) = torque
```

An implicit midpoint iteration advances angular rate with diagonal inertia fixed during each interval. The original fuel/mass calculation sets the next interval's inertia. An **ASSUMED** expelled-mass corotation flux cancels the changing-inertia term; exhaust/tank dynamics are not reconstructed. Orientation advances by the endpoint-rate quaternion exponential and normalization. This preserves the original principal-axis cadence and is first order for changing rate, not an exact general rigid-body integrator.

Torque-free component checks conserve body energy and angular-momentum magnitude near `1e-14`, while inertial momentum direction error falls from `1.66969e-4` to `8.34868e-5` relative over ten seconds when the step halves from 2 ms to 1 ms. This numerical limitation is measured and disclosed. General motion is bounded to steps ≤0.010001 s, body components ≤60°/s and middle-gimbal magnitude <80°. Solver nonconvergence, motion during zeroing, unsupported active alignment and main-engine operation are rejected. No controller or readiness check is replaced.

Translation requests from the legacy RCS combinations are recorded but the external adapter suppresses their PIPA operations. No translational state or PIPA feedback is integrated. All three rotational components and gimbals remain active, including gyroscopic coupling; nothing clamps the result to two dimensions.

## Initialization, timing and experiments

**ASSUMED initial conditions:** the retained model's identity attitude, zero body rates, ideal aligned stable platform and LM-7 mass/fuel defaults. These are synthetic fixture conditions, not an authenticated mission padload, REFSMMAT or calibrated alignment. The generated Tcl server, executed overlay, configuration hashes and raw initial-state records are retained with the final run.

The source-justified operate-only startup, V36 handling and delayed commands reuse Milestone 3. V37E00E spans calls 1,600,000–1,727,998; V77E spans 2,000,000–2,063,999. At call 2,200,000 the original software must show P00, zero FAILREG, cleared IMODES30/33 inhibition bits and set ACCSOKAY. DAPBOOLS address `0111`, ACCSOKAY mask `00004`, is resolved from original source. A flag already clear is not evidence that V77 newly changed it.

The rate-controller experiment starts at call 2,500,000. Yaw uses channel 031 decimal 12279 and one's-complement −20 (32747) on `0167`; pitch uses decimal 12286 and +20 on `0166`; combined uses decimal 12278 and both analog inputs before the same next CPU call. Neutralization is at 2,700,000/2,700,001. Counts are copied only through the original channel 013 gated read. Direction bits are documented active-low minimum-impulse signals; rate control uses analog counts/out-of-detent rather than an invented direction-bit controller.

One engine call represents exactly `12/1024000 s`. Physics boundaries are at most 853 calls (9.99609375 ms), split additionally at actual actuator changes. Host socket scheduling is absent. Independent yaw/pitch run through 4,000,000 calls (46.875 s); all combined variants were bounded before execution to 3,200,000 (37.5 s), keeping the disconnected control inside the gimbal domain.

The native observer adds read-only register, input-byte and three-FIFO inspection around the original engine. It matches real consumed packets and signed applications, including serialization of simultaneous-axis writes. Each axis allows one outstanding native request; the host applies conservative slow/fast spacing of 214/14 calls. Model interval-end, delivery, enqueue and application times are distinct. A separate native probe verifies three FIFOs and normal-packet prefixes without presenting it as spacecraft control.

Eight vehicle executions comprise the unchanged yaw baseline, quaternion-model yaw, pitch connected/disconnected/replay and combined connected/disconnected/replay. Independent pitch must succeed before combined cases run. Feedback-off cases log simulated measurements but deliver none. Actual AGC output remains free to change.

## Actual results and causal evidence

The final [native summary](phase7-evidence/runs/2026-10-17-verified-check/validation/integration/summary.json) contains actual RCS sequences, physical states, queue reconciliation, readiness samples, replay hashes and checks. [Complete raw JSONL traces](phase7-evidence/runs/2026-10-17-verified-check/validation/integration/) are losslessly compressed, with raw/compressed hashes in [retention.json](phase7-evidence/runs/2026-10-17-verified-check/retention.json). Duplicate unchanged traces reference existing preserved bytes.

| Connected case | Generated = delivered = consumed = enqueued = applied X/Y/Z | Final body yaw/pitch/roll °/s | Final native CDU counts X/Y/Z |
|---|---|---|---|
| Yaw | 1582 / 0 / 0 | −0.036645 / 0 / 0 | 31186 / 0 / 0 |
| Pitch | 0 / 1701 / 6 | −0.0000003 / −0.032862 / −0.008965 | 0 / 1697 / 32762 |
| Combined | 1264 / 1477 / 219 | −0.590839 / +1.323930 / −0.013248 | 31504 / 1477 / 32549 |

Pulse totals are not net signed angles. The combined final quaternion is `[0.982134517, -0.122676678, 0.142650281, -0.003622214]`; wrapped O/I/M are approximately `[−13.895373, +16.234115, −2.413710]°`. At call 2,510,379, authentic latches `005=00226`, `006=00252` drive simultaneous synthetic torque `[−1780,+1780,0] Nm` and actual concurrent yaw/pitch response. These torque magnitudes follow the disclosed model parameters, not historical measurements.

Disconnected pitch finishes at +11.019711°/s pitch; combined at −10.844281/+11.024825°/s yaw/pitch. Their actual CDUs stay zero. Authentic command words differ while the controller is still held, not only their timestamps. Fresh connected pitch and combined replays reproduce raw bytes exactly. Together these demonstrate that returned measurements materially affect subsequent original software.

The unchanged yaw baseline is byte-identical to Milestone 3. New-model yaw preserves exact timed RCS, actual CDU application sequence and physics boundaries. Maximum rate/angle differences are `1.75e-14°/s` and `1.42e-11°`, below the predeclared `1e-9°/s` and `1e-8°` limits; earlier assertions/references were not weakened.

At cutoff, physics and new sensor production explicitly freeze, pending requests drain through real CPU execution, then 1,000 quiet calls must leave every queue empty and counter unchanged. Combined's last Y operation applies at 3,200,034, followed by quiet completion at 3,201,034. Maximum settled quaternion-to-counter residual is 0.008654°, below one quantum (0.010986328125°). **Queue settlement is not physical equilibrium:** combined still has +1.323930°/s pitch rate at cutoff.

Maximum discrete interval-end origin-to-application latency is 925/862/868 calls for yaw/pitch/combined; delivery-to-application maximum is 220 calls. These exclude unobserved continuous threshold-crossing and real hardware delay. Body-rate magnitude remains an approximate CDU mode selector away from identity. Connected combined has seven conservative fast-mode boundary mismatches and no slow request above 4°/s actual gimbal speed. Disconnected combined generates 3,413 wrong-slow Z choices, up to 9.836114°/s, but delivers none. Hardware timing fidelity for those omitted measurements is not established.

Nonzero outputs `0174`–`0176` are retained: 51 yaw, 46 pitch, 58 combined. With actual channel 012 bit 4 clear, original `gyro_coarse_align` routes these to FDAI error needles, not spacecraft motion or platform torque. No active coarse-alignment/nonzero fine-alignment command occurs. Unsupported active alignment would stop the experiment.

## Tests and preservation

From the repository root:

```sh
make test                 # 136 prior milestone passes; historical suites reported separately
make test-phase7          # 16 physics + 23 integration tests
make reproduce            # unchanged Phase 6 reproduction
make validate-milestone2  # startup and signed FIFO diagnostics
make validate-milestone3  # paced single-axis regression
make validate-phase7      # source check, fresh physics and all native experiments
make check                # executes the full sequence above
```

`make check` actually ran on 2026-10-17, 15:27:34–15:29:41 UTC, **exit 0**. [Commands](phase7-evidence/runs/2026-10-17-verified-check/commands.json), [stdout](phase7-evidence/runs/2026-10-17-verified-check/make-check.stdout), stderr and machine-readable results preserve the real execution.

| Suite | Actual result |
|---|---|
| Milestone 1 / 2 / 3 | 55 / 47 / 34 passed; zero failures/errors |
| Phase 7 | 39 passed; zero failures/errors/skips |
| Original historical suites | 38 run: 35 passed, 3 known missing-log errors |
| Included original Phase 5 / Phase 6 | 11 passed + 1 error / 10 passed + 1 error |
| Fresh source / component validation | 22 source files checked; 13 physics checks passed |
| Fresh native integration | Three-FIFO probe and all eight vehicle cases completed |

Thus 210 tests passed and three historical tests errored across 213 test executions. The wrapper's explicit missing-log policy permits `make check` to exit zero; it does not convert those errors into passes. All 29 previously inventoried historical log gaps remain disclosed and unreconstructed.

The 39 new tests distinguish modern component dynamics from authentic execution. Integration tests rebuild a native observer, reconcile captured actual vehicle traces, and reject corrupted identities, signs, FIFO heads, counters, coordinate endpoints and provenance. Full `validate-phase7` performs the vehicle experiments afresh. Component tests alone are not the basis of the authentic-control claim.

All 1,520 prior tracked evidence/instruction/tool files match the frozen [prior inventory](phase7-evidence/prior_hashes.json) before and after. Earlier reports and reference comparisons are untouched. Failed development probes and their executed source snapshots remain under the physics/integration directories. The final [packaging inventory](phase7-evidence/runs/2026-10-17-verified-check/retention.json) records 33 identical-trace references, eight lossless trace compressions and omitted rebuildable source/binary copies with hashes. No missing execution log was recreated.

## Scope, repository state and next milestones

**VERIFIED:** bounded level C, original readiness and RCS software, reproducible single-axis regression, independent pitch, simultaneous yaw/pitch, returned measurements and causal controls. **ASSUMED:** ideal alignment, stable-frame choice, synthetic mass properties/lever arms, mass-flux approximation and bounded sensor transport policy. **NOT RUN:** independent roll/full D, arbitrary attitude or duration, sustained stability envelope, new native/WebAssembly coupled comparison and cross-platform reproduction. **BLOCKED outside this fixture:** calibrated mission initialization, active platform alignment and flight-fidelity sensor/vehicle models require further source-justified work. Descent and landing remain unproven.

Changes are confined to new `docs/phase7-evidence/`, this report, and root `Makefile`, `README.md`, `roadmap.md`. No application/frontend subsystem, Luminary source, original emulator, old model/evidence or dependency lock was replaced. Final [repository-state record](phase7-evidence/repository-state.json) and [package manifest](phase7-evidence/package-manifest.json) identify the local files. Branch remains `main`, HEAD remains `c10810700d875099d226384a37487376d0cf9460`; Phase 7 changes are uncommitted and unpushed.

The next three experiments, ranked by dependencies, are:

1. **Descent-throttle counter and pulse-contract feasibility.** Original `THROTTLE_CONTROL_ROUTINES.agc:DOIT` writes THRUST counter `055` and sets channel `014` bit 4. The pinned emulator has no automatic THRUST servicing path, so an existing automatic throttle output is not established. Verify pulse direction, rate, termination and manual limits before adding source-justified support and a disconnected engine fixture. A GUI throttle value is insufficient.
2. **PIPA specific-force delta-V feedback, then navigation consumption.** Validate counters `037/040/041` using PINC/MINC, stable/body transformations, scale, sign and timing, including original `SERVICER` read/reset into DELV/PIPTIME. A source-justified force model and synchronized translational state must precede a navigation feedback claim. Gravity is distinct from accelerometer specific force; ideal free fall produces zero ideal specific force. Mission initialization/REFSMMAT is a cross-cutting prerequisite.
3. **Radar data-provider contract, then measurement acceptance.** The pinned ringbuffer's `RequestRadarData` callback is empty even though the engine calls it before `RADARUPT`. Validate RNRAD `046`, selectors, coding/scales and data-good/status signals. An interrupt alone is not a measurement. Credible closed-loop radar experiments additionally require physical position/velocity, navigation frames and a radar scene.

These contract investigations may overlap; the ranking reflects dependencies for a later integrated descent experiment. They are recommendations, not Phase 8 work performed here.
