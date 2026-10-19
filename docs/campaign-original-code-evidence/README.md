# Campaign original-code extension investigation

This new evidence directory investigates whether the existing completed original
Comanche P52 fixture can immediately support original **P47 thrust monitoring**.
It retains a negative result. **No playable P47 task, departure maneuver, landing,
or additional historical mission leg was enabled.**

## Actual execution

A fresh unchanged pinned ringbuffer/native engine executes the existing original
Comanche055 rope. The harness first completes original P51 fixture preparation
and then original P52 using the same bounded manual controller deflections,
DSKY keys and MARK inputs available to the player. Original gyro outputs and
returned CDU feedback qualify the P52 prerequisite. No host writes flight RAM,
a state vector, time, a readiness flag or a computed result.

The next input is `VERB 3 7 ENTR 4 7 ENTR`. Raw original relay output briefly
shows PROG47, but the original computer then leaves that mode. Original
`VERB 0 5 NOUN 0 9 ENTR` exposes **01204**. The original source defines that
alarm as a **negative or zero WAITLIST call**. Recovery with real
`VERB 3 7 ENTR 0 0 ENTR` returns P00.

The separate `VERB 1 6 NOUN 6 2 ENTR` request produces zero registers after the
abort, with PROG still blank. Those zeros are **not a working P47 monitor or
orbital telemetry**. An accepted key sequence, transient mode relay or arbitrary
numeric display cannot certify an executed program's sustained operation.

The exact initialization cause is **unresolved**. The fixture supplies no
validated CMC navigation state. `TIMEDELT` is a fixed original rope constant
(`2DEC1250`), not an absent erasable padload, and changing the clock does not
establish a valid state vector. Original P27 supports state-vector updates, but
a validated vector, epoch, frames, flags and instrument dynamics would be a
separate experiment. No speculative initialization was added to bypass the
failure.

## Retained runs

- `runs/p47-probe`: original P52 completion, P47 request, readout, actual alarm,
  and P00 recovery.
- `runs/p47-repeat`: fresh native repeat, with a raw trace byte-identical to the
  first run.
- `runs/p47-v96-control`: real original V96 before the P47 request. It still
  reaches 01204 rather than sustained monitoring.

Each directory contains summary JSON, compressed full observation frames, and a
lossless compressed raw packet/cycle trace. `verification.json` records raw
fingerprints and the actual regression result. These tests are native only;
no new WebAssembly equivalence is asserted.

## Source interpretation

The retained original `Comanche055/P40-P47.agc`, printed pages691–692, has
`P47CSM` call `R02BOTH`, then `MIDTOAV2`, then schedule `TIGON` with `WAITLIST`.
Its normal monitor is **V16N83**, accumulated delta-V components. `CALCN83` also
calls `S11.1` to compute N62. N62 means inertial velocity magnitude, altitude rate
and altitude; it is not the accumulated delta-V display.

Primary original source listings:

- [P40–P47](https://www.ibiblio.org/apollo/listings/Comanche055/P40-P47.agc.html)
- [Integration initialization](https://www.ibiblio.org/apollo/listings/Comanche055/INTEGRATION_INITIALIZATION.agc.html)
- [Alarm definitions](https://www.ibiblio.org/apollo/listings/Comanche055/ASSEMBLY_AND_OPERATION_INFORMATION.agc.html)
- [P27 update program](https://www.ibiblio.org/apollo/listings/Comanche055/UPDATE_PROGRAM.agc.html)

These files are already retained inside the unchanged source archive at
`docs/earth-orbit-evidence/corresponding-source.tar.gz`. This investigation reads
those bytes; it does not replace the archive, Apollo source, emulator or earlier
evidence.

## Application capability contract

The existing `/api/earth-alignment/capabilities` response now includes:

- `originalPrograms.P52`: availability follows actual native discovery;
  classification remains `LIVE ORIGINAL CMC / MODELED INSTRUMENTS`.
- `originalPrograms.P47`: `available:false`, classification
  `UNVALIDATED ORIGINAL PROGRAM`, with the specific observed limitation.

This describes available validated application tasks. The ordinary DSKY remains
freely operable, so a player can still request an unsupported original program;
the interface does not invent its response or turn its failure into success.
No new command endpoint, automatic command macro or completion flag was added.
Existing `task.complete` remains qualified P52 completion only, and
`flightExecuted` remains false.

## Reproduce and verify

Use a new output directory:

```sh
python3 -B docs/campaign-original-code-evidence/experiments/probe_p47.py \
  --out .build/campaign-original-code/my-p47-probe
python3 -B docs/campaign-original-code-evidence/experiments/probe_p47.py \
  --terminate-integration --out .build/campaign-original-code/my-p47-v96
python3 -B -m unittest backend.tests.test_cmc_alignment \
  backend.tests.test_earth_alignment_service \
  backend.tests.test_earth_alignment_http -v
```

Actual result: **38 tests passed**, including fresh original P52 integration,
the new original P47 negative probe, strict command transport and HTTP checks.
The capability test rejects unavailable original programs; the service test
shows that P47 keys plus an N62 frame cannot create alignment or flight success.
This is a preserved boundary, not completion of the requested full mission.
