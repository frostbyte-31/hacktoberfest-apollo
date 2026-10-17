# Milestone 3 — Corrected signed yaw feedback and queue settlement

17 October 2026. **VERIFIED** identifies source inspection or actual captured
execution; **ASSUMED** identifies synthetic fixture interpretation; **NOT RUN**
identifies unexecuted work. This is a single-axis modern model correction and
bounded feedback validation. Phase 7 has not started.

**Result:** the corrected model selects negative FAST operations at yaw-rate
magnitudes of 4°/s and above. Authentic Luminary RCS output drives the existing
external model; paced sensor requests reach actual CDU X memory without loss in
the tested cases. A separate cutoff experiment drains real pending work. These
results establish finite transport accounting and bounded response, not sustained
vehicle stability, historical hardware fidelity or descent readiness.

## Small correction, preserved baseline

The source-locked adapter changes the X/yaw selector in the original modern
`AGC_IMU.tcl`, line 527:

```diff
-     if {$Omega_Yaw < 4} {
+     if {abs($Omega_Yaw) < 4} {
```

It requires the complete original module's SHA-256
`4f63cf0954d4587ec6e983428d7e43d4473c11da72210444c2aa0ae4204e9c7e` and
creates a derived file in scratch. A separately disclosed public wrapper rejects
nonzero Y/Z increments before changing state. Pitch/roll selectors are untouched
and unsupported. No original source archive, emulator, flight software, earlier
report/evidence or Milestone 1–2 tool was edited.

Twenty-four paired component scenarios produce 1,014 state rows per model. All
numerical states, pulse counts and directions match. Exactly 1,455 operation
modes change at negative rates of magnitude at least 4°/s. The original raw
output remains byte-identical to Milestone 2. Four controls verify that Y/Z
increments fail before any gimbal, fed angle or packet changes. Quantization,
angle wrap and the original zeroing/lock inhibits remain intact.
[Adapter, exact diffs and component records](milestone3-evidence/model/README.md)
describe this prescribed-motion diagnostic separately from AGC-controlled motion.

## Coupled experiment

Each case starts a fresh native process and stationary synthetic LM-7 model.
The unchanged pinned ringbuffer engine executes the retained Luminary 099 rope.
The original Phase 5 plant server and procedures compute physics; the Milestone 2
read-only inspector exposes actual native queue state. New orchestration supplies
pacing, observations and explicit cutoff boundaries, without a second physics or
emulator implementation or flight RAM patches.

The delayed V37 sequence begins at call 1,600,000; V77 keys follow at 2,000,000.
At 2,200,000 the probe requires P00, zero FAILREG values and clear IMODES30/33
inhibit/initialization bits. V77 is recorded as a delivered key sequence; an
already-clear flag is not evidence of a new transition. The fixture retains the
original V36 fresh-start path and does not imply alarm-free cold power-on,
calibrated alignment, REFSMMAT or mission padload.

The retained negative RHC words are delivered at 2,500,000/2,500,001, then neutral
at 2,700,000/2,700,001. They use the source-justified negative yaw discrete and
one's-complement −20 controller word, rather than an imposed vehicle rate.
Actual channel 006 RCS words drive the original jet latches and synthetic
dynamics. Simulated sensor operations return only to X counter `032` octal.
Nonzero channel 005 jets, unsupported channel 006 bits, cross-axis motion or
counter changes, rejected packets and unaccounted CDU transitions fail the run.

The new fixture uses the exact engine convention, 12/1,024,000 seconds per CPU
call. Model intervals end at actual jet/zeroing changes or within 853 calls
(9.99609375 ms), using retained semi-implicit dynamics. Earlier rounded-clock
fixtures remain unchanged. Inspection on individual CPU calls does not add
physics integration steps.

The modern pacing policy allows one outstanding CDU request until its actual
application, with at least 214 calls between deliveries of slow requests or 14
for fast requests. A host FIFO preserves pending request order. This deliberately
conservative policy is not presented as historical sensor hardware or the
engine's maximum throughput. Generated, delivered, consumed, enqueued and applied
operations are observed separately; FIFO-head sign/rate, actual modular counter
deltas and deadlines corroborate application. Summaries are reconciled against
raw events, rather than accepted as proof by themselves.

## Measured outcomes

The primary cases end vehicle integration at call 4,000,000 (46.875 seconds).
Original and corrected selector runs use identical initialization, inputs,
clock, integration and pacing. Their trajectories diverge as feedback affects
the authentic controller; pulse totals need not match between trajectories.

| Case | Generated / applied | Negative FAST pulses | Peak host requests | Maximum recorded origin→delivery calls |
|---|---:|---:|---:|---:|
| Original selector, connected | 1439 / 1439 | 0 | 128 | 27351 |
| Corrected selector, connected | 1582 / 1582 | 691 | 5 | 710 |
| Corrected, feedback disconnected | 16169 / 0 | 16021 generated only | 0 | No deliveries |
| Corrected replay | 1582 / 1582 | 691 | 5 | 710 |

All connected requests were accepted, consumed, enqueued and applied, with zero
rejections or silent FIFO drops. Native FIFO occupancy never exceeded one
pending count, by design; the host peak of 128 is **not** native FIFO saturation.
The original selector generated 825 slow negative requests while rate was at
most −4°/s. The corrected selector generated none in that condition. Its 1,582
actual decrements end at CDU X 31,186; Y/Z remain zero.

“Origin” is the **end of a discrete integrated model interval**, not the
unobserved continuous quantum crossing. Origin→delivery maxima are about
320.52 ms original and 8.32 ms corrected. Origin→actual-application maxima are
27,565 and 925 calls respectively (about 323.03 and 10.84 ms); interval
quantization/coupling remains a separate limitation. These are measured fixture
delays, not total physical sensor latency or portable timing guarantees.

Corrected peak yaw magnitude is 4.8580°/s, establishing that the corrected branch
was exercised naturally. With the RHC still held, its real channel 006 output
changes to `00012` at call 2,568,700 and `00240` at 2,602,959; the disconnected
case continues issuing `00252` until neutral. Actual command sequences and model
response therefore depend on the feedback connection. The corrected final rate
is −0.03665°/s versus −10.8434°/s disconnected. This bounded observation is not a
stable-hold certification. Corrected and replay raw traces are byte-identical.

At the primary cutoff, host, input ringbuffer and native FIFO are already empty.
A fifth corrected case deliberately stops production at call 2,650,000, before
RHC neutral, with **three real pending host requests**. All 501 generated
requests apply; the final three drain by 2,650,047. Another 1,000 genuine CPU
calls leave queues empty and counters unchanged. After cutoff the plant and new
sensor production are explicitly frozen, while authentic AGC outputs continue
to be logged. This tail proves finite transport settlement; it does not evolve
or stabilize the vehicle. [Feedback protocol, raw captures and limitations](milestone3-evidence/feedback/README.md)
document both boundaries.

## Reproduction and actual checks

```sh
make test                  # recorded suites; Python 3.9+, make and cc; no downloads
make validate-milestone3   # locked Tcl, paired components, five fresh feedback cases
make check                 # all tests and all three milestone reproductions/probes
```

The final [`make check` record](milestone3-evidence/runs/2026-10-17-verified-check/commands.json)
ran from 14:51:10 to 14:52:08 UTC and exited **0**:

| Check | Actual result |
|---|---|
| Milestone 3 tests | 34 passed: 14 model, 20 feedback/evidence |
| Milestone 2 tests | 47 passed |
| Milestone 1 tests | 55 passed |
| Historical Phase 2–6 suites | 38 run: 35 passed, three known missing-log errors retained |
| Original feedback reproduction | Connected/disconnected/replay traces still byte-identical to Phase 6 |
| Fresh Milestone 2 probes | All original startup, transport and component validations pass |
| Fresh Milestone 3 probes | 24 paired component cases, four axis controls and five feedback cases pass |
| Prior evidence | All 1,135 tracked prior docs/tools/AGENTS files unchanged |

A zero command exit does not turn the three historical errors into passes. The
29 missing historical logs remain missing. Actual
[test records](milestone3-evidence/runs/2026-10-17-verified-check/milestone3-tests/results.json),
[feedback analysis](milestone3-evidence/runs/2026-10-17-verified-check/validation/feedback/summary.json),
[component checks](milestone3-evidence/runs/2026-10-17-verified-check/validation/model/validation.json)
and [preservation results](milestone3-evidence/runs/2026-10-17-verified-check/validation/preservation-after.json)
are retained. New raw feedback traces use lossless gzip plus uncompressed hashes.
The [retention inventory](milestone3-evidence/runs/2026-10-17-verified-check/retention.json)
identifies byte-identical prior traces by reference and records omitted scratch
source/build binaries by hash.

An interrupted first feedback attempt coupled physics to each inspection call;
its partial trace, source snapshot and termination record are retained and never
classified as a completed result. The final harness separates inspection from
physical integration. A component test-only path canonicalization assertion
failure and its successful rerun are also preserved.

Execution platform: macOS arm64, Python 3.9.6, Apple clang 21 and locked Tcl
8.6.16. Virtual AGC source remains
`f577e3fd917866c59334e6cdd32504f09df76f60`; rope SHA-256 remains
`1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
Host tools are recorded, not pinned; portable binary identity is not claimed.

**ASSUMED:** synthetic LM-7 rotational dynamics and operate-only stationary
initialization suffice for this bounded diagnostic. **NOT RUN:** sustained
attitude hold, general sign-symmetric trajectories, other axes, physical sensor
calibration, new WebAssembly comparison, historical mission initialization,
throttle/radar, powered descent or landing. A useful next single-axis question
is sensitivity to coupling/pacing and longer rate/hold acceptance criteria;
implementing another milestone requires separate approval.
