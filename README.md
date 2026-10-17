# Apollo AGC feedback investigation

This repository runs retained Luminary 099 through the pinned Virtual AGC engine
and validates a bounded, single-axis spacecraft feedback demonstration. It is
research infrastructure for a lunar landing simulator. Powered descent, landing,
multi-axis control, multiplayer and AI crew are **not demonstrated**.

The authentic flight computation, modern emulator and synthetic LM-7 dynamics
remain separate. There is no npm application to build.

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

`make test` runs the unchanged Phase 2–6 suites, packaging tests, and Milestone 2
startup/CDU/component tests.
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

The model remains synthetic yaw/X-CDU only, with semi-implicit integration,
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
unchanged plant still selects slow mode for negative high rates: +8°/s produces
FAST operations while −8°/s produces slow operations. That defect is diagnosed,
not repaired by these validation harnesses.

[Milestone 2 findings and evidence](docs/MILESTONE2_STARTUP_CDU_VALIDATION.md)
separate authentic software observations from synthetic sensor/component probes
and state the limits on stronger control claims. No Phase 7 work is included.

## Evidence and provenance

- [Repository audit](docs/PROJECT_STATE_AUDIT.md) records what was verified before
  packaging work and explains the reported Phase 1–6 results and limitations.
- [Milestone 1 packaging report](docs/MILESTONE1_REPRODUCIBILITY.md) records the new
  baseline and actual validation results.
- [Milestone 2 validation report](docs/MILESTONE2_STARTUP_CDU_VALIDATION.md) records
  the clean post-V36 interval, signed transport timing, capacity and model limits.
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
contains its own license. No Phase 7 work is included.
