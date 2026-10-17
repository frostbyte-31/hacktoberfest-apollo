# Phase 1 — Proof-of-Execution Plan (no app build yet)

Scope: deliver `docs/PHASE1_PROOF_PLAN.md` and attempt the smallest real execution inside this sandbox. No frontend, multiplayer or AI crew yet. Each result in the doc is labelled **VERIFIED** (we ran it and kept the log), **ASSUMED**, or **NOT RUN**.

## Already checked (read-only GitHub API, 2026-10-17)

- `virtualagc/virtualagc` HEAD `f577e3fd917866c59334e6cdd32504f09df76f60`. It contains `yaYUL/`, `yaAGC/`, `yaDSKY2/`, `Luminary099/` (with `Makefile`, `Luminary099.binsource`, `AP11ROPE.binsource`), plus `LUM99R2/` and `LMY99R0/` (other Luminary 99 revisions), `Contributed/LM_Simulator/` (`lm_simulator.tcl` and `.ini` files, including a no-DSKY mode), `yaACA*` (hand controller), `yaUniverse`, `Validation/`, and `Dockerfile`.
- `chrislgarry/Apollo-11` HEAD `911e5c0283c629c50cb97666f34065e8c07d71a5`. Used only to cross-check provenance; the build uses virtualagc.
- `siravan/moonjs` HEAD `b99615c41972ffb7d032222e203df62fa75ec184` (GPL-2.0). It is an Emscripten build of an older yaAGC.
- Not yet checked: what each binsource represents (an assembler-output check versus a physical rope dump), and which revision Apollo 11 flew. Apollo 11 is generally cited as Luminary 1A, Luminary 099 (rev 1). LUM99R2 and LMY99R0 must be explained in the doc rather than assumed.

## What I will do after approval

1. **Pinning:** clone each repo at the SHAs above into `/tmp/apollo` (outside the app). Record the SHAs, the compiler versions (`gcc --version`, `make --version`), and the licenses (virtualagc LICENSE/COPYING, public-domain status of the AGC sources) in the doc. The doc also gives the Dockerfile recipe for reproducing this on another machine.
2. **Build:** run `make` for `yaYUL` and `yaAGC` (and `oct2bin`, if the binsource conversion needs it). Then assemble `Luminary099/MAIN.agc`, which produces `Luminary099.bin`.
3. **Rope comparison:** convert both binsource files to binary with the repository's own tool. Compare them with `cmp -l` and `sha256sum`, counting differing words per bank, and checking that bank checksums (BUGGER words) match. The doc states exactly what a match proves (the assembler output matches the reference image) and what it does not prove, depending on the investigated provenance of that reference image.
4. **Milestone M1 — authentic instructions execute:** run `yaAGC --core=Luminary099.bin` headless. Capture execution using yaAGC's own debug or trace mode, or its socket channel output. Pass: the instruction trace shows fetches from fixed memory at the GOJAM/restart entry, and the cycle counter advances. Fail: a crash, or a trace that does not match the listing addresses.
5. **Milestone M2 — mission-software behavior:** a small Python client using yaAGC's documented socket protocol (the same one yaDSKY2 uses) sends DSKY keycodes on channel 015 for `V37E 00E`, then `V35E` (lamp test), then `V16N36E` (clock). It decodes channel 010 relay words into PROG/VERB/NOUN/R1–R3 digits. Pass: the decoded displays match the expected Luminary responses (for example, the N36 time incrementing) in a logged, replayable JSONL transcript. P63 entry needs a valid state and alignment, so it is listed as a stretch goal.
6. **Milestone M3 — physics coupling:** this is investigation only in Phase 1. I will document which LM interfaces `LM_Simulator` already implements (IMU CDU/PIPA counters, RCS jet channels, throttle, radar) and how yaUniverse/yaACA connect, all taken from their source rather than invented. Pass criteria are defined (for example, a change in AGC throttle output measurably changes simulated thrust in the log), but M3 will be marked NOT RUN.
7. **WebAssembly evaluation, kept separate:** check the age of moonjs's yaAGC against upstream, and whether the current Emscripten can compile the pinned yaAGC. If time allows, run the same M1/M2 scripts under Node with the WebAssembly build and diff the transcripts against the native build. It is viable only if the transcripts are identical.
8. **Deliverable:** `docs/PHASE1_PROOF_PLAN.md`, containing the commands, dependencies, artifacts (SHA-256 of each binary), validation procedure, actual results with log excerpts, and explicit limitations. Raw logs go in `docs/phase1-evidence/`.

## Limitations to state up front

- The sandbox may lack compilers or toolkit libraries. yaDSKY2 needs wxWidgets and LM_Simulator needs Tcl/Tk, so GUIs are skipped and only headless paths are used. Any step that cannot run here will be reported with the exact command to run on a local Linux machine or in the virtualagc Docker image.
- Nothing will be claimed as "matches flown software" or "AGC controls landing" without the corresponding logged evidence.
