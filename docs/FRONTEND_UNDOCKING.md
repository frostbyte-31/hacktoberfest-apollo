# Playable undocking checklist and integration contract

The first chapter is now an **interactive procedure trainer**. The player takes
the three crew stations in turn, works 28 selected source-backed actions, and
commands Columbia's docking-probe release. The server owns checklist progress,
modeled switch selections, crew reports and the docking-attachment state.

This is not original AGC/AGS execution or a validated historical flight. Earlier
tunnel closeout, pressure checks, probe installation/preload, docking-ring latch
release and computer preparation are declared entry assumptions. The model has
no pressure, electrical transit, latch dynamics, orbital position, velocity,
attitude, spring impulse or flight clock. Exact release hold duration was not
established, so no invented timer or probe talkback is displayed.

## Play

From the repository root:

```sh
python3 -B frontend/serve.py --port 4173
```

Open **http://127.0.0.1:4173/play.html**, then select **Begin undocking checklist**.
Select the indicated crew station before each action. Read the declared entry
setup, acknowledge crew-report tasks and set each labeled cockpit control to
the checklist position. Incorrect supported switch positions remain visible
without advancing. Future steps cannot bypass the current action.

Collins operates **DOCKING PROBE EXTD/REL** from Columbia, after the LM readiness
checks and probe circuit-breaker settings. The next action returns the control
to **OFF**. Aldrin then records release confirmation and Collins hands off to
the next chapter. Those last acknowledgments are manual reports, not simulated
physical sensors. [Source research and page-specific primary references](FRONTEND_UNDOCKING_RESEARCH.md).

One person switches crew stations; this is not multiplayer or an AI crew.
The source does not assign an individual hand to every LM switch, so some
CDR/LMP station routing is an instructional choice. Actual vehicle ownership
is preserved: LM switches are in Eagle; the probe control is in Columbia.

If port 4173 already runs the current server, reuse it. To run another instance:

```sh
python3 -B frontend/serve.py --port 4180
```

Open the same `/play.html` path on port 4180. An old running server needs a
restart to expose the new routes. `--replay-only` deliberately disables the
interactive trainer. The first checklist needs only Python; native runtime
preparation is for the separate attitude lab. `make play` still prepares that
optional runtime before starting the existing server.

## Architecture

| Component | Responsibility |
| --- | --- |
| `frontend/dist/data/undocking-procedure.json` | Reviewed sequence, exact control positions, entry assumptions, citations and limits |
| `backend/procedure_service.py` | Atomic role/order/revision validation and authoritative training state |
| `frontend/serve.py` | Three new procedure routes using existing loopback/token/JSON boundaries |
| `frontend/dist/procedure-client.mjs` | Capability discovery, immutable snapshots, serialized commands and explicit resynchronization |
| `frontend/dist/undocking-ui.mjs` | Source validation, crew-station controls, checklist, acknowledgments and source links |
| `frontend/dist/mission-3d.mjs` | Separate static mechanical diagram; no flight propagation |

`NativeSession`, `ControlService`, the original Apollo source, emulator and
retained experiments are unchanged. A procedure action never calls the native
AGC. Native readiness cannot satisfy this checklist, and checklist completion
cannot unlock native flight capability.

## Implemented HTTP contract

Bootstrap adds `procedureEnabled` and `procedureCapabilities`. Its procedure
capabilities explicitly set `originalAgc`, `flightPhysics`, `sensorReadback` and
`historicalMissionClock` to false. The native `liveEnabled` field retains its
existing meaning and is not an announcement of mission-flight support.

| Method / route | Request | Response |
| --- | --- | --- |
| `GET /api/procedure/status` | None | Current procedure snapshot; does not start a session |
| `POST /api/procedure/start` | `{}` | Fresh session snapshot; invalidates previous procedure session identities |
| `POST /api/procedure/action` | `{sessionId, sequence, expectedRevision, role, action, value}` | `{accepted, advanced, meaning, snapshot}` |

POSTs require the existing same-origin loopback checks, `X-Apollo-Token`, bounded
`Content-Length`, `application/json`, unique JSON keys and exact field sets.
Replay-only mode blocks mutation. Native `/api/session/*` and `/api/input`
behavior and their schemas remain unchanged. No WebSocket was introduced.

`action` is the current source step's ID. `role` is CDR, LMP or CMP and denotes
the solo player's selected station; it is not authenticated multiplayer
authorization. `sequence` must increase within the session. `expectedRevision`
must equal the server's current revision. Rejected requests change no state or
log. A supported but incorrect selector value is an accepted modeled selection
with `advanced: false`; it increments the revision without completing the step.

Snapshots identify schema version, exact classification
`INTERACTIVE PROCEDURE TRAINER`, session/status/revision/sequence, current step,
completed IDs, modeled controls, crew reports, action log, attachment, chapter,
capabilities and the SHA256 of the source definition. Controls start unknown;
empty initial selections do not imply that the spacecraft switches were off.

Evidence kinds are **crew-report** and **trainer-control**. Attachment evidence
changes from **initial-trainer-configuration** to **modeled-mechanical-release**
only at the sourced CMP release action. Wall UTC timestamps date player actions;
they are not reconstructed mission GET. Snapshots expose no flight r/v/q or DSKY.

The browser verifies that its definition hash, complete current step, ordered
completed IDs and attachment transition agree with the server. No optimistic
progress is drawn. Requests time out after five seconds. An uncertain or stale
POST is never retried automatically; one status read reconciles its outcome.
A 403 response clears the expired local token and locks controls until explicit
reconnection obtains a new bootstrap token and current state. Failed
reconciliation also disables controls and preserves the last acknowledged model
state with an unavailable label. Reconnect reads state before any action.

Sessions are local, single-owner, in memory, and lost on server restart.
Reloading the browser restores a running server's session. Restarting the
checklist creates a fresh identity. No training progress is stored as Apollo
execution evidence.

## Diagram and chronological handoff

The renderer accepts:

```js
renderer.draw({mode: 'procedure-illustration', dockingState: 'released'});
```

Before release it shows the connected assembly. After acknowledgment it shows
a static exploded diagram. The gap has no physical units and is never animated
as a simulated flyaway. Public physical position, velocity and quaternion are
unavailable in this mode. Recorded propulsion continues to use its independent
verified sample provider and source labels.

The chapter advances from docked preparation to modeled release. It then hands
off to **relative-motion management and Eagle inspection**, followed by the later
CSM separation maneuver, LM alignment, DOI, P63 preparation and powered descent.
The combined historical "undock and inspect" chapter is not marked complete
merely because this release checklist finishes. Previewing later chapters does
not execute them or complete inspection.

The next physical chapter needs validated relative motion, ACA/AGS authority,
attitude feedback and inspection geometry. CSM maneuvering also needs Columbia's
separate computer and vehicle integration. These capabilities remain gated.

## Verify

```sh
make frontend-check
make test-frontend
python3 -B -m unittest discover -s backend/tests -v
```

[Actual test output, browser walkthrough and preservation evidence](frontend-undocking-evidence/README.md).
