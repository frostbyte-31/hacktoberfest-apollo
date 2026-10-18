# Original P52 instrument integration

The default Earth-parking task now executes original Comanche 055 P52 option 3
with manual optics controls and bounded external IMU/optics models. The
earlier cold-start diagnostic remains at
`/campaign.html?play=1&stage=earth-parking&task=diagnostic`.

The user selected **original-code execution only; finish alignment first**.
No reconstructed Saturn guidance or TLI flight was added. Apollo 11's normal
departure belongs to the Saturn IU/LVDC; no AS-506 flight program or integrated
S-IVB vehicle is available here. P52 completion never changes full-flight
capability gates.

## Data and ownership

`backend/cmc_alignment.py` executes the unchanged pinned native core and the
existing Comanche binary in a fresh worker. Boot powers the modeled IMU through
its actual discrete and runs original P51 with two actual optical observations
to compute this fixture's reference. It does not restore a historical flight
checkpoint or write a computed matrix/validity flag from the host.

Manual controls produce actual counter/discrete/MARK inputs. Original gyro
output channel 0177 drives the external instrument model, which returns real
CDU counter operations. The source-verified hardware interrupt adapter, bounded
coupling latency, geometry and calibration limitations are documented in the
[separate native evidence set](earth-departure-evidence/README.md). This new
integration has not been separately validated against WebAssembly.

`backend/earth_alignment_service.py` owns one queue and worker, separate from
the cold-start CMC, lunar attitude and educational flight services. All DSKY
and instrument inputs share one strict session/sequence. Read-only status
requests only read published observations. A background owner advances bounded
CPU slices; CPU time is not wall time or historical mission GET.

## Implemented routes

These routes are implemented in `backend/final_server.py`:

| Method / route | Body or response |
| --- | --- |
| GET `/api/earth-alignment/capabilities` | Availability, scope, software, keys, instrument controls and private same-origin token |
| GET `/api/earth-alignment/status` | Published original-computer, instrument and task observation |
| POST `/api/earth-alignment/start` | `{}`; fresh original P51 setup, then P00 ready for manual P52 |
| POST `/api/earth-alignment/key` | `{sessionId,sequence,key}`; one real DSKY input |
| POST `/api/earth-alignment/instrument` | `{sessionId,sequence,control,value}`; one bounded modeled hardware action |
| POST `/api/earth-alignment/stop` | `{sessionId}`; stop worker, retain stale final observation |

Host/Origin/fetch-site/token checks, bounded JSON, strict fields, nonfinite and
duplicate-field rejection use the existing HTTP protections. Recorded-only
mode disables live alignment. Unsupported CMC optics motor drive is rejected;
the original software still receives actual supported manual hardware inputs.

Instrument controls are `power_imu` (boolean), `optics_mode`
(`MANUAL`, `ZERO`; automatic `CMC` unavailable), `mark` (`MARK`/`REJECT`) and
`optics_slew` (`{shaft,trunnion,rate,seconds}`). Each deflection is in −1…1,
duration is greater than zero and at most one CPU second, and rate is `HIGH`
or `LOW`. There is no public angle-teleport, acquire-star, automatic DSKY macro,
arbitrary memory-write or spacecraft-engine endpoint.

Snapshots identify `LIVE ORIGINAL CMC / MODELED INSTRUMENTS`, with the inner
computer separately identifying live AGC execution and original software hashes.
`computer.instruments` contains power/mode, physical angles in degrees, fixed
catalog-star geometry, measurement counts, original gyro observations and
qualified completion evidence. Optical LOS and relative mechanical trunnion
are different readouts. `flightState` remains null and historical checkpoint
loading remains false.

## Completion and frontend boundary

The service requires a manually entered P52 request, two MARK inputs, actual
N05/N93 output, explicit PRO approval, original nonzero gyro commands, applied
counter feedback and matching readback, the original completion request
V50N25/00014, and intentional final P00. A P51-ready flag, expected key script,
unapplied command or final P00 alone cannot complete the task.

The native `p52Complete` qualification becomes available after observed
computation and instrument feedback. The service's `task.alignmentCompleted`
and overall task completion additionally require its complete manual workflow
and P00 recovery. These are fixture results, not claims of historical physical
calibration. `flightExecuted` stays false.

The typed `earth-alignment-client.mjs` validates mode, native clock, relay data,
provenance, geometry and completion evidence. Acknowledgments identify the
specific session, sequence and applied key/control. Uncertain or unreadable
mutations trigger a single status resynchronization; they are never retried.

The existing DSKY console is reused through a client factory. The new navigation
panel renders a perspective acquisition diagram from backend-owned angles and
star directions. Choosing a guide affects the overlay only. The user must
enter identities and operate the OHC/MARK controls. The frontend calculates no
alignment correction or physical spacecraft dynamics. Actual output determines
the displayed procedural prompt.

## Startup and next integration

Run `make play` with Python and a C compiler, then open
`http://127.0.0.1:4173/campaign.html?play=1&stage=earth-parking`.
No frontend bundler, external model download, Node or Tcl is needed for this
CMC task. Existing lunar laboratory modes keep their own dependencies.

Next original-code steps require a validated historical CMC flight checkpoint,
expanded physical instrument calibration/visibility and the appropriate
original Saturn program, peripherals and vehicle dynamics. The modern
educational LM laboratory must remain a separate provider.
