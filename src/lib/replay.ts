import data from "@/data/replay.json";

export type Frame = { t: number; omega: number[]; gimbals: number[]; jets: number[]; cdu: number[] };
export type Event = { t: number; kind: string; text: string };
export type Run = {
  name: string; source: string; sha256: string; frames: Frame[]; events: Event[];
  sensor_generated: number; sensor_delivered: number; final_cdu: number[];
};

export const runs = data.phase7 as unknown as Record<"closed" | "feedback_off", Run>;
export const phase8 = data.phase8 as unknown as { source: string; sha256: string; events: Event[]; final: { MODREG: number; FAILREG0: number; FAILREG1: number; FAILREG2: number; THRUST: number } };

/** Latest frame at or before t (recorded values only, no interpolation). */
export function frameAt(run: Run, t: number): Frame {
  let f = run.frames[0]!;
  for (const x of run.frames) { if (x.t <= t) f = x; else break; }
  return f;
}

/** AGC CDU counts are one's-complement 15-bit; return signed counts. */
export function cduSigned(v: number): number {
  return v & 0o40000 ? -(~v & 0o37777) : v;
}

export const oct = (v: number, w = 5) => v.toString(8).padStart(w, "0");
