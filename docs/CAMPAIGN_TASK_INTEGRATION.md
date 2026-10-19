# Original-computer campaign integration

## Delivered scope

`campaign.html` now separates a player task, original source references, retained experiments and historical flight. The 16-stage chronological catalog is preserved. **This change does not complete the sixteen-stage flight game.** Live P52 is the qualified original-computer task. The selected undocking checklist and recorded guidance/propulsion experiments retain their separate classifications.

The new source index identifies the original programs behind every chapter, including exact symbols, original file lines, source hashes and eight-line excerpts. Read-only excerpts are never presented as execution. Full original flight still needs initialized computers, spacecraft peripherals, vehicle dynamics and measured outcomes.

## Player workflow

1. Start `make play PORT=4180` from this checkout. Open `http://127.0.0.1:4180/campaign.html?play=1&stage=earth-parking`. Use another free port if needed.
2. Read **Your task**, then select **Open alignment station** and **Prepare alignment instruments**. The latter runs a disclosed fresh original P51 setup through modeled instrument inputs.
3. Operate the on-screen DSKY, optics hand controller and MARK controls. Follow the next-action instructions and five observed checkpoints. The task requires actual P52 computations, gyro commands, modeled instrument feedback and final P00; entering a sequence alone cannot complete it. The detailed operator guide is in `EARTH_ALIGNMENT_INTEGRATION.md`.
4. After qualified completion, the task card shows the current session result. **Inspect departure requirements** opens the next historical chapter; it does not ignite an engine or execute TLI.
5. Select any chapter and choose **Inspect original software**. Expand a source excerpt or open the full original listing. The displayed missing systems describe why that historical maneuver is not currently executable.
6. At Eagle preparation or powered descent, **Inspect original recording** opens the retained experiment. At undocking, the separate trainer link opens its 28 selected crew actions. Neither completes a historical flight goal.
7. Reload to observe saved local task history. An active computer is verified only after a new valid service observation. A stopped or lost connection cannot retain current-run qualification.

`make play PORT=4180` serves the existing static application and Python backend. No frontend build or installation step is required. The native original-computer task needs Python, a C compiler and retained source/binary assets. The launcher reports missing dependencies. `--recorded-only` disables live CMC execution and cannot be used for P52.

## Frontend modules

- `campaign-task-state.mjs`: immutable original-task definitions and qualified run/history state, independent of `campaign-state.mjs` historical navigation.
- `campaign-task-panel.mjs`: root-scoped task, current instruction, source exploration and result display; dispatches only explicit navigation callbacks.
- `campaign-programs.mjs`: source-index validation. A source listing cannot announce execution availability.
- `data/campaign-programs.json`: 16 chronological stages, 23 original entry points across 15 source files; source text checked against retained corresponding-source archives/listings.
- `campaign.mjs`: connects the existing original-computer provider to task qualification. Neither the tour, camera controls nor chapter navigation sends spacecraft commands or issues task receipts.

The existing `EarthAlignmentClient` remains responsible for authenticated transport, strict input sequencing, acknowledgements, observation validation, timeouts and resynchronization. An uncertain input is never automatically repeated.

## Completion and persistence contract

P52 qualification requires the pinned Comanche rope hash, a ready original computer and all five service-owned steps. Six ordered source-bound checkpoints must identify original P52 selection, two marks, N05 review, N93 review, completion request 00014 and final P00. Original gyro outputs and feedback operations must be present. No capability boolean, replay completion or caller-supplied task receipt can substitute.

Receipts are scoped by task, native session, source/engine hashes and original completion cycle. The first qualified receipt is immutable; subsequent observation polling does not rewrite saved history. A repeated P52 attempt preserves earlier history while requiring fresh completion evidence for the current attempt.

Browser storage key: `apollo11.original-task-history.v1`. At most 32 receipts are retained. Only history is serialized—never tokens, commands, live-session authority, flight state or capabilities. Restored receipts are classified `local-history-unverified`; a fresh service observation is required before a run is current. Invalid, old or blocked storage does not prevent play. Clearing saved history does not reset the running CMC; restart the alignment fixture to create a new recorded attempt afterward.

This is an educational local history, not a signed server certificate or multiplayer achievement service.

## Verified backend integration

The implementation continues using the existing `/api/earth-alignment/{capabilities,status,start,key,instrument,stop}` contract. Capabilities now include:

```json
{
  "originalPrograms": {
    "P52": {"available": true, "classification": "LIVE ORIGINAL CMC / MODELED INSTRUMENTS"},
    "P47": {"available": false, "classification": "UNVALIDATED ORIGINAL PROGRAM"}
  }
}
```

P52 availability follows actual native discovery; the example assumes dependencies are present. P47 carries its actual unavailable reason. No new flight endpoint was invented. Existing crew procedures, recorded providers and the independent modern landing laboratory are unchanged.

## Next original-code milestones

1. Isolate the actual P47 abort cause in a reproducible initialized CMC experiment. Fresh retained P52→P47 runs reach original alarm **01204**; displaying N62 afterward is not a successful monitor. The cause is unresolved. `TIMEDELT` is a fixed rope constant, not a missing erasable padload. See `campaign-original-code-evidence/README.md`.
2. Establish a validated CMC navigation epoch/state and documented original input/update path. Couple real actuator outputs to external modeled hardware and return sensor counter operations, with causal controls.
3. Validate one maneuver outcome before enabling its campaign task. CMC alignment or monitoring cannot substitute for the Saturn V launch-vehicle computer that controlled nominal TLI.
4. Integrate CSM RCS/docking and SPS maneuvers; then the LGC DPS/radar/attitude chain for P63/P64/P66. The retained fixed-attitude engine fixture does not demonstrate retrograde braking or a landing.
5. Extend to surface/ascent, two-vehicle rendezvous, SPS Earth return and original CMC entry with atmosphere/recovery hardware. Earth return ends in direct atmospheric entry and splashdown.

The source-by-source requirements for all sixteen chapters are in `CAMPAIGN_ORIGINAL_CODE_SCOPE.md`. Capability names are integration targets, not promises of existing services.

## Verification

Run `make test-frontend`, `make frontend-check`, the frontend TypeScript check, and the focused native CMC/alignment HTTP tests. Source-index tests verify hashes/excerpts against retained files rather than trusting the exported index. Browser checks should cover an actual P52 completion, reload, stopped execution, unavailable TLI, source inspection, retained recordings and a mobile viewport.

No historical Apollo source, emulator instruction semantics or prior experiment evidence is modified by this integration.
