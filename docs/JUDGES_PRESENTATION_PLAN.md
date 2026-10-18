# Apollo 11: presentation plan

A new manually playable opening is available before the reference tour:
[the original Columbia CMC diagnostic](EARTH_ORBIT_PLAYABLE_GUIDE.md). Show real
DSKY input, V35 output, the running clock, original P52 `00210` readiness alarm
and P00 recovery. Allow two additional minutes, or use the clock/alarm portion
in place of some historical-reference narration. Explain that this is a
cold-start control bench, not a restored orbital checkpoint or completed P52.
The historical tour below remains a separate chronological reference.

Present the mission in its real order: **Earth parking orbit → lunar orbit → Eagle landing → ascent and rendezvous → Earth entry and splashdown**. The complete mission is a guided historical reference. Demonstrate the independently classified original-AGC evidence and interactive procedures at the appropriate chapters.

Opening sentence:

> “Our goal is to make Apollo's engineering understandable through its original software, real crew procedures and visible spacecraft behavior. We'll follow the mission from Earth orbit to recovery, and the interface identifies exactly which parts are original execution, training or historical reference.”

## Prepare before the judges arrive

1. Start the application from the repository root with `make play`. On an already prepared machine, `python3 -B tools/final_demo.py --port 4173` is equivalent. Keep that terminal open. Reuse the existing server if port 4173 is already serving the current build.
2. Open three local browser tabs:
   - [Chronological mission](http://127.0.0.1:4173/campaign.html), initially paused at Earth.
   - [Original guidance evidence](http://127.0.0.1:4173/guidance.html).
   - [Interactive undocking](http://127.0.0.1:4173/play.html).
3. On the guidance tab, check that the 15 km, 16 km and missing-site cases load. Use **Restart replay** before presenting; **Go to P63** and **View recorded result** provide bounded shortcuts through the recording.
4. For a short live undocking demonstration, complete the first **24 of 28** selected checklist actions beforehand, using the required crew stations and settings. Stop at Collins's **DOCKING PROBE** release step. Say during the presentation that the readiness checks were prepared beforehand. Do not claim a fresh execution of the whole checklist in the demonstration minute.
5. On the tour tab, rehearse **Start guided tour**, **Pause tour**, **Restart at Earth**, **Next chapter →** and **← Previous chapter**. [Opening with `?tour=1`](http://127.0.0.1:4173/campaign.html?tour=1) starts automatically after loading; it needs no additional click. Use **Pause tour**, then **Restart at Earth** to prepare a stationary opening screen. A paused tour shows **Resume guided tour** after the opening chapter.
6. Rehearse the LM-preparation and powered-descent inserts: **8 preparation observations** and **18 engine/feedback observations**, both from the **same retained Phase 12 synthetic experiment**. The separate `/guidance.html` page contains the full Phase 10 scenarios. Keep each scene's source and scope labels visible.
7. Put the browser at a readable desktop size. Confirm that the app still loads with network access disabled; external source documents are supporting links, while retained recordings are served locally. Complete first-run runtime downloads before the venue demonstration.

The undocking trainer is a single local training session. A second open tab can observe it; avoid restarting it in another tab after preparing the 24-action checkpoint.

**Control the presentation pace.** Ordinary tour chapters advance after **8 seconds**. At the two recorded inserts, the tour holds the chapter while observations advance every **2.5 seconds**, then resumes the historical route **5 seconds after the excerpt finishes**. Press **Pause tour** before a longer explanation or switching tabs; it also pauses the excerpt. With the tour paused, use **Play observations**, **Pause observations**, **Next observation**, **Previous observation** and **Restart excerpt** independently. Use **Next chapter →**, **← Previous chapter**, or the chapter title in the list to continue at your own pace. Clicking a chapter title pauses the automatic tour. The seven-minute script therefore requires pauses; it is longer than an unattended tour.

## Seven-minute chronological demonstration

| Time | Show and do | Say to the judges |
| --- | --- | --- |
| **0:00–0:40** | Open `/campaign.html`. Show the three goals and the **Earth parking orbit** starting chapter. Orbit the camera slightly to reveal the S-IVB and adapter. | “We start after launch, in Earth orbit. Eagle is still stowed inside the adapter. The upper Saturn stage has not yet been discarded. These are reference models, with an explicitly labeled scale and source.” |
| **0:40–1:35** | Click **Start guided tour**. Follow **Translunar injection → Retrieve Eagle → Navigate to the Moon → Brake into lunar orbit → Establish the lunar parking orbit**. If using `/campaign.html?tour=1`, playback is already running. Press **Pause tour** whenever the explanation needs more than 8 seconds. | “Saturn's separate LVDC guides the departure burn. Collins then turns Columbia around to retrieve Eagle. Columbia's own computer and service engine perform lunar arrival. One Lunar Module program does not control every vehicle.” |
| **1:35–2:30** | At **Activate Eagle and prepare guidance**, show the 8-observation Phase 12 preparation excerpt. Press **Pause tour** before switching to `/guidance.html`: **Go to P63 → View recorded result**; then select **Missing landing site** and show its actual Phase 10 result. Return to the same tour chapter. | “Here is original Luminary executing in a documented synthetic state. These DSKY values and outcomes come from retained execution. A target and valid initialization matter. This result demonstrates a guidance calculation; it does not establish that the whole landing has flown.” |
| **2:30–3:40** | Select **Undock and inspect Eagle** in the chapter list, which pauses the tour, then switch to the prepared `/play.html` tab. At action 25, use **Collins → EXTD/REL**, then **OFF**. Use **Aldrin** for release confirmation and **Collins** for the inspection handoff. Show the model and source links. | “I completed the first 24 readiness actions before this presentation. We now execute the release controls live. Collins operates the probe from Columbia; it is not a DSKY release command. The server checks the station, order and setting. This is a mechanical procedure model, not a simulated orbital flyaway.” |
| **3:40–4:40** | Return to the paused tour. Use **Next chapter →** for **Lower Eagle's orbit**, then again for **Descend and land Eagle**. Click **Play observations** for the 18-observation propulsion excerpt, allowing roughly 45 seconds. If opening the full recording, use `/play.html` → **Separate recorded propulsion experiment → Play recording**. | “DOI first lowers Eagle's orbit; powered descent comes afterward. This retained experiment demonstrates the path from original computer output through an external spacecraft model to sensor feedback. Its bounded synthetic conditions are displayed. Apollo's actual final landing used P66 with Armstrong's assisted manual controls.” |
| **4:40–5:25** | Keep the tour paused and use **Next chapter →** through **Tranquility Base → Launch from the Moon → Rejoin Columbia**. Point out the change to the ascent-stage configuration. | “Armstrong and Aldrin land; Collins remains in orbit. The descent stage stays on the Moon. Only Eagle's ascent stage launches to rejoin Columbia, and the crew and samples transfer before the LM is discarded.” |
| **5:25–6:15** | Continue with **Next chapter →** through **Depart lunar orbit → Navigate home → Enter Earth's atmosphere and splash down**. Show that only the Command Module remains at entry. | “The return burn is Columbia's. All three astronauts return together. Apollo 11 did not enter Earth orbit again: the Command Module entered directly and splashed down in the Pacific.” |
| **6:15–7:00** | Return to the three-goal overview. Open the source/provenance information and, if asked, the launcher at `/` to show the three crew seats. | “The historical route makes the mission understandable; the original execution evidence makes the engineering inspectable. Human roles, deterministic assistants and optional configured model agents are different participation modes. We preserve that distinction, just as we preserve the boundary between a historical illustration, a procedure trainer and a measured experiment.” |

Do not wait through long coasts in real time. The tour advances explanations and reference chapters; it does not accelerate a verified end-to-end flight. At the two original-AGC excerpts, point at the change in source classification before explaining the data.

Closing sentence:

> “Our strongest result is a traceable connection between original flight-computer decisions, explicit crew actions and visible consequences, with the remaining integration work clearly exposed.”

## Three-minute version

| Time | Action and message |
| --- | --- |
| **0:00–0:35** | Open `/campaign.html`: show Earth parking orbit and the three goals. “The mission starts with Eagle stowed above the Saturn upper stage; it ends at splashdown.” |
| **0:35–1:05** | Keep automatic playback paused; use **Next chapter →** through TLI, Eagle retrieval and lunar arrival. “Saturn LVDC, Columbia CMC and Eagle LGC have different jobs.” |
| **1:05–1:40** | Select **Activate Eagle and prepare guidance**, then **Play observations** for its 8-observation excerpt. “Original software; synthetic initialized scenario; actual retained DSKY output.” |
| **1:40–2:10** | In the prepared undocking tab, execute Collins's **EXTD/REL → OFF**. “Readiness checks were prepared beforehand. This is a source-backed, server-checked procedure model.” |
| **2:10–2:35** | Select **Descend and land Eagle** and use **Next observation** to inspect two or three exact recorded observations. The full 18-observation autoplay is too long for this slot. “This demonstrates output and sensor feedback; it is not the full flown descent.” |
| **2:35–3:00** | Use the chapter list or **Next chapter →** through ascent, rendezvous, TEI and entry. “The descent stage stays behind, the crew reunites in Columbia, and the Command Module returns directly to the ocean.” |

## Optional interactive-laboratory extension

If the judges want to play after the historical presentation, open [the crew launcher](http://127.0.0.1:4173/). Choose the independent **3D landing lab** with a human Commander and deterministic assistants for the other seats, create the mission, mark ready and start. The shared physical lab is an educational synthetic experiment. It is not a continuation of the historical tour's state, and its assistance controller is not Luminary.

For a model-AI demonstration, configure and verify the actual server provider before the event. If no provider is configured, show the unavailable state or use explicitly named deterministic assistants. Do not describe a fallback controller as a language model. Do not call a successful lab landing an original-AGC-guided Apollo 11 landing.

## Offline and failure fallback

- **No venue internet:** use the already prepared local build. If native dependencies are unavailable, run `python3 -B tools/final_demo.py --recorded-only --port 4173`. The local reference tour, retained recordings and procedure trainer do not need a live model provider. Source-document links need internet; the data's source identifiers and locators remain available.
- **Port already occupied:** reuse the verified current application; otherwise run `make play PORT=4180` and change the three browser URLs to port 4180. Do not stop an unidentified process on stage.
- **Replay cannot load:** show the error honestly, then use retained visual evidence: [guidance recording](final-integration-evidence/frontend/screenshots/recorded-guidance.png), [propulsion recording](final-integration-evidence/frontend/screenshots/recorded-propulsion.png), [probe release](frontend-undocking-evidence/released.png). Say, “These are captured results from a previous verified run,” rather than presenting screenshots as a current execution.
- **Prepared procedure session is gone:** demonstrate the opening station/order check, then use the retained release screenshot. A server restart creates a fresh session; it does not justify silently skipping 24 steps.
- **Question about a full perfect flight:** answer, “The complete historical mission is the reference route. Original execution is demonstrated in the labeled bounded experiments; complete historic vehicle integration is still gated.”

For historical sources and the revision-specific Luminary claim, see [Apollo 11 chronology](APOLLO11_CHRONOLOGY.md). For exact startup and crew-provider configuration, see [submission guide](SUBMISSION_GUIDE.md).
