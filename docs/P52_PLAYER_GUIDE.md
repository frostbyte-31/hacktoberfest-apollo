# Play original P52 alignment

Start the application with `make play`, keep the terminal running, and open
`http://127.0.0.1:4173/campaign.html?play=1&stage=earth-parking`.
If it is already running on 4173, use that page. To run another instance:
`make play PORT=4180` and use that port in the address.

Choose **Prepare alignment instruments**. The setup starts a fresh original
Comanche 055 and runs original P51 with modeled optical measurements to obtain
the initial reference. No reference matrix or ready flag is written into flight
memory by the host. This is disclosed preparation of a stationary instrument
fixture, not a reproduction of Apollo 11's post-insertion computer state.

Your goal is to complete **P52 option 3**: identify and sight two stars, inspect
the original calculations, authorize gyro correction, observe its sensor
feedback and recover to P00. The CMC supplies all DSKY responses.

## Player checklist

Use the on-screen Apollo keys, one at a time. Wait for each acknowledgement and
for a stable original prompt. The relay displays refresh over time: a partial
number or a blank display during processing is not the next prompt. The
navigation station gives the next action from the observed display.

1. **Select P52.** Press `VERB 3 7 ENTR 5 2 ENTR`. Observe PROG 52 and NOUN 06.
2. **Choose REFSMMAT.** Press `VERB 2 2 ENTR 0 0 0 0 3 ENTR`, then **PRO**.
   Wait for V50N25 with R1 `00015`.
3. **Select manual acquisition.** Press **ENTR**, then wait for NOUN 70.
4. **Identify Menkent.** Press `VERB 2 1 ENTR 0 0 0 3 0 ENTR`, then **PRO**.
   Wait for VERB 51, which can take several CPU seconds.
5. **Mark Menkent.** Select the **30 Menkent** acquisition guide. It starts
   centered in this fixture at shaft 0°, optical LOS 40°. With OPTICS MODE
   **MANUAL**, press **MARK**. At V50N25/`00016`, press **PRO**. Verify code
   `00030` under NOUN 71, then press **PRO** to confirm. Wait for NOUN 70.
6. **Identify Nunki.** Select the **37 Nunki** guide. Press
   `VERB 2 1 ENTR 0 0 0 3 7 ENTR`, then **PRO**. Wait for VERB 51.
7. **Acquire Nunki using the OHC.** Its fixture target is shaft 104.3980°,
   optical LOS 40°. Selecting the guide only changes the overlay. It does not
   move the optics or enter a DSKY identity. A tested manual route is:
   - HIGH gain, 1-second duration: tap **SHAFT +** five times → 100°.
   - HIGH gain, 0.1-second duration: tap **SHAFT +** twice → 104°.
   - LOW gain, 1-second duration: tap **SHAFT +** twice → 104.4°.
   - Confirm the sighting offset is approximately 0.0013°. Keep the optical
     LOS at 40°. You can use the shaft/trunnion controls to make corrections.
8. **Mark Nunki.** Press **MARK**, then **PRO** at V50N25/`00016`.
   Verify `00037` under NOUN 71, then **PRO** to confirm.
9. **Review the star fit.** Wait for original V06N05. R1 has 0.01° units.
   Inspect its result; **PRO** accepts it, while **ENTR** recycles the sightings.
   The exercise requires a fit within 0.05°. The original software computes
   the result; a poor mark is not silently corrected.
10. **Review gyro torque.** Wait for original V06N93. Each signed register has
    0.001° units. Press **PRO** to authorize the correction. Watch the actual
    gyro-output and sensor-operation counts change.
11. **Finish.** Wait for V50N25 with R1 `00014`. Press
    `VERB 3 7 ENTR 0 0 ENTR`. All five task checkpoints must read **OBSERVED**.

**PRO** is the real separate hardware input. **MARK** and **MARK REJECT** use
the navigation-panel input and hardware interrupt. The DSKY remains freely
operable; the interface does not substitute fake responses for wrong commands.
Restart the alignment setup if you want a clean attempt.

The OHC uses bounded on-screen deflections, rather than a physical analog
handle. HIGH uses the documented approximate direct limits of 20°/s shaft and
10°/s trunnion. LOW uses disclosed model rates of 0.2/0.1°/s. The duration
selector specifies CPU execution time. Automatic CMC optics drive and the
RESOLVED controller transform are unavailable. ZERO operates the original
switch/counter path; it changes the sighting, so use it deliberately.

## What to observe after playing

- Open **Original software and input provenance**: the same Comanche binary
  produces the displays and computations throughout the task.
- Compare your measured N05/N93 with your marked directions. These are newly
  computed results, not copied historical values.
- Inspect the model's gyro responses and returned counter operations. A
  disconnected-feedback validation run does not receive a completion certificate.
- Inspect the 3D Earth-orbit configuration. Camera movement is independent of
  instrument control; no orbital motion is propagated by this task.
- Continue the chronological mission chapters as references. Original Saturn
  departure remains unavailable, following the requested original-code-only
  scope. Completing this fixture does not authorize or execute TLI.
- The **Cold-start diagnostic** link preserves the earlier IMU-off experiment.
  Original Luminary recordings and the undocking trainer remain separate
  experiences accessible from the page header and home screen.

Historically Collins used stars **30 Menkent / 37 Nunki**, but this task uses a
constructed instrument orientation and modeled sensors. It does not reproduce
his historical encoder readings, calibration or flight state. See the
[procedure research](EARTH_DEPARTURE_PROCEDURE_RESEARCH.md),
[native execution evidence](earth-departure-evidence/README.md), and
[integration contract](EARTH_ALIGNMENT_INTEGRATION.md).
