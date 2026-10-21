# Apollo 11: screen-by-screen presentation script

Read **Say** aloud. **Do** tells you what to show; do not read those directions.
The sections are independent clips. You do not need to read every appendix in
one video. A full manual P52 demonstration plus the mission chapters takes
longer than a short pitch. Rehearse once, then shorten waits in the edit.

Start with `make play` and open `http://127.0.0.1:4173/`. Keep the terminal open.
Use **Pause tour** and **Next chapter →** to control the pace. The tour navigates
historical references; it does not execute the maneuvers. Use **Play P52
alignment** at Earth orbit for the live task. Clicking a chapter pauses the tour.

## Opening and crew setup

**Do:** Show the home screen, choose **Apollo mission**, then **Solo** for a
reliable one-person demonstration. Open the Earth-orbit task.

**Say:** “We’re building an Apollo 11 learning experience. You explore the mission
in its real order and perform selected tasks using original flight software and
documented crew procedures. The aim is to understand why the astronauts did each
step, rather than just watch a rocket move.”

**Do:** Point to the three crew positions.

**Say:** “There are three positions: Neil Armstrong, Buzz Aldrin and Michael
Collins. In solo mode, one player works the stations in turn. Armstrong and
Aldrin later move into Eagle, the Lunar Module. Collins stays with Columbia
while they land.”

**If showing the other presets, say:** “The separate landing laboratory supports
three local browser clients and programmed assistants. Model AI needs a
configured provider. The historical tour itself does not become an AI-flown
mission when we choose a crew preset.”

## Explain the computer and interface

**Do:** Point to the DSKY before entering commands.

**Say:** “The Apollo Guidance Computer helped calculate navigation and guidance
and control the spacecraft. The crew still made decisions and operated hardware.
Columbia and Eagle each had their own guidance computer. Saturn had a separate
computer for its normal departure burn.”

**Say:** “This panel is the DSKY: the display and keyboard. PROG tells us which
program is running. VERB tells the computer what action we want. NOUN identifies
the information. The three registers show inputs and results. ENTR enters data,
and PRO means Proceed when the computer asks us to continue.”

**Do:** Point to **LIVE ORIGINAL CMC / MODELED INSTRUMENTS**.

**Say:** “An emulator reproduces the computer’s operation so the original software
can run. Here, the computer calculations are original, while the instruments
are a modern training model.”

**Other labels, when they appear:**

| Screen component | Say |
| --- | --- |
| Verified recorded execution | “This is a retained run of the original software. Playback shows what that run actually produced.” |
| Static historical configuration | “This model explains the spacecraft arrangement. Moving the camera does not fly it.” |
| Interactive procedure trainer | “This checks selected crew actions and their order. It is a training model of the procedure.” |
| Live simulated physics | “This is the separate modern physics laboratory. Its landing controller is not original Apollo guidance.” |
| Clock | “Each view identifies its clock. Computer execution time and recorded experiment time are different from Apollo’s historical mission time.” |
| Unknown value or question mark | “The source does not provide that measurement, so we leave it unknown.” |

## Chapter 1 — Earth parking orbit: play the complete P52 task

**Do:** Open `/campaign.html?play=1&stage=earth-parking`. Keep the tour paused.
Click **Play P52 alignment**, then **Prepare alignment instruments** or
**Restart alignment setup**. Wait until the keys are enabled.

**Say:** “We begin in Earth orbit. Eagle is still stowed below Columbia, and the
Saturn upper stage is attached. Our first playable task is alignment: checking
the reference the computer uses to understand direction.”

### A. Prepare the instruments

**Say:** “The setup runs original P51 to establish a training reference. We then
perform P52 ourselves. These are modeled instrument readings, rather than
recovered measurements from Apollo 11.”

### B. Select P52

**Do:** Press `VERB 3 7 ENTR 5 2 ENTR`. Wait for PROG 52 and NOUN 06.

**Say:** “I select program 52 using the Apollo keyboard. The original software
now asks which alignment option we want.”

### C. Choose option 3

**Do:** Press `VERB 2 2 ENTR 0 0 0 0 3 ENTR`, then **PRO**.
Wait for V50 N25, code `00015`. Press **ENTR** and wait for NOUN 70.

**Say:** “We choose the option that checks and corrects the existing reference.
We will identify and sight two stars.”

### D. Identify Menkent

**Do:** Select the **30 Menkent** guide. Press
`VERB 2 1 ENTR 0 0 0 3 0 ENTR`, then **PRO**. Wait for VERB 51.

**Say:** “Our first star is Menkent. I enter its catalog code through the
keyboard. Selecting the guide only helps us aim; it does not enter the code.”

### E. Mark and confirm the first star

**Do:** Menkent begins centered in this fixture. Keep optics in **MANUAL** and
press **MARK**. At V50 N25 / `00016`, press **PRO**. Verify `00030` at NOUN 71,
then **PRO** again. Wait for NOUN 70.

**Say:** “The first star is centered in this setup. MARK captures the sighting.
We then check and confirm which star we measured.”

### F. Identify Nunki

**Do:** Select the **37 Nunki** guide. Press
`VERB 2 1 ENTR 0 0 0 3 7 ENTR`, then **PRO**. Wait for VERB 51.

**Say:** “Now we choose Nunki. Two different star directions let the computer
check the alignment.”

### G. Aim the optics

**Do:** Use the optics hand controller:

1. HIGH gain, 1-second duration: **SHAFT +** five times, reaching 100°.
2. HIGH gain, 0.1-second duration: **SHAFT +** twice, reaching 104°.
3. LOW gain, 1-second duration: **SHAFT +** twice, reaching 104.4°.

Keep optical LOS at 40°. The displayed sighting offset should be about 0.0013°.

**Say:** “I move the optics quickly toward the star, then switch to a slower
setting for the final adjustment. This controller points the optics. It does
not steer the spacecraft.”

### H. Capture the second sighting

**Do:** Press **MARK**, then **PRO** at V50 N25 / `00016`. Verify `00037` at
NOUN 71, then **PRO** to confirm.

**Say:** “I mark the second star and confirm its identity. The computer now has
both observations for its calculation.”

### I. Review the star-angle difference

**Do:** Wait for V06 N05. R1 is in hundredths of a degree. Read the actual result;
for example, `+00002` means 0.02°. The exercise requires a fit within 0.05°.
**PRO** accepts; **ENTR** recycles the sightings.

**Say:** “This number checks the agreement between our two sightings and the
catalog. We inspect it before accepting the measurements.”

**Optional, only if the display agrees:** “This run shows 0.02 degrees.”

### J. Review and apply the correction

**Do:** Press **PRO**. Wait for stable V06 N93. The three signed registers are
correction angles in thousandths of a degree. Press **PRO** to authorize them.
Wait for V50 N25 / `00014` and observe gyro output and sensor counters.

**Say:** “These are the small corrections calculated by the original computer.
I approve them. The computer sends gyro commands, and our instrument model
returns measurements. This completes the feedback loop.”

### K. Finish at P00

**Do:** At code `00014`, press `VERB 3 7 ENTR 0 0 ENTR`.
Verify all five objectives read **OBSERVED**.

**Say:** “All five alignment objectives are complete. We return to program
zero. We have completed an original-computer alignment task with modeled
instruments; the spacecraft has not left Earth orbit.”

Keep the [full player guide](P52_PLAYER_GUIDE.md) available when rehearsing.
The P52 procedure is documented in the
[original Comanche listing](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html).

## Chapter 2 — Translunar injection

**Do:** Select **Translunar injection**. Show the attached upper stage.

**Say:** “The next historical step is the burn toward the Moon. Saturn’s upper
stage supplies the thrust, guided by its own launch vehicle computer. Our app
explains this stage, but original Saturn departure execution is not connected.”

## Chapter 3 — Retrieve Eagle

**Do:** Select **Retrieve Eagle**. Show the docked Columbia–Eagle configuration.

**Say:** “After departure, Columbia separates, turns around, docks with Eagle
and pulls it from the adapter. The crew now travels toward the Moon in the
joined spacecraft. This view explains the resulting arrangement.”

## Chapter 4 — Navigate to the Moon

**Do:** Select **Navigate to the Moon**.

**Say:** “The journey includes long periods of coasting. The crew and ground
team check the trajectory and make the necessary corrections. Turning the
spacecraft changes its orientation; thrust is needed to change its velocity.”

## Chapter 5 — Brake into lunar orbit

**Do:** Select **Brake into lunar orbit**.

**Say:** “Columbia’s service engine slows the spacecraft so it can enter lunar
orbit. The computer guides the maneuver while the crew enables and monitors
it. This chapter is a historical reference, rather than a live burn.”

## Chapter 6 — Establish the lunar parking orbit

**Do:** Select **Establish the lunar parking orbit**.

**Say:** “Another burn adjusts the orbit before Eagle’s departure. The crew
checks the spacecraft and prepares for the landing mission.”

The outward mission sequence follows the app’s sourced
[NASA mission overview](https://www.nasa.gov/missions/apollo/apollo-11-mission-overview/)
and [Earth-orbit record](https://apollojournals.org/afj/ap11fj/02earth-orbit-tli.html).

## Chapter 7 — Activate Eagle and prepare guidance

**Do:** Select **Activate Eagle and prepare guidance**. Use **Play observations**
or **Next observation** on the eight-observation insert.

**Say:** “Armstrong and Aldrin prepare Eagle for independent flight. At this
point, we can inspect a separate recorded experiment with original Luminary
software. Its inputs are synthetic, and it does not continue the historical
flight shown above.”

Use one short line for each observation if stepping manually:

| Observation | Say |
| --- | --- |
| 1. P51 starts | “Original P51 begins with synthetic star sightings.” |
| 2. Reference ready | “The original software establishes its navigation reference.” |
| 3. P27 mission inputs | “The experiment supplies its documented starting state and target through original P27 transactions.” |
| 4. DAP review | “The digital autopilot settings are reviewed.” |
| 5. Mass input | “The experiment supplies the mass input used by the computer.” |
| 6. P63 selected | “Program 63 begins the descent-guidance preparation.” |
| 7. Reference readiness | “The computer passes its reference-readiness check.” |
| 8. V06 N61 review | “The original display reaches the pre-ignition crew-review point.” |

For the three scenario comparison, use the guidance appendix below, then return
to this chapter. These are separate retained experiments, not historical stages.

## Chapter 8 — Undock and inspect Eagle

**Do:** Select **Undock and inspect Eagle**, then open `/play.html`. Choose
**Begin undocking checklist**. Switch to the astronaut named by each step.

**Say:** “Eagle is ready to become a separate spacecraft. This trainer checks
28 selected crew actions in order. Some earlier preparation is assumed complete.
The probe release is operated from Columbia by Collins; it is not a command
typed into Eagle’s guidance computer.”

### Every undocking action: screen cue and short narration

These rows match the retained trainer definition. CDR = Armstrong;
LMP = Aldrin; CMP = Collins. Some LM hand assignments are teaching choices.
Crew reports acknowledge assumed checks; they do not measure pressure or hardware.

| Step | Do, at the indicated station | Say |
| --- | --- | --- |
| 1 | CMP: confirm completed tunnel closeout | “We acknowledge the earlier tunnel and hatch preparation.” |
| 2 | LMP: confirm helmets, gloves and communications | “Eagle’s crew checks protective equipment and communications.” |
| 3 | CDR: confirm hatch and cabin configuration | “We confirm the hatch and cabin are configured for separation.” |
| 4 | CDR: GUID CONT → AGS | “We select the checklist’s abort-guidance setting. This trainer records the switch selection; it does not run an AGS emulator.” |
| 5 | LMP: confirm display selections | “We verify the displays needed for this procedure.” |
| 6 | CDR: ATT/TRANSL → 2 JET | “We select the checklist’s two-jet configuration.” |
| 7 | CDR: BAL CPL → ON | “We set balance coupling on.” |
| 8 | CDR: DEADBAND → MAX | “We select the maximum deadband setting.” |
| 9 | LMP: ATTITUDE CONTROL ROLL → PULSE | “We set roll control to Pulse.” |
| 10 | LMP: ATTITUDE CONTROL PITCH → PULSE | “We also set pitch to Pulse.” |
| 11 | LMP: ATTITUDE CONTROL YAW → PULSE | “We check yaw separately. All three axes need the correct setting.” |
| 12 | LMP: MODE CONT PGNS → ATT HOLD | “We set the primary guidance mode switch to attitude hold.” |
| 13 | LMP: MODE CONT AGS → ATT HOLD | “We set the abort guidance mode switch to attitude hold too.” |
| 14 | CDR: TTCA CDR → JETS | “The commander’s controller is selected for jets.” |
| 15 | LMP: TTCA LMP → JETS | “We check the pilot’s controller selection as well.” |
| 16 | CDR: ACA/4 JET CDR → DISABLE | “We disable this separate four-jet path, as the checklist requires.” |
| 17 | LMP: ACA/4 JET LMP → DISABLE | “We check the matching setting at the pilot’s station.” |
| 18 | CDR: TTCA/TRANSL CDR → ENABLE | “We enable the commander’s translation-control path.” |
| 19 | LMP: TTCA/TRANSL LMP → DISABLE | “The pilot’s translation-control path is disabled for this configuration.” |
| 20 | LMP: confirm remaining preparation | “We report the remaining equipment and preparation checks complete.” |
| 21 | CMP: confirm Columbia ready | “Collins checks Columbia’s controls and undocking configuration.” |
| 22 | CMP: DOCK PROBE MNA breaker → IN | “We close the first docking-probe circuit breaker.” |
| 23 | CMP: DOCK PROBE MNB breaker → IN | “We close the second breaker.” |
| 24 | CDR: report Eagle ready | “Eagle reports ready before Collins commands release.” |
| 25 | CMP: DOCKING PROBE → EXTD/REL | “Collins operates Extend/Release. The trainer now releases the modeled connection.” |
| 26 | CMP: DOCKING PROBE → OFF | “We return the probe control to Off.” |
| 27 | LMP: report visual release confirmation | “Eagle’s crew reports release. The expanded model explains the disconnected arrangement.” |
| 28 | CMP: confirm inspection handoff | “The next historical task is managing relative motion and inspecting Eagle. We do not skip directly to landing.” |

**Say at completion:** “All 28 selected actions are complete. The server checked
their order, station and setting. This demonstrates a procedure model, not a
physical orbital separation.”

For a short video, prepare steps 1–24 beforehand and say that explicitly. Then
perform steps 25–28 on camera. The trainer is selected material from the
[Apollo 11 activation checklist](https://apollojournals.org/afj/ap11fj/pdf/a11_lm_systems_activation_checklist-19690708.pdf)
and the [undocking record](https://apollojournals.org/afj/ap11fj/17day5-undock-doi.html),
with detailed source mapping in `frontend/dist/data/undocking-procedure.json`.

## Chapter 9 — Lower Eagle’s orbit

**Do:** Return to the campaign and select **Lower Eagle’s orbit**.

**Say:** “After undocking and inspection, Eagle lowers part of its orbit.
This prepares a low point for powered descent. Lowering the orbit and beginning
the final descent are two different burns.”

## Chapter 10 — Descend and land Eagle

**Do:** Select **Descend and land Eagle**. Show the historical model first.

**Say:** “Historically, Eagle’s guidance moved through braking, approach and
assisted manual landing. Armstrong and Aldrin worked with the guidance and
controls while Collins stayed in lunar orbit. Our app does not yet execute that
complete historical descent.”

**Do:** Move to the separate recorded propulsion insert. Use **Next observation**
to explain individual events, or **Play observations** for the complete excerpt.

**Say:** “This separate experiment lets us inspect the engineering chain:
original computer output, engine response, sensor measurements and navigation
feedback. The test uses simplified, fixed-attitude synthetic conditions.”

### Every propulsion observation

| Observation | Say |
| --- | --- |
| 1. Pre-ignition review | “The original computer is at its crew-review display.” |
| 2. Physical state available | “The retained physical-model measurements begin here.” |
| 3. Checklist 14 | “The recording contains the computer’s checklist request and the test’s crew response.” |
| 4. Attitude review | “The computer displays attitude information. This fixed-attitude test does not prove the vehicle reached a real burn attitude.” |
| 5. Cockpit inputs | “The test supplies the recorded engine and control-switch inputs.” |
| 6. Crew enable request | “The software asks for crew permission. Permission is separate from ignition.” |
| 7. IGNITION routine | “The original ignition routine is executing.” |
| 8. ENGINE ON output | “We now observe the actual computer output requesting engine on.” |
| 9. Physical thrust | “The external engine model now produces measured thrust.” |
| 10. Sensor counts generated | “The modeled accelerometers turn the engine’s effect into sensor counts.” |
| 11. Counts delivered | “Those sensor counts are delivered back to the original computer.” |
| 12. Navigation feedback | “Original navigation now consumes that feedback.” |
| 13. P63ZOOM | “The original guidance reaches another transition in this bounded test.” |
| 14. FLATOUT | “The original software issues its high-throttle command.” |
| 15. ENGINE OFF output | “The computer removes the engine-on request.” |
| 16. P00 shutdown | “The software has returned to P00. An incomplete reset remains disclosed in the evidence.” |
| 17. Crew disarm | “A separate crew-disarm input completes the external model’s shutdown.” |
| 18. Experiment ends | “The retained test ends here. It did not execute a lunar landing.” |

**Do:** Point at the source band, the thrust readout, sensor counts and 3D view.

**Say:** “The 3D viewer follows the recorded samples. Its spacecraft is enlarged
for visibility. The engine data and sensor data retain their source observations.”

## Chapter 11 — Tranquility Base

**Do:** Select **Tranquility Base**.

**Say:** “In the historical mission, Armstrong and Aldrin now carry out surface
work and prepare to leave. Collins continues his independent orbital mission.
This chapter explains the mission; the surface activities are not playable.”

## Chapter 12 — Launch from the Moon

**Do:** Select **Launch from the Moon**. Point out the ascent-stage configuration.

**Say:** “Only Eagle’s ascent stage launches from the Moon. The descent stage
stays behind. The goal is to reach an orbit that allows the crew to meet Columbia.”

## Chapter 13 — Rejoin Columbia

**Do:** Select **Rejoin Columbia**.

**Say:** “The spacecraft rendezvous and dock. Armstrong, Aldrin and the return
cargo move into Columbia. Eagle’s ascent stage is discarded before the journey
home.”

## Chapter 14 — Depart lunar orbit

**Do:** Select **Depart lunar orbit**.

**Say:** “With all three astronauts aboard, Columbia fires its service engine
to leave lunar orbit. This places them on the path back toward Earth.”

## Chapter 15 — Navigate home

**Do:** Select **Navigate home**.

**Say:** “The crew and ground team check the return path and prepare for entry.
They are aiming for the right atmospheric entry conditions, rather than another
parking orbit around Earth.”

## Chapter 16 — Enter Earth’s atmosphere and splash down

**Do:** Select **Enter Earth’s atmosphere and splash down**. Show that only the
Command Module remains.

**Say:** “The Service Module is discarded. Columbia enters Earth’s atmosphere
with its heat shield protecting the crew. Parachutes slow the final descent,
and the mission ends with splashdown in the Pacific.”

Return chronology: [NASA mission overview](https://www.nasa.gov/missions/apollo/apollo-11-mission-overview/)
and [entry and splashdown record](https://apollojournals.org/afj/ap11fj/27day9-entry.html).

## Appendix A — Every guidance-explorer task and panel

Open `/guidance.html`. Present this at chapter 7 if desired. Its three runs
are separate synthetic experiments, not continuations of the campaign.

| Do / component | Say |
| --- | --- |
| Select 15 km orbit; Start replay | “This retained experiment starts from a synthetic 15-kilometer lunar orbit. We replay what original Luminary actually computed.” |
| P51 event | “Alignment establishes the reference needed to interpret direction.” |
| P27 event | “The test loads its documented navigation and target inputs through original software.” |
| Go to P63 | “P63 now performs the guidance preparation for descent.” |
| View recorded result | “The recorded calculation reaches crew review. Its calculated ignition time is 360.29 seconds on this synthetic mission clock. No engine firing occurs in this experiment.” |
| Select 16 km; View recorded result | “A separately executed higher-orbit case gives 360.44 seconds. These are two actual recorded answers, rather than a browser estimate.” |
| Select Missing landing site; View recorded result | “Here the target was not initialized. The original software reaches alarm 01406 and does not complete an ignition-time solution. Missing mission data has a visible consequence.” |
| Compare results | “The comparison keeps each experiment’s own recorded outcome. We do not assume these two cases define a general rule for every orbit.” |
| Moon and spacecraft geometry | “This diagram projects the supplied three-dimensional starting state. The arrow shows initial velocity direction. It is not an animated descent path.” |
| Inspect initialized 3D state | “Position tells us where the vehicle is. Velocity tells us how fast it moves and in which direction. We also need their coordinate frame and time.” |
| Recorded DSKY | “These digits came from original computer output. This replay keypad is read-only, and unavailable lamp states remain unknown.” |
| Signed time-to-go | “This is the guidance program’s signed time variable. Read it using the convention shown here, rather than treating every negative number as a fault.” |
| Calculated ignition time | “This is an absolute time on the experiment’s mission clock, not a countdown.” |
| Ignition lead | “This shows how far the calculated ignition time is ahead of the clock at that recorded solution.” |
| ROOTPSRS results | “The original numerical solver finds roots used by the guidance calculation. The browser displays its retained results.” |
| Event timeline | “We can step between real recorded events to see how the calculation develops.” |
| Evidence / provenance | “Each retained result can be traced back to the recorded execution and its source files.” |
| Capability and crew panels | “This page identifies its own available features. Planned crew controls here are different from the working local crew features in the separate landing lab.” |

### Every field note: short teaching lines

| Field note | Say |
| --- | --- |
| Where and how fast? | “A state vector combines position and velocity in three dimensions.” |
| Orbital velocity | “An orbit is continuous free fall: sideways motion keeps the spacecraft moving around the Moon.” |
| Ignition timing | “Starting a burn at a different point can change where the spacecraft goes.” |
| Guidance equation | “Guidance relates where we are, where we want to go and how much time remains.” |
| Polynomial solver | “The flight software builds an equation and searches for a value that makes it balance.” |
| Missing site | “A solver needs meaningful mission inputs. It cannot invent the landing target.” |
| 16-kilometer case | “Changing the starting state means the guidance must calculate again.” |
| Original or modern? | “Original software produced the calculations. Modern code supplies the test environment and presentation.” |
| Alignment | “The computer needs a reliable reference for direction before it can interpret its measurements.” |
| Thrust and feedback | “Thrust produces acceleration. Sensors report its effects so the computer can update navigation.” |

## Appendix B — Attitude replay and live bounded control

Open `/attitude-replay.html`. This is a separate experiment, not the next
historical step after a campaign chapter.

| Do / component | Say |
| --- | --- |
| Recorded replay; choose Yaw, Pitch or Yaw + pitch | “These recordings test rotation around supported axes. They do not simulate a descent.” |
| Play replay | “The visual model follows the external model’s recorded orientation.” |
| RCS jet activity | “These indicators decode actual original computer output bits for the small control jets.” |
| Angular-rate chart | “The graph shows how fast the vehicle rotates. Rotation rate is different from the direction it is facing.” |
| Sensor return | “The external instrument model returns orientation measurements to the computer.” |
| Compare feedback | “We compare retained connected and disconnected feedback conditions to investigate what the sensor return changes.” |
| Live AGC → Start live AGC, if available | “Now we start a fresh bounded run of original software.” |
| Briefly hold an on-screen yaw or pitch control, then release | “This on-screen control supplies a modeled Apollo hand-controller input. The original computer chooses the jet outputs; our buttons do not directly rotate the picture.” |
| Release to neutral | “We release the input and observe the response within this short, supported test.” |
| Stop run / session record | “The run is bounded and its record can be inspected. It does not establish full spacecraft flight fidelity.” |

Do not claim roll control or physical joystick hardware. Use the on-screen
buttons for the demonstration. Start live mode only when the service reports
it available; otherwise present the retained replay as a recording.

## Appendix C — Optional modern landing laboratory

Open `/mission.html`, or choose **3D landing lab** from the launcher. Keep this
separate from the original-code mission presentation.

**Say before entering:** “This extra laboratory teaches flight physics using
modern controls and synthetic starting conditions. It is not an original-AGC
landing or the next state of the historical tour.”

| Do / component | Say |
| --- | --- |
| Create a training mission; take Commander and choose assistants for other seats | “For one-player practice, I take the commander position and use programmed assistants for the other two seats.” |
| Human seats / join form, if demonstrating multiple clients | “Other local browser clients can join the open seats and share the server’s mission state.” |
| Ready and Start mission | “Each human must be ready before the mission starts.” |
| Model AI availability | “A model-driven participant requires a configured provider. A programmed fallback is identified separately.” |
| Objective and telemetry | “We watch altitude, vertical velocity, horizontal speed and remaining propellant. The server supplies the actual limits for this exercise.” |
| Throttle | “More thrust changes acceleration. It does not instantly cancel downward velocity.” |
| Pitch | “Tilting redirects the engine’s force. Some thrust then acts sideways.” |
| Cyan velocity arrow | “This arrow shows motion. The spacecraft can face one way while still moving another way.” |
| Amber landing reference | “This is the synthetic exercise reference, rather than Apollo 11’s recovered flight path.” |
| 3D / 2D switch | “Both views display the same server-owned state. They offer different ways to inspect it.” |
| Training assist, if used | “This assist is a modern teaching controller, not the Apollo Guidance Computer.” |
| LMP flight checklist | “The pilot reviews position and velocity, braking and propellant.” |
| Crew messages | “Participants can exchange flight callouts. Programmed assistant messages remain labeled.” |
| Pause / Restart | “We can stop to discuss the physics, then restart a fresh exercise.” |
| Debrief | “The outcome comes from the server’s measured final state. We report the actual result, whether it is a landing or an unsuccessful attempt.” |
| Equation a = F / m | “Force divided by mass gives the thrust’s acceleration contribution. Gravity acts at the same time.” |

Collins’s lab communications role is a teaching adaptation. He does not pilot
Eagle. Do not promise model-provider operation or a successful landing before
observing it.

## Appendix D — Optional cold-start diagnostic

Use `/campaign.html?play=1&stage=earth-parking&task=diagnostic` only to explain
readiness and recovery. It is a different starting state from the working P52
instrument task. Follow [its exact guide](EARTH_ORBIT_PLAYABLE_GUIDE.md).

| Task | Say |
| --- | --- |
| Display test | “A display test helps verify that the original computer responds to our inputs.” |
| Select P00 | “We select the base program before continuing.” |
| Live clock | “The changing clock is generated by the running computer. It is not Apollo 11’s historical flight time.” |
| Request P52 with the fixture’s IMU off | “The original software rejects this unready instrument state and reports alarm 00210.” |
| Recover to P00 | “We deliberately return to P00 through the original keys. This is a diagnostic, rather than a completed alignment.” |

## Closing and likely questions

**Say:** “We connect original software, crew actions and understandable
visualizations. Today’s live alignment and recorded feedback tests give us
inspectable engineering results. Completing the historical flight requires
more verified spacecraft and instrument integration.”

| Judge asks | Answer |
| --- | --- |
| Is this original Apollo code? | “The labeled computer tasks execute or replay original Comanche or Luminary software. The interface and external models are modern.” |
| Did you simulate the entire landing? | “No. We demonstrate bounded original-code experiments and a separate educational landing lab.” |
| What did the player accomplish? | “In P52, the player sights two stars, reviews original calculations, approves correction and receives completion based on observed feedback.” |
| Why use stars? | “They provide known directions for checking the navigation reference.” |
| Does the AGC control every action? | “No. Crew hardware operations and Saturn’s launch-vehicle computer have separate responsibilities.” |
| What comes next? | “Additional validated instruments, control authority and vehicle dynamics, connected one mission stage at a time.” |

## Recording checklist

- Rehearse the entire P52 checklist once before recording.
- Use manual chapter navigation so narration sets the pace.
- Keep source/mode labels visible when changing experiences.
- Read numerical results from the current screen; do not memorize one run’s values.
- Tell viewers if preparations were completed before the recorded segment.
- Shorten waiting periods in editing, preserving the order of actions and results.
- Keep original execution, procedure training, references and the optional lab distinct.

This script is mapped to the current campaign catalog, undocking procedure,
recorded showcase event lists and application guides. It adds presentation
material only; it does not add or validate flight functionality.
