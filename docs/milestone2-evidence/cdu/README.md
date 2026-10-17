# Signed CDU X transport diagnostics

**VERIFIED native execution:** nine finite workloads and their fresh-process replays execute real Luminary099 through the pinned yaAGC ringbuffer backend. Sixteen tests rebuild and execute those workloads and check output-preservation guards; they do not infer success from retained prose. **Scope:** synthetic counter-transport diagnostics on CDU X (`032` octal), with no spacecraft model, controller, DSKY input schedule or absolute counter writes. These results do not establish mission readiness, sensor calibration, DAP filter acceptance, a vehicle trajectory or another supported axis.

From the project root, after extracting the retained 24-file Phase 6 corresponding-source archive into a new directory:

```sh
python3 docs/milestone2-evidence/cdu/run_validation.py \
  --source /path/to/unchanged/extracted/source \
  --output .build/milestone2-cdu/new-run
python3 -m unittest discover -s docs/milestone2-evidence/cdu -p 'test_*.py' -v
```

The runner accepts `--cc` and rejects existing output directories. The native tests independently extract and hash-check the retained bundle in new scratch, build the native library and launch every workload plus a replay. No network, Nix, Tcl or emulator source change is required. Compiler, Python, platform, commands, UTC execution times, binary/input hashes and complete event traces are recorded. Failed commands retain their stdout/stderr and nonzero exit in `commands.json`.

`inspect_bridge.c` includes the **unchanged** upstream `agc_engine.c` once, which makes its static FIFO visible to read-only getter functions in that translation unit. This changes inspection visibility, not the engine, flight code, counter operations, control flow or global state. The actual FIFO head's upper bits are decoded by `diag_head_code()` into its sign/rate operation code, with zero indicating an empty FIFO; this observed code is captured in every snapshot. Application records use that actual code, compare it with the independently tracked requested order, and verify both the modular counter change and real deadline increment. The other six engine compilation units are linked unchanged; all 24 retained source hashes are checked. `diag_step` executes the genuine CPU and drains its real output ringbuffer. It discards those outputs because this probe measures sensor transport, and never labels diagnostic records as authentic flight output. Each worker starts a new process because upstream FIFO and ringbuffer state are static and `cpu_reset()` alone is not asserted to reset those globals.

Initial conditions are explicit: fresh CPU and authentic rope; 200,000 CPU calls with default emulator hardware inputs and no plant; CDU X/Y/Z and all input/FIFO queues observed zero/empty before delivery. This is an idle diagnostic setup, **not** a clean initialized flight state. Only counter-operation packets to `032` are delivered. After all queues settle, a further 1,000 genuine CPU calls must leave the counters unchanged. Other axes must stay zero throughout. A one-million-call bound rejects unsettled workloads.

## Source proofs

All references below are to retained unchanged Virtual AGC revision `f577e3fd917866c59334e6cdd32504f09df76f60`; `inputs.json` records the participating hashes. The source is in `docs/phase6-evidence/corresponding-source.tar.gz`, so these claims remain inspectable offline.

| Source and lines | Verified behavior |
|---|---|
| `yaAGC/wasm.c:101–113`, `131–151` | `cpu_step` calls the engine once per requested step; `packet_write` formats a packet and returns ringbuffer insertion status. Its 11.72 µs timing instruction is rounded. |
| `yaAGC/ringbuffer.c:38–50`, `yaAGC/ringbuffer.h:25–33` | Four-byte elements and 4,096-byte buffer; one slot reserved to distinguish empty/full, so actual usable input capacity is 1,023 packets. Full input returns zero. |
| `yaAGC/ringbuffer_api.c:107–140` | Each counter packet invokes `UnprogrammedIncrement`, then returns immediately from input processing. Packet insertion is neither FIFO enqueue confirmation nor immediate counter application. |
| `yaAGC/agc_engine.c:1246–1276` | `CounterPCDU`/`CounterMCDU` increment/decrement modulo `077777 + 1` (32,768), using the unsigned angle-counter representation. They do not use AGC one's-complement arithmetic. |
| `yaAGC/agc_engine.c:1385–1397`, `1420–1480` | Three FIFOs; 128 run entries each. Same sign **and rate** coalesce into a counted run. A new sign/rate run at capacity is silently dropped; `UnprogrammedIncrement` has no acceptance return. A run's 30-bit count has no arithmetic-overflow guard; billion-pulse workloads are outside this experiment. |
| `yaAGC/agc_engine.c:1482–1563` | One FIFO is checked per service visit, round robin. Deadlines advance in slow intervals `213,213,214` or fast intervals `13,13,14`, following the **operation just applied**, including at rate transitions. Initial deadline is enqueue cycle plus 213 or 13. |
| `yaAGC/agc_engine.c:1570–1604` | Decimal operation codes 1/3 (octal `001/003`) queue positive/negative slow counts; decimal 17/19 (octal `021/023`) queue positive/negative fast counts for X/Y/Z. |
| `yaAGC/agc_engine.c:1906`, `1951–1988` | The cycle counter increments before channel processing. Counter-packet input, instruction extra delay and pending instruction cycles can return before FIFO service. A due CDU update consumes a CPU call. |

The source's nominal cycle convention is `1024000/12` CPU calls per second, hence one call is 11.71875 µs. Three slow deadline increments total 640 calls: nominal 400 operations/s. Three fast increments total 40 calls: nominal 6,400 operations/s. The older wrapper's 11.72 µs is 1.25 ns longer per call (0.010667%); four million calls differ by 5 ms. These are emulator timing conventions, not measured hardware clocks or historical mission time.

**Timing qualification:** the deadlines do not guarantee a hard minimum separation between actual applications. Counter-input calls postpone service while the first deadline keeps aging; subsequent service can catch up. With 24 fast packets delivered at call 200,000, the first is consumed at 200,001 and due at 200,014. Service starts only after the input burst, applying at 200,026 and 200,029, three calls apart. The later applications occur at 12–16-call intervals. Slow applications likewise jitter around the nominal interval because of round robin and instruction timing. Actual `application` rows, rather than nominal-rate multiplication, establish when counts reached erasable memory.

## Workloads and measured outcomes

Each phase delivers its finite burst before further CPU steps. All integers in JSON are decimal; trace headers identify counter `032` in octal. `delivery` records host insertion and its cycle; `consumption` records the later engine input call and observed FIFO enqueue/drop; `application` records the actual memory transition and deadline before/after; `settled` records empty queues and the extra 1,000-call quiet observation. Summary counts reconcile every request, explicit rejection, silent FIFO drop and application.

| Workload | Requested / packet accepted / applied | Peak FIFO run entries | Final CDU X | Loss classification |
|---|---:|---:|---:|---|
| Positive slow | 12 / 12 / 12 | 1 | 12 | None |
| Negative slow | 12 / 12 / 12 | 1 | 32756 | None |
| Positive fast | 24 / 24 / 24 | 1 | 24 | None |
| Negative fast | 24 / 24 / 24 | 1 | 32744 | None |
| Mixed `+4 slow, −3 slow, +8 fast, −7 fast` | 22 / 22 / 22 | 4 | 2 | None |
| 64 alternating sign/rate runs | 64 / 64 / 64 | 64 | 0 | None |
| Negative one, settle; positive one, settle | 2 / 2 / 2 | 1 | 0 | None; actual wrap `0→32767→0` |
| **Negative control:** 129 alternating slow signs | 129 / 129 / 128 | 128 | 0 | Exactly one silent FIFO drop; last requested `+1` never enqueued |
| **Negative control:** 1,025 identical positive fast requests | 1025 / 1023 / 1023 | 1 | 1023 | Exactly two explicit ringbuffer rejections; zero FIFO loss |

Positive and negative pure slow workloads have identical application-cycle sequences; the fast pair also matches exactly. This establishes transport sign symmetry for these finite conditions. It does not certify the external plant's slow/fast mode selector, long-duration transport capacity or the flight DAP response.

The tests require lossless order and modular deltas for supported workloads and reject unaccounted changes in counter or queue state. Overflow is exercised only in the two named bounded negative controls, whose exact expected loss/rejection is asserted. A zero net counter value alone cannot prove no loss: the 64 alternating supported pulses return to zero with 64 observed applications, while the 129-request overflow control returns to zero with only 128 observed applications.

**NOT RUN:** native/WebAssembly transport comparison for these new probes, full vehicle queue draining, high-rate plant flight control, absolute-angle initialization, hardware clock validation, another axis, Phase 7 or powered descent.
