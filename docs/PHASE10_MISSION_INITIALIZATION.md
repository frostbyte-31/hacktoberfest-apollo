# Phase 10 — mission initialization and original P63 numerical guidance

**COMPLETE AND VERIFIED for the bounded numerical objective.** Original
Luminary 099 accepts documented mission inputs through its P27 DSKY update
program, constructs nondegenerate time-to-go coefficients, returns nine good
ROOTPSRS solutions, and completes its ignition-time iteration. It stops at
the original V06N61 crew-review display. **Powered descent remains NOT RUN.**

The selected scenario is **SYNTHETIC**. Published Apollo 11 target padloads
are used with a coherent diagnostic lunar orbit, nominal epoch and zero
libration. This is not a recovered Apollo 11 trajectory or calibrated flight
alignment. No original instruction, emulator instruction semantics, readiness
flag or alarm logic was changed.

## Baseline and provenance

Started on clean `main`, HEAD `6859637ae8dcb1041db3944489d0f909ed58429f`,
origin `git@github.com:frostbyte-31/hacktoberfest-apollo.git`. The experiment
uses the existing checkout; it does not assert that the remote was fetched.
All **4098 previously tracked files** were fingerprinted before work and
remain byte-identical, including prior reports, evidence, roadmap and app.
Existing missing historical files remain missing.

| Input | Verified identity |
|---|---|
| Virtual AGC revision | `f577e3fd917866c59334e6cdd32504f09df76f60` |
| Pinned source archive SHA-256 | `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267` |
| Original Luminary rope SHA-256 | `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e` |
| Original listing SHA-256 | `d5547c4db630c444004be99556a34e612954eed0b3f27bac4bbe318ad8fbc108` |
| Listing-derived symbols SHA-256 | `16ee199168beb4105f94bf8c0e61ccc2429914e73c1f6d731b1f214b81eeb40b` |

Each native invocation verifies the archive, selected 359 original source
files, listing, symbols and rope before building. It verifies source files
again afterward. The native ringbuffer engine and retained Phase 5/9 bridge
are reused. Only read-only observation addresses are extended. Host:
macOS 26.6.2 arm64, Python 3.9.6, Apple clang 21.0.0. Exact commands,
environment, generated observer, dependency hashes and build output are
retained per run; host-specific shared libraries are omitted with hashes.

**VERIFIED baseline:** fresh Phase 9 alignment, replay and mark-IRQ disconnect
were run. Original P51 computes REFSMMAT and sets REFSMFLG; P63 passes R02BOTH,
then reaches ROOTPSRS/BADROOT/01406 with the missing-state fixture. Its raw
trace remains exactly
`343419a500fdcf9d548fabdc6eba4805a72490d72161e23153461fa31a3e7128`.
Phase 8's independent invalid-REFSMMAT tests still pass. Phase 7 regressions
and fresh validation confirm its bounded simultaneous yaw/pitch capability C;
they do not establish roll, general flight fidelity or powered descent.

## Root cause and original dependency chain

The defect was missing mission initialization, including navigation, landing
geometry and target padloads. It was not an alarm to disable. The Phase 9
fixture leaves the four coefficients zero; a zero polynomial and zero
derivative do not define a meaningful Newton root problem. Original division
saturation and exhausted iterations lead to authentic 01406.

Original source establishes this chain:

```text
P27 state update -> INTWAKEU/ATOPLEM -> RRECTLEM, VRECTLEM, TETLEM
                                  -> original LEMPREC -> RATT1, VATT1
RLS + TLAND -> original RP-TO-R -> REFSMMAT -> LAND
integration state -> REFSMMAT -> R, V
LAND, R, V, WM, CG -> RGU, VGU
RGU/VGU + braking target padloads -> TTF/8CL -> TABLTTF
ROOTPSRS -> original normal return -> TTF/8 -> QUADGUID/CGCALC
          -> DDUMCALC ignition iteration -> IGNALGRT -> V06N61
```

`RN/VN` are servicer/downlink state, not the permanent direct inputs to the
first preignition integration. They have different scales. Their being zero
alone is insufficient diagnosis. `RLS` and `TLAND` are mission inputs;
`RGU/VGU`, `TABLTTF` and solved `TTF/8` are original computed values.

Exact numbered references are preserved in
[source/DEPENDENCIES.md](phase10-evidence/source/DEPENDENCIES.md):
`THE_LUNAR_LANDING.agc:84–125,141–215`,
`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:238–315,419–471,499–526,647–710,1250–1384`,
`P12.agc:229–251`, `INTEGRATION_INITIALIZATION.agc:1042–1103`, and
`UPDATE_PROGRAM.agc:119–143,251–258,429–457`.

The normalized cubic is constructed by original instructions:

```text
A0 = 3/8 * (RDG_z - RGU_z)
A1 = 3/4 * VGU_z + VDG2TTF
A2 = ADG2TTF
A3 = JDG2TTF
```

The starred target quantities are separately scaled published parameters,
not coefficients supplied to TABLTTF. The original algorithm first clears
TTF/8, then TTFINCR incorporates elapsed time. The first observed guess is
**−664.4 seconds**; it was not supplied by the driver.

## Mission initialization architecture

The exact Phase 5 startup prefix and Phase 9 P51 sighting workflow are reused.
After original alignment, normal `V37E00E` establishes P00. Nine original
P27/V71 transactions enter 73 payload words, with five-digit octal fields,
observed V21N01 load prompts, actual component acceptance, V21N02 verification
and `V33E`. Normal `V37E63E` then requests P63. There is no runtime memory
setter, restored core, forced flag, direct coefficient load or fake output.

For the special state update the documented identifier `77775` means LM in
the lunar sphere. Original INTWAKEU/ATOPLEM clears the identifier, establishes
permanent state and sets its own state flags. Actual permanent R/V/epoch
words are checked against those entered. Generic padload stores are checked
word for word. P27's verification flag changes through original instructions.

| Transaction start, octal ECADR | Payload | Provenance and representation |
|---|---:|---|
| UPSVFLAG `1501` | 15 | Identifier + synthetic R/V/epoch; position m/2^27, velocity (m/cs)/2^5, epoch cs/2^28 |
| TEPHEM `1706` | 3 | Synthetic zero TP cs/2^42; TIMSUBO aliases it |
| 504LM `2012` | 6 | Synthetic zero libration; DP radians |
| RLS `2022` | 6 | Synthetic Moon-fixed site; m/2^27 |
| TLAND `2400` | 2 | Synthetic nominal landing epoch; cs/2^28 |
| RBRFG `2402` | 18 | Published full braking R/V/A target vectors |
| VBRFG* `2424` | 10 | Published starred targets, gain and coordinate-transition times |
| VIGN `2472` | 12 | Published ignition targets and KIGN parameters |
| ZOOMTIME `3422` | 1 | Published `05050` octal, SP 2600 cs = 26 s |

Actual source limits P27 to 20 decimal components, hence 18 payload words,
despite the introductory source comment saying `200` octal. Larger target
regions are split; the original check is preserved.

Every payload word, source symbol, reason, units, scale and provenance is in
[configs/mission-15km.json](phase10-evidence/configs/mission-15km.json).
The original [NASA/Grumman preflight padload](https://www.ibiblio.org/apollo/Documents/Luminary99PadLoads.pdf)
was retained and visually checked. Its SHA is
`e112f47d5c413a1c7385e6422c7dbb12e19f2802fdecb31429828d90cac9ff86`.
The [transcription](phase10-evidence/research/padload-transcription.json)
records addresses, octals, units/scales and scan pages; 23 components pass
independent quantization checks. It excludes a complete mission-computed
state vector. Historical TLAND/RLS are therefore not silently mixed with the
synthetic clock, orbit or spherical reference radius.

## Synthetic state, frames and numerical conventions

**ASSUMED scenario:** a lunar-centered circular orbit 15 km above original
rope radius 1,738,090 m; rope μ = 4.902778e12 m³/s². State epoch is 120 s;
TLAND is 784.4 s. The state starts 0.50 radians behind the site's future
basic-reference +X direction, with +Z travel and zero radial velocity:

```text
r_REF = (1538481.213424, 0, -840476.117472) m
v_REF = (801.752223300, 0, 1467.597600606) m/s
|v|   = 1672.31855365 m/s
RLS_MoonFixed = (-696657.487042, -1592359.564368, 4026.361408) m
```

Declared values are rounded only for this display. Exact encoded values are
in the configuration. Position quantization is 0.5 m; velocity quantization
is approximately 0.00001192 m/s. No modern propagator supplies guidance:
the modern calculation only defines/validates initial inputs; original
LEMPREC propagates them. Original gravity and lunar orientation constants
remain in the rope.

Zero TEPHEM defines synthetic AGC clock zero at midnight 1 July 1969,
consistent with the original epoch definition and 1969–70 constants. Zero
libration is an explicit diagnostic approximation. No historical flight
state is claimed.

Original RP-TO-R maps Moon-fixed RLS by `M(t)^T` into basic reference axes,
with libration here zero. REFSMMAT maps basic reference to stable-member
coordinates. CG then maps stable-member to guidance coordinates; its first
pass is identity, and later rows follow landing radial/cross-track geometry.
`RGU` is site-relative geometry, not directly altitude; norm(position) minus
reference radius supplies the independent altitude check. Screen and body
coordinates play no role.

DP uses two signed 15-bit one's-complement words with radix 2^14; both signed
zeros and mixed-sign pairs are decoded. REFSMMAT/CG physical matrix entries
are twice their stored fractions. R/LAND/RGU use m/2^24, VGU uses (m/cs)/2^10.
For root fraction x, signed TTF seconds are **x × 1310.72**. Full derivations
and native frame comparisons are under [math/](phase10-evidence/math/README.md).

**VERIFIED numerical alignment:** actual Phase 9 REFSMMAT determinant is
1.000000000563 and max orthogonality error 5.96e−8. This is a valid numerical
rotation within quantization, not proof of calibrated physical star geometry.
All calculations consistently use the actual measured matrix.

## Actual original execution results

Canonical evidence is [runs/final-validation/](phase10-evidence/runs/final-validation/analysis.json).
Seven fresh native processes cover Phase 9 final/replay/IRQ disconnect and
Phase 10 final/replay/16 km variant/missing-site control.

| Observation | Actual result |
|---|---|
| P63/R02BOTH | Valid REFSMFLG, original return into P63 |
| First ROOTPSRS entry | CPU call 18,502,150 |
| First normalized A0…A3 | 0.01868770644, 0.01073084399, −0.02664020285, −0.01203429699 |
| First normal root | −1014.61159180 s, 3 iterations, fractional residual 1.748e−9 |
| Whole bounded run | 9 roots, 9 good returns, 9 QUADGUID entries, 3 DDUMCALC iterations |
| Final root | −582.79472168 s |
| Original IGNALGRT | Call 18,880,712; TIG 360.29 s, clock 221.26 s |
| Final horizon | 1,000,000 CPU calls after P63 keys; clock 227.62 s |
| Final display | V06N61; ignition remains 132.67 s in the future |
| Alarm history | Preserved legacy 01520; no new alarm/01406/00220 |

This is the original event-timer/TTF review, awaiting crew input. N61's TTF
field must not be mislabeled TIG. Original later BURNBABY requests integration
at TIG−29.9 s and needs a 20 s allowance; at IGNALGRT the independently
calculated margin is 89.13 s. **That later path was NOT RUN.**

Independent checks find coefficient errors ≤0.75 DP LSB, nonzero derivatives,
`|i*Ai|<1`, maximum normalized residual about 1.56e−7 and maximum relative
residual 7.32e−6. Original return/store continuations are observed, rather
than inferring convergence from alarm disappearance. LAND agrees with the
independent lunar frame at the actual TPIP within 0.525 m; R/RGU/VGU and CG
agree within the documented fixed-point tolerances.

LAND is transported from TLAND to TPIP by original GUILDRET/TTFINCR. An early
comparison against the wrong epoch produced an apparent 3 km discrepancy;
the correct source formula explains it without changing the inputs.

Final/repeat raw JSONL is byte-identical, **4,361,253 bytes**, SHA-256
`6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2`.
The 16 km coherent circular variant changes the first root to
−1015.17764160 s. Removing only RLS preserves three partial good roots before
authentic BADROOT/01406, without IGNALGRT. Nonzero coefficients alone are
therefore not treated as successful initialization.

## Preservation, exploratory failures and package

All original evidence remains intact. New runs preserve full raw JSONL using
lossless deterministic gzip, observers, input configuration, source hashes,
commands and actual results. `retention.json` records both raw and packaged
hashes and explicit host-binary omissions. `checksums.json` covers this report
and the new evidence; `check_integrity.py` also verifies all 4098 prior files.

Earlier Phase 10 attempts are retained separately: protocol-probe-01 failed
before CPU execution on an invalid observer symbol; probe-02 verified P27.
Angle-0.15 runs solved roots but produced past TIG; angle-0.40 runs solved
roots with insufficient comfortable lead for later scheduling. Their traces
were retained and the synthetic starting orbital phase was moved earlier,
without changing clocks/results/flight logic. The exploratory failed
analysis is retained in `attempts/analysis-01.json`: it incorrectly expected
a native checkpoint for an interpretive DDUMGOOD label and zero partial good
roots in the missing-site case. These were observer/analysis assumptions,
not AGC failures or reasons to change flight software.

Read-only observers resolve interpreter push-list quantities through FIXLOC
and captured VAC areas. A CPU-call checkpoint can precede completion of a
multi-cycle instruction; ROOTSTOR+4 and QUADGUID establish completed original
root/iteration stores and good return. Pure interpretive entry labels are
not claimed as native program-counter events.

## Reproduction and actual tests

Commands below are the local executed paths. Use new output directories.
On a fresh checkout first run `python3 -B docs/phase9-evidence/prepare.py
--cache .build/phase10-dependencies`; optionally append `--archive` with the
pinned tarball for offline use. Substitute its returned setup.json path.
It checks all integrity requirements and requires no Nix.

```sh
python3 -B docs/phase10-evidence/validate.py \
  --setup .build/phase9/setup-test/setups/20261017T181903Z-486ff63e/setup.json \
  --output .build/phase10/final-angle050-validation

python3 -B docs/phase10-evidence/run_tests.py \
  --runs .build/phase10/final-angle050-validation \
  --output .build/phase10/final-tests

python3 -B docs/live-control-evidence/run_final_checks.py \
  --node /Users/ggtrinkalipu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  --output .build/phase10/regressions

python3 -B docs/live-control-evidence/run_final_checks.py --contracts-only \
  --node /Users/ggtrinkalipu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  --output .build/phase10/regressions-loopback
```

| Final unique test suites | Passed | Errors |
|---|---:|---:|
| Legacy Phases 2–6 | 35 | 3 |
| Milestones 1/2/3 | 55 / 47 / 34 | 0 |
| Phase 7 | 39 | 0 |
| Backend / frontend Python / frontend Node / live evidence | 32 / 12 / 22 / 9 | 0 |
| Phase 8 / Phase 9 | 10 / 19 | 0 |
| Phase 10 actual-native-evidence / independent arithmetic | 14 / 14 | 0 |
| **Total** | **342** | **3** |

345 tests ran, no assertion failures or skips. The three original errors are
preservation tests encountering the missing historical
`docs/phase3-evidence/build.log`; they remain errors, not passes. Initial
loopback restrictions caused 11 backend socket-bind errors. Their actual
output is retained; the permitted localhost rerun passes all 32 backend
tests. `make check`'s zero exit classifies known historical gaps and does not
mean every old test passed. Fresh Phase 6/Milestone 2/3/Phase 7 native
validations also completed. Exact per-suite records are in
[test-results.json](phase10-evidence/test-results.json) and `runs/`.

To inspect the retained compressed package without native execution:

```sh
python3 -B docs/phase10-evidence/analyze.py \
  --runs docs/phase10-evidence/runs/final-validation \
  --baseline-analysis docs/phase10-evidence/runs/final-validation/phase9-baseline/analysis.json \
  --output .build/phase10/retained-analysis.json
python3 -B docs/phase10-evidence/check_integrity.py
```

## Limits, repository status and next experiments

**VERIFIED:** original numerical progression and causal input dependence in
this coherent synthetic fixture. **ASSUMED:** circular initial orbit, nominal
epoch, zero libration, fixed stable member and published target reuse.
**UNRESOLVED:** physical alignment calibration and completeness for operational
flight. **NOT RUN:** crew continuation, R51/attitude maneuver, MIDTOAV1 timing
execution, BURNBABY, engine ignition/response, PIPA/radar feedback, P64/P66,
powered descent or landing. The original startup 01520 remains disclosed.

New files are this report and `docs/phase10-evidence/`: retained-harness
adapter, input manifests, read-only analysis, focused tests, primary sources,
independent arithmetic and actual run evidence. No prior tracked file was
modified. Branch remains `main`, HEAD remains `6859637ae8dcb1041db3944489d0f909ed58429f`;
new Phase 10 files are uncommitted. Nothing was pushed. Exact file inventory
is in `phase10-evidence/repository-state-after.json`.

Highest-value next experiments, without automatically starting them:

1. Continue the bounded original preignition crew workflow with a physically
   calibrated IMU/attitude fixture and verify R51/R60 and scheduled navigation
   deadlines. Preserve the numerical baseline and its synthetic provenance.
2. Validate timed PIPA/inertial navigation counter input and original
   servicer/state propagation independently, including force-free and known
   acceleration controls. Engine-off preignition success does not validate
   acceleration integration.
3. Trace and bench-test authentic DPS enable/throttle interfaces, mission
   mass/thrust padloads and a minimal documented thrust plant connected to
   that navigation feedback. Integrate landing-radar data after those
   prerequisites; no arbitrary throttle controller or full landing system.
