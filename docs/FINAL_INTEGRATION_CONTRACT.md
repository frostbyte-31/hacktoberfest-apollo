# Final mission application: integration contract v1

This document describes implemented routes in `backend/final_server.py`,
`backend/mission_service.py` and `frontend/dist/mission-live-provider.mjs`.
It does not propose a live original-AGC landing API.

## Execution boundaries

| Experience | Source | Commands | Physical authority |
|---|---|---|---|
| `/guidance.html` | Verified recorded Phase 10 execution | Replay navigation only | No propagated spacecraft |
| `/index.html` | Live original Luminary and existing native attitude adapter | Existing validated yaw/pitch inputs | Existing bounded attitude model |
| Engine inspector in `/mission.html` | Verified recorded Phase 12 raw runs | Case selection, play/pause/scrub | Recorded original experiment |
| Flight laboratory in `/mission.html` | Live server educational physics | Validated manual/model/fallback actuator requests | One server-owned physical plant per shared mission |

The flight laboratory has `mode: EDUCATIONAL_PHYSICS_LAB`,
`authenticAGC: false`, `hasAGCNavigationFeedback: false`. Its state and commands
are never sent to the original AGC. The engine inspector has
`RECORDED_AUTHENTIC_AGC_EXPERIMENT`; replay elapsed time, physical propagation
time, and original AGC cycle are separate quantities. Missing observations are
unavailable; values are held between actual retained observations, not invented.

## Implemented HTTP routes

The server binds **127.0.0.1**. Use the same origin in every client. It supports
three browser clients on this local service, not an authenticated internet
deployment. Existing loopback Host, Origin, fetch-site and anti-CSRF checks
remain in force for APIs. Top-level static document navigation has a narrow
exception so an ordinary external link can open the application.

| Method / path | Request | Result |
|---|---|---|
| GET `/api/v1/capabilities` | None | Schema 1, global command token, capabilities, scenarios, crew roles, limitations and dependency error |
| POST `/api/v1/missions` | `scenarioId`, `name`, `role`, `crewModes` | Mission ID, private participant token, role and snapshot |
| POST `/api/v1/missions/{id}/join` | `name`, `role` | Participant credentials and snapshot; rejects occupied seats |
| GET `/api/v1/missions/{id}` | Optional participant header | Public snapshot; authenticated caller also receives `you` and refreshes connection presence |
| POST `/api/v1/missions/{id}/command` | Sequence, run ID, action, payload | Accepted result with sequence, revision and current snapshot |

POST requests require JSON, matching Origin and `X-Apollo-Token`. Commands also
require `X-Apollo-Participant`. Mission IDs are 16 hexadecimal characters;
participant tokens are opaque and private. The invite contains only a mission
ID. Browser credentials are held per tab in session storage. JSON bodies are
limited to 8192 bytes; duplicate fields, nonfinite numbers, extra command fields
and unsupported transfer encoding are rejected.

Existing `/api/bootstrap`, `/api/status`, `/api/record`, `/api/session/start`,
`/api/input` and `/api/session/stop` remain delegated to the original attitude
service. Their contract is in `LIVE_ATTITUDE_CONTROL.md`. New mission commands
do not replace those endpoints or provide arbitrary AGC memory access.

Creation example (field names and role identifiers are exact):

```json
{
  "scenarioId": "training",
  "name": "Commander",
  "role": "commander",
  "crewModes": {
    "commander": "human",
    "lunar-module-pilot": "fallback",
    "command-module-pilot": "fallback"
  }
}
```

The other scenarios are `braking` and `low-fuel`. Crew modes are `human`,
`fallback` and `llm`. Model seats are rejected unless a provider is configured.
An observer creator uses `role: null`; this enables three fallback/model seats.
There are exactly three crew seats, even when an observer hosts the mission.

## Commands and permissions

Each command is `{sequence, runId, action, payload}`. Sequence must be an integer
in [0, 2³¹), strictly greater than the participant's last applied sequence.
Restart changes the run ID, so delayed commands cannot affect the new flight.

| Action | Payload | Permission / precondition |
|---|---|---|
| `ready` | `{ready: boolean}` | Seated crew member |
| `start` | `{}` | Host or commander; lobby and all three seats ready |
| `pause`, `resume` | `{}` | Host or commander; matching current lifecycle state |
| `restart` | `{}` | Host or commander; creates a new physical run |
| `controls` | `{throttle: 0..1, pitch: -1..1}` | Commander, running, manual assistance disabled |
| `assist` | `{enabled: boolean}` | Commander; explicitly modern deterministic teaching aid |
| `checklist` | `{item: "state-vector" / "braking" / "propellant"}` | Lunar Module Pilot |
| `message` | `{text: string}` | Joined participant; 1–300 characters |

No command writes position, velocity, orientation, AGC words or a landing result.
Commands and validation rejections are logged in the mission audit. Human flight
inputs expire after 1.5 wall seconds unless renewed; release sends zero throttle
and pitch. Frontend refresh is 200 ms, control renewal 400 ms. Physics does not
wait for clients. Pause stops simulated time; resume requires fresh input after
an expired lease. Reconnection within the same tab restores its participant and
sequence from authoritative state. Credentials are not transferable in invites.

## State, coordinates and timing

`LabSnapshot` in `mission-live-types.d.ts` describes the new domain separately
from the existing recorded-guidance types. A shared snapshot includes schema,
mission/run IDs, monotonically changing revision, lifecycle, physics, three crew
seats, events, messages, checklist, trajectory, optional debrief and fault.

Physics uses three-component SI vectors in Moon-centered inertial REF. Initial
local up is +X; downrange is +Z. Body +X is the engine direction. Quaternion
order is `[w,x,y,z]`, body to REF. Positive pitch is right-handed about body +Y,
turning thrust toward REF −Z. Radial velocity is signed (negative descending);
horizontal speed is a magnitude, while horizontal velocity is signed. Altitude
is radius minus the modeled 1,738,090 m reference radius. The SVG projects these
measurements and discloses its diagrammatic scale; it never integrates motion.

Time is integer ticks × 0.01 s. The server advances five ticks per nominal
50 ms wall interval; it slows rather than skipping physical steps on an
overloaded host. Plant snapshots carry source, mode, units, frame, assumptions,
engine provenance and measured outcome. The 3D representation remains planar
in this bounded lab: only pitch is actuated; this is not general 6-DOF fidelity.

## Optional model provider

All configuration is server-side: `APOLLO_AI_MODEL` is explicit;
`APOLLO_AI_BASE_URL` selects a service; `APOLLO_AI_PROTOCOL` is `responses`
(default) or `chat-completions`; `APOLLO_AI_API_KEY` is optional for a local
provider. Remote URLs require HTTPS. No ambient provider key is auto-discovered
and no key is published in capabilities, snapshots, client code or audit rows.

`ModelProvider.decide(role, public_snapshot, recent_results)` returns proposed
`{action,payload}` objects. Structured function-call wire formats follow the
[official function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).
Commander tools request actuator settings, Aldrin tools review the checklist,
and all roles can send a message. Models have no plant reference or state-write
tool. The ordinary service validator applies each proposal and records its
origin as `LLM_PROVIDER`; deterministic commands use `DETERMINISTIC_FALLBACK`.

Requests run outside the physics loop with at most three outstanding jobs,
one request per model seat per four wall seconds, a four-second provider timeout,
256 KiB response limit and four tool calls per response. Lease expiry, invalid
responses and unavailable providers produce explicit fallback labels. Restart
discards old proposals. Live model behavior is **NOT RUN** in this sprint;
both wire formats and failure cases were tested with synthetic provider stubs.

## Unimplemented integration

There is no live AGC-controlled landing mission endpoint, arbitrary mission-data
editor, internet identity service, persisted session restore after server exit,
voice link or full Command Module model. Those capabilities must be added only
after source and end-to-end validation; the current capability response does
not advertise them.
