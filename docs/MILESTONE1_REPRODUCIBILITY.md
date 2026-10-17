# Milestone 1 — Evidence packaging and reproducible native setup

17 October 2026. Scope: repair packaging and repeat the accepted single-axis
experiment. No Phase 7, new vehicle physics, flight initialization, guidance,
frontend or multiplayer work is included.

**VERIFIED:** the new baseline checks every retained file; a source-locked local
Tcl build executes the unchanged Phase 5 integration; all three fresh raw traces
match Phase 6 byte for byte. **Historical completeness remains false:** 29 logs
are absent, and the original preservation tests still error. The earlier audit
and all Phase 1–6 reports, harnesses, captures and manifests remain unchanged.

## Evidence policy

[baseline.json](milestone1-evidence/baseline.json) pins 307 files present at audit
commit `4d77f7bdb2c32986874db72238b988a417f00fa0`: the phase reports/evidence,
audit records/report and project instructions. This is a new byte snapshot, not
a reconstruction of missing historical evidence.

[missing-historical.json](milestone1-evidence/missing-historical.json) records the
29 absent paths and their original hashes from 44 manifest references. The
verifier checks this inventory against the pinned audit and the actual original
manifests. A recovered log must match its original hash. New missing files,
changed bytes, unsafe/symlinked files, inconsistent metadata or unlisted evidence
make verification fail. Existing Python caches are pinned; new bytecode is
disabled/ignored. There is no automatic baseline-regeneration command.

The new test runner executes the unchanged suites in isolated child processes.
It retains original unittest outcomes/tracebacks and classifies only the three
specific preservation checks' audited missing-log errors as known historical
gaps. Wrong exception, wrong path, other source frame, skip, unexpected failure,
missing test or child-process failure causes rejection. The overall result is
`verified_with_historical_gaps`; `all_tests_passed` remains `false`.

## Reproducible setup and integration

From a checkout with Python >=3.9, `make` and a working C compiler:

```sh
make verify       # no network: verify retained bytes and explicit gaps
make test         # no network: original suites plus packaging tests
make reproduce    # first run downloads/builds pinned Tcl locally
make check        # tests followed by reproduction
```

The [runtime lock](../tools/reproducibility/runtime-lock.json) pins official Tcl
8.6.16, source SHA-256
`91cb8fa61771c63c262efb553059b7c7ad6757afa5857af6265e4b0bdc2a14a5`,
and configure/compiler options. The bootstrap checks the archive before
extraction and verifies source tree, installed tree, executable and exact
version/math smoke test before reuse. It installs only under `.build/`.
[Runtime documentation](../tools/reproducibility/README.md) explains offline
archive reuse and non-relocatable build paths.

**VERIFIED environment:** macOS arm64, Python 3.9.6, Apple clang 21.0.0, make 3.81,
Tcl 8.6.16. **Limitation:** host Python/compiler/OS/system libraries are recorded,
not pinned; portable byte-identical binaries are not claimed. Linux and the
upstream Tcl test suite are **NOT RUN**. The source/hash lock replaces the old
unpinned Nix package lookup for this entry point.

[reproduce.py](milestone1-evidence/reproduce.py) verifies retained inputs,
validates/extracts the original 24-file source bundle, and compiles the unchanged
engine and `plant_bridge.c`. Each child imports the original `run_loop.py`.
[run_loop_with_tcl.py](milestone1-evidence/run_loop_with_tcl.py) replaces only its
exact Nix/Tcl subprocess command with the validated local Tcl executable and
records both commands. No fake Nix executable is supplied. Sensor generation,
actuator decoding, coupling, counter delivery and flight computations are reused
unchanged. User Tcl/library environment overrides are removed for the plant.
The original Phase 6 analyzer produces categories and causal summaries.

Output directories must be new and outside retained evidence; failures preserve
their records. Timed-out reproduction command groups are terminated. Generated
sources, binaries and full raw captures stay under ignored `.build/`; dated
retained records refer to existing raw captures only after exact comparison.

## Actual validation

| Check | Actual result |
|---|---|
| Retained baseline | 307 byte matches, 29 explicit historical gaps, zero new missing files or changes |
| Original suites | 38 run: 35 passed, 3 actual errors; all three classified only as known historical gaps |
| New tests | 55 run, 55 passed: evidence tampering/recovery, strict error policy, runtime integrity, adapter/archives/output safety and failure records |
| Local dependency build | Official locked Tcl source built successfully; exact version and required math verified |
| Fresh connected/disconnected/replay | All three commands exit 0; original causal checks pass; every raw trace matches Phase 6 exactly |

Connected: peak synthetic yaw `4.859385265209125°/s`, final X-gimbal
`16.84156247751019°`, final CDU X `1533`, 1539 generated/delivered sensor requests.
Disconnected: peak yaw `11.341167317374987°/s`, final CDU `[0,0,0]`, 16173 generated
and zero delivered requests. Replay is byte-identical. Accepted requests are not
asserted to equal settled counter applications.

Retained commands, versions, source/input/binary hashes, tests and raw references:

- [Test results](milestone1-evidence/runs/2026-10-17-final-tests/results.json)
- [Runtime build records](milestone1-evidence/runs/2026-10-17-runtime/)
- [Fresh demo completion](milestone1-evidence/runs/2026-10-17-verified-demo/completion.json)
- [Raw comparison](milestone1-evidence/runs/2026-10-17-verified-demo/retained-trace-comparison.json)
- [Derived demonstration summary](milestone1-evidence/runs/2026-10-17-verified-demo/SUMMARY.md)

One preliminary packaging test failed because its temporary path expectation did
not resolve macOS `/var` aliases. The test expectation was corrected; the failure
is retained in [initial-test-failure](milestone1-evidence/runs/2026-10-17-initial-test-failure/).
It was not a flight-software or model failure. Tcl build warnings remain in their
original output; no warning-free build claim is made.

**ASSUMED physical fidelity:** synthetic LM-7 constants, zero initial attitude,
yaw/X-CDU only, semi-implicit integration, maximum 853-call (~10 ms) coupling and
undrained counter queues. **NOT RUN:** general multi-axis control, new startup
or signed-CDU experiments, coupled WASM, throttle/radar, powered descent or
landing. Source/rope authenticity limits from the audit remain unchanged.
