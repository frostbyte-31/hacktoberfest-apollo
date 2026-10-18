# Final integration evidence

New captures for the Phases 13–16 integration sprint, based on backend commit
`22bd3c24c524334973beb6f9b3d168f21ca93e71`. They are generated diagnostic and
application evidence, not historical Apollo mission telemetry.

The completion report is `../FINAL_INTEGRATION.md`; the implemented v1 API and
execution-mode boundary are in `../FINAL_INTEGRATION_CONTRACT.md`.

| Directory / file | Meaning |
|---|---|
| `baseline-gate/` | Fresh unchanged Phase 12 native execution, raw trace comparisons, 39 tests and a capability-by-capability acceptance gate |
| `prior-regressions/` | 267 old regression passes, three historical missing-log errors, unchanged original integrity checks, fresh bounded attitude traces and read-only code review |
| `final-checks/` | Final current-source test command/output, strict types, export checks, integrity results and disjoint count summary |
| `frontend/` | Real browser actions, desktop/responsive screenshots, actual three-client receipts, live native attitude record and educational debrief |
| `physics/` | Independent physical model checks and actual ballistic/braking/fuel-exhaustion histories |
| `crew-service/` | Two real Tcl-backed deterministic crew flights, raw audits and compared command values |
| `crew-development/` | Mock provider/async tests and initial HEAD-guard defect capture; no real LLM |
| `controller-development/` | The genuinely failed initial modern fallback-controller experiment |
| `launch/` | Actual recorded-only launch, occupied-port protection, owned shutdown and final full-server capability observations |
| `preservation-before.json`, `frontend-integration-copy.json` | Original worktree inventories and safe frontend copy decisions |
| `preservation-after.json`, `preservation-final.json` | Original worktree and integration-byte checks at successive source states |
| `repository-final.json`, `checksums.json` | Final Git/file inventory and SHA-256 fingerprints for new files/application changes |

The canonical test total is **526 passed, zero final assertion failures, three
historical missing-evidence errors, zero skipped**. Earlier and repeated runs
are kept for diagnosis but not added again. `make check` itself exits zero despite
its three recorded preservation errors; see actual suite outputs.

`final-checks/mvp-preservation.stdout` records the old Phase 10.5 whole-package
checker rejecting exactly four authorized application changes. Its manifests
and assertions remain unchanged. The same command passes in the original clean
backend checkout. No historical evidence exception was added to make it pass.
The separate new preservation checker verifies all old evidence and both original
worktrees, allowing only the explicitly listed new application versions in the
integration checkout. Its original-worktree checks require those locally kept
worktrees; they are an audit of this integration environment, not a launcher
dependency on another developer's paths.

## Reproduction

From the integrated checkout:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime --port 0
make test-final NODE=/path/to/node
python3 -B -m backend.propulsion_recording --check
python3 -B docs/final-integration-evidence/check_preservation.py --output /tmp/apollo-preservation.json
python3 -B docs/final-integration-evidence/check_launch.py --output .build/new-launch-check
```

The test target prepares its own verified native assets; it does not require a
manually created `.build/final-demo-assets.json`. Python, compiler/make, the locked
runtime and Node for tests are required. Application launch does not need Node.
The final launcher prints its selected free-port URL, verifies sealed source/data
and disables unavailable capabilities honestly.

Original scientific suites retain their old whole-application checks and run
from the clean original backend or frozen original Phase 10 staging checkout.
The precise commands, dependency paths, clocks, raw/compressed fingerprints and
source revisions are recorded in `baseline-gate/commands.json` and
`prior-regressions/`. No historical logs were regenerated or relabeled recovered.

Browser verification is described in `frontend/README.md`. Responsive layout was
checked in a real 390×844 same-origin iframe in desktop Chrome; physical mobile
hardware, touch and real remote LLM operation were **NOT RUN**. Final polish
receipts supersede earlier screenshots only for the changed explanatory text;
earlier captures remain preserved.

The checksum manifest excludes itself. Scientific retained artifacts remain
covered by their original seals, which the launcher independently verifies.
