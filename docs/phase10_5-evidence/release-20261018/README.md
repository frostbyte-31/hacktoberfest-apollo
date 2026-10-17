# Final Phase 10 and 10.5 release checks — 2026-10-18

Fresh final checks before commit/push: **376 passed, 3 known historical
missing-evidence errors, 0 failing assertions, 0 unexpected errors, 0 skips**.
Counts are derived from captured per-suite records and actual test logs.
The three errors remain errors; gap-aware command exit zero does not make them
passing tests. Their exact original details are in `summary.json`.

The unchanged original Phase 10 native experiment ran again in a hash-verified
baseline snapshot. All four canonical trace hashes matched; seven complete fresh
native traces (including the Phase 9 controls) are losslessly compressed here.
Command logs retain actual observed paths and bytes. Generated host binaries,
the Git archive and extracted source/build trees are omitted; their source/build
metadata and relevant hashes remain available. No historical logs are recovered
or manufactured by this package.

Reproduce native execution with `python3 -B tools/demo/demo.py reproduce`.
Verify and launch the recorded UI with `make demo-verify` and `make demo`.
See `record.json` and `*.command.json` files for exact executed commands, times
and environment. See the parent Phase 10.5 report for portable prerequisites,
scenario assumptions, source references and actual browser smoke evidence.

Prior Phase 10/10.5 reports, seals and evidence are untouched. `preservation.json`
records their fresh integrity check; this release has its own independent seal.
`checksums.json` covers every release file except itself. `manifest.json` also
records original raw hashes for lossless trace decompression verification.

The UI replays recorded authentic guidance using synthetic mission inputs and a
static state projection. It does not run live pre-ignition guidance. Engine
ignition, thrust response, powered descent and landing remain NOT RUN. **Phase 11
is NOT RUN.** An internal launcher docstring says Python 3.8+; the actual public
launch instructions correctly require Python 3.9+ and govern this release.
