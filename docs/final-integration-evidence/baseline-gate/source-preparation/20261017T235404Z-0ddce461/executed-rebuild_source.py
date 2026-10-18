#!/usr/bin/env python3
"""Build original yaYUL and assemble an unmodified Luminary099 copy.

This script never changes the supplied extracted pinned source directory.
The output directory must not exist. Symbols are parsed from actual assembler
output, not assigned by the fixture. Supply the retained rope for comparison.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import platform
import re
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(source):
    return {
        str(path.relative_to(source)): sha(path)
        for folder in ("yaYUL", "Luminary099")
        for path in sorted((source / folder).rglob("*"))
        if path.is_file()
    }


def parse_symbols(listing):
    symbols = {}
    for lineno, line in enumerate(listing.splitlines(), 1):
        for match in re.finditer(
            r"(\d+),([CEFI?]):\s+(\S+)\s+((?:E?[0-7]{1,2},)?[0-7]{4,7})(?=\s|$)",
            line,
        ):
            index, kind, name, address = match.groups()
            row = dict(index=int(index), kind=kind, addressOctal=address,
                       listingLine=lineno)
            if "," in address:
                bank, register = address.split(",")
                row.update(bank=int(bank.lstrip("E"), 8), sRegister=int(register, 8))
                if bank.startswith("E"):
                    row["linearErasable"] = row["bank"] * 256 + row["sRegister"] - 0o1400
                else:
                    row.update(fixedBank=row["bank"], offset=row["sRegister"] - 0o2000)
            else:
                row["value"] = int(address, 8)
            if name in symbols:
                raise ValueError("Duplicate symbol in listing: " + name)
            symbols[name] = row
    if len(symbols) != 7104:
        raise ValueError(f"Unexpected symbol count {len(symbols)}; inspect original assembler output")
    return symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    source, out, reference = args.source.resolve(), args.out.resolve(), args.reference.resolve()
    before = source_hashes(source)
    out.mkdir(parents=True, exist_ok=False)
    (out / "source-before.json").write_text(json.dumps(before, indent=2, sort_keys=True) + "\n")
    for folder in ("yaYUL", "Luminary099"):
        shutil.copytree(source / folder, out / folder)
    records = []

    def run(argv, cwd, name):
        process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        (out / (name + ".stdout")).write_text(process.stdout)
        (out / (name + ".stderr")).write_text(process.stderr)
        records.append(dict(argv=argv, cwd=str(cwd), exit=process.returncode,
                            stdout=name + ".stdout", stderr=name + ".stderr"))
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        if process.returncode:
            raise RuntimeError(f"{name} exited {process.returncode}; see retained stdout/stderr")
        return process

    run(["cc", "--version"], out, "compiler-version")
    escaped_quote = chr(92) + chr(34)
    run(["make", "NATIVE=1", "cc=cc", "NVER=" + escaped_quote + "1.0" + escaped_quote],
        out / "yaYUL", "build-yayul")
    assembled = run([str(out / "yaYUL/yaYUL"), "MAIN.agc"], out / "Luminary099", "assemble")
    listing = out / "Luminary099/MAIN.agc.lst"
    listing.write_text(assembled.stdout)
    symbols = parse_symbols(assembled.stdout)
    (out / "symbols.json").write_text(json.dumps(dict(
        derivedFrom="Luminary099/MAIN.agc.lst", listingSHA256=sha(listing),
        symbolCount=len(symbols), symbols=symbols), indent=2, sort_keys=True) + "\n")
    after = source_hashes(source)
    (out / "source-after.json").write_text(json.dumps(after, indent=2, sort_keys=True) + "\n")
    original_unchanged = before == after
    copied_unchanged = all(sha(out / name) == digest for name, digest in before.items())
    rope = out / "Luminary099/MAIN.agc.bin"
    summary = dict(timeUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   platform=platform.platform(), ropeSHA256=sha(rope),
                   referenceSHA256=sha(reference),
                   byteIdentical=rope.read_bytes() == reference.read_bytes(),
                   originalSourceUnchanged=original_unchanged,
                   copiedSourceUnchanged=copied_unchanged,
                   sourceFileCount=len(before), symbolCount=len(symbols),
                   files={str(p.relative_to(out)): sha(p) for p in
                          (out / "yaYUL/yaYUL", rope, out / "Luminary099/MAIN.agc.symtab")})
    (out / "build-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if not all((summary["byteIdentical"], original_unchanged, copied_unchanged)):
        raise SystemExit("Integrity comparison failed; inspect retained evidence")


if __name__ == "__main__":
    main()
