# Phase 6 — Reproducible AGC-controlled vehicle demonstration

2026-10-17 UTC. Technical command-line demonstration only. **VERIFIED** means inspected source or retained execution, identified below; **ASSUMED** means an unvalidated physical/model interpretation; **NOT RUN** means not executed. Prose channels, words, counter addresses and alarms are octal; trace/schedule integers and CPU-call indices are decimal.

## Result and stop decision

**VERIFIED execution:** a repeatable entry point now builds the unchanged pinned engine, executes original Luminary099 against the existing external vehicle/IMU model, and produces raw logs, categorized observations, selected event chronology and a concise summary. Connected feedback, feedback-disconnected control and a fresh connected replay all exit0. Connected replay is byte-identical, and all three traces also exactly match the corresponding accepted Phase5 traces.

**VERIFIED independent-source reproduction:** a second launch using only the retained minimal corresponding-source bundle produced the same three raw trace hashes. No second emulator, physics implementation, flight algorithm, readiness bypass or injected RCS command was created. Six fresh executions were performed only for demonstration reproducibility and causal-control validation; prior readiness, blocked-actuator and opposite-input experiments were audited, not repeated.

**ASSUMED physical fidelity:** this remains a synthetic single-axis LM-7-model experiment, not historical flight telemetry or Apollo11 dynamics. **NOT RUN:** powered descent or a lunar landing. Phase6 stops here; the suggested later hackathon experience is not implemented or underway.

## 1. Audit of Phases 1–5 — VERIFIED retained evidence/source inspection

- Phase1 establishes original-source instruction execution, DSKY behavior and byte agreement of three assembled/transcribed rope images. It does not establish identity with physical flown hardware; AP11ROPE is a recreation and reconciled transcription, not independent hardware telemetry.
- Phase2 establishes cold-start P63 dispatch/readiness rejection and native/WASM agreement for its diagnostic schedules, not initialized descent. Mission state, throttle and radar integration remain unresolved.
- Phase3 establishes internal IMU coarse-alignment feedback through0174–0176, not spacecraft propulsion.
- Phase4 identifies the separate005/006 RCS interface and the IMU-unusable shutdown gate. Its injected-jet component test alone was not an AGC-driven spacecraft loop.
- Phase5 resolves the minimum fixture's IMU OPERATE input defect through a source-justified one-bit correction; original ISSUP clears inhibition and STARTDAP executes. Its connected, sensor-disconnected, actuator-blocked, opposite-input and replay evidence establishes bounded causal feedback; its retained12-test log passes. `test_readiness.py`, `results.json`, readiness transcripts and plant transcripts were inspected without rewriting them.

Authentic computation is the public-domain Luminary099 Rev1 rope, executed by the modern GPL yaAGC emulator. Modern components are the ringbuffer/ctypes bridge, Python coupling transport, synthetic controller schedule, active upstream Tcl LM-7 vehicle and IMU model, and the Phase6 inspection/launch layer. Model readings are not historical Apollo telemetry. Source revision: `f577e3fd917866c59334e6cdd32504f09df76f60`. Rope SHA-256: `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`,73728bytes.

Before Phase6 additions,177 files under earlier reports/evidence were fingerprinted, including existing hidden/cached files. Final `phase6-evidence/preservation_check.json` has zero mismatches. No Phase1–5 report or evidence file was changed.

## 2. Repeatable entry point

From project root on Linux with Python3, GCC/libm and Nix available:

```sh
mkdir -p /tmp/apollo-phase6-source
tar -xzf docs/phase6-evidence/corresponding-source.tar.gz -C /tmp/apollo-phase6-source
python3 docs/phase6-evidence/demonstrate.py \
  --source /tmp/apollo-phase6-source \
  --output /tmp/apollo-phase6-new-run
cat /tmp/apollo-phase6-new-run/SUMMARY.md
python3 -m unittest discover -s docs/phase6-evidence -p 'test_demonstration.py' -v
```

Output must not already exist; choose a new scratch directory each time. The source bundle is the minimum unchanged compilation units, headers, active simulator modules/main initialization and license files, not a full upstream checkout. For full flight-source inspection use the pinned archive:

`https://codeload.github.com/virtualagc/virtualagc/tar.gz/f577e3fd917866c59334e6cdd32504f09df76f60`

Full archive SHA-256: `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267` (prior evidence). The new bundle entries and hashes are in `corresponding-source-hashes.json`; no source edits are present. Emulator/harness licensing is GPL-2.0-or-later; binaries remain scratch build outputs with hashes and corresponding source retained.

Preflight checks compare all Phase5 recorded participating source, rope and fixture hashes, check dependencies, and record additional header hashes. The launcher records exact commands, UTC times, tool versions, exit codes and stdout/stderr; failed commands produce a failure record, not a completion assertion. Each command has a180-second timeout. It rejects incomplete/non-finite inspected traces, rejected inputs/feedback and unsupported axes. The existing Phase5 child-process implementation is reused unchanged; the wrapper timeout is not a guarantee of process-tree cleanup in every failure case. Such fault-injection testing is **NOT RUN**.

Verified environment: Python3.13.12, GCC14.3.0, Nix2.31.2, Tcl8.6.16 provisioned via `nix shell nixpkgs#tcl -c tclsh`. Nix's package reference is not a frozen lockfile; versions/observations are recorded rather than claiming portable bit-identical binaries. Raw output equality was verified in the recorded environment.

## 3. Initial conditions and exact initialization

The entry point reuses `phase5-evidence/run_loop.py`, `plant_bridge.c`, `plant_server.tcl` and `operate_inputs.txt` directly; it does not duplicate their integration. Each run resets the CPU and starts a fresh Tcl process. No saved core, historical padload, initial flight-memory patch or external readiness-flag write is used. Vehicle body rates and gimbals start at zero; the main-file defaults are literal upstream LM-7 constants. Engine outputs initially latch zero.

The full decimal input schedule is copied verbatim into each run's `initial_conditions.json` and remains in the Phase5 fixture. Key sequence:

| CPU-call index | Existing fixture action |
|---:|---|
|100000|Channel031=067777: attitude hold selected|
|100001|Channel030=036377: PGNCS ownership and active-low IMU OPERATE asserted; healthy/released remaining fixture lines|
|426665–490664|V36E through channel015 key packets|
|1000000–1127998|V37E00E; this premature request is refused during initialization, producing01520, not P00|
|1600000–1663999|V77E|
|2500000|Channel031 yaw-controller direction discrete; channel0167 held controller value20 at2500001|
|2700000–2700001|Controller value zero; attitude-hold neutral restored|
|4000000|Stop after46.88s under the wrapper timing convention; no counter-queue drain|

**VERIFIED Phase5 instruction evidence, not newly instrumented in Phase6:** IMUOP→PROCTNON/OPONLY→CAGESUB2/ISSZERO→UNZ2→ISSUP. Original zero discrete is asserted; software zeroes counters and waits its executable10.24s settling delay. V36 starts initialization again. ISSUP changes IMODES33 from036040 to036000 at1480209, then STARTDAP executes at1484080. Phase6 begins motion only after this fixture's established readiness timing; its actual outputs/readbacks reproduce Phase5 exactly. This is operate-only readiness, not full90-second cold turn-on, calibrated alignment, valid REFSMMAT or clean major-mode initialization. Cold-start01107 and later01520 remain disclosed.

## 4. Inspectable chain and data categories

Raw logs are unchanged JSONL. Derived `*.categorized.jsonl` preserve every observation and raw1-based line number with explicit category: `agc_output`, `simulated_vehicle`, `simulated_sensor`, `agc_diagnostic_readback` or `diagnostic`. Inputs and explanations are not mislabeled flight outputs. `*.summary.json` selects observed milestones; `SUMMARY.md` is human-readable. Derived times use the disclosed11.72µs CPU-call convention, not measured hardware or historical mission elapsed time.

Connected trace (`demo-run/closed.jsonl`):

| Stage | CPU-call index | Raw line | Actual observation |
|---|---:|---:|---|
|Synthetic controller input|2500000|4302|Direction packet accepted|
|AGC-generated RCS|2509125|4348|Channel006 word00125|
|Simulated vehicle response|2509384|4350|Yaw rate+0.0149686812°/s; X-gimbal+0.0000454371°; actual jet latch00125|
|Simulated sensor request|2514502|4373|PCDU to counter032, delivered and accepted|
|Emulator sensor readback|2515355|4377|Actual AGC CDU X=1, Y/Z=0|
|Subsequent original control output|2705321|6028|Opposing channel006 word00252|

RCS mapping is source-verified in `lm_simulator.tcl:812–818` and `AGC_Simulation_Monitor_Control.tcl:237–242`:006 bits1–8 select Q3A/Q4F/Q1F/Q2A/Q2L/Q3R/Q4R/Q1L.00125 selects positive-yaw jets;00252 selects the opposing set. The model computes angular-rate change from the actual jet latch, integrates body rotation, transforms it to stable-member gimbals (`AGC_IMU.tcl:660–692`), and quantizes it into PCDU/MCDU operations. The unchanged emulator paces queued slow/fast operations at400/6400Hz; acceptance is not immediate counter application. No absolute angle-counter writes replace feedback.

**Causality qualification:** the table is a chronological observed chain, not an instruction-level claim that one particular sensor pulse caused one particular jet instruction. The controlled disconnected-feedback comparison establishes feedback dependence of original AGC commands. Identical synthetic inputs/model code and fresh resets are used; only sensor delivery is suppressed.

## 5. Validation results — VERIFIED execution

| Run | Peak abs model yaw °/s | Final model X-gimbal ° | Final AGC CDU X | Generated / delivered sensor requests |
|---|---:|---:|---:|---:|
|Connected|4.859385265209125|16.84156247751019|1533|1539 /1539|
|Sensor feedback disconnected|11.341167317374987|177.68649693043514|0|16173 /0|
|Fresh connected replay|4.859385265209125|16.84156247751019|1533|1539 /1539|

All delivered requests are accepted. Connected output includes seven00252 opposing-jet words; feedback-disconnected output includes none. Full AGC RCS transcripts differ, while disconnected CDU readback stays zero despite model motion. Exact replay and separately extracted-source reproduction are byte-identical for each of the three modes. Raw bundle-reproduction logs are therefore represented by their verified hashes and retained identical primary raw logs rather than duplicate copies.

The new11-test suite passes: prior-file preservation, exact replay, actual initial jet timing/value, feedback-dependent commands, disconnected readback with retained motion, accepted versus applied sensor counts, origin/delivery timestamp separation, deterministic analysis, incomplete/non-finite trace rejection and eight successful command exits. Tests exercise data/behavior, not text appearance. An initial test-run error shadowed unittest's `run` method with a directory variable; corrected to `records`. The original failure log is preserved; it was test infrastructure, not an emulator failure.

## 6. Approximations and unimplemented systems

- **ASSUMED:** upstream LM-7 inertia/jet coefficients and stationary zero-state fixture are suitable synthetic demonstration conditions; not validated Apollo11 parameters.
- **VERIFIED implementation limitation:** semi-implicit integration; at most853 CPU calls (~9.998ms) per coupling chunk; actual jet/zero-latch interval integration; sensor operations delivered at chunk end before the next CPU chunk. Sensor origin and delivery timestamps are separate. Raw row order is not globally timestamp-sorted because outputs are drained before plant/sensor analysis.
- **VERIFIED limitation:** direct cycle-locked jet decoding is not the upstream socket dispatcher's stale-latch ordering or wall-clock timing. This validates the bounded external coupling, not the complete GUI simulator.
- **VERIFIED inherited issue:** slow/fast selection uses `Omega_Yaw <4`, not absolute rate; positive/negative performance is not certified symmetric. Counter queues are not drained, so final1533 is not asserted equal to1539 generated requests.
- **NOT RUN:** complete IMU startup/alignment, cold-start01107 isolation, clean P00 entry, long-duration attitude-hold certification, nonzero initial attitude/general three-axis control, calibrated sensors/dynamics, coupled native/WASM comparison, mission padload, throttle/radar integration, P63/P64/P66 descent, touchdown, frontend, multiplayer and AI crew.

Evidence inventory: `prior_hashes.json`, `preservation_check.json`, `demonstrate.py`, `test_demonstration.py`, tests and initial failure log, minimal corresponding-source bundle/hashes, `demo-run/` raw/categorized traces and summaries, `bundle-reproduction/` commands/versions/hashes/comparison, `phase5_trace_comparison.json`, and the evidence SHA-256 manifest. Hash manifests provide integrity comparisons, not cryptographic signatures or independent historical authenticity.

**Stop:** the requested technical demonstration is reproducible and inspectable. A later small playable mission remains a separate authorization and must keep actual AGC outputs, simulated state and unfinished placeholders distinct; no completed landing capability is implied.