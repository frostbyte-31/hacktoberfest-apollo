# Phase 10 primary-source research

Research date: 2026-10-17 UTC. These artifacts support a diagnostic experiment. They are not recovered Apollo flight telemetry or evidence that powered descent has run.

## Published Apollo 11 data

**VERIFIED:** [Grumman/NASA SNA-8-D-027(II) Rev 1, Table LM5/4.5.1-1](https://www.ibiblio.org/apollo/Documents/Luminary99PadLoads.pdf) contains Luminary 99 mission-tape guidance targets, ignition parameters, and launch-tape constants. The introduction explicitly excludes mission-computed state vectors. Relevant scans are retained in full as `Luminary99PadLoads.pdf`; pages 5, 6, 8 and 19 were rendered and visually checked. `padload-transcription.json` records octal words, source addresses, units, binary scale factors and printed decimal values. The octal entries are the load data; the printed decimals precede quantization.

`check_padload.py` independently decodes the 23 mission-tape components. All match their printed decimals within half a quantization unit, except unity, whose specified encoding is the largest representable positive fraction. `independent-padload-validation.json` is actual output from that command. This validates transcription/scaling, not AGC execution. Version 2 adds ZOOMTIME: address `3422` octal, SP word `05050`, scale 14, 2600 cs (26 seconds), verified visually on PDF p.15. Original EXGSUB uses it with TRIMACCL to compute trim velocity, and DDUMGOOD subtracts it to obtain ignition time from throttle-up time. The earlier 22-component transcription and arithmetic output are preserved as `*.v1.json`; early experimental configurations embedded that earlier version.

Important limits: historical TLAND is a preflight estimate, not actual landing time. The historical RLS has radius about 1,735,016.737 m, while the rope's equatorial lunar radius is 1,738,090 m. A synthetic spherical scenario must name its radius and epoch and must not silently mix these.

## Authentic initialization path

**VERIFIED in pinned local source:** `Luminary099/UPDATE_PROGRAM.agc`, original pp. 1386-1396, defines P27 and V71 contiguous updates in P00. The update is staged in UPBUFF, verified by V33 at flashing V21N02, then stored by original instructions. The executed bounds accept total component count 3 through 20 decimal, including count/address, hence at most 18 payload words. The source comments' apparent `200` bound must not override the instructions.

The same source specifically documents the lunar LM state-vector update: V71, total count `00021` octal, ECADR of UPSVFLAG, identifier `77775`, DP position X/Y/Z, DP velocity X/Y/Z, DP epoch, V33. `INTEGRATION_INITIALIZATION.agc:1046-1106` shows INTWAKEU interprets identifier magnitude 2 as lunar scaling, negative sign as LM, and calls ATOPLEM. It sets the appropriate navigation origin through original software. Loading permanent state-vector erasables alone would omit that supported path.

[Contemporary Luminary 1B update memorandum](https://www.ibiblio.org/apollo/Documents/luminary_1b_updates.pdf), retained as `luminary_1b_updates.pdf`, confirms lunar position scaling m/2^27, velocity (m/cs)/2^5 and state epoch cs/2^28. It also describes V72 RLS/TLAND updates. It is a later revision; the 099 code and its symbols control addresses and execution claims.

## Frames and constants

**VERIFIED in pinned source:** `PLANETARY_INERTIAL_ORIENTATION.agc:34-154` defines RP-TO-R and R-TO-RP, using lunar libration and the time-dependent MOONMX matrix. RP is Moon-fixed; R is basic inertial. These are not screen coordinates. `P12.agc:229-249` constructs WM from the transformed lunar pole, REFSMMAT and MOONRATE; it computes /LAND/ from RLS. `THE_LUNAR_LANDING.agc:79-115` transforms RLS at TLAND before guidance. `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc:420-473` computes RGU and VGU in guidance coordinates. REFSMMAT maps basic inertial vectors to the stable-member frame; its numerical rotation quality requires an independent check against the actual run.

`CONTROLLED_CONSTANTS.agc:258-259,279-289,325-327` supplies lunar mu 4.9027780e8 m^3/cs^2 (4.9027780e12 SI), equatorial radius 1738090 m and rotation rate 2.6616994890062991e-8 rad/cs. These are authentic model constants, not present-day estimates.

[Colossus 2 GSOP, March 1969, Section 5.1.4](https://www.ibiblio.org/apollo/Documents/R-577-Colossus2-Martin-5.1.pdf) defines the shared basic inertial system: origin at the active primary's center, X toward the 1969 mean equinox, Z toward mean terrestrial north, Y completing the right-handed triad. This is CSM documentation, used only to corroborate the shared frame.

[Luminary 1C GSOP, Section 5.1.4-5.1.5](https://www.ibiblio.org/apollo/NARA-SW/R-567-sec5-rev8-5.1-5.2.pdf) describes Moon-fixed axes (X toward the mean visible center, Z lunar north), landing-site storage and P27 updates. Its basic inertial epoch is 1970, so it must not supply the 1969 orientation unchanged. It corroborates frame roles, not exact 099 execution or mission values.

## Historical pre-descent preparation

**VERIFIED:** [Apollo 11 Mission Report, November 1969, §§5.1-5.2 and Table 5-III](https://www.ibiblio.org/apollo/Documents/A11_MissionReport.pdf) describes optical IMU alignment, ground-filtered tracking and post-DOI state validation before PDI. Table 5-III (printed 5-14, PDF p.63) gives operational/best-estimate/onboard latitude, longitude and altitude. Its onboard altitude is 49,955 ft. This table does not give a complete inertial position, velocity and epoch suitable for an exact historical state upload. `mission-report-p051.png` and `mission-report-p063.png` preserve the inspected pages. The full source was downloaded to a temporary file for inspection; its checksum is recorded in `sources.json`, rather than retaining an additional 12 MB copy.

[Apollo 11 landing transcript](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html), approximately 102:19-102:27, records solar-alignment, radar and visual altitude checks. These checks underline the difference between Phase 9's synthetic stationary optical fixture and mission-calibrated flight navigation. They supply no replacement six-component inertial state for Phase 10.

**UNRESOLVED:** An exact Apollo 11 pre-PDI inertial state with all frame, epoch and padload conventions has not been recovered by this focused research. A source-scaled, physically coherent **SYNTHETIC** lunar diagnostic state is appropriate if separately documented; the historical target-shape padload may be reused with its provenance. No initial-state numbers should be inferred from the all-zero diagnostic fixture.

## Reproduction

```sh
curl --fail --location https://www.ibiblio.org/apollo/Documents/Luminary99PadLoads.pdf --output /tmp/Luminary99PadLoads.pdf
shasum -a 256 /tmp/Luminary99PadLoads.pdf
python3 -B docs/phase10-evidence/research/check_padload.py
```

Expected PDF SHA256: `e112f47d5c413a1c7385e6422c7dbb12e19f2802fdecb31429828d90cac9ff86`. Online documents are provenance; the sealed retained bytes are the experiment's source artifacts. Native experiment commands and actual outcomes belong in the Phase 10 report/harness evidence, not this research note.
