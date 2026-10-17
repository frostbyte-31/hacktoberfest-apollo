#!/usr/bin/env python3
"""Verify pinned upstream inputs and assemble original Luminary099 without Nix.

Example (network): python3 docs/phase9-evidence/prepare.py --cache .build/phase9/dependencies
Example (offline): append --archive /path/to/verified-upstream.tar.gz

Every invocation creates a unique setup record. Existing source files are
verified against the hash-checked archive, never repaired or overwritten.
Compiler and assembler failures retain their actual stdout/stderr.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = "f577e3fd917866c59334e6cdd32504f09df76f60"
URL = "https://codeload.github.com/virtualagc/virtualagc/tar.gz/" + REVISION
ARCHIVE_SHA = "1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267"
ROPE_SHA = "1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e"
PREFIX = "virtualagc-" + REVISION
DIRECTORIES = {"yaAGC", "yaYUL", "Luminary099"}
NOTICES = {"COPYING", "LICENSE.txt", "AgcHtmlNotice.txt"}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_archive(cache, provided, run):
    archive = provided.resolve() if provided else cache / (PREFIX + ".tar.gz")
    record = dict(url=URL, revision=REVISION, expectedSHA256=ARCHIVE_SHA,
                  archive=str(archive), suppliedOffline=bool(provided))
    if not archive.exists():
        if provided:
            raise FileNotFoundError("Supplied archive does not exist: " + str(archive))
        temporary = cache / (PREFIX + ".download-" + uuid.uuid4().hex)
        record["downloadTemporary"] = str(temporary)
        save(run / "archive.json", record)
        request = urllib.request.Request(URL, headers={"User-Agent": "Apollo-Luminary099-reproducibility"})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as output:
            record["responseURL"] = response.url
            shutil.copyfileobj(response, output, 1024 * 1024)
        record["downloadSHA256"] = sha(temporary)
        if record["downloadSHA256"] != ARCHIVE_SHA:
            save(run / "archive.json", record)
            raise ValueError("Downloaded archive checksum mismatch; actual bytes retained at " + str(temporary))
        # Exclusive publication avoids overwriting even an unverified concurrent file.
        with temporary.open("rb") as source, archive.open("xb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        temporary.unlink()
    record.update(bytes=archive.stat().st_size, actualSHA256=sha(archive))
    record["verified"] = record["actualSHA256"] == ARCHIVE_SHA
    save(run / "archive.json", record)
    if not record["verified"]:
        raise ValueError("Pinned archive checksum mismatch; no extraction attempted")
    return archive, record


def selected_members(archive):
    """Return safe regular input members only, after caller verifies archive hash."""
    members = {}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != PREFIX:
            raise ValueError("Unsafe archive member: " + member.name)
        if len(path.parts) < 2:
            continue
        relative = PurePosixPath(*path.parts[1:])
        if relative.parts[0] not in DIRECTORIES and str(relative) not in NOTICES:
            continue
        if member.isdir():
            continue
        if not member.isfile() or member.issym() or member.islnk():
            raise ValueError("Unsupported selected archive member: " + member.name)
        key = relative.as_posix()
        if key in members:
            raise ValueError("Duplicate selected archive member: " + key)
        members[key] = member
    if not all(any(name.startswith(folder + "/") for name in members) for folder in DIRECTORIES):
        raise ValueError("Pinned archive lacks required source directory")
    if not NOTICES.issubset(members):
        raise ValueError("Pinned archive lacks required license notices")
    return members


def verify_or_extract(archive_path, cache, run):
    source = cache / "source"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = selected_members(archive)
        expected = {}
        for name, member in members.items():
            with archive.extractfile(member) as stream:
                expected[name] = hashlib.sha256(stream.read()).hexdigest()
        save(run / "source-archive-hashes.json", expected)
        reuse = source.exists()
        if source.is_symlink():
            raise ValueError("Cached source directory must not be a symlink")
        if not reuse:
            temporary = cache / ("source-extraction-" + uuid.uuid4().hex)
            temporary.mkdir(exist_ok=False)
            for name, member in members.items():
                target = temporary / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output)
            temporary.rename(source)
    actual = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Cached source contains a symlink: " + str(path))
        if path.is_file():
            actual[path.relative_to(source).as_posix()] = sha(path)
    mismatches = {name: dict(expected=expected.get(name), actual=actual.get(name))
                  for name in sorted(set(expected) | set(actual)) if expected.get(name) != actual.get(name)}
    save(run / "source-verification.json", dict(reused=reuse, fileCount=len(expected),
                                               verified=not mismatches, mismatches=mismatches,
                                               source=str(source)))
    if mismatches:
        raise ValueError("Cached source differs from pinned archive; files left untouched")
    return source, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".build/phase9/dependencies")
    parser.add_argument("--archive", type=Path, help="Offline pinned tar.gz; checksum is still mandatory")
    args = parser.parse_args()
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    run = cache / "setups" / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    save(run / "environment.json", dict(timeUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                        python=sys.version, executable=sys.executable,
                                        platform=platform.platform(), machine=platform.machine(),
                                        cwd=str(Path.cwd()), argv=sys.argv,
                                        tools={name: shutil.which(name) for name in ("cc", "make", "python3")},
                                        scripts={p.name: sha(p) for p in (Path(__file__).resolve(), HERE / "rebuild_source.py")}))
    shutil.copyfile(Path(__file__).resolve(), run / "executed-prepare.py")
    shutil.copyfile(HERE / "rebuild_source.py", run / "executed-rebuild_source.py")
    try:
        archive, archive_record = verified_archive(cache, args.archive, run)
        source, input_hashes = verify_or_extract(archive, cache, run)
        reference = ROOT / "docs/phase1-evidence/artifacts/MAIN.agc.bin"
        if sha(reference) != ROPE_SHA:
            raise ValueError("Retained Phase 1 rope integrity mismatch")
        assembly = cache / ("assembly-" + uuid.uuid4().hex)
        command = [sys.executable, str(HERE / "rebuild_source.py"), "--source", str(source),
                   "--out", str(assembly), "--reference", str(reference)]
        with (run / "build.stdout").open("w") as stdout, (run / "build.stderr").open("w") as stderr:
            process = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        save(run / "commands.json", [dict(argv=command, cwd=str(ROOT), exit=process.returncode)])
        if process.returncode:
            raise RuntimeError("Assembly failed; output preserved at " + str(assembly))
        result = json.loads((assembly / "build-summary.json").read_text())
        if not all(result[key] for key in ("byteIdentical", "originalSourceUnchanged", "copiedSourceUnchanged")) or result["ropeSHA256"] != ROPE_SHA:
            raise ValueError("Assembly integrity check failed")
        # Verify the emulator inputs too, after assembly, against the archive.
        changed = {name: sha(source / name) for name, digest in input_hashes.items()
                   if sha(source / name) != digest}
        save(run / "source-after-build.json", dict(verified=not changed, changed=changed,
                                                   checkedFiles=len(input_hashes)))
        if changed:
            raise ValueError("Source changed during assembly; no setup published")
        setup = dict(verified=True, sourceRevision=REVISION, archiveSHA256=ARCHIVE_SHA,
                     archive=str(archive), source=str(source), assembly=str(assembly),
                     symbols=str(assembly / "symbols.json"),
                     listing=str(assembly / "Luminary099/MAIN.agc.lst"),
                     symtab=str(assembly / "Luminary099/MAIN.agc.symtab"),
                     rope=str(assembly / "Luminary099/MAIN.agc.bin"), ropeSHA256=ROPE_SHA,
                     sourceFileCount=len(input_hashes), setupFile=str(run / "setup.json"),
                     provenance=str(run), licensing="Original Luminary source is public domain; Virtual AGC tools carry GPL notices. See source/COPYING, LICENSE.txt and individual source headers.")
        save(run / "setup.json", setup)
        print(json.dumps(setup, indent=2, sort_keys=True))
    except Exception as error:
        save(run / "failure.json", dict(errorType=type(error).__name__, message=str(error),
                                         evidence=str(run)))
        print("Setup failed; retained diagnostics: " + str(run), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
