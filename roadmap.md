# Roadmap

## Phase 1 (done — see docs/PHASE1_PROOF_PLAN.md)
- [x] Pinned source, versions, licenses
- [x] Provenance + formats of both binsource files
- [x] Build yaYUL/oct2bin/yaAGC; assemble Luminary099; hashes
- [x] Binary comparison (3 images byte-identical)
- [x] M1 authentic execution trace
- [x] M2 DSKY V35 / V16N36 via socket
- [x] M3 LM_Simulator interface investigation (no coupling)
- [x] WASM build + equivalence run

## Phase 2 (done — investigation and validation only)
- [x] Compare authentic initialization candidates and recommend a reproducible approach
- [x] Investigate P63/P64/P66 prerequisites and attempt the smallest descent-entry test
- [x] Inspect throttle, radar, and simulator hardware interfaces
- [x] Run step-locked native/WebAssembly comparison and real-browser validation
- [x] Deliver docs/PHASE2_POWERED_DESCENT_FEASIBILITY.md and new evidence

## Phase 3 (done — minimum instrument integration experiment)
- [x] Review prior evidence and verify minimum sensor/actuator loop in pinned sources
- [x] Execute Luminary099 V41 IMU-gimbal feedback with recorded synthetic initial conditions
- [x] Verify sensor reception, actual AGC output, gimbal motion, feedback-dependent completion, disconnected controls, negative sign, and exact replay (7 tests pass)
- [x] Deliver docs/PHASE3_CLOSED_LOOP_FEASIBILITY.md and docs/phase3-evidence/; verify Phases 1–2 unchanged

## Phase 4 (done — bounded control-path validation, blocker alternative)
- [x] Reviewed and fingerprinted all 78 prior documentation/evidence files; zero preservation mismatches
- [x] Traced Phase 3 output to IMU gimbals/error needles, not spacecraft thrusters; audited the active RCS implementation
- [x] Executed a 4M-cycle original-software readiness probe and exact replay: no STARTDAP, 469 shutdown visits, all 942 RCS packets zero; IMODES33 bit6 blocks control
- [x] Executed active upstream yaw-model component sign/sensor checks, explicitly not an AGC-driven loop
- [x] Delivered docs/PHASE4_CONTROL_PATH_VALIDATION.md and docs/phase4-evidence/; six evidence checks pass

## Phase 5 (done — bounded readiness and spacecraft-model feedback)
- [x] Fingerprinted 109 prior files; reproduced Phase 4 outputs and failure exactly, with zero preservation mismatches
- [x] Traced IMU-off input and captured original readiness gate; corrected only active-low channel030 bit9
- [x] Verified original ISSUP clears inhibition, STARTDAP runs, actual RCS outputs appear, and IMU-off restores rejection
- [x] Executed actual RCS/body/CDU feedback with active upstream model, actuator/sensor disconnects, opposite input, exact replay and explicit single-axis guards
- [x] Delivered docs/PHASE5_IMU_READINESS.md and docs/phase5-evidence/; 12 concrete evidence tests pass

## Phase 6 (done — reproducible technical demonstration)
- [x] Audited Phase 1–5 and fingerprinted 177 prior files; zero preservation mismatches
- [x] Added repeatable entry point reusing unchanged Phase 5 integration and retained minimal corresponding source
- [x] Categorized actual outputs, model state, sensor observations and diagnostics; linked selected raw trace milestones
- [x] Verified fresh replay, feedback disconnect, exact Phase 5 agreement and minimal-source reproduction; 11 tests pass
- [x] Delivered docs/PHASE6_DEMONSTRATION.md and docs/phase6-evidence/; stopped without application development

## Milestone 1 packaging (after the repository audit)
- [x] Preserve the 307 retained files and inventory 29 missing historical logs with original hashes; no reconstructed historical evidence
- [x] Add a separate dated baseline and strict test runner; preserve the original 35 passes / 3 errors explicitly
- [x] Pin Tcl 8.6.16 source/options, build locally and record host toolchain; replace only the legacy Nix dependency launch through an explicit adapter
- [x] Rebuild the unchanged engine/model fixture on macOS arm64; verify connected, disconnected and replay raw traces exactly match Phase 6
- [x] Run 55 new packaging/runtime/launcher tests successfully; Linux and upstream Tcl suite remain NOT RUN
- [x] Verify a clean local clone rebuilds Tcl from the pinned archive and passes make check while retaining the three historical errors explicitly
- [x] Document actual build commands and retain dated milestone evidence in docs/milestone1-evidence/

## Milestone 2: startup and signed CDU timing (single-axis diagnostics)
- [x] Trace the cold reset's zero phase pairs through original PTBAD/01107; preserve the alarm and all earlier evidence
- [x] Verify original V36, ISSUP/STARTDAP and delayed V37 produce a bounded clean post-V36 P00 interval; test early-key, no-V36 and IMU-off controls
- [x] Measure signed slow/fast CDU X timing, modular wrap, mixed runs and settled queues through actual counter-operation packets
- [x] Expose accepted-but-dropped FIFO data and explicit ringbuffer rejection in bounded negative controls
- [x] Confirm the unchanged plant's signed mode-selection defect with paired imposed-yaw component probes
- [x] Retain raw traces, source/rope address proofs, exact replays and the integrated test/check results in docs/milestone2-evidence/

## Milestone 3: corrected yaw selector and paced feedback
- [x] Generate a source-locked modern model with the X/yaw selector changed to use rate magnitude; reject unsupported Y/Z increments
- [x] Verify paired component motion retains numerical states, pulse counts, directions, quantization, wraparound and original inhibits
- [x] Run authentic negative RHC/RCS feedback with distinct packet delivery, FIFO enqueue and counter-application observations
- [x] Compare the original selector, corrected selector, disconnected feedback and exact replay under the same clean startup and conservative pacing
- [x] Preserve all prior evidence and keep the emulator, Luminary and original source archive unchanged
- See docs/MILESTONE3_SIGNED_FEEDBACK.md for actual check results and the separate transport-tail experiment

## Phase 7: bounded simultaneous yaw/pitch feedback (verified capability C)
- [x] Reproduce the unchanged single-axis baseline and preserve all 1,520 earlier retained files
- [x] Verify original Luminary jet, RHC and gimbal mappings against pinned sources and primary documentation
- [x] Extend the retained external model with bounded rigid-body coupling, quaternion attitude and all three derived CDU measurements
- [x] Demonstrate independent pitch, then simultaneous yaw/pitch through actual Luminary RCS packets, connected/disconnected controls and exact replays
- [x] Reconcile real native packet consumption, all three sensor FIFOs, signed applications and settled quaternion-to-counter angles
- [x] Execute 39 Phase 7 tests, all 136 prior milestone tests and fresh validation; retain the three original missing-log errors explicitly
- See docs/PHASE7_MULTIAXIS_VALIDATION.md and docs/phase7-evidence/ for actual commands, measured limits and preserved attempts
- Full independent three-axis control, calibrated spacecraft/IMU fidelity and sustained attitude stability remain NOT RUN. Empty queues establish transport settlement, not vehicle equilibrium.
- Mission initialization, calibrated IMU alignment and source-justified propulsion/radar interfaces remain prerequisites for a credible descent experiment.

## Unresolved descent prerequisites
- Authenticated Rev-1 mission initialization and synchronized vehicle/peripheral state are not available.
- Automatic throttle and radar-measurement integration is not implemented in inspected sources.
- Cold-reset 01107 is explained for the zeroed-memory fixture. A clean post-V36 P00 interval still does not provide calibrated alignment, mission padload or descent readiness.

## Live attitude console (verified bounded local sessions)
- [x] Connect source-mapped yaw/pitch RHC inputs to fresh original Luminary executions, with original readiness, bounded leases, genuine RCS/vehicle/CDU feedback and recorded gateway/native traces
- [x] Verify signed controls, combined input, exact native replay, HTTP boundaries and desktop/phone presentation; preserve recorded replay as a separate mode
- See docs/LIVE_ATTITUDE_CONTROL.md and docs/live-control-evidence/. This remains the synthetic Phase 7 attitude fixture, not a mission initialization or landing application.

## Phase 8: P63 selection from the unchanged Phase 5 startup (verified feasibility)
- [x] Reproduce the literal legacy Phase 5 input schedule and original probe bytes, including its early rejected P00 request and retained 01520
- [x] Add only V37E63E; observe original P63 dispatch, clear REFSMFLG, R02 rejection and 00220, with exact fresh replay
- [x] Trace the pre-entry THRUST counter/channel014 change to V37's original engine-off/autothrottle reset, without claiming thrust or guidance
- [x] Preserve all prior evidence, failed observer attempts and ten passing focused tests in docs/phase8-evidence/
- See docs/PHASE8_POWERED_DESCENT_FEASIBILITY.md. Phase 8 does not depend on Phase 9 alignment and does not demonstrate powered descent.

## Phase 9: original P51 alignment and subsequent P63 readiness (verified synthetic fixture)
- [x] Re-fetch and verify the pinned archive, rebuild unchanged Luminary byte-for-byte, and resolve observers from the actual listing
- [x] Drive authentic P51 DSKY prompts and two COAS-mode star pairs using explicitly synthetic stationary geometry and normal key/mark inputs
- [x] Supply the documented mark interrupt through an external hardware-event bridge; show that normal channel016 packets without this interrupt cannot complete a pair
- [x] Observe original matrix stores and interpreter SET REFSMFLG, then normal V37E63E passing R02; repeat the complete native trace byte-for-byte
- [x] Identify the next actual blocker: zero mission vectors produce a degenerate time-to-go cubic; observed zero-divisor saturation and ROOTPSRS limit route to abortive 01406
- [x] Preserve all Phase 1–8 evidence and run 19 focused tests plus relevant regressions; historical missing-log errors remain disclosed
- See docs/PHASE9_IMU_ALIGNMENT.md and docs/phase9-evidence/. Software validity in this synthetic fixture is not calibrated physical alignment or a valid descent mission state.

## Next prerequisites — not implemented here
1. Establish source-justified, internally consistent mission geometry, state vectors, epochs and guidance padload; inspect the degenerate cubic before another descent-entry attempt. Do not force flags or coefficients to clear 01406.
2. Validate the throttle counter/pulse hardware contract, then a separate engine/thrust plant and specific-force/PIPA transport. The Phase 8 reset signal alone is insufficient.
3. Validate the radar measurement provider/status/interrupt contract after navigation frames and translational state exist.

## Outside the completed Phase 8–9 scope
- Powered descent, ignition/engine response, P64/P66, landing radar, touchdown, new frontend features, multiplayer, AI crew and a complete lunar physics application
