# Development observations — not acceptance results

These nine earlier captures are losslessly retained so the investigation is
reviewable. They have different observer/adapter revisions and must not replace
`../runs/verified/`. The original local build directories remain intact. Each
available executed source snapshot and raw checksum is copied as it existed;
missing snapshots are not reconstructed.

- `sink-probe1`: build stopped on treating fixed rope force constants as
  erasable observer symbols. No native success is claimed. The final observer
  explicitly excludes fixed constants from RAM snapshots.
- `sink-probe2`: early disconnected command probe, before original V48 mission
  mass initialization and the external DINC clock. A register observed while
  digits were still updating led to waiting for complete R51 checklist 14.
- `sink-probe3`, `connected-probe1`, `final-connected`: intermediate hardware,
  navigation-observer and physical coupling investigations.
- `verified-*`: pre-final four-case captures, before documented ZOUT completion
  and explicit crew disarm. The directory name belongs to that development
  run; these are not final acceptance evidence. The failed analysis exposes
  the newly written, incorrect expectation that P00 drains all reset pulses.
  Source inspection established that original STARTSB2 cancels the train early.
  The final test requires actual partial drain and preserves the AGC counter.

`preservation-status-format-mismatch.json` records a diagnostic checker error:
it compared `git status --short --untracked-files=all` with the preflight's
grouped `git status --short`. All file hashes and inventories matched; the
final check uses identical options and verifies branch/head/status too.
No frontend file changed.

The initial physical-model threshold-fixture issue is described separately in
`../source-engine.md`. Final native and model tests all pass. Development
failures are not included in the count of disjoint final tests.
