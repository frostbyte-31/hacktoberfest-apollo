export type Status = "VERIFIED" | "ASSUMED" | "NOT RUN" | "BLOCKED" | "PARTIAL";

export type Phase = {
  n: string; title: string; objective: string; status: Status;
  shown: string[]; notShown: string[]; tests: string; paths: string[]; caveat?: string;
};

const MISSING_LOGS =
  "About 30 historical .log files from Phases 1–6 are missing (a global *.log ignore rule kept them out of version control and they were not recoverable). They have not been recreated. The Milestone 1 integrity suite therefore refuses to run.";

export const phases: Phase[] = [
  { n: "1", title: "Proof of execution", status: "VERIFIED", objective: "Build the pinned Virtual AGC tools and run genuine Luminary 099 at least once with a preserved log.",
    shown: ["Pinned virtualagc commit f577e3f built (yaYUL, yaAGC)", "Assembled Luminary 099 byte-identical to the reference rope (SHA-256 1f5326e0…)", "DSKY socket input showed the AGC clock (V16N36E)", "WebAssembly run matched native for the first 27 display states"],
    notShown: ["Any mission program beyond startup and basic DSKY verbs"], tests: "Milestone 1 integrity suite — CANNOT RUN (missing logs)",
    paths: ["docs/PHASE1_PROOF_PLAN.md", "docs/phase1-evidence/"], caveat: MISSING_LOGS },
  { n: "2", title: "Powered-descent feasibility", status: "PARTIAL", objective: "Find descent starting data and test P63/P64/P66; compare native vs WebAssembly.",
    shown: ["P63 entry reaches P63LM and the R02 readiness check", "Native, Node and Chromium transcripts matched byte-for-byte"],
    notShown: ["Authentic pre-PDI state vector (not in repository)", "Ignition, P64, P66 (NOT RUN)", "Throttle / landing radar interfaces (empty hooks)"],
    tests: "Phase 2 validation scripts", paths: ["docs/PHASE2_POWERED_DESCENT_FEASIBILITY.md", "docs/phase2-evidence/"], caveat: MISSING_LOGS },
  { n: "3", title: "Instrument feedback loop", status: "VERIFIED", objective: "Close a minimum loop between AGC commands and a synthetic IMU gimbal.",
    shown: ["V41N20 commands moved the gimbal; CDU feedback returned; Luminary took its success branch", "Suppressing feedback caused failure"],
    notShown: ["Spacecraft attitude control (this was instrument alignment only)"], tests: "7 tests passed at the time", paths: ["docs/PHASE3_CLOSED_LOOP_FEASIBILITY.md", "docs/phase3-evidence/"], caveat: MISSING_LOGS },
  { n: "4", title: "Control-path audit", status: "BLOCKED", objective: "Check whether the AGC actually drives RCS jets.",
    shown: ["Phase 3 runs contained no nonzero RCS packets", "Upstream yaw model responds to injected jet flags", "Blocker found: IMU marked unusable (IMODES33 bit 6), STARTDAP never ran"],
    notShown: ["AGC-driven vehicle loop"], tests: "6 tests passed at the time", paths: ["docs/PHASE4_CONTROL_PATH_VALIDATION.md", "docs/phase4-evidence/"], caveat: MISSING_LOGS },
  { n: "5", title: "IMU readiness & autopilot", status: "VERIFIED", objective: "Find the IMU blocker and apply only a source-justified correction.",
    shown: ["One-bit channel 030 correction (IMU OPERATE, active-low)", "Original ISSUP cleared the fault; STARTDAP ran; nonzero RCS output", "Closed-loop vs feedback-off causality; exact replay (yaw only)"],
    notShown: ["Physical fidelity of LM-7 model (ASSUMED)", "Descent, throttle, radar, three-axis, browser loop"], tests: "12 tests passed at the time", paths: ["docs/PHASE5_IMU_READINESS.md", "docs/phase5-evidence/"], caveat: MISSING_LOGS },
  { n: "6", title: "Reproducible demonstration", status: "VERIFIED", objective: "Make the Phase 5 loop repeatable and inspectable.",
    shown: ["Three fresh runs and a bundle-only launch reproduced Phase 5 traces byte-for-byte"], notShown: ["Anything beyond single-axis yaw"],
    tests: "11 tests passed at the time", paths: ["docs/PHASE6_DEMONSTRATION.md", "docs/phase6-evidence/"], caveat: MISSING_LOGS },
  { n: "7", title: "Second axis (pitch)", status: "VERIFIED", objective: "Bounded pitch-axis feedback experiment.",
    shown: ["AGC-driven pitch feedback", "Disconnected-feedback and opposite-direction controls", "Exact replay; yaw baseline byte-identical to Phase 6"],
    notShown: ["Simultaneous pitch+yaw, roll-only, descent, browser loop (NOT RUN)", "Model fidelity (ASSUMED)"], tests: "10 tests + 11 analysis checks", paths: ["docs/PHASE7_MULTI_AXIS_VALIDATION.md", "docs/phase7-evidence/"] },
  { n: "8", title: "Powered-descent attempt", status: "BLOCKED", objective: "Select P63 from the Phase 5 startup and record the outcome.",
    shown: ["V37E63E accepted; P63 selected", "R02 raised alarm 00220: REFSMMAT not valid (REFSMFLG clear)"], notShown: ["Anything past R02 (NOT RUN)", "Meaning of a channel-014 signal seen at program change (ASSUMED)"],
    tests: "7 tests", paths: ["docs/PHASE8_POWERED_DESCENT_FEASIBILITY.md", "docs/phase8-evidence/"] },
  { n: "9", title: "IMU alignment (P51)", status: "VERIFIED", objective: "Produce a valid REFSMMAT through the original P51 two-star alignment, then retry P63.",
    shown: ["Two driver bugs fixed (PROCEED bit; angle field width)", "P51 completed; AGC itself populated REFSMMAT and set REFSMFLG", "V37E63E selected P63 with no alarm 00220", "P63 then aborted: POODOO 01406 (ignition algorithm) — descent targeting not loaded", "Exact replay (alignment-06 identical to -05)"],
    notShown: ["Star geometry is synthetic (ASSUMED)", "Ignition, P64/P66, descent, landing (NOT RUN)"], tests: "13 tests passed; 1163 prior evidence files fingerprinted, 0 mismatches",
    paths: ["docs/PHASE9_IMU_ALIGNMENT.md", "docs/phase9-evidence/runs/alignment.jsonl … alignment-06.jsonl"] },
];

export type Help = { title: string; what: string; real: string; sim: string; evidence: string; missing: string; tech?: string };
export const help: Record<string, Help> = {
  lm: { title: "Lunar Module picture", what: "A drawing of the Apollo Lunar Module above the Moon.", real: "The LM carried two astronauts from lunar orbit to the surface.",
    sim: "The drawing is decoration (MOCK VISUAL). In Phase 7 runs its tilt follows the recorded pitch angle of our simulated vehicle; in the Phase 9 run nothing moved, so it stays still.",
    evidence: "docs/phase7-evidence/runs/closed.jsonl (pitch gimbal)", missing: "Height, position, descent and landing are not simulated.", tech: "Pitch = recorded model gimbal Y, wrapped to ±180°. No interpolation between 0.1 s samples." },
  dsky: { title: "DSKY", what: "The astronauts' keyboard and display for the guidance computer.", real: "Crews typed VERB/NOUN commands and read numbers and alarms on it.",
    sim: "We show values read from the AGC's memory during a recorded run: the program number, the verb and noun the AGC was using, and alarm registers.",
    evidence: "docs/phase9-evidence/runs/alignment-05.jsonl (sample rows)", missing: "We don't decode the real display relays, so lamp and digit rows are shown from memory registers, not from the physical display.",
    tech: "PROG = MODREG, VERB = VERBREG, NOUN = NOUNREG, rows = FAILREG0/1/2 in octal. PROG ALARM lamp is inferred from FAILREG being nonzero. MODREG 77777 (minus zero) is shown as --." },
  telemetry: { title: "Telemetry", what: "Numbers describing the vehicle at this moment.", real: "Flight controllers watched telemetry radioed from the spacecraft.",
    sim: "Only values that were really recorded are shown: rotation rates, gimbal angles, the AGC's angle counters and jet commands.", evidence: "Phase 7 run files",
    missing: "Altitude, speeds, fuel, engine thrust and distance to touchdown are NOT MODELLED.", tech: "CDU counts are 15-bit one's-complement, shown signed. Jets are raw channel 005/006 words in octal." },
  timeline: { title: "Event timeline", what: "The list of things the computer and our test driver did, in order.", real: "Flight logs recorded crew actions and computer events.",
    sim: "Each line comes from the recorded run file. Times are AGC time (machine cycles × 11.72 µs).", evidence: "Run file shown under the panel",
    missing: "Times are emulator time, not Apollo 11 mission time.", tech: "Driver steps, AOT mark pulses and changes in MODREG / FAILREG / FLAGWRD3 / REFSMMAT are extracted by tools/replay/extract_replay.py." },
  playback: { title: "Playback", what: "Controls to replay a recorded run.", real: "—", sim: "This is a RECORDED REPLAY. Nothing here talks to a running emulator.",
    evidence: "SHA-256 of each run file is shown so you can check it.", missing: "No live AGC connection exists in this app." },
};

export type Quiz = { q: string; options: string[]; answer: number; why: string };
export type Tutorial = {
  id: string; title: string; objective: string; body: string[]; diagram: "arch" | "agc" | "gnc" | "dsky" | "imu" | "loop" | "phase9" | "remaining";
  example: string; verified: string[]; notYet: string[]; quiz: Quiz[];
};

export const tutorials: Tutorial[] = [
  { id: "architecture", title: "Apollo 11 architecture", diagram: "arch", objective: "Know the main pieces and how they connect.",
    body: ["Apollo 11 had two crewed spacecraft: the Command Module (stayed in lunar orbit) and the Lunar Module (went down to the surface).", "Each carried an Apollo Guidance Computer (AGC). The LM's AGC ran a program called Luminary; Apollo 11 flew Luminary version 099.", "The crew talked to the AGC through the DSKY (display and keyboard). The IMU, a set of spinning gyroscopes on gimbals, told the AGC which way the spacecraft was pointing."],
    example: "We run the real Luminary 099 program, assembled from the public source, inside the yaAGC emulator. Its assembled output is byte-identical to the reference copy.",
    verified: ["Luminary 099 runs in the emulator (Phase 1)", "DSKY commands are accepted (Phases 1, 8, 9)"], notYet: ["Command Module software is not used", "No real hardware is involved"],
    quiz: [{ q: "Which spacecraft ran Luminary?", options: ["Command Module", "Lunar Module", "Saturn V"], answer: 1, why: "Luminary was the LM's program; the Command Module ran Colossus." }] },
  { id: "agc", title: "How the AGC works", diagram: "agc", objective: "Follow the path from source code to a running program.",
    body: ["Programmers wrote AGC assembly language — human-readable instructions.", "An assembler (yaYUL) converts it into machine instructions: numbers the computer executes.", "On Apollo those numbers were woven into 'rope memory'. We instead load them into an emulator — a program that behaves like the AGC hardware.", "The AGC keeps working values in erasable memory, runs several jobs in turn, and reads keys and writes the display through I/O channels."],
    example: "When our test driver 'presses' PROCEED, it sets channel 032 bit 14. Phase 9 found the driver had been setting bit 15 by mistake, which is why the computer ignored it.",
    verified: ["Source → assembler → binary chain reproduced (Phase 1)", "Native and WebAssembly emulators agree (Phase 2)"], notYet: ["Browser version of the coupled vehicle experiments (NOT RUN)"],
    quiz: [{ q: "What does an emulator do?", options: ["Translates English to code", "Behaves like the original hardware so its programs can run", "Draws the DSKY"], answer: 1, why: "yaAGC mimics the AGC hardware so the unchanged Luminary binary can execute." }] },
  { id: "gnc", title: "Guidance, navigation and control", diagram: "gnc", objective: "Tell the three jobs apart.",
    body: ["Navigation: where am I, which way am I pointing, how am I moving?", "Guidance: given that, what should I do next?", "Control: fire jets or engines so the vehicle actually does it."],
    example: "Car analogy: GPS is navigation, the route planner is guidance, your hands on the wheel are control. In our project, the IMU angles are navigation inputs and RCS jet commands are control outputs.",
    verified: ["Control loop through RCS jets on yaw (Phase 5–6) and pitch (Phase 7)"], notYet: ["Descent guidance never ran to completion", "No translational navigation (position/velocity)"],
    quiz: [{ q: "Firing a thruster to turn is…", options: ["Navigation", "Guidance", "Control"], answer: 2, why: "Issuing commands to produce behaviour is control." }] },
  { id: "dsky", title: "Understanding the DSKY", diagram: "dsky", objective: "Read PROG, VERB, NOUN and alarms.",
    body: ["PROG shows the major program running (for example 51 = IMU alignment, 63 = braking phase of descent).", "VERB says what to do (display, load, run…); NOUN says what data it applies to.", "ENTER finishes a command. PROCEED tells a waiting program to continue.", "A flashing VERB/NOUN means the computer is waiting for the crew.", "PROG ALARM lights when the computer records an alarm code."],
    example: "V37E63E means: VERB 37 (change program), ENTER, 63, ENTER. That is the exact sequence our driver keyed in Phases 8 and 9 to select P63.",
    verified: ["V37 program changes, V21/V22 data loads and PROCEED all accepted (Phase 9)"], notYet: ["We read memory registers, not the physical display relays"],
    quiz: [{ q: "What does a flashing VERB/NOUN mean?", options: ["An error", "The computer is waiting for crew response", "The DSKY is broken"], answer: 1, why: "Flashing requests crew action, such as PROCEED or entering data." }] },
  { id: "imu", title: "The IMU and REFSMMAT", diagram: "imu", objective: "Understand why alignment matters.",
    body: ["The IMU holds a platform steady in space. To use it, the AGC must know how that platform is oriented relative to the stars.", "That relationship is a 3×3 table of numbers called REFSMMAT. A flag, REFSMFLG, says whether it is valid.", "Program P51 builds REFSMMAT from two star sightings through the Alignment Optical Telescope (AOT)."],
    example: "In Phase 9 we gave P51 two catalog stars and pressed the AOT mark buttons through the normal interface. P51's own code computed REFSMMAT and set REFSMFLG. The star angles were computed by us from the catalog (synthetic, ASSUMED) — not real sky observations.",
    verified: ["REFSMMAT populated and REFSMFLG set by original P51 code (Phase 9)"], notYet: ["Real star geometry for a specific mission time", "Physical IMU drift"],
    quiz: [{ q: "What sets REFSMFLG in Phase 9?", options: ["Our script writes memory", "The original P51 code", "The DSKY"], answer: 1, why: "No memory writes were used; the trace shows P51 setting the flag." }] },
  { id: "feedback", title: "Feedback control", diagram: "loop", objective: "See how a command and a measurement form a loop.",
    body: ["The AGC commands an RCS jet. The simulated vehicle starts to rotate.", "The IMU senses the new angle and sends counts back to the AGC.", "The AGC compares the angle to what it wants and adjusts the next command. That cycle is feedback."],
    example: "Switch the dashboard between 'feedback connected' and 'disconnected' (Phase 7). With feedback disconnected, the AGC never sees the motion it causes.",
    verified: ["Feedback causality for yaw and pitch, single axis at a time"], notYet: ["Main engine and powered-descent physics", "All axes together"],
    quiz: [{ q: "If you cut the IMU feedback, what happens?", options: ["Nothing changes", "The AGC can't see the effect of its commands", "The LM lands"], answer: 1, why: "Without measurements returning, the loop is open." }] },
  { id: "phase9", title: "What happened in Phase 9?", diagram: "phase9", objective: "Walk through the recorded sequence.",
    body: ["The driver selected P51 (V37E51E) and pressed PROCEED.", "For each of two stars it loaded a star code and AOT angles, then sent mark pulses.", "P51 computed the alignment: REFSMMAT filled and REFSMFLG set.", "The driver selected P63. This time there was no alarm 00220 — the Phase 8 blocker was gone.", "Shortly after, P63 aborted with POODOO alarm 01406 (bad return from the ignition algorithm) because descent targeting data was never loaded."],
    example: "Clearing 00220 is a genuine result: the computer accepted its own alignment. But an abort one second later shows powered descent is not working.",
    verified: ["Order of events in alignment-05; identical replay alignment-06"], notYet: ["Descent targeting data, ignition, landing"],
    quiz: [{ q: "Did Phase 9 achieve powered descent?", options: ["Yes", "No — P63 aborted with 01406", "Partly — it landed roughly"], answer: 1, why: "P63 was selected and passed its readiness check, then aborted before any descent." }] },
  { id: "remaining", title: "What remains before landing?", diagram: "remaining", objective: "See the outstanding work honestly.",
    body: ["Provide valid descent-targeting data through the authentic software.", "Understand and resolve the P63 ignition-algorithm abort (01406).", "Connect AGC engine commands to a justified thrust model.", "Simulate motion under lunar gravity.", "Feed back sensor and landing-radar data.", "Validate the descent control loop.", "Test the browser version against the native one."],
    example: "None of these steps has been completed.", verified: ["Prerequisite: valid alignment (Phase 9)"], notYet: ["All seven items above"],
    quiz: [{ q: "Is the thrust model implemented?", options: ["Yes", "No"], answer: 1, why: "Powered-descent physics are NOT MODELLED." }] },
];
