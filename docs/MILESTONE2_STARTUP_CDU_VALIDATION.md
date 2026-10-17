# Milestone 2 — Clean startup interval and signed CDU timing

17 October 2026. **VERIFIED** means source inspection or the identified actual
execution; **ASSUMED** identifies synthetic fixture/model interpretation;
**NOT RUN** identifies unexecuted work. This is single-axis prerequisite
validation, separate from Phase 7 and from the earlier Phase 2 report.

**Result:** original Luminary reaches P00 with zero alarm registers after V36
and observed readiness. Signed CDU transport matches within a fixed rate mode
for the tested workloads. The experiment also exposes an existing plant mode
defect and silent FIFO overflow. Neither has been hidden or repaired by changing
the pinned engine, flight software or model.

## Startup: what is now established

The native probe loads the retained rope into the unchanged pinned ringbuffer
engine. It only observes flight RAM and sends hardware/DSKY channel packets.
There is no saved memory image, absolute counter write, vehicle motion,
RHC stimulus or readiness bypass. Seven fresh stationary cases include early
and delayed V37, replay, no-V36, IMU-off and before/after-readiness controls.

| Delayed case observation | CPU calls already executed |
|---|---:|
| Original PTBAD reached with all twelve phase words zero | 526 |
| Original alarm `01107` appears in FAILREG | 553 |
| Original V36 clears alarm registers | 491361 |
| Original ISSUP clears initialization/inhibition flags | 1480208 |
| Original STARTDAP reached | 1484077 |
| First delayed V37 key delivered | 1600000 |
| MODREG changes from −0 to P00 after V37 | 1729504 |
| Bounded capture ends, alarm registers still zero | 2200000 |

**VERIFIED cause of `01107`:** the emulator's reset clears erasable memory, then
enters original restart processing. Luminary checks stored complemented/direct
phase pairs with RXOR and expects negative zero. In this fixture both words are
positive zero. Actual instruction observations show pair six selected, `A=0` at
the check, PTBAD and then `01107`. V36 invokes the original fresh-start path and
clears the recorded alarm. This validates a **clean post-V36 interval**, not
alarm-free power-on or historical hardware initialization.

The old early V37 timing reaches original CANTROO and `01520`; the delayed and
after-ready cases reach P00 without that alarm. Omitting V36 leaves `01107`
recorded despite P00. IMU-off also permits P00 while inhibition remains and
STARTDAP never runs. Thus mode selection, alarm cleanliness and DAP readiness
are separate claims.

The delayed trace and replay are byte-identical. The accepted schedule observes
ISSUP, both initialization/inhibit flags clear, and STARTDAP before its first
V37 key. Its specific call indices are not universal wait times: moving keyboard
interrupts changes execution timing. At the engine's exact clock convention,
readiness is observed at 17.3461875 seconds and the first V37 key at 18.75 seconds.

Three pinned original Luminary source files, their upstream commit URLs/hashes,
numeric erasable layout resolution and exact rope instruction checks are
retained in [startup source/proof](milestone2-evidence/startup/README.md).
This is source-anchored observation, not fresh rope assembly or full alignment.

## Signed CDU: delivered, queued and applied are distinct

The transport probe executes real Luminary in fresh native processes with default
hardware inputs. Only synthetic CDU X counter-operation packets (`032` octal)
are delivered. Read-only getters expose actual FIFO entries, pending counts,
head sign/rate, deadlines and counter transitions. The original engine translation
unit is included unchanged once to expose its static FIFO to those getters.
These are diagnostic sensor requests/readbacks, not AGC-generated telemetry or
an AGC-controlled vehicle experiment.

Nine workloads each have an exact fresh-process replay. Supported signed slow,
fast and mixed streams reconcile every request, enqueue and application; queues
empty and counters stay unchanged during a further 1000 genuine CPU calls.
Actual packet operations demonstrate unsigned angle wrap `0 → 32767 → 0`.
Y/Z counters stay zero.

| Workload | Requested / accepted / applied | Result |
|---|---:|---|
| Positive / negative slow | 12 / 12 / 12 each | Identical application cycles; final X 12 / 32756 |
| Positive / negative fast | 24 / 24 / 24 each | Identical application cycles; final X 24 / 32744 |
| Mixed sign/rate | 22 / 22 / 22 | Four FIFO runs; final X 2 |
| Alternating supported | 64 / 64 / 64 | 64 runs, final X 0 with all applications observed |
| FIFO saturation control | 129 / 129 / 128 | 128 run entries; one accepted request silently dropped |
| Ringbuffer saturation control | 1025 / 1023 / 1023 | Two explicit input rejections; one coalesced FIFO run |

Capacity is **128 sign/rate runs**, not 128 pulses. Same-sign, same-rate requests
coalesce; alternating runs exhaust capacity. The overflow cases intentionally
assert exact loss/rejection and are never classified as supported lossless
operation. An unchanged final counter alone cannot establish no loss.

**VERIFIED timing:** the source uses `1024000/12` engine calls/second
(11.71875 µs/call). Slow deadlines advance `213,213,214` calls, nominally 400/s;
fast deadlines advance `13,13,14`, nominally 6400/s. Actual application depends
on instruction timing, round-robin service and input processing. With 24 fast
packets, the first deadline is 200014, but service begins at 200026 after input
consumption; the next application is at 200029. Deadline catch-up therefore
permits a three-call interval. The nominal rate is not a hard minimum spacing.
The retained vehicle wrapper's rounded 11.72 µs adds 5 ms over four million calls;
it remains unchanged and explicitly labeled.

[Transport source proofs and traces](milestone2-evidence/cdu/README.md) establish
these finite native conditions. They do not certify sustained sensor bandwidth,
queue occupancy in the old vehicle traces, DAP response or WebAssembly timing.

## Unchanged plant: signed mode defect confirmed

Twenty-four imposed yaw/X component scenarios run the existing Tcl procedures
with pinned Tcl 8.6.16. Motion is diagnostic input, not an authentic actuator
command. At ±8°/s, both signs generate 727 pulses over 0.999716 seconds, but:

- +8°/s emits PCDU_FAST (decimal 17).
- −8°/s emits slow MCDU (decimal 3).

The source compares signed `Omega_Yaw < 4`, rather than speed magnitude. +4 and
above select fast operations; all tested negative rates select slow operations.
Quantization, short-angle wrap and zeroing/lock controls were also measured.
The model's quantum is `360/32768°`, with a strict `residual > quantum` test.
Full [component scope, numerical integration and source evidence](milestone2-evidence/plant/README.md)
are retained. The observed ~728 pulses/s at −8°/s requests a nominal 400/s mode;
that is a source-proven interface limitation. No corrected high-rate negative
closed loop or general sign-symmetric vehicle control is claimed.

## Reproduction and actual checks

```sh
make test                  # historical suites, Milestone 1 and Milestone 2 tests
make validate-milestone2   # fresh startup, transport and component probes
make check                 # tests, original feedback demo and all new probes
```

All new sources and required original source excerpts are local. The existing
source-locked Tcl bootstrap is reused. The final
[`make check` command](milestone2-evidence/runs/2026-10-17-verified-check/command.json)
exited **0** with these actual results:

| Check | Actual result |
|---|---|
| Milestone 2 tests | 47 passed: 13 startup, 16 native transport, 16 plant/evidence, 2 preservation |
| Milestone 1 regression tests | 55 passed |
| Historical Phase 2–6 suites | 38 run: 35 passed, 3 unchanged known missing-log errors, explicitly retained |
| Original vehicle feedback reproduction | Connected, disconnected and replay raw traces still byte-identical to Phase 6 |
| Fresh Milestone 2 probes | Seven startup runs, nine transport workloads plus replays, 24 plant scenarios; all commands exit 0 |
| Prior evidence | All 534 preserved files match; no newly missing, changed, unsafe or unlisted old evidence |

This does not mean all historical tests passed. Their missing-log errors and the
29 historical gaps remain unchanged. Test and experiment records are separate:

- [Milestone 2 test outcomes](milestone2-evidence/runs/2026-10-17-verified-check/milestone2-tests/results.json)
- [Historical/Milestone 1 test outcomes](milestone2-evidence/runs/2026-10-17-verified-check/milestone1-tests/results.json)
- [Fresh startup checks](milestone2-evidence/runs/2026-10-17-verified-check/validation/startup/validation.json)
- [Fresh transport summaries and raw traces](milestone2-evidence/runs/2026-10-17-verified-check/validation/cdu/summary.json)
- [Fresh plant findings](milestone2-evidence/runs/2026-10-17-verified-check/validation/plant/validation.json)
- [Preservation check](milestone2-evidence/runs/2026-10-17-verified-check/validation/preservation-after.json)

Earlier diagnostic attempts are retained, including a caught startup preflight
address-assertion typo and the initial counter observer. The final observer reads
the actual FIFO-head bits and compares them with the requested sequence, rather
than assigning the sequence as its observation. The complete check was rerun
after that strengthening. No earlier trace was edited to fit the later observer.
New raw transport/startup traces are retained; duplicate original vehicle traces
are represented by verified hashes/references, with build binaries left in
ignored scratch.

The validation remains native macOS arm64/Python 3.9.6/Apple clang 21/Tcl 8.6.16.
Source pin: Virtual AGC `f577e3fd917866c59334e6cdd32504f09df76f60`; rope SHA-256
`1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
No emulator, flight source, original model, earlier report/evidence or Milestone 1
tool was edited. The preservation inventory checks all 534 prior files.

**ASSUMED:** stationary synthetic operate-only startup and imposed yaw suffice
for these bounded prerequisites. **NOT RUN:** historical mission padload,
REFSMMAT/calibrated alignment, corrected plant feedback, general multi-axis
control, new WASM comparison, throttle/radar, descent or landing. Phase 7 is not
started. The next useful change requires separate authorization: identify and
repair the modern model's signed mode selector, then validate paced negative
feedback and settled queues within the same single axis.
