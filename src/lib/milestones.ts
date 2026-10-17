import { phase9, type Event } from "@/lib/replay";

/** Phase 9 milestones, matched against recorded events in chronological order. */
const MILESTONES: [string, (e: Event) => boolean][] = [
  ["AGC startup (Phase 5 fixture)", (e) => e.text.startsWith("MODREG (PROG) = 32767")],
  ["P51 entered", (e) => e.text === "MODREG (PROG) = 51"],
  ["Star data and marks entered", (e) => e.text.startsWith("Star 2: PROCEED after marks")],
  ["REFSMFLG set · REFSMMAT populated", (e) => e.text.startsWith("REFSMFLG SET")],
  ["P63 selected — no alarm 00220", (e) => e.text === "MODREG (PROG) = 63"],
  ["Alarm 01406 — P63 aborted", (e) => e.text === "FAILREG1 = 01406"],
];
export const milestones = MILESTONES.map(([l, m]) => ({ label: l, t: phase9.events.find(m)?.t ?? Infinity }));

