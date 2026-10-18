#!/usr/bin/env python3
"""Rebuild and execute the original CMC bench; never changes prior evidence."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.cmc_native import (CmcProcess, prepare_cmc_assets, ROPE_SHA256,
                                CMC_ARCHIVE_SHA256, EVIDENCE, _extract, _digest)


def run(argv, cwd, output, label, input_bytes=None):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, input=input_bytes,
                            capture_output=True, timeout=120)
    for name, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
        with gzip.GzipFile(filename=str(output / f"{label}.{name}.gz"), mode="wb", mtime=0) as stream:
            stream.write(raw)
    (output / f"{label}.command.json").write_text(json.dumps({"argv": [str(x) for x in argv],
        "cwd": str(cwd), "exit": result.returncode}, indent=2) + "\n")
    if result.returncode:
        raise RuntimeError(label + " failed: " + result.stderr.decode(errors="replace")[-2000:])
    return result


def assemble(output):
    manifest = json.loads((EVIDENCE / "source-manifest.json").read_text())
    if _digest(EVIDENCE / "corresponding-source.tar.gz") != CMC_ARCHIVE_SHA256:
        raise ValueError("Comanche source archive differs")
    source = output / "source"
    _extract(EVIDENCE / "corresponding-source.tar.gz", source,
             {name: record["sha256"] for name, record in manifest["files"].items()})
    assembler = source / "yaYUL/yaYUL"
    run([shutil.which("cc"), "-O2", '-DNVER="pinned-f577e3f"',
         *sorted((source / "yaYUL").glob("*.c")), "-lm", "-o", assembler], ROOT, output, "assembler-build")
    assembled = run([assembler, "MAIN.agc"], source / "Comanche055", output, "assembly")
    if not all(text in assembled.stdout for text in (b"Unresolved symbols:  0", b"Fatal errors:  0", b"Warnings:  0")):
        raise ValueError("Comanche assembly summary differs")
    converter = source / "Tools/oct2bin"
    run([shutil.which("cc"), "-O2", '-DNVER="pinned-f577e3f"', source / "Tools/oct2bin.c",
         source / "Tools/utils.c", "-o", converter], ROOT, output, "converter-build")
    proof = output / "octal-proof"
    proof.mkdir()
    run([converter], proof, output, "octal-conversion",
        input_bytes=(source / "Comanche055/Comanche055.binsource").read_bytes())
    rope = source / "Comanche055/MAIN.agc.bin"
    if not rope.read_bytes() == (proof / "oct2bin.bin").read_bytes() == (EVIDENCE / "artifacts/Comanche055.bin").read_bytes():
        raise ValueError("Assembly, proofed octal listing and retained rope differ")
    return {"assembledRopeSha256": _digest(rope), "octalRopeSha256": _digest(proof / "oct2bin.bin"),
            "byteIdentical": True, "unresolvedSymbols": 0, "fatalErrors": 0, "warnings": 0,
            "sourceFiles": len(manifest["files"])}


def case(assets, output):
    computer = CmcProcess(assets, output)
    checkpoints = []
    key_acks = []
    def checkpoint(name, snapshot):
        checkpoints.append({"name": name, "cycle": snapshot["cycle"],
                            "dsky": snapshot["dsky"], "dskySource": snapshot["dskySource"]})
        return snapshot["dsky"]
    def keys(sequence):
        for key in sequence:
            key_acks.append(computer.key(key)["ackpacket"])
        return computer.advance(2)
    try:
        checkpoint("cold_start", computer.boot())
        lamps = checkpoint("original_V35_lights_test", keys(["VERB", "3", "5", "ENTR"]))
        assert all(lamps[name] == "88" for name in ("PROG", "VERB", "NOUN"))
        assert all(lamps[name] == "88888" for name in ("R1", "R2", "R3"))
        # Let the original five-second light test finish before resetting.
        computer.advance(5)
        p00 = checkpoint("original_P00", keys(["RSET", "VERB", "3", "7", "ENTR", "0", "0", "ENTR"]))
        assert p00["PROG"] == "00"
        clock1 = checkpoint("original_V16N36_clock", keys(["VERB", "1", "6", "NOUN", "3", "6", "ENTR"]))
        assert clock1["VERB"] == "16" and clock1["NOUN"] == "36"
        clock2 = checkpoint("original_clock_progression", computer.advance(3))
        assert [clock1[f"R{i}"] for i in (1, 2, 3)] != [clock2[f"R{i}"] for i in (1, 2, 3)]
        checkpoint("P52_selected_original_readiness_gate", keys(["VERB", "3", "7", "ENTR", "5", "2", "ENTR"]))
        alarm = checkpoint("actual_original_0210_IMU_unavailable", keys(["VERB", "0", "5", "NOUN", "0", "9", "ENTR"]))
        assert alarm["VERB"] == "05" and alarm["NOUN"] == "09" and alarm["R1"] == "00210"
        recovered = checkpoint("original_P00_recovery", keys(["RSET", "VERB", "3", "7", "ENTR", "0", "0", "ENTR"]))
        assert recovered["PROG"] == "00"
        pro = computer.key("PRO")["ackpacket"]
        assert pro["channel"] == 0o32 and [packet["channel"] for packet in pro["packets"]] == [0o432, 0o32, 0o32]
        assert [packet["value"] for packet in pro["packets"]] == [0o20000, 0, 0o20000]
        assert all(ack["consumedAtCycle"] > ack["queuedAtCycle"] for ack in key_acks)
        assert all(ack["accepted"] > 0 for ack in key_acks)
        result = {"status": "VERIFIED", "checkpoints": checkpoints, "keyPacketsConsumed": len(key_acks),
                  "proceedDiscreteVerified": True, "physicalFlightExecuted": False,
                  "alignmentCompleted": False, "result": "Original CMC computer checkout and real IMU-readiness diagnosis; flight gate remains closed"}
        (output / "checkpoints.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        computer.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--with-wasm", action="store_true", help="Also require exact cycle-locked native/WASM output identity (requires Node)")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("Validation output must be a new directory")
    output.mkdir(parents=True)
    assembly = assemble(output)
    assets = prepare_cmc_assets(output / "assets")
    first = case(assets, output / "first")
    repeat = case(assets, output / "repeat")
    if (output / "first/trace.jsonl").read_bytes() != (output / "repeat/trace.jsonl").read_bytes():
        raise ValueError("Fresh-process deterministic CMC replay differs")
    report = {"status": "VERIFIED", "assembly": assembly, "native": {
        "checkpoints": len(first["checkpoints"]), "keyPacketsConsumed": first["keyPacketsConsumed"],
        "freshProcessTraceByteIdentical": True, "traceSha256": _digest(output / "first/trace.jsonl"),
        "ropeSha256": ROPE_SHA256, "actualReadinessAlarm": "00210"},
        "scope": "Original cold-start CMC DSKY execution only; no initialized Earth orbit, star measurements, alignment completion, TLI or spacecraft flight"}
    if args.with_wasm:
        if not shutil.which("node"):
            raise RuntimeError("Node is required for --with-wasm validation")
        comparison = output / "native-wasm-comparison.json"
        run([shutil.which("node"), EVIDENCE / "experiments/compare_wasm.mjs", output / "first/trace.jsonl",
             ROOT / "docs/phase2-evidence/artifacts/yaAGC.wasm", EVIDENCE / "artifacts/Comanche055.bin", comparison],
            ROOT, output, "native-wasm")
        report["nativeWasm"] = json.loads(comparison.read_text())
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
