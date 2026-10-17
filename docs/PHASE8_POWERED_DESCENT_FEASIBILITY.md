# Phase 8 — Powered-Descent Feasibility Assessment

**Outcome: B (blocked).** Authentic AGC-controlled powered descent cannot be shown with the current fixture.

- **VERIFIED:** with the IMU genuinely usable, Luminary 099 accepts **V37E63E** (MODREG = 63). R02 then raises **00220** because REFSMMAT is not valid. The AGC goes no further into landing guidance.
- During V37 handling the AGC itself wrote the THRUST counter (067777) and pulsed channel 014 bit4 (word 070010). Nothing in the simulator consumes that throttle output, and no descent guidance ran.

Powered descent is **NOT RUN**.

## 1. Audit of the current control path
| Item | Status | Evidence |
|---|---|---|
| AGC execution, fresh reset, Luminary 099 rope | VERIFIED | Phases 1, 5–7 |
| IMU readiness (OPERATE asserted; ISSUP clears IMODES33 bit6) | VERIFIED | PHASE5 §, this probe: IMODES33 = 036000 at selection |
| RCS commands → model → CDU feedback (yaw, pitch) | VERIFIED | Phases 6–7, byte-identical re-check |
| Descent engine / throttle interface | NOT PRESENT in fixture | THRUST = erasable counter 055 written by THROTTLE_CONTROL_ROUTINES:120–138, with channel 014 bit4 drive (Phase 2 §). The Tcl descent thrust is a GUI slider (AGC_Simulation_Monitor_Control.tcl:151–205), not AGC-driven |
| Translational dynamics / PIPA | PARTIAL | The Tcl model has `modify_pipaXYZ` for RCS translation only. It has no lunar gravity, no descent-engine thrust and no state vector |
| Landing radar | NOT PRESENT | P20-P25 selects via channel 013; the yaAGC API radar hooks are empty (Phase 2 §) |
| Mission initialization (state vector, REFSMMAT, TLAND, RLS) | NOT AVAILABLE | No Luminary 099 pre-PDI erasable load exists in the pinned repo (Phase 2 §) |

## 2. Authentic descent path (source references from Phase 2 evidence)
1. **Entry.** V37 MM63 → `P63LM` (FRESH_START_AND_RESTART.agc:748–794). It calls `R02BOTH` first (THE_LUNAR_LANDING.agc:47–80).
2. **R02 check.** R02 requires REFSMFLG (FLAGWRD3 bit13). Otherwise it raises alarm 00210 or 00220, selected by IMODES30 bit9, then VARALARM → GOTOPOOH (IMU_MODE_SWITCHING_ROUTINES.agc:917–935).
3. **Ignition estimates.** These need the integrated CSM/LM state and epochs, REFSMMAT, `RLS`, `TLAND` and lunar parameters (THE_LUNAR_LANDING.agc:84–207).
4. **Outputs.** Descent guidance produces:
   - throttle via the THRUST counter + channel 014 bit4
   - engine on/off via channel 011
   - trim gimbal
   - RCS commands
   - phase transitions to P64/P66 via WCHPHASE and MODREG
5. **Inputs.** It consumes:
   - PIPA delta-V (counters 037–041)
   - CDUs
   - landing radar (RNRAD 046 via channel 013 selection)
   - crew switches

## 3. Bounded experiment (executed)
- **What it adds.** `docs/phase8-evidence/p63_probe.py` reuses the Phase 5 `plant_bridge.c` and `operate_inputs.txt` unchanged. It adds only the keys V37E63E at 3,000,000 CPU calls (channel 015 codes 17,3,7,28,6,3,28; 21,333-call spacing) and runs to 4,600,000 calls.
- **Integrity.** No RAM writes and no flag forcing. No CDU feedback was connected, because no motion was required for this program-selection test.
- **What it records.** It reads back MODREG, FLAGWRD3, IMODES30/33, THRUST, FAILREG, and every output on channels 011–014.

Results (VERIFIED, `runs/p63.jsonl`; a fresh replay was byte-identical):
- All seven key inputs were accepted.
- At call 3133969, MODREG goes 077777 → **077** (P63 selected).
- At call 3135675, FAILREG = **01520, 00220, 0**. 01520 is the known Phase 5 alarm; **00220 is the R02 alarm for REFSMMAT not valid.**
- FLAGWRD3 = 02000 (REFSMFLG bit13 clear). IMODES30 = 037001, IMODES33 = 036000.
- THRUST counter (055) changes exactly twice: 0 → 077777 at call 491517 (startup), then → **067777 at call 3130557**, during V37E63E processing and before the R02 alarm.
- Channel 014 bit4 (THRUST drive) occurs exactly twice: word 00010 at call 495 (startup), then **word 070010 at call 3129803**, alongside the V37 processing.
- **ASSUMED / not decoded:** that this is a throttle reset made during program change. The writing routine was not traced; that source is not retained in the evidence. It is an authentic AGC throttle-interface output, but not descent guidance.
- No engine-on command was identified on channel 011, which carried only DSKY/status-type words (020000/020002/020040/020042).
- `test_p63_probe.py`: **7/7 tests passed** (`runs/tests.log`). An initial run failed 2/7: my first assumption was that THRUST and channel 014 bit4 were untouched, and the trace contradicted it. The tests and this report were corrected to match the recorded trace.

Interpretation: a usable IMU is necessary but not sufficient. Even with real readiness, the original software refuses descent because the platform has no valid alignment matrix. The blocker is now one precise step later than in Phase 2, where the IMU itself was not operating.

## 4. Minimum physics and interfaces still required (ASSUMED requirements, from source)
1. **Valid alignment.** Either run the authentic alignment programs (P51/P52) against a synthetic star/platform model, or load a source-justified REFSMMAT plus state vector through an existing uplink/erasable-load mechanism, with its provenance documented.
2. **Throttle plant.** Trace the routine that wrote THRUST at V37 (observed above), then read the THRUST counter pulses and channel 014 bit4 as the AGC emits them, and convert them to thrust in the plant.
3. **Translational dynamics.** Point-mass motion with lunar gravity, descent thrust along body X, and mass/fuel use. Return PIPA counts to counters 037–041. RCS, CDU and attitude are reused from Phases 5–7.
4. **Landing radar.** Model altitude and velocity from the plant state, answering the channel-013 radar selection with RNRAD counter pulses. Radar is not needed before about the P63 midpoint; a bounded experiment can stop before radar acceptance.
5. **Clean initialization.** Isolate 01520 and the earlier 01107 alarm.

A full terrain or landing simulation is not required for a bounded first descent test.

## 5. Not run
- Alignment / REFSMMAT
- State-vector load
- Ignition
- Throttle response
- PIPA feedback
- Radar
- P64/P66
- Landing
- WASM

## 6. Reproduce
```
python3 docs/phase8-evidence/p63_probe.py OUT/engine.so OUT/p63.jsonl   # engine.so built as in PHASE7 §7
cd docs/phase8-evidence && python3 test_p63_probe.py
```

## 7. Preservation
- Only new files were added: this report and `docs/phase8-evidence/`.
- Phase 1–7 files were not modified. `prior_hashes.json` records SHA-256 hashes of the pre-existing `docs/` files.

## 8. Recommended next milestone (Phase 9, not started)
Obtain a valid REFSMMAT through the authentic route: drive P52 (or P51) with a source-verified synthetic optics/star interface, so the original software sets REFSMFLG itself. The pass condition is V37E63E passing R02 (reaching `R02ZERO`/`R51P63`) without flag writes. Only then add the throttle/PIPA plant.
