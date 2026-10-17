# Phase 1 — AGC Proof of Execution: Report

Run date: 2026-10-17, UTC, in the Lovable sandbox (x86_64 Linux, gcc 14.3.0, GNU Make 4.4.1, Python 3.13.12, Node v22.22.0).
Raw evidence is in `docs/phase1-evidence/`. Every claim below cites a file there.

Labels: **VERIFIED** means it was run here and the output was kept. **ASSUMED** means it is believed but not demonstrated. **NOT RUN** means it was not executed.

## Summary

| Milestone | Result | Evidence |
|---|---|---|
| Pinned source and toolchain | VERIFIED | `00_`, `07_sha256.txt` |
| Build yaYUL, oct2bin, yaAGC (native) | VERIFIED (exit 0) | `01_`–`03_` |
| Assemble Luminary099 from source | VERIFIED (0 fatal, 1 warning) | `05_`, `05b_`, `05c_` |
| Binary comparison (B) | VERIFIED: 3 images byte-identical | `06_`, `08_` |
| M1: authentic instruction execution | VERIFIED | `10_`, `11_` |
| M2: mission-software DSKY behaviour | VERIFIED (V35, V16N36) | `20_`, `21_` |
| M3: physics coupling | NOT RUN (investigation only) | §M3 |
| WebAssembly: builds and runs same rope | VERIFIED, with one timing caveat | `30_`–`32_` |
| P63 / powered-descent behaviour | NOT RUN | — |

## 1. Pinned inputs

- **Virtual AGC** `virtualagc/virtualagc` commit `f577e3fd917866c59334e6cdd32504f09df76f60`. Fetched as a GitHub codeload tarball because stateful git commands are blocked in this sandbox. Tarball SHA-256 `1df5e3c4…1267`. VERIFIED.
- **Cross-reference only:** `chrislgarry/Apollo-11` at `911e5c02…71a5` (not used in the build). `siravan/moonjs` at `b99615c4…c184` (not used; see §W).
- **Licenses:** the AGC source and binsource headers say "Copyright: Public domain" (US Government work, MIT/IL). Virtual AGC tools ship `COPYING` (GNU GPL v2) and `LICENSE.txt`. Any redistributed emulator binary, including `yaAGC.wasm`, is GPL-2 and must come with its source. VERIFIED (file headers read).
- **WASI SDK** `wasi-sdk-24.0-x86_64-linux` from the official WebAssembly/wasi-sdk releases. Tarball SHA-256 is in `07_sha256.txt`.

Reproduce on any x86_64 Linux machine with gcc and make:
```sh
curl -L -o va.tgz https://codeload.github.com/virtualagc/virtualagc/tar.gz/f577e3fd917866c59334e6cdd32504f09df76f60
tar xzf va.tgz && mv virtualagc-f577e3fd* va && cd va
mkdir -p yaDSKY/src yaDEDA/src && touch yaDSKY/src/main.c yaDEDA/src/main.c   # see note 1
(cd yaYUL && make cc=gcc) && (cd Tools && make cc=gcc oct2bin) && (cd yaAGC && make cc=gcc)
```
- **Note 1:** `yaAGC/Makefile` (target `libyaAGC.a`) runs `touch ../yaDSKY/src/main.c`. That fails if the directory is missing, as in our partial extract. A full extract does not need the stub.
- **Note 2:** without `cc=gcc` the sub-Makefiles expand an empty `$(cc)` and the builds fail. The first attempts and their errors are described in this report; the logs show the corrected runs.

## 2. Reference images: provenance and format

- `Luminary099/Luminary099.binsource`: a hand transcription of the octal listing of Luminary 099 (listing pages 1590–1733), created in 2009. Its header says all banks have correct bugger words, "NO guarantee of correctness" until proofed. The format is 5-digit octal words, no parity, `BANK=n` directives.
- `Luminary099/AP11ROPE.binsource`: an independent 2017 OCR transcription (Tesseract, then manual fixes) of **AP11ROPE**, the octal listing of Don Eyles's 1971 recreation of Luminary 99 Rev 1. Its header records that all differences from `Luminary099.binsource` were resolved against the AP11ROPE scans, and a full ProoferBox pass found no errors. The format is `PARITY=1`, 6-digit octal (15 data bits plus a parity bit).
- Both files are converted by `Tools/oct2bin` to the same `.bin` layout as yaYUL output: 36 banks × 1024 words, 16-bit big-endian, data in bits 15–1, file order bank 2, 3, 0, 1, 4…35 (see `set_fixed()` in `yaAGC/wasm.c`). File sizes are 73728 bytes each. VERIFIED.
- The pinned `Luminary099/Makefile` builds `Luminary099.bin` from the binsource and `AP11ROPE.bin` from AP11ROPE. Its own `diff` against AP11ROPE is still commented out ("when AP11ROPE proofing is complete"), so the upstream project does not run this check by default.

## B. Binary comparison (independent milestone)

Commands are in `05_` and `06_`; results are in `08_binary_compare.log`.
- `yaYUL --unpound-page MAIN.agc` produced `MAIN.agc.bin` with exit 0, 0 unresolved symbols, 0 fatal errors, and 1 warning ("May overflow memory bank" at E3,1776 `TCDH ERASE +1`, an erasable allocation, `05b_`). 36 bugger (checksum) words were reported.
- `cmp` of MAIN.agc.bin, Luminary099.bin and AP11ROPE.bin, pairwise: 0 differing bytes, exit 0. All three have SHA-256 `1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e`. VERIFIED.

**What this establishes:** the transcribed assembly source, built with the pinned yaYUL, gives exactly the same words as two separately transcribed octal listings, one of which is AP11ROPE.

**What it does not establish:**
1. That AP11ROPE equals the physical flight rope. It is a 1971 printout of a recreation, not a dump of flown hardware.
2. That the two transcriptions are fully independent. The AP11ROPE file was reconciled against Luminary099 where they differed, so a shared error is unlikely but possible.
3. That the parity bit was checked: oct2bin removes it and the .bin files do not keep it.
4. Anything about the correctness of the emulator.

## M1. Authentic instruction execution (VERIFIED)

The emulator's command line was taken from the real `--help` output (`04_`). It has no `--core` flag. The usage is `yaAGC [options] exec-ropes-file`. In default (debug) mode it reads gdb-style commands on stdin. `--nodebug` runs freely and serves I/O on TCP port 19697.

Command (fresh directory, `--no-resume` so no saved core image is loaded):
```sh
yaAGC --no-resume --symbols=MAIN.agc.symtab MAIN.agc.bin < 11_M1_cmds.txt   # 60 × "step"
```
Results (`11_M1_source_step_trace.log`, exit 0):
- Execution starts at Z=04000 (GOJAM vector) and goes to `MAIN () at INTERRUPT_LEAD_INS.agc:36` → `TCF GOPROG` → `GOPROG () at FRESH_START_AND_RESTART.agc:215 INCR REDOCTR`, then runs through `LIGHTSET`, `NONAVKEY`, `DORSTART`, `STARTSUB` and `STARTSB2`.
- Registers after the 1-instruction stepi run (`10_`): FB=0x1400 (bank 05), Z=0x05B8 (02670). This matches the listing address `05,2667 GOPROG` plus 1.
- Conditional branches follow the data. For example, `BZF DORSTART` is taken because ERESTORE=0 in clean erasable memory, and `BZF NONAVKEY` is taken because channel NAVKEYIN reads 0.

**What this establishes:** the pinned yaAGC fetches and executes Luminary099 machine words from fixed memory. The order of execution matches the original source listing line by line, including bank switching and data-dependent branches.

**What it does not establish:** that yaAGC is cycle-exact against real hardware (timing is ASSUMED to follow yaAGC's documented 11.72 µs memory cycle), or anything about guidance.

## M2. Mission-software behaviour via DSKY (VERIFIED)

Protocol details checked against the pinned source:
- **Packet:** 4 bytes `00pppppp 01pppddd 10dddddd 11dddddd`, with a 9-bit channel (u-bit plus 8 bits) and 15-bit data. Source: `yaAGC/agc_utilities.c` `FormIoPacket` / `ParseIoPacket`.
- **Keys:** a keystroke is written to channel 015, which sets `InterruptRequests[5]` (KEYRUPT). Source: `yaAGC/SocketAPI.c:240`. PRO is not a keycode; it is channel 032 bit 14, sent with a mask packet on 0432. Sources: `yaDSKY2.cpp` `OutputPro`, and the AGC source comment.
- **Keycodes**, from the AGC source itself (`PINBALL_GAME__BUTTONS_AND_LIGHTS.agc` lines 383–395) and matching `yaDSKY2.cpp`: digits 1–9 are 1–9, 0=16, VERB=17, RSET=18, KEY REL=25, +=26, −=27, ENTR=28, CLR=30, NOUN=31.
- **Display:** channel 010 word `AAAABCCCCCDDDDD` (PINBALL lines 398–403). The digit relay codes are the low 5 bits of `RELTAB` (`FIXED-FIXED_CONSTANT_POOL.agc:68`): 0=21, 1=3, 2=25, 3=27, 4=15, 5=30, 6=28, 7=19, 8=29, 9=31, blank=0. The AAAA row map comes from `yaDSKY2.cpp:1953–2083`.

Run (`20_`, `21_`):
```sh
yaAGC --nodebug --no-resume --show-alarms --port=19697 MAIN.agc.bin &
python3 m2_dsky_client.py 19697 21_M2_dsky_transcript.jsonl   # exit 0; yaAGC stopped with SIGTERM (143)
```
The script sends `V35E` (lamp test), waits 8 s, sends `RSET`, then `V16N36E` (display the AGC clock). The transcript has 3475 lines, with every received packet and its decoded display state.

Observed, all decoded from channel 010 words sent by the AGC:
- The keystrokes echo on the display as typed: VERB shows `3 ` then `35`.
- V35: every field fills with `88`/`88888` (t≈6.3–6.7 s).
- V16N36: VERB 16, NOUN 36, R1 `00000`, R2 `00000`, and R3 counting up by 1.00 about once per wall-clock second: `01866` → `01966` → … → `02466`.

**What this establishes:** keyboard interrupts, PINBALL verb/noun parsing, display formatting and the AGC's own clock (TIME1/TIME2) all run inside the authentic program, and their outputs can be read programmatically.

**What it does not establish:**
- Any guidance program. P63 needs an aligned IMU, a state vector and pad loads, which were not supplied.
- How R3's low digits were refreshed: they only change when the AGC rewrites that relay pair. This is ASSUMED to be normal PINBALL behaviour, not checked.
- yaAGC (run with `--show-alarms`) printed nothing during the 24 s run (`20_`; the CMD line in that log leaves out the flag, and a note at the end records this), but alarm-free operation over longer runs is NOT RUN.

## M3. Physics coupling (NOT RUN — investigation only)

Virtual AGC's `Contributed/LM_Simulator` (Tcl/Tk, v0.94, 2007; needs a GUI, so it was not run here) already implements these interfaces. They were found by reading the source:
- **IMU:** gimbal CDU counters on channels 032/033/034 (PCDU/MCDU) and PIPA counters 037/040/041 (PINC/MINC), as unprogrammed counter increments (`AGC_IMU.tcl`). Gyro coarse align on 0174–0176 and fine align on 0177 (`lm_simulator.tcl:796–800`).
- **RCS:** jet-select output channels 05 and 06 decoded into the 16 quad thrusters (`AGC_Attitude.tcl` `update_RCS`). Rotational dynamics are in `dynamic_simulation`.
- **Crew inputs:** RHC on 0166/0167/0170, discretes on channels 030–033 (`AGC_Crew_Inputs.tcl`, `AGC_System_Inputs.tcl`).
- **DSKY:** keycodes on 015 and PRO on 032 (`AGC_DSKY.tcl`).
- **Gaps found:**
  - Descent-engine parameters exist (`lm_simulator.ini`), but no code was found that reads the AGC's THRUST drive output. Landing radar appears only as display labels. A closed descent loop (throttle and radar) is therefore NOT implemented upstream; this is ASSUMED from the search and needs confirming by a full read.
  - THC translation affects the PIPAs (ChangeLog v0.94).

Pass criterion defined for a later phase: with logged runs, a change in the AGC's RCS jet or throttle output on 05/06 or THRUST must cause a measurable change in simulated attitude or velocity, and the resulting CDU/PIPA counts must be read back by the AGC (for example, V16N20 or V16N21 values changing).

## W. WebAssembly option (evaluated separately)

- The pinned upstream already includes a WASI target (`yaAGC/Makefile` `yaAGC.wasm`, `yaAGC/wasm.c`, added 2021). It exports `cpu_reset`, `set_fixed`, `cpu_step`, `packet_write`, `packet_read`, `get_erasable_ptr`, `malloc` and `free`. It uses the same `agc_engine.c` as the native build. moonjs is not needed.
- **Build:** `make WASI=yes WASI_SDK_PATH=… yaAGC.wasm` with wasi-sdk-24.0, exit 0 (`30_`). SHA-256 is in `07_`. VERIFIED.
- **Run** (`31_`): the Node harness loads the same `MAIN.agc.bin`, stubs the WASI imports (the module uses them only for libc stdio), and sends the same keystroke script, with simulated time of 85333 steps per second. Exit 0, 3467 lines.
- **Comparison** (`32_`): native and WebAssembly runs each produced 35 distinct display states. The first 27 (boot, V35 lamp test, the V16N36 entry, the first clock frame) are identical. The first difference is the value of the clock itself (`01888` native versus `01788` WebAssembly). This is expected, because native runs on wall-clock time with socket delay while WebAssembly runs on simulated time. VERIFIED as behaviourally equivalent for this test.
- **Not established:** an instruction-by-instruction trace comparison between the native and WebAssembly builds (NOT RUN), and browser performance or SharedArrayBuffer and cross-origin-isolation requirements (NOT RUN; the module imports shared memory).

## Limitations and next tests

- `make` must be run with `cc=gcc` in this layout, and the warning in `05b_` needs to be explained.
- For an exact native versus WebAssembly match, run both builds by step count instead of wall clock. The native build would need the debugger `step N` mode, or a small harness linked to `libyaAGC.a`.
- P63 entry requires pad-load erasable initialisation. Next, look for existing Virtual AGC scenario or core files for Luminary 99 (the `scenarios/` directory, not extracted here) before writing any of our own.
- Nothing in Phase 1 shows that the AGC controls a landing.
