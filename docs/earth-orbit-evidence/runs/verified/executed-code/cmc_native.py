#!/usr/bin/env python3
"""Original Comanche055 control bench over the pinned, unchanged yaAGC core.

Fresh worker processes isolate the upstream core's static globals. Inputs use
the real ringbuffer I/O interface; displays come exclusively from channel 010.
This is a cold-start computer bench, not an initialized Apollo flight vehicle.
"""
from __future__ import annotations

from copy import deepcopy
import ctypes
import datetime
import hashlib
import json
import math
import os
import select
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/earth-orbit-evidence"
SOURCE_URL = "https://github.com/virtualagc/virtualagc/tree/f577e3fd917866c59334e6cdd32504f09df76f60/Comanche055"
ROPE_SHA256 = "2ba31de9291cd10fb351a64d261bae8514a1cb75b4651bfa6a135dfa821a2d79"
CMC_ARCHIVE_SHA256 = "8828f9a0f7e529b7072690a447d63385e67ab12e768a1cd4b199a642a79eac3d"
ENGINE_ARCHIVE_SHA256 = "6385d1a7abc4dec0ade1931cde2c29ac8801a56f1a0110a24265a2dde4c3a61d"
ENGINE_HASHES_SHA256 = "61e5f57dae86e3f4c6fd0f3a79d515b9a3c6b62c187b834159393f4136859538"
PERIOD = 12 / 1_024_000
KEY_CODES = {**{str(i): i for i in range(1, 10)}, "0": 16, "VERB": 17,
             "RSET": 18, "KEY REL": 25, "+": 26, "-": 27, "ENTR": 28,
             "CLR": 30, "NOUN": 31}
SUPPORTED_KEYS = ["VERB", "NOUN", "+", "-", "0", "1", "2", "3", "4", "5",
                  "6", "7", "8", "9", "CLR", "PRO", "KEY REL", "ENTR", "RSET"]
SEGMENTS = {0: " ", 21: "0", 3: "1", 25: "2", 27: "3", 15: "4", 30: "5",
            28: "6", 19: "7", 29: "8", 31: "9"}
RELAY_ROWS = {11: ("MD1", "MD2"), 10: ("VD1", "VD2"), 9: ("ND1", "ND2"),
              8: (None, "R1D1"), 7: ("R1D2", "R1D3"), 6: ("R1D4", "R1D5"),
              5: ("R2D1", "R2D2"), 4: ("R2D3", "R2D4"), 3: ("R2D5", "R3D1"),
              2: ("R3D2", "R3D3"), 1: ("R3D4", "R3D5")}


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _locked(path, wanted):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or _digest(path) != wanted:
        raise ValueError("Pinned CMC input differs or is missing: " + str(path))


def _inputs():
    _locked(EVIDENCE / "artifacts/Comanche055.bin", ROPE_SHA256)
    _locked(EVIDENCE / "corresponding-source.tar.gz", CMC_ARCHIVE_SHA256)
    _locked(ROOT / "docs/phase6-evidence/corresponding-source.tar.gz", ENGINE_ARCHIVE_SHA256)
    _locked(ROOT / "docs/phase6-evidence/corresponding-source-hashes.json", ENGINE_HASHES_SHA256)
    observer = EVIDENCE / "experiments/cmc_observer.c"
    if observer.is_symlink() or not observer.is_file():
        raise ValueError("CMC packet observer is missing")
    if not shutil.which("cc"):
        raise ValueError("A C compiler is required for the original CMC bench")


def availability():
    """Read-only discovery; never downloads, compiles, or starts a computer."""
    error = None
    try:
        _inputs()
    except (ValueError, OSError) as exc:
        error = str(exc)
    return {"available": error is None, "unavailableReason": error,
            "software": "Comanche055", "sourceUrl": SOURCE_URL,
            "ropeSha256": ROPE_SHA256, "engineSha256": None,
            "supportedKeys": list(SUPPORTED_KEYS),
            "scope": "Original CMC cold-start DSKY control bench; no initialized flight state"}


def _extract(archive, directory, hashes):
    directory.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        found = set()
        for entry in tar.getmembers():
            if entry.name not in hashes or not entry.isfile():
                raise ValueError("Unexpected pinned archive member: " + entry.name)
            target = directory / entry.name
            if target.resolve().is_relative_to(directory.resolve()) is False:
                raise ValueError("Unsafe archive member")
            raw = tar.extractfile(entry).read()
            if hashlib.sha256(raw).hexdigest() != hashes[entry.name]:
                raise ValueError("Pinned source hash differs: " + entry.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            found.add(entry.name)
        if found != set(hashes):
            raise ValueError("Pinned archive member inventory differs")


def prepare_cmc_assets(output=None):
    """Build unchanged engine sources using retained inputs; no network needed."""
    _inputs()
    path = Path(output) if output is not None else ROOT / ".build/earth-orbit/assets" / (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    if path.is_symlink() or path.exists():
        raise ValueError("CMC asset output must be a new directory")
    path.mkdir(parents=True)
    hashes = json.loads((ROOT / "docs/phase6-evidence/corresponding-source-hashes.json").read_text())
    source = path / "source"
    _extract(ROOT / "docs/phase6-evidence/corresponding-source.tar.gz", source, hashes)
    engine = source / "yaAGC"
    library = path / "cmc-engine.so"
    observer = EVIDENCE / "experiments/cmc_observer.c"
    names = ("agc_engine.c", "wasm.c", "agc_engine_init.c", "agc_utilities.c",
             "ringbuffer_api.c", "ringbuffer.c", "rfopen.c")
    command = [shutil.which("cc"), "-shared", "-fPIC", "-O2", "-I" + str(engine),
               str(observer), *[str(engine / name) for name in names], "-lm", "-o", str(library)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    (path / "build.stdout").write_text(result.stdout)
    (path / "build.stderr").write_text(result.stderr)
    (path / "build-command.json").write_text(json.dumps({"argv": command, "exit": result.returncode}, indent=2))
    if result.returncode:
        raise RuntimeError("CMC native build failed; inspect " + str(path / "build.stderr"))
    rope = EVIDENCE / "artifacts/Comanche055.bin"
    provenance = {"ropeSha256": ROPE_SHA256, "engineSha256": _digest(library),
                  "sourceUrl": SOURCE_URL, "upstreamRevision": "f577e3fd917866c59334e6cdd32504f09df76f60",
                  "engineSourceArchiveSha256": ENGINE_ARCHIVE_SHA256,
                  "observerSha256": _digest(observer), "hostFlightMemoryWrites": False,
                  "scope": "Cold-start original CMC; no historical state checkpoint, IMU optics, spacecraft dynamics or TLI"}
    assets = {"directory": str(path.resolve()), "library": str(library.resolve()),
              "rope": str(rope.resolve()), "provenance": provenance}
    (path / "assets.json").write_text(json.dumps(assets, indent=2) + "\n")
    return assets


class DskyDecoder:
    """Decode only received relay words; unseen fields remain unavailable."""
    def __init__(self):
        self.digits = {field: "?" for row in RELAY_ROWS.values() for field in row if field}
        self.sign_bits = {str(row): None for row in (7, 6, 5, 4, 2, 1)}
        self.last_cycle = None
        self.last_word = None
        self.rows = {}
        self.channel011 = None

    def apply(self, channel, value, cycle):
        if channel == 0o11:
            self.channel011 = value
        if channel != 0o10:
            return
        self.last_cycle, self.last_word = cycle, value
        row = (value >> 11) & 15
        self.rows[str(row)] = {"value": value, "cycle": cycle}
        if row not in RELAY_ROWS:
            return
        left, right = RELAY_ROWS[row]
        if left:
            self.digits[left] = SEGMENTS.get((value >> 5) & 31, "?")
        self.digits[right] = SEGMENTS.get(value & 31, "?")
        if str(row) in self.sign_bits:
            self.sign_bits[str(row)] = bool(value & 0o2000)

    def snapshot(self):
        fields = {"PROG": "MD", "VERB": "VD", "NOUN": "ND"}
        result = {name: self.digits[prefix + "1"] + self.digits[prefix + "2"]
                  for name, prefix in fields.items()}
        result.update({"R" + str(i): "".join(self.digits[f"R{i}D{j}"] for j in range(1, 6))
                       for i in range(1, 4)})
        signs = {}
        for name, positive, negative in (("R1", "7", "6"), ("R2", "5", "4"), ("R3", "2", "1")):
            plus, minus = self.sign_bits[positive], self.sign_bits[negative]
            signs[name] = None if plus is None or minus is None else ("+" if plus else "-" if minus else " ")
        word = self.channel011
        result["signs"] = signs
        result["lamps"] = {"keyRelease": None if word is None else bool(word & 0o20),
                           "verbNounFlash": None if word is None else bool(word & 0o40),
                           "operatorError": None if word is None else bool(word & 0o100),
                           "computerActivity": None if word is None else bool(word & 0o2)}
        return result


class _NativeComputer:
    def __init__(self, assets, output):
        _locked(assets["rope"], ROPE_SHA256)
        _locked(assets["library"], assets["provenance"]["engineSha256"])
        self.assets = assets
        self.trace = (output / "trace.jsonl").open("x")
        self.decoder = DskyDecoder()
        self.lib = ctypes.CDLL(assets["library"])
        for name in ("cmc_cycle", "cmc_output_cycle"):
            getattr(self.lib, name).restype = ctypes.c_uint64
        for name in ("cmc_step", "cmc_word", "cmc_peek", "cmc_pending"):
            getattr(self.lib, name).restype = ctypes.c_uint32
        self.lib.packet_write.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
        self.lib.set_fixed.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.lib.cmc_select()
        self.lib.cpu_reset()
        raw = Path(assets["rope"]).read_bytes()
        self.rope = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        self.lib.set_fixed(self.rope)
        self.booted = False
        self.channel032 = 0o77777  # upstream CPU reset default; updates are masked packets.
        self._emit({"ev": "cold_start", "cycle": 0, "provenance": assets["provenance"]})

    def _emit(self, row):
        self.trace.write(json.dumps(row, separators=(",", ":")) + "\n")

    def _step(self, count):
        if count < 0:
            raise ValueError("Invalid CPU cycle count")
        remaining = count
        while remaining:
            size = min(remaining, 853)
            before = self.lib.cmc_cycle()
            used = self.lib.cmc_step(size)
            if used == 0xFFFFFFFF:
                raise RuntimeError("Native CMC output observer overflow")
            if self.lib.cmc_cycle() != before + size:
                raise RuntimeError("Native CPU clock differs from requested memory cycles")
            for i in range(used):
                word = self.lib.cmc_word(i)
                channel, value = word >> 16, word & 32767
                cycle = self.lib.cmc_output_cycle(i)
                self.decoder.apply(channel, value, cycle)
                self._emit({"ev": "output", "cycle": cycle, "channel": channel, "value": value})
            remaining -= size

    def advance(self, seconds):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 30:
            raise ValueError("Advance must be 0 through 30 CPU seconds")
        self._step(round(seconds / PERIOD))
        return self.snapshot()

    def _packet(self, channel, value):
        if self.lib.cmc_pending():
            raise RuntimeError("Previous CMC input has not drained")
        queued = self.lib.cmc_cycle()
        accepted = self.lib.packet_write(channel, value)
        actual = self.lib.cmc_peek()
        expected = ((channel & 0x100 != 0) << 31) | ((channel & 0xFF) << 16) | value
        if accepted <= 0 or actual != expected:
            raise RuntimeError("Native CMC input ring rejected or changed packet")
        record = {"channel": channel, "value": value, "queuedAtCycle": queued, "accepted": accepted,
                  "observedRingPacket": actual}
        # CPU input polls are cycle locked; observe consumption, not a fabricated acknowledgement.
        for _ in range(2048):
            self._step(1)
            if not self.lib.cmc_pending():
                record["consumedAtCycle"] = self.lib.cmc_cycle()
                self._emit({"ev": "input", **record})
                return record
        raise RuntimeError("CMC did not consume the queued input packet")

    def boot(self):
        if self.booted:
            raise ValueError("CMC already booted")
        self.booted = True
        return self.advance(5)

    def key(self, key):
        if not self.booted:
            raise ValueError("Boot the CMC before pressing keys")
        if key not in SUPPORTED_KEYS:
            raise ValueError("Unsupported DSKY key")
        at = self.lib.cmc_cycle()
        packets = []
        if key == "PRO":
            # Original PRO is channel032 bit14, active low, sampled by T4RUPT.
            # A mask packet preserves the unrelated spacecraft discretes.
            packets.append(self._packet(0o432, 0o20000))
            press = self._packet(0o32, 0)
            packets.append(press)
            self.advance(0.2)
            packets.append(self._packet(0o32, 0o20000))
            self.advance(0.2)
            code, channel = 0, 0o32
        else:
            code, channel = KEY_CODES[key], 0o15
            press = self._packet(channel, code)
            packets.append(press)
            self.advance(0.4)
        ack = {"key": key, "code": code, "channel": channel, "queuedAtCycle": at,
               "consumedAtCycle": press["consumedAtCycle"], "afterCycle": self.lib.cmc_cycle(),
               "accepted": press["accepted"], "packets": packets}
        self._emit({"ev": "key", **ack, "dsky": self.decoder.snapshot()})
        self.trace.flush()
        return {"computer": self.snapshot(), "ackpacket": ack}

    def snapshot(self):
        cycle = self.lib.cmc_cycle()
        return {"software": "Comanche055", "mode": "LIVE AGC EXECUTION", "cycle": cycle,
                "cpuSeconds": cycle * PERIOD, "dsky": self.decoder.snapshot(),
                "dskySource": {"channel": 0o10, "cycle": self.decoder.last_cycle,
                               "relayWord": self.decoder.last_word, "rows": deepcopy(self.decoder.rows)},
                "provenance": deepcopy(self.assets["provenance"]),
                "flightState": None, "historicalCheckpointLoaded": False}


class CmcProcess:
    """Own one fresh native worker; calls are serialized by the caller."""
    def __init__(self, assets, output=None):
        self.assets = assets
        self.output = Path(output) if output is not None else ROOT / ".build/earth-orbit/sessions" / (
            datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        if self.output.is_symlink() or self.output.exists():
            raise ValueError("CMC session output must be a new directory")
        self.output.mkdir(parents=True)
        spec = self.output / "assets.json"
        spec.write_text(json.dumps(assets))
        self.stderr = (self.output / "worker.stderr").open("x")
        self.proc = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(spec)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                                     bufsize=0, cwd=ROOT)
        self._response_buffer = b""
        self._lock = threading.Lock()
        self.closed = False

    def _request(self, action, **data):
        if self.closed or self.proc.poll() is not None:
            raise RuntimeError("CMC worker is closed; inspect " + str(self.output / "worker.stderr"))
        with self._lock:
            self.proc.stdin.write((json.dumps({"action": action, **data}) + "\n").encode())
            self.proc.stdin.flush()
            deadline = time.monotonic() + 10
            while b"\n" not in self._response_buffer:
                remaining = max(0, deadline - time.monotonic())
                readable, _, _ = select.select([self.proc.stdout], [], [], remaining)
                if not readable:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                    raise RuntimeError("CMC worker response timed out; the worker was terminated")
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError("CMC worker stopped; inspect " + str(self.output / "worker.stderr"))
                self._response_buffer += chunk
                if len(self._response_buffer) > 524288:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                    raise RuntimeError("CMC worker response exceeded its size limit")
            line, self._response_buffer = self._response_buffer.split(b"\n", 1)
            response = json.loads(line)
            if not response.get("ok"):
                raise ValueError(response.get("error", "CMC request failed"))
            return response["result"]

    def boot(self):
        return self._request("boot")

    def key(self, key):
        return self._request("key", key=key)

    def advance(self, seconds):
        return self._request("advance", seconds=seconds)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if not self.proc.stdin.closed:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
        if self.proc.poll() is None:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        self.proc.stdout.close()
        self.stderr.close()


def _worker(spec):
    computer = _NativeComputer(json.loads(spec.read_text()), spec.parent)
    # Native upstream cpu_reset makes stdin nonblocking for its optional CLI.
    # This worker owns stdin as a line protocol, so restore the host FD mode.
    os.set_blocking(sys.stdin.fileno(), True)
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                action = request.get("action")
                if action == "boot":
                    result = computer.boot()
                elif action == "key":
                    result = computer.key(request.get("key"))
                elif action == "advance":
                    result = computer.advance(request.get("seconds"))
                else:
                    raise ValueError("Unsupported CMC worker action")
                response = {"ok": True, "result": result}
            except (ValueError, RuntimeError, TypeError) as exc:
                response = {"ok": False, "error": str(exc)}
            print(json.dumps(response, separators=(",", ":")), flush=True)
    finally:
        computer.trace.close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        _worker(Path(sys.argv[2]))
    else:
        raise SystemExit("This module is an internal original-CMC worker; start the application normally.")
