# Apollo 11 undocking: source and procedure boundary

The application definition is [`frontend/dist/data/undocking-procedure.json`](../frontend/dist/data/undocking-procedure.json). It is a **selected interactive procedure trainer**, using a server-owned discrete checklist state. It does not reproduce every item in the LM and CSM checklists. Its completion does not establish that original AGC/AGS computations, a pressure system, a docking mechanism or relative flight dynamics have executed.

## Who releases Eagle

**Michael Collins, in Columbia, operates the CSM docking-probe control.** Armstrong and Aldrin prepare Eagle and report ready. This is not an LM DSKY verb, a generic engine command or the later CSM/LM FINAL SEP pyrotechnic jettison. The real control is **DOCKING PROBE EXTD/REL/OFF/RETRACT**, on CSM main display panel 2, area H, grid E-28. The unchanged April 15, 1969 handbook table identifies EXTD/REL as powering the probe extension-latch release and capture-latch release motor. OFF removes power; RETRACT supplies the separate primary/secondary retraction switches. [Apollo Operations Handbook, page 3-99, PDF page 98](https://www.ibiblio.org/apollo/ApolloProjectOnline/Documents/SMA2A-03-BLOCK%20II%20Volume%201%2019691015/aoh-v1-3-cont%2Bdisp.pdf#page=98).

Two EXTD/RETR probe indicators sit at panel 2, H, D-28. The table associates striped flags with probe motion and gray with completed movement; these flags are contextual, not a universal green "undocked" light. The trainer does not manufacture their readings. [Same handbook, page 3-100, PDF page 99](https://www.ibiblio.org/apollo/ApolloProjectOnline/Documents/SMA2A-03-BLOCK%20II%20Volume%201%2019691015/aoh-v1-3-cont%2Bdisp.pdf#page=99).

The electrically commanded capture-latch release must not be confused with the twelve docking-ring latches, which are released/cocked manually earlier. The preloaded probe maintains the docked connection while those ring latches are released. [Docking and Transfer, pages 2.13-18 to 2.13-21](https://apollojournals.org/afj/aoh/aoh-v1-2-13-dock.pdf#page=18).

The available Apollo 11 flown Solo Book says to put both docking-probe circuit breakers IN before undocking. Its actual-release line is terse. We have not established an Apollo 11-specific number of seconds for holding EXTD/REL from these sources. Do not import the five-second instructions from Apollo 15 or ASTP. The browser's momentary action is a discrete command abstraction; it must not claim mechanical timing fidelity. [Flown CMP Solo Book, page 66A](https://apollojournals.org/afj/ap11fj/a11cmpsb/a11-cmpsb-013-66a.jpg).

## Entry setup comes before the playable subset

The trainer begins with a declared prior setup, which the player acknowledges. The earlier tunnel work is not silently executed by a button:

- Vehicle umbilicals are disconnected and stowed; this differs from the docking probe's own electrical umbilicals, which are connected for probe operation.
- The drogue and probe have been installed, the probe preloaded, capture-latch engagement checked, the release-handle lock secured, and twelve ring latches released/cocked.
- Both hatches have been secured, the hatch integrity check completed, and the tunnel finally vented; the tunnel vent valve and lights are OFF.
- Earlier activation, landing-gear deployment, propulsion/RCS checks, AGS calibration/update, undocking attitude preparation and go/no-go decisions are assumed complete.

These are stated assumptions. No pressure, latch, crew suit or AGS telemetry is available from this procedure service. The flown CSM checklist separates [umbilical removal and drogue installation, F11-4](https://apollojournals.org/afj/ap11fj/a11csmoc/a11-csmoc-f11-04.jpg), [probe installation/preload and hatch installation, F11-5](https://apollojournals.org/afj/ap11fj/a11csmoc/a11-csmoc-f11-05.jpg), and [hatch integrity/final tunnel venting, F11-6](https://apollojournals.org/afj/ap11fj/a11csmoc/a11-csmoc-f11-06.jpg). F11-6 includes a time-based pressure check; acknowledging its prior completion must not display newly measured pressures or pretend that the browser has performed it.

The crew debrief adds a significant computer dependency: P47 and AGS were used to handle undocking delta-V bookkeeping. Neither original program is run by this trainer. It would be misleading to invent corresponding DSKY or DEDA responses. [Technical Crew Debrief, sections 8.1.13 and 8.2.28](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11tcdb.html).

## LM checklist configuration

ACT-62 puts preparation around scheduled GET 100:05 and covers helmets/gloves, backup communications, hatches/cabin configuration and monitoring. ACT-63 continues with the control settings. The selected trainer switches preserve these values:

| Control | Reference setting |
| --- | --- |
| GUID CONT | AGS |
| ATT/TRANSL | 2 JET |
| BAL CPL | ON |
| DEADBAND | MAX |
| ROLL, PITCH and YAW ATTITUDE CONTROL | PULSE, each |
| PGNS and AGS MODE CONT | ATT HOLD, both |
| CDR and LMP TTCA selectors | JETS, both |
| CDR and LMP ACA/4 JET | DISABLE, both |
| CDR TTCA/TRANSL | ENABLE |
| LMP TTCA/TRANSL | DISABLE |

Remaining monitor, timer, camera, COAS, heater and breaker-chart items are explicit crew-report references. The interface must call them reports rather than observed sensor readbacks. The source says "JET" for the TTCA setting; the physical controller selector is commonly labeled JETS/THROTTLE. [Original Apollo 11 LM checklist, ACT-62 and ACT-63, PDF pages 68-69](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf#page=68).

The printed LM checklist does not assign an individual hand to every switch. Where the trainer routes such checks to CDR or LMP, that is an instructional routing choice. The vehicle and control ownership remain faithful: Eagle controls belong in the LM; the docking-probe switch belongs in Columbia. ACA/4 JET DISABLE does not mean every attitude-control path is disabled, and the pre-undocking TTCA setup does not establish that Armstrong thrusts the LM away at release.

## Correct chronology after release

The Flight Plan's 100:00-101:00 page distinguishes undocking/inspection from the later CSM separation maneuver. Its printed undocking time is planned metadata. Actual onboard calls place release around **100:12:03**, after Collins and Armstrong's readiness exchange. Aldrin reports a good separation at 100:12:10. Armstrong mentions nulling his rate at 100:12:59 and starting yaw at 100:13:13, then waits for Collins before pitching for inspection. These calls establish sequence, not a position/velocity trajectory for rendering. [Flown Flight Plan, page 3-67](https://apollojournals.org/afj/ap11fj/a11cmpsb/a11-cmpsb-016-3-67.jpg), [onboard transcript and Flight Journal](https://apollojournals.org/afj/ap11fj/17day5-undock-doi.html).

The next chapters must remain in this order: relative-motion management and LM inspection; Columbia's separation maneuver around 100:39; LM alignment and DOI preparation; Eagle DOI around 101:36; P63 selection/ignition review; powered descent braking; P64 approach; P66 final landing control; contact/shutdown. Surface operations, ascent/rendezvous and return follow later. The trainer stops at the inspection handoff because those subsequent physical maneuvers are not implemented by the procedure service.

Armstrong's debrief explicitly discusses a gentler extend-then-release idea that they **did not adopt before Apollo 11** because there was not enough time to investigate its effects. Do not replace Apollo 11's established release with the later soft-undocking procedure. [Debrief section 8.2.28](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11tcdb.html).

## Machine-readable action semantics

The JSON contains 28 sequential actions. A `select` stores a player's modeled switch selection; `crew-report` records acknowledgement; `momentary` submits a discrete command. Only the CMP `csm-release-probe` action has `effect: "release"`. A following switch action returns the same modeled probe control to OFF. LMP separation confirmation is explicitly a report, and the final CMP action hands off to inspection.

The service must reject wrong crew roles and out-of-order actions. Incorrect switch selections must not advance the checklist. Empty `initialControls` means values are unknown until the player selects them. Completion cannot turn on original AGC/AGS or physics capabilities, synthesize historical telemetry, or unlock DOI out of order. An expanded disconnected 3D assembly is a diagram; its spacing is not simulated relative flight.

## Verification of references

The original LM scanned pages, flown Solo Book page 66A, flown Flight Plan page 3-67, CSM Operations F11-4/F11-5/F11-6 and handbook pages 3-99/3-100 were inspected visually. PDF tools were used read-only. Temporary downloads and rendered pages live outside tracked evidence. The handbook compilation includes later revisions, so the page-specific unchanged April 15 control tables were used for hardware labels/functions; later pages were not treated as Apollo 11 flight procedures.
