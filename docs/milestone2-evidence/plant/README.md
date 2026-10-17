This is a **VERIFIED component diagnostic** of the pinned, unchanged Tcl yaw/X-gimbal path. Motion is imposed by the probe. It is not a new AGC-controlled vehicle demonstration, and it does not validate another axis.

The executable probe sources the retained `AGC_IMU.tcl` and `AGC_Simulation_Monitor_Control.tcl`; it does not copy their numerical algorithms. It intercepts only `write_socket` to record the operations that the existing model requests. Runtime validation reuses Milestone 1's Tcl source/install checks and requires Tcl 8.6.16. The source excerpts and SHA-256 values in `results/source-audit.json` are checked against Phase 6's retained inventory before execution.

The first actual execution completed with exit 0: 24 scenarios, 1,014 state rows. Its complete Tcl stdout, empty stderr, inputs, parsed packet trace, summaries, source audit, command record, and runtime manifest are retained in `results/`. The 16 component/evidence tests were run and passed. The project-level runner records its own later fresh execution and integrated tests separately.

The signed-rate finding is **VERIFIED**:

| Imposed yaw rate (degrees/second) | Pulses in 0.999716 seconds | Existing operation |
| --- | ---: | --- |
| +1 / -1 | 90 / 90 | PCDU / MCDU |
| +3.999 / -3.999 | 363 / 363 | PCDU / MCDU |
| +4 / -4 | 363 / 363 | PCDU_FAST / MCDU |
| +4.001 / -4.001 | 364 / 364 | PCDU_FAST / MCDU |
| +8 / -8 | 727 / 727 | PCDU_FAST / MCDU |

`AGC_IMU.tcl:527` compares signed `Omega_Yaw < 4`. Consequently every tested negative rate selects the slow operation, even at -8 degrees/second. Direction is determined separately by the signed X-angle residual: a negative delta with +8 rate emits MCDU_FAST, and a positive delta with -8 rate emits PCDU. The exact counter codes are 1/3 for slow positive/negative and 17/19 for fast positive/negative, with textual octal counter address `32` (decimal 26).

The model's angular quantum is `360/32768 = 0.010986328125` degrees. Its loop uses strict `residual > quantum`: an isolated exact quantum emits zero operations; two exact quanta emit one. Sub-quantum residual is retained. Signed wraparound follows the short rotation. The existing zeroing and gimbal-lock inhibits suppressed both motion and packets in the diagnostic controls. Pitch, roll, Y/Z angles, and all non-X counter feedback are rejected by the trace parser.

The model therefore produces roughly 728 signed pulses/second at +/-8 degrees/second, while the negative case requests the engine's nominal 400-count/second mode. This is a mode-selection defect in the pinned simulator. Component output alone does not measure engine queue lag: the separate CDU transport experiment establishes queue pacing and settlement. No correction was applied to the upstream model, emulator, flight software, or old evidence. A corrected selector would need a separately identified model change and fresh paired engine/closed-loop traces before it could be used as validated feedback.

Scheduling and numerical scope are explicit:

- Each rate scenario imposes constant yaw rate and calls the existing `dynamic_simulation` 100 times. This calls the existing body-to-stable-member transform and quantizer. There are no thruster commands, CPU execution, or hardware counter writes in this component probe.
- The step is `853 * 0.00001172 = 0.00999716` seconds, matching the retained Phase 5 wrapper's nominal maximum coupling interval and its rounded cycle duration. Engine clock accuracy is evaluated separately. Calling this exactly 10 ms would conceal a 0.0284% difference.
- The retained wrapper first calculates acceleration with zero `Delta_Time2`, then updates RCS rate over each actual latch interval, and finally integrates angle using the updated rate over that interval. This is endpoint-rate (semi-implicit Euler) angular integration, with fresh fuel/mass accounting by the existing model. Sensor requests are injected after the CPU chunk, labeled at that chunk end; individual latch intervals can be shorter than 853 calls. This component fixture does not reproduce that actuator loop.
- The original GUI `read_socket` loop uses host milliseconds, 5/10 ms waits, and an accumulated `Delta_Time2 > 0.025` gate before `dynamic_simulation` (`lm_simulator.tcl:715-754`). The retained harness bypasses this host scheduling. There is no routine named `rate_pulse` in the retained source bundle; timing is split between these calls and the emulator's CDU queue.
- Multiple-axis dynamics, historical spacecraft fidelity, powered descent, and landing are **NOT RUN**.

From the repository root, after `make runtime`, reproduce in a fresh scratch directory with the extracted Phase 6 source:

```sh
python3 -B docs/milestone2-evidence/plant/run_validation.py \
  --source .build/reproducibility/runs/milestone1-verified/source \
  --tcl .build/reproducibility/runtime/bin/tclsh8.6 \
  --output .build/milestone2-plant/new-run
python3 -B -m unittest discover -s docs/milestone2-evidence/plant -p 'test_*.py' -v
```

Generated output must be new and inside `.build` or external scratch. No retained phase evidence is overwritten. The source path in the example is the existing verified local extraction; the project-level Milestone 2 runner supplies its own freshly extracted path.
