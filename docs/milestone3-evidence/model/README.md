The source-locked adapter corrects the modern external model's **yaw/X** slow/fast selector. It leaves Luminary, the emulator, every upstream source file, and all earlier evidence unchanged. This is a single-axis correction; pitch and roll selectors are not validated or repaired.

`fix_selector.py` reads the complete original `AGC_IMU.tcl`, requires SHA-256 `4f63cf0954d4587ec6e983428d7e43d4473c11da72210444c2aa0ae4204e9c7e`, and replaces exactly one line:

```diff
-     if {$Omega_Yaw < 4} {
+     if {abs($Omega_Yaw) < 4} {
```

The correction preserves the original 4 degree/second threshold. Both signs now select FAST at magnitude 4 and above. Direction still comes from the signed gimbal-angle residual, independent of rate sign. Quantization, angular transforms, integration, wraparound, zeroing, gimbal lock, engine timing, and original software readiness checks retain their previous implementation.

The generated file additionally appends an explicit axis boundary. It renames the original corrected procedure to `::milestone3_yaw::upstream_modify_gimbal_angle` and exposes `modify_gimbal_angle {dx dy dz}` as a wrapper. That public wrapper rejects nonzero `dy` or `dz` before invoking the original body, including when zeroing or gimbal lock would otherwise cause an early return. The internal procedure is retained for provenance, not a supported integration interface. Call only the public procedure. No other-axis numerical behavior is claimed.

For another validation harness, import `apply_selector(source, destination)` from this directory. `source` may be the original module or the extracted source root. `destination` must be a new file in `.build` or external scratch. The function writes the derived module and returns an audit dictionary containing exact source, selector-only, bounded-module and guard hashes, original line 527, and both the one-line selector diff and complete diff. Persist that returned audit. Source the derived file once in a fresh Tcl process after the original model setup; subsequent calls use its guarded public procedure. No original file is rewritten.

The equivalent command-line interface is:

```sh
python3 -B docs/milestone3-evidence/model/fix_selector.py \
  --source .build/milestone3/pinned-source \
  --destination .build/milestone3/new-model/AGC_IMU.corrected-yaw.tcl \
  --audit .build/milestone3/new-model/selector-audit.json
```

The paired component validation reuses Milestone 2's original scenario generator, Tcl probe, trace parser, and summary code. A single audited source-loading line lets the corrected probe source the derived module. No vehicle, transform or quantizer algorithm is copied. Tcl 8.6.16 is validated against the retained source/install manifest before execution.

**VERIFIED:** the first fresh run executed all 24 original and 24 corrected scenarios, with 1,014 raw state rows per model, plus four unsupported-axis controls. Original output matches the retained Milestone 2 bytes exactly. Corrected output has identical numerical states, pulse counts and directions in every row; precisely 1,455 operation modes change from slow to FAST at negative rates of magnitude at least 4. The paired cases include +/-3.999, +/-4, +/-4.001 and +/-8 degrees/second; signed quantization boundaries; a delta opposite to rate sign; angle wraps; and existing zeroing/lock inhibits. The four guard controls reject Y/Z before changing any gimbal, fed angle or captured packet list.

| Imposed rate | Original operation / pulses | Corrected operation / pulses |
| --- | --- | --- |
| -3.999 degrees/second | MCDU / 363 | MCDU / 363 |
| -4 degrees/second | MCDU / 363 | MCDU_FAST / 363 |
| -4.001 degrees/second | MCDU / 364 | MCDU_FAST / 364 |
| -8 degrees/second | MCDU / 727 | MCDU_FAST / 727 |
| +8 degrees/second | PCDU_FAST / 727 | PCDU_FAST / 727 |

These rate cases retain the previous 100 steps of `853 * 11.72` microseconds: 0.999716 seconds. The 11.72 microseconds is the retained wrapper's rounded convention; the engine's exact CPU-call convention is 11.71875 microseconds. This component diagnostic imposes motion and records requested operations. It does not execute AGC control or measure counter application or FIFO settlement; the separate feedback experiment addresses those questions.

The complete actual command records, stdout/stderr, inputs, paired JSONL, source excerpts, generated source, diffs, hashes and validation are retained in `results/`, without native binaries. All three Tcl processes exited 0 with empty stderr. Fourteen Python tests pass without Tcl, network access or a build. They check source/output guards, exact patch scope, captured real-process evidence, paired reconciliation, signed thresholds and adversarial trace mutations. The first test run had one assertion failure because macOS `/var/...` and canonical `/private/var/...` were compared without resolving the expected path; that test-only fix and actual rerun are recorded in `test-attempts/`. No model result was altered to pass a test.

From the repository root, reproduce into new scratch after preparing the pinned source and locked runtime:

```sh
python3 -B docs/milestone3-evidence/model/run_validation.py \
  --source .build/milestone3/pinned-source \
  --tcl .build/reproducibility/runtime/bin/tclsh8.6 \
  --output .build/milestone3/new-model-validation
python3 -B -m unittest discover -s docs/milestone3-evidence/model -p 'test_*.py' -v
```

An explicit `--runtime-manifest PATH` is supported. Otherwise the runner uses the runtime cache's canonical `runtime-manifest.json` beside the `runtime/` installation.

Another axis, Phase 7, general vehicle fidelity, physical IMU hardware validation, powered descent, and landing remain **NOT RUN** here.
