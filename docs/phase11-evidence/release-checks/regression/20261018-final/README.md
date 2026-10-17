# Final Backend Phase 11 regression checks

Executed immediately before the authorized commit/push: **376 passed, 0 failing assertions, 3 known historical missing-evidence errors, 0 skips**. The three original FileNotFoundError results remain visible in `make-check-suites/legacy-and-milestone1`; no historical logs or assertions were replaced.

`commands.json` and per-command files contain exact arguments, directories, timestamps, exits and raw output. `summary.json` gives disjoint suite counts. The original four Phase 8–10 child logs and commands are under `phase10-focused-tests/`; all original `make check` test records are under `make-check-suites/`. Additional checks verify demo startup artifacts and Phase 10.5 package integrity. `phase7-fresh-native/` retains fresh native completion, command, preservation and summary evidence; its summary is losslessly gzip-compressed with a zero timestamp.

The first unchanged `make test-live` attempt hit sandbox loopback socket restrictions (21 pass, 11 PermissionError errors). The complete permission-enabled rerun passed 66 tests. Both attempts are retained separately; the environment restriction is not confused with historical evidence gaps. The native HTTP watchdog validator and separate frontend worktree tests were not run. No prior report, prior evidence, frontend branch, or working source file was modified.

The parent release records preserve fresh Phase 11 native execution and new test results separately; these regression counts do not imply powered descent or later guidance integration.
