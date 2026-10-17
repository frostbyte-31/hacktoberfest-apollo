# Backend Phase 11 regression checks

Final executed regression suites: **376 passed, 0 failing assertions, 3 known historical missing-evidence errors, 0 skips**. The three errors remain actual FileNotFoundError results in the original Phase 4, 5 and 6 preservation tests, first encountering `docs/phase3-evidence/build.log`. They have not been replaced, recovered or relabeled as passes.

| Actual command | Result |
|---|---|
| `make check` | 210 passed; 3 known historical errors; existing gap-aware runner exit 0 |
| Unchanged staged Phase 10 `run_tests.py --output <new-directory>` | Phase 8: 10, Phase 9: 19, Phase 10 native: 14, math: 14; 57 passed |
| `make test-live NODE=<verified-node-executable>` | 32 backend Python, 12 replay-data Python, 22 Node; 66 passed |
| `python3 -B -m unittest discover -s docs/live-control-evidence -p 'test_*.py' -v` | 9 passed |
| `python3 -B -m unittest discover -s frontend/tests -p test_guidance_data.py -v` | 14 passed |
| `python3 -B -m unittest discover -s tools/demo/tests -v` | 6 passed |
| `node --test frontend/tests/guidance.test.mjs` | 14 passed |

Each top-level command has its captured argv, cwd, timestamps, exit status and raw stdout/stderr in this directory. `phase10-focused-tests/` contains the original four child commands and raw test output. `make-check-suites/` contains the original per-test records and original error tracebacks from the earlier evidence suites. `summary.json` reports the disjoint counts and actual classifications.

The first `make test-live` attempt could not bind the sandbox's loopback sockets: 21 passed, 11 PermissionError errors; make stopped before its replay/Node groups. Its raw output is retained as `test-live.*`. After requesting the required local-socket permission, the identical complete suite passed; its output is `test-live-escalated.*`. This environment restriction is separate from the three historical evidence errors and is not silently discarded.

Additional checks exited 0: `make demo-verify`, `python3 -B docs/phase10_5-evidence/retain_native.py --check`, and `python3 -B docs/phase10_5-evidence/check_integrity.py`. The latter checked 413 MVP-package files and 4809 prior-evidence files without problems. These are integrity checks, not additional unit-test passes.

`make check` also executed fresh native Phase 6, milestone 2/3 and Phase 7 experiments. The fresh Phase 7 result was capability C: independent yaw and pitch plus simultaneous two-axis control, causal disconnected controls and exact repeat traces; full three-axis control remains unverified. Compact original summaries, commands and source fingerprints are retained in `phase7-fresh-native/`. The original integration summary is losslessly compressed with a fixed gzip timestamp.

The existing native HTTP watchdog-neutralization validator was **NOT RUN** because it is unrelated to these cycle-locked PIPA experiments. No watchdog behavior or assertions were changed. The separate frontend developer worktree was not changed or tested by these commands; these regressions exercise the preserved application on the backend branch.
