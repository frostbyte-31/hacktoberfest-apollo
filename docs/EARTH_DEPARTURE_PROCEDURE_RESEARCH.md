# Earth-orbit alignment and departure: procedure research

Research date: 18 October 2026. This is a source and integration audit, not a
claim that an alignment or translunar flight has been implemented or validated.

## Correct mission and computer sequence

The first Earth-orbit task belongs to **Columbia's Command Module Computer
(CMC), running Comanche 055**. Eagle remains stowed inside the spacecraft–LM
adapter above the S-IVB. The sequence is parking orbit, systems checks and
alignment, translunar injection (TLI), CSM separation, transposition/docking and
LM extraction, then translunar coast. Lunar-orbit undocking occurs much later.
The final flight plan places the optional early realignment in the first night
period; it also identifies the CDR/LMP/CMP couch positions through TLI. See
[Apollo 11 final flight plan, sections I and III, pages 1-1, 1-13 and 3-1–3-4](https://www.ibiblio.org/apollo/Documents/Apollo11FlightPlan.pdf).

At **000:18:42 GET**, Houston recommended P52 and supplied a **+0.22° delta
azimuth correction**. Collins accepted. The transcript records optics-cover
jettison at **000:38:46**, star work near **000:45**, the TLI Go at
**002:26:38**, and ignition near **002:44:16**. This establishes chronology;
it does not supply a complete emulator checkpoint or all instrument readings.
See [Apollo 11 Earth-orbit transcript](https://www.apollojournals.org/afj/ap11fj/02earth-orbit-tli.html).

The flown pair was **30 Menkent / 37 Nunki** (octal codes), followed by a
**34 Atria** check. Aldrin reported N05 `00001`, N93 `+00016, +00033, +00152`
and torque time **000:48:15** at **000:53:35**. Use the radioed X value: the
journal's earlier commentary gives `.018`, whereas the spoken report gives
`.016`. Neither supplies raw shaft/trunnion measurements for a checkpoint.

## What a completed P52 means

P52 **option 3** preserves the reference orientation and corrects drift,
assuming uninterrupted IMU power and no gimbal lock. Its original entry calls
`R02BOTH`; an IMU-off or invalid-reference rejection requires valid
hardware/state initialization. The program then requests an orientation option
and celestial-body acquisition.

The original fine-alignment path `R51` requests a star identity with
**V01N70**, runs optics tracking/sighting, acquires a second star, displays the
star-angle difference with **V06N05**, computes a correction and requests
acceptance of the **V06N93** gyro torquing angles. `R55` sends the original
torque commands after the crew proceeds. Its finish includes a **V50N25 /
00014** request to select P00. A P00 selection alone does not establish that
these calculations or torque operations happened. See
[Comanche 055 P51–P53, printed pages 737–742 and 756–761](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html).

The real interaction therefore needs the navigation-panel optics mode/zero
controls, shaft/trunnion hand control, telescope/sextant line of sight, MARK and
MARK REJECT, in addition to DSKY input. The computer samples **three IMU CDU
angles, two optics CDU angles and time** when accepting a sighting. Those
observations must originate in the external instrument/spacecraft model.
Exactly which switch positions and star choices are flown must be established
against the mission's checklist, not copied from a later Apollo mission.

The application should separately report computer execution, fixture
initialization, measurement origin, software acceptance and physical alignment
error. A declared ideal instrument fixture can exercise the genuine
algorithm; its success does not prove reproduction of Collins's historical
measurements or a flying spacecraft.

## TLI belongs to Saturn's IU

Nominal Saturn guidance uses the **Launch Vehicle Digital Computer (LVDC)**,
the LVDA, the ST-124 inertial system and the analog flight-control computer.
These issue sequencing and steering commands for the S-IVB. Apollo 11's
technical summary describes manual spacecraft takeover as a backup, with
additional conditions during powered flight. It is not the nominal TLI
interaction. See [AS-506 technical information summary, printed pages 27–29](https://www.ibiblio.org/apollo/Documents/19700011707_1970011707.pdf).

The actual preburn crew transcript checks **LV GUIDANCE — IU**, **SC CONT —
SCS**, **TRANSLUNAR — INJECT**, EDS power, direct-ullage circuit breakers and
pyro controls. The crew sets the EMS delta-V counter and event timer, checks
attitude and monitors the burn. These are crew preparation/monitor controls,
not an astronaut typing a DSKY command that directly starts nominal TLI. The
crew debrief describes checking DSKY altitude rate at 30-second intervals and
standing ready for manual intervention. See [technical crew debrief, sections
4–5](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11tcdb.html).

**Do not transplant P15 from Artemis.** The retained Comanche 055 `MAIN.agc`
does not include P15. The publicly listed P15 source is part of **Artemis 072,
Apollo 15–17**. See [Artemis P15 identification](https://www.ibiblio.org/apollo/listings/Artemis072/P15.agc.html).

Comanche's **V83** is the original `R31` range/range-rate/angle display. It is
not a TLI engine command. `P11` contains the Earth-orbit insertion monitor and
Saturn stick-takeover interfaces; its existence is not proof that nominal
TLI is controlled by this CMC. See [Comanche R31](https://www.ibiblio.org/apollo/listings/Comanche055/R31.agc.html),
[extended verbs, V83](https://www.ibiblio.org/apollo/listings/Comanche055/EXTENDED_VERBS.agc.html),
and [P11 program description](https://www.ibiblio.org/apollo/listings/Comanche055/P11.agc.html).

### Correct CMC burn monitor: P47 and N62

The Apollo 11 AC/Delco manual identifies **P47 — Thrust Monitor**:
`VERB 3 7 ENTR 4 7 ENTR` starts the program and its flashing **V16N83**
display of accumulated body-axis delta-V. Selecting **N62** displays inertial
velocity, altitude rate and altitude. `V16N62E` explicitly requests that
monitor. P47 should run immediately around a thrust maneuver to limit
integration/bias error. See [AC/Delco Apollo 11 manual, P47 program description
and selected displays](https://www.ibiblio.org/apollo/Documents/AcElectronicsApollo11.pdf).

This is also directly visible in the retained original source:
`P47CSM` calls `R02BOTH`, starts the average-G path, and `CALCN83` calls
`S11.1` to calculate **VI, H, HDOT for N62**. `P47/DSP` selects `V1683`.
Thus **N83 is not V83**. Entering only `V83E` requests the separate R31
routine and **V16N54**; entering `V82E` requests orbital parameters
**V16N44**. Neither replaces P47's N62 burn monitor. See
[Comanche P40–P47, printed pages 691–692](https://www.ibiblio.org/apollo/listings/Comanche055/P40-P47.agc.html)
and [extended verbs, printed pages 254–256](https://www.ibiblio.org/apollo/listings/Comanche055/EXTENDED_VERBS.agc.html).

The transcript's preburn reference to V83 does not establish that V83 was the
VI/HDOT/H display. The original source and mission-specific program manual
resolve that ambiguity. Do not create a P15 control or relabel an N54 display
as N62.

### Verified panel labels and preparation positions

These identify historical controls for future integration; this milestone
does not connect them to a Saturn reconstruction.

| Physical control | Verified positions/action | Evidence locator |
| --- | --- | --- |
| LAUNCH VEHICLE GUIDANCE | **IU / CMC**; nominal pre-TLI **IU** | Original training panel diagram; actual voice checks at 002:04:12 and 002:12:53 |
| XLUNAR | **INJECT / SAFE**; nominal **INJECT** | Original training panel diagram; actual voice check at 002:23:39 |
| SC CONT | Nominal **SCS** | Actual voice check at 002:24:48; do not infer unverified alternative positions here |
| EMS MODE | **STBY**, then **NORMAL** for the test; returned **STBY** before delta-V loading | Actual voice sequence 001:55:23–001:57:48 |
| EMS FUNCTION | **OFF**, **ΔV SET**, **ΔV TEST**, **ΔV** | Actual sequence 001:55:20–002:01:00; these are spoken function names, not proof of the exact combined SET/VHF-ranging panel caption |
| EMS delta-V set control | Load historical TLI monitor value **10,435.6 ft/s** | Actual confirmation at 002:00:52; reference value, not new simulated telemetry |
| Digital event timer | Preset **51:00**, stopped | Actual preset discussion 002:04:44–002:05:08; exact start event and switch markings require the mission cue card/control diagram before automation |

Panel labels are visible in the original
[Apollo Training: Guidance and Control, Block II, S/C 101, September 1967](https://www.ibiblio.org/apollo/Documents/ApolloTrainingGuidanceAndControl_09-67.pdf)
and [Sequential Systems training control diagrams](https://www.ibiblio.org/apollo/Documents/apollo_training_a-324_sequential_systems.pdf).
The flown positions/times come from the [Earth-orbit transcript, stated GET
locators](https://www.apollojournals.org/afj/ap11fj/02earth-orbit-tli.html).

### Optics hand control bounds

The operations handbook's **manual direct** mode maps forward/back to
increasing/decreasing trunnion and right/left to increasing/decreasing shaft.
Maximum drive rates are approximately **20°/s shaft and 10°/s trunnion**.
LOW/MED/HIGH select drive sensitivity; exact intermediate gains have not been
verified here. A fixed-duration jog must disclose its chosen rate rather than
claiming an exact measured historic hand-controller response.

**RESOLVED** additionally transforms the commands using shaft orientation and
the cosecant of the star-line-of-sight angle; independent shaft/trunnion jogs
must be labelled **DIRECT**. MARK and MARK REJECT are separate physical
buttons. See [Apollo Operations Handbook, §§2.2.4.9–2.2.4.10.5, printed pages
2.2-33–2.2-35](https://www.ibiblio.org/apollo/Documents/SM2A-03-BLOCKII-2.1_2.2.pdf#page=37).
That scan records an April 1969 basic date with April 1970 changes; the
[Apollo 11 handbook transcription](https://safepic.com/Apollo11ManualWeb/Guidenance%20and%20Navigation.html)
corroborates the manual-direct direction and maximum-rate descriptions.

## Available implementation and remaining contracts

At this audit's starting revision, the repository exposes fresh native
Comanche DSKY execution through `backend/cmc_native.py` and the Earth-orbit
service. Its retained evidence proves original display/key behavior. It has
no validated historical post-insertion checkpoint, operational CSM
IMU/optics model or Saturn departure provider. The earlier Luminary P51 result
is explicitly a stationary synthetic **LM** instrument fixture; its source,
coordinates and hardware assumptions cannot silently become Columbia P52.

The upstream Virtual AGC project has a **yaLVDC CPU emulator**, but documents
that it does **not** emulate the LVDA. Its current available-software table
lists AS-206RAM, AS-512 and AS-513; no Apollo 11 **AS-506** flight image was
located in that catalog or in this repository. An emulator without the
appropriate program and peripherals cannot authenticate an Apollo 11 burn.
See [Virtual AGC LVDC catalog and emulator scope](https://www.ibiblio.org/apollo/LVDC.html).

Before enabling a physical departure, retain:

- A provenance-checked initialization/checkpoint with known attitude,
  REFSMMAT, time and state-vector frame/units.
- An external IMU/optics model that consumes actual output commands and
  returns measured CDU/counter/discrete inputs, with documented latency.
- Negative alignment controls: incorrect star identity, displaced marks,
  absent sensor feedback and rejected/omitted torque approval.
- The correct Saturn program/provider, LVDA/FCC/APS/J-2 interfaces and backend
  translational state. Explicitly distinguish any modern implementation of
  documented guidance from execution of an original recovered flight image.
- Crew controls connected to real provider actions, plus original-input/raw
  output traces and causal checks before awarding alignment or departure.

These are acceptance boundaries. They should not be replaced by a countdown,
an animated trajectory or a front-end success flag.
