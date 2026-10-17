# Original P63 continuation: source investigation

This is a source investigation of the pinned Luminary 099 revision, not an
execution claim. The procedure below must be checked against retained native
observations. It does not establish burn attitude, ignition or physical thrust.

Source: Virtual AGC `f577e3fd917866c59334e6cdd32504f09df76f60`,
`Luminary099/`. Line numbers refer to that exact source tree.

## Crew and hardware sequence

| Observation / action | Original path and source | Meaning / limitation |
| --- | --- | --- |
| Phase 10 `V06N61` | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:761-767` | Countdown/crew event-timer review. PROCEED returns through `ASTNRETN`; ENTER recycles the display. It is not engine enable. |
| DSKY `V33E` | `DISPLAY_INTERFACE_ROUTINES.agc:90-92` | Original documented PROCEED response. Can reuse the verified ordinary channel `015` key interface; no new key bridge is required. |
| `ASTNRETN` | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:811-821` | Stops displaying while keeping the clock task running, starts `ASTNRET`. |
| Checklist 14, `V50N25` | `P51-P53.agc:724-733`; `THE_LUNAR_LANDING.agc:216-224` | At `R51P63`, ENTER returns through the original interpreter's `QMAJ` to `P63SPOT2`. PROCEED requests another fine alignment (`R51C`). Accepting existing alignment is a real software path; physical calibration of the synthetic fixture remains unverified. |
| Attitude request, `V50N18` | `R60,R62.agc:39-95,126-175` | PROCEED requests an automatic attitude maneuver; ENTER declares the maneuver accepted and returns. ENTER is a crew assertion, not a measured proof that the vehicle has the requested burn attitude. The stationary instrument fixture must retain this limitation. |
| R60 automatic-switch test | `R60,R62.agc:234-250` | `CHAN30` bit 10 must be zero (PGNCS control), `CHAN31` bit 14 must be zero (AUTO). Otherwise the original code redisplays the maneuver request. |
| Landing-radar antenna position | `THE_LUNAR_LANDING.agc:245-261` | `CHAN33` bit 6 must be zero (position 1). Otherwise checklist 500 is displayed; PROCEED checks the hardware again. `SETPOS1` is called only after the source test is satisfied. This does not supply radar measurements or implement radar navigation. |
| `BURNBABY`, computer/auto-throttle check | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:168-187,911-943` | `P40AUTO` checks PGNCS/AUTO and, with the descent stage, `CHAN30` bit 5 = zero (AUTO THROTTLE). Missing switches produce checklist 203. `ENGINOF3` occurs before the countdown sequence; it is an engine-off/reset, not ignition. |
| Precision propagation to TIG−29.9 s | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:193-241`; `INTEGRATION_INITIALIZATION.agc:919-1030` | `MIDTOAV1` integrates the original navigation state to the requested future epoch, transfers original `RATT/VATT` to `RN1/VN1`, and sets `PIPTIME1`. Insufficient computation allowance produces authentic 01703 and slips TIG. Do not write navigation values to avoid it. |
| Servicer activation | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:293-357` | At TIG−30, `ULLGNOT` sets the program's `AVEGEXIT`; if servicer is not already active, `REDO4.2` starts original `PREREAD`. This is the useful source-supported P63 PIPA-navigation prerequisite. |
| TIG−5 engine-enable request | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:361-425,776-789` | Original countdown sets `V99N62` for P63. This asks the crew to enable the engine; the request itself is not engine-on output. |
| `V33E` at V99 | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:823-827,867-889` | Original `*PROCEED` sets `ASTNFLAG` and enters `IGNITE`. If TIG has already arrived, original WAITLIST schedules `IGNITION`; otherwise TIG−0 will check the crew response. No bridge should write either flag. |
| Scheduled original `IGNITION` | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:395-474` | Sets the original engine flag and writes `DSALMOUT` engine-on; source comments and channel definition identify channel `011` bit 13 (octal mask `010000`). This is an authentic enable/on command, distinct from simulated physical ignition. |
| P63 throttle-up | `BURN,_BABY,_BURN_--_MASTER_IGNITION_ROUTINE.agc:401-415,569-592` | P63 schedules `P63ZOOM` `ZOOMTIME` after nominal TIG, calls original `FLATOUT`, and reconnects `LUNLAND` through `AVEGEXIT`. This later original guidance path needs independent observations; it must not be inferred from pre-ignition reset activity. |

## Input signal polarity and PRO key

`INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:148-168` explicitly states that
channels `030`–`033` are inverted: zero means the signal is present.
Relevant source-defined crew/hardware discretes are `030` bit 3 (engine armed),
bit 5 (auto throttle), bit 10 (PGNCS control), `031` bit 14 (AUTO), and `033`
bit 6 (landing-radar antenna position 1). These are external hardware inputs,
not writable substitute readiness flags. Every experiment must record the
initial value and any documented switch transition rather than silently
asserting them in AGC memory.

An optional physical PRO pushbutton is `032` bit 14. Its original polling loop
is `T4RUPT_PROGRAM.agc:153-179`: every 120 ms it compares that input with the
previous `IMODES33` state and queues original `PROCKEY` on a new active-low
press. A pulse shorter than the polling interval can be missed. Reusing
`V33E` avoids introducing another hardware mechanism and is expressly
documented by the original display interface.

## Minimum bounded experiment recommendation

1. Reproduce the untouched Phase 10 prefix and require its actual V06N61.
2. Use `V33E`; wait for actual checklist 14; use ENTER only as an explicitly
   documented crew acceptance of the existing synthetic alignment.
3. Wait for actual V50N18. Do not silently equate ENTER with achieved physical
   orientation. For a diagnostic sink, document manual crew acceptance and
   record the actual CDU/body-to-stable transform separately.
4. Inspect the genuine external switch values. If checklist 500/203 appears,
   supply only the documented external hardware state through existing packet
   input and record the event. Never alter the internal status/flag copy.
5. Observe original `MIDTOAV1`, `PREREAD`, `READACCS`, PIPA processing and P63
   `AVEGEXIT`. Bound waiting by the observed original TIG and clock.
6. On actual V99N62, issue the documented PROCEED response; observe original
   `IGNITION`, channel `011`, and the independent throttle-drive path.
7. Keep thrust disconnected until the output interpretation is separately
   source-verified. Stop before any unsupported P64/P66 transition.

Capture instruction checkpoints before/after every continuation, original
input/output packets, current TIG/TIME2/PIPTIME1, `RN/VN`, `AVEGEXIT`, relevant
status words, throttle counter and engine command channels. A diagnostic
engine-on write alone proves no physical motion, and none of the crew
acknowledgments proves a calibrated physical alignment.

## Throttle and mass initialization investigation

**VERIFIED source distinction:** the first diagnostic continuation can use the
unchanged Phase 10 mission inputs. Original `IGNITION` and `FLATOUT` do not
require an extra numerical mass or threshold padload to emit their command.
`THROTTLE_CONTROL_ROUTINES.agc:195-204` implements FLATOUT as a 4096-pulse
command. This does not prove that later guidance-computed throttle requests
have meaningful mass and hysteresis inputs.

| Quantity | Original definition / use | Initialization finding |
| --- | --- | --- |
| `FMAXPOS` | `CONTROLLED_CONSTANTS.agc:133`, decimal 3467 pulse units; comment FMAX = 43454.6769 N | Immutable original rope constant, not a missing erasable padload. |
| `FMAXODD` | `CONTROLLED_CONSTANTS.agc:132`, decimal 3841 pulse units; comment FSAT = 48145.4413 N | Immutable original rope constant. The source distinguishes saturation encoding from actual full thrust. |
| `SCALEFAC` | `CONTROLLED_CONSTANTS.agc:135`; `THROTTLE_CONTROL_ROUTINES.agc:206-222` | Immutable original conversion used by `MASSMULT`; source comment BITPERF = 0.0797959872 pulse units/N. |
| `THROTLAG` | `CONTROLLED_CONSTANTS.agc:134`, decimal 20 centiseconds | Original 0.2 s response-lag compensation. It is a flight-software constant, not proof that a modern plant implements that lag. |
| `HIGHESTF` | `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:618-637,1476` | Immutable original maximum-force constant. The guidance bounds lateral acceleration using `HIGHESTF / MASS`. |
| `MASS` / `WEIGHT/G` | `ERASABLE_ASSIGNMENTS.agc:666-668`; `AOSTASK_AND_AOSJOB.agc:278` | Original DP total vehicle mass, kg scaled at 2^16. Observe its runtime value; zero cannot be assumed merely because Phase 10 does not explicitly load it. |
| `LEMMASS`, `CSMMASS` | `ERASABLE_ASSIGNMENTS.agc:760-761`; `AOSTASK_AND_AOSJOB.agc:113-168` | SP component masses. Original `1/ACCS` derives the LM mass from total/docked configuration, applies original ascent/descent limits, and corrects total mass. The result may be a fallback, not a mission-calibrated mass. |
| `HIASCENT` | `FRESH_START_AND_RESTART.agc:137-138`; `CONTROLLED_CONSTANTS.agc:210` | Fresh start explicitly initializes this fallback maximum ascent mass to original `FULLAPS` = 5050 kg until a padload is done. It is not a Phase 10 mission mass. |
| `LOWCRIT`, `HIGHCRIT` | `ERASABLE_ASSIGNMENTS.agc:1384-1385`; `THROTTLE_CONTROL_ROUTINES.agc:73-118` | Explicitly padloaded erasables. The throttle code copies them into `L*WCR*T/H*GHCR*T` and uses them for hysteresis across the throttleable/full-thrust regimes. The Phase 10 blocks end the VIGN block before these words. No numerical initialization for either was found in pinned Luminary 099 source. Observe the actual untouched words; do not invent historical thresholds. |
| `TFI` | `ERASABLE_ASSIGNMENTS.agc:2157` | Alias of `TTOGO`; no separate P63/THROTTLE TFI padload is supported by the inspected source. |

The original mass interface is R03/Verb 48,
`EXTENDED_VERBS.agc:1289-1490`. `V48E` starts V01N46. A documented `V33E`
accepts the displayed DAP configuration and original `DPDAT1` derives the
stage/docked bits and working mass. `STIKLOAD` then requests V06N47. Noun 47
components 1 and 2 are LM and CSM mass, displayed/loaded as five decimal pounds
(`ASSEMBLY_AND_OPERATION_INFORMATION.agc:383-384,559-560,842-843`;
`PINBALL_NOUN_TABLES.agc:684-685`). Normal noun-loading verbs can supply those
fields. A following PROCEED executes original bounds checks and original
`DAPDAT2` stores the total DP `MASS` and calls `RESTORDB`.

For descent configuration the next V06N48 is trim-angle data. `V34E` at that
request takes the original terminate return rather than initiating a gimbal
trim (`EXTENDED_VERBS.agc:1457-1466`). Any future use must record every key and
actual display, retain the original mass checks, and choose the entered mass
from documented physical initialization. The source mechanism justifies an
input path; it does not justify choosing a convenient historical-looking value.

**UNRESOLVED:** numerical hysteresis padloads and physical calibration beyond
the bounded command experiment. **NOT RUN in this source investigation:** V48
mass loading or any P63 native continuation. Native trace findings belong in
the Phase 12 execution report, not in these source-only notes.

## Original low-thrust gate and shutdown boundary

The disconnected engine sink is expected to execute no guidance `THROTTLE`
calls despite reaching `LUNLAND`. `SERVICER.agc:257-278` first clears
`STEERSW`, then restores it only when genuine measured `ABDELV` exceeds
`DVTHRUSH`. The P63 startup sets that threshold to original `DPSTHRSH` = 36
counts (`THE_LUNAR_LANDING.agc:56-60`, `CONTROLLED_CONSTANTS.agc:141`). With
zero PIPA input, original `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:809-832`
branches to `RATESTOP` before `THROTTLE`. Authentic physical PIPA feedback is
therefore a source-supported prerequisite for this particular control path;
neither `STEERSW` nor the measured delta-v should be supplied by the driver.

Normal `V37E00E` is a bounded software stop but must not be mislabeled as a
completed automatic-throttle reset. `P40-P47.agc`'s `ENGINOF3` requests engine
OFF and a negative reset pulse train. The ensuing original software cleanup
`FRESH_START_AND_RESTART.agc:437-478` (`STARTSB2`) preserves engine ON/OFF
discretes but applies `BIT6` to channel `014`, clearing the throttle-drive
enable. This can stop the requested negative counter train before it reaches
zero. The driver must honor that output; keeping an artificial clock running
would bypass the original hardware control. Report actual engine OFF,
remaining internal THRUST count and external DECA count separately. A physical
crew disarm, when implemented and traced, is a separate hardware action.
