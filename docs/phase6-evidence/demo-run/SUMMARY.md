# Recorded demonstration summary

**VERIFIED — native single-axis feedback demonstration; not a landing.**

| Run | Model peak yaw °/s | Model final X ° | AGC CDU X | Sensor generated / delivered |
|---|---:|---:|---:|---:|
| closed | 4.859385 | 16.841562 | 1533 | 1539 / 1539 |
| feedback_off | 11.341167 | 177.686497 | 0 | 16173 / 0 |
| repeat | 4.859385 | 16.841562 | 1533 | 1539 / 1539 |

## Connected event trace (decimal CPU-call indices; octal channel words)

- controller_input: call 2500000, raw line 4302: `{"ev": "input", "cycle": 2500000, "channel": 25, "value": 12283, "accepted": 4}`
- first_nonzero_rcs: call 2509125, raw line 4348: `{"ev": "output", "cycle": 2509125, "channel": 6, "value": 85}`
- first_motion: call 2509384, raw line 4350: `{"ev": "plant", "cycle": 2509384, "omega": [0.014968681222858068, 0.0, 0.0], "gimbals": [4.5437132478361206e-05, 0.0, 0.0], "jets": [0, 85], "zero": 0}`
- first_sensor_request: call 2514502, raw line 4373: `{"ev": "sensor", "cycle": 2514502, "origin_interval_end": 2514502, "counter": 26, "code": 1, "delivered": true, "accepted": 4}`
- first_cdu_readback: call 2515355, raw line 4377: `{"ev": "sample", "cycle": 2515355, "imodes33": 15360, "cdu": [1, 0, 0], "failreg": [848, 0, 0]}`
- first_opposite_jet_word: call 2705321, raw line 6028: `{"ev": "output", "cycle": 2705321, "channel": 6, "value": 170}`

Actual channel006 word00125 selects positive-yaw jets in this model; word00252 selects opposing jets. The latter occurs in the connected run and not the feedback-disconnected run.

Categorized traces separate AGC outputs, simulated vehicle, simulated sensors and diagnostic readbacks. Sensor delivery and model-origin timestamps are distinct; rows are not globally time-sorted.

**ASSUMED:** synthetic LM-7 dynamics, zero initial rates/gimbals, operate-only hardware fixture. Semi-implicit integration; at most853 CPU calls per coupling chunk; sensor delivery at chunk end; counter queues not drained.

**NOT RUN:** historical calibration, complete IMU alignment/REFSMMAT, clean mission initialization, cold-start01107 isolation, general three-axis control, coupled WASM, throttle/radar, powered descent, landing, UI, multiplayer or AI crew.

Readiness instruction proof is retained in Phase5, not rerun here. The schedule retains V36E, prematurely requested V37E00E (01520; not P00), and V77E. This is not alarm-free mission readiness.
