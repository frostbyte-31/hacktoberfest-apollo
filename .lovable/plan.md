# Apollo 11 AGC Simulator — Feasibility Report and Build Plan

Per the brief's "First Action": research and proof-of-execution come before building the full game.

## 1. Source repository and provenance (checked)

- `chrislgarry/Apollo-11` (GitHub): transcribed source of **Luminary099** (Lunar Module, the version flown on Apollo 11) and **Comanche055** (Command Module). The files are a transcription of MIT Instrumentation Lab listings. They are not a build system.
- `virtualagc/virtualagc` (GitHub, active Oct 2026): the authoritative Virtual AGC project. It contains the same Luminary099 sources, the `yaYUL` assembler, `AP11ROPE.binsource` (a rope dump used to check the assembled binary against the flown rope), and the `yaAGC` emulator plus `yaDSKY`.
- `siravan/moonjs` (GPL-2.0): yaAGC compiled to JavaScript with Emscripten. It runs Luminary in a browser. This shows a WebAssembly route is possible.
- Licensing: the AGC code is public domain (US Government work). Virtual AGC tools are GPL. Any emulator we ship must stay GPL-compatible.

Still to verify in Phase 1: that a yaYUL build of Luminary099 matches the rope dump byte for byte, and which yaAGC revision we pin.

## 2. Execution environment

- **Emulator:** upstream `yaAGC`, unmodified at the instruction level. It emulates the Block II AGC instruction set, erasable and fixed memory banks, one's-complement arithmetic, timers, interrupts and I/O channels.
- **Program:** `Luminary099.bin` built with `yaYUL` from the virtualagc sources and checked against `AP11ROPE.binsource`.
- **Phase:** Powered Descent (P63, then P64, then P66) through touchdown. This phase has the clearest AGC to physics loop: IMU, landing radar, throttle and RCS.

## 3. Platform constraint (the main architectural decision)

A Lovable app can serve the interface and use Lovable Cloud (database, logins, realtime channels, short-lived server functions). It **cannot host a long-running native process** such as yaAGC ticking at about 85k instructions per second for 12 minutes. So there are two honest options:

- **A (recommended, matches the brief):** an external **Sim Server** written in C/C++ or Rust, running in a container (for example Fly.io), that links yaAGC plus the physics model and acts as the authoritative source of truth. Lovable builds the frontend, lobby, crew and AI orchestration, and an explicit typed interface to the server.
- **B (fallback, demo-friendly):** yaAGC compiled to WebAssembly and run inside one "host" crew member's browser. That browser becomes the authority and broadcasts state over Cloud realtime. The original instructions are still executed, but authority depends on one client. This would be documented as a deviation.

Lovable can build and test the WebAssembly path in-app. The native Sim Server must be built and deployed outside Lovable. I will define its interface here and document the integration work it still needs.

## 4. Minimal proof-of-execution

1. Build Luminary099 with yaYUL and confirm the checksum matches the rope dump.
2. Boot yaAGC headless. Enter `V37E 63E` (start P63) through DSKY channel inputs. Read the DSKY outputs (PROG 63, then V06 N61 / V06 N63) from the output channels.
3. Close the loop: feed IMU counters (CDU and PIPA channels) and landing radar from the physics model. Read the throttle and RCS jet channels back into the physics model.
4. Pass test: the program reaches P64 on its own with plausible altitude and rate displays. Also, a mismatched radar input produces alarm 1202/1201 or a program alarm, which is observable evidence that the AGC itself is reacting.

## 5. Architecture

```text
 Browser (Lovable app)                     Lovable Cloud
 ┌─────────────────────────┐   realtime   ┌──────────────────────────┐
 │ Lobby / crew assignment │◄────────────►│ missions, crew, events   │
 │ CDR / LMP / CMP panels  │              │ AI crew functions (LLM   │
 │ DSKY, FDAI, telemetry   │              │ via AI Gateway: tools =  │
 │ Comms, event log, debrief│              │ same commands as humans) │
 └───────────┬─────────────┘              └────────────┬─────────────┘
             │ WebSocket: telemetry + commands         │ commands
             ▼                                         ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Sim Server (external)  tick loop                                │
 │  yaAGC (Luminary099.bin) ◄─ I/O channels ─► LM physics           │
 │  (DSKY keys, IMU, radar, throttle, RCS)   (gravity, mass, DPS)   │
 │  Authoritative state, replay log, deterministic seeds           │
 └─────────────────────────────────────────────────────────────────┘
```

- Crew roles: **CDR** (attitude/throttle hand controller, P66 landing), **LMP** (DSKY entries, monitoring, callouts), **CMP** (in Columbia: tracking, comm relay, abort and rendezvous readiness). Each seat can be a human or an AI.
- AI crew can only act through the same command interface (DSKY key presses, switch changes, hand controller inputs) that humans use. They never calculate guidance. Each AI action is shown with its reasoning in the comms panel and labelled as AI.
- Telemetry shown in the interface always carries a source tag (`AGC`, `PHYSICS`, or `MOCK`). Any mock data is clearly labelled.

## 6. Major risks

- yaAGC I/O channel mapping for the LM (radar, CDUs, throttle) is complex. Some of it comes only from Virtual AGC's LM simulators, so it needs careful study.
- Real-time pacing and determinism across the network.
- Physics fidelity: DPS throttle limits, mass depletion, lunar terrain under the radar.
- LLM latency during a 12-minute descent. Mitigation: event-driven turns, not polling.
- Deploying and hosting the external server is outside Lovable.

## 7. Prioritized plan (two-person hackathon team)

1. **Feasibility (Person A):** build the rope, boot yaAGC headless, script P63 entry, log DSKY output. Deliverable: a proof-of-execution transcript.
2. **Interface contract (both):** typed telemetry and command schema shared by the server and the frontend.
3. **Frontend in Lovable (Person B), in parallel:** Apollo-era console design; lobby; 3 seats with Human/AI badges; working DSKY that sends real key codes; FDAI, altitude and rate tapes, fuel; event log; debrief. Runs against a clearly labelled MOCK feed until the server exists.
4. **Lovable Cloud:** missions, crew seats, logins, realtime command/event bus, mission history.
5. **Closed loop (Person A):** physics model plus I/O channel bridge, then a WebSocket server, then deploy.
6. **AI crew:** server functions using the AI Gateway with tool calls limited to crew commands. Multiple models can be chosen per seat.
7. **Validation:** replay tests (P63 to P64 transition, 1202 alarm reproduction, touchdown under 3 m/s), with labels that say exactly what was verified.

## What I will build in Lovable next (after approval)

Steps 2, 3, 4 and 6: the full interface, lobby and crew system, AI crew, and the documented Sim Server interface, plus `docs/FEASIBILITY.md` and `docs/SIM_SERVER_INTERFACE.md`. I will also try Option B (yaAGC in WebAssembly) as an in-browser proof of execution, so that real Luminary099 instructions run in the app before the external server exists.
