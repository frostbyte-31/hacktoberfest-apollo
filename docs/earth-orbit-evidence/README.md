# Original Command Module computer: Earth-orbit control bench

This milestone adds **fresh, interactive execution of the original Comanche055 Command Module computer software**. Real DSKY key presses become actual ringbuffer input packets; original instructions generate the DSKY relay output. The retained Luminary software and all previous experiment evidence remain unchanged.

This is a cold-start computer bench placed at the campaign's Earth-orbit chapter. It is **not a restored Apollo 11 flight-memory checkpoint**. No historical orbit, physical IMU, star measurements, launch-vehicle computer, TLI maneuver or spacecraft flight is being simulated by this bench. The spacecraft picture is a separate static configuration model.

## Playable objective and genuine result

1. Optional control familiarization: enter **VERB 3 5 ENTR**. Original Comanche performs its lights test; the received displays become `88 / 88 / 88` and three `88888` registers. This training action is not presented as a documented item that Collins performed at this exact mission time.
2. Let the original five-second light test finish; press **RSET** and enter **VERB 3 7 ENTR 0 0 ENTR** to select original P00.
3. Enter **VERB 1 6 NOUN 3 6 ENTR**. The original computer displays its running clock. This is **CPU execution time**, not Apollo 11 ground elapsed time.
4. Enter **VERB 3 7 ENTR 5 2 ENTR**, corresponding to the real P52 realignment program used during Earth parking orbit.
5. Enter **VERB 0 5 NOUN 0 9 ENTR** to inspect the actual alarm registers. This cold-start bench produces **`00210`**, because the required IMU and known reference orientation are unavailable. Noun 09 displays three stored alarm codes; earlier codes can occupy R1, so the readiness code may appear in R2 or R3.
6. Enter **RSET, VERB 3 7 ENTR 0 0 ENTR** to return to P00. Completing the exercise means a successful computer checkout and readiness diagnosis. It does not complete P52 alignment or authorize TLI.

The real historical P52 included optical star sightings and IMU corrections. No star mark, known-matrix flag, successful alignment, or launch/transfer has been fabricated here. The flight gate remains closed.

The uninitialized cold start also produces **`01107`**, the original phase-table failure alarm. It remains visible in the original alarm history until an original **RSET** clears it. This is another reason this bench is not described as an operational historical flight checkpoint. The original [alarm-and-abort source](https://www.ibiblio.org/apollo/listings/Comanche055/ALARM_AND_ABORT.agc.html), printed pages 1493–1494, stores the first, second and third alarms in consecutive `FAILREG` words; the Noun 09 table points to those words. The [restart source](https://www.ibiblio.org/apollo/listings/Comanche055/FRESH_START_AND_RESTART.agc.html), page 181, and the assembly-information alarm table, page 24, identify `01107` as a phase-table failure. Earlier alarm codes are never hidden or overwritten by this application.

## Original software and transport provenance

- Upstream revision: `f577e3fd917866c59334e6cdd32504f09df76f60`.
- Comanche source: [pinned upstream tree](https://github.com/virtualagc/virtualagc/tree/f577e3fd917866c59334e6cdd32504f09df76f60/Comanche055).
- Retained rope SHA-256: `2ba31de9291cd10fb351a64d261bae8514a1cb75b4651bfa6a135dfa821a2d79` (73,728 bytes).
- The unmodified pinned yaYUL assembler reports **0 unresolved symbols, 0 fatal errors and 0 warnings**. Its output is byte-identical to an independent conversion of the proofed `Comanche055.binsource` octal listing using the pinned `Tools/oct2bin` utility.
- `corresponding-source.tar.gz` retains 129 original source/build/license files; `source-manifest.json` records every SHA-256 and upstream Git blob identity. Source transcription provenance is preserved; a bit-identical dump of the physical flown rope is not claimed.
- The engine is built from the unchanged pinned archive in `docs/phase6-evidence/corresponding-source.tar.gz`. The new external C observer reads actual queued packets, output words and cycle counters. It never writes flight RAM, program counters, alignment flags or sensor counters.
- Each bench runs in a fresh native worker process so static core and ringbuffer globals cannot leak between sessions. The existing emulator's CM personality configuration is selected before reset; its instruction semantics remain unchanged.
- Eighteen normal keys use channel `015` and their original key codes. **PRO** is the separate active-low channel `032` bit-14 discrete, including a mask packet, press and release. It is not substituted with `V33E`.
- A key acknowledgement includes the actual queued ring word and observed CPU cycle of consumption. “Accepted” means the native ringbuffer accepted the packet, not that a requested maneuver succeeded.
- Numerical displays, signs and decoded indicators derive from received channel `010`/`011` output. Unobserved fields remain `?` or unavailable. No display value is copied from a tutorial script.
- CPU timing uses exactly **12 / 1,024,000 seconds per memory-cycle call**. A key response advances 0.4 CPU seconds; further polling advances the same native computer. The CPU clock is separate from wall time and historical GET.

## Source-backed readiness gate

The original [P51–P53 source](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html) enters `R02BOTH` before presenting P52 options. The original [IMU mode switching source](https://www.ibiblio.org/apollo/listings/Comanche055/IMU_MODE_SWITCHING_ROUTINES.agc.html), printed pages **1443–1444**, checks `REFSMFLG` and the IMU status. A missing known reference/IMU produces the original `0220`/`0210` readiness alarm path. Fresh cold-start execution in this fixture specifically produces **`0210`**, verified through original `V05N09` output.

The [Apollo 11 Flight Journal](https://apollojournals.org/afj/ap11fj/02earth-orbit-tli.html) records Houston recommending P52 at **000:18:42** and Collins accepting at **000:18:54**. The bench's extra training checks and failure state are labeled separately from that historical checklist.

## Reproduce the evidence

From the repository root, with Python 3.11+ and a C compiler (`cc`) installed:

```sh
python3 -B -m unittest backend.tests.test_cmc_native -v
python3 -B docs/earth-orbit-evidence/experiments/run_validation.py \
  --output .build/earth-orbit/validation/my-fresh-run
# Optional cross-runtime comparison, using Node and the retained pinned WASM:
python3 -B docs/earth-orbit-evidence/experiments/run_validation.py \
  --with-wasm --output .build/earth-orbit/validation/my-native-wasm-run
```

Choose a new output directory for every validation. No network, Tcl runtime or Node runtime is needed for the native CMC bench after checkout. The validation rebuilds both original assemblers/converters, compares the three rope images, builds the unchanged CPU core, runs all observed checkpoints in two fresh processes and requires byte-identical raw traces. Retained summaries and compressed logs are in `runs/verified/`.

The optional WASM comparison replays the exact same 44 real input packets over 3,566,967 CPU cycles, using ringbuffers with one CPU call per observation. All **6,915** output `(cycle, channel, value)` tuples match exactly. The retained WASM module does not export CM personality selection, so the validator explicitly rejects any schedule that uses the pinned core's personality-specific RHC path. The validated DSKY/PRO subset does not use that path. This bounded result does not imply a validated CSM vehicle, IMU or flight model.

`backend/cmc_native.py` exports read-only `availability()`, `prepare_cmc_assets()`, and `CmcProcess.boot/key/advance/close`. `advance` accepts 0–30 finite CPU seconds. Unsupported keys, command macros and invalid time advances are rejected without executing extra cycles. Worker responses have a ten-second deadline and a size limit; failed workers are terminated. The frontend service owns exercise progression; the native driver never manufactures success or spacecraft telemetry.
