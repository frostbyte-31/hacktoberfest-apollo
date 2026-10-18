# Final integration browser verification

These are newly captured development checks, not historical Apollo telemetry.
The application source is in the isolated `codex/final-integration` checkout.
Earlier evidence and the separate frontend worktree were not changed.

## Actual checks

- `node-tests-final.command.json` records the exact Node command, checkout,
  timestamps and exit status. `node-tests-final.stdout` records **81 passed,
  0 failed, 0 skipped**. This includes 21 new provider/rendering tests.
  After matching the new TypeScript definitions to the actual backend records,
  `node-tests-contract.*` repeated all 81 successfully; the corresponding syntax
  check and current source fingerprints are retained alongside it.
- Desktop Chrome loaded `http://127.0.0.1:4189/mission.html` through the final
  server. Creation, readiness, start, pause, resume and manual throttle worked.
  A 100% manual input produced 45,040 N in the server sample, reduced propellant,
  and changed vertical velocity from descending to ascending. This was the
  independent educational physical model, not original AGC landing guidance.
- Three independent browser tabs joined one mission through the real forms.
  `three-browser-crew.json` records their common mission/sample, messages and
  separate roles. `running-role-permissions.json` records commander-only flight
  controls and the Lunar Module Pilot's separate checklist access.
- The observer workflow started three explicitly labeled deterministic fallback
  crew positions. The actual server-computed educational flight completed at
  33.74 s with vertical velocity -0.73 m/s, horizontal speed 0.04 m/s,
  346.6 kg propellant and 3.8 m downrange. The debrief classified its measured
  contact as a soft landing and explicitly distinguished it from an original
  AGC-controlled landing. See `browser-debrief.json` and
  `screenshots/measured-debrief.png`. These are modern rules, not an LLM or
  Apollo guidance.
- The preserved guidance screen still displayed all three retained scenarios.
  The 15 km and 16 km recordings displayed ignition times 360.29 and 360.44 s
  GET respectively; the missing-site recording retained alarm 01406. See
  `recorded-experiences.json`. These UI checks do not replace native execution
  validation.
- The new engine-evidence inspector selected all three retained Phase 12 cases.
  Play, pause and end scrubbing held actual observations and DSKY values, with
  source cycles, raw lines and SHA-256 fingerprints. It never ran live propulsion
  or interpolated AGC measurements.
- The preserved live attitude screen started an original native AGC session.
  Actual 700 ms browser button holds produced yaw +3.330 degrees/s with channel
  006 word 00125, then pitch +2.829 degrees/s with channel 005 word 00226.
  The run was stopped normally. `live-attitude/` preserves the actual backend
  session record, request log and checksums from this browser check.
- `browser-missions/` preserves the actual manual, three-human and fallback
  session audit logs, plus the fallback run's server debrief. Its checksum file
  identifies each retained raw artifact. The early pause-race rejection remains
  visible in the audit; it was not removed to make the run look successful.

## Responsive check and its limits

Chrome's documented viewport override did not change its measured 1470-pixel
desktop viewport. The desktop capture was therefore not labeled as mobile.

A temporary same-origin iframe rendered the actual application at **390 by
844 CSS pixels**. Its source is retained as `responsive-layout-fixture.html`;
it was removed from the application output after the check. The actual screen
reflowed to stacked flight/controls panels and two-column metrics. See
`responsive-layout.json` and `screenshots/mobile-layout-frame.png`.

This validates a responsive layout in desktop Chrome. An actual mobile device,
mobile browser emulation and touch input were **NOT RUN**. To repeat this check,
copy the retained fixture temporarily into `frontend/dist/`, open it through
the final demo server, and remove that temporary application copy afterward.

## Browser findings corrected

1. A queued control keepalive could arrive after Pause and produce a legitimate
   server rejection. The new frontend now checks authoritative status and run ID
   immediately before sending queued controls. Rapid resume/pause was repeated
   successfully; server validation remains intact.
2. An inherited SVG rule made the new flight grid too bright. The new screen's
   scoped CSS now keeps those lines subdued.
3. The final server initially rejected cross-site top-level static document
   navigation from Chrome's extension. The backend owner added a narrow static
   navigation exception while retaining API Origin/token/fetch-site checks.

No existing guidance, attitude or original AGC source file was edited by the
new-screen implementation. The frontend implementation added separate files.
The owned test server on port 4189 exited normally with code 0 after Ctrl+C;
owned test tabs were closed and the viewport override was reset.
