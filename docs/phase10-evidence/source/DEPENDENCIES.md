# Phase 10 original-source dependency investigation

Classification: **VERIFIED source relationships**; numerical execution is a
separate experiment. This note does not assert that a proposed padload ran or
that any P63 calculation succeeded. The accompanying numbered excerpts and
SHA-256 inventory refer to pinned Virtual AGC revision
`f577e3fd917866c59334e6cdd32504f09df76f60`. Assembly-derived addresses are in
`dependency-symbols.json`; they come from the same listing used by Phase 9.

## Initialization and computation are different

`ERASABLE_ASSIGNMENTS.agc:1033–1043` labels `RLS` a padloaded landing-site
vector in Moon reference coordinates. Lines 1353–1383 label the `TLAND` through
`JAPFG*` region W-matrix padloads, including the braking/approach target
parameters and ignition parameters. These entries are mission inputs, not
outputs to inject into a solver.

`THE_LUNAR_LANDING.agc:84–125` performs the following original computation:

1. `RP-TO-R` transforms Moon-fixed `RLS` at nominal landing time `TLAND` to the
   basic reference system. Multiplication by `REFSMMAT` expresses `LAND` in
   stable-member coordinates.
2. `GUIDINIT` constructs the stable-member lunar rotation vector `WM` and
   landing-site radius `/LAND/` (`P12.agc:229–247`). It uses original
   `RP-TO-R`, current computer time, `REFSMMAT`, rope `MOONRATE` and `RLS`.
3. `LEMPREC` integrates the permanent LM state to
   `TDEC1 = TLAND − GUIDDURN`, where original `GUIDDURN` is approximately
   664.4 seconds (`THE_LUNAR_LANDING.agc:96–100,275`).
4. Original ignition initialization erects identity `CG`, clears the trim
   correction `UNFC/2`, and initializes `TTF/8` to original `HI6ZEROS`, an alias
   of `ZEROVECS` (`TAGS_FOR_RELATIVE_SETLOC_AND_BLANK_BANK_CARDS.agc:318`).
   This is before original `TTFINCR`: the first actual root guess incorporates
   `TAT−TLAND` through the normal timing update. In the initialized development
   fixture that produces approximately −664.4 seconds. A nonzero externally
   supplied root guess would change this algorithm.
5. `RATT1` from integration is transformed by `REFSMMAT` into `R` and passed
   to original `MUNGRAV`. `CALCRGVG` similarly transforms `VATT1`, adds the
   previous trim correction, and constructs the surface-relative state.

`RN` and `VN` are permanent servicer/downlink position and velocity
(`ERASABLE_ASSIGNMENTS.agc:657–663`). They are not the direct permanent inputs
to the first preignition `LEMPREC` call. Observing zero `RN` and `VN` alone
does not locate the missing preignition state: inspect `RRECTLEM`, `VRECTLEM`,
`TETLEM`, the actual integration output, `R`, `V`, `LAND`, `RGU` and `VGU`.

## Supported input paths

`UPDATE_PROGRAM.agc:54–61,119–143` explicitly documents original P27's LM
state-vector update:

```text
V71E21E<ECADR UPSVFLAG>E77775E
<DP X position><DP Y position><DP Z position>
<DP X velocity><DP Y velocity><DP Z velocity>
<DP state epoch>
V33E
```

Every DP field comprises two five-digit octal words with Enter after each
word. The count `21` is octal. `77775` is the documented LM/lunar-sphere
identifier, not a readiness flag. P27 is accepted while the LM is in P00.
The driver must observe the original loading and verification displays and
wait for actual P27 completion. A queued word is not proof of a completed
state update.

**VERIFIED documentation/implementation discrepancy:** the introductory V71
comment at lines 92–99 says a maximum `200` octal components. Actual
`OHWELL1` at lines 251–258 compares with `UP21`, which line 317 defines as
decimal 21, and accepts only 3 through **20 decimal components**. Therefore a
contiguous transaction has at most 18 data words after its count and address.
Split larger padload blocks. Do not change this original check to follow the
outdated introductory comment.

`INTWAKEU` (`INTEGRATION_INITIALIZATION.agc:1042–1103`) processes this special
update: it copies loaded `RRECT/VRECT` into conic state, invokes original
`RECTIFY+13D` to clear integration deviations and previous root/time, chooses
the Moon from the identifier, and calls `ATOPLEM`. Original routines update
their own state flags and copy permanent state. This is preferable to writing
42 permanent state words and manually setting their flags.

The same P27 generic contiguous-block mechanism can load documented mission
padload data (`UPDATE_PROGRAM.agc:92–115,429–457`). It is not permission to
load `TABLTTF`, `TTF/8`, computed outputs or arbitrary flags. Separate
pre-start padload mechanisms are also possible only when every allowed
location and its provenance are explicitly recorded. Original simulation
preload documentation is `INTEGRATION_INITIALIZATION.agc:130–198`.

| Input | Source-defined representation |
|---|---|
| LM position | Moon-centered basic-reference DP metres, divided by `2^27` |
| LM velocity | Same inertial axes; DP metres/centisecond divided by `2^5` |
| LM state epoch | DP centiseconds from AGC clock zero, divided by `2^28` |
| RLS | Moon-fixed landing-site DP vector; metres divided by `2^27` |
| TLAND | Nominal landing epoch, DP centiseconds divided by `2^28` |
| REFSMMAT | Basic-reference to stable-member 3×3 matrix, each DP entry divided by 2 |
| TEPHEM / TIMSUBO | Original planetary-orientation epoch, TP centiseconds divided by `2^42` |
| 504LM | Lunar libration vector in Moon-fixed axes, DP radians, binary scale zero |
| Braking/ignition target padloads | Require separately justified units/scales and values; their names are insufficient provenance |

The LM state scales are explicit in `INTEGRATION_INITIALIZATION.agc:130–181`
and `CONIC_SUBROUTINES.agc:104–149`. Generic P27 values have the internal
representation. Signed words are 15-bit ones-complement with positive and
negative zero. For canonical same-sign DP words, the signed normalized value
is the signed 28-bit magnitude divided by `2^28`; negate by complementing
both 15-bit words. Observers must also tolerate legal mixed-sign arithmetic
pairs. Upstream `yaAGC/agc_engine.c:1070–1125` describes their normalization;
`yaYUL/Parse2DEC.c:221–260` documents assembler rounding and word formation.

## Frames, epochs and immutable physical constants

`PLANETARY_INERTIAL_ORIENTATION.agc:33–58` defines
`R = M(T)^T (RP + L × RP)`: `RP` is Moon-fixed, `R` is basic reference,
`L` is libration, and `M` is the planetary-orientation matrix. `MOONMX` uses
original fixed lunar angles/rates plus the time epoch; `NEWANGLE` explicitly
constructs `X = X0 + XDOT*(T + T0)` (lines 262–299).

Lunar gravitational parameters and most orientation parameters are already
rope constants. `CONTROLLED_CONSTANTS.agc:258,305–308,326` contains
`mu = 4.9027780e8 m³/cs²` (`4.9027780e12 m³/s²`);
line 259 contains `MOONRATE = 0.26616994890062991e−7 rad/cs`;
lines 551–560 contain `COSI`, `SINI`, node/longitude rates and reference
angles. Do not treat these constants as missing erasable padloads or invent
replacement gravity. Choosing zero `TEPHEM` and zero libration is a labeled
synthetic nominal epoch/zero-libration assumption, not an Apollo 11 epoch.
More specifically, `LUNAR_AND_SOLAR_EPHEMERIDES_SUBROUTINES.agc:91–94`
defines `TEPHEM` as time from midnight 1 July preceding launch to AGC clock
zero. The original `RATESP` constants explicitly cover 1969–1970. A zero
synthetic epoch therefore anchors clock zero to midnight 1 July 1969; it does
not anchor it to the Apollo 11 launch.

`REFSMMAT` maps basic-reference vectors into stable-member coordinates. Its
software-valid flag alone does not demonstrate a calibrated physical mount.
A diagnostic fixed stable member can be mathematically coherent if its
measured matrix is close to a proper rotation and *all* initial vectors and
independent checks use the actual same matrix. That does not establish the
Phase 9 COAS fixture as a physical spacecraft alignment.

`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:419–471` constructs
`VGU = CG*(V − WM × R)` and `RGU = CG*(R − LAND)`.
`CG` is the stable-member to guidance-coordinate matrix. It initially equals
identity. Original `CGCALC` (lines 647–710) subsequently uses `UNIT(LAND)` as
its radial row, a cross-track row derived from the compensated velocity and
landing geometry, and the radial/cross-track cross-product as its final row.
Thus initial guidance component 2 is not automatically geographical altitude.
Coordinate labels must be qualified by the actual `CG` at that pass.

## Construction and failure of the time-to-go polynomial

Original `TTF/8CL` (lines 499–526) builds normalized coefficients, without
modern guidance replacement:

```text
A3 = JBRFG*
A2 = ABRFG*
A1 = 3/4 * VGU[2] + VBRFG*
A0 = 3/8 * (RBRFG[2] − RGU[2])
```

The source comments identify `JBRFG* = 8*Jtarget[2]`,
`ABRFG* = 6*Atarget[2]`, and `VBRFG* = 18*Vtarget[2]/8` in their respective
internal scales. The table's precision word is `BIT8`; its degree is three.
These are not all the same physical units; an independent decoder must apply
their scaling before comparing physical quantities.

`TTFINCR` (lines 299–315) adds an 11-bit-left-shifted DP centisecond interval
to `TTF/8`, whereas the epochs are scaled by `2^28`. This establishes stored
root `x = physical_time_to_go_cs / 2^17`, or physical seconds `x*1310.72`.
`RGU` metres divided by `2^24` follows original integration/REFSMMAT shifts;
`VGU` metres/centisecond divided by `2^10` is explicit in
`THE_LUNAR_LANDING.agc:136–138` and guidance-equation comments. Validate these
claims against actual readbacks rather than assuming all vectors share scales.

`ROOTPSRS` (lines 1250–1384) applies original Newton iteration, records its
iteration count, and returns through `BADROOT` after eight unsuccessful
corrections. Its documented preconditions include `i*|Ai| < 1` and absence
of overflow during residual/derivative evaluation. The all-zero Phase 9 table
has zero derivative and supplies no meaningful root problem. Original
division saturation and exhausted iteration do not prove a controller defect.

Even a converged isolated root is insufficient: verify a sensible time sign,
bounded residual, real nondegenerate geometry, actual navigation state and
target inputs. P63 then performs further guidance passes, coordinate
construction and ignition-time iteration. These can reveal genuine additional
missing inputs. Neither root convergence nor departure from 01406 demonstrates
ignition or engine thrust.

Useful original basic checkpoints are `ROOTSTOR=31,3670`,
`BADROOT=31,3656`, `QUADGUID=31,3121`, `CGCALC=31,3245`,
`EXGSUB=31,3331`, `DDUMCALC=32,3102`, `DDUMGOOD=32,3163`, and
`IGNALGRT=32,3202`. At entry to `ROOTSTOR`, the final root is still in
`ROOTPS`; original instructions then move it into `MPAC` and store the
iteration count in `MPAC+2`. Observe the actual good-return continuation as
well as the final root, rather than treating a single label visit as complete
guidance execution.

The retained native observer records **post-CPU-call** snapshot contents
alongside the **pre-call** bank/Z. A CPU call is not always a completed
instruction. `yaAGC/agc_engine.c:1958–1979,2546–2563` explicitly delays
multi-MCT computation until its last cycle. A first `ROOTSTOR` checkpoint can
therefore still precede its first `DXCH ROOTPS`; after that instruction the
root is in `MPAC` and `ROOTPS` contains the old `MPAC`. An observation at
`ROOTSTOR+1` establishes completion of the preceding DXCH, and one at
`ROOTSTOR+4` establishes that original iteration-count storage completed.
Interpret checkpoint values with this ordering; do not call every label
observation a completed instruction. The interpreter push-list
labels `RATT1`, `VATT1`, `TAT` and `TDEC1` are constant offsets 14, 20, 12 and
32 decimal into the active VAC area; they are not absolute erasable addresses.
Resolve them using the observed `FIXLOC` and the relevant VAC contents
(`ERASABLE_ASSIGNMENTS.agc:447–455`, `INTERPRETER.agc:207`).

## Minimum source dependency boundaries

The first cubic consumes the loaded braking downrange position, the three
starred braking quantities and the actual computed `RGU/VGU`. Meaningful
subsequent quadratic guidance additionally consumes full three-component
`RBRFG/VBRFG/ABRFG`; coordinate erection consumes `GAINBRAK` and
`TCGFBRAK/TCGIBRAK`. The resulting ignition iteration consumes `VIGN`,
`RIGNX`, `RIGNZ`, `KIGNX/B4`, `KIGNY/B8`, and `KIGNV/B4`.
`TLAND` through `TCGIBRAK` is 30 words total including `TLAND`, so it
requires at least two P27 contiguous transactions. Targeting after a root
return is not justified by loading only the four cubic inputs.

Authoritative Apollo 11 target padload data were located separately by the
research investigation under `../research/`. The PDF's octal words and stated
scales should be used together with these source dependencies. Its historical
target parameters can support a clearly labeled synthetic navigation fixture;
they do not make a synthetic mission epoch, orbit or position historical.
