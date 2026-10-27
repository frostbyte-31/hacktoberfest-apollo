
# Apollo 11 — The Guidance Experience

An interactive Apollo 11 mission experience combining original Apollo Guidance Computer (AGC) software, spacecraft procedures, 3D mission visualization, and hands-on flight simulations.

The project explores what it takes to recreate the Apollo 11 mission as an interactive experience while keeping original computer behavior, historical references, and educational simulations distinct.

From entering Earth parking orbit to lunar landing and the return to Earth, the experience follows the mission chronologically. Along the way, you can interact with the original AGC, work through DSKY procedures, inspect recorded guidance experiments, and explore spacecraft operations in dedicated training environments.

## Get Started

```sh
make play
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173) and select **Apollo mission → Open Earth-orbit task**.

For the guided historical presentation, choose **Guided tour** or open [the campaign tour](http://127.0.0.1:4173/campaign.html?tour=1).

The application runs locally with Python 3.9+. No npm installation is required for the standard experience.

On a fresh checkout, prepare the locked runtime once:

```sh
python3 -B tools/final_demo.py --bootstrap-runtime
```

The native execution and live attitude features additionally require `cc`, `make`, and the verified Tcl runtime. If those dependencies are unavailable, the recorded experiments and procedural guides remain available.

To run without native preparation:

```sh
python3 -B tools/final_demo.py --recorded-only --port 4173
```

If port 4173 is already in use, run `make play PORT=4180` and open the corresponding local URL.

## Explore the Mission

### 1. Earth Orbit and the Original AGC

**Route:** `/campaign.html?play=1`

Start with the live Columbia Command Module Computer (CMC) and its DSKY interface. Execute Comanche software, enter commands through all 19 DSKY keys, inspect display and indicator behavior, and explore clock, readiness-diagnostic, and recovery workflows.

The Earth-orbit alignment task focuses on the original **Comanche 055 P52** procedure, including manual optical-mark inputs and modeled gyro feedback. The original computer performs the alignment calculations, while the stationary instruments use an explicitly documented training geometry.

This is a cold-start computer bench, not a restored historical orbital checkpoint. An operational IMU, actual star measurements, and a completed historical alignment are not provided.

Player instructions: [`docs/P52_PLAYER_GUIDE.md`](docs/P52_PLAYER_GUIDE.md)  
Instrument integration: [`docs/EARTH_ALIGNMENT_INTEGRATION.md`](docs/EARTH_ALIGNMENT_INTEGRATION.md)  
Cold-start guide: [`docs/EARTH_ORBIT_PLAYABLE_GUIDE.md`](docs/EARTH_ORBIT_PLAYABLE_GUIDE.md)

### 2. The Historical Apollo 11 Mission

**Route:** `/campaign.html`

Explore 16 historical chapters covering the mission from Earth orbit through lunar operations and the return to Earth.

The experience includes 3D spacecraft configurations, three mission goals, historical references, original AGC evidence inserts, and a guided tour that walks through the available material.

The mission sequence is:

Earth parking orbit → Trans-Lunar Injection (TLI) → transposition and docking → translunar coast → lunar arrival → LM preparation → undocking → descent orbit insertion (DOI) → powered descent → lunar surface → ascent and rendezvous → Trans-Earth Injection (TEI) → Earth entry and splashdown.

The tour presents historical references and recorded observations; it does not issue flight commands or simulate a completed end-to-end Apollo mission.

Chronology and primary sources: [`docs/APOLLO11_CHRONOLOGY.md`](docs/APOLLO11_CHRONOLOGY.md)  
Campaign integration: [`docs/APOLLO11_CAMPAIGN_INTEGRATION.md`](docs/APOLLO11_CAMPAIGN_INTEGRATION.md)

### 3. Apollo Procedures and Undocking

**Route:** `/play.html`

Work through 28 selected undocking actions using documented control labels and positions, three crew stations, and a server-validated procedure sequence.

The experience includes a release diagram and a training debrief, making it possible to explore the operational sequence and understand the purpose of each action.

This is procedural training: earlier mission preparation is assumed, and the checklist does not execute AGC/AGS logic or spacecraft separation dynamics.

Procedure and source documentation: [`docs/FRONTEND_UNDOCKING.md`](docs/FRONTEND_UNDOCKING.md)

### 4. The 3D Landing Laboratory

**Route:** `/mission.html`

Experiment with a separate educational landing simulation. Control throttle and pitch, observe fuel consumption and thrust, and explore the effects of gravity and vehicle dynamics.

The laboratory supports multiple scenarios, pause and restart controls, crew messages, mission checks, and measured outcomes.

Its physics runs on the server using synthetic initial conditions. It is designed for experimentation and learning rather than as a reconstruction of the historical Apollo 11 powered descent.

### 5. Original Guidance Experiments

**Route:** `/guidance.html`

Explore three Phase 10 scenarios using recorded executions of original guidance software, including P51, P27, and P63 observations.

The interface presents trace-derived DSKY behavior, comparisons, and explanations to help connect computer output with guidance procedures.

Additional experiments cover original engine, throttle, navigation, and PIPA observations, along with a bounded attitude-control fixture.

These experiments use synthetic scenarios or fixed-attitude conditions where specified; they are not a calibrated reconstruction of the complete historical descent.

### 6. Live Attitude-Control Experiment

**Route:** `/attitude-replay.html`

Explore a bounded two-axis control fixture using original AGC software, yaw and pitch hand-controller inputs, RCS outputs, and sensor feedback.

This experiment demonstrates a closed control loop in a limited environment. It does not simulate a complete spacecraft flight.

## Crew and Multiplayer

The project models the three Apollo 11 crew roles:

- **Neil Armstrong** — Commander, Eagle
- **Buzz Aldrin** — Lunar Module Pilot, Eagle
- **Michael Collins** — Command Module Pilot, Columbia

Collins remains in lunar orbit while Armstrong and Aldrin land on the Moon.

In the flight laboratory, up to three human participants can share a server-authoritative mission. Participants join through a mission ID and can occupy separate browser tabs. Each role has server-enforced permissions, and participants must join and mark themselves ready before the flight begins.

An observer can also host a presentation with three assistant-controlled seats.

The available assistant modes are distinct:

- **Assistant:** deterministic, locally defined teaching logic.
- **Model AI:** an optional external model provider configured on the server.

External model execution has not been verified in this release. Provider protocols and failure cases are covered by stub tests; the model option should not be interpreted as a verified live integration.

This multiplayer implementation is intended for local demonstrations, not deployment as an internet-authenticated service.

## Engineering and Implementation

The project brings together several areas of software engineering:

- **Original software execution:** native execution of Apollo guidance software, with DSKY interaction and trace-derived observations.
- **Systems integration:** separate components for the CMC, Lunar Module Guidance Computer (LGC), Saturn launch vehicle guidance computer (LVDC), and crew procedures.
- **Simulation:** server-owned educational physics and bounded attitude-control experiments.
- **Frontend engineering:** interactive interfaces, 3D spacecraft configurations, mission chapters, and procedural training.
- **Shared mission state:** server-side validation, crew roles, readiness checks, and synchronized participants.
- **Evidence and testing:** retained experiment outputs, source references, integration contracts, and automated checks.

The architecture deliberately separates original-computer execution, recorded experiments, historical presentation, and synthetic simulation. Each provides a different way to explore Apollo without treating one as proof that another has been reproduced.

## Run the Checks

Run the project's main verification commands:

```sh
make frontend-check
make test-final
```

For frontend development, install the frontend dependencies and run the TypeScript check:

```sh
npm --prefix frontend ci
npm --prefix frontend run typecheck
```

See the [frontend development guide](frontend/README.md) for additional information.

## Project Documentation

- [Submission and demo guide](docs/SUBMISSION_GUIDE.md)
- [Earth-orbit computer and interface evidence](docs/frontend-earth-orbit-evidence/README.md)
- [Campaign visual and test evidence](docs/frontend-campaign-evidence/README.md)
- [Shared-mission integration contract](docs/FINAL_INTEGRATION_CONTRACT.md)
- [Chronology and primary sources](docs/APOLLO11_CHRONOLOGY.md)
- [Campaign integration contract](docs/APOLLO11_CAMPAIGN_INTEGRATION.md)
- [Judges' presentation plan](docs/JUDGES_PRESENTATION_PLAN.md)

## Scope and Current Limitations

Apollo 11 used several distinct guidance and control systems, each with its own responsibilities. Reproducing the complete mission requires integrating those systems, their operational state, spacecraft dynamics, and the transitions between mission phases.

This project provides working experiences across selected parts of that problem, rather than claiming a fully integrated, original-computer-controlled Earth–Moon–Earth flight.

The historical campaign, native AGC experiments, procedural trainer, and synthetic landing laboratory remain separate experiences. Their results and limitations are documented individually.

The goal is to make Apollo's guidance software and mission procedures more tangible through interactive experiments, inspectable behavior, and a navigable historical reference.
