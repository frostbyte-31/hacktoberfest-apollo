# Independent Phase 10 arithmetic diagnostics

These files inspect observed AGC words. They do not run the CPU, initialize its
memory, calculate control commands, or replace navigation or ROOTPSRS.

## Reproduce

```sh
python3 -B -m unittest discover -s docs/phase10-evidence/math -p 'test_*.py' -v
python3 -B docs/phase10-evidence/math/diagnostics.py \
  --phase9-trace docs/phase9-evidence/runs/final/trace.jsonl.gz \
  --output .build/phase10-independent-phase9-matrix.json
```

The output argument must name a new file. The retained result is
`phase9-matrix.json`; its trace digest is the digest of uncompressed original
JSONL. The original compressed trace is read only.

## Number representation — VERIFIED

The pinned Virtual AGC source `yaAGC/agc_engine.c:1058–1126` describes DP as two
adjacent signed one's-complement SP words, MSW first, with fourteen magnitude
bits per word. Its `SpToDecent` normalizes unlike signs. An equivalent exact
mathematical value for diagnostics is:

```
signedSP(w) = w                          if sign bit 040000 is clear
            = -(077777 XOR w)            otherwise
DPcount     = signedSP(MSW)*2^14 + signedSP(LSW)
fraction    = DPcount / 2^28
```

Both `00000` and `77777` are zero. A negative-zero LSW must contribute zero,
not the positive magnitude bits `037777`. For example observed matrix element
`20000 77777` is exactly +0.5. This matters for the Phase 9 diagonal entries.
The original assembler `yaYUL/Parse2DEC.c:222–269` also explicitly complements
both output words for negative constants and emits 28 fractional bits.

## Phase 9 reference matrix — VERIFIED numerical properties

`P40-P47.agc:826` explicitly defines REFSMMAT as a matrix **from reference to
stable-member coordinates, scaled at 2**. `INFLIGHT_ALIGNMENT_ROUTINES.agc:
216–224` says AXISGEN outputs three half-unit vectors. Consequently physical
direction cosines equal twice the decoded DP fractions.

At CPU call 4,760,295 the retained native trace reports AGC-computed:

```
  1.000000000000   -0.000009298325   -0.000000461936
  0.000009313226    1.000000000000   -0.000021800399
  0.000000476837    0.000021860003    1.000000000000
```

Maximum absolute element of `R Rᵀ − I`: `5.960908566748913e-8`.
Determinant: `1.0000000005633745`. Maximum difference from identity:
`2.1860003471374512e-5`. This is a numerically sound near-identity proper
rotation within the synthetic sighting quantization. It is consistent with the
stationary zero-CDU fixture and synthetic approximately identity COAS sightings.

**NOT RUN:** physical instrument calibration, historical Apollo 11 alignment,
or body attitude consistency with any subsequently supplied descent state.
REFSMFLG alone does not prove those properties. The matrix does not by itself
specify vehicle translational state, lunar orientation, or mission time.

## Frames and scales — source-supported interpretation

All references are to the pinned original Luminary 099 source, not new model
conventions. `B−n` means physical quantity divided by `2^n` in the stored
fraction; a reference to units scaled at `2(n)` is the corresponding unit size.

| Quantity | Meaning and scale | Original source |
|---|---|---|
| RLS | Moon-fixed landing-site position; meters B−27 | `ERASABLE_ASSIGNMENTS.agc:1043`; `PLANETARY_INERTIAL_ORIENTATION.agc:35–65`; pinned `yaAGC/ddd-77777-Luminary099.tsv:34–36` independently labels B27 |
| RP-TO-R output | Position transformed into basic reference system; lunar case meters B−27 | `PLANETARY_INERTIAL_ORIENTATION.agc:35–65` |
| RN, VN | Servicer/reference state uses meters B−29 and m/cs B−7 | `yaAGC/ddd-77772-Luminary099.tsv:79,82`; do not confuse with rectified lunar integration state |
| RRECTLEM, VRECTLEM | Permanent lunar rectified integration state; meters B−27 and m/cs B−5 | `INTEGRATION_INITIALIZATION.agc:120–154` |
| TETLEM, TLAND, TPIP | Times in centiseconds, B−28 | integration source `:128–134,210–220`; landing source `THE_LUNAR_LANDING.agc:84–103` |
| RATT1, VATT1 | Lunar integration result, meters B−27 and m/cs B−5 | `INTEGRATION_INITIALIZATION.agc:175–185` |
| R, LAND | Stable-member positions, meters B−24 | `THE_LUNAR_LANDING.agc:84–95,118–123`: half-unit REFSMMAT times B−27 vector, followed by VSL4, gives B−24 |
| V | Stable-member velocity, m/cs B−7 | `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:430–451`: half-unit REFSMMAT times VATT1 B−5, followed by VSR1 |
| WM | Lunar angular-velocity vector in stable-member axes; fraction is rad/cs multiplied by `2^17` | `P12.agc:229–251`: RP-TO-R of half-unit UNITZ/current time, half-unit REFSMMAT, then MOONRATE scaled B+19 gives B+17; original `CONTROLLED_CONSTANTS.agc:259` supplies moon rate in rad/cs |
| /LAND/ | Landing-site radius, meters B−24 | `P12.agc:247–251`: norm(RLS) followed by SL3 |
| RGU | CG times (R−LAND); meters B−24 | `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:414–477`; CG is half-unit and VSL1 cancels its half scale |
| VGU | CG times surface-relative velocity; m/cs B−10 | same source `:435–466`; R×WM+V then VSR2 and half-unit CG |
| CG | Stable-member-to-guidance half-unit matrix | same source `:647–692`: first row UNIT(LAND), second row perpendicular to LAND and the direction of predicted motion; third is first×second |
| TTF/8 | Signed time coordinate; decoded fraction times `2^17` is TTF in centiseconds | same source `:288–315`: ΔTPIP B−28 is shifted left 11 and added to TTF/8; comment explicitly says delta time rescaled to `2(17)` cs |

Guidance axis 0 is therefore locally radial via CG's first row. The initial
IGNITION-ALGORITHM CG is explicitly the identity (`THE_LUNAR_LANDING.agc:
104–112`) before CGCALC erects the local frame. Thus the first guidance pass
requires special care: components need not initially be local vertical and
downrange. Guidance axis 1 is out of plane; axis 2 completes the right-handed
frame. Screen coordinates have no role.

The third row is stored at octal offset `+14` = decimal 12, not decimal 14.
Original `.agc` offsets without a `D` suffix are octal. All 18 matrix words are
three contiguous DP rows.

## Coefficient and root checks — diagnostic only

`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:499–526` constructs these exact fractional
relationships before original ROOTPSRS:

```
A0 = 3/8 (RDG_z − RGU_z)
A1 = 3/4 VGU_z + VDG2TTF
A2 = ADG2TTF
A3 = JDG2TTF
```

The starred target words are **already scaled**: source comments identify
VDG2TTF as `18/8 VDG_z`, ADG2TTF as `6 ADG_z`, and JDG2TTF as `8 JDG_z` under
their respective computational scales. They are not arbitrary replacements for
TABLTTF. The four coefficients must be observed after original computation.
The utility `expected_coefficient_fractions` performs only a separate ideal
arithmetic comparison of observed operands; rounding must be allowed explicitly.

Original ROOTPSRS (`:1247–1380`) uses Newton iterations and requires all
`abs(i*A_i) < 1` and no polynomial/derivative overflow. The utility checks the
first requirement, evaluates the polynomial and derivative at the **observed**
AGC root, and reports the residual. It does not solve for another root and does
not assert overflow is absent merely because the derivative coefficients fit.

For TTF/8 fraction `x`, signed time-to-go is `x * 2^17 / 100` seconds. Its
increase with elapsed time in TTFINCR means the original countdown convention
can be negative before the target epoch. A modern positive remaining-time
convention must not be silently substituted.

The original Phase 9 all-zero polynomial has both zero residual and zero
derivative for every x. A residual of zero alone is therefore **not** evidence
of a meaningful root. `degenerate_all_zero` and a nonzero derivative are
separate diagnostics.

## Synthetic candidate geometry (input proposal, not execution evidence)

`candidate_geometry.py` reads the original rope words by the exact file bank
ordering in pinned `yaAGC/wasm.c:62–91`. It decodes original `MUM`, `RSUBM`,
and lunar-orientation constants, then prepares an explicitly synthetic
initial state. It does not call or replace AGC navigation.

```sh
python3 -B docs/phase10-evidence/math/candidate_geometry.py \
  --rope docs/phase1-evidence/artifacts/MAIN.agc.bin \
  --symbols .build/phase9/setup-test/assembly-77742cdf916841e29275f47e6b53a910/symbols.json \
  --epoch-cs 12000 --output .build/phase10-candidate-t120.json
```

The initial 120-second-epoch candidate uses the actual rope lunar radius
1,738,090 m and gravitational parameter 4,902,778,000,000 m³/s². It places
the LM in a circular orbit 15,000 m above that radius, 0.15 radians behind
the future site, with speed 1,672.31855365 m/s and zero radial velocity.
Coordinates are basic-reference `(r cos(theta), 0, -r sin(theta))`, velocity
`(v sin(theta), 0, v cos(theta))`. Nominal landing epoch is 784.4 seconds,
so original `TLAND-GUIDDURN` requests integration to the 120-second state
epoch. It does not require spoofing the running computer clock.

Moon-fixed `RLS = M(TLAND)*(RM,0,0)` is calculated only to define the mission
input coordinate consistently with a basic-reference +X landing direction.
The diagnostic lunar matrix follows the original MOONMX formulas
(`PLANETARY_INERTIAL_ORIENTATION.agc:151–263`) and original rope angle/rate
constants. `TEPHEM=0` and zero libration are synthetic nominal-epoch
assumptions. The raw `COSI/SINI` pair is slightly non-unit at rope precision;
its numerical discrepancy is retained rather than normalized away.

Before any native coherence claim, the original AGC's actual RP-TO-R and
REFSMMAT transformations must independently produce a consistent LAND vector.
This modern input-coordinate construction alone does not establish that
runtime agreement or guidance success. The fixed-point quantization is 0.5 m
per LSB for lunar position and about 0.00001192 m/s for velocity.

`synthetic-candidate-t120-alt16km.json` changes altitude to 16,000 m and
recomputes the circular speed, preserving the epoch, target and lunar data.
It is a physically coherent causal input variant. The earlier
`synthetic-candidate-t60.json` is a preserved preliminary candidate, not the
final runtime input; it is not presented as an executed experiment.

All candidate JSON files are labeled **SYNTHETIC CANDIDATE**. Actual loaded
mission manifests, AGC outputs and native evidence belong to the runtime
experiment elsewhere in `phase10-evidence/`.

The initial angle-0.15 runs subsequently exposed an operational-timing
limitation: the original ignition epoch was already in the past by the time
mission data entry and P63 selection completed. They remain numerical
diagnostics, not operational descent initializations. The source review
motivated a separate earlier-position candidate, rather than changing the
computer clock or its results.

`synthetic-candidate-t120-angle040.json` retains the same radius, speed, epochs,
target direction and lunar constants, moving the orbit phase to 0.4 radians
behind the site (surface arc 695,236 m). Position becomes
`(1614702.81798, 0, -682685.40172)` m and velocity becomes
`(651.231519, 0, 1540.307389)` m/s. The `-alt16km` variant independently
preserves a circular orbit at 16,000 m altitude. A new native run must establish
that original TIG and TTOGO are now operationally future-facing. The geometry
preparation alone does not assert that result. All earlier JSON files and the
late-selection native results are preserved.

## First native mission run: LAND epoch investigation

```sh
python3 -B docs/phase10-evidence/math/inspect_native.py \
  --run .build/phase10/mission-15km-01 \
  --output .build/phase10-independent-native-math.json
```

`native-mission-15km-01.json` preserves the actual result of this read-only
inspection against the first native run. Its trace/map/configuration hashes
identify the inputs. The run has seven original ROOTPSRS entries and seven
original ROOTSTOR_RESULT observations. The four coefficients agree with the
independent ideal operand formulas within 0.875 DP LSB. The observed first
root is −396.2309814453125 s with fractional residual `1.22234e-9` and nonzero
derivative `0.0248987`; all seven observed relative residuals are below
`1.94e-6`. This is a residual check of the AGC-computed root, not a modern root
calculation.

A diagnostic initially compared the first observed LAND with the landing site
at TLAND and noticed approximately 3 km difference. **VERIFIED explanation:**
that comparison used the wrong epoch. Original GUILDRET
(`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:238–246`) copies old TPIP to TPIPOLD,
then installs PIPTIME1 into TPIP. On the first pass this moves the observation
epoch from TLAND=78,440 cs to TPIP=12,000 cs. Original TTFINCR (`:288–315`)
then transports LAND with lunar rotation. Its formula is
`/LAND/ * unit(LAND − (LAND × WM) * Δtime)`, with internally matched scales.

At the first ROOTPSRS entry:

| Quantity | Stable-member meters |
|---|---|
| Site at TLAND from independent M(TLAND), actual RLS/REFSMMAT | `(1738089.94653, 16.10034, 0.94335)` |
| Site at TPIP from independent M(TPIP), actual RLS/REFSMMAT | `(1738087.25570, -2835.57605, -1146.01534)` |
| Original TTFINCR formula evaluated independently with actual WM | `(1738087.25571, -2835.44447, -1146.32351)` |
| Actual AGC LAND at TPIP | `(1738087.25, -2835.375, -1146.5)` |

The actual LAND differs by 0.190 m from the independent evaluation of original
first-order transport, and by 0.525 m from the independent time-varying lunar
matrix. The latter also contains small differences from rope angle-rate
quantization and the first-order transport approximation. Across all seven
passes the current-epoch matrix comparison error is at most 0.620 m.
The input candidate was retained unchanged: no adjustment was needed to fit
observed output. An initial raw pre-transport LAND value was not captured at a
purely interpretive GUIDINIT entry; the native current-epoch observations and
source relation establish this comparison instead.

The same inspection checks original coordinate transformations. For these
seven observed passes, components of `R − REFSMMAT*RATT1` are within 0.061 m,
`RGU − CG*(R−LAND)` within 0.110 m, and
`VGU − CG*(V−omega×R)` within 0.000267 m/s. Physical half-unit matrices are
decoded consistently. The initial CG is identity; later CG matrices have
maximum orthogonality error below `9.77e-8` and determinant near +1.

These results establish numerical and frame consistency for this bounded
synthetic experiment. They do not establish historical alignment, engine
response, an integrated descent trajectory, or a landing.
