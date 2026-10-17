# Phase 12 descent-engine source investigation

This document records source findings, not native execution success. The pinned
Virtual AGC revision is `f577e3fd917866c59334e6cdd32504f09df76f60`.
All original-source line numbers below refer to that revision. SHA-256 values
for the examined files are in `mapping.json`. The original Luminary rope,
CPU semantics and previous evidence are not changed by this investigation.

## Authentic hardware interface — VERIFIED in original source

All addresses and masks in this section are octal. A bit number is one-based.
The machine-readable version is `mapping.json`.

| Signal | Location | Meaning |
|---|---|---|
| Engine ON | Channel 011, bit 13, mask 010000 | Original computer's engine-on output |
| Engine OFF | Channel 011, bit 14, mask 020000 | Original computer's engine-off output |
| Thrust drive activity | Channel 014, bit 4, mask 000010 | Requests hardware servicing of the signed throttle delta |
| THRUST | Erasable counter 055 | Signed incremental throttle count; not an absolute throttle percentage |
| Engine armed | Channel 030, bit 3, mask 000004, active low | Crew/hardware input; separate from engine-on output |
| Automatic throttle | Channel 030, bit 5, mask 000020, active low | Computer throttle control selected |
| PGNCS control | Channel 030, bit 10, mask 001000, active low | Computer rather than AGS control |
| Automatic attitude mode | Channel 031, bit 14, mask 020000, active low | Automatic stabilization selected |

Sources: `INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:58–75,115–120,148–163,175–189`;
`ERASABLE_ASSIGNMENTS.agc:149`; `R60,R62.agc:232–243`.
Engine arm and mode inputs are supported physical switch signals. Supplying
these inputs does not justify writing internal software flags.

### Throttle counter handshake

The upstream ringbuffer interface recognizes a counter operation when packet
channel bit `0x80` is set (`yaAGC/ringbuffer_api.c:128–139`). The lower seven
bits select the genuine erasable counter. For THRUST the packet channel is
`0x80 | 055 = 0255` octal (173 decimal). A DINC operation has value 4 decimal;
`UnprogrammedIncrement` masks the counter address and dispatches DINC to the
unchanged original `CounterDINC` (`agc_engine.c:1570–1606`). This is not an
ordinary channel write and must not be modeled as assigning erasable 055.

`CounterDINC` (`:1278–1311`) diminishes a signed one's-complement value toward
zero. For a positive value it emits POUT `015`; for a negative value it emits
MOUT `016`; for either signed zero it emits ZOUT `017`. The output pseudochannel
is again `0x80 | counter`. These output values mean discrete signed pulses,
not thrust magnitudes. A positive POUT raises the external DECA accumulator;
a negative MOUT lowers it. ZOUT ends that drain operation. The final nonzero
count first produces a real pulse; the following operation reports zero.

The pinned engine does not automatically clock the descent THRUST counter.
Its internal `BurstOutput` is restricted to the three IMU CDU command counters
(`agc_engine.c:1630–1659`); the automatic call sites at `:2397–2422` concern
only those CDU drives. External hardware simulation must therefore schedule
source-supported DINC events. An adapter must consume genuine DINC outputs,
not replace them with invented throttle packets. `CpuWriteIO` always emits the
output packet (`agc_engine.c:603–659`), even if the channel value is unchanged.
Consequently a new bit-4 output write can start another command after ZOUT;
a rising-edge-only detector would incorrectly miss subsequent commands.
CounterDINC does not clear channel 014. The later primary hardware manual
confirmation below justifies clearing only its bit 4 after a genuine ZOUT;
this is a documented hardware completion event, separate from CPU output.

`THROTTLE_CONTROL_ROUTINES.agc:130–150` writes the signed command into THRUST,
sets channel 014 bit 4 and states the drive rate as 32 units per centisecond,
which is 3,200 pulses per second. Hardware event spacing must be derived from
AGC cycle time with an explicit deterministic rounding rule. One MCT is
12/1024000 s; the exact pulse period is 80/3 MCT, for example event n at
`start + ceil(n*80/3)` with a disclosed phase convention. Ringbuffer
counter operations preserve their CPU timing cost; see `NullAPI.c:98–154`.

### Original command producers

* `P40-P47.agc:476–496`, ENGINOF3, clears the original engine-on flag, writes
  the engine-off channel pattern and sends THRUST = −4096 with thrust drive
  enabled. This resets automatic throttle. It is not positive engine thrust.
  The comment distinguishes the computer's reset on engine-off from the
  physical hardware reset when disarmed.
* `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:423–438`, IGNITION, sets
  the original engine-on flag, clears the two engine-control output bits,
  asserts bit 13 and records the event time. An armed hardware plant is a
  separate prerequisite; the output alone does not prove physical ignition.
* `THROTTLE_CONTROL_ROUTINES.agc:197–204`, FLATOUT, sends +4096 pulses through
  the same DOIT path. This deliberately saturating throttle-up command must
  not be converted into 4096 percent or treated as a guidance acceleration.
* `THROTTLE_CONTROL_ROUTINES.agc:41–54,121–138`, THROTTLE, computes present
  thrust FP from measured acceleration ABDELV and mass, requested thrust FC
  from guidance acceleration `/AFC/` and mass, and an incremental command PIF.
  Nonlinear-region logic and previous-command lag compensation are genuine
  original instructions. `MASSMULT:206–221` performs the force conversion.
* `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:810–837` gates throttle/steering
  outputs on STEERSW and absence of numerical overflow, then calls THROTTLE.
  Thus observing FLATOUT does not by itself establish recurrent
  guidance-computed throttle regulation.

`CONTROLLED_CONSTANTS.agc:132–135` defines FMAXODD = 3841 pulse units,
FMAXPOS = 3467, THROTLAG = 20 cs, and SCALEFAC's nominal force conversion
0.0797959872 pulse/N (about 12.532 N/pulse). These are the software's nominal
conversion/calibration values. They are not a complete measured engine map.
The physical minimum, saturation, response lag, mass and specific impulse
must remain separate model parameters with documented provenance.

## Legitimate P63 progression — VERIFIED in source; runtime result separate

The Phase 10 V06N61 endpoint is a review display, not an ignition demonstration.
The following source-controlled continuation is available:

1. The V06N61 crew response enters ASTNRET and R51P63. `THE_LUNAR_LANDING.agc:218–237`
   states that PROCEED performs fine alignment while ENTER returns to
   P63SPOT2. That branch computes POINTVSM and asks R60LEM for the burn
   attitude maneuver.
2. `R60,R62.agc:40–80,113–166` describes V50N18: PROCEED initiates the original
   automatic maneuver; ENTER accepts and returns. A stationary diagnostic
   fixture accepting that display must not be described as achieving the
   requested physical attitude. Its attitude uncertainty remains explicit.
3. P63SPOT3 checks channel 033 bit 6 for landing-radar antenna position 1.
   If missing, V50N25 code 00500 requests antenna positioning. PROCEED checks
   again; ENTER goes to SETPOS1 (`THE_LUNAR_LANDING.agc:243–261`). A supplied
   switch indication describes only antenna position, not radar measurements.
4. BURNBABY invokes P40AUTO. `BURN…agc:911–934` checks PGNCS control,
   automatic attitude mode and automatic throttle; V50N25 code 00203 asks
   for those modes. Only supported crew inputs can meet this gate.
5. BURNBABY issues the ENGINOF3 reset. P41SPOT/P63SPOT initializes navigation
   to TIG−29.9 s and reaches the scheduled average-g/PIPA path
   (`BURN…agc:167–240,301–352`). This legitimately differs from the Phase 10
   pre-ignition review endpoint and must be observed, not assumed.
6. The countdown produces V99 at TIG−5 s. `*PROCEED:823–826` sets ASTNFLAG
   using original software and enters IGNITE; `IGNYET?:417–421` checks this
   response at TIG. Normal original IGNITION then emits ENGINE ON.
7. P63ZOOM is scheduled for nominal TIG+ZOOMTIME (`:399–415`). At that time
   `:573–578` switches AVEGEXIT to lunar landing guidance and calls FLATOUT.
   Later actual PIPA acceleration detection and guidance state decide whether
   THROTTLE executes. Neither countdown nor FLATOUT proves those later steps.

No program counter forcing, RAM flag assignment, readiness patch or fabricated
output is justified by this path. Unmet physical attitude or navigation
requirements must be reported rather than hidden by a crew acknowledgement.

## Physical plant and existing implementation boundaries

The pinned upstream LM simulator has an existing physical DPS calculation in
`Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl:163–188`:
it computes mass flow as thrust divided by effective exhaust velocity,
subtracts propellant mass, computes acceleration and passes a body +X velocity
increment to its IMU path. However its thrust is taken from a GUI slider and
its enable is a separate model variable. Reusing it without a validated AGC
engine command adapter would not establish authentic engine control.

The retained Phase 7 model adds quaternion/body angular dynamics in
`docs/phase7-evidence/physics/orientation.tcl`. This should remain the shared
attitude convention. Phase 11's `pipa_sensor.py` already handles full
reference-to-stable-member transformation and quantization. A bounded DPS
extension needs a small force/mass/translational-state layer, not a new
attitude or navigation controller. Zero trim is a model approximation;
full trim-gimbal, pressure, erosion and throttle hardware behavior are beyond
this experiment unless independently validated.

Physical force uses spacecraft body +X, transformed to reference coordinates
by the documented body orientation. Then `a_REF = g_REF + F_REF / m`, with
specific force `f_REF = a_REF − g_REF`. Existing Phase 11 sensor conversion
returns measurements to the AGC. Gravity-only motion produces no ideal PIPA
specific-force input. Original AGC navigation may still change velocity due
to its own gravity integration.

## Historical primary references and limits

[MIT R-567 GSOP Section 6, November 1968](https://www.ibiblio.org/apollo/NARA-SW/R-567-sec6.pdf),
6.4.6, describes DECA as a saturating accumulator, reset when disarmed, driven
at 3200 pulses/s; it includes engine delays and lag. The LM coordinate system
is described in 6.4.1. This is LM-6 simulator control data, not an exact LM-5
flight calibration.

[NASA, Apollo Lunar-Descent Guidance, throttle routine](https://www.nasa.gov/wp-content/uploads/static/history/alsj/ApolloDescentGuidnce.pdf)
explains approximately 12.5 N/pulse, a separate manual minimum and an upper
mechanical stop. Its discussion corroborates incremental control; the pinned
099 instructions remain authority for this binary's actual behavior.

[NASA TN D-7143, Apollo Experience Report—Descent Propulsion System](https://ntrs.nasa.gov/api/citations/19730011150/downloads/19730011150.pdf)
provides development and Apollo 11 flight background. No parameter in a
synthetic test is thereby labeled as a recovered Apollo 11 flight value.

## Read-only diagnostic quantities

Recommended observations are THRUST (1 word); PIF (2); PIFPSET (1);
PSEUDO55 (1); FC (2); FCODD (2); FP (2); FWEIGHT (2); FCOLD (1); TTHROT (1);
`/AFC/` (2, an alias of NORMEX); MASS (2); MASS1 (2); ABDELV (1);
ABDVCONV (2); PGUIDE (2); PIPTIME (2); and the existing navigation vectors,
REFSMMAT, program/verb/noun and flag snapshots. `/AF/` in throttle comments
is a conceptual measured-acceleration name, not a separate erasable symbol.
MASS and MASS1 use B16 kg (`AOSTASK_AND_AOSJOB.agc:278`,
`EXTENDED_VERBS.agc:1448–1453`). FP, FC and PIF represent force in pulse
units, with the high word carrying the integer part and the low word its
fixed-point fraction; THRUST receives the signed coarse count. They must not
be decoded as normalized absolute throttle. ABDELV is described as normalized
velocity magnitude in SERVICER and B13 cm/s² in AOSTASK; at the nominal
two-second PIPA interval one coarse count corresponds to 0.005 m/s².
ABDVCONV is explicitly B5 m/cs (`SERVICER.agc:200–207`).

For physical-engine parameter selection, DPSVEX in
`CONTROLLED_CONSTANTS.agc:101` gives a software nominal effective exhaust
velocity magnitude 2955.88868 m/s (the encoded sign supports the original
mass-decrement computation). A modern plant may choose a constant 3000 m/s
for a labeled synthetic test, but must not silently attribute that rounded
choice to the software or a flight-specific engine calibration.

## Modern adapter development observation

The first propulsion unit-test run produced 22 passes and one assertion
failure at an intentionally exact 0.02m/s sensor threshold: upstream binary
floating-point arithmetic made the force interval slightly smaller, so the
unchanged exact-rational Phase11 sensor produced one pulse and retained the
remaining fraction. This was a test-fixture precision issue, not an observed
AGC failure. The physical/sensor consistency test now uses 0.02048m/s, safely
between pulse thresholds, while retaining its exact two-pulse assertion.
No sensor rounding rule, old assertion or original software was modified.

## Implemented bounded physical adapter

`propulsion.py` and `legacy_engine.tcl` execute the **whole unchanged upstream
`dynamic_simulation` procedure**, using the same exact initialization slice as
retained `phase5-evidence/plant_server.tcl`. Source hashes are checked against
Phase6's corresponding-source manifest, and the Tcl runtime manifest is
validated using the repository's existing runtime validator. The original
procedure supplies force divided by preburn mass, mass flow using its 3050m/s
effective exhaust velocity, propellant depletion and body +X delta-v.

The wrapper captures the upstream delta-v instead of using that old simulator's
PIPA quantizer. The independently validated Phase11 PIPA sensor remains the
sole pulse quantization layer in this experiment. Zero angular rates are
explicitly enforced; existing Phase7 quaternion-matrix code transforms force
into the reference frame. No new attitude controller is introduced.

Only the missing translational state is added: central lunar gravity and
velocity-Verlet position/velocity integration, with thrust acceleration frozen
at the original procedure's preburn mass for each interval of at most 10ms.
This is a first-order mass-consumption approximation; an independent rocket-equation
convergence test quantifies its small-step behavior. Engine response
is instantaneous as in the reused upstream model: actual historical startup,
shutdown and throttle transport delays are NOT modeled. The unused upstream
initialization wall-clock variable does not enter the model calculations or
recorded results.

The external receiver separates the 3428-count saturating DECA accumulator
from a 45040N mechanical thrust stop and a 4560N manual minimum. The min/max
and 3050m/s values are inherited from the pinned simulator's stated LM-7
configuration. Applying the Luminary nominal pulse/N conversion to that
physical response is an explicit synthetic approximation. It is not an exact
LM-5/Apollo11 engine calibration. Manual lever modulation, trim-gimbal
response, changing attitude, propellant exhaustion, erosion and thermal or
pressure systems remain outside this fixture.

## Primary hardware completion confirmation and P00 partial reset

A later focused investigation obtained the original
[AGC Interface Specification, Block II, FR-2-130](https://www.ibiblio.org/apollo/Documents/agcis_30_block_ii_agc.pdf),
§30-103/104, printed page 30-67 (PDF page index 70). The retained page and
full-download hash are under `source/agcis-thrust-drive-*`. The manual says
THRSTD is generated while channel 014 bit 4 is set. Counter priority then
requests DINC for THRUST 0055; the signed pulse train continues at 3.2kpps
until zero, when genuine ZOUT clears the channel's drive bit. This confirms
level gating and the hardware completion latch operation. A software clear
also removes the gating level; an unfinished command must not continue by
assumption.

The pinned CounterDINC emits ZOUT without implementing that output-channel
latch clear. The external peripheral wrapper may consequently clear only
channel 014 bit 4 after receiving the genuine THRUST ZOUT. This is hardware
completion, not an Apollo instruction change, fabricated output packet,
THRUST memory assignment or readiness flag write. It must be logged as a
separate peripheral event, and read-only CPU snapshots taken before the clear
remain pre-completion observations.

The bounded P00 shutdown experiment has a different path: original ENGINOF3
writes THRUST=−4096 at cycle 28133493 and starts the negative drain. Seventeen
authentic MOUT pulses are emitted, then the original software clears channel
014 at cycle 28133962. The retained listing maps its context `05,3206` to
`FRESH_START_AND_RESTART.agc:478`, WAND CHAN14, preserving only BIT6. The
normal caller is P00's GOMOD→GOGOPROG→GOPROG2→STARTSB2
(`:901–909,293,437–478`). Engine OFF already exists at that point, but the
remaining THRUST counter is −4079. No ZOUT has occurred for that command,
and a model must not force it to zero to satisfy a drain assertion. The
external DECA counter can remain at 3411 while delivered thrust is zero.

A subsequent physical crew disarm is a separate, source-supported action:
R-567 §6.4.6.2 specifies that the automatic throttle counter is held at ground
state while disarmed. The existing active-low channel 030 bit 3 represents
that switch state. Such a disarm may reset the external physical DECA counter
without changing the remaining AGC THRUST word; both observations must be
recorded distinctly. It does not retroactively establish a complete P00
automatic-counter drain.

Independent review of `engine_bridge.c` confirmed that the completion clear
is restricted to actual output event channel 0255/value 017, masks only bit4,
emits a separate kind-5 latch event, and leaves the pinned CounterDINC and
Luminary instructions untouched. The loop separately stops when original
channel-014 output clears bit4. That honors the observed P00 interruption
without inventing extra negative pulses.
