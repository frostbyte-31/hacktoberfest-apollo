#!/usr/bin/env python3
"""GPL-2.0-or-later. Live orchestration of the retained native Phase 7 fixture.

This module owns no guidance or physics implementation. It uses the unchanged
Phase 7 engine observer and Tcl model, and accepts only the source-verified
bounded RHC input contract. A session must be owned by one calling thread.
"""
from collections import deque
import datetime
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PHASE7 = ROOT / "docs/phase7-evidence"
READY_CYCLE = 2_200_000
END_CYCLE = 3_200_000
MAX_PULSE_CYCLES = 85_333  # <1 simulated second; integer CPU-call time.
MAX_HOST_QUEUE = 512
_ACTIVE = threading.Lock()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Import through the retained integration module's own provenance loaders.
INTEGRATION = _load("live_retained_phase7_integration", PHASE7 / "integration/run_validation.py")
PERIOD, CHUNK = INTEGRATION.PERIOD, INTEGRATION.CHUNK
digest, write_json = INTEGRATION.digest, INTEGRATION.write_json


def new_output(kind, proposed=None):
    path = Path(proposed) if proposed is not None else ROOT / ".build/live" / kind / (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    return INTEGRATION.M3.destination(path)


def validate_contract():
    """Reject altered retained sources instead of bypassing their integrity checks."""
    old = INTEGRATION.verify_prior()
    if not old["ok"]:
        raise ValueError("Earlier phase evidence/source integrity check failed")
    manifest = json.loads((PHASE7 / "package-manifest.json").read_text())
    checked = 0
    for name, expected in manifest["files"].items():
        if not name.startswith("docs/phase7-evidence/"):
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected["sha256"]:
            raise ValueError("Retained Phase 7 evidence changed: " + name)
        checked += 1
    mapping = json.loads((PHASE7 / "source/mappings.json").read_text())
    if (mapping["rhc"]["yaw"]["port_decimal"], mapping["rhc"]["pitch"]["port_decimal"],
            mapping["words"]["neutral"], mapping["signed_20"]["minus_ones_complement"]) != (119, 118, 28671, 32747):
        raise ValueError("Retained RHC contract changed")
    return {"prior_files_checked": old["files_checked"], "phase7_files_checked": checked,
            "phase7_manifest_sha256": digest(PHASE7 / "package-manifest.json")}


def prepare_assets(output=None, runtime_manifest=None, cc="cc"):
    """Extract verified minimal source and compile unchanged native semantics.

    Uses the installed, source-locked Tcl runtime. Install it with ``make runtime``
    if unavailable; no system Tcl or alternate emulator is silently substituted.
    Every build has a new append-only output directory.
    """
    integrity = validate_contract()
    out = new_output("assets", output)
    out.mkdir(parents=True)
    manifest_path = Path(runtime_manifest or ROOT / ".build/reproducibility/runtime-manifest.json").resolve()
    runtime_loader = _load("live_locked_runtime", ROOT / "tools/reproducibility/bootstrap_runtime.py")
    runtime = runtime_loader.validate_runtime(manifest_path)
    source = out / "source"
    INTEGRATION.M3.retained.extract_source(ROOT / "docs/phase6-evidence/corresponding-source.tar.gz", source,
        json.loads((ROOT / "docs/phase6-evidence/corresponding-source-hashes.json").read_text()))
    commands = []
    INTEGRATION.run_command(INTEGRATION.build(source, out, cc), "build", out, commands)
    physics = _load("live_locked_physics_overlay", PHASE7 / "physics/apply_physics.py")
    overlay = out / "physics-overlay.tcl"
    audit = physics.apply_physics(source, overlay)
    write_json(out / "physics-audit.json", audit)
    # Reuse the exact retained model wire server, not a second physics entry point.
    server = out / "server.tcl"
    shutil.copyfile(PHASE7 / "runs/2026-10-17-verified-check/validation/integration/server.tcl", server)
    paths = [Path(__file__), PHASE7 / "integration/run_validation.py", PHASE7 / "integration/inspect_axes.c",
             PHASE7 / "physics/apply_physics.py", PHASE7 / "physics/orientation.tcl",
             ROOT / "docs/phase1-evidence/artifacts/MAIN.agc.bin", server, overlay, out / "engine.so"]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    metadata = {"repository_revision": revision, "upstream_revision": "f577e3fd917866c59334e6cdd32504f09df76f60",
        "integrity": integrity, "runtime_manifest_sha256": digest(manifest_path), "runtime": runtime,
        "platform": platform.platform(), "python": sys.version,
        "inputs_sha256": {str(path): digest(path) for path in paths},
        "scope": "Live synthetic attitude fixture only; original Luminary and emulator unchanged; no descent"}
    write_json(out / "provenance.json", metadata)
    return {"directory": str(out), "source": str(source), "library": str(out / "engine.so"),
            "overlay": str(overlay), "server": str(server), "tcl": runtime["executable"],
            "provenance": metadata}


def rhc_word(yaw, pitch):
    """Verified active-low direction/out-of-detent input, not an AGC output."""
    for value in (yaw, pitch):
        if type(value) is not int or value not in (-1, 0, 1):
            raise ValueError("Yaw and pitch must be integer -1, 0, or +1")
    if not yaw and not pitch:
        return 28671
    return 12287 - ({-1: 8, 0: 0, 1: 4}[yaw] + {-1: 2, 0: 0, 1: 1}[pitch])


def validate_sensor_mode(axis, code, model):
    """Reject the inherited body-rate approximation outside its proven domain."""
    if code in (1, 3) and abs(model["gimbal_rates_deg_s"][axis]) > 4 + 1e-9:
        raise ValueError("Unsupported slow CDU mode at actual gimbal rate >4 deg/s")


class NativeSession:
    """One bounded native AGC+external vehicle session; call from one owner thread."""
    def __init__(self, assets, output=None):
        self.assets = assets
        self.output = new_output("sessions", output)
        self.status = "created"
        self.ready = False
        self.closed = False
        self._locked = False
        self._owner = threading.get_ident()
        self.events = deque(maxlen=100)
        self.error = None
        self.tick = self.plant_cursor = 0
        self.next_coupling = CHUNK
        self.model = None
        self.jets = {5: 0, 6: 0}
        self.actual_output_jets = {5: 0, 6: 0}
        self.channel013_latch = 0
        self.freeze_cycle = None
        self.zero = 0
        self.queues = [deque() for _ in range(3)]
        self.inflight = [None] * 3
        self.last_delivery = [None] * 3
        self.counts = [{key: 0 for key in ("generated", "delivered", "consumed", "enqueued", "applied")} for _ in range(3)]
        self.peak_host = [0] * 3
        self.serial = 0
        self.control = {"yaw": 0, "pitch": 0, "neutral_at": None}
        self.schedule = [row for row in INTEGRATION.make_schedule("yaw") if row[0] < READY_CYCLE]
        self.schedule_index = 0
        self.proc = self.log = self.stderr = self.engine = None

    def _assert_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("Native session must be called by its single owner thread")

    def _emit(self, event, category, **values):
        row = {"ev": event, "category": category, **values}
        self.log.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
        if event in ("pilot_command", "neutral", "startup_checkpoint", "freeze", "error", "summary"):
            self.events.append(row)
            self.log.flush()

    def start(self):
        self._assert_owner()
        if self.status != "created":
            raise ValueError("Session already started")
        if not _ACTIVE.acquire(blocking=False):
            raise RuntimeError("One native session is already active in this process")
        self._locked = True
        try:
            # CDLL globals are intentionally serialized; each fresh session resets
            # the original native CPU and receives its own fresh Tcl process.
            for name in ("library", "overlay", "server"):
                path = Path(self.assets[name])
                wanted = self.assets["provenance"]["inputs_sha256"].get(str(path))
                if not wanted or digest(path) != wanted:
                    raise ValueError("Prepared asset changed: " + name)
            self.output.mkdir(parents=True)
            self.log = (self.output / "trace.jsonl").open("x")
            self.stderr = (self.output / "model.stderr").open("x")
            # cpu_reset resets the CPU, not every retained bridge static/FIFO.
            # A new loader pathname gives the unchanged C module fresh globals.
            # Never synthesize a wider reset by modifying emulator state.
            library = self.output / "engine.so"
            shutil.copyfile(self.assets["library"], library)
            if digest(library) != digest(Path(self.assets["library"])):
                raise ValueError("Fresh native library copy integrity failed")
            self.engine = INTEGRATION.Engine(library)
            self.proc = subprocess.Popen([self.assets["tcl"], self.assets["server"], self.assets["source"], self.assets["overlay"]],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
            config = {"ready_cycle": READY_CYCLE, "end_cycle": END_CYCLE, "max_pulse_cycles": MAX_PULSE_CYCLES,
                "cycle_seconds": PERIOD, "max_coupling_calls": CHUNK, "startup_schedule": self.schedule,
                "initial_conditions": "Fresh CPU, fresh model, zero physical rates, identity quaternion, genuine delayed V36/V37/V77 fixture",
                "classification": "Simulated vehicle and sensors, authentic Luminary commands; not historical flight telemetry",
                "alignment": "Assumed ideal identity aligned fixture; not authenticated mission padload or physical calibration",
                "scope": "Yaw/pitch RHC only; no throttle, PIPA or powered descent",
                "provenance": self.assets["provenance"]}
            write_json(self.output / "configuration.json", config)
            self._emit("initial", "diagnostic", **config)
            self.status = "starting"
            self.advance_to(READY_CYCLE)
            self._check_ready()
            self.ready, self.status = True, "running"
            self._emit("startup_checkpoint", "agc_diagnostic_readback", cycle=self.tick,
                registers=self.engine.execution(), state=self.engine.snapshot(), verified=True)
            return self.frame()
        except BaseException as error:
            self.error = str(error)
            self._fail(error)
            raise

    def _check_ready(self):
        values = self.engine.execution()
        if values["modreg"] or any(values["failreg"]) or (values["imodes30"] | values["imodes33"]) & 0o40 or not values["dapbools"] & 4:
            raise ValueError("Original clean IMU/DAP readiness is not established")

    def _input(self, channel, value, origin):
        row = self.engine.write(channel, value)
        self._emit("input", "authentic_external_input", cycle=self.tick, origin=origin, **row)
        if row["accepted"] <= 0:
            raise ValueError("Native input ring rejected authentic input")

    def _set_control(self, yaw, pitch, neutral_at, origin):
        word = rhc_word(yaw, pitch)
        encode = lambda value: 20 if value > 0 else 32747 if value < 0 else 0
        # Normal packets are contiguous before the next engine call; only the
        # unchanged native channel013-gated original RHC copy consumes them.
        for channel, value in ((0o167, encode(yaw)), (0o166, encode(pitch)), (0o31, word)):
            self._input(channel, value, origin)
        self.control = {"yaw": yaw, "pitch": pitch, "neutral_at": neutral_at}
        self._emit("pilot_command" if yaw or pitch else "neutral", "authentic_external_input", cycle=self.tick,
            yaw=yaw, pitch=pitch, channel031=word, yaw_port0167=encode(yaw), pitch_port0166=encode(pitch),
            neutral_at=neutral_at, origin=origin)

    def command(self, yaw=0, pitch=0, duration_cycles=MAX_PULSE_CYCLES):
        self._assert_owner()
        rhc_word(yaw, pitch)
        if type(duration_cycles) is not int or not (1 <= duration_cycles <= MAX_PULSE_CYCLES or duration_cycles == 0 and not yaw and not pitch):
            raise ValueError("Pulse duration must be 1..85333 native CPU calls")
        if self.closed or self.status != "running" or not self.ready:
            raise ValueError("Live session is not ready")
        self._check_ready()
        if self.tick >= END_CYCLE:
            raise ValueError("Live experiment reached its bounded horizon")
        deadline = min(END_CYCLE, self.tick + duration_cycles) if yaw or pitch else None
        self._set_control(yaw, pitch, deadline, "browser pilot")
        return {"cycle": self.tick, **self.control, "duration_cycles": 0 if deadline is None else deadline - self.tick}

    def _integrate(self, start, stop):
        if stop <= start:
            return
        self.proc.stdin.write(f"{(stop-start)*PERIOD:.17g} {self.jets[5]} {self.jets[6]} {self.zero}\n")
        self.proc.stdin.flush()
        response = self.proc.stdout.readline()
        if not response:
            raise ValueError("Retained vehicle process stopped unexpectedly")
        self.model, packets = INTEGRATION.parse_response(response)
        self._emit("plant", "simulated_vehicle", cycle=stop, interval_start=start,
            jets=[self.jets[5], self.jets[6]], zero=self.zero, **self.model)
        self._emit("actuator_decode", "decoded_agc_actuator", cycle=stop,
            channel005=self.jets[5], channel006=self.jets[6], active_thrusters=INTEGRATION.decode_jets(self.jets[5], self.jets[6]))
        self._emit("execution_sample", "agc_diagnostic_readback", cycle=self.tick, registers=self.engine.execution())
        for axis, code in packets:
            try:
                validate_sensor_mode(axis, code, self.model)
            except ValueError:
                self._emit("unsupported_sensor_mode", "diagnostic", cycle=stop,
                    axis=axis, code=code, actual_gimbal_rate_deg_s=self.model["gimbal_rates_deg_s"][axis],
                    meaning="Original model selector uses body rate; reject unsupported slow operation without substituting a mode")
                raise
            self.serial += 1
            request = {"id": self.serial, "axis": axis, "counter": 0o32+axis, "code": code, "origin": stop, "available": self.tick}
            self.counts[axis]["generated"] += 1
            self.queues[axis].append(request)
            self.peak_host[axis] = max(self.peak_host[axis], len(self.queues[axis]))
            self._emit("generated", "simulated_sensor", **request)
            if len(self.queues[axis]) > MAX_HOST_QUEUE:
                raise ValueError("Sensor host queue exceeded bounded capacity")

    def _step(self, target, frozen=False):
        while not frozen and self.schedule_index < len(self.schedule) and self.schedule[self.schedule_index][0] == self.tick:
            _, channel, value = self.schedule[self.schedule_index]
            self.schedule_index += 1
            self._input(channel, value, "retained startup key sequence")
        if not frozen and self.control["neutral_at"] is not None and self.tick >= self.control["neutral_at"]:
            self._set_control(0, 0, None, "automatic bounded pulse neutral")
        for axis in range(3):
            if self.queues[axis] and self.inflight[axis] is None:
                request = self.queues[axis][0]
                spacing = 14 if request["code"] in (17, 19) else 214
                if self.last_delivery[axis] is None or self.tick-self.last_delivery[axis] >= spacing:
                    request = self.queues[axis].popleft()
                    row = self.engine.write(128 | request["counter"], request["code"], request)
                    self._emit("delivery", "diagnostic_sensor_transport", cycle=self.tick, request=request, wire=row, tail=frozen)
                    if row["accepted"] <= 0:
                        raise ValueError("Native sensor ring rejected a paced operation")
                    self.inflight[axis] = {**request, "delivery": self.tick, "wire_id": row["wire_id"], "consumed": False}
                    self.last_delivery[axis] = self.tick
                    self.counts[axis]["delivered"] += 1
        state = self.engine.snapshot()
        busy = state["incoming"] or any(self.inflight)
        step = min(1 if busy else CHUNK, target-self.tick)
        if not frozen:
            step = min(step, self.next_coupling-self.tick)
            if self.schedule_index < len(self.schedule):
                step = min(step, self.schedule[self.schedule_index][0]-self.tick)
            if self.control["neutral_at"] is not None:
                step = min(step, self.control["neutral_at"]-self.tick)
        for axis in range(3):
            if self.queues[axis] and self.inflight[axis] is None and self.last_delivery[axis] is not None:
                spacing = 14 if self.queues[axis][0]["code"] in (17, 19) else 214
                step = min(step, max(1, self.last_delivery[axis]+spacing-self.tick))
        if step <= 0:
            raise ValueError("Non-progressing exact native time boundary")
        _, after, events, outputs = self.engine.step(step)
        for event in events:
            kind, axis = event.pop("ev"), event.get("axis")
            if kind == "enqueue":
                request = self.inflight[axis]
                if request is None or request["id"] != event["request_id"] or request["consumed"]:
                    raise ValueError("Actual native enqueue identity mismatch")
                request["consumed"] = True
                self.counts[axis]["consumed"] += 1
                self.counts[axis]["enqueued"] += 1
            elif kind == "application":
                request = self.inflight[axis]
                if request is None or not request["consumed"] or request["code"] != event["code"]:
                    raise ValueError("Actual native application identity mismatch")
                event.update(request_id=request["id"], delivery=request["delivery"], origin=request["origin"])
                self.counts[axis]["applied"] += 1
                self.inflight[axis] = None
            self._emit(kind, "agc_diagnostic_readback" if kind == "application" else "diagnostic_sensor_transport", tail=frozen, **event)
        relevant = []
        for at, channel, value in outputs:
            self._emit("output", "agc_output", cycle=at, channel=channel, value=value, tail=frozen)
            if channel in self.actual_output_jets:
                self.actual_output_jets[channel] = value
            if channel == 0o13:
                self.channel013_latch = value
            if channel == 0o13 and value & 0o600 == 0o600:
                self._emit("rhc_gate_observation", "agc_diagnostic_readback", cycle=at,
                    readback_cycle=after["cycle"], channel013=value,
                    rhc_pitch_counter0042=self.engine.lib.inspect_ram(0o42),
                    rhc_yaw_counter0043=self.engine.lib.inspect_ram(0o43),
                    meaning="Read-only counter observation after native call containing the original RHC gated read; no memory writes")
            if channel in (5, 6, 10):
                relevant.append((at, channel, value))
            # Existing fixture does not model these actuators. Observed outputs
            # remain in the raw log, and the session fails before applying them.
            if channel == 0o11 and value & (1 << 12):
                raise ValueError("Unsupported main engine-on command")
            if channel == 0o12 and value & 0o7400:
                raise ValueError("Unsupported descent-engine gimbal trim command")
        if any(event.get("unsupported") for event in events):
            raise ValueError("Unsupported active coarse/fine alignment command")
        self.tick += step
        if not frozen:
            for at, channel, value in relevant:
                self._integrate(self.plant_cursor, at)
                if channel in self.jets:
                    self.jets[channel] = value
                else:
                    self.zero = int(bool(value & 16))
                self.plant_cursor = at
            if self.tick == self.next_coupling:
                self._integrate(self.plant_cursor, self.tick)
                self.plant_cursor = self.tick
                self.next_coupling += CHUNK
            if self.ready and self.tick >= READY_CYCLE:
                self._check_ready()

    def advance_to(self, target_cycle):
        self._assert_owner()
        if self.closed or self.status not in ("starting", "running"):
            raise ValueError("Session cannot advance")
        if type(target_cycle) is not int or target_cycle < self.tick or target_cycle > END_CYCLE:
            raise ValueError("Advance target is outside the bounded live timeline")
        try:
            while self.tick < target_cycle:
                self._step(target_cycle)
            if self.tick == END_CYCLE:
                self.stop("bounded live horizon reached")
            return self.frame()
        except BaseException as error:
            self._fail(error)
            raise

    def advance(self, cycles=8533):
        if type(cycles) is not int or cycles < 1:
            raise ValueError("Advance requires a positive integer native CPU-call count")
        return self.advance_to(min(END_CYCLE, self.tick+cycles))

    def frame(self):
        state = self.engine.snapshot() if self.engine is not None else None
        return {"status": self.status, "ready": self.ready and not self.closed, "cycle": self.tick,
            "sim_time": self.tick*PERIOD, "interactive_time": max(0, self.tick-READY_CYCLE)*PERIOD,
            "remaining_time": max(0, END_CYCLE-self.tick)*PERIOD,
            "model": self.model, "cdu": state["cdu"] if state else [0, 0, 0],
            "model_cycle": self.plant_cursor,
            "freeze_cycle": self.freeze_cycle,
            "physical_time": self.plant_cursor*PERIOD,
            "jets": {str(key): value for key, value in self.jets.items()},
            "actual_output_jets": {str(key): value for key, value in self.actual_output_jets.items()},
            "thrusters": INTEGRATION.decode_jets(self.jets[5], self.jets[6]),
            "execution": self.engine.execution() if self.engine else None, "native": state,
            "rhc_readback": ({"channel013_output_latch": self.channel013_latch,
                "pitch_counter0042": self.engine.lib.inspect_ram(0o42),
                "yaw_counter0043": self.engine.lib.inspect_ram(0o43)} if self.engine else None),
            "counts": self.counts, "host_pending": [len(queue) for queue in self.queues],
            "control": dict(self.control), "events": list(self.events), "error": self.error,
            "trace_path": str(self.output / "trace.jsonl"),
            "classification": "Live Luminary output; synthetic 3D attitude/sensors; no powered descent"}

    def stop(self, reason="operator stop"):
        self._assert_owner()
        if self.closed:
            return self.summary
        if self.engine is None or self.log is None:
            raise ValueError("Session was not started")
        try:
            self._set_control(0, 0, None, "stop neutral")
            # Integrate the final incomplete interval before freezing production.
            self._integrate(self.plant_cursor, self.tick)
            self.plant_cursor = self.tick
            self.freeze_cycle = self.tick
            self._emit("freeze", "diagnostic", cycle=self.tick, reason=reason,
                meaning="Physical evolution/production frozen; CPU transport tail only; not vehicle equilibrium")
            end = self.tick+2_000_000
            while any(self.queues) or any(self.inflight) or self.engine.snapshot()["incoming"]:
                self._step(end, frozen=True)
                if self.tick >= end:
                    raise ValueError("Bounded native transport settlement timed out")
            settled = self.engine.snapshot()
            self._emit("settled", "diagnostic", state=settled)
            before, quiet, events, outputs = self.engine.step(1000)
            self.tick = quiet["cycle"]
            for event in events:
                self._emit(event.pop("ev"), "diagnostic_instrument_classification", tail=True, **event)
            for at, channel, value in outputs:
                self._emit("output", "agc_output", cycle=at, channel=channel, value=value, tail=True)
                if channel in self.actual_output_jets:
                    self.actual_output_jets[channel] = value
                if channel == 0o13:
                    self.channel013_latch = value
            if any(event.get("unsupported") for event in events):
                raise ValueError("Unsupported alignment command in quiet tail")
            if quiet["cdu"] != settled["cdu"] or quiet["incoming"] or any(f["pending"] or f["entries"] for f in quiet["fifo"]):
                raise ValueError("Native queue did not remain quiet")
            if any(len(set(count.values())) != 1 for count in self.counts):
                raise ValueError("Generated sensor operations were not all applied")
            self.status, self.ready = "stopped", False
            self.summary = {"status": "VERIFIED bounded live session", "reason": reason,
                "counts": self.counts, "settled": settled, "quiet": quiet, "final_model": self.model,
                "peak_host_queue": self.peak_host, "state_writes": 0,
                "scope": "Authentic bounded yaw/pitch input execution; queue settlement is not vehicle stability"}
            self._emit("summary", "diagnostic", **self.summary)
            write_json(self.output / "summary.json", self.summary)
            self._cleanup()
            return self.summary
        except BaseException as error:
            self._fail(error)
            raise

    def _cleanup(self):
        if self.proc:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            try:
                code = self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
                code = self.proc.returncode
            if code and self.error is None:
                self.error = "Vehicle process exit: " + str(code)
                self.status = "failed"
        for stream in (self.log, self.stderr):
            if stream and not stream.closed:
                stream.close()
        if self.log:
            write_json(self.output / "files.json", {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                for p in sorted(self.output.iterdir()) if p.is_file() and p.name != "files.json"})
        self.closed = True
        if self._locked:
            self._locked = False
            _ACTIVE.release()

    def _fail(self, error):
        if self.closed:
            return
        self.error, self.status, self.ready = str(error), "failed", False
        # No further vehicle integration after an unsupported state. Genuine
        # neutral inputs are still delivered and consumed before process close.
        if self.engine and self.log:
            try:
                self._set_control(0, 0, None, "fail closed neutral")
                for _ in range(16):
                    if not self.engine.snapshot()["incoming"]:
                        break
                    _, _, events, outputs = self.engine.step(1)
                    for event in events:
                        self._emit(event.pop("ev"), "failure_transport_observation", **event)
                    for at, channel, value in outputs:
                        self._emit("output", "agc_output", cycle=at, channel=channel, value=value, tail=True)
            except Exception as neutral_error:
                self._emit("neutral_failure", "diagnostic", error=str(neutral_error))
            self.tick = self.engine.snapshot()["cycle"]
            self._emit("error", "diagnostic", cycle=self.tick, error=self.error)
            self.summary = {"status": "FAILED", "error": self.error, "counts": self.counts,
                "state": self.engine.snapshot(), "no_claim": "Failed/incomplete session; no fabricated settlement"}
            write_json(self.output / "summary.json", self.summary)
        self._cleanup()
