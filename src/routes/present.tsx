import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { DskyFace } from "@/components/console";
import { phase9, REFSMFLG, stateAt } from "@/lib/replay";
import { milestones } from "@/lib/milestones";

export const Route = createFileRoute("/present")({
  head: () => ({
    meta: [
      { title: "Presentation — Apollo LM AGC Project" },
      { name: "description", content: "Full-screen walkthrough of our recorded Luminary 099 experiments and what remains before landing." },
      { property: "og:title", content: "Presentation — Apollo LM AGC Project" },
      { property: "og:description", content: "Full-screen walkthrough of our recorded Luminary 099 experiments." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Present,
});

function Replay({ from, to }: { from: number; to: number }) {
  const [t, setT] = useState(from);
  useEffect(() => { setT(from); const id = setInterval(() => setT((v) => (v >= to ? to : v + 0.4)), 50); return () => clearInterval(id); }, [from, to]);
  const s = stateAt(phase9, t);
  const ev = useMemo(() => phase9.events.filter((e) => e.t <= t && e.t >= from - 1 && e.kind !== "input").slice(-6), [t, from]);
  return (
    <div className="grid w-full max-w-5xl gap-6 md:grid-cols-[320px_minmax(0,1fr)]">
      <div className="rounded-sm border border-border bg-card p-3"><DskyFace prog={s.prog} verb={s.verb} noun={s.noun} regs={[s.f0, s.f1, s.f2]} alarm={s.f1 !== 0} />
        <p className="mt-2 font-mono text-xs text-accent">REFSMFLG {s.flag3 & REFSMFLG ? "SET" : "CLEAR"} · T+{t.toFixed(1)} s</p></div>
      <ol className="space-y-1 font-mono text-sm">{ev.map((e, i) => <li key={i} className={`animate-in fade-in ${e.kind === "alarm" ? "text-destructive" : e.kind === "state" ? "text-primary" : ""}`}>T+{e.t.toFixed(1)}  {e.text}</li>)}</ol>
      <p className="font-mono text-[10px] text-muted-foreground md:col-span-2">RECORDED · {phase9.source} · sha256 {phase9.sha256.slice(0, 16)}…</p>
    </div>
  );
}

const m = (i: number) => milestones[i]!.t;
const slides: { kicker: string; title: string; body: React.ReactNode }[] = [
  { kicker: "PROJECT", title: "Running Apollo 11's real flight software", body: <p>In July 1969 the Lunar Module's guidance computer ran Luminary 099. We assembled that exact program and ran it, unchanged, in an emulator — then tested how far it can go toward a landing, recording everything as evidence.</p> },
  { kicker: "THE COMPUTER", title: "The AGC and its DSKY", body: <p>The crew spoke to the computer with VERB/NOUN commands on the DSKY. PROG shows the running program, VERB the action, NOUN the data. Everything shown next is read from the AGC's own memory in a recorded run.</p> },
  { kicker: "PHASE 9 · RECORDED", title: "P51: aligning the platform with the stars", body: <Replay from={m(1) - 1} to={m(3) + 2} /> },
  { kicker: "PHASE 9 · RECORDED", title: "P63 selected — then alarm 01406", body: <Replay from={m(4) - 4} to={m(5) + 3} /> },
  { kicker: "HONEST STATUS", title: "Demonstrated vs remaining", body: (
    <div className="grid gap-6 text-left md:grid-cols-2">
      <ul className="list-disc space-y-1 pl-5"><li className="list-none font-display tracking-widest text-accent">DEMONSTRATED</li><li>Authentic Luminary 099 execution</li><li>RCS feedback on yaw and pitch</li><li>P51 alignment by original code</li><li>P63 readiness check passed (no 00220)</li></ul>
      <ul className="list-disc space-y-1 pl-5"><li className="list-none font-display tracking-widest text-destructive">NOT YET</li><li>Descent targeting data · 01406 abort</li><li>Engine thrust & lunar gravity</li><li>Landing radar · P64/P66</li><li>Any landing</li></ul>
      <p className="text-sm text-muted-foreground md:col-span-2">Star geometry synthetic (ASSUMED). ~30 Phase 1–6 logs missing; Milestone 1 integrity check cannot run.</p>
    </div>) },
  { kicker: "QUESTIONS", title: "Explore further", body: <div className="flex flex-wrap justify-center gap-3"><Link to="/learn" className="rounded-sm bg-primary px-5 py-2 font-display tracking-widest text-primary-foreground">TUTORIALS</Link><Link to="/evidence" className="rounded-sm border border-border px-5 py-2 font-display tracking-widest">EVIDENCE</Link><Link to="/" className="rounded-sm border border-border px-5 py-2 font-display tracking-widest">MISSION CONTROL</Link></div> },
];

function Present() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "ArrowRight" || e.key === " ") setI((v) => Math.min(slides.length - 1, v + 1)); if (e.key === "ArrowLeft") setI((v) => Math.max(0, v - 1)); };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);
  const s = slides[i]!;
  return (
    <main className="flex min-h-screen flex-col bg-space p-6 text-foreground">
      <div className="flex items-center justify-between font-mono text-xs text-muted-foreground">
        <Link to="/">✕ Exit</Link><span>{i + 1} / {slides.length} · ← → keys</span>
        <button onClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen())}>⛶ Full screen</button>
      </div>
      <section key={i} className="flex flex-1 animate-in fade-in flex-col items-center justify-center gap-6 text-center">
        <p className="font-mono text-sm tracking-[0.4em] text-primary">{s.kicker}</p>
        <h1 className="max-w-4xl font-display text-5xl font-bold tracking-wide md:text-6xl">{s.title}</h1>
        <div className="max-w-5xl text-lg leading-relaxed text-muted-foreground">{s.body}</div>
      </section>
      <div className="flex justify-between">
        <button onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0} className="rounded-sm border border-border px-4 py-1.5 font-display tracking-widest disabled:opacity-30">◂ PREV</button>
        <button onClick={() => setI((v) => Math.min(slides.length - 1, v + 1))} disabled={i === slides.length - 1} className="rounded-sm bg-primary px-4 py-1.5 font-display tracking-widest text-primary-foreground disabled:opacity-30">NEXT ▸</button>
      </div>
    </main>
  );
}
