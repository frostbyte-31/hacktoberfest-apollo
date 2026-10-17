# Native yaw and pitch AGC feedback integration

**VERIFIED execution:** authentic Luminary099 produces RCS packets that drive independent pitch and simultaneous yaw/pitch experiments in the explicitly modern rotational fixture. Sensor packets return through all three derived gimbal/CDU paths, with actual native input bytes, FIFO heads, signed counter applications and settlement observed. Disconnected controls change genuine flight-software commands, and fresh pitch/combined replays are byte-identical. This establishes bounded capability **C** (simultaneous two-axis feedback), following separately demonstrated pitch and retained yaw. **D, full three-axis control, is NOT RUN.** Incidental roll dynamics and middle-gimbal readings do not establish D.

**ASSUMED physics:** synthetic LM-7 defaults, inferred principal inertias and assumed one-metre component torque arms. These are modern simulated states, not Apollo 11 calibration or historical telemetry. No descent propulsion, PIPA integration, landing, frontend, multiplayer or AI crew is added.

## Reproduction

```sh
python3 docs/phase7-evidence/integration/run_validation.py \
  --source .build/milestone3/pinned-source \
  --tcl .build/reproducibility/runtime/bin/tclsh8.6 \
  --runtime-manifest .build/reproducibility/runtime-manifest.json \
  --output .build/phase7/new-integration-run
python3 -m unittest discover -s docs/phase7-evidence/integration -p 'test_*.py' -v
```

The source directory is an unchanged extraction of the retained 24-file Phase 6 archive. The CLI validates every participating source hash, the authentic rope, earlier evidence and the locked Tcl runtime manifest/version. `--cc` records a selected host compiler. A new output directory is required; outputs cannot replace retained evidence. Commands, UTC times, actual exits, input/code/binary hashes, source snapshots and complete raw traces are captured. Full validation executes a diagnostic native probe, an unchanged Milestone 3 yaw baseline, a new quaternion-model yaw run, independent pitch on/off/replay, then simultaneous on/off/replay only after independent pitch succeeds.

The 23 tests require no Tcl cache or downloads. They rebuild and execute the mixed-axis native observer from the retained source bundle, reconcile actual captured control traces and reject altered packet identities, FIFO heads, counter changes, settlement, orientation interfaces and provenance. Full `run_validation.py` executes the actual vehicle experiments afresh with Tcl.

## Reuse and observation

Earlier Phase 1–6 and Milestone 1–3 files remain unchanged. The new driver imports retained Milestone 3 timing, destination validation and initialization scheduling. Its old worker/parser hardcode X-only state, so a separate observational `Engine` and orchestration layer are necessary for three sensor FIFOs; they contain no emulator, guidance algorithm or vehicle integration.

`inspect_axes.c` includes the retained Milestone 2 bridge, which includes the unchanged pinned `agc_engine.c` exactly once. The retained Phase 5 actual-output bridge and other pinned compilation units are linked unchanged. New getters read all three FIFO states and peek/parse actual input ringbuffer bytes without advancing its tail. There are no flight-memory patches, absolute counter writes, readiness bypasses or injected jet commands.

Every host write gets a wire sequence ID. Before each busy CPU call the observer parses the actual queued native packets. Original `ChannelInput` consumes normal packets until the first counter operation, then returns. The driver compares the observed occupancy decrease with that exact parsed prefix, matches normal/DSKY/CDU packet identities and observes which FIFO actually enqueued a sign/rate operation. Thus simultaneous sensor traffic cannot be assigned to an axis merely from a change in queue size. The fresh native probe verifies a first call consuming two normal packets plus X, followed by Y and Z in subsequent calls; actual applications produce `[1,32767,1]` before empty-queue and 1,000-call quiet checks.

Each CDU has its own host queue and permits one accepted request outstanding until actual application; deliveries on that FIFO are separated by at least 214 slow or 14 fast CPU calls. Different FIFOs may receive packets at the same boundary and are then serialized by the real engine. Actual FIFO head bits identify sign/rate. Applications must have the corresponding modular counter delta and genuine deadline increment. Generated, delivered, consumed, enqueued and applied counts reconcile separately for each axis. Packet acceptance is never equated with counter application.

The physics overlay is owned by `../physics/`: it reuses the original source-locked jet decoder, original `update_RCS` thrust/fuel computation and original IMU quantizer, adds bounded Euler gyroscopic coupling and unit quaternion orientation, and corrects the existing signed rate selectors with absolute values. The driver initializes the retained Tcl server modules and calls `phase7_step`; it does not duplicate physics. Raw state includes actual jet latches, decoded source-derived thruster names, torque, angular acceleration, body rates, quaternion, gimbals, both inertia samples, mass/fuel and gimbal rates. Translation/PIPA behavior remains explicitly excluded by the physics adapter.

Read-only AGC samples include Z/PC, EB/FB/BB bank words, NextZ, MODREG, IMODES30/33, FAILREG and DAPBOOLS. Register indices `RegEB=03`, `RegFB=04`, `RegZ=05`, `RegBB=06` come from the pinned engine header. Samples describe the current CPU boundary; `model_interval_end` separately identifies a possibly earlier interval endpoint. These are bounded state samples, not an instruction-by-instruction trace or a claim that the sampled instruction caused one particular jet packet.

## Source-justified initialization and frames

The pinned source mappings and primary documentation are retained in `../source/`. Body X/P is yaw, Y/Q is pitch, Z/R is roll; CDU X/Y/Z are outer/inner/middle gimbals. The source-supported orientation factorization is `Ry(inner) Rz(middle) Rx(outer)`. Body axes and gimbal axes differ after compound rotation. All three derived gimbal measurements are delivered; neither middle-gimbal motion nor gyroscopic roll is suppressed to make the experiment appear two-dimensional.

The delayed startup schedule is retained from Milestone 3: V37E00E at 1,600,000–1,727,998 CPU calls and V77E at 2,000,000–2,063,999. At 2,200,000, actual MODREG must be P00, all FAILREG words zero, IMODES30/33 inhibition bits clear and original ACCSOKAY set. Its source-resolved location is DAPBOOLS `0111` octal, mask `00004`. V77 keys are delivered; a flag already clear is not described as proof that the verb changed it. This remains operate-only initialization, not calibrated alignment, valid REFSMMAT or a descent mission state.

Yaw retains its exact negative fixture: channel031 word 12279 then channel0167 one's-complement −20 (32747). Pitch alone uses source-proven channel031 word 12286 and channel0166 +20. Combined yaw-negative/pitch-positive uses channel031 word 12278. Both analog values are written at CPU call 2,500,001 before the same native call; neutral analog values likewise share 2,700,000. This prevents a serial inter-axis input bias. Original Luminary QR control and source Crew Inputs, rather than invented mappings, establish these interfaces.

The clock convention is exactly `12/1024000` seconds per call. Physical integration boundaries are at most 853 calls apart (9.99609375 ms), also split at actual jet/zero-latch output times. Per-call transport inspection does not create extra physics steps. Yaw/pitch experiments stop at 4,000,000 calls; **before execution** all combined cases were bounded to 3,200,000 to keep the disconnected control inside the active ±80° middle-gimbal domain. No singularity guard is disabled or relaxed.

At production stop, the model and new sensor production freeze explicitly. Queued sensors continue through the real CPU, genuine subsequent outputs remain logged as a diagnostic tail, then all three FIFOs/ringbuffer/host queues must be empty and 1,000 further CPU calls leave counters unchanged. This establishes transport settlement, not physical equilibrium. Final actual CDU angles (`count × 360/32768`) must agree, modulo 360°, with an independent diagnostic decomposition of the final quaternion within one original quantum (0.010986328125°) plus 1e-8° roundoff. Recorded model gimbals must also represent that quaternion.

## Actual bounded results

| Experiment | Generated = delivered = consumed = enqueued = applied, X/Y/Z | Peak body yaw/pitch/roll °/s | Final body yaw/pitch/roll °/s |
|---|---|---|---|
| New-model yaw | 1582 / 0 / 0 | 4.858000 / 0 / 0 | −0.036645 / 0 / 0 |
| Independent pitch | 0 / 1701 / 6 | 0.000004 / 4.213513 / 0.008965 | −0.0000003 / −0.032862 / −0.008965 |
| Simultaneous yaw/pitch | 1264 / 1477 / 219 | 4.864697 / 4.212138 / 0.013248 | −0.590839 / +1.323930 / −0.013248 |

All connected operations are accounted for without rejection/loss, and actual native FIFO occupancy stays at most one pulse per axis. Independent pitch disconnected generates 2/16420/2 pulses but intentionally delivers none; its final pitch rate is +11.019711°/s and all actual CDUs remain zero. Combined disconnected generates 5652/5763/3782 pulses but delivers none; final yaw/pitch rates are −10.844281/+11.024825°/s with zero actual CDUs. Complete timed authentic RCS sequences differ, including different command words while the controller is held; these are feedback controls, not comparisons of histogram counts alone. Fresh pitch and combined replays reproduce complete raw bytes.

An actual simultaneous interval ends at call 2,510,379: original AGC latches are channel005 decimal150 (`00226`) and channel006 decimal170 (`00252`), decoded from original source. The modern model reports simultaneous torque `[−1780,+1780,0] Nm`, body rates `[−0.072351,+0.039435,−0.004097]°/s`, and nonzero yaw/pitch orientation components. The 1780 Nm values follow this synthetic fixture's force/arm assumption; they are not historical Apollo measurements or injected AGC commands.

Compatibility criteria were declared before the new model ran: the unchanged Milestone 3 yaw baseline must be byte-identical; new-model yaw must preserve exact timed RCS and actual CDU application sequences, physical interval boundaries, rate error ≤1e-9°/s and wrapped gimbal error ≤1e-8°. All pass. Observed numerical errors are 1.75e-14°/s and 1.42e-11°, respectively. Earlier reference traces were not weakened or rewritten.

Measured maximum discrete interval-end origin→application latency is 925 calls for yaw, 862 for pitch and 868 for combined; maximum delivery→application is 220 calls. Host queue peaks are respectively `[5,0,0]`, `[0,4,1]`, `[5,4,1]`. These are measured transport latencies from a discrete model endpoint, not total instrument/hardware delays or the unobserved continuous angle-crossing time. Final wrapped actual-counter/quaternion-gimbal errors are about `[.005281,0,0]°`, `[.000579,.005911,.005169]°` and `[.008654,.007309,.007704]°`, all within one quantum.

Connected combined middle-gimbal magnitude reaches 2.413710°; disconnected reaches 41.561087°, below the unchanged 80° guard. The final combined body still rotates at cutoff. No equilibrium, stability envelope or long-duration certification is claimed.

## Instrument outputs and remaining limitations

Nonzero convenience outputs0174–0176 occur: 51 in yaw, 46 in pitch and 58 in combined. They are retained as genuine AGC outputs. Original `AGC_IMU.tcl:461–497` routes them to FDAI error needles while channel012 bit4 is clear; only the enabled branch moves platform gimbals. Actual output-latch reconstruction shows zero active coarse-alignment commands and zero nonzero0177 fine-alignment commands. The driver classifies inactive packets explicitly, rejects unsupported active coarse/fine alignment and preserves raw triggering packets. Error-needle commands are not treated as RCS torque or spacecraft motion.

The retained absolute-body-rate selector approximates instrument rate; it does not equal gimbal speed under compound motion. Connected combined requests have four X and three Y boundary mismatches, all conservative fast choices. No connected slow request exceeds 4°/s actual gimbal speed: maxima are 3.962622/3.992888/.632269°/s. The deliberately disconnected combined Z path generates 3,413 slow choices above 4°/s, reaching 9.836114°/s; none is delivered. This is a disclosed sensor-mode approximation, not a hardware timing certification, and the work does not silently change another policy after measuring it.

The normalized quaternion and bounded Euler model still depend on assumed inertia/torque arms, integration choices and mass-flow interpretation; see `../physics/README.md`. No claim extends beyond these initial conditions, inputs, axes and horizons. **NOT RUN:** independent roll control/full D, a calibrated flight vehicle or IMU, arbitrary attitude/singularity coverage, full fine/coarse platform alignment, coupled WebAssembly comparison, translation/PIPA, descent engines/radar, powered descent or landing.

`runs/native-attempt-01` preserves the first successful diagnostic three-FIFO experiment. `runs/integration-attempt-01` preserves a completed baseline/yaw worker followed by a Python count-analysis `KeyError('axis')`; its source snapshot and failed status remain intact. `runs/integration-attempt-02` preserves the full eight vehicle runs that first established the measured controls before later instrumentation/provenance hardening. Raw JSONL is losslessly compressed with uncompressed SHA-256 hashes. Executed source snapshots, real commands and failure/completion metadata preserve each attempt's provenance. Later final validation uses new directories and does not overwrite these attempts.
