# Independent review: final 0.50-radian Phase 10 candidate

**VERIFIED: COMPLETE AND VERIFIED for the bounded numerical Phase 10 goal.**
Original P51/P27/P63 executes, mission inputs are source justified, the cubic
has meaningful nonzero operands, original ROOTPSRS returns sensible countdowns,
and the original ignition-time iteration completes. This conclusion does not
include powered descent, propulsion response or operational pre-PDI readiness.

This review supersedes `runtime-review-final.*` **for candidate selection**.
Those earlier files accurately retain the intermediate 0.40-radian case and its
short lead-time limitation. Neither those observations nor the earlier
0.15-radian timing failure have been overwritten.

## Independent actual trace findings

Read the completed `.build/phase10/final-angle050-validation` batch. Final and
repeat are byte-identical, raw SHA-256
`6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2`.
`runtime-review-angle050.json` retains the independently counted checkpoints,
all raw-table coefficient fractions, direct operand-formula errors, returned
roots, iteration counts, residuals and comparisons.

The final run records nine ROOTPSRS calls, nine ROOTSTOR_RESULT successful
continuations, nine QUADGUID entries, three DDUMCALC entries and one IGNALGRT
return. All cubic coefficient tables agree with independent arithmetic on the
actual observed operands to within **0.75 DP least-significant bits**.
Iteration counts are `3,1,1,2,1,1,1,1,1`. Maximum independently evaluated
normalized residual magnitude is approximately **1.56e−7**, with nonzero
derivatives. The last stored countdown is **−582.79472168 seconds**.
There is no BADROOT or 01406 path in this initialized run.

At actual IGNALGRT, call **18,880,712**, TIG is **360.29 seconds** and the
clock is **221.26 seconds**. Ignition is therefore **139.03 seconds in the
future**. Published ZOOMTIME is actually loaded as 2600 centiseconds. The
final display is original V06N61. No crew input proceeds beyond that boundary.

The 16 km altitude variant changes the first original coefficient table and
the original root. The missing-site control retains partial successful root
execution followed by genuine BADROOT/01406, without IGNALGRT. All **4098
protected prior files** remain unchanged. These controls support actual input
causality and preserve the originally observed failure rather than masking it.

## Exact later scheduling constants and limits

`angle050-scheduling-source.txt` preserves the original source for the later
path; its JSON companion independently reads the immutable rope words:

| Constant | Actual octal words | Decoded value |
|---|---|---:|
| D29.9SEC | `00000 05656` | 2990 centiseconds |
| TIMEDELT | `00000 03720` | 2000 centiseconds |

Original BURNBABY/P41SPOT sets `TDEC1=TIG−D29.9SEC` before MIDTOAV1.
MIDTOAV1 compares that target with `current time+TIMEDELT`; its NOTIME path
raises 01703 when integration cannot meet the requested time. At the observed
IGNALGRT clock, the later target would be **109.13 seconds ahead**, exceeding
the original 20-second allowance by **89.13 seconds**. This is a source-derived
independent scheduling sanity check, not execution of that later path.

The actual later crew response, R51 choice, attitude maneuver, scheduling
check, BURNBABY, engine ignition and thrust were **NOT RUN**. Delays in those
steps could still consume the margin. No claim is made about them, complete
flight padload, calibrated physical alignment, PIPA/radar feedback, P64/P66 or
landing. The verified result is authentic, reproducible numerical guidance
from a coherent explicitly synthetic mission state.
