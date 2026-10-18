# Apollo 11 operations reference for the frontend

This document defines the historical starting chapter and the limits of the cockpit interface. It is a design and integration reference. It does not certify the application as a complete Apollo 11 procedure simulator.

The machine-readable companion is [`frontend/dist/data/apollo-operations.json`](../frontend/dist/data/apollo-operations.json). Its historical configuration values must be displayed as checklist references, never as observed backend switch positions. Its timeline is chapter metadata, never generated telemetry.

## Starting point: Eagle still docked in lunar orbit

Begin the landing experience with **preparation for undocking**, with Armstrong and Aldrin in Eagle and Collins in Columbia. The original LM activation checklist places this section at approximately **100:05 GET**. This is a scheduled checklist time. Actual undocking was around **100:12 GET**. The later **100:39 GET** event was a CSM separation maneuver; it must not be mislabeled as undocking. [Apollo 11 activation checklist, ACT-62–63, PDF pages 68–69](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf), [Flight Journal, 100:12:03 and separation discussion](https://apollojournals.org/afj/ap11fj/17day5-undock-doi.html).

This is a chapter boundary, not the beginning of the complete mission. Launch, Earth orbit, translunar injection, the coast, lunar orbit insertion, and much LM activation have already happened. A future full-mission mode can introduce those earlier chapters without changing this boundary. Do not imply that reaching this screen means those operations have been simulated.

The historical reference configuration is stage-specific. ACT-62–63 specifies **GUID CONT AGS**, both MODE CONT switches at **ATT HOLD**, all three ATTITUDE CONTROL switches at **PULSE**, and separate ACA/4 JET and TTCA/TRANSL enable settings. That differs from a later PGNS automatic-descent configuration. The exact reference list and page locators are in the JSON. A player must not be shown a completed checklist merely because they opened the page. [Original checklist](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf).

The initial task should therefore read: **“Review Eagle's pre-undocking configuration and crew responsibilities.”** Until the backend supplies a validated historical checkpoint and actual switch readbacks, this is an inspectable preparation chapter with an explicit execution boundary. It cannot honestly offer a functional “Undock” button.

## Preserve the chronological sequence

| Order | Chapter | Historical reference |
| --- | --- | --- |
| 1 | Docked preparation | ACT-62–63; approximately 100:05 scheduled GET |
| 2 | Undock and inspect Eagle | Approximately 100:12 GET |
| 3 | Columbia separation maneuver | Approximately 100:39 GET |
| 4 | LM alignment and DOI preparation | P52 discussion around 101:17 GET |
| 5 | Eagle descent orbit insertion | Approximately 101:36 GET |
| 6 | P63 selection, review, and ignition preparation | Before powered descent |
| 7 | Powered descent initiation / P63 braking | Approximately 102:33 GET |
| 8 | P64 approach and landing-area assessment | Approximately 102:41 GET |
| 9 | P66 manual attitude / commanded descent rate | Approximately 102:43 GET |
| 10 | Contact, engine shutdown, landing checks | Approximately 102:45 GET |
| 11 | Surface operations and EVA | Future chapter |
| 12 | Ascent stage launch | Future chapter |
| 13 | Rendezvous, docking, crew transfer | Future chapter |
| 14 | Trans-Earth injection, coast, entry, recovery | Future chapter |

The orbital sequence follows the [Apollo 11 Flight Journal](https://apollojournals.org/afj/ap11fj/17day5-undock-doi.html). The descent phases follow [MSC-00171, sections 5.1–5.3 and Table 5-I, page 5-13](https://ntrs.nasa.gov/api/citations/19700008096/downloads/19700008096.pdf). Later chapters follow the [NASA mission overview](https://www.nasa.gov/history/apollo-11-mission-overview/).

Approximate labels are intentional: PAD ignition times, transcript call times, and postflight reconstructed event times are different observations. For example, Table 5-I lists P64 entry at 102:41:32, while the spoken P64 call is at 102:41:35. The UI must not silently turn a call timestamp into a precise simulated transition. The mission-report table lists P66 entry at 102:43:22 and landing at approximately 102:45:40. [Landing transcript and commentary](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html).

Apollo 11's LM performed DOI after undocking. Do not import the later Apollo mission procedure in which the CSM engine lowers the docked spacecraft's orbit before LM separation. [Landing Journal opening chronology](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html).

## The crew did use hand controllers

The answer to “Did astronauts have a joystick?” is **yes, with separate controls for rotation and translation/thrust**:

| Hardware | Physical use | Frontend implication |
| --- | --- | --- |
| ACA, Attitude Controller Assembly | Right-hand pistol grip. Fore/aft gives pitch down/up; left/right gives roll left/right; twisting gives yaw right/left. | A flat yaw/pitch pad is a partial proxy, not a replica. Provide three distinguishable axes and communicate which physical motion each input represents. |
| TTCA, Thrust/Translation Controller Assembly | Left-hand T-handle with THROTTLE/JETS selection. It commands RCS translation or descent thrust according to configuration. | Keep it separate from the ACA. A translation command changes linear velocity; an attitude command rotates the spacecraft. |
| ROD switch | Momentary switch at the commander's left-hand control area. | Show commanded vertical rate, rather than pretending the switch directly sets a throttle percentage. |
| DSKY | Dedicated computer keypad and display. | Verbs, nouns, program prompts, and key delivery must come from original execution. |

Hardware geometry is corroborated by the [Grumman handbook excerpt, §2.1.1.3.1–2, pages 2.1-12 and 2.1-15, Figures 2.1-9–10](https://www.ibiblio.org/apollo/Documents/LMA790-3-LM-2.1.pdf). **This available excerpt is a 1970 LM-10-and-subsequent revision.** Use it for corroborating the hardware layout, not for assigning later software behavior or procedures to Eagle. The [Apollo 11 checklist, ACT-47–53](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf) independently records the ACA axis checks and TTCA translation checks for LM-5.

Changing course near the surface was not simply “point the joystick toward the ground target.” The computer initially flew the braking and approach trajectory. For the final manual phase, Armstrong controlled attitude, thereby directing the thrust vector; the computer still controlled engine throttle for the selected vertical rate. Aldrin monitored and called flight data. Collins remained in lunar orbit. [Mission report, pages 5-1–5-2](https://ntrs.nasa.gov/api/citations/19700008096/downloads/19700008096.pdf), [crew landing transcript](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html).

## Modes and switches are part of the controls

The interface must distinguish these control families:

- **GUID CONT:** guidance-system selection.
- **MODE CONTROL PGNS / AGS:** separate AUTO / ATT HOLD / OFF switches.
- **ATTITUDE CONTROL:** independent ROLL, PITCH, and YAW switches, with MODE CONT / PULSE / DIR.
- **ACA/4 JET and TTCA/TRANSL:** separate enable/disable switches for the two crew positions.
- **THR CONT and MAN THROT:** automatic/manual thrust control and selected crew authority; these are distinct from the TTCA's THROTTLE/JETS selector.
- **ENG ARM, engine start/stop, abort, and abort-stage controls:** their electrical and physical interlocks must be modeled before enabling them as live controls.

Labels and procedure contexts are supported by the [Apollo 11 activation checklist](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf) and the [NASA control-panel reference, slide 68](https://www.nasa.gov/wp-content/uploads/2023/06/eppler-slides-apollo-lunar-landing-experience-report-20070-r4.pdf).

For Apollo 11, selecting **ATT HOLD followed by actuating the ROD switch** enters P66. It is not sufficient to make an “ATT HOLD” button universally mean “manual landing.” The original mode monitor also distinguishes manual throttle operation and P67. Each ROD pulse changes the commanded vertical rate by 1 ft/s; the guidance computer computes the throttle response. [Mission report, page 5-2](https://ntrs.nasa.gov/api/citations/19700008096/downloads/19700008096.pdf), [pinned original GUILDEN / P66NOW? / STARTP66 / STARTP67 / RODCOMP source](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/Luminary099/LUNAR_LANDING_GUIDANCE_EQUATIONS.agc).

A keyboard, pointer, or commodity gamepad can operate a browser representation of Apollo hardware. Its mappings must be labeled as input proxies, with the original controller name, physical motion, selected mode, and supported axes visible. Mechanical fidelity, cockpit switch fidelity, command delivery fidelity, and spacecraft physics fidelity are separate claims. A carefully drawn controller establishes none of the other three.

## Where the original Apollo software starts

The source used by this repository is pinned to Virtual AGC revision **`f577e3fd917866c59334e6cdd32504f09df76f60`**. These retained files were inspected without modification; their original hashes are recorded in `docs/phase9-evidence/source/source_hashes.json` and `docs/milestone2-evidence/startup/source/manifest.json`.

| File and symbol | Meaning |
| --- | --- |
| `Luminary099/MAIN.agc` | Assembly include order, not a linear mission screenplay or `main()` loop. |
| `INTERRUPT_LEAD_INS.agc`, `SETLOC 4000` | Fixed entry performs `INHINT`, selects bank context with `GOBB`, and transfers to `GOPROG`. The same file provides timer, keyboard, radar, and other interrupt lead-ins. |
| `FRESH_START_AND_RESTART.agc`, `GOPROG` | Restart processing, not a command to replay the entire flight history. |
| Same file, `SLAP1` / `STARTSUB` / `DOFSTART` | Requested fresh-start initialization, distinct from restarting active protected computations. |
| Same file, `V37XEQ` / `FCADRMM1` | Original major-mode selection, validation, dispatch, and scheduling. |
| `THE_LUNAR_LANDING.agc`, `P63LM` / `IGNALG` | Entry to the braking program and ignition preparation. It depends on mission data, alignment, and a landing target. |
| `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc`, `GUILDEN` / `RODCOMP` | Mode-dependent landing and vertical-rate processing. |

Primary source links: [interrupt lead-ins, listing pages 153–154](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/Luminary099/INTERRUPT_LEAD_INS.agc), [startup and mode selection, pages 211–237](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/Luminary099/FRESH_START_AND_RESTART.agc), [P63, pages 785–792](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/Luminary099/THE_LUNAR_LANDING.agc), [landing guidance, pages 798–828](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/Luminary099/LUNAR_LANDING_GUIDANCE_EQUATIONS.agc).

The practical starting point is therefore a **validated orbital checkpoint plus the corresponding crew checklist**, with Luminary already running. A cold computer reset does not create the historical LM state, clock, landing-site reference, CSM state, radar observations, or cockpit configuration. The successful synthetic P51/P27/P63 sequence is valuable execution evidence, but must not be described as every action Armstrong and Aldrin performed in orbit.

## Integration acceptance for a real procedure chapter

These are implementation requirements, not claims of existing endpoints:

1. A scenario/checkpoint identifies epoch, GET, reference frame, spacecraft state, target, alignment, mass, propellants, and provenance; its historical or synthetic status is explicit.
2. The backend owns cockpit state, mode/interlock decisions, command acknowledgments, and AGC input delivery. The frontend must not write a mode label and infer that the native machine entered it.
3. ACA inputs have three signed axes, neutral/detent state, calibration, proportional range, and separately validated pulse/hardover behavior. Unsupported axes are rejected rather than silently coupled.
4. TTCA translation and throttle inputs have independent authority and selector state. ROD is an edge event with a recorded acknowledgment. Abort/engine controls require their own validated paths.
5. A checklist item becomes satisfied only through a real readback or an explicitly manual acknowledgment. “Read this explanation” and “verified hardware action” must remain distinguishable.
6. The 3D viewer consumes backend state with units, coordinate frames, timestamps, and validity. Presentation models or retained synthetic fixtures retain their source labels and never establish historical flight progress.
7. The mission clock, recorded run time, and CPU/physical model clocks are labeled separately. A short fixture must not be relabeled as a full mission-duration flight.
8. PDI, approach, landing, ascent, and rendezvous remain unavailable until their end-to-end control and sensor loops have been demonstrated for the relevant chapter.

The first useful increment is an understandable orbital preparation screen with source-linked controls, historical checklist references, and an honest boundary to the available backend evidence. Enabling one validated cockpit action at a time can then progress toward the real mission without another synthetic target game becoming the main experience.
