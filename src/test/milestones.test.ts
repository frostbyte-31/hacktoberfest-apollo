import { describe, expect, it } from "vitest";
import { milestones } from "@/lib/milestones";
import { phase9 } from "@/lib/replay";

describe("Phase 9 recorded milestones", () => {
  it("are all present in the recorded run", () => {
    for (const m of milestones) expect(Number.isFinite(m.t)).toBe(true);
  });
  it("keep the recorded order: P51, alignment, P63, then 01406", () => {
    const ts = milestones.map((m) => m.t);
    expect([...ts].sort((a, b) => a - b)).toEqual(ts);
  });
  it("alarm 01406 is recorded only after P63 selection", () => {
    const p63 = phase9.events.find((e) => e.text === "MODREG (PROG) = 63")!.t;
    const alarm = phase9.events.find((e) => e.text === "FAILREG1 = 01406")!.t;
    expect(alarm).toBeGreaterThan(p63);
  });
});
