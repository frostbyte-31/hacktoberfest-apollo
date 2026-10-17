# Backend Phase 12 — authentic DPS interface and bounded propulsion

**COMPLETE AND VERIFIED for the bounded SYNTHETIC propulsion/PIPA/navigation
interface experiment.** Original engine commands cause modeled thrust and
motion; force-derived PIPA input changes original navigation and subsequent
original throttle execution. The connected repeat is byte-identical.

Historical engine calibration, a physically achieved burn attitude and complete
powered descent remain **UNRESOLVED / NOT DEMONSTRATED**. This is a fixed-attitude
diagnostic experiment, not an Apollo 11 flight reconstruction or a landing.

## Baseline and Phase 11 acceptance gate

Work starts from `codex/backend-phase11`, commit
`82499e64b5d85259ca54ebe06e6de896504f50f0`, in the isolated branch
`codex/backend-phase12`. Earlier reports were checked against source and fresh
execution, rather than accepted from test totals alone.

**VERIFIED:** the mandatory Phase 11 gate reached **Level 4**: genuine hardware
counter delivery, original counter updates, original navigation consumption and
corresponding state changes. Five fresh runs matched all five retained raw
trace digests. Positive/negative stable-member X inputs delivered and consumed
±600 pulses; matched original navigation epochs differed from zero by
±6.00004196167 m/s and ±30 m. Disconnected feedback matched zero navigation.
The source-supported `READACCS/PIPASR/SERVICER/CALCRVG/CALCN83` path and
independent arithmetic passed. The gate's 13 sensor and 16 native tests passed.
Phase 11 did not independently demonstrate later landing-guidance use.

**VERIFIED:** a fresh unchanged Phase 10 run matched its canonical raw SHA256
`6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2`.
Fresh Phase 7 regression retained capability C: independent yaw/pitch and
bounded simultaneous two-axis feedback; general three-axis fidelity is not
inferred. Gate details: [preflight/phase11-gate.json](phase12-evidence/preflight/phase11-gate.json).

## Original artifacts and environment

| Artifact | Verified identity |
|---|---|
| Virtual AGC revision | `f577e3fd917866c59334e6cdd32504f09df76f60` |
| Source archive SHA256 | `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267` |
| Luminary 099 rope SHA256 | `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e` |
| Original engine source SHA256 | `9c59728cdd968503caaaafe50a18ab3ed841f6176da3299c137f3a6a158fcbef` |
| Assembled listing SHA256 | `d5547c4db630c444004be99556a34e612954eed0b3f27bac4bbe318ad8fbc108` |
| Assembled symbols SHA256 | `16ee199168beb4105f94bf8c0e61ccc2429914e73c1f6d731b1f214b81eeb40b` |

Native execution uses the pinned engine's ringbuffer interface, one machine
cycle at a time inside the retained observer. One MCT is 12/1,024,000 seconds.
Host sockets or wall-clock pacing do not govern the experiment. Fresh source
preparation checks all 359 selected original files; the reused plant bundle
checks all 24 files. Build metadata fixes `SOURCE_DATE_EPOCH=1792195200` solely
for the retained assembler banner, not the mission clock. The actual platform,
compiler commands, Python and locked Tcl hashes are retained under
`phase12-evidence/validation/` and each capture's `source-integrity/`.

No original Apollo instruction or emulator instruction implementation changed.
Read-only observations identify native instruction addresses and original
interpreter dispatch through `NEWOPS/LOC/BANKSET`; observing an interpreted
routine does not redirect its program counter.

## Hardware interface

All addresses and masks in this table are **octal**. Pulse counts are signed
ones-complement quantities, not normalized absolute throttle percentages.

| Interface | Meaning and original source |
|---|---|
| Channel `011`, mask `010000` | ENGINE ON, original `IGNITION` in `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:395–474` |
| Channel `011`, mask `020000` | ENGINE OFF; `P40-P47.agc` `ENGINOF3` and normal shutdown |
| Channel `014`, mask `000010` | THRUST drive level gate |
| Erasable `0055` (`THRUST`) | Signed incremental automatic-throttle pulse count |
| Counter packet channel `0255`, operation 4 | Genuine emulator `DINC`; original `CounterDINC` returns `015` POUT, `016` MOUT or `017` ZOUT |
| Channel `030`, masks `000004/000020/001000` | Active-low engine armed, auto throttle, PGNCS control |
| Channel `031`, mask `020000` | Active-low automatic attitude mode |
| Channel `033`, mask `000040` | Active-low landing-radar antenna position 1; no radar measurement is supplied |

The pinned emulator implements signed DINC and its output packets but does
not provide the external throttle-drive clock. The adapter supplies its
documented **3,200 Hz** request train (ceil(n×80/3) MCT), only while the real
drive gate is set. Each request traverses the original packet/counter handler;
the adapter never fabricates POUT/MOUT/ZOUT. The original hardware specifies
that a genuine ZOUT also clears channel `014` bit 4. The small external bridge
implements that missing device completion as a distinct
`hardware_latch_clear` event, changing only that channel latch after genuine
ZOUT. It emits no invented AGC output and writes no navigation or readiness
memory. A software gate clear stops a pending train immediately.

Primary support: [AGC Interface Specification, Block II](https://www.ibiblio.org/apollo/Documents/agcis_30_block_ii_agc.pdf),
§§30-103/104, printed page 30-67. The exact page and source provenance/hash are
retained in `phase12-evidence/source/`. Source details and historical-reference
limits are in [source-engine.md](phase12-evidence/source-engine.md),
[source-procedure.md](phase12-evidence/source-procedure.md) and
[mapping.json](phase12-evidence/mapping.json).

`ENGINOF3`'s −4096 reset is separate from ON, ignition and thrust. `FLATOUT`
requests +4096; later original `THROTTLE` calculates incremental demand from
guidance force `FC`, measured force `FP` and correction `PIF`. Original
`SCALEFAC` represents nominal 0.0797959872 pulse/N. Immutable `FMAXPOS=3467`
and `FMAXODD=3841` are distinct original force limits, not missing padloads.
`LOWCRIT/HIGHCRIT` are erasable hysteresis padloads; their untouched zero
values in this diagnostic fixture remain **UNRESOLVED** for flight calibration.

## Startup and crew sequence

The Phase 5 startup, original Phase 9 P51 synthetic alignment and original
Phase 10 P27 input driver are reused from the sealed baseline, preserving all
old integrity checks. No restored core, forced flag, navigation-memory setter
or PC injection is used. New normal crew actions are recorded individually:

1. After the original P27 sequence, `V48E`; at V01N46 use `V21N46E20000E`
   to select the documented undocked descent configuration. `V33E` opens N47.
   `V21N47E+33069E`, then `V33E`, lets original R03 bounds/conversion establish
   DP `MASS=15000 kg` and `LEMMASS=3750` (SP B16 kg). At N48, `V34E`
   terminates without a trim maneuver. The entered five-digit pounds are a
   synthetic mass choice, not historical Apollo 11 vehicle data.
2. `V37E63E`; require actual V06N61 and original reference readiness.
3. `V33E`; wait for complete R51 V50N25 checklist **00014**, then ENTER.
4. At R60 V50N18, ENTER accepts the attitude review. This is explicitly a
   **crew assertion**; the fixture does not execute or prove the burn maneuver.
5. Set only documented external switches via real input packets: PGNCS,
   AUTO attitude, engine armed, AUTO THROTTLE and antenna position 1.
6. Original `P40AUTO/MIDTOAV1` and the source's current-time integration
   fallback handle preignition. At actual V99N62, use `V33E` to authorize
   original scheduled ignition.
7. Execute a bounded 3,000,000 further MCT after that key sequence. Observe
   original `IGNITION`, `P63ZOOM`, `FLATOUT`, navigation and throttle control.
8. Request normal P00 with `V37E00E`; observe actual ENGINE OFF and the
   partial reset. A separately logged hardware DISARM then clears only the
   external physical DECA accumulator. Stop; no P64/P66 or landing is attempted.

Original 01703 is retained when the synthetic timing provides insufficient
integration allowance: original `NOTIME/ENTMID2` changes the integration target
and the original master ignition routine recomputes TIG from PIPTIME1+29.9 s.
The `MIDTOAV2` entry itself is not reached in these captures; the shared fallback
is. The driver does not change time or suppress the alarm.

## Physics and frames

**INITIALIZED SYNTHETIC INPUTS:** the unchanged Phase 10 15 km candidate at
epoch 120.00 s uses Moon-centered basic-REF position
`[1538481, 0, −840476] m`, velocity
`[801.7522215843201, 0, 1467.5976037979126] m/s`, lunar μ
`4.902778e12 m³/s²` and reference radius 1,738,090 m. These are encoded P27
readbacks, not measured historical flight data. The external physical state is
coasted from that epoch to the current observed AGC clock with zero thrust.
No external propagation result overwrites AGC navigation.

**ASSUMED PHYSICAL MODEL:** 15,000 kg total initial mass, 6,804 kg synthetic
dry mass and 8,196 kg propellant. The adapter calls the whole unchanged pinned
LM simulator `dynamic_simulation` procedure for F/m, body +X delta-v and fuel
flow. Its LM-7 defaults are minimum 4,560 N, maximum 45,040 N, effective
exhaust velocity 3,050 m/s. These are not exact LM-5 flight calibration; in
particular they differ from Luminary's nominal DPSVEX magnitude 2,955.88868 m/s.
The external DECA accumulator saturates at 3,428 counts, with the documented
nominal pulse/N conversion applied as a synthetic plant approximation. OFF
stops thrust without silently resetting the armed accumulator; DISARM resets it.

The existing Phase 7 quaternion matrix rotates body +X thrust into basic REF.
Zero measured CDUs make body-to-stable-member identity in this fixed fixture.
Actual AGC-computed REFSMMAT maps REF to stable member; its normalized transpose
provides the fixed body-to-REF quaternion. RCS/attitude motion is disconnected
and unsupported rotation is rejected. This does not assume thrust is vertical.

The missing translational state uses transparent 3D velocity-Verlet integration:

```
g(r) = −μ r / |r|³
f_REF = Q_body→REF [F/m, 0, 0]
r_next = r + v dt + ½ [g(r) + f_REF] dt²
v_next = v + ½ [g(r) + g(r_next)] dt + f_REF dt
mass_flow = F / 3050;  m_next = m − mass_flow dt
specific_force = total_acceleration − gravity
```

Preburn mass and thrust are frozen within each ≤10 ms interval as in the
existing engine; native coupling is actually ≤426 MCT (4.9921875 ms), split
at genuine actuator events. Gravity is evaluated at both endpoints. Engine
response is instantaneous; ignition transients, lag, thermal/pressure systems,
gimbal trim and propellant exhaustion are outside the model. No new guidance,
attitude controller or competing frontend physics is introduced.

The unchanged Phase 11 sensor transforms REF specific force into stable-member
coordinates, accumulates delta-v and retains fractional residuals at **0.01 m/s
per pulse**. It emits real PINC/MINC counter requests for `0037/0040/0041`.
Requests generated within a chunk are delivered at its end, at most 426 MCT
late; original counter servicing adds the separately measured queue latency.
Free fall generates no ideal PIPA pulses. Navigation includes original lunar
gravity independently of this physical-model validation calculation.

## Experiment controls and validation boundaries

| Case | Original engine commands | Physical engine | Physical PIPA to AGC |
|---|---|---|---|
| `sink` | Captured/decoded | Disconnected; gravity-only trajectory | No pulses |
| `connected` | Captured/decoded | Connected | Connected |
| `no-feedback` | Captured/decoded | Connected | Disconnected; physical measurements still recorded |
| `repeat` | Same as connected | Connected | Connected |

Modern engine unit tests use clearly synthetic commands to validate only
physics/receiver behavior. Native tests separately require original source,
original instruction checkpoints, actual counter packets, actual physical
measurements and matched navigation epochs. Independent calculations verify
original `MUNRVG` velocity/position arithmetic and the pulse-plus-gravity budget;
they never supply an answer to executing flight software.

In source, `SERVICER.agc:257–278` clears `STEERSW` until measured `ABDELV`
exceeds P63 `DVTHRUSH=36` counts (about 0.18 m/s² at the nominal two-second
period). Without physical PIPAs, `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:809–832`
returns through `RATESTOP` before `THROTTLE`. This genuine software gate is
preserved; the experiment must demonstrate its causal effect instead of
setting STEERSW itself.

## Final execution results

The fresh portable validator completed all four cases, **33 native checks per
case and 13 causal comparisons**, with frozen adapter hashes unchanged. Full
measurements are in [validation/analysis.json](phase12-evidence/validation/analysis.json)
and compact derived accounting in [results.json](phase12-evidence/results.json).

**VERIFIED original execution:** all cases emit ENGINE ON at MCT **25,169,081**,
native context `36,2436` (octal), genuine channel `011` value `10400`. Original
`IGNITION` executes once; `P63ZOOM/FLATOUT` execute once about 26.0 s later,
with FLATOUT at MCT 27,387,427. This proves a software ignition command; the
physical engine's instantaneous response is the separate synthetic model.

The sink and no-feedback controls each produce 4,096 genuine positive FLATOUT
pulses over 1.2796875 s. Connected feedback executes original `THROTTLE`
after 2,941 of those pulses, overwriting the running counter with an authentic
+7,199 request. Later requests are +4,096. The original initial load does not
prove delivery of 4,096 uninterrupted pulses in the connected case.

| Whole bounded run, including normal shutdown | Sink | Engine, no PIPA feedback | Engine + PIPA |
|---|---:|---:|---:|
| Original paired `MUNRVG/MUNRETRN` cycles | 32 | 32 | 32 |
| Original `LUNLAND` / `THROTTLE` calls | 4 / 0 | 4 / 0 | 4 / 4 |
| Physical X PIPA pulses generated | 0 | 3,296 | 3,301 |
| X pulses actually delivered / consumed | 0 / 0 | 0 / 0 | 3,301 / 3,101 |
| X counts remaining at bounded stop | 0 | 0 | 200 |
| Genuine throttle POUT / MOUT / ZOUT | 4,096 / 4,162 / 3 | 4,096 / 4,162 / 3 | 21,656 / 4,162 / 5 |
| Final modeled mass, kg | 15,000 | 14,838.727833 | 14,838.513939 |

PIPA accounting balances exactly; the final 200 counts remain observed counter
contents after P00. Maximum sensor coupling delay was **425 MCT** and original
counter-service delay ≤2 MCT. Throttle clock phase error was ≤1/3 MCT and its
counter-service delay ≤3 MCT. Each genuine ZOUT has one separately recorded
hardware completion clearing only channel `014` bit 4.

**VERIFIED physical response:** at comparison cycle 27,875,065, **31.71075 s**
after ENGINE ON, connected versus sink basic-REF position differs by
`[189.926485738, −0.001767118, −0.010459347] m`; velocity differs by
`[23.793461734, −0.000221378, −0.001345121] m/s`. Connected mass is
14,883.451030 kg, a modeled consumption of 116.548970 kg. Delivered force is
45,040 N and body specific acceleration about 3.02618 m/s². Thrust points
approximately along REF +X, not a screen-defined vertical. Logged F/m, mass
flow, gravity, transformations and integration all satisfy retained tolerances.
These are external physics results, distinct from original navigation.

**VERIFIED original navigation:** at matched original PIPTIME 327.05 s,
connected minus disconnected stable-member velocity is
`[31.012916565, 0, −0.001621246] m/s` and position is
`[256, 0, −0.0625] m`. Independent quantized pulse contribution is
31.010001473 m/s; original gravity contributes +0.003242493 m/s in X. The
residual −0.000327401 m/s is within the conservative accumulated 0.024414063
m/s DP rounding budget. Per-cycle MUNRVG arithmetic error is at most
0.000043517 m/s and 0.0310593 m; original periods remain two seconds.
No-feedback navigation words match the sink exactly despite physical motion.

**VERIFIED bounded causal loop:** engine → specific force → PIPA counters →
original lunar navigation → measured-force/STEERSW gate → changed original
throttle execution/output. The physical receiver saturates at maximum thrust
in both connected-engine cases. This does not prove a calibrated throttle
policy or trajectory regulation. The fourth throttle call occurs during the
ordinary crew-input interval before P00 finishes, after the comparison instant.

**VERIFIED shutdown:** original P00 writes ENGINE OFF and requests −4,096;
original `STARTSB2` at `05,3206` clears throttle drive after only 17 MOUT.
Original THRUST remains **−4,079**. External DECA remains 3,411 with zero
thrust/flow until a separately logged crew DISARM resets it to zero. No adapter
forces internal settlement. Final FAILREG retains inherited startup **01520**,
observed **01703**, and zero. P64/P66, radar measurements and landing are NOT RUN.

| Case | Raw trace SHA256 |
|---|---|
| Sink | `34fefc6bd8963de1f96cf42a9d1ad3e3bde6bbb7389d59b924b4306d9baadaa2` |
| Connected | `8fcc5ecb31bcf8c0158f71657c04dd1cbb8eca1455bae5d3db48f37bd6d37b53` |
| No feedback | `39f5783d0b37e80a1916e6bcb49b9050eb90beaa0e308d9a54e95761a699e74f` |
| Connected repeat | `8fcc5ecb31bcf8c0158f71657c04dd1cbb8eca1455bae5d3db48f37bd6d37b53` |

The repeat matches the complete raw trace, including all recorded intermediate
state, not just selected telemetry.

## Actual tests

**444 passed, 0 assertion failures, 3 historical missing-evidence errors,
0 skipped** across disjoint final suites. The actual fresh command was:

```sh
python3 -B docs/phase12-evidence/validate.py --archive /Users/ggtrinkalipu/Documents/hacktoberfest-apollo/.build/phase89/virtualagc-f577e3fd.tar.gz --runtime-manifest /Users/ggtrinkalipu/Documents/hacktoberfest-apollo/.build/reproducibility/runtime-manifest.json --output .build/phase12/portable-final
```

Optional absolute paths identify this execution; the portable command below
does not require them. Its native assertions use `python3 -B -m unittest
discover -s docs/phase12-evidence -p test_native.py -v` with
`PHASE12_RUNS=<fresh-runs>`. Model tests use `test_propulsion.py --source
<verified-source> --tcl <locked-executable> --runtime-manifest <manifest> -v`.
`validation/commands.json` retains exact expanded argv and the source preparation.

| Executed group | Pass | Fail | Error | Skip |
|---|---:|---:|---:|---:|
| Fresh Phase 11 gate: sensor + native | 29 | 0 | 0 | 0 |
| Fresh Phase 12 native/causal tests | 16 | 0 | 0 | 0 |
| Phase 12 physical receiver/engine unit tests | 23 | 0 | 0 | 0 |
| `make check` | 210 | 0 | 3 | 0 |
| Unchanged staged Phase 10 `run_tests.py` (Phases 8–10) | 57 | 0 | 0 | 0 |
| `make test-live NODE=<verified-node>` | 66 | 0 | 0 | 0 |
| `python3 -B -m unittest discover -s docs/live-control-evidence -p 'test_*.py' -v` | 9 | 0 | 0 | 0 |
| `python3 -B -m unittest discover -s frontend/tests -p test_guidance_data.py -v` | 14 | 0 | 0 | 0 |
| `python3 -B -m unittest discover -s tools/demo/tests -v` | 6 | 0 | 0 | 0 |
| `node --test frontend/tests/guidance.test.mjs` | 14 | 0 | 0 | 0 |

Raw outputs and exact commands are in `validation/`, `preflight/` and
`regressions/`. The Phase 10 command executes inside the original sealed
baseline with its old assertions intact. The initial HTTP suite hit sandbox
socket-bind PermissionErrors; its identical authorized rerun passed all 66
tests. Both attempts are retained; counts include the completed rerun once.
Additional passing integrity commands are `make demo-verify`,
`python3 -B docs/phase10_5-evidence/retain_native.py --check` and
`python3 -B docs/phase10_5-evidence/check_integrity.py`; these are not extra tests.

`development/` separately preserves earlier diagnostic captures and the failed
new assumption that P00 drains its entire reset. The final test asserts the
source-verified interruption instead. The first fixed/erasable-symbol build
mistake and the model threshold-fixture precision issue are documented as
development problems, not Apollo behavior. No earlier assertion was weakened.

## Reproduction

From this backend checkout, with Python 3.8+, Git, make and a C compiler:

```sh
python3 -B docs/phase12-evidence/validate.py --output .build/phase12/reproduction
```

The output directory must be new. The unchanged preparer downloads the pinned
archive if necessary and verifies it before use. The original runtime bootstrap
establishes/validates locked Tcl. For offline reuse, append `--archive
/absolute/path/to/virtualagc-f577e3fd.tar.gz --runtime-manifest
/absolute/path/to/runtime-manifest.json`; hashes are still mandatory. There
are no required developer-specific paths in the entry point.

```sh
python3 -B -m unittest discover -s docs/phase12-evidence -p test_native.py -v
python3 -B docs/phase12-evidence/retain.py --check
```

The first command checks retained actual native runs; it is distinct from
fresh execution. The second checks the package seal and all decompressed raw
trace fingerprints. Exact executed argv, cwd, environment and outputs are in
`phase12-evidence/validation/commands.json`. Each capture includes source/build
checks, observer maps, the executed adapter source and raw `trace.jsonl.gz`.

## Preservation and remaining work

`prior_hashes.json` fingerprints 6,340 prior tracked files. Existing Phase 10
and 11 seals and the old 4,098-file guard remain unchanged; the latter runs in
the original sealed baseline. `frontend-before.json` records the separate
frontend branch/head/status and 5,607 file digests. Final preservation results
confirm no changes. No existing phase report, evidence, application or
frontend file is part of this implementation's edits.

The existing three historical missing-log errors remain errors: the original
Phase 4, 5 and 6 preservation tests encounter missing
`docs/phase3-evidence/build.log`. Nothing has been regenerated as historical
evidence. The unrelated HTTP native watchdog validator is NOT RUN; its
behavior is unchanged. The separate frontend worktree is preserved, not
revalidated as a newly integrated application.

## Changed files and repository state

Only this new report and `docs/phase12-evidence/` are added. Important executable
files are `run_engine.py`, `driver.py`, `engine_bridge.c`, `propulsion.py`,
`legacy_engine.tcl`, `analyze.py`, `test_native.py`, `test_propulsion.py`,
`validate.py` and `retain.py`. Other additions are source references,
inventories, retained execution/test artifacts and reproduction documentation.
No existing tracked file has a diff; application/frontend code is unchanged.

At completion: branch **codex/backend-phase12**, HEAD
**82499e64b5d85259ca54ebe06e6de896504f50f0**. The report and evidence directory
are untracked, ready for review. Nothing is committed, merged or pushed.
The prior backend branch remains clean at its original commit. Frontend branch
`codex/frontend-mission-control` remains at
`5a689c75d43613f29a49fa32d9bd786437825ee5` with exactly its pre-existing
uncommitted changes. [preservation-final.json](phase12-evidence/preservation-final.json)
records matching branch/head/status, all 5,607 frontend file hashes, all 6,340
prior backend hashes and unchanged 739-file Phase 10/509-file Phase 11 seals.

## Next engineering options

Recommended next experiments, in dependency order:

1. Establish source-supported numerical LOWCRIT/HIGHCRIT padloads and validate
   measured/guidance force scaling against a documented DPS calibration. Keep
   current zero-padload controls as negative fixtures.
2. Establish a physically consistent burn attitude and calibrated alignment,
   then couple the already validated bounded attitude plant to thrust/PIPAs.
   Crew acceptance of V50N18 must remain distinct from measured orientation.
3. Add documented DPS startup/throttle/shutdown response and command constraints
   to the existing plant, then repeat bounded causal navigation/control tests.
   Landing radar and complete descent require further independent validation.

No Phase 13 implementation, frontend feature work, commit, merge or push is
authorized by this milestone.
