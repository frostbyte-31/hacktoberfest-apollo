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

## Phase 7 (done — pitch-axis feedback loop VERIFIED; see docs/PHASE7_MULTI_AXIS_VALIDATION.md)

## Phase 8 (done — blocked at R02 alarm 00220, no valid REFSMMAT; see docs/PHASE8_POWERED_DESCENT_FEASIBILITY.md)

## Phase 9 (done — P51 alignment completed, REFSMMAT valid, P63 passed R02; see docs/PHASE9_IMU_ALIGNMENT.md)
- [x] Trace P51/P52 alignment, star-sighting interfaces, REFSMMAT generation and P63 readiness checks in pinned source
- [x] Design and run a source-faithful alignment experiment (no forced flags, no fabricated REFSMMAT)
- [x] Record V37E63E outcome after alignment attempt; classify all findings VERIFIED/ASSUMED/NOT RUN
- [x] Deliver docs/PHASE9_IMU_ALIGNMENT.md and docs/phase9-evidence/; keep Milestone 1 integrity failure visible
- Root cause of the V01N71 PROCEED failure: driver used channel 032 bit 15; PRO is bit 14 (VERIFIED). Second driver bug: 4-digit angle field for |angle| < 100 deg (VERIFIED).
- Outcome: P51 two-star alignment completed through original software (REFSMMAT populated, REFSMFLG set); V37E63E selected P63 with no alarm 00220; ignition algorithm then aborted POODOO 01406 on uninitialized descent targeting data (expected). No descent claimed.

## Next bounded validation (requires separate approval)
- Repair the modern model's signed rate-mode selection in a separately identified fixture, then test paced negative-rate feedback and queue settlement before stronger attitude-control claims.
- Keep the emulator/flight code and earlier baselines unchanged; do not expand axes or begin descent work as part of that correction.

## Unresolved descent prerequisites
- Authenticated Rev-1 mission initialization and synchronized vehicle/peripheral state are not available.
- Automatic throttle and radar-measurement integration is not implemented in inspected sources.
- Cold-reset 01107 is explained for the zeroed-memory fixture. A clean post-V36 P00 interval still does not provide calibrated alignment, mission padload or descent readiness.

## Not authorized
- Frontend, multiplayer, AI crew, complete lunar physics engine, full application development
