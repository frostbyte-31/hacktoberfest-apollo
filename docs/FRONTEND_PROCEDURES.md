# Procedure-led Apollo frontend

## Correction to the product direction

The principal experience is now `/play.html`: mission preparation with an
explicit current task, original recorded DSKY output and a guided evidence
sequence. The invented +3-degree target, timer and score are confined to
`/attitude-lab.html`, explicitly labeled as a separate synthetic exercise.

Original Luminary execution does not by itself establish an authentic crew
workflow. The existing P51/P27/P63 experiment is a synthetic test sequence,
not Apollo 11's complete flown checklist. This correction does not claim that
all historical astronaut actions are now simulated. The available interaction
is **reviewing recorded evidence**, not executing live cockpit procedures.

## Current implementation

`procedures.mjs` reuses `RecordedTraceProvider`, `renderDSKY` and the independent
3D renderer. It loads the same verified guidance export; it imports no live
client and sends no AGC commands. `procedure-state.mjs` binds eight explanatory
checkpoints to actual scenario events, retaining each original timestamp and
trace source. Missing required events fail; they are never invented or skipped.

The nominal and altitude variants end at their actual V06 N61 review checkpoint.
The missing-site variant instead selects its original root-failure and 01406
alarm events. The final navigation action disables at that boundary. There is no
working engine-arm or PROCEED control beyond it.

The DSKY uses recorded relay fields at the selected checkpoint. At nominal P63
entry, for example, PROG still reads 00 with VERB 37 / NOUN 63. The UI preserves
that actual relay lag instead of forcing PROG 63. Unknown digits, blanks and
unavailable lamps are not filled in. Live keypad entry is visibly unavailable.

The mission page's 3D Lunar Module is always an illustrative presentation pose.
Phase 10 provides no vehicle-attitude or propagated descent samples. Orbiting
the camera cannot change the recording or imply a flight maneuver. Its pose is
not combined with the separate live lab's quaternion.

## Controls and direction in the separate lab

The modern lab keeps its existing live native AGC/rotational-feedback loop.
Keyboard steering is disabled by default and requires an explicit checkbox.
An illustrative two-axis hand controller and accessible direction buttons use
only the already-supported integer yaw/pitch directions. The pad quantizes into
-1/0/+1 with a neutral deadband. It does not introduce analog authority, new
physical axes or new endpoints, and is not a calibrated replica of flight hardware.

The fixed attitude-error instrument marks YOU at the center and TARGET at the
relative yaw/pitch error. Positive yaw is right and positive pitch is up on that
instrument, regardless of camera orbit. Numerical relative angles, direction
highlights and an explanation of neutral/countersteering make the invented
objective legible. These assistance cues are modern lab UI, never an Apollo
checklist, autopilot command or landing-site designation.

Pointer release/cancel, lost focus, hidden page, unavailable telemetry and stopping
return the controller to neutral. Existing server leases remain authoritative.
The backend model, original input counts and emulator are unchanged.

## Historical source boundary

The [Apollo 11 landing transcript and crew commentary](https://apollojournals.org/alsj/a11/a11.landing.html)
records the cockpit interactions relevant to this direction. This journal is
linked from [NASA's Apollo Journals page](https://www.nasa.gov/history/alsj-and-afj/).
In particular, inspect 102:29:38 for the checklist/switch context, 102:42:05 and
its commentary for manual attitude control, and the discussion at 102:43:22 for
the later P66 transition. Those are historical mission times, not this test's
CPU-call timestamps.

The historical sequence must be mapped from primary checklist documents,
transcripts and the Apollo 11 mission report before being offered as an
executable crew procedure. The eight current observations are expressly labeled
as test evidence and are not that historical mapping. See the preserved
`docs/phase10-evidence/research/README.md` for the unresolved exact historical
pre-PDI navigation-state issue.

## Missing contracts for authentic mission interaction

These are **requirements**, not implemented routes or capabilities:

| Required capability | Necessary evidence and acknowledgement |
| --- | --- |
| Live DSKY keys | Exact historical key identity and key-down/up semantics, accepted/rejected session command, actual original relay response; no frontend-generated success |
| Cockpit switches/modes | Source-backed switch position, valid transitions and interlocks, observed AGC/vehicle response and crew authority |
| Hand-controller assembly | Validated axis/sign/range, mode-dependent rate or redesignation behavior, centering and hardware-equivalent mapping |
| Historical procedure state | Cited checklist step, actual mission epoch, crew role, preconditions, command intent and observed completion separately |
| Mission initialization | Recovered historical position/velocity/epoch, frames and padload conventions; distinguish reconstructed or synthetic inputs |
| Powered descent | Authoritative engine, throttle, position, velocity, fuel, radar and touchdown state through validated sensor/actuator feedback |
| Crew cooperation | Exactly three positions with permissions and shared observations; Armstrong/Aldrin in the LM and Collins in the CSM |

A future frontend procedure entry should include `historicalSource` (document,
page and/or transcript time), `crewRole`, `vehicle`, `preconditions`,
`requiredCapability`, `controlIntent`, `observedCompletion` and explicit
`unavailableReason`. Intent and observed completion must never be conflated.
An unavailable step stops progression; it must not be replaced by an invented
mini-game action. Proposed transport endpoints belong in a later reviewed
backend contract, not hardcoded into this frontend.

The next authentic interactive increment should connect one fully evidenced
DSKY/cockpit procedure end to end. Broadening the historical mission requires
incremental validation of the remaining controls and physical phases.

## Start and verify

```sh
make play
# Main: http://127.0.0.1:4173/play.html
# Separate lab: http://127.0.0.1:4173/attitude-lab.html
make frontend-check
make test-frontend
make test-live
```

The main recorded walkthrough also works on the existing replay-only server.
The live lab requires `make play`. No framework, runtime dependency or backend
interface was added. Validation and screenshots for this correction are in
[frontend-procedure-evidence](frontend-procedure-evidence/README.md). Earlier
evidence/report files describe their earlier delivered screens and remain intact.
