# Apollo 11: the campaign's historical sequence

The campaign begins in **Earth parking orbit**. Its three goals are to reach lunar orbit, land Eagle, and return the crew to Earth. The third goal ends with **direct atmospheric entry and Pacific splashdown**, rather than an Earth-orbit insertion. Apollo 11 did not brake back into a parking orbit around Earth.

The source-backed chapter catalog is [apollo-campaign.json](../frontend/dist/data/apollo-campaign.json). Its event times are historical references measured from launch, **not elapsed application time, simulated timestamps, or telemetry**. A chapter illustration is not evidence that the maneuver has been computed or flown by this application. Rounded labels deliberately avoid claiming more timing precision than the cited event supports.

## Goal 1: Earth parking orbit to lunar orbit

| Chapter | Historical reference (GET) | Spacecraft configuration and action |
| --- | --- | --- |
| Earth parking orbit | Insertion ~000:11:49 | Columbia above the closed Spacecraft–LM Adapter (SLA), Eagle stowed inside it, and Saturn's S-IVB upper stage still attached. Systems checks and CMC platform alignment precede departure. |
| Translunar injection (TLI) | Ignition 002:44:16 | The S-IVB J-2 engine restarts. The Saturn guidance system sends the stack toward the Moon. |
| Transposition, docking and extraction | 003:17–004:17 | Columbia separates, turns to face Eagle, docks and extracts it from the adapter. Only after this operation is the familiar nose-to-nose CSM/LM pair established. |
| Translunar coast | Between TLI and lunar arrival | Navigation observations, spacecraft checks and the required correction prepare the lunar approach. |
| Lunar orbit insertion (LOI-1) | Ignition ~075:49:50 | Columbia's Service Propulsion System (SPS) brakes the docked spacecraft into lunar orbit. |
| Lunar orbit circularization (LOI-2) | Ignition 080:11:36 | A second SPS maneuver lowers the high side of the orbit before the later LM departure. |

Sources: [NASA postlaunch mission operation report, Table 5](https://www.nasa.gov/wp-content/uploads/static/history/afj/ap11fj/pdf/a11-postlaunch-rep.pdf), [Earth orbit and TLI transcript](https://apollojournals.org/afj/ap11fj/02earth-orbit-tli.html), [transposition, docking and extraction transcript](https://apollojournals.org/afj/ap11fj/03tde.html), [LOI transcript](https://apollojournals.org/afj/ap11fj/12day4-loi1.html).

## Goal 2: Eagle to the lunar surface

| Chapter | Historical reference (GET) | Spacecraft configuration and action |
| --- | --- | --- |
| LM preparation | Before ~100:12 | Armstrong and Aldrin activate and prepare Eagle; Collins operates Columbia. Guidance, propulsion and crew hardware checks precede release. |
| Undocking and inspection | Undocking 100:12:03 | Collins commands the docking-probe release from Columbia. The crews confirm separation, manage relative motion and inspect Eagle. The later CSM separation maneuver is distinct. |
| Descent orbit insertion (DOI) | 101:36:14 | After the CSM separation maneuver and LM alignment, Eagle uses its descent engine to establish the low point for powered descent. |
| Powered descent | ~102:33–102:45:40 | P63 braking, P64 approach and Armstrong's assisted manual P66 landing. Radar, guidance, crew controls and spacecraft response all matter. |
| Lunar surface stay | Landing to liftoff ~124:22 | Armstrong and Aldrin perform surface operations and prepare to ascend. Collins remains in lunar orbit aboard Columbia. |

Sources: [undocking through DOI transcript](https://apollojournals.org/afj/ap11fj/17day5-undock-doi.html), [NASA landing transcript and crew comments](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html), [NASA final flight plan](https://www.nasa.gov/wp-content/uploads/static/apollo50th/pdf/a11final-fltpln.pdf).

Eagle's landing gear was deployed during LM activation **before undocking**. The lunar-departure model should therefore show deployed gear by the preparation/release chapters; an Earth-parking model shows the LM stowed in the closed adapter. [NASA's mission history describes this order explicitly](https://www.nasa.gov/history/50-years-ago-one-small-step-one-giant-leap/).

The landing record puts P64 entry at approximately **102:41:32** and P66 at **102:43:22**. Armstrong's ACA stick commands continued through the LM computer's digital autopilot; his final landing was not a fully automatic trip to the original target. Human decisions, control-stick inputs, descent-rate commands and the engine-stop action are part of the authentic procedure.

## Goal 3: Lunar ascent to Earth recovery

| Chapter | Historical reference (GET) | Spacecraft configuration and action |
| --- | --- | --- |
| Lunar ascent | Liftoff 124:22:00.8 | Eagle's ascent stage lifts off using its ascent engine and P12 guidance. The descent stage remains on the Moon. |
| Rendezvous and docking | Docking 128:03:00 | Eagle's ascent stage rejoins Columbia. Armstrong, Aldrin and return cargo transfer into the CSM; the ascent stage is jettisoned before departure. |
| Trans-Earth injection (TEI) | Ignition 135:23:42.3 | Columbia's SPS engine sends all three astronauts toward Earth. Eagle does not perform this burn. |
| Trans-Earth coast | TEI to entry preparation | Navigation, a correction and spacecraft configuration prepare the direct-entry corridor. |
| Entry and splashdown | Entry 195:03:06; splashdown 195:18:35 | The Service Module has been jettisoned at ~194:49:13. The Command Module alone enters, slows in the atmosphere and descends under parachutes to the Pacific. |

Sources: [NASA Mission Report, sections 5, 7.4 and 7.5](https://www.nasa.gov/wp-content/uploads/static/apollo50th/pdf/A11_MissionReport.pdf), [rendezvous and docking transcript](https://apollojournals.org/afj/ap11fj/19day6-rendezvs-dock.html), [TEI transcript](https://apollojournals.org/afj/ap11fj/21day6-tei.html), [entry and splashdown transcript](https://apollojournals.org/afj/ap11fj/27day9-entry.html), [NASA mission overview](https://www.nasa.gov/missions/apollo/apollo-11-mission-overview/).

The final Mission Report's splashdown time, 195:18:35, differs from the unofficial PAO time used in parts of the transcript. Early postlaunch reports also contain preliminary undocking/landing times. The catalog uses the later, final-report-backed references or explicitly rounded labels rather than mixing planned and actual event times.

## Which computer controlled what?

“Every Apollo action was controlled by the AGC” is not a historically accurate requirement. The accurate requirement is to preserve the **correct vehicle, computer, crew authority and hardware path for each action**.

| System | Historical responsibility | Product boundary |
| --- | --- | --- |
| Saturn Instrument Unit: LVDC, LVDA and flight control computer | Normal launch-vehicle guidance and control, including the S-IVB's TLI burn. The analog flight control computer drove steering actuators under the LVDC's guidance. | A Luminary run is not a Saturn/TLI simulation. CMC backup steering capability does not establish that it was used for Apollo 11 TLI. |
| Columbia CMC: Comanche 055 / Colossus 2A | CSM navigation, guidance and digital autopilot functions, SPS/RCS maneuvers and Command Module entry guidance. | Lunar arrival and Earth return require the CSM computer and vehicle, not Eagle's LGC. |
| Eagle LGC: Luminary family | LM navigation, primary guidance, descent, ascent and digital autopilot functions. | P63 calculations alone do not prove ignition, complete descent, touchdown, ascent or rendezvous. |
| Eagle Abort Guidance System (AGS) | Separate backup guidance computer and inertial system. | An AGS selector/report is not proof of an executing AGS simulation. |
| Crew and spacecraft hardware | Switches, circuit breakers, docking-probe operation, staging, manual handcontrollers, life support, surface work and recovery actions. | These must not be replaced by invented DSKY commands or relabeled as original AGC execution. |

Primary system references and original source:

- [NASA Saturn Astrionics System Handbook, section 1.4 and Figure 1.4-2](https://ibiblio.org/apollo/Documents/MSFC-IV-4-401-1-AstrionicsSystemHandbookSaturnLaunchVehicles.pdf).
- [Virtual AGC LVDC archive and original-system references](https://www.ibiblio.org/apollo/LVDC.html).
- [Original Comanche 055 listing](https://www.ibiblio.org/apollo/listings/Comanche055/MAIN.agc.html); [P11 insertion-monitor source](https://www.ibiblio.org/apollo/listings/Comanche055/P11.agc.html); [P40–P47 powered-maneuver source](https://www.ibiblio.org/apollo/listings/Comanche055/P40-P47.agc.html).
- [Original Luminary P12 ascent source](https://www.ibiblio.org/apollo/listings/Luminary099/P12.agc.html) and [Luminary source/revision archive](https://www.ibiblio.org/apollo/Luminary.html).

For example, the LOI and TEI records contain a CMC-requested burn enabled by the crew's **PRO** acknowledgment and followed by crew valve-bank operation. The undocking probe, by contrast, is released with a physical Columbia control. These are different control paths, and both belong in an authentic experience.

## What a guided showcase may claim

The chapter catalog is **historical reference material**. Advancing a tutorial chapter means advancing the explanation, not completing a spacecraft maneuver. A showcase may guide the viewer through the whole mission while opening independently identified evidence or laboratories at relevant chapters:

- At **LM preparation**, `guidance` links the retained synthetic P51/P27/P63 experiment. It demonstrates original-software calculations in its documented fixture, not historical CSM travel or the complete LM activation.
- At **undocking and inspection**, `undocking-trainer` links the selected source-backed crew procedure. Its discrete modeled hardware release is not original-AGC execution, sensor confirmation, inspection dynamics or an orbital separation trajectory.
- At **powered descent**, `propulsion` links the retained bounded synthetic propulsion evidence. Relevance to propulsion does not make that fixture a reproduction of Apollo 11's full descent.

The interactive physics laboratory and deterministic/model assistants retain their own classifications. A successful laboratory landing is not evidence of a full historical Apollo flight. An assistant that submits correct commands to a modern training service is not the original Apollo guidance program.

The catalog declares a distinct `historical*` required capability for each chapter's complete flight operation. These names are **proposed frontend capability requirements**, not assertions that the backend implements new endpoints. A general `physicsLab`, multiplayer or landing flag cannot satisfy them. A complete-flight chapter must remain unavailable until its original computer/control path, authoritative spacecraft integration and outcome have been demonstrated and exposed through a verified integration contract.

## Flight-software revision provenance

The commonly archived **Luminary 099/0** is authentic Apollo-era source and a preflight release for Apollo 11. The Virtual AGC archive and MIT release table identify **Luminary 99 revision 1 / LMY99 revision 001** as the flown release; the archived distinction includes a hardware-timer reset bug fix. Repository directory names are not sufficient proof of an exactly flown rope image. Product copy should identify the source/version actually loaded, and make narrower claims where that audit has not established identity. This refinement does not require or authorize changes to original source or retained evidence.

Sources: [Virtual AGC Luminary provenance](https://www.ibiblio.org/apollo/Luminary.html), [MIT final-report computer program release table](https://www.ibiblio.org/apollo/hrst/archive/1029.pdf).
