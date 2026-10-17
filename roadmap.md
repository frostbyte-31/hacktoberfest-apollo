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

## Unresolved prerequisites (not authorized follow-on work)
- Authenticated Rev-1 mission initialization and synchronized vehicle/peripheral state are not available.
- Automatic throttle and radar-measurement integration is not implemented in inspected sources.
- The additional 01107 alarm in the cold-start P63 attempt requires isolation before a stronger initialization claim.

## Not authorized
- Frontend, multiplayer, AI crew, physics engine, full application development
