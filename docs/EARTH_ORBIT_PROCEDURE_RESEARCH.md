# First playable Earth-orbit procedure: research and limits

Research date: 18 October 2026. This document identifies a small authentic CMC interaction that can become playable without representing a simulated translunar flight. It does not certify an implementation or a completed alignment.

## Historical starting point

Apollo 11's first-hour flight plan assigns the Command Module Pilot an optional **P52, option 3, REFSMMAT** IMU realignment. The same page places the stack in Earth parking orbit with Eagle still stowed in the adapter. It also records the launch crew positions and optics-cover preparation. See the [final flight plan, page 3-1, 00:00–01:00](https://www.ibiblio.org/apollo/Documents/Apollo11FlightPlan.pdf).

The actual mission transcript makes this a particularly useful first task: at **000:18:42 GET**, Houston recommended P52 and supplied a **+0.22° delta-azimuth correction**; Collins accepted. His star work is documented around **000:45 GET**. Those are historical references, not initial conditions proven by this application's emulator. The correction must not be inserted into an arbitrary register merely to make a demonstration work. See the [Earth-orbit Flight Journal, 000:18:42 and 000:45:02](https://apollojournals.org/afj/ap11fj/02earth-orbit-tli.html).

Use the **Command Module Computer, Comanche 055**, for this task. Eagle's Luminary software is not a substitute. The [Comanche source release identification](https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html) identifies the CM program as Comanche revision 055 / Colossus 2A.

## Recommended bounded objective

**As Collins, select P52 and request the retained REFSMMAT orientation. Reach the original computer's celestial-body acquisition prompt.**

This is a live computer preparation checkpoint, not “Earth orbit complete,” “IMU aligned,” “ready for TLI,” or a passed spacecraft inspection. The next physical task requires telescope/sextant acquisition and real measurement inputs.

The [P51–P53 listing, pages 737–741, `PROG52`, `P52A`, `P52B`, `P52C`](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html) describes the existing reference orientation as known; option 3 corrects drift without a power interruption or gimbal lock. The routine checks IMU status, requests the orientation option, and routes the REFSMMAT choice to acquisition and fine-alignment routines. Reaching its acquisition request is supportable without claiming that star measurements have been taken.

### Expected original-software interaction

These are source-derived expectations. Application acceptance must compare them with **actual channel output** from the pinned Comanche execution; do not hardcode the responses in the frontend.

| Crew action | Original CMC response to verify | Scope |
| --- | --- | --- |
| Use DSKY `VERB 3 7 ENTR 5 2 ENTR` | Program selection reaches the P52 orientation request, provided IMU checks pass | Select a real major mode |
| Inspect `VERB 50 / NOUN 06` | R1 requests orientation selection (`00001`); R2 holds the current option; R3 is blank | Display observations are authoritative |
| Load R2 with `00003`, using `VERB 2 2 ENTR 0 0 0 0 3 ENTR` while N06 remains selected | R2 reflects the loaded octal option | Select REFSMMAT; do not add a plus sign |
| Release the display when requested, then press the real `PRO` control | Original P52 progresses to `VERB 50 / NOUN 25`, R1 `00015` | Acquisition requested, alignment not completed |

The [display-interface listing, pages 1454–1456, `GOPERF4`, `GOPERF4R`, `GOPERF1`](https://www.ibiblio.org/apollo/listings/Comanche055/DISPLAY_INTERFACE_ROUTINES.agc.html) explains the option request and register usage: a V04N06 display is followed by V50N06; checklist requests use V50N25. The [assembly and operation information, pages 25–26](https://www.ibiblio.org/apollo/listings/Comanche055/ASSEMBLY_AND_OPERATION_INFORMATION.agc.html) maps R1 code `00001` to IMU orientation, component 2 choice `3` to REFSMMAT, and checklist `00015` to celestial-body acquisition. These option codes carry no distance or time units.

The exact initial R2 default and whether `KEY REL` is needed depend on original execution state. P52's source chooses a default from its preferred-orientation flag. The UI must follow observed output rather than insist that every boot begins with a particular option value.

## DSKY electrical inputs

The main-panel DSKY's ordinary key entries go through **input channel 015 octal**, with a five-bit code. A navigation-panel DSKY uses channel 016. **PRO has no five-bit keycode**; it is a separate discrete. The [Apollo Operations Handbook, Block II, volume 1, page 2.2-22](https://www.ibiblio.org/apollo/Documents/49176721-Apollo-Operations-Handbook-Block-II-Spacecraft-Volume-1.pdf) describes the main/navigation key channels and the separate PRO control.

For the pinned Virtual AGC interface, the [developer reference, input channels 015 and 032](https://www.ibiblio.org/apollo/developer.html) documents these octal codes:

| Key | Code | Key | Code |
| --- | --- | --- | --- |
| 0 | 020 | 1–9 | 001–011, corresponding to decimal digits |
| VERB | 021 | RSET | 022 |
| KEY REL | 031 | + | 032 |
| − | 033 | ENTR | 034 |
| CLR | 036 | NOUN | 037 |

`PRO` uses **channel 032 bit 14**, mask **020000 octal**, active low. Preserve other input discretes while pressing and releasing it. A V33E request follows a software proceed branch but is not the same physical input, so a button labelled PRO must send the discrete rather than silently type V33E.

## What must be initialized or remain unavailable

An application boot of a preserved rope is not an Apollo 11 post-insertion checkpoint. To offer the P52 setup objective, explicitly report any fixture initialization and its provenance. At minimum, verify live CMC startup, IMU power/operate discretes, the IMU readiness path, and the origin/validity of the retained REFSMMAT. CPU elapsed time is not historical GET.

A full alignment additionally needs spacecraft/platform attitude, optics-mode controls, actual telescope/sextant geometry, mark timing and encoder measurements, known star identities, IMU torquing output and physical feedback. Do not auto-create ideal marks, torque angles, state vectors, or a success report. The authentic computer may reject an unsuitable initial state; that rejection is evidence, not a reason to bypass its checks.

The [IMU status routine, pages 1443–1444, `R02BOTH`](https://www.ibiblio.org/apollo/listings/Comanche055/IMU_MODE_SWITCHING_ROUTINES.agc.html) checks the reference-orientation and ISS prerequisites. **Actual fresh-Comanche execution in this implementation first produces IMU-off alarm `00210`**, rather than the orientation option prompt. It can appear in any of the three N09 alarm-history registers. Do not substitute reference-matrix alarm `00220` for this observed result: a validated REFSMMAT is an additional, unproven prerequisite beyond the first encountered IMU gate. A live task asks the player to select P52, read the actual alarm using V05N09, and recover to P00. That is a completed diagnostic exercise; it must not award an alignment, Earth-orbit, or TLI milestone. A cold boot with valid code execution is not evidence of a retained post-insertion reference orientation.

No TLI permission follows from this bounded objective. Nominal S-IVB ignition and guidance belong to the Saturn launch-vehicle system; a new live CMC DSKY endpoint does not establish a launch-vehicle or translunar flight simulation.

## Smallest fallback if the P52 prerequisites cannot be demonstrated

**Live Comanche DSKY familiarization** can execute `VERB 3 5 ENTR`, observe the actual light/display test, wait for its original five-second lamp timeout, and recover using the original controls. The [PINBALL listing, pages 385–386, `VBTSTLTS`, `TSTLTS2`, `TSTLTS3`](https://www.ibiblio.org/apollo/listings/Comanche055/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc.html) implements the test and fills the numerical displays with eights.

V35 is genuine CMC functionality, but these sources do **not** establish that Collins performed V35 at the selected Earth-orbit instant. Label it optional control familiarization, not an Apollo 11 flown checklist action. Prefer the historically situated P52 setup checkpoint once its prerequisites are demonstrably satisfied.

The shipped first task combines this control familiarization with a real P52 readiness diagnosis: V35 display digits, P00, V16N36 computer clock, P52 request, V05N09 observation of `00210`, then RSET and V37E00E recovery. The UI's diagnostic completion is based on actual input intent and original display observations. It is not the unimplemented successful P52 sequence described above. See [the player observation checklist](EARTH_ORBIT_PLAYABLE_GUIDE.md).

## Acceptance evidence to retain

Retain the pinned emulator/rope identities, declared initialization operations, each crew key/discrete input, CPU cycle counts, raw output-channel packets and decoded display observations. Compare the successful setup path with an omitted/wrong orientation input and an unavailable IMU case. This verifies causal original-software interaction without claiming vehicle flight fidelity.
