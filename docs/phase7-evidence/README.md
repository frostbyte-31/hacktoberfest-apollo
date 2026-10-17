# Phase 7 evidence

The [validation report](../PHASE7_MULTIAXIS_VALIDATION.md) is the entry point. Capability C is verified only for the bounded synthetic yaw/pitch fixture. Original Luminary099/emulator code and all earlier evidence remain unchanged. Traces are generated simulation experiments, not historical mission telemetry.

- `source/`: pinned original routines, hardware mappings, primary corroboration, checksums and offline source checker.
- `physics/`: source-locked modern model overlay, deterministic component tests, actual component results and preserved development attempts.
- `integration/`: native observer/driver, three-FIFO and captured-trace tests, actual development runs and executed-source snapshots.
- `preflight/`: focused current-baseline commands and results, with references to byte-identical earlier traces.
- `runs/2026-10-17-verified-check/`: complete final `make check` command/output, suite results, fresh validation metadata, raw traces and preservation results.
- `prior_hashes.json`: 1,520 previously retained tracked files frozen before Phase 7 changes.
- `repository-state.json`, `final-integrity.json`, `package-manifest.json`: final local state, checks and SHA-256 inventory.

Run from the repository root:

```sh
make test-phase7
make validate-phase7
make check
```

The locked Tcl runtime is verified or built by the Make targets. Fresh output goes to new `.build` directories; retained evidence is not overwritten. Host compiler/Python/OS are recorded, not pinned. Existing historical missing-log errors are reported separately from passing suites.

JSONL traces use deterministic lossless gzip where retained under `.jsonl.gz`. `runs/2026-10-17-verified-check/retention.json` records each raw and compressed hash, references identical old traces without copying them, and lists omitted rebuildable binaries/source copies. Decompress before reading JSON lines. Generated absolute paths in captured execution records identify the actual run location; use this inventory to locate retained copies after moving the checkout.

The modern component harness can prescribe jet activity to test physics. Only the separately captured native integration cases establish authentic AGC control. Failed probes, partial attempts and their executed source snapshots are retained and distinguished from the final verified run. No historical missing log was synthesized.
