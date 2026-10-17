# Playable 3D Eagle flight trainer — verification report

Work date: 18 October 2026, Asia/Tbilisi. Branch: `UI/UX`.

The application now offers a playable attitude acquisition game at
`/play.html`. The player arms a fresh original Luminary 099 session, rotates a
3D Lunar Module toward a target, reduces its rotation rate and earns a score
after an observed target hold. Yaw, pitch and combined challenges, keyboard and
pointer holds, camera orbit/zoom, debrief, retry and an in-tab best score work.

This is bounded synthetic attitude training. It does not simulate translational
flight, engine ignition, descent, touchdown, multiplayer or AI crew. The target
and score are modern game objectives. Only actual native samples establish a
successful hold. Camera movement does not steer the spacecraft.

## Launch

From the repository root:

```sh
make play
```

Open **http://127.0.0.1:4173/play.html**. Select a challenge and press **Arm the
AGC**. Wait for **You have the controls**. Hold **A/D** for yaw, **S/W** for
pitch, or use the on-screen buttons. Try a short input first; neutral is not an
instant brake. Space releases controls. The 11.7-second physical window starts
at the first deflection. **Fly again** creates a fresh original execution.

Python 3.9+, make, a C compiler and initial download access are needed. The
first launch builds checksum-pinned Tcl 8.6.16 locally. There are no npm, CDN,
model-download or browser framework dependencies. For an occupied port use
`make play PORT=4180` and open that port. `make demo` intentionally disables
live input; the game explains the required startup and awards no score there.
Owned QA servers are stopped after validation; run the command above to play.

## Architecture and preserved infrastructure

The existing static HTML/CSS/ES module application and Python loopback server
were retained. No replacement frontend framework or new backend endpoint was
needed. Existing guidance and attitude pages link to the new game.

| Component | Responsibility |
| --- | --- |
| `play.html`, `flight.css` | Responsive game screen, help, telemetry, accessible controls |
| `flight.mjs` | Capability discovery, existing live client, controls, UI lifecycle |
| `game-state.mjs` | Pure target/hold/scoring rules using observed physical samples |
| `spacecraft-3d.mjs`, `spacecraft-mesh.mjs` | Procedural WebGL Lunar Module, camera, target outline, Canvas projection fallback |
| Existing `live.mjs` | Unchanged same-origin live transport and input leases |
| Existing native backend | Authoritative original AGC execution and external rotational model |

The renderer consumes scalar-first body-to-stable quaternions. It does not
integrate or extrapolate spacecraft motion. Malformed or unavailable telemetry
releases controls and is labeled as a last sample. Stopping freezes physical
integration; later native sensor settlement cannot earn a hold. A successful
scored sample is distinguished from the final backend orientation.

`preservation.json` confirms **5,521 existing tracked files** under `backend/`,
`tools/`, `docs/` and `AGENTS.md` match the pre-edit hashes. Original Apollo
sources, emulator semantics and all existing experiment evidence are untouched.

See [the integration contract](../FRONTEND_GAME_CONTRACT.md) for implemented
HTTP routes, timestamps, coordinate conventions, validity, numerical limits and
missing future capabilities.

## Actual checks

| Check | Result |
| --- | --- |
| `make runtime` | Checksum-pinned Tcl prepared successfully |
| `make frontend-check` | Original guidance export verified; every application module passes syntax checks |
| `node --test frontend/tests/*.test.mjs` | 79 passed, 0 failed/skipped |
| `make test-live` | 32 backend Python + 12 replay Python + 22 JavaScript passed |
| Guidance export Python tests | 14 passed |
| Unique automated tests | **137 passed**; the 22 live/replay JavaScript tests are already included in the 79 |
| Fresh core native execution | Six completed verified original sessions; readiness and lossless settlement checked |
| Real browser, WebGL | Desktop yaw and pitch acquisition; mobile on-screen yaw acquisition |
| Responsive layout | No horizontal overflow at 320, 390, 900 or 1440 CSS pixels |
| Replay-only server | Arming disabled, explicit unavailable message, visual model available, no score |

The guidance export remains exactly 2,736,537 bytes, SHA256
`36d380a5274312621145d3549a161fea7040d269c549738239ac4e7dabf52709`.
Test output is retained in `javascript-tests.txt`, `live-regression-tests.txt`,
`guidance-tests.txt` and `frontend-check.txt`. `validation.json` summarizes counts.

`browser-checks.json` retains actual UI observations: desktop yaw scored **884**,
desktop pitch **885**, and mobile yaw **890**. Three combined browser attempts
timed out and remain recorded as losses, including an attempt with the final
1.3°/s rule. Successful combined acquisition is verified separately using
actual captured native samples in the reducer tests; the browser attempts are
not described as successes. UI input arrival and original gated reads matter.
Camera orbit changed the view without changing telemetry. Browser console
warnings/errors were empty in the tested live page.

## Retained evidence

- `screenshots/`: desktop standby and actual acquired results, mobile model and
  controls, unavailable live service. These are actual browser captures.
- `browser-native-records.json`: all six actual HTTP sessions and requests,
  including winning and losing runs, with source record checksums.
- `native-result.json`, `native-combined-result.json`: six core fresh native
  runs, commands, source provenance, sampled physical frames and summaries.
- `readiness-metadata.json`: actual startup register readbacks and raw line
  hashes, separate from later per-frame observations.
- `traces/manifest.json`: six lossless gzip raw traces, **145,296 JSONL rows**,
  raw/compressed hashes and report/readiness mappings. Absolute `.build` paths
  in original reports are provenance; retained gzip copies are portable.
- `native-chord-result.json`: supplemental pulse analysis and an old-rule
  browser loss. Four additional native cases completed; a fifth was interrupted
  when calibration stopped. This extra diagnostic batch is explicitly
  **INCOMPLETE**, separate from the six verified core sessions.
- `checksums.json`: retained evidence integrity inventory.

`native_smoke.py` reproduces fresh native calibration into a new build directory;
it refuses to replace a retained report. `extract_readiness.py` reads the raw
startup checkpoints. `package_traces.py` makes lossless copies and refuses an
existing destination. None is an application replay provider. The live game
starts fresh native executions.

## Next integration steps

1. Add a backend capability for a longer validated physical timeline and a
   target-attitude command contract if supported by original software.
2. Add authoritative position, velocity, engine, fuel and contact state before
   implementing translational flight and landing challenges.
3. Add explicit crew ownership/permissions before multiplayer controls; keep
   future AI recommendations separate from accepted commands.

The current mesh is an illustrative vehicle. Detailed asset replacement, optional
AR and a future translation-aware viewer can reuse the renderer boundary.
