#!/usr/bin/env python3
"""Retain actual startup readbacks from the new game calibration raw traces."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=HERE / "readiness-metadata.json")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to replace retained metadata: " + str(args.output))
    result = {
        "classification": "Actual original startup diagnostic readbacks from fresh game calibration traces",
        "scope": "Initial execution registers only. Subsequent compact frames retain originalReady, not full per-frame register readbacks.",
        "sourceExtractor": {"path": str(Path(__file__).relative_to(ROOT)),
                            "sha256": digest_bytes(Path(__file__).read_bytes())},
        "cases": {}}
    for report_path in args.report or [HERE / "native-result.json", HERE / "native-combined-result.json"]:
        report_raw = report_path.read_bytes()
        report = json.loads(report_raw)
        for name, case in report["cases"].items():
            trace_path = Path(case["trace"]["path"])
            trace_raw = trace_path.read_bytes()
            trace_hash = digest_bytes(trace_raw)
            if trace_hash != case["trace"]["sha256"]:
                raise ValueError("Trace checksum changed: " + str(trace_path))
            checkpoints = [(line_number, raw_line, json.loads(raw_line))
                for line_number, raw_line in enumerate(trace_raw.splitlines(), 1)
                if b'"startup_checkpoint"' in raw_line]
            checkpoints = [(line_number, raw_line, row) for line_number, raw_line, row in checkpoints
                           if row.get("ev") == "startup_checkpoint"]
            if len(checkpoints) != 1:
                raise ValueError("Expected one actual startup checkpoint in " + str(trace_path))
            line_number, raw_line, row = checkpoints[0]
            first = case["frames"][0]
            if row["cycle"] != first["cycle"] or not row["verified"] or not first["originalReady"]:
                raise ValueError("Startup checkpoint does not match first compact frame")
            execution = row["registers"]
            if execution["modreg"] or any(execution["failreg"]) or (
                execution["imodes30"] | execution["imodes33"]) & 0o40 or not execution["dapbools"] & 4:
                raise ValueError("Actual startup registers fail native readiness checks")
            result["cases"][name] = {
                "execution": execution,
                "readbackCycle": row["cycle"],
                "verifiedStartup": row["verified"],
                "sourceReport": {"path": str(report_path.relative_to(ROOT)), "sha256": digest_bytes(report_raw)},
                "sourceTrace": {"path": str(trace_path), "sha256": trace_hash,
                                "lineNumber": line_number,
                                "rawLineSha256ExcludingNewline": digest_bytes(raw_line)},
                "actualStartupCheckpoint": row,
                "firstSampleClocks": {key: first[key] for key in ["cycle", "modelCycle", "cpuTimeSeconds", "physicalTimeSeconds"]},
                "couplingLagSecondsAtReady": first["cpuTimeSeconds"]-first["physicalTimeSeconds"],
            }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(str(len(result["cases"])) + " actual startup readbacks retained: " + str(args.output))


if __name__ == "__main__":
    main()
