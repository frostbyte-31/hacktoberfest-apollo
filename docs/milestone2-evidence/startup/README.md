# Milestone 2: stationary startup validation

**VERIFIED:** the retained cold reset enters an original Luminary restart check with zeroed phase-table pairs, producing `01107`. A DSKY `V36E` performs the original fresh-start path and clears the alarm. Waiting for original `ISSUP` and `STARTDAP` before `V37E00E` reaches `MODREG=0` without further `FAILREG` alarms in the bounded capture. This is a clean **post-V36 interval**, not alarm-free power-on or mission-ready alignment.

The emulator, rope, and flight software are unmodified. This probe extends the retained Phase 5 read-only instrumentation in a new evidence directory. It observes a stationary, zero-angle prerequisite without a vehicle model, CDU increments, RHC commands, or memory patches. The root Milestone 2 investigation owns signed CDU timing separately. This work does not validate another axis or begin Phase 7.

## Offline reproduction

Provide the source directory extracted and hash-checked from `docs/phase6-evidence/corresponding-source.tar.gz`. The runner checks every bundled source hash again before compiling. Only a native C compiler and Python standard library are required; no Nix, Tcl, network, assembler, or downloaded runtime is used by this startup experiment.

```sh
python3 docs/milestone2-evidence/startup/run_validation.py \
  --source .build/reproducibility/runs/milestone1-verified/source \
  --output .build/milestone2-startup/new-reproduction
APOLLO_STARTUP_RUN_DIR=.build/milestone2-startup/new-reproduction \
  python3 -m unittest discover -s docs/milestone2-evidence/startup/tests -v
```

The output must be new and reside under `.build` or external scratch. Existing evidence is never overwritten. The default tests inspect `runs/verified`; the environment variable selects fresh traces. `commands.json` retains each compiler/run command, UTC start/end, and actual exit status. Raw traces contain CPU-call indices and deterministic observations. `initial_conditions.json`, `inputs_source_hashes.json`, `binary_hashes.json`, and `resolved_addresses.json` record provenance.

## Captured results

The final seven fresh native runs completed with exit 0. The delayed capture and its fresh-process replay are byte identical. **13 tests passed**, with the actual output in `runs/verified/tests.stderr`; all twelve integrated behavioral checks passed in `validation.json`.

| Case | Observed result at CPU call 2,200,000 |
| --- | --- |
| Original V37 key timing, with later V77/RHC stimulus omitted | Original `CANTROO` at 1,128,333; `FAILREG=01520`, `MODREG=-0`. |
| Delayed V37, first key at 1,600,000 | Original readiness first observed at 1,480,208; `STARTDAP` at 1,484,077; `MODREG=0` at 1,729,504; all alarm registers zero after V36. |
| Delayed fresh-process replay | Exact raw-byte agreement. |
| No V36 | P00 can be selected, but original `01107` remains recorded. P00 alone does not establish clean initialization. |
| IMU OPERATE inactive | P00 can be selected, but `IMODES33` bit 6 stays set and `STARTDAP` is never reached. P00 alone does not establish DAP readiness. |
| V37 first key at 1,300,000 | `CANTROO` at 1,428,398 and original `01520`. |
| V37 first key at 1,500,000 | P00 accepted, no additional alarm. |

All values in raw JSON are decimal; addresses and alarm codes in this document are octal. `cpu_step(1)` is one pinned engine call: its clock is `12/1024000` seconds (11.71875 microseconds; see bundled `agc_engine.h:204–207`). The prior plant uses a rounded 11.72 microseconds, which is separately labeled in metadata and does not affect this stationary probe. These are schedule-specific observations, not universal minimum wall-clock waits. The positive rule is to observe the original completion path, rather than infer readiness from a time delay or a transient zero register value. In the validated delayed case the source-anchored `ISSUP` checkpoint at 17.3461875 simulated seconds precedes the first V37 key at 18.75 seconds. It also observes `IMODES30` bit 6 clear and then `STARTDAP`. The earlier Phase 5 probe's 1,480,209 call differs by one from this capture because its original premature V37 changes CPU scheduling; neither value is a general startup constant.

## Source and causal evidence

`source/manifest.json` records the pinned Virtual AGC revision `f577e3fd917866c59334e6cdd32504f09df76f60`, exact upstream raw URLs, SHA-256 values, and sizes for three original Luminary source files. Engine sources remain in the retained source bundle and are checked against its original manifest.

- `agc_engine_init.c` in that bundle, lines 260–264, clears erasable memory and selects `Z=04000`. The native process begins with all phase words zero, without harness writes.
- `source/ERASABLE_ASSIGNMENTS.agc` resolves the observed registers independently from original numeric `SETLOC`/`EQUALS` and consecutive `ERASE` declarations. This yields `FAILREG=0375`, phase pairs `0752..0765`, `MODREG=1011`, and `IMODES30/33=1302/1303`. `resolved_addresses.json` records this result.
- `source/FRESH_START_AND_RESTART.agc`, lines 299–310, compares the complemented/direct phase words and requires negative zero. At calls 517–524 the real execution selects pair six (`MPAC+5=5`, doubled index 10), whose words are both positive zero, and reaches `CCS A` with `A=0`. It then enters `PTBAD` (`05,3054`) at 526 and records original `01107` at 553. The exact rope instruction sequences are asserted before running. This establishes this pinned fixture's specific cold-reset behavior and preserves the original diagnostic.
- The same file, lines 47–73, shows requested fresh start and the original alarm-register clearing. After the unchanged V36 key sequence, `FAILREG` becomes all zero at call 491,361. The delayed case remains zero through 2,200,000 (25.78125 simulated seconds).
- The same file, lines 752–774, checks `IMODES30` bit 6 before accepting a V37 and calls original `01520` on rejection. The legacy and early control traces observe this instruction path with `A=32`.
- `source/T4RUPT_PROGRAM.agc`, lines 448–454, clears the original IMU initialization flags and DAP inhibit in `ISSUP`. The probe observes that actual instruction path; no memory value is forced. The retained `docs/phase5-evidence/address_resolution.txt` and `v37_address_resolution.txt` independently identify the ISSUP, STARTDAP, and V37 bank/address mappings. Preflight checks compare the relevant instructions against the actual rope.

The `without_v36` and `imu_off` controls keep initialization, major-mode selection, and DAP readiness distinct. The experiment neither claims a complete IMU alignment nor tests radar/PIPA behavior, DAP gain padloads, descent, fuel, or landing.

## Preserved development attempts

Earlier attempts remain in `runs/attempt-*`, with their raw captures, commands, hashes, and executed harness versions. Attempt 1 established the seven comparisons. Attempt 2 failed a new preflight rope assertion because the newly written assertion had a wrong BIT6 operand address; no CPU run occurred. Attempt 3 corrected that assertion and added full provenance checks. Attempt 4 added integrated validation. Attempt 5 strengthened the register address proof by deriving it from the original `SETLOC` origins. The final version additionally labels the exact engine clock and retained approximation separately. No original phase, audit, or Milestone 1 file was changed, and no missing historical log was reconstructed.
