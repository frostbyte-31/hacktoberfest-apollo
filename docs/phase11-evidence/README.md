# Backend Phase 11 evidence

See [the completion report](../PHASE11_PIPA_NAVIGATION.md). These are synthetic
diagnostic native executions of unchanged Luminary 099, never historical flight
telemetry. Verified achievement: bounded PIPA-to-original-navigation **Level 4**.
Later guidance use, ignition and powered descent are **NOT RUN**.

`runs/verified/` contains five captures from the completed portable validator.
Each `trace.jsonl.gz` decompresses to the exact bytes fingerprinted by its
`trace-sha256.json`. `sensor_plan` records all requested pulse times, force,
gravity, transform and quantization; `input`/`pipa_delivered` record actual
enqueue times; counter `transition` and original routine `checkpoint` records
provide read-only hardware/navigation observations. `observer-map.json` maps
every snapshot word to its original address. No sampled event is interpolated.

`validation/` holds final commands, environment, fresh source preparation,
analysis, source-code freeze, 13 sensor tests, 16 native tests, and the separate
unchanged Phase 10 canonical-hash comparison. Shared-library binaries and large
Git/source build caches are not copied; their source, build commands and hashes
are recorded. Use `validate.py` to rebuild and execute them.

`baseline/` is the pre-implementation Phase 10 reproduction.
`tests/` is the separately captured 376-pass regression run, including its three
real historical missing-evidence errors. `preservation/after.json` verifies all
5531 prior tracked files and all 5607 frontend worktree files, including branch,
status and file inventory. The full starting inventories are the adjacent
`prior_hashes.json` and `frontend-preservation-before.json`.

`investigation/` transparently retains earlier trials:

* `premature-p47`: a driver timing error; original NODOFLAG caused genuine 01520,
  no P47 success. The preliminary Python file was not copied at this stage;
  its recorded hash and actual trace remain, and the final driver is preserved
  independently. No missing old source copy has been fabricated.
* `settled-zero-initial-observer`: successful preliminary zero case before the
  interpreted CALCRVG observer existed.
* `observer-symbol-build-error`: fixed-fixed NEWOPS lacked a `fixedBank` field;
  the new observer build failed before starting the emulator.
* `pre-dispatch-dedup`: all five successful earlier captures, their analysis and
  native-test logs. This observer sampled NEWOPS twice while CPU Z was unchanged.
  Its twenty CALCRVG observations represent ten navigation passes. The final
  observer uses the same entry-edge convention as the retained Phase 9 observer
  and records ten distinct entries. Flight execution was unchanged.

The final `checksums.json` fingerprints this package plus the report and excludes
itself. Nested earlier manifests remain evidence of their narrower inventories.
To verify the seal, hash each repository-relative entry and compare its SHA-256.

Fresh native execution:

```sh
python3 -B docs/phase11-evidence/validate.py --output .build/phase11/new-run
```

Add `--archive /path/to/virtualagc-f577e3fd.tar.gz` for offline preparation.
Recorded-evidence tests:

```sh
python3 -B -m unittest discover -s docs/phase11-evidence -p 'test_*.py' -v
```

Evidence retention, after a successful fresh validation and into new destinations:

```sh
python3 -B docs/phase11-evidence/retain.py --validation .build/phase11/new-run
```

That packaging command intentionally refuses to overwrite `runs/verified/` or
`validation/`. Preserve existing captures and explicitly choose a separate
packaging workspace when collecting another release; native validation itself
only writes new `.build` directories.
