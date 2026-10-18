# Apollo 11 — submission and demonstration guide

The default Earth-orbit task now completes **original Comanche P52 with modeled IMU/optics**. Manual marks, original star-fit/torque displays and actual gyro/CDU feedback determine completion. [Play guide](P52_PLAYER_GUIDE.md) and [implemented alignment contract](EARTH_ALIGNMENT_INTEGRATION.md) describe this extension. No original Saturn departure was added; full flight remains unavailable. The cold-start diagnostic below remains separately accessible with `?task=diagnostic`.

The earlier cold-start diagnostic remains at
`/campaign.html?play=1&task=diagnostic`. It keeps its original IMU-off alarm,
without the new instrument setup. Its [player guide](EARTH_ORBIT_PLAYABLE_GUIDE.md),
[contract](EARTH_ORBIT_INTEGRATION.md) and [bounded native/WASM evidence](earth-orbit-evidence/README.md)
retain that separate scope. The new P52 hardware integration has native evidence only.

The default experience now begins in **Earth parking orbit** at `/campaign.html`.
Its sixteen historical chapters cover lunar arrival, landing, ascent and direct
Earth entry/splashdown. The guided tour (`?tour=1`) reviews historical references
and steps verified original-AGC excerpts; it does not execute a complete flight.
See [the chronological judges presentation plan](JUDGES_PRESENTATION_PLAN.md) and
[the current campaign verification](frontend-campaign-evidence/README.md).

The application also combines a source-backed orbital undocking trainer, a shared
educational landing laboratory, original Luminary 099 recordings and bounded
live AGC attitude control. Each experience displays its source and scope. The
educational landing lab is a separate synthetic experiment; it does not continue
the trainer's historical state or establish an authentic AGC-guided landing.

## Start

From the repository root:

```sh
make play
# Equivalent:
python3 -B tools/final_demo.py --port 4173
```

Open **http://127.0.0.1:4173/**. Choose an experience and configure the three crew
roles. Keep the terminal open; Ctrl-C shuts down the server and its owned
workers. No npm installation is needed. Opening HTML directly from disk is
unsupported.

The full physical lab and native attitude service require Python 3.9 or newer,
a C compiler, make and the pinned Tcl runtime. On a first installation:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime --port 4173
```

The initial pinned-source download requires network access. Alternatively,
prepare the runtime with `make runtime`, then use `make play`. The launcher
verifies original software and retained evidence before preparing native
assets. Available capabilities and dependency errors are shown explicitly.

To skip native preparation, run:

```sh
python3 -B tools/final_demo.py --recorded-only --port 4173
```

The historical undocking trainer and authentic recordings remain usable; the
physical landing lab and live native attitude controls are unavailable without
their dependencies. The older `frontend/serve.py` does not expose the new shared
mission API, and its `--replay-only` mode disables interactive commands.

If port 4173 already serves the current application, reuse that page. For
another instance, use `make play PORT=4180` and open
**http://127.0.0.1:4180/**. Restart an older server after integrating new routes.
The service binds to loopback; it is not deployed for remote devices.

## Player flow and crew combinations

Exactly three seats represent **Armstrong — Commander in Eagle**, **Aldrin —
Lunar Module Pilot in Eagle**, and **Collins — Command Module Pilot in Columbia**.
Collins stays in lunar orbit. His landing-lab support/communications role is a
disclosed gameplay adaptation; he does not pilot Eagle.

| Experience | Crew choices and play | Authority and boundary |
| --- | --- | --- |
| Historical mission at `/campaign.html` | Start above Earth; explore or automatically tour sixteen sourced chapters and two original-recording excerpts | Static 3D configurations and source-backed history; no full-flight execution or mission completion |
| Orbital undocking at `/play.html` | Solo station switching or human turns on one device; 28 selected source-backed checks and cockpit actions | Server-validated procedure model; static 3D mechanical release diagram, no physical flyaway or AGC/AGS execution |
| Landing lab at `/mission.html` | Three human/fallback/configured-model seats; training, braking and low-fuel scenarios; modern throttle/pitch, checklist, messages, lifecycle and debrief | One shared server-owned educational plant; synthetic conditions, planar pitch actuation, no original AGC landing guidance |
| Propulsion recording in the mission viewers | Play, pause, inspect observations and compare retained causal cases | Actual retained original engine output, 3D physical samples and sensor/navigation feedback; bounded synthetic experiment |
| Guidance at `/guidance.html` | Compare 15 km, 16 km and missing-site cases; replay events and inspect the DSKY | Verified retained Luminary execution; static initialized geometry, no descent |
| Attitude replay/live at `/attitude-replay.html` | Replay recordings or request a fresh bounded native run | Original yaw/pitch inputs, RCS output and external sensor feedback; separate bounded attitude fixture |

For one-player landing practice, take the Commander seat and choose
**deterministic fallback** for the other two. Mark yourself ready; fallback seats
are managed by the service. Optional training assist is a modern teaching
controller, explicitly separate from the AGC.

For human collaboration, leave the other seats human, create the flight, and
share the mission ID/invite with other local browser clients. Join open seats
before start, then mark every human ready. All three seats must be occupied
and ready. The Commander flies; the LM Pilot acknowledges the lab checklist;
joined crew exchange messages. Participant credentials stay private to each
tab. An invite contains the mission ID, not another player's credentials.
This is a local shared service, without internet identity or remote deployment.

An observer host can select three fallback/model seats and watch. Fallback is
deterministic code, not a model. Model seats are enabled only when a provider is
explicitly configured on the server. Real LLM operation was **NOT RUN** in this
delivery; the provider's wire formats and failure paths have retained stub tests.

## Optional model provider

Configure the server environment before launch:

| Variable | Meaning |
| --- | --- |
| `APOLLO_AI_MODEL` | Explicit model name; no ambient model is selected |
| `APOLLO_AI_BASE_URL` | Provider service URL; HTTPS required for remote services |
| `APOLLO_AI_PROTOCOL` | `responses` (default) or `chat-completions` |
| `APOLLO_AI_API_KEY` | Provider credential; optional for a local provider |

No ambient provider key is auto-discovered. Secrets stay server-side. A model
receives public mission telemetry and may propose only role-permitted commands
through the ordinary service validator; it cannot write position, velocity,
attitude or outcomes. Timeouts, unavailable providers and invalid responses have
explicit fallback labels. See [the implemented contract](FINAL_INTEGRATION_CONTRACT.md)
for request bounds, permissions, authentication, sequence/run checks and source
identifiers. Configuration support is not proof that a real provider was run.

## Chronological judged demonstration

Use the [seven-minute and three-minute presentation plans](JUDGES_PRESENTATION_PLAN.md).
Begin with Earth parking orbit and the correct Saturn/adapter configuration;
explain TLI and lunar arrival before demonstrating LM guidance and the undocking
trainer. Show DOI before powered descent, then the ascent-stage rendezvous and
Columbia's direct atmospheric return. The **Guided tour** preset opens this
historical sequence; it does not create an assistant-controlled landing.

The separate educational landing lab remains an optional hands-on extension
outside the authentic mission presentation. An observer can still select three
assistants in that lab's crew form. Original execution, historical reference,
procedure training and modern assistance must retain their visible source labels.

A longer demonstration can complete all 28 undocking actions. Only the valid
CMP release action changes the modeled attachment. Returning the control to OFF
and manual crew reports precede the inspection handoff. The earlier tunnel,
pressure, probe, latch and computer preparation remains an explicit assumption.
Some LM station assignments are instructional rather than individually specified
by the historical checklist.

## Verification and release handoff

```sh
make frontend-check
make test-final
```

Use [the submission evidence report](frontend-submission-evidence/README.md) for
this integrated delivery's actual test output, screenshots and browser checks.
[The earlier undocking evidence](frontend-undocking-evidence/README.md) preserves
the complete visible-control walkthrough, wrong-station/setting tests, reconnect
behavior and source-preservation checks. Scientific/native reproduction remains
a separate workflow; frontend tests do not establish flight fidelity.

The teammate's final backend revision **`origin/main` at `92adbb5`** was merged
into **`UI/UX`** by merge commit **`daffe51`**, preserving both propulsion replay
formats. The final delivery report identifies subsequent application commits,
new check results and push status. Earlier backend reports are historical
snapshots of their own branches and verification dates.

[Undocking contract](FRONTEND_UNDOCKING.md),
[historical checklist research](FRONTEND_UNDOCKING_RESEARCH.md),
[final shared-mission contract](FINAL_INTEGRATION_CONTRACT.md), and
[backend scientific integration report](FINAL_INTEGRATION.md) provide the
technical handoff. Full original-AGC-guided landing, later historical mission
chapters, real-model flight and internet deployment remain unverified.
