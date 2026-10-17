# Phase 11 original-source investigation

This is a source-level investigation of Virtual AGC revision
`f577e3fd917866c59334e6cdd32504f09df76f60`, specifically its unchanged
`Luminary099` and `yaAGC` sources. Line references below refer to that
revision, not to generated modern adapter code. Runtime achievement levels
must be established separately by retained native traces.

## Hardware interface — VERIFIED in source

`Luminary099/ERASABLE_ASSIGNMENTS.agc:134–136` assigns PIPAX, PIPAY and
PIPAZ to erasable counter addresses **037, 040, 041 octal**.
`yaAGC/agc_engine.h:248–250` independently assigns the same registers.
These are counter registers, not ordinary input channels.

`yaAGC/SocketAPI.c:215–230` recognizes a packet whose channel carries
`0x80`, then calls `UnprogrammedIncrement(State, Channel, Value)`.
`yaAGC/agc_engine.c:1570–1595` masks the address to seven bits and selects
operation **0 = PINC**, **2 = MINC**. Operations 1/3 are two's-complement
CDU operations and must not be substituted. The ringbuffer embedding must
preserve this original counter path; no navigation erasable is assigned
by the sensor adapter.

`CounterPINC` (`agc_engine.c:1188–1214`) and `CounterMINC`
(`:1217–1244`) implement **15-bit one's-complement** counting, including
both signed zeros. PINC takes negative zero `077777` to `000001`; MINC
takes positive zero `000000` to `077776` (-1). Positive/negative full-scale
overflow is handled in the original implementation. These small experiments
must remain well below overflow, since `UnprogrammedIncrement:1616–1621`
does not implement general counter-overflow interrupt behavior.

## Scale and physical frame — VERIFIED in source, model assumptions explicit

The LM's scale is **0.01 m/s per pulse**. It must not be replaced with
the CSM's frequently quoted different PIPA scale. This follows directly
from the constants and actual original computation:

* `CONTROLLED_CONSTANTS.agc:178–180`: KPIP = .0512, KPIP1 = .0128,
  KPIP2 = .0064, with corresponding velocity scales B5, B7, B8 m/cs.
* `SERVICER.agc:1052–1055`: MUNRVG multiplies DELV by KPIP2 and labels
  the result B8 m/cs. A raw integer pulse count occupies the high word
  of a DP vector, giving a fraction count / 2^14. Thus
  `.0064 * 2^8 * 100 / 2^14 = .01 m/s per count`.
* `SERVICER.agc:987–992`: CALCRVG performs DELV VXM REFSMMAT, multiplies
  by KPIP1 and shifts left once. The REFSMMAT is a half-unit rotation
  matrix, so the shift compensates that half scale. The same physical
  conversion results. Exact assembled DP constants introduce their own
  small fixed-point quantization; compare to the actual rope value.

PIPA readings are in **IMU stable-member coordinates**, not automatically
spacecraft body coordinates. The source describes MUNRVG's input/output
frame at `SERVICER.agc:1019–1022`. CALCRVG transforms the DELV row vector
through REFSMMAT back into the basic reference frame. `P40-P47.agc:1435–1448`
explicitly describes the inverse sequence used for a body-frame display:
reference vector -> REFSMMAT -> stable member -> CDU*SMNB -> LM body.
REFSMMAT therefore maps reference column vectors to stable-member vectors;
the VXM operation in CALCRVG implements the inverse row-vector operation.

For a synthetic sensor model in an inertial reference frame use
`f_REF = a_total_REF - g_REF`, then `f_SM = C_SM_from_REF * f_REF`, with
the full (twice encoded) REFSMMAT. Gravity-only free fall has f = 0.
An axis-aligned stable-member test may declare its input directly in SM
and separately verify the reference-to-SM transformation. A fixed stationary
instrument fixture and ideal, zero-bias sensors are **ASSUMED**, not a
calibrated Apollo trajectory or complete spacecraft plant. Accumulate
`delta_v_SM = integral(f_SM dt)` in m/s and quantize to integer pulses,
retaining fractional residuals. Any positive/negative residual rule,
event spacing and timing quantization must be documented by the adapter.

## The genuine PIPA consumption path

`SERVICER.agc:520–545` documents PIPASR's contract: read PIPAX/Y/Z plus
TIME2, store readings in DELV high words, save the time, and snapshot CDU
angles. `:553–602` implements this. Reading **clears the counters to
negative zero**, which is valid original behavior and must not be reported
as a sensor delivery failure. `:582–587` computes PGUIDE, the measured
interval between PIPA snapshots. `:595–600` also saves PIPATMPX/Y/Z.

`PREREAD:51–83` first schedules LASTBIAS, clears/reads old PIPs, sets
V37FLAG and AVEGFLAG using original instructions, initializes navigation,
then schedules READACCS after two seconds. `READACCS:88–148` adjusts TIME5
to reduce DAP-interrupt conflict, reads the counters, schedules SERVICER,
and repeats on the **two-second** task period. This is not a claim that
every task instruction finishes at the exact same cycle after injected
pulses: genuine counter operations consume emulator cycles.

`SERVICER:184–246` applies original PIPA compensation, obtains the DELV
magnitude, snapshots CDU orientation, and calls CALCRVG unless MUNFLAG
selects the lunar stable-member integration route. `IMU_COMPENSATION_PACKAGE.agc:42–84`
describes scale-factor and bias corrections. Uninitialized correction
values must be observed rather than silently substituted in modern code.

For the P47 route, `CALCRVG:987–1011` uses **DELV, REFSMMAT, previous
gravity GDT/2, RN, VN, PGUIDE** to compute RN1 and VN1 using original
CALCGRAV. RN/RN1 are reference-frame positions scaled B29 m; VN/VN1 are
reference-frame velocities scaled B7 m/cs (explicit comments `:1005,1011`).
`COPYCYCL:250–255` and `COPYCYC:503–515` copy the calculated state into
RN/VN/PIPTIME and clear PIPATMP values. Gravity is part of this update:
zero specific force must not be interpreted as constant inertial velocity.

`CALCGRAV:948–985` chooses its gravity scale from RTX2 (Earth 0, lunar 2)
and returns the appropriate gravity increment. These state calculations
are original Luminary navigation, distinct from an independent modern
delta-v sanity check.

## Why Phase 10 V06N61 is not sufficient by itself

The existing Phase 10 endpoint is a pre-ignition crew-review display.
`BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:761–767` documents V06N61
as the crew's event-timer/TIG check. It does not alone start READACCS.
The subsequent original P63 path includes R51 attitude handling, R60
attitude maneuver, landing-radar antenna checks (`THE_LUNAR_LANDING.agc:218–261`),
and BURNBABY. BURNBABY's P41SPOT/P63SPOT setup integrates to TIG−29.9 s
(`:197–240`) and TIG−30 invokes REDO4.2/PREREAD (`:301–352`). Later code
requests engine enable and ignition. Consequently completing P63's
downstream crew sequence is unnecessary scope and introduces unrelated
hardware prerequisites for this first sensor experiment.

## Source-supported bounded alternative: P47

**VERIFIED source path; native outcomes are recorded separately.** P47
is a genuine keyboard-selectable major mode: its original entry is in
`FRESH_START_AND_RESTART.agc:1057–1084`, including FCADR P47LM.
Normal DSKY `V37E47E` therefore provides a legitimate entry without forcing
the program counter, navigation erasables, or flags.

`P40-P47.agc:364–388` implements:

1. R02BOTH (the same original reference/alignment readiness check).
2. MIDTOAV2 (original precision integration of this vehicle's permanent
   state to the current time plus the computation allowance).
3. A timed STARTP47 task, which installs the original CALCN83 exit,
   initializes its display, and enters REDO4.2 -> PREREAD.

R02BOTH (`IMU_MODE_SWITCHING_ROUTINES.agc:917–935`) validates REFSMFLG /
IMU readiness and sets IMUSE itself. It is not bypassed. MIDTOAV2
(`INTEGRATION_INITIALIZATION.agc:936–996`) requires no caller-injected
state: it uses the current LM permanent state already initialized through
the documented P27 procedure. Its original TIMEDELT is **2000 cs = 20 s**
(`:1035`); it returns RN1, VN1, PIPTIME1 and the remaining delay, then the
original task begins. Allow at least that delay and observe actual
READACCS/SERVICER passes before sending the bounded force input, because
PREREAD deliberately clears pre-existing PIPs once at startup.

`P47BODY:423–429` clears only its display accumulators through original
instructions and displays **V16N83**. `CALCN83:391–411` accumulates
DELVREF into DELVCTL/DELVSIN, calls original S41.1 to calculate body-frame
DELVIMU, and returns to SERVEXIT. This gives two separate useful
observations: original navigation RN/VN updates and original accumulated
delta-v/body display updates. P47 does not call the ignition master
routine to start an engine. Explicitly stop at the bounded horizon and
inspect engine-enable outputs rather than infer their absence from a
program name.

P51 alignment and the Phase 10 P27 synthetic mission initialization can
be reused unchanged, followed by P47 through normal keys. This is a
separate non-ignition navigation experiment; Phase 10's P63 experiment
must also be reproduced unchanged as a regression control. It is also
legitimate to return from the recorded P63 review to P00 and then select
P47 using normal keys; runtime evidence must disclose the exact choice.
The original V37 cleanup at `FRESH_START_AND_RESTART.agc:836–852` waits
for integration and clears MUNFLAG, so P47 does not inherit P63's lunar
stable-member route merely because P63 ran first. `:881–898` also turns
the engine off, initializes coast mode and clears obsolete restart
groups. These operations remain original software behavior, not a
modern initialization shortcut; observe FLAGWRD6 to confirm the route.

## Suggested observations and causal checks

Read-only checkpoints: P47LM, MIDTOAV2, STARTP47, PREREAD, BIBIBIAS,
READACCS, PIPASR, PIPSDONE, SERVICER, CALCRVG, COPYCYCL, CALCN83,
SERVEXIT. Read-only quantities: PIPAX/Y/Z; DELV raw and compensated;
DELVREF, DELVCTL, DELVIMU; RN/VN and RN1/VN1; PGUIDE; PIPTIME;
REFSMMAT; IMODES30; FLAGWRD7; relevant engine output channel bits.

Compare positive, negative, zero and deliberately disconnected runs at
the actual PIPTIME epochs. Because positive/negative hardware events
steal CPU cycles, coarse wall-time comparisons and a checksum between
different force cases do not establish equivalent timing. Same-case
repeats should be byte-identical using a cycle-locked schedule. Derive
quantization tolerance from .01 m/s/count and DP arithmetic, and separate
gravity's contribution from the PIPA-induced difference. A native
checkpoint at PIPASR proves consumption only when DELV/counter clearing
also agrees with delivered pulses; navigation-state evidence is needed
for Level 4. P47 navigation alone does not establish Level 5 subsequent
P63 guidance use or powered descent.

## Investigated file SHA-256 values

These are checksums of the pinned source inspected for this note.

| Pinned source file | SHA-256 |
| --- | --- |
| Luminary099/ERASABLE_ASSIGNMENTS.agc | ec841599e818108cca4947141e1a51fca9956c103670a2764fdab9c3aaffe48c |
| Luminary099/CONTROLLED_CONSTANTS.agc | 8ff78c818b3f92e061af1543eb84deaf1b16e96187d2236e3438671bffaa79ae |
| Luminary099/SERVICER.agc | d975bffb0b203ec5660933a9c3d1e86fbd4fc40c0f6192bb9e32c77d8fcdb7b1 |
| Luminary099/P40-P47.agc | 1522e7cdc1a33328b49f57d4768a820f3f940bbefbb97152051342c1464d651c |
| Luminary099/INTEGRATION_INITIALIZATION.agc | 35197ba93b209defdcfb21f3deb65d9215097e7778b437d5264d05bf0e6bdf1e |
| Luminary099/IMU_COMPENSATION_PACKAGE.agc | fc43ab512b9adce00b9dea4e25fd401c4581de4e6685f8558333c56a8751c444 |
| Luminary099/IMU_MODE_SWITCHING_ROUTINES.agc | 49bf6c8ecb8f185e19547fe4405d1270e70c15503c28f065199a2a6645e2e31e |
| Luminary099/FLAGWORD_ASSIGNMENTS.agc | a952d345daf80ebf2279f2ff81cc440beba3359980a1c72e426ddce4be41921d |
| Luminary099/THE_LUNAR_LANDING.agc | 3bbcc4c34d50456bcabf4c0eb6ebe427a3d28b56ed44b0e1ec7728c05d199b4d |
| Luminary099/BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc | 8be1bf0b0346dc3ac8efd2bccb113d6cbd46dd9c22f716266cbaf4e3c1ce94d4 |
| yaAGC/agc_engine.c | 9c59728cdd968503caaaafe50a18ab3ed841f6176da3299c137f3a6a158fcbef |
| yaAGC/agc_engine.h | 8faf37332826692acbfba6fa211d94439b0868800545e9cda6941454086450c2 |
| yaAGC/SocketAPI.c | 3996697e26e9b27678232182f1c742870d80aac4b760e42fc8310ffc6aa43f38 |
