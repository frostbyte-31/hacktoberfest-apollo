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

## Minimum next validation (requires separate approval; Phase 7 not started)
- Clean revision-specific startup schedule: wait for initialization before V37, isolate cold-start01107, and validate symmetric signed CDU timing before stronger control claims.

## Unresolved descent prerequisites
- Authenticated Rev-1 mission initialization and synchronized vehicle/peripheral state are not available.
- Automatic throttle and radar-measurement integration is not implemented in inspected sources.
- The additional 01107 alarm in the cold-start P63 attempt requires isolation before a stronger initialization claim.

## Not authorized
- Frontend, multiplayer, AI crew, complete lunar physics engine, full application development
