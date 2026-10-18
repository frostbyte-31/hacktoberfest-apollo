# Play the cold-start computer diagnostic

The default Earth-orbit task now supports [complete original P52 with modeled instruments](P52_PLAYER_GUIDE.md). This page documents the separately retained cold-start diagnostic.

The first playable task operates **Columbia's original Comanche 055 Command Module Computer**. Your DSKY button presses are sent to the emulator as hardware inputs, and original Apollo software produces the displayed digits. The objective is to check the controls, inspect the live computer clock, diagnose P52's actual readiness gate, and recover to P00.

This is a fresh computer startup presented in the Earth-orbit chapter. It does not reconstruct Apollo 11's post-insertion computer memory, orbital state, IMU or star measurements. Completing the task means **computer diagnostic complete**; alignment and flight remain unperformed.

## Start it

From the repository root:

```sh
make play
```

Keep that terminal running. Use a modern browser at [http://127.0.0.1:4173/](http://127.0.0.1:4173/). Playing requires Python 3 and a C compiler for the pinned native emulator; it does not require npm or Node. Read any startup error before trying the browser. If port 4173 is already occupied, first check whether the application is already open there. To start another instance without stopping anything:

```sh
make play PORT=4180
```

Then use `http://127.0.0.1:4180/` for every link below. A recorded-only server cannot run this live CMC task.

## To-do: observe and play the new starting point

- [ ] On the home page, select **Apollo mission**, choose **Solo**, then **Open Earth-orbit task**. Select **Cold-start diagnostic** above the console. Alternatively open [the task directly](http://127.0.0.1:4173/campaign.html?play=1&task=diagnostic).
- [ ] Confirm the chapter is **Earth parking orbit**. All three astronauts are in Columbia; Eagle is stowed inside the closed adapter. The S-IVB is part of the correct departure configuration.
- [ ] Click **Start Columbia's CMC**. Allow the initial execution and relay observations to arrive. The panel identifies **live original CMC execution** and reports CPU time separately from historical mission time.
- [ ] Use the **on-screen DSKY**, one key at a time. After each click, wait until the execution acknowledgement finishes and the keys are enabled again. Read both the digits and the next-action instruction. There is no keyboard spacecraft steering.
- [ ] Work through the five steps below in order. After each sequence, wait for its step to become **OBSERVED** before proceeding. The task checks actual computer observations; a button press alone does not complete a step.
- [ ] After the last recovery, verify that the panel reports the computer checkpoint observed, while **alignment completed: no** and **flight executed: no** remain explicit.
- [ ] Open **Original software and input provenance**. Inspect the Comanche rope and emulator hashes, session identity, and input channel information. The last-key line identifies what you actually sent.

### 1. Exercise the original display test

Press:

```text
VERB  3  5  ENTR
```

Observe the numerical displays fill with eights from the original software. Allow the original test's approximately **five CPU seconds** to pass before continuing. This is control familiarization using genuine Comanche functionality; it is not claimed as a checklist action Collins performed at this historical instant.

The adapter decodes original digits and register signs from channel 010 relay words. **KEY REL**, **OPR ERR** and **COMP ACTY** show their last observed channel 011 states as ON or OFF. The **VERB / NOUN flash request** is reported as active or clear, without timed blinking. A sign or indicator marked `?` has not been observed; the other caution/status lamps remain unknown. Do not treat `?` as off or as a failed lamp test.

### 2. Select P00

Press:

```text
RSET  VERB  3  7  ENTR  0  0  ENTR
```

Observe **PROG 00**. RSET is an original error-reset key; it clears the software alarm history but does not fix an IMU or create a reference orientation.

### 3. Observe the live computer clock

Press:

```text
VERB  1  6  NOUN  3  6  ENTR
```

Enter the **entire sequence**, including VERB, NOUN and the final ENTR, even if part of the requested display is already visible. Observe the original V16N36 clock display and wait until at least one of R1, R2 or R3 changes. The checkpoint requires **two different observed `(R1, R2, R3)` clock tuples at increasing CPU cycles** after this complete request. Wait for the clock step to become OBSERVED before selecting P52. Its clock begins with this session's computer startup; it is **not Apollo 11's historical GET** and does not move a spacecraft through an orbit.

### 4. Request P52 and identify the actual readiness gate

Press:

```text
VERB  3  7  ENTR  5  2  ENTR
```

Then request the alarm display:

```text
VERB  0  5  NOUN  0  9  ENTR
```

Look for **`00210` in R1, R2 or R3**. N09 shows three alarm-history slots, so the code is not guaranteed to occupy R1. This is the actual fresh-start **IMU-off readiness alarm**. Other startup history can coexist; do not reinterpret an existing `01107` entry as the P52 result.

Historically, Collins performed P52 option 3 after launch. This session has no validated post-insertion IMU, so the original program refuses to proceed normally. Identifying that refusal is the task. Do not report “P52 aligned” or enter invented star data. The next required integration is physical IMU and optics support with a validated reference orientation.

### 5. Clear the diagnostic and recover to P00

Press:

```text
RSET  VERB  3  7  ENTR  0  0  ENTR
```

Wait for **PROG 00** and the observed diagnostic-completion message. The final P00 request is required even if the program display was already 00 after an alarm. It demonstrates an intentional recovery through real controls.

**Restart Columbia's CMC** begins a fresh diagnostic. **Stop computer** ends execution. If an input fails to acknowledge, refresh or reconnect and inspect the observation; the interface does not automatically resend an uncertain key press.

## To-do: observe the game as a whole

Use this order to distinguish what you can play from what you can currently inspect:

1. **Earth orbit:** complete the live CMC task above. Drag the 3D configuration to examine it; this changes the camera only. The model does not respond to DSKY inputs because spacecraft motion is not integrated here.
2. **Earth to lunar orbit:** select the chronological chapters for TLI, transposition/docking/extraction, coast and lunar-orbit insertion. Read the control-authority descriptions. These stages are historical references; they are not unlocked flight maneuvers. The optional guided tour navigates those references and never presses computer keys for you.
3. **Original lunar guidance:** open [Original guidance](http://127.0.0.1:4173/guidance.html). Select each available retained scenario and step the genuine AGC recordings, DSKY output and source provenance. The synthetic experiment geometry is not the historical Apollo 11 trajectory.
4. **Undocking:** open the [playable undocking trainer](http://127.0.0.1:4173/play.html). Work the selected source-backed checklist through the three stations and use each real labelled control. This trainer validates procedure order and animates the docking model; it does not run AGC/AGS guidance or an undocking flight dynamics simulation.
5. **Descent evidence:** return to the mission's descent chapters and inspect original guidance/propulsion recordings. A recorded ignition or bounded feedback test is not a demonstrated complete lunar landing.
6. **Surface to home:** inspect ascent, rendezvous/docking, return burn, coast, and entry/splashdown chapters. Notice that Eagle's descent stage stays on the Moon and only the Command Module returns through the atmosphere. These remain sourced configuration references.
7. **Other playable experiments, separately:** open [Attitude evidence](http://127.0.0.1:4173/attitude-replay.html) for the supported bounded original-AGC attitude interface. Use [the shared 3D landing laboratory](http://127.0.0.1:4173/mission.html) through the home page's **3D landing lab** setup to try server-owned educational physics and crew/assistant combinations. That laboratory uses modern control logic and synthetic initial conditions; it is separate from original Apollo flight.

There is presently no continuous original-computer-controlled Earth–Moon–Earth flight. Each experience identifies its own source and scope. The new task adds a manually playable original CMC interaction at the first chapter without representing the remaining historical stages as implemented flight.

## Historical and technical references

- [Apollo 11 Flight Journal, Earth orbit, 000:18:42 and approximately 000:45](https://apollojournals.org/afj/ap11fj/02earth-orbit-tli.html): Houston's P52 request and Collins's alignment activity.
- [Final Apollo 11 Flight Plan, page 3-1](https://www.ibiblio.org/apollo/Documents/Apollo11FlightPlan.pdf): first-hour P52 option 3 and crew preparation.
- [Comanche 055, P51–P53](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html): original alignment programs.
- [Comanche 055, IMU status routines, pages 1443–1444](https://www.ibiblio.org/apollo/listings/Comanche055/IMU_MODE_SWITCHING_ROUTINES.agc.html): real readiness checks and alarm paths.
- [Comanche 055, PINBALL, pages 385–386](https://www.ibiblio.org/apollo/listings/Comanche055/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc.html): V35 display-test implementation.
- [Procedure research and initialization limits](EARTH_ORBIT_PROCEDURE_RESEARCH.md): source-derived successful P52 path and prerequisites that this diagnostic does not claim to satisfy.
