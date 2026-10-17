# Phase 11 focused baseline verification

VERIFIED: the unchanged Phase 10 nominal native experiment reproduced before Phase 11 implementation. This is a bounded synthetic pre-ignition numerical-guidance experiment, not engine ignition or powered descent.

## Preserved inputs and execution

- Backend branch base: `5a689c75d43613f29a49fa32d9bd786437825ee5`.
- `python3 -B tools/demo/demo.py verify` exited 0: all 739 sealed Phase 10 files, the original rope, all four canonical raw-trace fingerprints, and the existing exported recorded-replay payload passed their existing integrity checks.
- Used the existing `tools/demo/demo.py:stage_baseline` without changes. It verified/extracted Git baseline `6859637ae8dcb1041db3944489d0f909ed58429f` and copied the sealed Phase 10 package into `.build/phase11/baseline-validation/baseline`. All 4098 original tracked-file guards remained intact. The current application was not copied over the frozen baseline.
- Reused an existing verified setup produced by the unchanged Phase 9 preparer. `run_mission.py` reverified the pinned archive, all 359 selected original source files, assembled listing, symbols and rope before building. Source files were checked again after execution.
- Pinned Virtual AGC revision: `f577e3fd917866c59334e6cdd32504f09df76f60`.
- Upstream archive SHA-256: `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267`.
- Original Luminary rope SHA-256: `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.

## Actual command and result

The full absolute argv, execution directory, timestamps and exit status are captured in `.build/phase11/baseline-validation/phase10-nominal.command.json`. In terms of its verified inputs, the command was:

```sh
python3 -B "$BASELINE/docs/phase10-evidence/run_mission.py" \
  --setup "$VERIFIED_SETUP" \
  --config "$BASELINE/docs/phase10-evidence/configs/mission-15km.json" \
  --output "$BACKEND_WORKTREE/.build/phase11/baseline-validation/nominal"
```

`BASELINE` is the staged directory above. `VERIFIED_SETUP` was the existing setup under the primary checkout's `.build/phase10_5/release-20261018/native/baseline/.build/phase10_5/dependencies/setups/20261017T203617Z-9a3f5310/setup.json`. Its host-specific paths are verified cache references, not required portable paths or new source dependencies. A clean machine can obtain a new valid setup using the existing preparer with `SOURCE_DATE_EPOCH=1792195200`; `tools/demo/demo.py reproduce` performs the complete portable staging/build/validation workflow.

Observed native execution:

- Exit 0; original before/after preservation checks: 4098 files checked, none changed or missing.
- Original selected source after execution: 359 files checked, none changed or missing.
- Original P51 alignment, nine P27 verified input transactions, P63 and its post-R02 continuation observed.
- Nine `ROOTPSRS`, nine `ROOTSTOR_RESULT`, nine `QUADGUID` and one `IGNALGRT` checkpoint observed.
- Final actual DSKY: program 63, verb 06, noun 61.
- Raw native trace SHA-256: `6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2`, byte-identical to the sealed Phase 10 nominal trace.
- Existing Phase 10 `analyze_run` returned `all_pass: true`. Detailed results: `.build/phase11/baseline-validation/nominal-analysis.json`.

This was one fresh native experiment plus existing integrity/analyzer checks. No unit-test pass count is inferred from it. Full focused-regression execution can use the unchanged Phase 10 runner inside this snapshot; the original retained evidence provides its other comparison cases.

## Reuse boundary for Phase 11

The Phase 10 `Driver` subclasses the unchanged Phase 9 driver. `run_alignment.execute(driver)` performs unchanged Phase 5 hardware startup, original P51 and subsequent P63 request. Phase 10 intercepts that request only to perform original P00/P27 DSKY mission-data transactions first. A Phase 11 driver can reuse those classes and extend read-only generated observer addresses/checkpoints plus external counter-event delivery in new Phase 11 files. The retained original harnesses need no edits.

The Phase 10 V06N61 result does not prove that active inertial navigation or PIPA consumption is already scheduled. Source-supported activation and genuine navigation effects require separate Phase 11 evidence.
