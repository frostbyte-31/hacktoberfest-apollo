#!/usr/bin/env python3
"""Retain verified game calibration traces without rerunning native experiments.

Read the existing new-game reports and append gzip copies to a fresh destination.
Existing destinations and manifests are never replaced. For a later run choose
--destination PATH outside the retained evidence directory.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=HERE / "traces")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise ValueError("Refusing to replace retained trace destination: " + str(destination))
    report_paths = [HERE / "native-result.json", HERE / "native-combined-result.json"]
    readiness_path = HERE / "readiness-metadata.json"
    readiness_raw = readiness_path.read_bytes()
    readiness = json.loads(readiness_raw)
    plan = []
    for report_path in report_paths:
        report_raw = report_path.read_bytes()
        report = json.loads(report_raw)
        for case_name, case in report["cases"].items():
            if case["nativeSummary"]["status"] != "VERIFIED bounded live session":
                raise ValueError("Only completed verified core cases may be packaged")
            raw = Path(case["trace"]["path"]).read_bytes()
            raw_hash = digest(raw)
            if raw_hash != case["trace"]["sha256"] or raw_hash != readiness["cases"][case_name]["sourceTrace"]["sha256"]:
                raise ValueError("Raw trace/report/readiness checksum mismatch: " + case_name)
            rows = raw.splitlines()
            source = readiness["cases"][case_name]["sourceTrace"]
            if digest(rows[source["lineNumber"]-1]) != source["rawLineSha256ExcludingNewline"]:
                raise ValueError("Readiness checkpoint line checksum mismatch: " + case_name)
            compressed = io.BytesIO()
            with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as stream:
                stream.write(raw)
            packed = compressed.getvalue()
            if gzip.decompress(packed) != raw:
                raise ValueError("Lossless gzip verification failed")
            name = case_name+".jsonl.gz"
            plan.append((name, packed, {
                "case": case_name,
                "classification": "Core verified fresh native calibration; no partial or supplemental case",
                "file": name, "gzipSha256": digest(packed), "gzipBytes": len(packed),
                "rawSha256": raw_hash, "rawBytes": len(raw), "rawJsonlRows": len(rows),
                "originalRawPath": case["trace"]["path"],
                "sourceReport": {"path": str(report_path.relative_to(ROOT)), "sha256": digest(report_raw),
                                 "traceJsonPointer": "/cases/"+case_name+"/trace"},
                "readinessMetadata": {"path": str(readiness_path.relative_to(ROOT)), "sha256": digest(readiness_raw),
                                      "traceJsonPointer": "/cases/"+case_name+"/sourceTrace",
                                      "startupLineNumber": source["lineNumber"]},
            }))
    manifest = {
        "schemaVersion": 1,
        "classification": "Lossless retained copies of six core fresh native game calibration traces",
        "sourcePackager": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": digest(Path(__file__).read_bytes())},
        "compression": "gzip level 9, empty stored filename, mtime 0",
        "traceCount": len(plan),
        "totalRawBytes": sum(item[2]["rawBytes"] for item in plan),
        "totalGzipBytes": sum(item[2]["gzipBytes"] for item in plan),
        "pathMapping": "For each sourceReport/readinessMetadata JSON pointer, use the sibling gzip file; verify the decompressed bytes against rawSha256. Original absolute paths are provenance, not a runtime requirement.",
        "supplementalCases": "Supplemental browser/chord and interrupted calibration cases are not part of this core trace package.",
        "traces": [item[2] for item in plan],
    }
    destination.mkdir(parents=True)
    for name, packed, _ in plan:
        with (destination / name).open("xb") as stream:
            stream.write(packed)
    with (destination / "manifest.json").open("x") as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False)+"\n")
    print("Retained", manifest["traceCount"], "core traces:", manifest["totalRawBytes"], "raw bytes ->",
          manifest["totalGzipBytes"], "gzip bytes at", destination)


if __name__ == "__main__":
    main()
