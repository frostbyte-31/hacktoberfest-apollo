# Original Comanche P52: instrument integration evidence

This new evidence set validates original **Comanche 055 P52 option 3**, using a
bounded external CSM instrument fixture. It does **not** restore Apollo 11's
post-insertion checkpoint or simulate translunar injection. No original Apollo
source, pinned emulator source or earlier captured evidence was changed.

## What actually runs

The application builds the unchanged retained ringbuffer engine, selects its
existing CSM personality, and executes the previously verified Comanche rope:

`2ba31de9291cd10fb351a64d261bae8514a1cb75b4651bfa6a135dfa821a2d79`.

A new observer adds read-only erasable/channel inspection and one external
**KEYRUPT2 hardware edge** after a real CSM MARK/REJECT channel 016 packet has
been consumed. The pinned ringbuffer stores that packet but omits the hardware
interrupt, as previously documented in the separate Phase9 investigation. The
adapter writes the external interrupt request latch, never flight RAM, program
counters, REFSMMAT, computed guidance values or readiness flags.

A fresh session first powers the modeled IMU through active-low channel030
bit 9 and waits for original operate-only initialization. Its disclosed automatic
fixture setup then operates **original P51** using two actual optical encoder
observations and MARK interrupts. The original program computes REFSMMAT; only
its original validity bit and matrix are read back. This is a preparation of the
training fixture, not a claim that Collins ran P51 after orbital insertion.

The player starts in P00 and manually runs P52. The original software requests
option3, star identities, marks, star-angle review, gyro-angle review and P00.
DSKY output is decoded exclusively from original emitted relay packets.

## Instrument model and numerical scope

The fixture holds the body stationary with initially zero IMU gimbals. Its two
fixed inertial star vectors are taken from the original `STAR_TABLES.agc`:
**30 Menkent** and **37 Nunki**, using octal astronaut codes. The source table's
comments use decimal indices 24 and 31. Their separation is
**61.04741080287203°**. A fixed orientation places their optical lines of sight
at `(shaft 0°, trunnion 40°)` and `(shaft 104.39795116083444°, trunnion 40°)`.
This is a constructed 3D orientation preserving the original catalog geometry,
not historical Apollo 11 attitude or measured encoder data.

The original optical transform additionally applies the retained navigation-base
mounting matrix. Tests independently verify that original P51's decoded
REFSMMAT is orthonormal and maps both catalog vectors to these physical sight
vectors within 0.05°. No computed reference matrix is fed into the model.

Optics DIRECT controls produce individual real PCDU/MCDU operations for counter
035 (trunnion) and036 (shaft). Motion is scheduled across the requested CPU
interval, allowing flight instructions to execute between counter inputs.
The bounded manual envelope is shaft ±270° and optical line-of-sight
trunnion 0–64.7°. This is the supported fixture subset, not a complete mechanical
optics certification. The encoder bias is 19.775390625°; the relative mechanical
readout is displayed separately. Original ZERO switching and counter-zeroing
are exercised; automatic CMC optical motor drive is unavailable.

HIGH DIRECT maximum rates are 20°/s shaft and 10°/s trunnion, consistent with the
Apollo Operations Handbook's approximate maxima. LOW uses the engineering
model gains 0.2/0.1°/s, also used by NASSP, without claiming flight calibration.
No RESOLVED hand-controller transform is implemented or advertised.

Real original gyro output channel 0177 drives a separate bounded stable-member
model: count bits 1–11, sign bit 15, selectorA/B bits 14/13, and
`360 / 2097152` degrees per pulse. The X/Z/Y left-handed gimbal transformation
follows the CSM instrument geometry independently of AGC computation. Sensor
feedback returns through real counter 032/033/034 fast PCDU/MCDU packets. The
model rejects coarse-alignment outputs and fine gimbal motion beyond ±5°.

Engine execution is processed in chunks of at most 853 memory cycles
(approximately 10 ms). Gyro feedback is delivered after the chunk containing its
actual command, plus packet-consumption time; the core's counter FIFO supplies
its own pulse timing. Every command, hardware edge, generated operation and
emitted output retains an execution cycle. Host wall-clock scheduling does not
calculate the model's instrument motion. This is bounded deterministic coupling,
not exact hardware-event-time equivalence.

## Retained observations

The connected run uses only public DSKY/instrument interactions after its
disclosed P51 setup. It observes original P52 N05 `+00002` (**0.02°**), followed
by original N93 `-00003, -00011, +00010`
(**−0.003°, −0.011°, +0.010°**). These are new executed results, not the radioed
Apollo 11 historical numbers.

Three original gyro packets contain Y−63, Z+61 and X−19 pulses. The external
platform responds and sends two quantized sensor operations. Original CDU
readback becomes `[0,1,32767]`; the latter is the wrapped negative count.
Original P52 produces **V50N25/00014**, and the real final command returns P00.

An exercise completion certificate additionally requires two P52 marks, an
observed N05 fit ≤0.05°, crew PRO approval at actual N93, nonzero original gyro
output, actual sensor feedback and matching original counter readback. The
0.05° exercise gate is an application quality rule; the original computer can
accept a poor observation if the operator proceeds.

| Fresh execution | Actual result |
| --- | --- |
| Connected | Original P52 fit, torque, physical feedback, completion display, P00 |
| Repeat | Raw native trace byte-identical to connected |
| UI target 104.4° | Practical controller precision also completes |
| Feedback disconnected | Original torque commands still run; counters remain zero; no qualified alignment |
| MARK interrupt disconnected | Actual packet alone leaves original P52 at V51 waiting for a sighting |
| IMU off | Original `00210` alarm; reference validity lost; no alignment |
| N93 PRO withheld | Original display remains at N93; no gyro commands |
| Second sighting 5° off | Original N05 exposes the error; no exercise success certificate |

## Reproduce

A C compiler and Python3 are sufficient; no Node, Tcl, simulator download or
network access is needed for this instrument test. Use a **new output path**:

```sh
python3 -B docs/earth-departure-evidence/experiments/run_validation.py \
  --out .build/my-p52-proof --mode connected
python3 -B -m unittest backend.tests.test_cmc_alignment -v
```

The runner's other `--mode` choices are listed in `--help`. Disconnected-loop
controls exist only inside this validation harness; they are not application
commands. Each run is a fresh process because the original core has static
engine globals. `runs/*` retains compressed raw traces, observation frames,
summaries, build commands, environment and hashes; `executed-source` preserves
the exact new adapter/runner sources. The existing source archives and their
hashes remain in the earlier evidence sets, referenced by `inputs.json`.

**14 native tests pass.** They include the physical matrix check, real complete
execution, causal controls, exact replay, controller timing, original ZERO,
invalid-input clock preservation and provenance. This new hardware integration
has **not** been separately cross-validated against WebAssembly; the earlier
cold-start DSKY native/WASM result is not extended to it by inference.

## Limits and source references

There is no historical flight checkpoint, historical IMU calibration, mission
state vector, original launch-vehicle execution or authoritative spacecraft
translation here. Original cold-start time/ephemeris defaults are retained.
The two-star field omits Earth/Sun occultation, star visibility and sextant
image brightness. Gyro motor/encoder behavior is an ideal bounded external
model, not a calibrated physical IMU. P52 completion in this fixture is not
permission or evidence for an S-IVB burn or leaving Earth orbit.

Primary procedure/code research and exact source links are in
[the Earth-departure research document](../EARTH_DEPARTURE_PROCEDURE_RESEARCH.md).
In particular see [original P51–P53](https://www.ibiblio.org/apollo/listings/Comanche055/P51-P53.agc.html),
[original CSM geometry](https://www.ibiblio.org/apollo/listings/Comanche055/CSM_GEOMETRY.agc.html),
[original SXTMARK](https://www.ibiblio.org/apollo/listings/Comanche055/SXTMARK.agc.html),
and the [BlockII Operations Handbook §2.2.4.9–10](https://www.ibiblio.org/apollo/Documents/SM2A-03-BLOCKII-2.1_2.2.pdf).
The independent external gyro convention was checked against
[NASSP's IMU implementation](https://github.com/orbiternassp/NASSP/blob/623a383a727d60949d9a9d4f5d729ce268c0de28/Orbitersdk/samples/ProjectApollo/src_sys/imu.cpp).
The six fetched NASSP files used in this convention audit match their immutable
Git blob identities at commit `623a383a727d60949d9a9d4f5d729ce268c0de28`; the files,
GPL license, URLs and SHA-256 hashes are retained in
[source-audit/NASSP-source-manifest.json](source-audit/NASSP-source-manifest.json).
They are reference sources, not an executed application dependency.
