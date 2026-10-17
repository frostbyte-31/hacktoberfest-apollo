# Apollo 11 — guidance and live attitude control

This repository runs original Luminary 099 through the pinned Virtual AGC engine.
Phase 7 verifies bounded, simultaneous yaw/pitch spacecraft feedback, following
independent single-axis demonstrations. A visual replay console presents the
captured experiments and connects bounded pilot inputs to fresh native AGC sessions.
Full independent three-axis control, sustained attitude
stability, powered descent, landing, multiplayer and AI crew remain unverified.

The authentic flight computation, modern emulator, synthetic LM-7 dynamics and
frontend remain separate. No npm installation is needed for the demo.

## Open the visual demo

```sh
python3 -B frontend/serve.py
```

Open **http://127.0.0.1:4173/**. The console shows a rotating illustrative lunar
module, actual recorded RCS commands, sensor readouts and angular-rate histories.
Switch yaw/pitch experiments, compare connected/disconnected feedback, scrub the
timeline and download a provenance record. In **Live AGC** mode, start a fresh
native Luminary session and hold **A/D for yaw**, **W/S for pitch**, or the
on-screen buttons. Actual RHC hardware inputs reach the original software;
actual RCS output drives the retained external model and CDU feedback.

Live mode needs the C compiler and pinned Tcl runtime (`make runtime` on first
use). The server remains local and the CPU waits for the first pilot deflection
after original readiness. Runs last at most 11.7 simulated seconds after that
point. Release or input expiry neutralizes the controller; it does not instantly
stop the vehicle. Use `--replay-only` for a recording viewer without native
dependencies. No landing is simulated. See [frontend instructions and data
boundaries](frontend/README.md) and [live validation evidence](docs/live-control-evidence/README.md).

Frontend data and presentation checks:

```sh
python3 -B -m unittest discover -s frontend/tests -p test_replay.py -v
node --test frontend/tests/replay.test.mjs frontend/tests/live.test.mjs
make test-live      # includes local HTTP/worker contract tests; Node 20+
make validate-live  # actual fresh native signed-axis/replay and HTTP experiments
```

## Check the evidence and tests

Requirements: Python **3.9 or newer**, `make`, and a C compiler available as `cc`
for the native CDU tests. The Python harnesses use the standard library and these
checks require no downloads:

```sh
make verify
make test
```

`make verify` checks the dated baseline's **307 retained files** against their
SHA-256 hashes. It separately reports **29 missing historical logs**. New missing
files, changed bytes, unsafe paths or unlisted retained evidence cause failure.
The baseline does not reconstruct missing evidence or change old manifests.

`make test` runs the unchanged Phase 2–6 suites, packaging tests, Milestone 2
startup/CDU/component tests, and Milestone 3 selector/feedback checks.
The historical result remains **38 tests: 35 passed, 3 errors** on missing logs.
Only those exact preservation errors may be classified as known historical gaps;
unexpected errors, failures or skipped tests make the command fail. A successful
packaging check reports `verified_with_historical_gaps`, with
`all_tests_passed: false`. It never reports that all 38 old tests passed.

Each test invocation records commands, versions, per-test outcomes, tracebacks
and integrity checks in a new `.build/reproducibility/tests/` directory. The
original phase suites can still be run directly and still expose their errors.

## Rebuild and reproduce the existing demonstration

The bootstrap targets macOS and Linux, with Python >=3.9, a C compiler available
as `cc`, `make`, and `curl` for the initial dependency download. This milestone
was verified on macOS arm64; Linux execution remains **NOT RUN**:

```sh
make reproduce
# Or run the tests and reproduction together:
make check
```

The bootstrap downloads **Tcl 8.6.16** from the official release, checks the locked
SHA-256 **before extraction**, and builds it locally under `.build/`. It installs
no system packages and requires neither Nix nor Node. Network access is needed
only for the first Tcl source download. For an offline build with the exact
archive already available:

```sh
python3 tools/reproducibility/bootstrap_runtime.py --archive /absolute/path/tcl8.6.16-src.tar.gz
make reproduce
```

[runtime-lock.json](tools/reproducibility/runtime-lock.json) pins Tcl source and
build options. Host Python, compiler, make, OS and system libraries are recorded
rather than pinned; portable byte-identical binaries are not claimed. Each reuse
checks the downloaded source, extracted source, installed runtime and Tcl smoke
test. If cached inputs change, select a fresh `--cache-dir` and investigate.

The new launcher builds the unchanged pinned engine and Phase 5 bridge, runs
connected feedback, disconnected feedback and a fresh connected replay, and
reuses Phase 6's trace analysis. A narrow, recorded adapter replaces only the old
runner's exact Nix/Tcl launch command with the locked Tcl executable. No emulator,
vehicle model, schedule or guidance algorithm is duplicated or modified.

New run directories under `.build/reproducibility/runs/` contain raw traces,
categorized observations, `SUMMARY.md`, source/input/binary hashes, exact commands,
dependency launch records and validation results. A successful run must pass the
existing causal checks, preserve retained evidence and match **all three original
raw traces byte for byte**. Existing output directories are never overwritten.

This retained Phase 6 reproduction remains synthetic yaw/X-CDU only, with semi-implicit integration,
about 10 ms maximum coupling latency and undrained counter queues. Operate-only
readiness does not establish complete IMU alignment or clean mission startup.

## Validate startup and signed CDU timing

```sh
make validate-milestone2
```

This runs seven stationary startup comparisons, nine X-CDU transport workloads
with fresh-process replays, and 24 imposed-yaw component scenarios. `make check`
also runs this validation after the original three-mode feedback reproduction.
All source inputs are retained locally; only the first Tcl bootstrap needs a
download. Earlier evidence stays unchanged.

The new startup fixture reaches P00 with clear alarm registers after original
V36 and observed software readiness. It retains and explains the initial
`01107`; it does not claim alarm-free power-on or flight-ready alignment.
Transport signs match within a fixed slow/fast mode, and queues settle for the
supported finite cases. Capacity controls expose a silent FIFO drop. The
Milestone 2 plant baseline selects slow mode for negative high rates: +8°/s produces
FAST operations while −8°/s produces slow operations. That defect is diagnosed,
not repaired by these validation harnesses.

[Milestone 2 findings and evidence](docs/MILESTONE2_STARTUP_CDU_VALIDATION.md)
separate authentic software observations from synthetic sensor/component probes
and state the limits on stronger control claims. No Phase 7 work is included.

## Validate the corrected yaw selector and paced feedback

```sh
make validate-milestone3
```

The Milestone 3 fixture generates a derived model from the hash-checked original
source. Its X-axis rate selector uses `abs(Omega_Yaw) < 4`; an explicit boundary
rejects unsupported Y/Z increments. Earlier model files and traces remain intact.
The emulator and Luminary are unchanged.

Paired component probes check the selector correction. Coupled native runs use
actual AGC RCS output, paced X-CDU feedback, and observations of packet
consumption, FIFO enqueue and counter application. A separately labeled tail
ends vehicle integration and sensor generation before draining finite queued
work. Queue settlement does not establish vehicle stability or mission readiness.
`make check` includes these fresh experiments after the earlier reproduction and
Milestone 2 probes.

[Milestone 3 findings and evidence](docs/MILESTONE3_SIGNED_FEEDBACK.md) record its
single-axis outcomes and limits. Phase 7 extends that fixture separately below;
powered descent remains unproven.

## Phase 7: authentic multi-axis attitude validation

```sh
make test-phase7       # fresh locked-Tcl physics tests and integration checks
make validate-phase7   # source checks and fresh native attitude experiments
```

Both targets use the existing source-locked runtime bootstrap. Only its first
download requires network access. `make check` includes these targets after all
earlier tests and reproductions.

The Phase 7 fixture retains original Luminary, the emulator, jet decoding and
model response coefficients. A source-locked external overlay adds quaternion
orientation and rigid-body angular-momentum coupling. Body yaw/pitch commands
and all three derived IMU gimbal measurements remain distinct. The authoritative
rotational state is independent of display coordinates. The separate visual
demo consumes retained traces without changing the validation fixture.

[Phase 7 capability, actual results and limitations](docs/PHASE7_MULTIAXIS_VALIDATION.md)
distinguish independent-axis tests, simultaneous control, modern physics unit
checks and historical hardware assumptions. Earlier evidence remains intact.

## Evidence and provenance

- [Repository audit](docs/PROJECT_STATE_AUDIT.md) records what was verified before
  packaging work and explains the reported Phase 1–6 results and limitations.
- [Milestone 1 packaging report](docs/MILESTONE1_REPRODUCIBILITY.md) records the new
  baseline and actual validation results.
- [Milestone 2 validation report](docs/MILESTONE2_STARTUP_CDU_VALIDATION.md) records
  the clean post-V36 interval, signed transport timing, capacity and model limits.
- [Milestone 3 feedback report](docs/MILESTONE3_SIGNED_FEEDBACK.md) records the
  external model correction, pacing and finite queue settlement.
- [Phase 7 validation report](docs/PHASE7_MULTIAXIS_VALIDATION.md) records the
  multi-axis source mappings, attitude model and actual native experiments.
- [Phase 7 and frontend release checks](docs/phase7-evidence/release-checks/20261017T164459Z/SUMMARY.md)
  preserve the final test results, unchanged trace references and browser proof.
- [Historical gap inventory](docs/milestone1-evidence/missing-historical.json)
  retains the 29 absent paths, original expected hashes and manifest references.
  Recovered logs are accepted only at their original hash. Fresh logs belong in
  dated new evidence, never under a missing historical filename.
- [Phase 6 report](docs/PHASE6_DEMONSTRATION.md) describes the original demonstration
  and retained minimal corresponding-source bundle. The engine revision is
  `f577e3fd917866c59334e6cdd32504f09df76f60`; the retained rope SHA-256 is
  `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.

The minimum source bundle rebuilds the emulator/model fixture; it does not include
the full assembler and Luminary flight sources needed to reassemble the rope.
Existing phase evidence and tracked historical Python caches are preserved.
New bytecode and generated build outputs are ignored. Emulator/harness GPL and
source-license files remain in the corresponding-source archives; the Tcl release
contains its own license. That minimal archive predates Phase 7; the new external
attitude fixture and its evidence are maintained separately in
`docs/phase7-evidence/`.
