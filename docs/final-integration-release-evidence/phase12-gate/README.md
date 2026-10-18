# Fresh Phase12 release acceptance gate

VERIFIED: the unchanged validator was executed in the clean
`codex/backend-phase12` checkout at
`22bd3c24c524334973beb6f9b3d168f21ca93e71`. It prepared the pinned original
software, revalidated the locked Tcl runtime, and ran the engine-disconnected,
engine/PIPA-connected, PIPA-disconnected, and connected-repeat experiments.

- Native tests: **16 passed**, zero failures, errors, or skips.
- Propulsion model tests: **23 passed**, zero failures, errors, or skips.
- All four fresh raw traces equal the decompressed sealed original traces byte
  for byte. Both connected runs have the same raw SHA-256 fingerprint.
- All **6,340** prior source/evidence files are unchanged.
- The Phase10, Phase11, Phase12, and Phase12 release evidence seals remain intact
  (**739**, **509**, **538**, and **468** files respectively).
- The protected frontend worktree retains all **5,607** file fingerprints and
  the identical branch, HEAD, inventory, and working-tree status.

`launch.json` records the exact command, source checkout, UTC timestamps, and
exit status. `commands.json` records each actual validation subprocess.
`native-tests.stderr` and `model-tests.stderr` contain the complete unittest
output. `analysis.json` contains the actual causal measurements; `release-gate.json`
and `trace-comparison.json` record the independent preservation and trace checks.
`native-metadata/` preserves command, build, execution, and integrity metadata.

The exact fresh native output remains at the `raw_output` location in
`release-gate.json`. Its raw traces are not duplicated here: the retained
compressed streams in `docs/phase12-evidence/runs/verified/` contain the same
verified bytes. This does not replace a fresh execution with replay.

To repeat the native validation from an unchanged Phase12 checkout, supply the
existing verified archive and runtime manifest and a **new** output directory:

```sh
python3 -B docs/phase12-evidence/validate.py \
  --archive "$PINNED_ARCHIVE" \
  --runtime-manifest "$LOCKED_RUNTIME_MANIFEST" \
  --output .build/phase12/final-integration-release
```

The exact archive/manifest paths used for this run appear in `launch.json`.
`collect-command.json` records the subsequent independent checks performed by
the new read-only `collect.py` collector. Older reports and evidence were not
modified, and no Git operation changed a branch, index, commit, or working tree.

These results verify the existing **bounded synthetic fixed-attitude DPS/PIPA
experiment**. They do not establish a calibrated historical descent trajectory,
full powered descent, or a lunar landing.
