# Procedure-led frontend correction — verification

Work date: 18 October 2026, Asia/Tbilisi. Branch: `UI/UX`.

The default `/play.html` now centers the mission task and the original recorded
computer observations. It does not represent the earlier arbitrary attitude
challenge as an Apollo 11 mission procedure. The modern target exercise remains
separately available at `/attitude-lab.html` with an explicit synthetic label.

## What changed

- A visible current task, its purpose, the recorded action and expected observation.
- Eight evidence-backed checkpoints across all three retained scenarios; previous,
  next and direct checkpoint navigation.
- Read-only original DSKY digits, actual trace locations and guidance results.
- An explicit stopping boundary before unavailable crew continuation and ignition.
- A separate static 3D vehicle illustration, without invented recorded attitude.
- In the separate lab: YOU/TARGET relative-direction instrument, numerical yaw/pitch
  guidance, highlighted direction buttons and an illustrative drag controller.
- Flight keyboard shortcuts disabled by default; opt-in only in the lab.
- Updated entry links, startup documentation and future cockpit integration requirements.

This correction does **not** implement the full historical mission, a flown
checklist reconstruction, live DSKY keys, switch interlocks, descent, landing or
multiplayer. The current primary experience is recorded evidence review. The
main page makes that distinction explicit rather than impersonating live actions.

## Actual validation

| Check | Result |
| --- | --- |
| JavaScript frontend tests | **87 passed**, no failures or skips |
| Python frontend evidence/replay tests | **26 passed** |
| Existing backend tests | **32 passed** |
| Unique automated total | **145 passed** |
| `make frontend-check` | Verified unchanged guidance export and all ES-module syntax |
| Main browser walkthrough | Actual P63-entry relay lag, nominal and 16 km review results, missing-site alarm |
| Browser lab keyboard test | D held for 300 ms with opt-in off; AGC stayed ready/paused, 11.72 s remaining |
| Browser illustrative controller | Rightward drag sent actual +yaw then neutral through the unchanged live API |
| Main responsive widths | 320, 390 and 1440 CSS pixels: no horizontal overflow |
| Browser console | No warning/error messages observed in the main page or separate lab |

The new eight tests protect event provenance, read-only semantics, missing-event
failure, real P00 display lag at P63 entry, the actual negative-control outcome,
relative-direction assistance and discrete-only controller mapping. They reuse
the existing retained recording and do not reproduce physics in the browser.

At the actual nominal P63 entry checkpoint, the display remained PROG 00 / VERB 37 /
NOUN 63. At crew review it showed 63 / 06 / 61. Ignition calculations were 360.29 s
and 360.44 s in their respective synthetic scenarios. The missing-site case retained
01406 with no ignition result. Selecting these observations sends no AGC commands.

The native controller smoke was operator-stopped at about 0.35 s of physical
elapsed time. It is input/neutralization evidence, not a successful target hold,
historical control calibration or a flight demonstration. The retained record
contains exactly two controller requests: yaw +1 / pitch 0, followed by neutral.
No backend source or model parameter changed.

## Evidence and reproduction

- `browser-checks.json`: actual UI readbacks, size checks and main console logs.
- `controller-native-record.json`: actual loopback session, requests and provenance.
- `screenshots/mission-desktop.jpg`: the main procedure view at recorded P63 entry.
- `screenshots/mission-mobile.jpg`: responsive main view.
- `screenshots/separate-lab.jpg`: explicitly separate synthetic exercise and new controls.
- `javascript-tests.txt`, `python-frontend-tests.txt`, `backend-tests.txt`,
  `frontend-check.txt`: actual command output.
- `preservation.json`: all existing tracked backend/tools/docs evidence hashes match
  the baseline taken before this correction.
- `checksums.json`: SHA256 inventory of this evidence directory.

Run from the repository root:

```sh
make play
# Open http://127.0.0.1:4173/play.html
# Optional separate lab: http://127.0.0.1:4173/attitude-lab.html
make frontend-check
make test-frontend
make test-live
```

No runtime dependencies were added. The existing user-requested server was reused
and left running for the open mission screen. The temporary lab test tab was closed
and its native session stopped. Temporary viewport overrides were reset.

[Procedure architecture, sources and missing contracts](../FRONTEND_PROCEDURES.md)
explain the next authentic interactive increment. Earlier reports and captured
results remain untouched and describe their earlier interface revision.
