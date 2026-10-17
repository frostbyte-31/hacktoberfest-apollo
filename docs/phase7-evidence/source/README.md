# Phase 7 source investigation: RCS, RHC and IMU frames

17 October 2026. **VERIFIED** here means inspection of the pinned original source, retained emulator/model source, or the identified external primary document. This directory contains source investigation and reproducible source checks. Coupled Phase 7 execution results belong to the integration evidence, not this source note.

**Recommendation:** add **pitch, Q**, to the existing **yaw, P**, controller fixture. Original Luminary has a complete Q/R autopilot, using Q/R RHC counts and U/V jet selection. Pitch and roll both have authentic input support; pitch is a practical first choice because its small-angle sensor coordinate is the inner gimbal rather than the middle gimbal associated with gimbal lock. This is an engineering choice, not a claim that pitch remains independent during combined rotation. Simultaneous P/Q motion can change all three gimbal angles and can produce physical R motion; those effects must be integrated and returned, not clamped to zero.

All original source files fetched here use Virtual AGC revision `f577e3fd917866c59334e6cdd32504f09df76f60`. `manifest.json` records exact URLs, hashes, sizes, retained dependencies and primary-document extraction provenance; `fetch-records.json` preserves actual fetch commands and outcomes, including an unused 404 and the resumed large-PDF download. Earlier evidence is read-only.

Run `python3 docs/phase7-evidence/source/verify_sources.py` for offline hash checks and source-derived mask, gimbal, RHC and readiness assertions. The optional `--primary-pdf /path/to/original.pdf` also verifies the full primary-document download against its recorded SHA-256. `source-check.json` records the actual successful check, with commands and UTC times in `source-check-command.json`.

## Original actuator interface

Only bits 1-8 of channels `005` and `006` command these RCS jets. A set bit means on; a reset bit terminates the firing. `mappings.json` lists all sixteen bit positions, original jet numbers, modern model names and P/U/V rotational signs. No channel word in this note is to be injected as an actuator command: the emulator must generate actual words from original Luminary.

The original source's `P-AXIS_RCS_AUTOPILOT.agc:100-105` derives body-rate acceleration as P from P jets, Q from **U minus V**, and R from **U plus V**, with the corresponding axis acceleration coefficients. The original `Q,R-AXES_RCS_AUTOPILOT.agc:779-783` explicitly describes transformation from body Q/R into non-orthogonal U/V control axes. A channel-005 bit therefore can affect both Q and R; a Q/R control-axis pulse is not an independent physical pitch-only or roll-only actuator.

The following source masks independently constrain the bit map:

| Original table | Octal word | Jet bits |
| --- | --- | --- |
| Q/R `ALLJETS`, -U | `00110` | 4, 7 |
| Q/R `ALLJETS`, -V | `00022` | 2, 5 |
| Q/R `ALLJETS`, +U | `00204` | 3, 8 |
| Q/R `ALLJETS`, +V | `00041` | 1, 6 |
| P `JETSALL`, -P | `00252` | 2, 4, 6, 8 |
| P `JETSALL`, +P | `00125` | 1, 3, 5, 7 |

The source-locked modern model names channel-005 bits 1-8 `Q4U,Q4D,Q3U,Q3D,Q2U,Q2D,Q1U,Q1D`, and channel-006 bits `Q3A,Q4F,Q1F,Q2A,Q2L,Q3R,Q4R,Q1L`. These aliases are preserved in its socket decoder and retained Phase 5 server. They are distinct from the older document's F/S jet suffixes; the bit and jet-number correspondence is explicit in the JSON table.

**External primary corroboration:** NASA/MIT MSC Internal Note 69-FS-4, *Programmed Guidance Equations for Luminary 1B*, September 1969, printed page 37 (PDF page 49), gives the complete channel-005/006 bit, jet-number and P/U/V effect tables. The [original document](https://www.ibiblio.org/apollo/Documents/j2-80-MSC-69-FS-4_text.pdf) is later than build 099 and is used as a cross-check, while pinned build-099 source remains authoritative. The rendered scan and verbatim text extraction are retained. Visual inspection confirms channel-005 bit 5 is **2U**; PDF OCR incorrectly reads that cell as 2D. No flight behavior or mapping is taken from the incorrect OCR cell.

## Authentic hand-controller path and proposed packets

The source-locked `ringbuffer_api.c:88-93,158-175` latches fictitious input ports and copies them to RHC counters only when original flight software writes channel `013` with bits 8 and 9 set. `INPUT_OUTPUT_CHANNEL_BIT_DESCRIPTIONS.agc:100-112` documents those two enable/read bits. Original `P-AXIS_RCS_AUTOPILOT.agc:714-724` performs that read. `Q,R-AXES_RCS_AUTOPILOT.agc:277-312` computes Q/R desired rates from the saved counts; it does not require a fabricated state write.

| Pilot/body command | Emulator input port, octal (decimal) | Actual RHC counter, octal | Channel-031 minimum-impulse direction bits, + / - |
| --- | --- | --- | --- |
| P / modern yaw | `0167` (119) | `0043` | 3 / 4 |
| Q / modern pitch | `0166` (118) | `0042` | 1 / 2 |
| R / modern roll | `0170` (120) | `0044` | 5 / 6 |

RHC values use 15-bit one's complement: +20 is decimal 20; -20 is decimal 32747 (`077753`). The direction bits and channel-031 out-of-detent bit 15 are active low. Direction bits are documented for minimum-impulse mode; rate-command mode instead uses the analog count ports and shared out-of-detent discrete. Supplying the consistent direction bits follows the original external crew-input adapter but does not establish that rate mode consumes them.

The existing neutral channel-031 word is decimal 28671 (`067777`): attitude hold selected, all translation and direction requests inactive, RHC in detent. Clear bit 15 and the relevant direction bit to form:

| Synthetic controller condition | Decimal channel-031 word | Other hardware-port data |
| --- | ---: | --- |
| Pitch +20 alone | 12286 | `0166=20`, `0167=0`, `0170=0` |
| Pitch -20 alone | 12285 | `0166=32747`, `0167=0`, `0170=0` |
| Existing yaw -20 | 12279 | `0166=0`, `0167=32747`, `0170=0` |
| Combined yaw -20, pitch +20 | 12278 | `0166=20`, `0167=32747`, `0170=0` |
| Combined yaw -20, pitch -20 | 12277 | `0166=32747`, `0167=32747`, `0170=0` |

The new integration harness owns the schedule. It can reuse the verified delayed V36 / V37 / V77 sequences, deliver the controller word at 2,500,000, enqueue both count-port values at 2,500,001 before advancing the CPU, and return both count ports to zero at 2,700,000 before restoring channel-031 neutral at 2,700,001. Full raw scheduled and consumed input observations must establish what was actually delivered. Packet insertion success or a fictitious-port echo alone does not prove DAP use.

The [Virtual AGC assembly-language manual](https://www.ibiblio.org/apollo/assembly_language_manual.html) independently corroborates the three fictitious ports, signed format and enable/read gating. The NASA/MIT primary document's printed pages 41, 46 and 47 corroborate gating and the channel-031 bit directions. The local primary-document extracts preserve those pages.

## Body axes, U/V axes and gimbal coordinates

Use body rates `(P,Q,R)`, corresponding to the retained model's names `(Omega_Yaw,Omega_Pitch,Omega_Roll)`. They are not three independent stable-member gimbal rates. Original `T4RUPT_PROGRAM.agc:1316-1366` states `AOG=CDUX, AIG=CDUY, AMG=CDUZ`, or **OIM=XYZ**. Thus counter `032` measures outer gimbal O, `033` inner gimbal I, and `034` middle gimbal M. The source's GPMATRIX gives:

```text
P = dO + sin(M) dI
Q = cos(O) cos(M) dI + sin(O) dM
R = -sin(O) cos(M) dI + cos(O) dM
```

The inverse is the retained `Transform_BodyAxes_StableMember` near non-singular attitudes. Independently multiplying the complete retained model matrix gives stable-to-body `T=Rx(-O) Rz(-M) Ry(-I)`, or body-to-stable `R=Ry(I) Rz(M) Rx(O)`. For `cos(M)>0`, extraction from T is `M=asin(T12)`, `O=atan2(-T32,T22)`, `I=atan2(-T13,T11)`. A new quaternion implementation must declare which direction its rotation maps and test this convention numerically; its numerics remain modern simulated physics, not original guidance.

There are two documentation discrepancies to preserve. The generic input/output source headings call channel 006 "ROLLJETS" even though build 099's actual P-axis selection tables define its P control. Also, the current external assembly manual's counter paragraph assigns X/Y/Z as inner/middle/outer, which conflicts with the pinned LM source's explicit OIM=XYZ and actual gimbal-lock monitor on CDUZ. Those generic labels are not used to choose the LM frame mapping.

## Original multi-axis initialization prerequisites

No additional Q/R-only readiness bypass is justified or required by the inspected source. Original `DAPIDLER_PROGRAM.agc:46-94` requires a valid mode switch, common IMU/DAP inhibition clear, PGNCS authority and `ACCSOKAY`. STARTDAP initializes P/Q/R rates, U/V jet times, Q/R filter terms, all old CDU readings, skip counters and T6 event state. The Q/R controller then uses the shared mode/PULSES state and saved Q/R RHC counts.

The independently resolved addresses are: original `ERASABLE_ASSIGNMENTS` numeric `SETLOC 067` leads to `STATE=0074`; `FLAGWORD_ASSIGNMENTS.agc:1187-1190` defines `DAPBOOLS=FLGWRD13=STATE+13D`, hence `0111` octal (unswitched bank 0). `ACCSOKAY=BIT3`, mask decimal 4; `PULSES=BIT15`, mask `040000` octal. Read-only checks may inspect them. Keep the Milestone 2 clean post-V36 P00/IMODES checks, confirm ACCSOKAY, then require actual RCS and counter-application evidence for each tested command. This still does not establish mission padload, calibrated alignment, REFSMMAT, engine/radar behavior or descent.

**ASSUMED:** later primary-document bit tables are a useful corroboration of the pinned 099 masks; the selected synthetic inertia, lever arms and finite two-axis workload are adequate only for the explicitly measured experiment. Jet direction bits prove no lever-arm magnitude or historic moment of inertia. **NOT RUN by this source investigation:** any coupled Phase 7 maneuver, vehicle stability, hardware-clock validation, powered descent or landing.
