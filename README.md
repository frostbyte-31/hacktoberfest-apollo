# Apollo 11 — the guidance experience

Assemble the three Apollo crew stations, work the source-backed undocking
checklist, and explore lunar landing physics in a separate shared **3D flight
laboratory**. Original Luminary 099 execution and verified DSKY/propulsion
recordings remain available throughout the product.

## Start

```sh
make play
```

Open **http://127.0.0.1:4173/**. Choose an experience and your crew.
The launcher verifies the retained evidence and prepares cached native assets.
On a new checkout, enable the locked runtime bootstrap once:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime
```

Python 3.9+ runs the application. The physical lab/live attitude modes also need
`cc`, `make`, and the verified Tcl runtime. No npm install is needed to play.
If those native dependencies are unavailable, the sourced checklist and recorded
experiments remain accessible; the app never substitutes invented live data.

If another server already uses 4173, reuse the current application or run
`make play PORT=4180`. Open HTTP URLs, not files from disk. For recordings and
checklist training without native preparation:

```sh
python3 -B tools/final_demo.py --recorded-only --port 4173
```

## Choose your experience

| Experience | What works | Source and limit |
| --- | --- | --- |
| **Apollo procedures** (`/play.html`) | 28 selected undocking actions, real control labels/positions, three local crew stations, server-checked order, release diagram, training debrief | Documented checklist training; earlier preparation is assumed. No AGC/AGS or separation dynamics is executed here. |
| **3D landing laboratory** (`/mission.html`) | Shared missions, throttle/pitch, fuel/gravity/thrust, scenarios, pause/restart, crew messages/checks, measured outcome | Server-owned educational physics from synthetic initial conditions. Independent of original AGC guidance. |
| **Original guidance** (`/guidance.html`) | Three Phase 10 scenarios, original P51/P27/P63 observations, authentic trace-derived DSKY, comparison and explanations | Verified recorded original-software execution in synthetic pre-ignition scenarios. |
| **Propulsion inspectors** | Original engine/throttle/navigation/PIPA observations and causal controls, retained 3D state | Verified fixed-attitude Phase 12 experiments; not a calibrated historical descent. |
| **Live attitude** (`/attitude-replay.html`) | Actual original AGC yaw/pitch hand-controller inputs, RCS outputs and sensor feedback | Bounded native two-axis fixture, not a whole flight. |

The historical sequence is undocking → relative-motion management and Eagle
inspection → Columbia separation → LM alignment → DOI → P63 preparation →
powered descent. Unimplemented historical flight chapters remain gated. The
synthetic landing lab is a separate teaching activity, never a substitute for
those mission procedures or evidence of an original-AGC-controlled landing.

## Crew and agents

Exactly three seats are available: **Neil Armstrong / Commander / Eagle**,
**Buzz Aldrin / Lunar Module Pilot / Eagle**, and **Michael Collins / Command
Module Pilot / Columbia**. Collins remains in lunar orbit during landing.

- Historical procedures: one player switches stations, or humans pass the same device.
- Flight lab: 0–3 human crew seats share one authoritative mission on the local
  server. Other humans join with the mission ID/invite in separate tabs.
- **Assistant** is explicitly deterministic modern teaching logic.
- **Model AI** uses a real optional server-side provider. The option is gated by
  the service's configuration; it is not interchangeable with fallback logic.

An observer can host three assistants for a presentation. Human seats must join
and mark ready before flight starts. Each role has server-enforced permissions.
Invites contain only the mission ID; private participant credentials remain in
their own browser tab. This is a loopback/local demonstration, not an
internet-authenticated multiplayer deployment.

Model configuration is explicit and server-side: `APOLLO_AI_MODEL`,
`APOLLO_AI_BASE_URL`, `APOLLO_AI_PROTOCOL` (`responses` or `chat-completions`),
and optional `APOLLO_AI_API_KEY`. No key is entered into the frontend. Model
proposals pass the same command validator and can fall back with visible labels.
**Real external model execution has not been verified in this release**;
provider protocols and failure cases are covered by stub tests.

## Submission and verification

[Judge demo and startup guide](docs/SUBMISSION_GUIDE.md) ·
[Current screenshots and actual test results](docs/frontend-submission-evidence/README.md) ·
[Implemented shared-mission contract](docs/FINAL_INTEGRATION_CONTRACT.md) ·
[Undocking contract and primary sources](docs/FRONTEND_UNDOCKING.md) ·
[Frontend development guide](frontend/README.md).

```sh
make frontend-check
make test-final
npm --prefix frontend run typecheck  # development only; needs npm ci in frontend
```

The final backend from `origin/main` (`92adbb5`) is merged into `UI/UX`.
Original Apollo software, emulator semantics and scientific experiment evidence
are preserved. The two propulsion export formats are retained separately as
`propulsion.json` and `propulsion-lab.json`, with distinct providers.
