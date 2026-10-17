# Phase 9 — original P51 and P63 readiness evidence

**VERIFIED for the synthetic stationary fixture:** two original P51 sightings
populate REFSMMAT and set REFSMFLG. Subsequent normal P63 selection passes R02,
then aborts with `01406` while solving a degenerate time-to-go cubic. No
powered descent, engine/thrust response or landing is demonstrated.

The [report](../PHASE9_IMU_ALIGNMENT.md) distinguishes observed execution,
source-derived explanations and assumptions. Phase 8 remains independently
sealed and does not use this alignment driver.

## Reproduce

Python 3.9+, a C compiler available as `cc`, and `make` are required. No Nix,
browser, Node, system Tcl, restored core or preloaded flight memory is used.

```sh
python3 -B docs/phase9-evidence/prepare.py --cache .build/phase9/dependencies
```

The first invocation fetches the pinned Virtual AGC archive and checks its
SHA-256 before extraction. For offline execution append
`--archive /absolute/path/virtualagc-f577e3fd.tar.gz`. Copy the `setupFile` path
from the printed JSON into the next command:

```sh
python3 -B docs/phase9-evidence/validate.py --setup /absolute/path/to/setup.json
python3 -B -m unittest discover -s docs/phase9-evidence -p test_alignment.py -v
python3 -B docs/phase9-evidence/verify_integrity.py
```

`validate.py` creates fresh `.build/phase9/validation/` output with final,
repeat and disconnected-mark-interrupt runs plus independent analysis. All
359 source files, the rope, listing and listing-derived symbols are checked
again before native execution. It refuses changed cached inputs rather than
repairing them. Both final runs must agree in complete raw trace bytes. Native
execution occurs in separate processes with the pinned ringbuffer backend.

Tests default to the retained runs. To test a fresh batch, provide an
`APOLLO_PHASE9_VALIDATION_CONFIG` JSON file containing absolute `run`, `repeat`
and `negative` directory paths. These tests inspect actual traces and rejection
behavior; `validate.py` performs fresh original flight-software executions.

## Retained results

- `runs/final`, `runs/repeat`, `runs/mark-irq-off`: actual final native traces,
  original packet inputs/outputs, external interrupt assertions, native memory
  transitions, instruction and interpreter readbacks, provenance and summaries.
- `validation/`: executed commands, independent analysis and before/after
  integrity checks. Positive/replay pass 20 checks each; the negative control
  passes 15; two comparisons establish exact replay and causal dependence.
- `runs/development/`: actual failed V24-prompt expectation and successful
  intermediate observer runs. The V24 operation displays V21 then V22 component
  prompts; the early timeout was a driver bug, not a flight-software failure.
- `source/`: 27 exact pinned source files with Git blob and SHA-256 checks,
  mappings, line references and actual read-only findings.
- `setup/`: source/archive verification, original assembly and exact rope
  agreement, actual setup integrity controls and preserved toolchain failure.
- `checks/`: ten Phase 8 and nineteen Phase 9 tests, plus Phase 8 seal check.
- `regression/`: fresh prior-phase native reproductions and complete existing
  test output: 285 passes and three retained historical missing-log errors.

Together the test suites report **314 passes and 3 known historical errors**.
Four separate setup experiments passed (fresh setup, cache reuse, wrong archive
rejection and altered source rejection); they are not counted as unit tests.
Network fetching through the new Python setup entry point itself is **NOT RUN**;
its successful executions used the independently re-fetched, verified archive.

`retention.json` inventories copied and compressed bytes and explicit omissions
of rebuildable binaries/original source extractions. JSONL uses lossless gzip.
No historical missing log or failed attempt was reconstructed. `prior_hashes.json`
freezes 3,393 prior Phase 1–8, live application and tooling files for this work.

## Hardware and scope

Keys use channel `015`. Optical mark words use channel `016`, followed only
after receipt by the documented KEYRUPT2/interrupt6 event. This external bridge
is necessary because neither pinned transport supplies that interrupt. Its
only new AGC-state mutation is the hardware interrupt latch, not flight erasable
memory. Original MARKRUPT samples the actual zero CDU counters and time. The
disabled-interrupt control receives identical mark packets and cannot align.

COAS detent7 and catalog stars01/02 use explicitly synthetic instrument angles.
N87 directions differ between sightings while CDUs remain zero: this is a
numerical line-of-sight fixture, not a model of fixed COAS mounting, optics
mechanics or spacecraft slewing. The fixture is stationary; no physical alignment certification, mission state,
padload, engine plant, radar, PIPA integration or descent physics is supplied.
Original Luminary alone computes the matrix, validity flag and later alarm.
