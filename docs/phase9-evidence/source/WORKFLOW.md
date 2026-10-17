# Luminary 099 alignment source investigation

All line references below refer to the exact retained `.agc` files in this
directory, revision `f577e3fd917866c59334e6cdd32504f09df76f60`.
`source_hashes.json` records their SHA-256 and Git blob SHA-1; all 27 source
files matched the pinned repository tree blobs. These are source findings,
not claims that a driver or alignment execution succeeded.

## P51, P52 and the P63 gate — VERIFIED source

* `P51-P53.agc:1019–1046`: P51 calls IMUCHK, which checks only the operating
  IMU state (`:2318–2331`). It then displays checklist code octal `015`
  through GOPERF1. The PROCEED return selects P51B. The ENTER return instead
  sets desired gimbal angles to zero, displays V06N22/V41, and calls COARSE.
  The driver may legitimately accept the already operating fixture with
  PROCEED; this is an original branch, not a bypass patched into the AGC.
* `P51-P53.agc:1048–1065,1135–1150`: P51B calls NCOARSE, which initializes
  PIPA integration bookkeeping and sets DRIFTFLG itself. It initializes
  STARIND to zero, calls AOTMARK and then waits through AOTSTALL.
* `P51-P53.agc:1066–1120`: after the first sighting, the observed vector is
  preserved and PLANET fetches the associated catalog/reference vector.
  STARIND becomes one; the real marking workflow repeats for the second
  star. CHKSDATA compares the observed and reference pair separation. When
  the operator accepts, P51G calls AXISGEN, MATMOVE copies its computed XDC
  matrix into REFSMMAT, and the original interpreter SET instruction sets
  REFSMFLG before GOTOPOOH. Neither the matrix nor flag is a driver input.
* `P51-P53.agc:135–136`: P52 starts by calling R02BOTH. It therefore requires
  an already valid reference matrix. Its reference-matrix option is not an
  independent remedy for Phase 8's invalid-REFSMMAT condition.
* `THE_LUNAR_LANDING.agc:47–51`: P63 calls R02BOTH before its mission/guidance
  initialization. `IMU_MODE_SWITCHING_ROUTINES.agc:917–936` tests FLAGWRD3
  using REFSMBIT. If valid, R02ZERO sets IMUSE and returns. If invalid,
  the IMODES30 bit9 operating check distinguishes alarm `00220` (operating
  but invalid matrix) from `00210` (not operating), then GOTOPOOH returns.
* `FLAGWORD_ASSIGNMENTS.agc:466–476`: FLAGWRD3 is STATE+3; REFSMFLG is the
  interpreter flag identifier decimal 47, **not an erasable address**.
  REFSMBIT is bit13, decimal 4096 / octal `10000`.
* `ERASABLE_ASSIGNMENTS.agc:970–972`: REFSMMAT is 18 words (nine DP entries).
  Exact banked addresses must be taken from the listing of the same rope.
* After the successful R02 gate, `THE_LUNAR_LANDING.agc:84–207` consumes RLS,
  TLAND, REFSMMAT and integrated state through RP-TO-R, GUIDINIT, LEMPREC,
  and the ignition-guess iteration. Valid alignment alone is not a valid
  pre-descent mission state. The next **observed** blocker must come from
  the execution trace; source availability does not establish its result.

## Authentic input and display workflow — VERIFIED source

The driver must wait for actual AGC display/state transitions rather than
assume that elapsed host time means an operator request was accepted.

1. Select P51 using the normal DSKY channel015 keystrokes `V37E51E`.
2. At the original V50N25 checklist request `00015`, issue `V33E` to accept
   the operating, unchanged startup fixture.
3. `AOTMARK.agc:108–126` displays V01N71 (detent/star code). Load component1
   through `V21N71E`, five octal digits, ENTER. AOTCODE bits1–6 hold the star
   identifier; bits7–9 hold detent. For detent7 and catalog stars1/2, the
   full octal words are `00701`/`00702` (decimal449/450). PROCEED accepts.
4. `AOTMARK.agc:133–151` explicitly supports detent7/COAS and asks for V06N87,
   optic-axis azimuth and elevation. Load both components via `V24N87E`,
   wait for the actual **V21N87** R1 load prompt, enter signed five decimal
   digits and ENTER, wait for **V22N87** R2 load prompt, enter signed five
   digits and ENTER; then PROCEED. V24 selects the two-component operation;
   it is not the verb held on the display during component entry. Original
   `PINBALL_GAME__BUTTONS_AND_LIGHTS.agc:1816–1824` explicitly updates the
   displayed verb to VBSP1LD before REQDATX, then to VBSP2LD before REQDATY;
   these constants are decimal21/22 (`:1889–1890`). REQDATX/Y blanks the
   corresponding data register and enables flashing (`:1108–1120`).
   `PINBALL_NOUN_TABLES.agc:520,806–809` assigns two CDU-degree
   components, `XXX.XX` degrees (`:56`). `PINBALL...agc:1203–1204` requires
   exactly five numerical characters for each decimal field. A missing
   digit or wrong load return sequence is a driver defect, not AGC failure.
5. `AOTMARK.agc:323–340` initializes marking and displays V54N71, requesting
   an X or Y mark. Mark hardware is channel016 NAVKEYIN, not DSKY015.
   `INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:137–144` and MARKRUPT
   (`AOTMARK.agc:438–501`) agree: bit3/value4 X mark, bit4/value8 Y mark,
   bit5/value16 reject. Supply each documented event separately through the
   normal input bridge and release to zero; do not write MARKSTAT/CDUs.
6. `AOTMARK.agc:616–641` selects display verbs according to accepted marks:
   V54N71 none or complete pair, V53N71 needs Y, V52N71 needs X. Thus a
   second V54N71 alone must be distinguished from its initial occurrence.
   MARKSTAT and sampled native PC are legitimate **read-only** observers.
7. After a complete pair, PROCEED follows MARKCHEX/AVESTAR. MARKRUPT samples
   actual CDUY/Z/X and TIME2/1 (`:425–436`), VACSTOR stores them (`:563–603`),
   and the original routines transform both mark planes to stable member
   and form a line of sight (`:378–394`). AOTSTALL returns after MKRELEAS.
8. Repeat steps 3–7 for the second catalog star.
9. `P51-P53.agc:826–895` computes the observed-versus-reference separation
   difference, displays **V06N05** (VB6N5), and waits for operator acceptance.
   A header comment says noun3, but the executable constant is noun5.
   PROCEED enters CHKSDA with FREEFLAG set; ENTER clears it and recycles.
10. Observe the original matrix stores and flag transition and P00 return,
    then request P63 via normal `V37E63E`; do not supply new readiness bits.

DSKY keyboard codes are defined at `PINBALL_GAME__BUTTONS_AND_LIGHTS.agc:383–396`:
zero=16, digits1–9=1–9, VERB=17, RESET=18, KEY RELEASE=25, plus=26,
minus=27, ENTER=28, CLEAR=30, NOUN=31 (all values decimal here). PROCEED
has no DSKY keycode; V33E is the documented verb alternative. A physical
PROCEED key is channel032 bit14 (active-low convention); it should only be
used if its full assertion/release path is verified separately.
`DISPLAY_INTERFACE_ROUTINES.agc:91–95,247–255,306–313` documents the
terminate/proceed/enter return ordering used by these requests.

### Missing mark interrupt delivery — VERIFIED source limitation

Pinned `ringbuffer_api.c:145–180` stores the received input channel word,
but does not request interrupt 6 when channel016 arrives. The upstream
socket backend (`SocketAPI.c:239–273`) has the same omission. This is an
input-device delivery limitation; neither backend's channel016 storage
alone exercises MARKRUPT. Original `INTERRUPT_LEAD_INS.agc:65–68` routes
KEYRUPT2 (interrupt 6) to MARKRUPT. The flight input-channel description
at `INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:137–144` explicitly identifies
this interrupt and the mark bits.

The experiment may add a small external hardware-event bridge which first
delivers a real mark packet through the retained ringbuffer, checks that
the documented channel word is present, and asserts only the corresponding
interrupt request latch. Releasing the mark input to zero must not assert
a second mark interrupt. This implements a documented external event,
without writing any erasable, forcing readiness, replacing flight logic,
or changing instruction semantics. A disconnected-interrupt control
should establish that channel storage alone does not progress marking.

## A reproducible synthetic geometry candidate — ASSUMED fixture

The existing ideal stationary zero-CDU fixture is not historical Apollo
mission geometry. A synthetic instrument test may choose a consistent
reference orientation and calculate COAS azimuth/elevation from actual
stored catalog vectors. This is an instrument measurement input, not a
fabricated AGC result, provided that the real AOTMARK/AXISGEN flow runs.

`AOTMARK.agc:249–304` computes, in navigation-base axes:

```
u = (sin(el), cos(el)*sin(az), cos(el)*cos(az))
az = atan2(u_y, u_z)
el = asin(u_x)
```

With identity orientation and zero CDU measurements at both X/Y marks,
choose the original catalog vectors from `CONTROLLED_CONSTANTS.agc:501–507`:

| Catalog star | X | Y | Z | AZ degrees | EL degrees | N87 fields |
|---|---:|---:|---:|---:|---:|---|
| 1 | .8748658918 | .0260879174 | .4836621670 | 3.0874453969 | 61.0291079402 | `+00309`, `+06103` |
| 2 | .9342640400 | .1735073142 | -.3115219339 | 150.8836534221 | 69.1095689512 | `+15088`, `+06911` |

Catalog separation is approximately 47.8394151237 degrees. Values are
quantized to the noun's .01-degree input resolution; original CDU scaling
and fixed-point computations introduce further rounding. This candidate
is **not execution evidence**. The final driver must record actual fields,
marks, matrix and discrepancy; acceptance of a large discrepancy must not
be represented as calibrated alignment success.

An alternative detent1–6 fixture requires appropriate actual spacecraft
orientation/CDU evolution between stars. Do not invent absolute sensor
words to obtain those orientations.

## Driver mistake separated from AGC behavior

The first runtime attempt requested `V24N87E` correctly but waited for a
V24N87 prompt. The actual AGC displayed V21N87 with a blank R1, precisely
as ABLOAD specifies. The timeout was a driver expectation error, not an
alignment/readiness failure. Keep that attempt's raw log; the corrected
driver must wait for V21 then V22 as described above.

## Actual post-alignment P63 result and the 01406 boundary

**VERIFIED attempt02 runtime observations:** the fresh native trace at
`.build/phase9/attempt02/trace.jsonl` contains P63LM at cycle4894934,
R02BOTH at4895158, then the **first instruction after R02's return** at
cycle4895231, bank32 Z3002 (P63LM+4). Its snapshot has MODREG63,
FLAGWRD3 octal12000 (bit13 set), and the 18 words populated by P51's
original calculations. R02 passed its invalid-REFSMMAT check in this run.
FAILREG+1 changes to decimal774 / octal01406 at cycle4967636. No 00220
result is being substituted for this different observed behavior.

**VERIFIED source meaning:** `ASSEMBLY_AND_OPERATION_INFORMATION.agc:987–991`
identifies 01406 as a bad return from ROOTPSRS. During the ignition
algorithm it is POODOO; during actual guidance it is non-abortive ALARM.
`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:496–528` builds a cubic time-to-go
polynomial TABLTTF from RGU, VGU and descent target coefficients, then
calls ROOTPSRS with TTF/8 as the initial guess. On a bad return,
INDEX WCHPHASE selects WHATALM. The P63 ignition phase WCHPHASE=-1
selects the table entry immediately before WHATALM (`:99–103`), leading
to 1406POO (`:1422–1425`) and its original POODOO01406.

ROOTPSRS uses Newton iteration (`:1251–1278`). Its documented bad-return
condition is failure to converge within the iteration limit; the actual
instructions test MODE bit4 and return through BADROOT (`:1355–1374`).
This is an ignition-algorithm feasibility failure, not evidence of engine
ignition, thrust, flight guidance or descent.

**Evidence limit for attempt02:** its observer did not retain the root
finder's internal checkpoints, polynomial coefficients or iteration
counter. The alarm and source establish its defined meaning, but cannot
identify the precise numerical root inputs or independently count the
iterations. New read-only instrumentation in a further fresh run can
capture ROOTPSRS/ROOTLOOP/BADROOT/1406POO plus WCHPHASE, MODE, TABLTTF,
TTF/8 and the initial mission inputs. A missing flight padload is a
known fixture limitation; its unique causal contribution to this failure
must not be claimed without those measurements.

## Attempt04: identifying the original flag store — VERIFIED runtime and source

The read-only extraction in `attempt04_readonly_findings.json` records the
trace and observer-map checksums and the actual values summarized here.
At CPU-call cycle 4,759,831, FLAGWRD3 first acquires bit13, changing from
octal02000 to octal12000. The instruction just executed is original
INTERPRETER bank01 Z2554, `TS STATE`, reached through SWSTORE at01,2553.

This is not an unexplained interpreter write attributed to P51 by timing
alone. The same captured snapshot retains the interpretive context:

| Observer | Actual octal value | Source implication |
|---|---:|---|
| LOC | 03562 | Original P51G's REFSMFLG operand is at14,3562 |
| BANKSET | 030005 | Fixed-bank field identifies bank14; low field preserves the working erasable bank |
| INTBIT15 | 0 | Captured interpretive address-mode state |
| POLISH | 01462 | Assembled REFSMFLG switch operand following SET/EXIT at14,3561 |
| SWBIT | 010000 | Bit13 valid-reference-matrix mask |
| SWWORD | 3 | STATE+3, exactly FLAGWRD3 |

`P51-P53.agc:1110–1119` shows AXISGEN, MATMOVE into REFSMMAT, then SET EXIT
with REFSMFLG. `INTERPRETER.agc:2991–3056` explains switch encoding and the
actual store: SWITCHES derives SWBIT and SWWORD from POLISH, the SET arm
ORs SWBIT into the original word, and SWSTORE indexes SWWORD before
`TS STATE`. The actual interpreted operand address, bank, switch word,
mask and basic store therefore tie this flag transition to the original
P51G instruction, without any external write to matrix, flags or memory.

## Attempt04: measured numerical boundary — VERIFIED observations

At ROOTPSRS entry (cycle 4,959,517), the four double-precision cubic
coefficients TABLTTF[0:8] are all positive-zero words. TABLTTF+10 in the
flight source uses an **octal addend**: its precision is at offset8 decimal,
and the measured word is128 decimal. TABLTTFL points to TABLTTF+3, so the
root finder's `INDEX ...; CA5` selects that same precision word.
The initial TTF/8 and DXCRIT are both double negative zero, `[077777,077777]`.

The actual ROOTLOOP checkpoints occur nine times, with MODE values0 through8.
The first checkpoint has MPAC `[0,0]`; the next eight show
`[037777,037777]`, positive double-precision maximum. BADROOT executes at
cycle 4,967,600 with MODE8 and WCHPHASE077776 (ones-complement minus one).
1406POO follows at4,967,606. Thus the executed limit branch, bad return
and abortive ignition-phase alarm are directly observed. The routine's
comment says eight passes; the executable trace establishes nine
ROOTLOOP visits from MODE0 throughMODE8 before its limit test returns.

The retained mission inputs at this root-entry snapshot are RLS six zero
words, TLAND two zero words, RN and VN each six zero words. RGU is six
negative-zero words; VGU contains only positive/negative zeros. These are
actual cold-fixture contents, not a valid flight state, landing target or
mission padload inferred from successful alignment.

**Source-derived numerical explanation:** an all-zero coefficient table
describes an identically zero polynomial. Its derivative is also zero,
so Newton's residual/derivative correction is undefined (0/0).
ROOTPSRS calls POWRSERS for both terms, then DDV/BDDV for the correction
(`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:1332–1358`). Original
`INTERPRETER.agc:1789–1832` routes a zero divisor through BUFZERO to DVOVF,
which saturates the DP quotient to signed POSMAX and sets OVFIND. The
positive maximum magnitude observed after each attempted correction is
consistent with this original arithmetic path; it exceeds the zero
DXCRIT, so convergence is never accepted before the limit branch.
No individually retained DVOVF instruction checkpoint is claimed here.

This identifies the immediate invalid numerical inputs and observed
failure mechanism. It does not establish a unique missing mission datum
whose isolated correction would make P63 operational, nor does it validate
the orbit integration, target constants, guidance, engine or descent.
