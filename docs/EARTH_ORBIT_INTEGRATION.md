# Playable Columbia computer integration

The Earth-parking-orbit chapter now contains a manually playable **original
Comanche 055 CMC** console. All nineteen DSKY keys send their actual hardware
inputs to the unchanged pinned yaAGC ringbuffer core. Computer displays come
from original output packets. No tutorial code supplies a display response.

The task is a **cold-start computer readiness diagnostic**, not a restored
post-insertion Apollo 11 checkpoint. There is no orbital state, operating IMU,
known reference orientation or optical instrument model. P52's real `00210`
readiness alarm remains visible. Completing the diagnostic does not complete
alignment, Earth-orbit preparation, TLI or a flight goal.

[Player to-do list and entire-app walkthrough](EARTH_ORBIT_PLAYABLE_GUIDE.md) ·
[historical procedure research](EARTH_ORBIT_PROCEDURE_RESEARCH.md) ·
[original software/native/WASM evidence](earth-orbit-evidence/README.md).

## Startup

```sh
make play
```

Open `http://127.0.0.1:4173/`, choose **Apollo mission**, then **Open Earth-orbit
task**. Direct entry: `http://127.0.0.1:4173/campaign.html?play=1`.

The CMC requires Python 3.9+ and `cc`. It builds from retained source on request,
without downloading software or requiring Node, npm or Tcl. Existing lunar
attitude/physical-lab modes retain their separate pinned Tcl requirements.
`--recorded-only` explicitly disables live CMC execution. Reuse the running app
if the port is occupied, or use `make play PORT=4180`.

## Implemented interfaces

These routes extend `backend/final_server.py`; older LM, procedure and shared
mission routes are unchanged. No new WebSocket or remote service was introduced.

| Method / route | Request / result |
| --- | --- |
| `GET /api/earth-orbit/capabilities` | Verifies retained CMC inputs and compiler availability; returns mode, supported keys, scope and the existing private same-origin control token |
| `GET /api/earth-orbit/status` | Read-only published computer/task observation; never starts or advances a computer itself |
| `POST /api/earth-orbit/start` | `{}` starts a fresh native worker and resets only this diagnostic's progress |
| `POST /api/earth-orbit/key` | `{sessionId,sequence,key}` submits one exact hardware key; no macros, arbitrary RAM writes or spacecraft commands |
| `POST /api/earth-orbit/stop` | `{sessionId}` closes that native worker and retains its final observation, marked stopped |

POSTs retain existing loopback Host, matching Origin, fetch-site and
`X-Apollo-Token` checks. Bodies reject duplicate/nonfinite JSON, extra fields,
unsupported media and transfer encoding. Key sequences begin at zero, must be
contiguous, and cannot be replayed across restarted sessions. Requests are
serialized by one CMC owner thread; the LM worker remains separate.

Normal keys use channel `015`; **PRO** uses channel `032`, active-low bit 14,
with a mask, press and release. PRO is not replaced with `V33E`. Acknowledgments
identify actual queued ringbuffer bytes and observed consumption cycles. Input
acceptance does not imply that a requested program succeeded.

Snapshots identify `LIVE ORIGINAL CMC EXECUTION`, software and binary hashes,
session/revision/sequence, CPU call count, raw relay-derived DSKY fields and
source cycles. CPU seconds equal calls × `12 / 1,024,000`. These are neither wall
time nor historical GET. Unobserved fields remain unavailable. No spacecraft
position, velocity or flight outcome is synthesized.

The digit adapter also decodes register signs from original channel `010`
relay bits and held channel `011` states for KEY REL, OPR ERR, COMP ACTY and
the VERB/NOUN flash request. The frontend reports that request without timed
blinking. Unknown sign/indicator values remain `null` in the contract and `?`
in the panel; other caution/status lamps are not decoded.

`backend/cmc_native.py` owns the isolated native process and bounded pipe
protocol. `earth_orbit_service.py` owns input serialization, published snapshots
and diagnostic observation checks. The CPU executes bounded 0.1-second slices
while active, plus original key-settling intervals; this is a computer bench,
not a real-time flight clock. Ten minutes without operator input stops it.
Read-only validation can advance CPU calls through a private service method;
there is deliberately no HTTP time-jump endpoint.

## Frontend boundary

`earth-orbit-client.mjs` validates the current typed contract in
`earth-orbit-types.d.ts`, keeps the token private and requires exact key
acknowledgments. It never retries an uncertain key. Failed/stale acknowledgments
trigger observation resynchronization and require user review.

`earth-orbit-panel.mjs` renders the authentic staggered DSKY keypad and the
server's next instruction. It does not infer digits from task position.
Polling pauses while the console is hidden. Manual computer operation pauses
the optional historical tour; reference navigation never presses DSKY keys.
Camera interaction remains unrelated to computer or actuator input.

The server verifies the requested operation **and an actual original output
observation** before marking a checkpoint. Entering the right button script
without corresponding computer output cannot complete a step. Original N09
contains three alarm-history registers: `00210` can occupy any one, with an
earlier cold-start `01107` still present. Only original RSET clears that history.

The five checkpoints are display-test familiarization, P00, clock observation,
P52/IMU-off diagnosis and intentional P00 recovery. Each retains the observed
DSKY tuple and source cycle. `alignmentCompleted` and `flightExecuted` remain
false, including after all five checkpoints. Historical mission capability
gates therefore remain unchanged.

The clock checkpoint requires the full post-P00 hardware sequence
`VERB 1 6 NOUN 3 6 ENTR` (`V16N36E`) and numeric R1/R2/R3 observations under
V16N36. It is awarded only after two **different** `(R1, R2, R3)` clock tuples
are observed at increasing CPU cycles. A partial command, a held clock display,
two identical readings or CPU advancement by itself cannot complete the step.

## Next meaningful game step

Restore a source-validated post-insertion CMC checkpoint through authentic
initialization, and connect an operating IMU/optics model with known reference
orientation. Then implement and validate Collins's actual P52 option-3 star
measurements and correction workflow. Only its observed result can establish
alignment readiness. Saturn departure guidance and authoritative CSM flight
integration are separate prerequisites before TLI can become playable.
