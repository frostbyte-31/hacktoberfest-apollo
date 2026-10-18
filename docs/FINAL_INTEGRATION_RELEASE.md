# Final integration release verification

The user authorized final checks, a commit and a push to `hacktoberfest-apollo`.
This release contains the previously verified final application plus new release
evidence. **No application source changes were needed.** The prior 736-file seal
remains byte-identical. No further engineering phase was started.

## Actual fresh results

| Executed group | Passed | Failed | Errored | Skipped |
|---|---:|---:|---:|---:|
| Current `make test-final` | 220 | 0 | 0 | 0 |
| Unchanged original-checkout `make check` | 210 | 0 | 3 | 0 |
| Unchanged staged Phase 10 tests, including Phases 8/9 | 57 | 0 | 0 | 0 |
| Fresh original Phase 12 native/causal + model tests | 39 | 0 | 0 | 0 |
| **Disjoint total** | **526** | **0** | **3** | **0** |

The current application group is 98 backend, 26 frontend Python, 6 demo guard,
9 retained attitude-evidence and 81 Node tests. Exact commands, environment,
stdout/stderr and counts are in `final-integration-release-evidence/`.
The three historical errors remain missing `docs/phase3-evidence/build.log`
preservation evidence, not passing tests. No assertions or integrity guards
were weakened. `make check` exits zero despite recording those three errors;
the actual errors are retained and reported separately.

Strict TypeScript contracts, Python syntax, guidance export, propulsion export,
scientific seals, native MVP retention, frontend preservation and application
source whitespace checks passed. The full staged whitespace command reports
trailing tabular delimiters in retained raw `.stdout` evidence; those original
captured bytes are preserved, with the findings recorded in the new release
directory. Original Phase 10.5 integrity and demo verification commands also
passed unchanged in the original clean backend checkout. New tests exercise
provider wire formats with stubs; real LLM operation is **NOT RUN**.

## Independent execution and preservation

All four newly executed Phase 12 raw streams matched the corresponding sealed
retained streams byte for byte; connected and repeat matched each other:

| Case | Raw bytes | SHA-256 |
|---|---:|---|
| Engine disconnected | 95,246,632 | `34fefc6bd8963de1f96cf42a9d1ad3e3bde6bbb7389d59b924b4306d9baadaa2` |
| Connected | 194,558,720 | `8fcc5ecb31bcf8c0158f71657c04dd1cbb8eca1455bae5d3db48f37bd6d37b53` |
| PIPA disconnected | 104,903,145 | `39f5783d0b37e80a1916e6bcb49b9050eb90beaa0e308d9a54e95761a699e74f` |
| Connected repeat | 194,558,720 | `8fcc5ecb31bcf8c0158f71657c04dd1cbb8eca1455bae5d3db48f37bd6d37b53` |

The earlier native regression group also produced 41 fresh traces matching the
previous sprint checks byte for byte. Original Luminary, emulator semantics and
earlier phase reports/evidence remain unchanged. The Phase 12 collector verified
6,340 prior files and all four original seals. The integration preservation
checker independently verified all 7,348 original backend files in place and
their integration copies, with exactly four previously declared application
updates. No historical evidence is among those updates.

The frontend developer's **5,607 files**, exact inventory, branch, HEAD and
working-tree status remain unchanged on `codex/frontend-mission-control`.
All 79 safe-copy paths were reviewed: 78 still match the initial copy exactly;
the integration checkout's TypeScript configuration intentionally adds the new
live provider/types to its existing compiler input list. Compiler options and
the original frontend worktree were not changed. The initial broad copy-identity
review finding is retained alongside the final scoped review. No old copy
receipt or checksum was rewritten.

Artifact review found no credential-pattern matches, suspicious filenames,
compiled executables, ignored candidate files or files at least 50 MiB. This is
a bounded structural review; raw values are not printed. All application and
evidence modes retain their authentic/recorded/synthetic distinctions.

## Release scope and repository

Release branch: `codex/final-integration`, based on
`22bd3c24c524334973beb6f9b3d168f21ca93e71`. Remote:
`git@github.com:frostbyte-31/hacktoberfest-apollo.git`.
Only this integration branch is authorized for push. `main`,
`codex/backend-phase12` and `codex/frontend-mission-control` are not merged,
reset, rewritten or pushed by this release. The release commit is the commit
containing this report; its exact hash is reported after creation.

Original sprint reports are preserved as historical snapshots, including their
then-accurate uncommitted state. New release captures are kept separately under
`docs/final-integration-release-evidence/` with a new checksum manifest. Exact
post-push ref and clean-tree confirmation is recorded outside the committed
tree, avoiding a self-referential commit hash or another evidence-only commit.

## Capabilities and launch

The application still provides the bounded authentic recorded engine experiment,
live original-AGC attitude controls, recorded original preignition guidance,
shared three-seat educational flight, measured outcomes and labeled fallback
crew. **Full authentic AGC-guided lunar landing remains unverified.** Remote
deployment, real model execution and physical mobile/touch testing remain
unverified. This release does not change those limitations.

From the integrated checkout:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime --port 0
```

Open the printed mission URL. The full demonstration and API instructions are
in `FINAL_INTEGRATION.md` and `FINAL_INTEGRATION_CONTRACT.md`.
