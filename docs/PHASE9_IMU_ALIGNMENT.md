# Phase 9 — IMU Alignment and P63 Readiness (P51 / REFSMMAT)

Date: 2026-10-17. Scope: diagnose the Phase 9 blocker (PROCEED ignored at the
P51 V01N71 flash), correct only the driver, and determine whether Luminary 099's
original P51 two-star alignment can produce a valid REFSMMAT so that V37E63E
passes the R02 readiness check. No AGC memory writes, no forced flags, no
Luminary modifications, no bypassed checks.

## Result summary

- **P51 two-star alignment completed through the original software** — VERIFIED.
  REFSMMAT (erasable 01733, 18 words) was populated by P51's own AXISGEN/MATMOVE
  path (P51-P53.agc, P51G) and REFSMFLG was set by the original `SET REFSMFLG`
  (FLAGWRD3 bit 0o10000 observed transitioning 02000 → 012000 at cycle 15388427).
- **P63 passed the R02 readiness check** — VERIFIED. After P51 completed,
  V37E63E selected P63 (MODREG 077 octal = program 63) with **no alarm 00220**.
  The Phase 8 blocker is cleared by a genuine alignment.
- **P63 then aborted with POODOO alarm 01406** ("BAD RETURN FROM ROOTPSRS —
  IGNITION ALGORITHM") — VERIFIED and expected: descent targeting erasables
  (ignition state, target vectors) were never loaded, so the ignition
  algorithm's root solver fails. This is not a descent attempt and no descent
  is claimed.
- Star sightings were synthetic (catalog unit vectors from
  CONTROLLED_CONSTANTS.agc converted to AOT az/el by the documented OANB
  convention) and entered through the normal DSKY load verbs and the authentic
  AOT mark path (channel 016 mark bits + KEYRUPT2). Geometry fidelity of the
  synthetic sightings is ASSUMED; the software path is the original one.

## Root cause of the V01N71 PROCEED failure — VERIFIED

Two driver bugs, both in `alignment_probe.py` (the experiment driver), neither
in Luminary or the emulator:

1. **Wrong PRO bit.** The driver wrote channel 032 bit 15 (0o40000). Luminary's
   INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc states channel 032 **bit 14**
   (0o20000) = "INDICATES PROCEED KEY IS DEPRESSED", and T4RUPT's PROCEEDE
   monitors exactly that bit (off→on transition spawns PROCKEY → VBPROC →
   RECALTST → ENDIDLE wake). With bit 15, PROCEEDE never saw a transition, so
   PROCKEY never ran and the mark ENDIDLE was never woken: the display stayed
   at V01N71 forever. Corrected to 0o20000; the V01N71 PROCEED then advanced
   normally (verified in isolation and in the full run).
   - Side observation (ASSUMED, not fully traced): the spurious bit-15 writes
     in the earlier failed run coincided with V50N25 advancing once. Channel 032
     bit 15 is undocumented and inert in both the Luminary source readers
     (SERVICER RAND, T4RUPT PROCEEDE) and the emulator; the mechanism of that
     single advance is UNRESOLVED but irrelevant — it is not the PRO path and
     does not occur with the corrected driver.
2. **Angle field width.** `deg_str` used `f'{v:05.2f}'`, which yields only 4
   digits for |angle| < 100° (e.g. EL 56.54° → "+5654"). Pinball rejects a
   4-digit entry into a 5-digit CDU DEG field as incomplete: the ENTER is
   ignored, DSPLOCK stays set, and the V06N87 flash never re-establishes
   (observed as the alignment-02 EL stall). Corrected to `:06.2f` (5 digits);
   both AZ and EL loads then completed.

## Experiment runs (all preserved, each a separate file)

| Run | Outcome |
|---|---|
| `runs/alignment.jsonl` | Preserved original failure: PRO (wrong bit) ignored at V01N71; REFSMMAT zero. |
| `runs/alignment-02.jsonl` | PRO bit fixed; AZ loaded; EL load stalled on the 4-digit field bug. |
| `runs/alignment-03.jsonl` | Both sightings completed through marks; run ended before the post-star-2 display; REFSMMAT still zero. |
| `runs/alignment-04.jsonl` | Extended window; V06N05 mark-difference display observed; V37E63E during it → P63 selected, alarm 00220 (REFSMMAT still invalid because V06N05 was never accepted). |
| `runs/alignment-05.jsonl` | **Full success path**: V06N05 accepted → AXISGEN → REFSMMAT valid, REFSMFLG set → GOTOPOOH → V37E63E → P63 selected, no 00220 → ignition algorithm POODOO 01406 (uninitialized targeting data). |
| `runs/alignment-06.jsonl` | Exact replay of alignment-05: 2165 events, byte-identical (determinism check). |

## Key verified trace points (alignment-05)

- P51 entry via V37E51E; V50N25 PROCEED; per star: V01N71 (AOT code 00701 /
  00717 loaded via V21), V06N87 (AZ/EL loaded via V21/V22), V54N71 marks via
  channel 016 + KEYRUPT2, PROCEED to accept.
- Cycle 15388427: FLAGWRD3 02000 → 012000 (REFSMFLG set by P51G); REFSMMAT
  nonzero (see run file final sample).
- Cycle 18917344: MODREG 063 → 077 (P63 selected after V37E63E).
- Cycle 19003497: FAILREG1 = 01406 (ignition-algorithm POODOO). FAILREG0 =
  01520 is pre-existing from the unchanged Phase 5 startup (a V37 request
  rejected at cycle 1128851, long before P51 entry) — retained, not hidden.

## Files changed this session

- `docs/phase9-evidence/alignment_probe.py` — PRO bit 0o40000 → 0o20000;
  `deg_str` width fix; END extended to 24M calls; optional-flash step type;
  V06N05 accept step; MARKCNTR/STARIND sampling.
- `docs/phase9-evidence/runs/alignment-02..06.jsonl` — new run evidence.
- `docs/phase9-evidence/test_phase9_alignment.py` — 13 regression tests.
- `docs/PHASE9_IMU_ALIGNMENT.md` — this report.

No Luminary source, emulator, Phase 1–8 evidence, or UI files were modified.
Prior-evidence fingerprints: 1163 files checked, 0 mismatches, 0 missing
(`docs/phase9-evidence/prior_hashes.json`). The Milestone 1 missing-log
integrity failure is retained and untouched.

## Commands and tests

```
python3 docs/phase9-evidence/alignment_probe.py /tmp/apollo/p9.so docs/phase9-evidence/runs/alignment-05.jsonl
python3 docs/phase9-evidence/alignment_probe.py /tmp/apollo/p9.so docs/phase9-evidence/runs/alignment-06.jsonl
python3 docs/phase9-evidence/test_phase9_alignment.py   # 13 passed, 0 failed
```

## Classification

- VERIFIED: PRO = channel 032 bit 14; both driver bugs and their fixes; P51
  completing with REFSMMAT valid and REFSMFLG set through original code; P63
  passing R02 (no 00220); ignition-algorithm abort 01406; replay determinism;
  prior-evidence integrity.
- ASSUMED: synthetic star-angle geometry (catalog vectors → AOT az/el via the
  OANB convention); the mechanism of the one spurious V50N25 advance under the
  old bit-15 writes.
- NOT RUN: P63 ignition with valid targeting data, P64/P66, any descent or
  landing, throttle/radar coupling, browser/WASM variant of this experiment.
  No powered descent is claimed.
