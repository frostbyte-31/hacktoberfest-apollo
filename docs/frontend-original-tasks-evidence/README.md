# Campaign original-task verification

Verified 2026-10-19 in the isolated `UI/UX` worktree. This verifies the original-computer task interface and source integration. **The complete Earth–Moon–Earth flight game remains unimplemented.**

## Automated results

| Check | Result | Retained output |
| --- | --- | --- |
| Full backend suite, Python 3.11.8 | 205 passed | `backend-tests.log` |
| Frontend Python suite, Python 3.11.8 | 50 passed | `frontend-tests.log` |
| Final frontend JavaScript suite | 332 passed | `frontend-js-tests.log` |
| Evidence export and module syntax check, default Python 3.14.7 | Passed | `frontend-check.log` |
| TypeScript declarations/provider contract check | Exit 0 | Frontend `tsconfig.json`, existing TypeScript 5.9.3 |
| Normal `make play PORT=4181`, default Python 3.14.7 | Server ready; original CMC available | `startup-python314.log` |

Total: **587 regression tests passed**. `frontend-tests.log` also contains an earlier 331-test JavaScript run; the final 332-test run adds a regression for stopped-computer display classification. Use the final JavaScript log for the final count.

The full backend suite requires its native test manifest. For a fresh test checkout, prepare the verified runtime/assets first:

```sh
make runtime
python3.11 -B -m backend.final_assets
python3.11 -B -m unittest discover -s backend/tests -v
make test-frontend PYTHON=python3.11
make frontend-check
```

The first full-backend attempt encountered three setup errors because `.build/final-demo-assets.json` was absent. Preparing that retained-asset manifest resolved them; the subsequent complete 205-test run passed.

Two existing default-Python startup differences were corrected in read-only display calculations. Python 3.12+ changed floating-point `sum()` behavior. Explicit original arithmetic order now preserves existing guidance and propulsion exports under Python 3.11 and 3.14. Recorded observations, physics, prior evidence and the existing 8-ULP projection validation limit are unchanged.

## Browser results

The application was served on an isolated port 4180, without operating the user's port 4173 instance.

- Manually selected original P52 using the DSKY, selected REFSMMAT option 3, identified octal star codes 30 and 37, slewed the modeled sextant and sent physical MARK inputs.
- Observed original V06N05 R1 `+00001`, then original V06N93 torque-angle review, three original gyro outputs and resulting counter feedback.
- Observed original V50N25 request `00014`, then manually returned to P00. All five service-owned task checkpoints completed; the source/session-bound receipt appeared only then.
- Stopped the CMC. Live qualification and the continuation control disappeared; the completed receipt remained local history.
- Reloaded. The prior result stayed labeled as history. No control inputs were replayed.
- Inspected all 16 chronological chapters. Each displayed its relevant original-source references and correct source/availability classification; `chapters.json` retains the results.
- Inspected unavailable departure. No departure/engine command was exposed. Original P47 alarm 01204 remains an unresolved integration issue, separately retained in `../campaign-original-code-evidence/`.
- Checked a 390×844 mobile viewport, including expanded source code. Document width and viewport width both measured 390 pixels; no horizontal page overflow. Restored the normal viewport afterward.
- Browser error/warning log was empty at the check.

## Screenshots

- `p52-complete.png`: current-run qualified P52, alongside original source.
- `saved-history.png`: stopped execution and retained history after reload.
- `departure-source.png`: original departure-related source, with flight unavailable.
- `mobile-task.png`: task and source layout at 390-pixel width.
- `mobile-3d.png`: retained 3D Earth-parking configuration at mobile width.

These screenshots document the UI and the bounded original P52 instrument fixture. They do not prove historical orbital flight, a lunar landing or a complete mission.

## Preservation checks

`git diff --exit-code` confirmed no changes to prior phase evidence, generated guidance/propulsion recordings, `cmc_alignment.py` or `cmc_native.py`. Original source and emulator instruction behavior were not edited. Main-checkout user presentation files remained untouched.
