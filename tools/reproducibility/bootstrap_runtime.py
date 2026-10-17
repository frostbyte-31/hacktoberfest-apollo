#!/usr/bin/env python3
"""Build a source-locked Tcl in an isolated cache; never install system packages."""
from pathlib import Path
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
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCK_PATH = HERE / "runtime-lock.json"
DEFAULT_CACHE = ROOT / ".build/reproducibility"


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def tree_digest(path):
    """Include names and link targets, so additions and replacements also fail."""
    records = []
    for item in sorted(Path(path).rglob("*")):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            records.append([relative, "symlink", os.readlink(item)])
        elif item.is_file():
            records.append([relative, "file", digest(item)])
        elif not item.is_dir():
            raise RuntimeError(f"Unexpected special file: {item}")
    return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()


def clean_environment():
    env = dict(os.environ)
    for name in ("TCL_LIBRARY", "TCLLIBPATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH",
                 "DYLD_FALLBACK_LIBRARY_PATH", "CONFIG_SITE", "MAKEFLAGS", "MFLAGS"):
        env.pop(name, None)
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    return env


def smoke_test(executable, version):
    # Tcl exits zero for some stdin script errors: an explicit marker and exact
    # output also establish that all commands, including the required math, ran.
    script = ("if {[info patchlevel] ne {" + version + "}} {exit 2}\n"
              "if {[expr {hypot(3.0, 4.0)}] != 5.0} {exit 3}\n"
              "puts {[info patchlevel]}\n"
              "puts [info patchlevel]\nputs {APOLLO_TCL_SMOKE_OK}\n")
    result = subprocess.run([str(executable)], input=script, text=True,
                            capture_output=True, timeout=15, env=clean_environment())
    expected = f"[info patchlevel]\n{version}\nAPOLLO_TCL_SMOKE_OK\n"
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise RuntimeError(f"Tcl {version} runtime smoke failed: {result!r}")
    return {"version": version, "hypot_3_4": 5.0, "status": "VERIFIED"}


def validate_runtime(manifest_path):
    """Fail closed on changed lock, source, installed files or Tcl behavior."""
    manifest_path = Path(manifest_path).resolve()
    data = json.loads(manifest_path.read_text())
    lock = json.loads(LOCK_PATH.read_text())["tcl"]
    if data.get("schema") != 1 or data.get("lock_sha256") != digest(LOCK_PATH):
        raise RuntimeError("Runtime manifest does not match the current runtime lock")
    if data.get("version") != lock["version"] or data.get("source_sha256") != lock["sha256"]:
        raise RuntimeError("Runtime manifest does not match pinned Tcl")
    for name in ("archive_path", "source_path", "runtime_path", "executable"):
        if not Path(data[name]).is_absolute():
            raise RuntimeError(f"Runtime manifest requires absolute {name}")
    if digest(data["archive_path"]) != lock["sha256"]:
        raise RuntimeError("Cached Tcl archive checksum mismatch")
    if tree_digest(Path(data["source_path"])) != data["source_tree_sha256"]:
        raise RuntimeError("Extracted Tcl source changed after the recorded build")
    runtime = Path(data["runtime_path"])
    executable = runtime / lock["executable"]
    if str(executable) != data["executable"] or not executable.is_file():
        raise RuntimeError("Runtime executable is missing or outside the locked install path")
    if tree_digest(runtime) != data["runtime_tree_sha256"]:
        raise RuntimeError("Installed Tcl runtime changed after the recorded build")
    if digest(executable) != data["executable_sha256"]:
        raise RuntimeError("Installed Tcl executable checksum mismatch")
    smoke_test(executable, lock["version"])
    return data


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def extract_source_archive(archive_path, destination):
    """The locked release contains only files/directories; reject links outright.

    Validate every member before extracting any, including on Python versions
    predating tarfile's extraction filters. The destination is newly created.
    """
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts or "\\" in member.name:
                raise RuntimeError(f"Unsafe Tcl archive member: {member.name}")
            if not member.isfile() and not member.isdir():
                raise RuntimeError(f"Unsupported Tcl archive link or special file: {member.name}")
        tar.extractall(destination)


def validate_cache(cache, root=ROOT):
    """Keep dependency outputs in .build or external scratch, before any write.

    Resolve the requested cache, but keep the allowed .build boundary lexical:
    resolving both would authorize a .build symlink into retained evidence.
    """
    root, cache = Path(root).resolve(), Path(cache).resolve()
    if cache == root or root in cache.parents:
        build = root / ".build"
        if cache == build or build not in cache.parents:
            raise RuntimeError("Use a .build subdirectory or external scratch; retained evidence is read-only")
    return cache


def bootstrap(cache, archive=None, cc="cc", jobs=2):
    cache = validate_cache(cache)
    lock = json.loads(LOCK_PATH.read_text())["tcl"]
    manifest = cache / "runtime-manifest.json"
    if manifest.exists():
        return validate_runtime(manifest)
    runtime = cache / "runtime"
    if runtime.exists():
        raise RuntimeError(f"Unmanifested runtime already exists: {runtime}; select a fresh --cache-dir")
    compiler = shutil.which(cc)
    make = shutil.which("make")
    if not compiler or not make:
        raise RuntimeError("A C compiler and make are required; no system tools will be installed")
    source_archive = Path(archive).resolve() if archive else cache / "downloads" / lock["archive"]
    source_archive.parent.mkdir(parents=True, exist_ok=True)
    record = cache / "build-records" / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    record.mkdir(parents=True)
    commands = []
    env = clean_environment()
    env.update(CC=compiler, CFLAGS=lock["cflags"], CPPFLAGS="", LDFLAGS="", CXXFLAGS="")

    def run(argv, label, cwd=ROOT, timeout=900):
        command = {"argv": [str(arg) for arg in argv], "cwd": str(cwd),
                   "start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            with (record / f"{label}.stdout").open("w") as stdout, (record / f"{label}.stderr").open("w") as stderr:
                result = subprocess.run(command["argv"], cwd=cwd, stdout=stdout, stderr=stderr,
                                        timeout=timeout, env=env)
            command["exit"] = result.returncode
        except subprocess.TimeoutExpired:
            command["exit"] = "TIMEOUT"
        command["end_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        commands.append(command)
        write_json(record / "commands.json", commands)
        if command["exit"] != 0:
            raise RuntimeError(f"{label} failed ({command['exit']}); see {record}")

    try:
        if not source_archive.exists():
            if archive:
                raise RuntimeError(f"Requested offline source archive is missing: {source_archive}")
            curl = shutil.which("curl")
            if not curl:
                raise RuntimeError("curl is required to download Tcl; or supply --archive PATH")
            partial = source_archive.with_suffix(source_archive.suffix + ".partial")
            run([curl, "--fail", "--location", "--retry", "2", "--connect-timeout", "30",
                 "--max-time", "300", "--proto", "=https", "--proto-redir", "=https",
                 "--output", partial, lock["url"]], "download", timeout=330)
            if digest(partial) != lock["sha256"]:
                raise RuntimeError("Downloaded Tcl archive checksum mismatch; archive was not extracted")
            partial.rename(source_archive)
        if digest(source_archive) != lock["sha256"]:
            raise RuntimeError("Tcl source archive checksum mismatch; archive was not extracted")
        source_parent = cache / "sources" / record.name
        source_parent.mkdir(parents=True)
        extract_source_archive(source_archive, source_parent)
        source = source_parent / lock["source_directory"]
        if not (source / "unix/configure").is_file():
            raise RuntimeError("Pinned archive did not contain the expected Tcl configure script")
        source_hash = tree_digest(source)
        build = cache / "build" / record.name
        build.mkdir(parents=True)
        run([compiler, "--version"], "compiler_version")
        run([make, "--version"], "make_version")
        run([str(source / "unix/configure"), "--prefix=" + str(runtime),
             *lock["configure_arguments"]], "configure", cwd=build)
        run([make, f"-j{jobs}"], "make", cwd=build)
        run([make, "install"], "install", cwd=build)
        executable = runtime / lock["executable"]
        smoke = smoke_test(executable, lock["version"])
        if tree_digest(source) != source_hash:
            raise RuntimeError("Tcl build changed extracted sources; inspect build before accepting")
        data = {"schema": 1, "version": lock["version"], "executable": str(executable),
                "executable_sha256": digest(executable), "runtime_path": str(runtime),
                "runtime_tree_sha256": tree_digest(runtime), "source_path": str(source),
                "source_tree_sha256": source_hash, "archive_path": str(source_archive),
                "source_sha256": lock["sha256"], "lock_sha256": digest(LOCK_PATH),
                "source_url": lock["url"], "build_record": str(record),
                "configure_arguments": lock["configure_arguments"], "cflags": lock["cflags"],
                "compiler": compiler, "compiler_version": (record / "compiler_version.stdout").read_text(),
                "make": make, "make_version": (record / "make_version.stdout").read_text(),
                "python_version": sys.version, "platform": platform.platform(),
                "machine": platform.machine(), "smoke_test": smoke,
                "toolchain_scope": json.loads(LOCK_PATH.read_text())["scope"]}
        write_json(manifest, data)
        return validate_runtime(manifest)
    except Exception as error:
        write_json(record / "failure.json", {"status": "FAILED", "error": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--archive", type=Path, help="Use an already downloaded exact archive, without network access")
    parser.add_argument("--cc", default="cc", help="Host compiler to record; default: cc")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--describe-json", action="store_true", help="Validate an existing runtime and print its manifest; do not build")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        if args.describe_json:
            data = validate_runtime(args.cache_dir / "runtime-manifest.json")
        else:
            data = bootstrap(args.cache_dir, args.archive, args.cc, args.jobs)
        print(json.dumps(data, indent=2))
    except (OSError, ValueError, RuntimeError, tarfile.TarError) as error:
        parser.exit(1, f"Runtime bootstrap failed: {error}\n")


if __name__ == "__main__":
    main()
