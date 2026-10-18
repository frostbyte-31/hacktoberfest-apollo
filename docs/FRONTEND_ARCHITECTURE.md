# Apollo 11 frontend architecture

The first chapter now supports a 28-action, server-owned **interactive undocking
procedure trainer**. It adds source-linked cockpit selections and crew reports,
with modeled docking release, independent of original AGC execution and flight
physics. See [current playable chapter and contract](FRONTEND_UNDOCKING.md).

The current primary entry point is `/play.html`: a historical lunar-orbit starting
chapter plus a separately labeled 3D replay of the sealed Phase 12 propulsion and
navigation experiment. See [current mission architecture](FRONTEND_MISSION_START.md)
and [Apollo hardware and chronology](FRONTEND_APOLLO_OPERATIONS.md). The earlier
preparation walkthrough remains at `/preparation.html`. The Phase 10 architecture
below continues to describe the unchanged `/guidance.html` explorer.

## Delivered experience

The Phase 10 mission-control screen is `frontend/dist/guidance.html`. It presents
verified recorded original Luminary 099 execution with synthetic mission inputs.
Its boundary is pre-ignition numerical guidance. Browser functionality establishes
neither powered descent nor a successful lunar landing.

The implementation extends the existing Phase 10.5 application. The repository had
no React, TypeScript build, Tailwind, npm manifest, or WebSocket framework to reuse.
It already had static HTML/CSS/ES modules, a Python loopback server, a sealed-trace
exporter, deterministic JSON, replay helpers, and tests. Preserving that stack keeps
the offline demo usable with Python alone and avoids a second rendering/build app.
The separate attitude application at `/` and all backend routes remain intact.

## Start and verify

From the repository root, using Python 3.9 or newer:

```sh
python3 -B tools/demo/demo.py launch
# Equivalent: make demo
```

Open **http://127.0.0.1:4173/guidance.html**. If that port is occupied:

```sh
python3 -B tools/demo/demo.py launch --port 4180
```

Open **http://127.0.0.1:4180/guidance.html**. Stop the server with Ctrl-C.
The launcher checks the sealed Phase 10 evidence, exports recorded observations,
and starts the existing server with `--replay-only`. It never starts a live AGC.
No npm installation, compiler, GPU, CDN, network access, or external fonts are
required for replay. Use a standard modern browser supporting ES modules,
`structuredClone`, `dialog`, and SVG; opening the HTML through `file:` is unsupported.

The static source is the served artifact; there is no bundling step:

```sh
make frontend-check  # evidence-export consistency + syntax checks for all ES modules
make test-frontend  # Python data/provenance tests and all Node presentation tests
make test-live      # existing backend HTTP/worker and attitude replay regressions
make demo-verify    # full original Phase 10 seal + export checks
```

Node 20+ is needed only for tests and syntax checks. The checked JSDoc domain
contract can also be verified with the already-installed development TypeScript:

```sh
node_modules/.bin/tsc --noEmit --allowJs --checkJs --module nodenext --target es2022 --moduleResolution nodenext --skipLibCheck frontend/dist/mission-provider.mjs
```

This optional command is not a runtime dependency. No dependencies were installed
or changed for this milestone.

## Component and data boundaries

```text
Original Luminary + pinned native AGC / ringbuffer
  → retained Phase 10 traces and original analyzer
  → existing read-only hash-checking export_guidance.py
  → unchanged dist/data/guidance.json
  → RecordedTraceProvider
  → mission controller + independent display components
```

| File | Responsibility |
| --- | --- |
| `frontend/dist/mission-types.d.ts` | Domain interfaces for snapshots, spacecraft, guidance, DSKY, events, crew, capabilities, command results, and metadata |
| `frontend/dist/mission-provider.mjs` | Validated, immutable recorded provider; source/time/unit annotations; explicit unavailable live-guidance boundary |
| `frontend/dist/guidance-state.mjs` | Existing sample-and-hold lookup, formatting, event navigation, replay timing, static projection |
| `frontend/dist/guidance.mjs` | Selected scenario, playback, event navigation, keyboard handling, observation updates, educational context, dialogs, load/retry |
| `frontend/dist/dsky-view.mjs` | Read-only recorded display digits; no inferred program values or lamp responses |
| `frontend/dist/spacecraft-view.mjs` | Replaceable SVG renderer of supplied static 3D initial state; no replay-time input or physics |
| `frontend/dist/mission-panels.mjs` | Evidence-derived scenario comparison, capability display, exactly three planned crew positions |
| `frontend/dist/guidance.html` / `guidance.css` | Responsive mission-control layout, Apollo-inspired panel, educational content, accessible controls |

The provider accepts the existing exported presentation schema, not AGC memory
addresses. It validates chronology, source references, required quantities, and
consistent recorded end results before enabling controls. Imported observations
are deeply frozen copies. Per-value source timestamps remain separate from the
replay cursor. The UI keeps actual values until the next observation; there is no
interpolation or invented countdown.

`LiveBackendProvider` is an explicit unavailable adapter: no requests, no default
endpoint, no replay fallback, and rejected command results. The existing bounded
attitude `LiveClient` remains separate. New mission functionality must provide a
validated service and capability before a control can become available. See the
[implemented and missing integration contracts](FRONTEND_INTEGRATION_CONTRACT.md).

## Visual and interaction design

The desktop screen uses a charcoal instrument-panel treatment, amber highlights,
muted green DSKY digits, native monospaced numerical values, and simple typography.
The three-column console places the DSKY left, mission geometry center, and held
guidance observations right. Smaller tablet layouts use two columns and a shared
observation strip. A desktop replay dock stays within reach while the console is in view. Phone layouts put replay controls and geometry ahead of dense
telemetry. The comparison table scrolls inside its own container.

Users can select three actual experiments; play, pause, restart, change speed,
scrub, step retained events, jump to P63, or inspect the recorded final result.
The comparison table stays explicitly independent of replay position. Selecting
its result opens that scenario's own final observation.

Keyboard outside controls: Space toggles replay; left/right step important events;
R restarts. Range inputs retain their native keyboard controls. Focus outlines,
semantic sections, a skip link, status announcements, native dialogs, and reduced
motion support are retained. Hidden tabs pause replay. Loading/failure leaves
unknown values and disabled controls; Retry refetches the exported recording.

The DSKY is an Apollo-inspired layout using [NASA's crew-station displays report](https://ntrs.nasa.gov/citations/19750012347)
and [Virtual AGC's LM drawings/layout references](https://www.ibiblio.org/apollo/yaDSKY.html).
Its digits and blanks come from original output-channel 010. Indicator/sign lamps
are not decoded by the existing export and are explicitly unavailable (`?`),
including COMP ACTY. There is no live keypad or simulated key response. Display
relay updates can lag a recorded program event; the renderer preserves that fact.

The SVG depicts documented Moon-centered basic REF X–Z geometry. The numerical
state retains X, Y, and Z in SI units. Spacecraft navigation epoch 120 s and planned
site epoch TLAND 784.4 s are separately disclosed. Reference geometry uses the
supplied lunar radius; the vehicle symbol, crater artwork, and arrow length are
illustrative. Geometry never changes with replay time. No orbit propagation,
descent trajectory, thrust, fuel, or unverified physical state is supplied.

Ten short field notes cover navigation vectors, orbital speed, ignition timing,
guidance equations, roots, missing targets, scenario changes, original execution,
alignment, and future thrust/sensor feedback. The observation panel also explains
the selected original stage. Future physics examples are identified as education,
not telemetry.

## Extension roadmap

1. Agree an authoritative mission-snapshot/capability service with execution IDs,
   source/validity metadata, explicit clocks, and coordinate frames. Keep bounded
   attitude control distinct from descent guidance.
2. After validated propulsion/dynamics exists, add engine, acceleration, fuel,
   throttle, and authoritative 3D position/velocity observations. Never derive a
   competing frontend plant.
3. Supply actual propagated samples to a separate trajectory layer. Keep the
   initial-state illustration and physical playback explicitly distinguishable;
   optionally replace/supplement the SVG with a 3D renderer.
4. Add exactly three authenticated participant seats with server-enforced command
   permissions and shared state. Armstrong/Aldrin use the LM; Collins remains in
   the Command Module in lunar orbit.
5. Add AI recommendations/proposals only after real participant and command
   contracts exist. Extend educational context from validated physical samples.
6. A licensed spacecraft mesh and device-tested USDZ/browser viewer could support
   optional AR model viewing. No 3D/AR dependency or operational AR claim is added
   to this MVP.

These are capability increments, not assumptions about future phase numbers.

## Verification and limits

Actual command results, preservation receipt, browser readbacks, screenshots, and
current test output are retained in [frontend Phase 10 evidence](frontend-phase10-evidence/README.md).
No fresh native guidance experiment was needed or run for this frontend change.
The sealed recording remains the source of numerical claims. Historical reports
and earlier evidence manifests remain unchanged; their old screenshots represent
those earlier application revisions, not this screen.
