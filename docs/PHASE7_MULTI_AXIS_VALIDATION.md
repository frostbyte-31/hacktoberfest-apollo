# Phase 7 — Multi-Axis Attitude-Control Validation

**Outcome A: VERIFIED.** A reproducible second-axis (pitch) feedback loop was executed. The original Luminary 099 software produced the channel005 jet commands. The unchanged upstream LM model applied them, and the CDU Y counter returned the result to the AGC. Disconnecting that feedback changed the AGC's later jet commands. This is not powered descent, a landing, or general three-axis control.

## 1. What was reused (unchanged)
- `docs/phase5-evidence/plant_bridge.c`, `plant_server.tcl`, `operate_inputs.txt` (the verified OPERATE-asserted initialization), `docs/phase1-evidence/artifacts/MAIN.agc.bin`.
- Pinned engine and simulator: virtualagc `f577e3fd917866c59334e6cdd32504f09df76f60`, restored from `docs/phase6-evidence/corresponding-source.tar.gz`.
- New code: `docs/phase7-evidence/run_axis_loop.py`, a copy of the Phase 5 `run_loop.py` with three bounded changes:
  1. The controller pulse uses pitch instead of yaw.
  2. channel005 words are applied instead of rejected.
  3. All three CDU counters are delivered.
- Other new files: `analyze_axis.py` and `test_multi_axis.py`.
- The Phase 5/6 harnesses were not edited.

## 2. Interface mapping (source-traced)
| Item | Source | Finding |
|---|---|---|
| ch005 bits1-8 | AGC_Simulation_Monitor_Control.tcl:237-242 (Phase 4 trace) | Q4U Q4D Q3U Q3D Q2U Q2D Q1U Q1D |
| ch006 bits1-8 | same | Q3A Q4F Q1F Q2A Q2L Q3R Q4R Q1L |
| Model rotation | update_RCS, lines 231-299 | nv=(Q2D+Q4U)−(Q2U+Q4D), nu=(Q1D+Q3U)−(Q1U+Q3D), np from ch006. Omega_Yaw∝np, **Omega_Pitch∝(nu−nv)**, **Omega_Roll∝(nu+nv)** |
| Body→gimbal | AGC_IMU.tcl:660-692 Transform_BodyAxes_StableMember | (yaw,pitch,roll) increments are converted using the current gimbal angles. At zero gimbals: yaw→X/CDU 032, pitch→Y/CDU 033, roll→Z/CDU 034 (observed in traces) |
| Feedback | plant_server PCDU/MCDU requests → packet 0200\|counter | Codes 1/3/17/19 (slow/fast ±) |
| Hand controller | channel031 bits1/2 = ±pitch (bits3/4 = ±yaw, as used in Phase 5); counter 0166 pitch, 0167 yaw | Bit assignment ASSUMED from the Phase 5 yaw analogue plus the AGC response. The response is consistent: pitch-only jets appeared |

Units: rates in °/s and gimbals in degrees (Tcl model). CDU counters use AGC one's-complement counts (e.g. 32761 = −6). Time convention: 11.72 µs per CPU call.

Note on terminology: the model's pitch/roll come from ch005 U/D jet pairs. Any single U/D pair couples pitch and roll by construction. Pure pitch needs the AGC to balance nu = −nv.

## 3. Initial conditions
- Fresh `cpu_reset`, fresh Tcl model, zero rates and gimbals, no RAM writes.
- Phase 5 schedule; the only change is the pulse at 2500000/2500001:
  - channel031 = 027776 (+pitch) or 027775 (−pitch)
  - counter 0166 = 20 or 32747
  - neutral restored at 2700000/2700001
- Run length: 4,000,000 CPU calls.

## 4. Results (VERIFIED, from `docs/phase7-evidence/runs/`)
| Run | ch005 nonzero words | Peak pitch °/s | Peak roll °/s | Peak yaw | Final gimbals ° | AGC CDU [X,Y,Z] | Sensor gen/delivered |
|---|---:|---:|---:|---:|---|---|---:|
| closed | 59 | 4.236101 | 0.010390 | 0 | [0.0012, 18.8227, 359.9122] | [0, 1713, 32761] | 1720/1720 |
| feedback_off | 49 | 11.505120 | 0.006830 | 0 | [0.0273, 180.4363, 0.0055] | [0,0,0] | 16427/0 |
| negative | 61 | 4.236512 (opposite sign) | 0.011363 | 0 | [359.9991, 341.3657, 0.0301] | [0, 31071, 2] | 1701/1701 |
| repeat | identical to closed (byte-identical trace) | | | | | | |
| yaw_baseline (Phase 5 run_loop, unchanged) | SHA-256 9708a22c… = Phase 6 `demo-run/closed.jsonl` | | | | | | |

Connected chronology:
1. First AGC ch005 word 00022 (Q4D+Q2U) at call 2509765.
2. First pitch motion at 2509906.
3. First CDU-Y request at 2515355.
4. First AGC readback CDU Y=1 at 2516208.

The connected run contains balancing/opposing words (00151, 00041, 00110, 00001, 00011…) that are absent from or rare in the disconnected run. The disconnected run is dominated by 00226 (45×) and its pitch rate reaches 11.5°/s. Channel006 stayed zero in all pitch runs. The final FAILREG is 01520 in all runs (the same V37-during-init alarm as in Phase 5), and IMODES33 = 036000 (IMU usable).

Validation (`runs/validation.json`): all 11 checks passed. `test_multi_axis.py`: 10 tests passed (`runs/tests.log`). Environment: GCC 14.3.0, Tcl 8.6.16, Python 3.13.12.

## 5. Cross-axis effects
- **VERIFIED:** yaw rate is exactly 0 in every pitch run, and ch006 stays zero.
- **VERIFIED:** a small roll coupling appears (≤0.0114°/s). It comes from the unbalanced U/D pairs the AGC fired, and the AGC later balances it. A small CDU Z count (7 requests) reached the AGC. This is a property of the synthetic model's jet geometry. It is not checked against Apollo data.

## 6. Assumptions / limitations
- **ASSUMED:**
  - Synthetic LM-7 default dynamics.
  - Semi-implicit integration.
  - Coupling chunks of ≤853 CPU calls (~10 ms), with sensor delivery at chunk end.
  - The channel031 pitch bit assignment.
  - Not historically calibrated.
- **NOT RUN:**
  - Simultaneous multi-axis commands.
  - Roll-only test.
  - Large-angle gimbal cases.
  - Coupled WASM run.
  - Calibrated alignment/REFSMMAT.
  - Clean init (01520 present; 01107 not isolated).
  - Throttle/radar.
  - Powered descent and landing.
  - UI, multiplayer, AI crew.

## 7. Reproduce
```
tar xzf docs/phase6-evidence/corresponding-source.tar.gz -C /tmp/apollo/va
gcc -shared -fPIC -O2 -I/tmp/apollo/va/yaAGC docs/phase5-evidence/plant_bridge.c /tmp/apollo/va/yaAGC/{wasm.c,agc_engine.c,agc_engine_init.c,agc_utilities.c,ringbuffer_api.c,ringbuffer.c,rfopen.c} -lm -o OUT/engine.so
for m in closed feedback_off negative; do python3 docs/phase7-evidence/run_axis_loop.py /tmp/apollo/va OUT/engine.so OUT/$m.jsonl $m; done
python3 docs/phase7-evidence/run_axis_loop.py /tmp/apollo/va OUT/engine.so OUT/repeat.jsonl closed
python3 docs/phase5-evidence/run_loop.py /tmp/apollo/va OUT/engine.so OUT/yaw_baseline.jsonl closed
python3 docs/phase7-evidence/analyze_axis.py OUT
```
All runs exited 0.

## 8. Preservation
`docs/phase7-evidence/prior_hashes.json` fingerprints 1128 pre-existing files under `docs/`. Checking against the Phase 6 manifest found 0 mismatches. No Phase 1–6 file was modified.

## 9. Recommended next milestone
Simultaneous pitch+yaw (and roll-only) commands in the same bounded fixture. Check the roll channel and the cross-coupled gimbal transform at non-zero gimbal angles. Then isolate the 01520/01107 alarms for a clean initialization. Phase 8 was not started.
