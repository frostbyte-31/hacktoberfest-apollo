# Apollo 11 mission-control frontend

This frontend milestone presents the existing, verified Phase 10 pre-ignition
experiments. It does not implement the backend powered-descent milestone also
provisionally called “Phase 11.” Original flight software, emulator semantics,
scientific reports and historical evidence remain outside its edit scope.

## Starting point and implementation choice

The isolated branch is `codex/frontend-mission-control`, based on
`5a689c75d43613f29a49fa32d9bd786437825ee5`. The existing application is plain
HTML, CSS and browser ES modules served by `frontend/serve.py`; there was no
React, npm application build, WebSocket service or live P63 API to extend.
Keeping that stack preserves the functioning attitude lab and dependency-free
recorded demo. Types are introduced at the data boundary rather than by
rebuilding the application in a framework.

The primary educational screen is `/guidance.html`. The existing `/` attitude
lab, its recorded experiments and its separate bounded live controls remain
available. Selecting a recording never starts a native AGC.

The screen uses a three-column desktop composition: DSKY left, prominent lunar
geometry center, guidance right. The top bar identifies the recorded mode,
stage and held mission-clock observation. Scenario/transport controls and the
event log remain interactive. On narrow screens, the static spacecraft view
and important controls come first. `mission-control.css` layers the new layout
over the retained guidance styles rather than replacing the old attitude app.

## Data and rendering boundaries

```text
Unchanged Luminary 099 + pinned emulator
  → retained native Phase 10 traces and source checkpoints
  → existing integrity-checked Python exporter
  → data/guidance.json
  → typed RecordedTraceProvider
  → mission-control screen + independent SVG viewer

Existing local attitude HTTP service
  → read-only LiveBackendProvider capability/status discovery
  → availability information; no live guidance substitution
```

The frontend is a consumer of execution evidence. It does not implement an AGC,
calculate new guidance roots, propagate an orbit, create thruster commands or
own authoritative spacecraft state. Replay controls select a retained
observation. Between observations, numbers hold their preceding value. The
browser clock advances playback position, not an emulated mission clock.

The existing `frontend/tools/export_guidance.py` verifies the Phase 10 seal,
original rope, retained compressed and raw traces, configuration, observer map
and original analysis assertions before producing the browser artifact. The
new provider adapts this artifact; it does not reinterpret AGC memory or create
new backend results. Raw evidence remains under `docs/phase10-evidence/`.

## Screen and component responsibilities

| Component | Responsibility | Boundary |
|---|---|---|
| Mission shell | Mission stage, execution mode, observed clock, navigation | Always identifies recorded execution |
| DSKY panel | Retained PROG/VERB/NOUN/register digit observations | Unknown signs/indicator states remain unknown |
| Spacecraft viewer | Moon, initial state projection, velocity direction and site reference | Static illustration; no trajectory generation |
| Guidance panel | Observed roots, signed time-to-go, ignition epoch and solution lead | Different time meanings retain distinct labels |
| Event/replay controls | Scenario, play/pause, restart, speed, scrub and event steps | Selects actual samples/events; no interpolated AGC states |
| Comparison dialog | Completed recorded results from the three scenarios | Does not accept arbitrary mission inputs |
| Learning panel | Short explanations connected to displayed evidence | Educational equations never replace original guidance |
| Capability/crew sections | Available data sources and planned crew roles | No fabricated engine, multiplayer or AI activity |

`guidance.mjs` coordinates the screen and user interactions. Presentation helpers
remain separate from the provider. The SVG spacecraft viewer accepts documented
three-dimensional initialization data, so a future renderer can consume the same
state without moving physics into the UI. The older `spacecraft.mjs` attitude
viewer is retained for the existing attitude lab.

| Module | Public boundary |
|---|---|
| `frontend/dist/mission-types.d.ts` | Frontend-domain types for modes, observations, provenance, mission snapshots, geometry, DSKY, capabilities and planned crew |
| `frontend/dist/mission-provider.mjs` | Read-only RecordedTraceProvider and LiveBackendProvider; capability and crew metadata |
| `frontend/dist/guidance-state.mjs` | Retained recording validation, bounded replay timing and formatting |
| `frontend/dist/spacecraft-view.mjs` | Independent static SVG projection renderer |
| `frontend/dist/guidance.mjs` | Scenario/replay screen, events and detail dialogs |

The viewer exports `spacecraftViewModel(initial)` for presentation geometry and
`renderSpacecraftView(root, initial)` for scoped SVG rendering. Neither mutates
the initialized state nor advances a physics clock. The screen also offers
twelve short learning explanations and exactly three explicitly planned crew
cards; those are reusable presentation structures, not active flight systems.

The provider has `// @ts-check` and imports its JSDoc types from the declaration
file. `frontend/tsconfig.json` checks that boundary with TypeScript 5.9.3 and
`noEmit`; it does not claim that every legacy application module has been
converted or strictly checked. The dev dependency adds no browser runtime or
production build requirement.

The original P51 sequence uses synthetic star sightings and a stationary
instrument fixture. A software-set alignment-valid flag demonstrates the
original readiness logic, not a physically calibrated Apollo 11 navigation
alignment. The Phase 10 initialized mission geometry is likewise synthetic.

The three scenarios are deliberately bounded:

| Scenario | Retained outcome |
|---|---|
| Synthetic 15 km orbit | Nine observed ROOTPSRS results; completed ignition-time iteration; V06N61; TIG 360.29 s GET |
| Synthetic 16 km orbit | Nine observed results; V06N61; TIG 360.44 s GET |
| Missing landing-site load | Three provisional results, then original 01406; no completed ignition-time solution |

The scenario comparison reads each completed recording. It does not infer a
general altitude-to-ignition formula from these two observations.

## Geometry, time and DSKY conventions

The supplied spacecraft position and velocity are Moon-centered basic REF
inertial vectors in metres and metres/second at epoch 120 s. The site is a
Moon-fixed initialized vector independently transformed to basic REF using the
documented nominal matrix at TLAND 784.4 s. These are separate epochs. The
viewer projects X–Z, with screen vertical opposite REF Z. Decorative lunar
texture, vehicle symbol and arrow length are illustrative. The orbit circle is
an initial-radius guide, not a propagated flight path.

Playback elapsed time, sampled AGC mission time, negative signed guidance
time-to-go, absolute ignition epoch and ignition lead at the solution observation
are distinct. In the nominal recording, held solution values include TIG
360.29 s GET and lead 139.03 s. The lead is not a live countdown. The final
nominal signed time-to-go is approximately −582.79 s; its sign is preserved.

The DSKY arrangement is inspired by the Apollo instrument. Digits come from the
existing channel `010` relay decoder. The recording adapter does not decode the
register sign lamps, flashing or complete annunciator outputs. An unknown lamp
is not an unlit lamp, and an alarm-register value is not proof of its lamp state.
The panel does not generate responses to arbitrary keyboard commands.

The primary references checked for this distinction are the Virtual AGC
[peripheral interface documentation](https://www.ibiblio.org/apollo/developer.html)
and [yaDSKY documentation](https://www.ibiblio.org/apollo/yaDSKY.html), plus the
[pinned LM instrument configuration](https://github.com/virtualagc/virtualagc/blob/f577e3fd917866c59334e6cdd32504f09df76f60/yaDSKY2/LM.ini).
The retained `yaDSKY2/LM.ini` SHA-256 is
`5ebfa0fdb970e1f18d962c00ea1e7c5d680c205e7c0915df633d8790754a1ba2`.
These references
separate digit relays, indicator signals and emulated flashing; yaDSKY also
documents the Apollo 11–14 LM indicator legends. The repository's pinned
decoder and captured words remain the source of displayed values. The NASA
[archived document HSI-208424](https://www.ibiblio.org/apollo/Documents/HSI-208424.pdf)
is supplementary reference material, not an assertion that this UI recreates
every instrument function.

## Live execution and future expansion

The implemented live backend controls a separate bounded synthetic yaw/pitch
attitude fixture. Its inputs are rotational-hand-controller deflections, not
arbitrary DSKY commands or P63 mission inputs. The guidance screen may discover
that service and read its status; this never changes the provenance of the
recorded guidance screen. Existing live control remains in the attitude lab.
See [the integration contract](FRONTEND_INTEGRATION_CONTRACT.md) for actual
routes and restrictions.

Exactly three future crew positions are represented: Neil Armstrong, Commander;
Buzz Aldrin, Lunar Module Pilot; and Michael Collins, Command Module Pilot in
lunar orbit. They are planned roles, with no active participant, permissions,
communications service, multiplayer session or AI agent. Backend capability
availability, rather than a provisional phase number, should determine when
future controls become enabled.

Future engine and translational displays require an authoritative backend
contract first: units, coordinate frame, timestamp, validity and provenance for
each sample. A future 3D viewer should replace or supplement only the rendering
component. Live mission guidance, remote shared state and crew commands are
separate unimplemented integrations. Optional AR/3D is deferred; no model license,
asset, USDZ conversion or device support is claimed by this milestone.

## Launch, checks and evidence

From this checkout, with Python 3.9 or newer:

```sh
make demo PORT=4182
# Equivalent launcher without make:
python3 -B tools/demo/demo.py launch --port 4182
```

Open `http://127.0.0.1:4182/guidance.html`. The launcher checks the evidence and
starts the existing server in replay-only mode. Recorded playback requires no
Node runtime, compiler, external fonts, CDN or backend execution service.

To use the preserved live attitude lab separately:

```sh
python3 -B frontend/serve.py --port 4183
```

Open `http://127.0.0.1:4183/`. Native startup requires the existing compiler and
locked-runtime prerequisites. It begins only on an explicit start action in
that lab. Running the guidance screen does not prove native flight execution.

Artifact checks and fresh native reproduction remain separate:

```sh
make demo-verify
make demo-reproduce
```

For development, the pinned type checker and Node presentation tests are separate
from the Python-only launch:

```sh
cd frontend
npm ci
npm run typecheck
npm test
```

The existing Python exporter/provenance tests remain runnable from the repository
root with `python3 -B -m unittest discover -s frontend/tests -p 'test_*.py' -v`.
These are reproduction commands; actual outcomes are recorded in the new
frontend evidence, rather than inferred from the command list.

The final frontend test, browser and preservation receipts are retained under
`docs/frontend-evidence/`. They distinguish source/type/unit/browser checks
from native AGC experiment evidence. The three known historical missing-log
errors remain evidence gaps; this frontend neither recreates those logs nor
removes their checks. No powered descent or landing is established by a
successful UI check.

## Next frontend integrations

1. Agree on a source-stamped live mission snapshot with the backend before
   displaying live P63 or propulsion state. Keep guidance, physical state and
   sensor measurements independently identifiable.
2. Expose complete DSKY relay/sign/annunciator observations and validated key
   actions when a native mission service exists; do not infer them from stage
   names.
3. Add crew participation only after the backend supplies session identity,
   exactly three role assignments, permissions and acknowledged commands.
