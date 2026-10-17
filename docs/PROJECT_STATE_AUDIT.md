# Project state audit — 17 October 2026

**VERIFIED:** this repository contains an inspectable, bounded AGC attitude-feedback investigation. It does not yet contain the proposed multiplayer landing application. Retained evidence supports single-axis spacecraft-model feedback; a fresh readiness reproduction succeeds. The checkout is Git-clean at the starting revision, but its evidence package is incomplete and three existing test suites currently fail preservation checks.

Here **VERIFIED** identifies source inspection, retained-data checks, or fresh execution as stated; **ASSUMED** identifies unvalidated physical interpretations; **NOT RUN** identifies work not executed in this audit. Channel numbers, addresses, words and alarms below are octal; CPU-call indices are decimal.

## Repository and Git state

- Starting branch/revision: `main`, `ee5e7012bda1768b69ff2be8443a5c589abd7838`; initial working tree clean. Local `origin/main` and GitHub `main` matched that revision. GitHub exposes only `main` on this remote. Recent history contains the phase evidence, generic `Changes` commits, and README additions; history was not rewritten.
- Configured fetch/push destination: `git@github.com:frostbyte-31/hacktoberfest-apollo.git`. The brief's `hacktoberfest-apollo26` also exists, at a different `main` revision (`8709b2543373d052108dca4c6fe6cafa92960dda`). The owner explicitly selected the **current origin** for this audit's push; the remote configuration was preserved.
- The 243 tracked files comprise instructions, roadmap, Lovable metadata, six phase reports and their evidence. There is no application source tree, `package.json`, root build system, authoritative simulation service, frontend, multiplayer or AI crew implementation. DSKY clients here are investigation harnesses.
- `README.md` describes a Lovable screenshot project and recommends `npm i` / `npm run dev`, but no npm project exists. These are not working build instructions. `AGENTS.md` and `roadmap.md` fit the actual investigation architecture more closely.

All six expected reports and `docs/phase1-evidence/` through `docs/phase6-evidence/` exist. Their tracked evidence-file counts are respectively **13, 27, 31, 29, 66, 66**. Full inventory, missing paths and integrity results are in [integrity.json](audit-evidence/2026-10-17/integrity.json).

## What the phase evidence establishes

| Phase | VERIFIED support and qualification |
|---|---|
| 1 | Three retained 73,728-byte rope images are byte-identical, SHA-256 `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`. Native/WASM DSKY transcripts exist. Reassembly and restart-debugger reproduction were **NOT RUN**; full flight source, assembler and several claimed logs are absent. Agreement of these images does not independently establish identity with physical flown rope. |
| 2 | Fresh native clock/P63 executions exactly match retained native captures; retained Node/browser captures also match those traces. Both evidence tests pass. P63 reaches IMU-readiness rejection with `01107/00210`, rather than descent. Agreement covers these scenarios, not full hardware/ISA validation. |
| 3 | All five fresh scenarios exactly match retained captures; seven evidence tests pass. Coarse-alignment outputs `0174–0176` move a synthetic IMU gimbal; counter feedback completes the software check. Sensor/actuator disconnections add `00211`; opposite input reverses counts. This moves an instrument. All RCS words are zero. |
| 4 | Five behavioral checks pass; preservation check errors. Retained original-software probe has 469 shutdown visits, no STARTDAP, and 942 zero RCS packets. Separate injected-jet component tests establish model sign/sensor behavior, not AGC-driven control. This readiness blocker is superseded by Phase 5. |
| 5 | Eleven behavioral checks pass; preservation check errors. Fresh unchanged readiness runner compiled and executed baseline, operate, repeat and IMU-off cases: all four 4-million-call traces exactly match retained Linux captures. Retained five-mode vehicle traces establish actual RCS, motion, sensor return and feedback-dependent subsequent commands. The vehicle loop itself was not freshly launched here. |
| 6 | Ten analysis/behavior checks pass; preservation check errors. Retained connected/replay traces match exactly; connected feedback generates opposing RCS commands absent from the disconnected control. The 24-file source bundle matches its manifest. Fresh documented demo launch exits 1 at missing-Nix preflight, before engine/vehicle execution. |

**VERIFIED discrepancy:** the Phase 1 display-comparison helper prints `identical: False` at a clock frame while exiting 0. Host/socket timing differs, and its clock filter retains some clock frames. This helper's exit code is not an equivalence assertion. Phase 2's cycle-locked comparison addresses a different, stronger bounded claim.

## Actual AGC-to-vehicle feedback path

The source pin is Virtual AGC `f577e3fd917866c59334e6cdd32504f09df76f60`. The modern yaAGC engine executes the retained Luminary 099 rope. Minimal archives retain engine/model sources and licenses, but not the full Luminary assembly or assembler. Fresh builds below therefore reuse the retained rope rather than re-establishing assembly provenance.

`phase5-evidence/run_loop.py` and `plant_bridge.c` reset/step the pinned engine through its ringbuffer backend. They consume actual channel `005/006` RCS output and channel `012` zeroing output, timestamp actuator intervals, and pass them to the external `plant_server.tcl`. That script reuses upstream LM-7 initialization plus the active vehicle and IMU modules; it does not replace flight computation.

The source-mapped channel `006` bits select yaw jets. The model converts their latch intervals into angular acceleration/rate and X-gimbal rotation. It quantizes motion into PCDU/MCDU operations for counter `032`, delivered through emulator counter-operation packets. Later CDU readbacks and original RCS commands change. No direct absolute CDU or flight-state memory writes supply feedback. Retained sensor-disconnected, actuator-blocked, opposite-input and replay controls distinguish these causal links ([runner](phase5-evidence/run_loop.py), [plant](phase5-evidence/plant_server.tcl), [tests](phase5-evidence/test_readiness.py)).

Readiness is not bypassed: relative to the Phase 4 baseline, the correction changes only active-low channel `030` IMU OPERATE bit 9. Original initialization/ISSUP clears `IMODES33` inhibition and STARTDAP runs. Fresh readiness traces reproduce that result. Premature `V37` still produces `01520`. Cold-start `01107` appears early and V36 clears its register; its cause remains unresolved. DAP readiness is not a clean mission padload or complete alignment.

**ASSUMED:** synthetic LM-7 constants and zero initial rates/gimbals are adequate demonstration conditions, not calibrated Apollo 11 dynamics. **VERIFIED limits:** yaw/X-CDU only; unsupported axes are rejected; semi-implicit integration; maximum 853-call coupling interval (about 10 ms at the fixture's 11.72 µs convention); sensor delivery at chunk end; counter queues not drained. Packet acceptance does not imply applied counts. The inherited signed-rate test uses `Omega_Yaw < 4` rather than magnitude; sign symmetry is unproven. FIFO saturation/drop instrumentation is absent; this audit does not assert that retained runs dropped data.

## Commands and actual results

Audit host: macOS arm64, Python 3.9.6, Apple clang 21 exposed as `gcc`, native Tcl 8.5.9. Nix, Node and Emscripten are absent from the command path. Existing tests were run without bytecode writes:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/phase2-evidence -p test_validation.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/phase3-evidence -p test_loop.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/phase4-evidence -p test_control_path.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/phase5-evidence -p test_readiness.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/phase6-evidence -p test_demonstration.py -v
```

**Actual total: 38 tests, 35 passed, 3 errors.** Phases 2/3 exit 0; Phases 4/5/6 exit 1 on missing `docs/phase3-evidence/build.log`. These are retained-capture/integrity tests, not automatic new emulator launches. Commands, times, exit codes and full output are retained in [audit evidence](audit-evidence/2026-10-17/test-commands.json).

For safe fresh native execution, extract `docs/phase6-evidence/corresponding-source.tar.gz` into a new scratch directory and use a new output directory:

```sh
python3 docs/phase3-evidence/run_experiment.py SOURCE NEW_OUTPUT
python3 docs/phase5-evidence/run_validation.py SOURCE NEW_OUTPUT
python3 docs/phase6-evidence/demonstrate.py --source SOURCE --output NEW_OUTPUT
```

The first two build original engine compilation units with the retained harnesses. Phase 6 additionally requires Nix and Tcl >=8.6 through `nix shell nixpkgs#tcl`; the repository does not lock that package reference. On this host its launch was **attempted but blocked at preflight**, not passed. [Failure and command](audit-evidence/2026-10-17/auxiliary-commands.json) are preserved. Browser/WASM execution and rope reassembly were **NOT RUN**. Avoid running `browser_validate.py` in the retained evidence directory: it overwrites captures. Use isolated scratch outputs for fresh investigations.

Fresh native builds and **11 executions** succeeded: two Phase 2 schedules, five Phase 3 scenarios and four Phase 5 readiness cases. All 11 raw traces match retained captures byte for byte across Linux/GCC and this Mac/clang. Exact compilation/execution commands, source/input hashes and comparisons are in [native-reproduction/](audit-evidence/2026-10-17/native-reproduction/), [readiness-launch.json](audit-evidence/2026-10-17/readiness-launch.json) and [readiness-reproduction/](audit-evidence/2026-10-17/readiness-reproduction/). Identical new captures are represented by hashes and retained raw references; binaries are excluded. A preliminary audit-orchestration error from Python 3.9's unsupported tar extraction keyword is recorded separately; compatible validated extraction resolved it before compilation, without changing source.

## Evidence gaps and remaining blockers

**VERIFIED:** 29 unique repository log files referenced by manifests are absent: Phase 1 has 14, Phase 2 seven, Phase 3 four, Phase 4 one, Phase 5 one, Phase 6 two. These include claimed test/build/failure logs. All present files checked against phase manifests match; absence is not evidence of tampering. Neither current ignore rules nor available all-ref history explains the omission. Historical “all tests pass”/“all logs retained” statements cannot be applied unchanged to this checkout. Existing preservation manifests and tests were preserved, not weakened or regenerated.

The minimum source bundle is sufficient for bounded native harness builds, not offline rope reassembly. Historical `/tmp/apollo/va` and `/tmp/wbuild` do not exist. README instructions, absent logs, missing dependency lock and tracked Python caches prevent calling this a fully reproducible clean package, despite its initially clean Git state.

**NOT RUN / unproven:** multi-axis control, coupled native/WASM vehicle agreement, authenticated revision-specific mission initialization, complete IMU alignment/REFSMMAT, calibrated descent dynamics, powered descent or landing. `THRUST` is erasable counter `055` with channel `014` enable semantics, not output channel `055`. The current harness wires no descent-throttle or radar contract; the pinned ringbuffer `RequestRadarData` is empty. Upstream descent equations alone do not establish integrated propulsion. Synchronized mission epoch/frame, gravity/translation, PIPA/radar inputs, fuel and touchdown remain prerequisites for a credible descent experiment.

## Three recommended milestones — not implemented

1. **Repair the reproducibility package first.** Recover original missing logs if available; otherwise record their loss explicitly and retain a separately dated fresh baseline. Supply correct root build instructions and a locked supported environment. Acceptance: fresh-clone baseline checks and the unchanged three-mode Phase 6 demo pass with recorded hashes. Historical preservation checks can pass only if their original inputs are recovered; keep unresolved failures explicit. Do not fabricate old logs or rewrite their manifests to claim preservation.
2. **Validate clean initialization and signed sensor timing.** Wait for source-traced readiness before V37, isolate `01107/01520`, then measure positive/negative CDU pacing, queue settlement and overflow observability. Keep the existing single-axis model and disconnected controls. This reduces more immediate uncertainty than adding axes.
3. **Establish the smallest descent-interface prerequisite.** Source-map and independently test throttle-counter/enable behavior and required PIPA/radar measurements with explicit units/frames and revision-compatible initial state. Reject unsupported hardware behavior; require these gates before attempting bounded P63 descent. This is a prerequisite experiment, not a complete landing implementation.

Only this audit and new audit records were added. [All 238 original documentation/evidence files remain unchanged](audit-evidence/2026-10-17/preservation_check.json). No application, emulator, model or fixture was changed. Work stops at this audit; the next engineering milestone requires owner approval.
