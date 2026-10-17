# Independent native trace review: development mission-15km-02

**VERIFIED development observations**, not the final Phase 10 validation.
The independently read input was
`.build/phase10/mission-15km-02/trace.jsonl`, raw SHA-256
`bb4ebf0d2fc362a88a4ecc227e44281c7db6ecf87a6aede6bc31e61b5f640b3b`.
The machine-readable review with configuration fingerprint and all root values
is `runtime-review-mission-15km-02.json`. Final run packaging must preserve
this development trace if it is cited; the `.build` path alone is temporary.

| Actual checkpoint | Observations |
|---|---:|
| Original P63 continuation after R02 | 1 |
| ROOTPSRS | 9 |
| ROOTLOOP | 12 |
| ROOTSTOR_RESULT continuation | 9 |
| QUADGUID | 9 |
| CGCALC | 9 |
| DDUMCALC | 3 |
| IGNALGRT | 1, at CPU call 18,340,935 |
| BADROOT / 1406POO | 0 / 0 |
| ASTNRET / P63SPOT2 | 0 / 0 |

The nine stored root results, in physical seconds, were approximately
`−396.230981, −396.252158, −396.252158, −588.428730, −588.437466,
−588.437466, −584.911650, −584.910967, −584.910967`.
Recorded Newton iteration counts were `3,1,1,2,1,1,1,1,1`.
These are actual original solver outputs; independent residual and overflow
checks are separate validation. Snapshots at ROOTSTOR_RESULT use the original
continuation after the root and iteration-count stores, rather than guessing
which internal state is available at first ROOTSTOR entry.

`DDUMGOOD` is an interpretive label, so zero basic bank/Z checkpoint matches
there do not imply it was skipped. Original `THE_LUNAR_LANDING.agc:175–207`
branches to DDUMGOOD only after the ignition correction falls within
`DDUMCRIT`; that path stores TIG, forms OUTOFPLN, then exits the interpreter
to IGNALGRT. The actual IGNALGRT observation, computed TIG and subsequent
countdown display demonstrate that the original ignition algorithm reached
its return path.

## What V06N61 means

**VERIFIED source:** original `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc`
lines 684–766 implement ASTNCLOK/STCLOK2, CLOKTASK and CLOKJOB. N61 is the
crew's event-timer review display reached from IGNALGRT. Its Proceed return
goes to ASTNRETN, which schedules ASTNRET (lines 812–820). The run supplied
no further crew input there, so it stopped before the subsequent original
alignment-choice workflow. This is a supported bounded stopping point.

`ASSEMBLY_AND_OPERATION_INFORMATION.agc:590–594` and original noun tables
define N61 registers as TTFDISP, TTOGO and OUTOFPLN. In particular CLOKJOB
computes **TTOGO = TIME2/TIME1 − TIG**, not TIG minus time. Increasing positive
R2 digits cannot be described as a countdown to future ignition.

## Timing defect in this development fixture

At the actual IGNALGRT observation:

- TIG words were `[77777,03245]` octal, a legal mixed-zero DP representation
  of **17.01 seconds** after AGC clock zero.
- The actual clock was **214.93 seconds**.
- Thus computed ignition was already **197.92 seconds in the past**.
- The final displayed R2 `03 23` agrees with time elapsed since that ignition;
  the horizon ended approximately 203 seconds after it.

The synthetic circular state at epoch 120 seconds and 0.15 radians behind the
landing direction was physically meaningful as a state vector, but the long
DSKY initialization completed too late for its computed ignition. This run
demonstrates original numerical guidance convergence, not operationally timely
pre-PDI setup. A revised synthetic initial along-track position or mission
epoch must be justified as a mission input and must yield a future TIG if that
stronger claim is made. Changing initialization data is preferable to forcing
the solver, flags, clock or ignition output.

## Another consumed padload to document

`ZOOMTIME` is explicitly a padload
(`ERASABLE_ASSIGNMENTS.agc:2109`). Original EXGSUB multiplies it by TRIMACCL
to obtain the trim-velocity correction, and DDUMGOOD subtracts it from the
integrated ignition estimate before storing TIG. This development config left
it at zero. Any final mission fixture must supply its published value or
explicitly justify zero as a synthetic instantaneous-throttle assumption;
it must not silently imply the entire relevant targeting padload was loaded.

No thrust, ignition, sensor-driven navigation, R51 alignment choice, P64/P66 or
landing is established by this trace. Final FAILREG remained only historical
startup `01520`; disappearance of 01406 is supported by the positive solver
and guidance continuations above, rather than merely by an alarm being absent.
