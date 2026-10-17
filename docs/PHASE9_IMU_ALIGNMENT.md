# Phase 9 — original P51 alignment and subsequent P63 readiness

2026-10-17 UTC. **VERIFIED: the feasibility objective succeeds in a synthetic
stationary instrument fixture.** Original Luminary 099 completes two P51
sighting pairs, computes REFSMMAT and sets REFSMFLG itself. A subsequent normal
P63 request passes the reference-matrix check that blocked Phase 8. It then
aborts with **01406** in the time-to-go root calculation. **Powered descent,
ignition, engine response and landing remain NOT RUN.**

VERIFIED below distinguishes source inspection and actual execution. ASSUMED
identifies the synthetic geometry and physical boundary. UNRESOLVED identifies
missing mission initialization. Addresses, channels, masks and alarms in prose
are octal; CPU-call counts and JSON integers are decimal.

## Baseline and preserved evidence

Reviewed the Phase 1–8 reports, roadmap, original Phase 5 startup/probe, pinned
engine transport, Phase 7 integration conventions, later live adapter and
associated tests. No earlier report, evidence, emulator, flight instruction,
application code or existing assertion changed. Root `roadmap.md` records the
new results; application development was not extended.

Execution base was `d8969a456cf59ae6873aea42bc2e480e84adae3a`, `main`, with the
new Phase 8/9 files identified by actual execution hashes. Before final Phase 9
runs, `phase9-evidence/prior_hashes.json` froze **3,393** prior tracked
documentation, tooling and application files, including the independently
completed Phase 8 package. Before/after checks have **zero mismatches**.
Phase 8 is preserved independently and does not depend on this alignment work.

Pinned Virtual AGC revision: `f577e3fd917866c59334e6cdd32504f09df76f60`.
The original archive was re-fetched from its pinned codeload URL and matched
SHA-256 `1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267`.
Original yaYUL assembled unchanged Luminary to the retained 73,728-byte rope,
SHA-256 `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
Two clean builds reproduced the rope, listing and all **7,104** parsed symbols.
The original possible-bank-overflow warning remains recorded; fatal errors and
unresolved symbols were zero. Binary `.symtab` embeds output paths, so portable
byte identity for that debug artifact is not claimed.

The new source setup checks **359** selected source/license files against the
verified archive before and after assembly. Each final execution verifies the
archive, cached sources, rope, actual listing and derived observer symbols
again. Changed inputs are rejected without repair. The retained 27-file source
selection also matches pinned Git blob identifiers and SHA-256 fingerprints.

## Original program logic and the missing interface

`P51-P53.agc:1019–1119` defines P51: IMUCHK, alignment-choice prompt, NCOARSE,
two AOTMARK sightings, CHKSDATA, AXISGEN, MATMOVE and original SET REFSMFLG.
IMUCHK requires an operating IMU; it does not require an existing REFSMMAT.
`INFLIGHT_ALIGNMENT_ROUTINES.agc:135–136` begins P52 with R02BOTH, so P52 cannot
independently remove the initial invalid-reference-matrix condition. P52
execution itself is **NOT RUN**.

P63 calls R02BOTH before its landing initialization. The original check in
`IMU_MODE_SWITCHING_ROUTINES.agc:917–936` tests FLAGWRD3 bit13. Clear validity
with an operating IMU produces00220; valid state returns to P63. No driver
writes to FLAGWRD3, REFSMMAT, AGC erasable memory or software readiness flags.

**VERIFIED transport limitation:** neither pinned `ringbuffer_api.c` nor
`SocketAPI.c` raises interrupt6 when receiving channel016. A normal mark packet
alone therefore cannot enter the original MARKRUPT. The original channel-bit
descriptions identify X/Y marks and interrupt6; `INTERRUPT_LEAD_INS.agc:65–68`
routes KEYRUPT2 to MARKRUPT.

The new external `hardware_bridge.c` includes the unchanged Phase 5 bridge.
The driver first queues a real channel016 packet, observes actual receipt, then
asserts **only `State.InterruptRequests[6]`**, once per mark pulse. It guards the
actual mark word and pending latch. Release is a normal zero packet without a
new interrupt. Original MARKRUPT samples actual CDU counters/time and performs
all sighting processing. No engine instruction semantics or original transport
source changed. This is explicit delivery of a documented hardware event, not
a synthesized software sighting or fabricated AGC output.

## Exact experiment

The exact Phase 5 startup packets before call2,200,000 are reused, including
the original V36E, early rejected V37E00E, V77E and operate-only IMU discretes.
The legacy **01520** remains; no later clean-start schedule is substituted.
The subsequent Phase 5 RHC motion experiment is not part of this stationary
alignment fixture. All CDUs remain zero; no counter or inertial data is injected.

The event-driven driver observes genuine channel010 relay displays, reusing
the retained Phase 1 decoder, before responding:

1. Send `V37E51E`. At V50N25/code00015, send original `V33E` to use the existing
   zero-gimbal condition through P51's supported proceed path.
2. At V01N71, use `V21N71E00701E` for detent7/catalog star01, then V33E.
3. At V06N87, request `V24N87E`. Original ABLOAD displays **V21N87** for AZ,
   then **V22N87** for EL. Enter `+00309E`, then `+06103E`, observing each prompt.
4. Proceed to V54N71; deliver channel016 X=4 and Y=8 with their documented
   interrupt6 events and explicit zero releases. Observe original pair completion.
5. Repeat for star02/code`00702`, with fields `+15088E` and `+06911E`.
6. At original V06N05 star-separation review, send V33E. Observe original
   REFSMMAT changes and REFSMFLG set, then issue normal `V37E63E`.
7. Observe a bounded additional400,000 CPU calls; retain the actual next alarm.

Keys use original channel015 codes and 21,333-call spacing. N71 fields are
five-digit octal; N87 fields have a sign and exactly five decimal digits.
`PINBALL_GAME__BUTTONS_AND_LIGHTS.agc:1816–1824,1889–1890` explains V24's
component prompts. Raw input packets, display transitions and native readbacks
are retained. Schedules are cycle-driven, independent of host/socket timing.

**ASSUMED geometry:** catalog stars01/02 and COAS-mode detent7 provide a
non-collinear synthetic line-of-sight pair. OANB computes
`(sin(EL), cos(EL) sin(AZ), cos(EL) cos(AZ))`. N87 directions change between
sightings while the spacecraft/CDUs remain stationary. This is a numerical
instrument fixture, not a model of fixed COAS mounting, optics mechanics,
spacecraft slewing or historical Apollo observations. Software validity is not
calibrated physical alignment or a validated flight mission state.

## Actual native results and causal controls

| Observation | CPU call / result |
|---|---|
| Original MARKRUPT entries / completed star pairs | 4 / 2 |
| First native REFSMFLG set | 4,759,831 |
| Flag-setting CPU instruction | bank01,Z2554, original interpreter TS STATE |
| Interpreter context | LOC03562, BANKSET030005, POLISH01462, SWBIT10000, SWWORD3 |
| P63 R02 entry | 4,895,158 |
| Success continuation bank32,Z3002 | 4,895,231 |
| ROOTPSRS entry | 4,959,517 |
| ROOTLOOP observations | 9 visits, MODE0 through8 |
| BADROOT / 1406POO | 4,967,600 / 4,967,606 |
| FAILREG gains01406 | 4,967,636 |
| Final FAILREG / MODREG | `[01520,01406,00000]` / decimal63 |

The interpreter context identifies bank14,3562: the original REFSMFLG operand
immediately after P51G's SET/EXIT word. Fourteen observed value changes populate
the 18-word REFSMMAT before the validity transition. Unchanged zero entries are
not counted as observed writes. This is stronger evidence than a final success
message; basic CPU checkpoints are not misrepresented as execution of
interpretive operand labels.

P51's original completion requests a major-mode change through GOTOPOOH. At the
alignment readback MODREG is still51; the driver then requests P63. A clean P00
acceptance or complete mission initialization is **not** claimed.

The final and fresh-process replay are **byte-identical**, raw SHA-256
`343419a500fdcf9d548fabdc6eba4805a72490d72161e23153461fa31a3e7128`.
The disconnected-interrupt control receives mark packets but has zero native
MARKRUPT entries, no accepted pair, zero REFSMMAT and clear REFSMFLG. Thus the
external documented event is necessary; channel metadata cannot substitute for
original sighting execution. Extended read-only observers also preserve the
prototype's exact actual input/output packets and timestamps.

## Next genuine blocker:01406

**VERIFIED source and runtime:** `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:496–528`
builds a cubic time-to-go problem and calls ROOTPSRS. The final trace captures
four DP coefficients at TABLTTF offsets0,2,4,6, all zero. RLS, TLAND, RN and VN
are zero; RGU/VGU contain only positive/negative zero. The initial guess and
DXCRIT are zero. No mission state vector or padload was supplied.

The trace directly records nine BUFZERO→DVOVF paths inside this root-solving
interval, maximum DP corrections, ROOTLOOP MODE0–8 and BADROOT at MODE8.
Original interpreter division handles the zero divisor by saturation. ROOTPSRS
tests MODE bit4 and returns through BADROOT; observed visit count is reported
instead of treating its rounded eight-pass header comment as execution evidence.
WCHPHASE is one's-complement−1 (77776), selecting abortive1406POO, rather than
the later in-flight nonabortive1406ALM path.

This establishes the degenerate numerical problem and genuine abort path.
**UNRESOLVED:** which complete revision-specific mission initialization and
physical/navigation conditions should replace this diagnostic fixture. It does
not establish that supplying any single invented datum would make descent valid.
No coefficients, state vectors, flags or original checks were patched.

## Reproduction, tests and evidence

Python3.9+, `cc` and `make`; no Nix, Tcl, frontend or engine plant is needed.

```sh
python3 -B docs/phase9-evidence/prepare.py --cache .build/phase9/dependencies
# Or append --archive /absolute/path/to/the/pinned.tar.gz for offline setup.
# Copy setupFile from the verified setup JSON:
python3 -B docs/phase9-evidence/validate.py --setup /absolute/path/to/setup.json
python3 -B -m unittest discover -s docs/phase9-evidence -p test_alignment.py -v
python3 -B docs/phase9-evidence/verify_integrity.py
```

Fresh outputs never overwrite evidence. Setup re-fetch implementation through
Python is **NOT RUN**; actual setup tests used the independently re-fetched and
verified archive. macOS arm64 was tested; other hosts remain **NOT RUN**.

Final actual results: **20 alignment checks,20 replay checks,15 disconnected
checks,2 comparisons;19 focused tests passed**. Phase8's ten tests and the
existing285 passes also passed: **314 passed,3 known historical missing-log
errors**, with no unexpected failures. `make check` freshly repeated the earlier
native demonstrations; backend/HTTP/frontend tests also ran. Four separate setup
integrity experiments passed. They are not added to the unit-test count.

Evidence is under `phase9-evidence/`: `runs/{final,repeat,mark-irq-off}`,
`validation/analysis.json`, `checks/`, `regression/`, `setup/` and `source/`.
`package-manifest.json` seals stored bytes; retention inventories additionally
identify raw/compressed hashes and omitted rebuildable files. All3,393 prior
files remain unchanged. Historical missing logs were not reconstructed.

Development attempt01 preserved a driver timeout caused by expecting V24 to
remain displayed; original V21/V22 behavior was correct. Later successful
development traces preserve their progressively expanded read-only observers.
The initial assembler NVER-quoting failure and negative integrity inputs are
also retained. Failed validation is never reclassified as flight success.

**NOT RUN:** physical IMU/optics calibration, P52 execution, valid pre-PDI mission
initialization, throttle-to-thrust plant, PIPA/navigation feedback, ignition,
P64/P66, landing radar, descent dynamics or landing. Stop here: the next task is
source-justified mission-state/geometry feasibility, not a Phase10 landing system.
