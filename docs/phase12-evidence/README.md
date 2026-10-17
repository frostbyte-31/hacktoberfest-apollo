# Backend Phase 12 evidence

Start with [the report](../PHASE12_DESCENT_PROPULSION.md). All runs here are new
synthetic diagnostic captures, never historical Apollo mission telemetry.

- `preflight/`: actual Phase 11 Level 4 gate, fresh trace comparisons and
  original Phase 10 regression, captured before Phase 12 implementation.
- `source-engine.md`, `source-procedure.md`, `mapping.json`, `source/`: pinned
  original software mappings, crew paths and primary hardware references.
- `run_engine.py`, `driver.py`, `engine_bridge.c`: original-driver continuation,
  read-only instruction observations and external hardware events. No original
  instruction implementation or guidance algorithm is replaced.
- `propulsion.py`, `legacy_engine.tcl`: bounded actuator/translation adapter
  around the existing pinned physical engine and Phase 7 orientation matrix.
- `validate.py`: fresh source preparation and all four causal native cases,
  independent analysis, 16 native and 23 model tests, source freeze/preservation.
- `analyze.py`, `test_native.py`, `test_propulsion.py`: independent validation
  of actual captures versus separate modern-model unit checks.
- `runs/verified/`: final losslessly compressed raw traces and execution/source
  metadata for sink, connected, disconnected-feedback and identical repeat.
- `validation/`: exact final commands, environment, source preparation, raw
  test output and completion/retention records.
- `regressions/`: unchanged earlier suites, actual errors and fresh Phase 7
  comparisons. See that directory's README for disjoint test accounting.
- `results.json`: compact observations derived from the completed validator;
  full independent arithmetic remains in its analysis.
- `development/`: earlier probes and failed development assumptions, preserved
  separately from the final frozen acceptance runs.
- `prior_hashes.json`, `frontend-before.json`: original protected inventories;
  final preservation results are added separately. No earlier seal is updated.
- `checksums.json`: final package/report seal; verify using `retain.py --check`.

Fresh reproduction uses `python3 -B docs/phase12-evidence/validate.py --output
.build/phase12/reproduction` from the backend checkout. Offline dependency flags
are documented in the report. Retained native assertions use
`python3 -B -m unittest discover -s docs/phase12-evidence -p test_native.py -v`.
These are different activities: an assertion over a retained trace is not a
fresh execution.

Hardware completion (`hardware_latch_clear`) is separately labeled from
genuine AGC output packets. Original software's partial P00 throttle reset and
subsequent physical crew DISARM are separately observable. Modern synthetic
engine tests are not presented as original AGC control tests.
