# Phase 12 regression evidence

These unchanged earlier suites produced **376 passes, 0 failing assertions,
3 known historical missing-evidence errors, and 0 skips**. This count excludes
the separately retained fresh Phase 11 gate (29 passes) and new Phase 12 tests.

| Actual command | Actual result |
|---|---|
| `make check` | 210 passes, three original missing-log errors; existing gap-aware runner exit 0 |
| Unchanged staged Phase 10 `run_tests.py --output <fresh-directory>` | 57 passes: Phase 8 10, Phase 9 19, native Phase 10 14, math 14 |
| `make test-live NODE=<bundled-node-path>` | 66 passes: backend 32, replay data 12, Node 22 |
| `python3 -B -m unittest discover -s docs/live-control-evidence -p 'test_*.py' -v` | 9 passes |
| `python3 -B -m unittest discover -s frontend/tests -p test_guidance_data.py -v` | 14 passes |
| `python3 -B -m unittest discover -s tools/demo/tests -v` | 6 passes |
| `node --test frontend/tests/guidance.test.mjs` | 14 passes |

`commands.json` and individual command records retain exact argv, cwd, UTC
start/end and exits. Raw stdout/stderr accompany every top-level command.
`make-check-suites/` contains unchanged child test records and their real
tracebacks; `phase10-focused-tests/` contains the four original child commands
and outputs. No original assertions or historical files were changed.

The errors are the original Phase 4, 5 and 6 preservation tests encountering
missing `docs/phase3-evidence/build.log`. They remain errors, not recovered logs
or passes. The first sandbox `make test-live` attempt had 21 passes and 11
local socket-bind PermissionErrors. After requesting loopback permission, the
identical complete command passed. Both attempts are retained; the final count
counts each test once using the completed rerun.

`make check` also rebuilt and executed earlier native demonstrations, including
Phase 7 capability C: independent yaw and pitch plus simultaneous two-axis
response, causal controls and exact repeats. `phase7-fresh-native/` retains
its original summaries, source hashes and commands; the full integration
summary is losslessly compressed with gzip timestamp zero.

Additional integrity commands all exited zero: `make demo-verify`,
`python3 -B docs/phase10_5-evidence/retain_native.py --check`, and
`python3 -B docs/phase10_5-evidence/check_integrity.py`. These checks are not
additional test passes.

The unrelated native HTTP watchdog-neutralization validator was NOT RUN.
Tests used the preserved application in the backend worktree; the separate
frontend branch/worktree was not edited or tested.
