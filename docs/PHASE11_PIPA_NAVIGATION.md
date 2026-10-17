# Backend Phase 11 — authentic PIPA and inertial navigation

**COMPLETE AND VERIFIED through Level 4, within this bounded synthetic P47 experiment.**
Original Luminary 099 consumes genuine positive/negative PIPA counter operations,
performs its original gravity/navigation calculation, and updates RN/VN. This is
diagnostic simulation data, not Apollo 11 flight measurements. Later P63 use of
the changed navigation state (**Level 5**), ignition, powered descent and landing
are **NOT RUN**.

## Baseline and preservation

Work is isolated on `codex/backend-phase11`, based on
`5a689c75d43613f29a49fa32d9bd786437825ee5`. Main and the separate
`codex/frontend-mission-control` worktree were left untouched. All 5531 previously
tracked files were fingerprinted before work. The frontend worktree's tracked and
nonignored untracked files, branch and Git status were fingerprinted separately;
the end comparison is retained under `phase11-evidence/preservation/`.

The fresh, unchanged Phase 10 experiment reproduced the canonical raw trace
`6fe0d3c6ee46639c82d9c563925f206324325bc14bdabb5a3f4c6293c8085bc2`:
P51, original P27 loading, P63 readiness, nine original ROOTPSRS solutions and
V06N61. Its original 4098-file preservation checks still run unchanged inside
the existing sealed baseline staging procedure. The fresh Phase 7 regressions
again demonstrated capability C: independent and simultaneous bounded yaw/pitch;
independent full three-axis control remains **NOT RUN**.

Pinned Virtual AGC: `f577e3fd917866c59334e6cdd32504f09df76f60`.
Original archive SHA-256:
`1df5e3c4432d58d30736cf2a46b7456a9de99debe1d35dfed72be37dcd813267`.
Unchanged Luminary rope SHA-256:
`1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`.
All 359 selected original source files, the assembled listing and its symbols
are verified before execution and the source is checked again afterward. A fresh
offline archive extraction/assembly was also executed by the final portable run.
Host Python, compiler and OS are recorded, not pinned across platforms.

## Source-supported hardware and navigation

Exact pinned-source references and hashes are in
[source-investigation.md](phase11-evidence/source-investigation.md).

| Interface | VERIFIED meaning |
|---|---|
| Erasable counters `037`, `040`, `041` octal | PIPAX, PIPAY, PIPAZ |
| Packet channel `0x80 \| counter` | Counter event, not a normal channel-value write |
| Operation `0` / `2` | PINC / MINC, one's-complement counting |
| Nominal LM scale | 0.01 m/s per PIPA count |
| PIPA frame | IMU stable member, not a screen/body axis |
| READACCS | Original two-second sensor-reading task |
| PIPASR | Reads counters into DELV and clears counters to negative zero |
| SERVICER → CALCRVG | Compensation, REF-frame delta-v, original gravity/state update |
| COPYCYCL/COPYCYC → CALCN83 | RN1/VN1 copied to RN/VN, original accumulated delta-v |

These follow `ERASABLE_ASSIGNMENTS.agc:134–136`,
`ringbuffer_api.c:130–139`, `agc_engine.c:1570–1602`,
`CONTROLLED_CONSTANTS.agc:178–180`, and `SERVICER.agc:520–602,987–1011`.
Counter operations 1/3 are CDU operations and are not used for PIPA.
No counter-overflow behavior is claimed; the experiment stays far below overflow.

The unchanged P63 V06N61 fixture does not establish active accelerometer
integration. Rather than proceed toward ignition, the experiment selects original
P00 then **P47 (`V37E47E`)**. `P40-P47.agc:364–429` invokes R02BOTH,
MIDTOAV2, STARTP47 and PREREAD. Original MIDTOAV2 propagates the already supplied
P27 permanent state and schedules activation approximately 20 seconds ahead.
The driver allows 30 seconds after selection and observes established sensor
cycles before applying force. Original V37 cleanup clears MUNFLAG; the observed
clear FLAGWRD6 bit 8 confirms CALCRVG rather than MUNRVG.

The first trial requested P47 before a background P63 task had cleared NODOFLAG;
it received genuine alarm 01520 and remained in P00. The corrected driver waits
for **original software** to clear FLAGWRD2 bit 1, then allows two seconds before
the next DSKY request. No flag is assigned by modern code. A separate observer
build trial exposed an incorrect assumption that fixed-fixed symbols have a
`fixedBank` field; it failed before execution. Both are retained as driver/build
investigations, not successful AGC runs.

## Sensor model, frames and timing

The external [pipa_sensor.py](phase11-evidence/pipa_sensor.py) is an ideal sensor
adapter, not a navigation integrator or another spacecraft plant:

```text
f_REF = a_total_REF − g_REF                 [m/s²]
f_SM = C_SM_from_REF · f_REF               [m/s²]
Δv_SM = integral(f_SM dt)                 [m/s]
one signed event per accumulated 0.01 m/s
```

`C_SM_from_REF` is twice the DP-encoded, AGC-computed Phase 9 REFSMMAT. The
matrix is checked as a proper rotation within 1e-6; its existing synthetic
near-identity alignment is not a physically calibrated Apollo attitude.
The requested stable-member X force is expressed in REF using its transpose.
RN uses Moon-centered basic REF coordinates in metres (B29); VN uses REF velocity
in m/cs (B7), converted to m/s only for diagnostics. No axis is named “altitude.”

**ASSUMED:** fixed instrument orientation, ideal zero-noise sensor, no vibration,
bias drift or scale error. Original PIPASCF/PIPABIAS are observed as zero, never
assigned by the new driver. The adapter supports three-component vectors and
tested rotations; native force delivery here validates **stable-member X only**.
It does not connect to Phase 7's deliberately disabled translational plant.

The native zero case explicitly supplies equal, nonzero total/gravity vectors:
free fall generates no pulses. A held constant diagnostic gravity vector is
calculated from observed RN and the existing rope-derived lunar μ, solely to
exercise subtraction. Positive/negative cases add the specified force to that
same gravity vector. These held vectors are a measurement fixture, not an
externally propagated trajectory; original Luminary owns its navigation/gravity.

Time is emulator MCT, exactly `12/1024000 s`, not host wall time or the old
plant's rounded step. Exact rational accumulation retains signed fractional
pulses across intervals. Threshold times round up to the next MCT; pulses in
these runs are accepted by the ringbuffer and observed in genuine counters on
the following MCT. No queued pulse is lost. Disconnection drops generated events
without accumulating a later catch-up burst. After six seconds of force there
are four seconds for original reads/settlement.

## Actual native results and independent checks

Every run executes unchanged Phase 5 startup → original P51 → original P27 →
P63 V06N61, then the P00/P47 sequence above. Each fresh run ends at CPU call
23,678,413 with P47 V16N83 and no new alarm; the inherited early-startup 01520
remains in FAILREG as before. Phase 10.5/frontend files are not used to produce
these results.

| Synthetic input, 6 s | Generated/delivered X counts | Original accumulated REF Δv X | Original VN X difference vs zero |
|---|---:|---:|---:|
| Zero specific force | 0 / 0 | 0 m/s | 0 m/s |
| Approximately +1 m/s² stable X | +600 / +600 | +6.00004196167 m/s | +6.00004196167 m/s |
| Approximately −1 m/s² stable X | −600 / −600 | −6.00004196167 m/s | −6.00004196167 m/s |
| Positive force, disconnected | +600 / 0 | 0 m/s | 0 m/s |

All delivered counts are observed both in counter transitions and original
SERVICER raw DELV reads. Original DELVREF is independently compared with the
retained rope's KPIP1 (`33,2021`: `00321 26706` octal,
0.012800000607967377) and actual REFSMMAT, within two velocity DP LSB
(0.0000953674 m/s). The small difference from ideal 6 m/s is original fixed-point
conversion/rounding, not a fabricated sensor adjustment.

Causal VN comparisons match original PIPTIME timestamps. Their derived tolerance
is approximately 0.0018874 m/s, combining a conservative gravity-gradient bound
and four velocity DP LSB per matched navigation sample; the largest observed
component error is below 0.000056 m/s. RN changes with the sign as well: ±30 m
at the last completed display/navigation job, and ±42 m at the final copied RN
snapshot (position resolution 2 m). The bounded horizon stops during the final
CALCN83 job, after the latest RN/VN copy; it does not claim that job completed.

The zero-force run still changes VN under **original gravitational integration**.
Disconnected RN/VN, PIPTIME and accumulated delta-v match zero word-for-word.
The positive repeat's complete raw trace is byte-identical. Native CPU checkpoints
identify original READACCS/PIPASR/SERVICER/COPYCYCL/CALCN83. CALCRVG is interpreted
code: the new read-only bridge observes its original NEWOPS dispatch using LOC
and BANKSET, rather than mistaking a native Z address for interpreted execution.

| Validation level | Result |
|---|---|
| 1. Genuine counter-event transport accepted | VERIFIED |
| 2. Original counters respond, including negative zero/signs | VERIFIED |
| 3. Original navigation consumes readings | VERIFIED |
| 4. Original navigation computes causal RN/VN changes | VERIFIED, bounded P47/X-axis experiment |
| 5. Changed navigation influences subsequent landing guidance | NOT RUN |

## Reproduction and tests

From the backend worktree, with Python 3.8+, Git, C compiler and make:

```sh
python3 -B docs/phase11-evidence/validate.py --output .build/phase11/my-validation
```

The unchanged preparer downloads and verifies the pinned source. For an offline
source archive add `--archive /path/to/virtualagc-f577e3fd.tar.gz`; its hash must
match. The existing assembler's build banner is reproduced using
`SOURCE_DATE_EPOCH=1792195200`, supplied by the driver, not as an Apollo clock.
Output directories must be new; failed trials are preserved. The command runs
five fresh native cases, causal analysis, a separate unchanged Phase 10 nominal
execution/hash comparison and both new test suites. Exact launch commands,
toolchain, child logs and source/code fingerprints are retained in the output.

To check the retained native evidence without compiling:

```sh
python3 -B -m unittest discover -s docs/phase11-evidence -p 'test_*.py' -v
```

Actual final totals: **405 passed, 0 failing assertions, 3 known historical
missing-evidence errors, 0 skips**. The 29 new tests comprise 13 modern sensor
unit tests and 16 assertions against real native execution, kept distinct.
The 376 existing regression passes and exact commands are documented in
[tests/README.md](phase11-evidence/tests/README.md): `make check` (210 + 3 errors),
unchanged Phase 8–10 runner (57), `make test-live` (66), live evidence (9),
guidance-data (14), demo guards (6), and Node guidance (14). Fresh Phase 7 native
cases also passed. Integrity checks for Phase 10/10.5 passed unchanged.

The three actual FileNotFoundError errors remain in the original Phase 4/5/6
preservation tests, first encountering `docs/phase3-evidence/build.log`.
No historical logs were fabricated or tests weakened. An initial HTTP-unit-test
attempt also hit 11 sandbox socket-binding PermissionErrors; the unchanged
permission-enabled rerun passed. Both attempts are retained. The unrelated
native HTTP watchdog-neutralization validator is **NOT RUN** and unchanged.
The separately preserved frontend branch was not tested or modified here.

## Evidence and implementation

Only new Phase 11 files are added. Original Apollo instructions, emulator
semantics, prior reports/evidence, application code and validated calculations
are unchanged.

* `phase11-evidence/run_pipa.py`: reuses sealed staging, existing drivers and
  original P51/P27/P63, then authentic P47/counter inputs.
* `pipa_sensor.py`: SI specific force, rotation, quantization and signed timing.
* `pipa_bridge.c`: external read-only interpreted-dispatch observer.
* `analyze.py`, `test_sensor.py`, `test_native.py`: independent checks and tests.
* `validate.py`: portable fresh-build/native/test entry point.
* `runs/verified/`: all five compressed raw traces, input plans, counter and
  navigation snapshots, generated observer maps, commands and checksums.
* `validation/`: actual final orchestration, baseline hash agreement and tests.
* `baseline/`, `investigation/`, `tests/`, `preservation/`: preflight, failed
  driver trials, earlier regressions, before/after preservation evidence.
* `checksums.json`: final report/evidence fingerprints. Gzip is lossless and the
  decompressed raw SHA-256 remains separately verifiable.

## Remaining limitations and next experiments

**ASSUMED:** synthetic mission geometry and stationary alignment, ideal sensor,
short bounded acceleration fixture. **UNRESOLVED:** calibrated physical alignment,
realistic sensor errors, general overflow/rate limits, sustained moving-IMU
translation and integration with the attitude plant. Additional native Y/Z force
and rotating-frame experiments are **NOT RUN**. This verifies no propulsion,
historical trajectory, landing or continuous flight simulator.

Three next options, in dependency order:

1. Validate the original **P63 stable-member navigation path** using legitimate
   crew continuation and a strict pre-ignition cutoff; show whether sensor-driven
   state changes alter subsequent original guidance (Level 5). Check its genuine
   timing/readiness prerequisites before extending the plant.
2. Validate authentic **descent-engine discretes and throttle-counter meaning**
   on a bench with causal controls and source evidence, without claiming thrust.
3. After those interfaces are verified, connect a minimal **nongravitational
   force plant** to PIPA, with explicit inertial/body/stable transforms and bounded
   gravity propagation. This is a subsequent milestone, not work performed here.

No commit, merge or push was made. Stop at Backend Phase 11.
