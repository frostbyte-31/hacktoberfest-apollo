# Authorized Backend Phase 11 release checks

The user requested final checks, commit and push of Backend Phase 11 to
`frostbyte-31/hacktoberfest-apollo`, preserving evidence and leaving the separate
frontend branch untouched. These are additive release records. The original
509-file package and its seal remain unchanged; the completion report's final
"No commit, merge or push was made" sentence describes its initial handoff.
This note records checks performed before the authorized release commit.

Branch: `codex/backend-phase11`; base HEAD:
`5a689c75d43613f29a49fa32d9bd786437825ee5`. The remote `main` still matched that
base when checked. The backend feature branch is the push target. No merge,
frontend work or next-phase implementation is included.

## Actual final results

**405 passed, 0 failing assertions, 3 known historical missing-log errors,
0 skipped.**

* `native/`: fresh source extraction/assembly, five fresh native sensor cases,
  causal analysis, 13 sensor-model tests and 16 native-evidence tests, plus the
  unchanged Phase 10 canonical-trace comparison. All child commands exited 0.
  Each Phase 11 raw trace matches its original retained capture byte-for-byte;
  positive and repeat are also identical. Commands and actual stdout/stderr are
  retained; `retained-trace-comparison.json` records the raw hashes.
* `regression/20261018-final/`: 376 existing tests passed. `make check` reports
  210 passes and three real historical FileNotFoundError errors, with fresh
  Phase 7 capability C native validation. Phase 8–10 focused tests: 57;
  `make test-live`: 66; live evidence: 9; guidance data: 14; demo guards: 6;
  Node guidance: 14. Exact commands, original error tracebacks, summaries and
  integrity checks are retained there.
* The first sandbox-restricted HTTP unit-test attempt had 11 socket-binding
  PermissionErrors. The identical permission-enabled rerun passed. Both attempts
  remain preserved, separate from the three historical evidence errors.

The unrelated native HTTP watchdog validator was NOT RUN and unchanged. The
separate frontend developer branch was preserved rather than tested or modified.
Backend Phase 11 remains a bounded synthetic **Level 4 P47 navigation** result;
Level 5 guidance use, engine ignition and powered descent are NOT RUN.

## Preservation

`preflight.json`, `frontend-before.json` and `preservation-after.json` record the
original package, prior tracked files and frontend file inventory/branch/status.
All 5531 prior tracked files and 5607 frontend worktree files remain unchanged.
Fresh native runs again passed the original 4098-file baseline guard and
359-file pinned-source checks; the Luminary rope hash remains unchanged.

`checksums.json` seals this additive release directory and references the
unchanged original package seal. Raw traces are losslessly compressed; their
decompressed SHA-256 values remain in each capture's `trace-sha256.json`.

For a new native reproduction from the backend worktree:

```sh
python3 -B docs/phase11-evidence/validate.py --output .build/phase11/new-check
```

Add `--archive /path/to/virtualagc-f577e3fd.tar.gz` for offline source preparation.
Every output directory must be new, so existing evidence is never overwritten.
