# Phase 8 evidence

Read [the report](../PHASE8_POWERED_DESCENT_FEASIBILITY.md) for the result and
source explanation. P63 is selected and rejected by original R02 with00220;
the unchanged Phase5startup's01520 is preserved. No powered descent occurred.

`run_validation.py` uses the original Phase5 schedule plus only normal DSKY
V37E63E. It refuses existing output directories, validates source/rope inputs,
builds the read-only observer, and executes four fresh native processes.

```sh
python3 -B docs/phase8-evidence/run_validation.py --source .build/phase89/source --output .build/phase8/new-run
python3 -B -m unittest discover -s docs/phase8-evidence -p 'test_feasibility.py' -v
python3 -B docs/phase8-evidence/verify_integrity.py
```

`runs/attempt-03` is the final verified experiment; attempts01/02 retain actual
development validation mistakes and exact executed source. Their native runs
completed; their validation assertions did not pass. Do not treat them as
successful validation or discard them. The report explains each mistake.

Large raw stdout files are losslessly gzip-compressed with mtime0. Every run's
`retention.json` contains original/compressed hashes, byte counts and omitted
native-binary hashes. The compressed transcripts are generated simulation
evidence, not historical Apollo mission telemetry. Original source instructions
and emulator semantics are unchanged; the new C code only observes memory.

`prior_hashes.json` and `preservation_check.json` protect3,268 earlier tracked
documentation/evidence files. `sha256.json` seals the new package and report.
None of these files fills missing historical logs or modifies earlier evidence.
