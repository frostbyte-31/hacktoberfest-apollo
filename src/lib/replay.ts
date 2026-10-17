import data from "@/data/replay.json";

export type Frame = { t: number; omega: number[]; gimbals: number[]; jets: number[]; cdu: number[] };
export type Event = { t: number; kind: string; text: string };
export type Run = {
  name: string; source: string; sha256: string; frames: Frame[]; events: Event[];
  sensor_generated: number; sensor_delivered: number; final_cdu: number[];
};
/** One recorded AGC memory sample (Phase 9). prog/verb/noun are MODREG/VERBREG/NOUNREG as stored. */
export type State9 = { t: number; prog: number; verb: number; noun: number; f0: number; f1: number; f2: number; flag3: number; refs: boolean };
export type Run9 = { name: string; source: string; sha256: string; states: State9[]; events: Event[]; final_refsmmat: number[] };

export const runs = data.phase7 as unknown as Record<"closed" | "feedback_off", Run>;
export const phase8 = data.phase8 as unknown as { source: string; sha256: string; events: Event[]; final: { MODREG: number; FAILREG0: number; FAILREG1: number; FAILREG2: number; THRUST: number } };
export const phase9 = (data as unknown as { phase9: Run9 }).phase9;

/** Latest frame at or before t (recorded values only, no interpolation). */
export function frameAt(run: Run, t: number): Frame {
  let f = run.frames[0]!;
  for (const x of run.frames) { if (x.t <= t) f = x; else break; }
  return f;
}
export function stateAt(run: Run9, t: number): State9 {
  let s = run.states[0]!;
  for (const x of run.states) { if (x.t <= t) s = x; else break; }
  return s;
}

/** AGC CDU counts are one's-complement 15-bit; return signed counts. */
export function cduSigned(v: number): number {
  return v & 0o40000 ? -(~v & 0o37777) : v;
}

export const oct = (v: number, w = 5) => v.toString(8).padStart(w, "0");
/** 077777 is one's-complement minus zero: no program number stored. */
export const two = (v: number) => (v === 0o77777 ? "--" : String(v).padStart(2, "0"));
export const REFSMFLG = 0o10000;
