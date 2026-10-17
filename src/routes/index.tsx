import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { LunarScene } from "@/components/LunarScene";
import { cduSigned, frameAt, oct, phase8, runs, type Event } from "@/lib/replay";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "LM Console — Recorded AGC Replay" },
      { name: "description", content: "Recorded replay of Luminary 099 attitude feedback and the Phase 8 P63 blocker." },
      { property: "og:title", content: "LM Console — Recorded AGC Replay" },
      { property: "og:description", content: "Recorded replay of Luminary 099 attitude feedback and the Phase 8 P63 blocker." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Console,
});

type RunKey = "closed" | "feedback_off";

function Panel({ title, tag, children, className = "" }: { title: string; tag?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-sm border border-border bg-card ${className}`}>
      <header className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5">
        <h2 className="truncate font-display text-sm font-semibold tracking-[0.2em] text-muted-foreground uppercase">{title}</h2>
        {tag}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

const Tag = ({ kind }: { kind: "rec" | "none" | "mock" }) => {
  const map = {
    rec: ["RECORDED", "border-accent text-accent"],
    none: ["NO DATA", "border-muted-foreground text-muted-foreground"],
    mock: ["MOCK VISUAL", "border-mock text-mock"],
  } as const;
  return <span className={`shrink-0 rounded-sm border px-1.5 font-mono text-[10px] tracking-widest ${map[kind][1]}`}>{map[kind][0]}</span>;
};

function Readout({ label, value, unit, dim }: { label: string; value: string; unit?: string; dim?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/50 py-1.5 last:border-0">
      <span className="font-display text-xs tracking-widest text-muted-foreground uppercase">{label}</span>
      <span className={`font-mono text-sm ${dim ? "text-muted-foreground" : "seg text-accent"}`}>
        {value} {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
      </span>
    </div>
  );
}

function Console() {
  const [runKey, setRunKey] = useState<RunKey>("closed");
  const run = runs[runKey];
  const t0 = run.frames[0].t, t1 = run.frames[run.frames.length - 1].t;
  const [t, setT] = useState(t0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => setT(runs[runKey].frames[0].t), [runKey]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT((v) => (v + 0.05 * speed >= t1 ? (setPlaying(false), t1) : v + 0.05 * speed)), 50);
    return () => clearInterval(id);
  }, [playing, speed, t1]);

  const f = frameAt(run, t);
  const events = useMemo(() => run.events.filter((e) => e.t <= t && e.t >= t0 - 0.2).slice(-14).reverse(), [run, t, t0]);
  const pitchGimbal = f.gimbals[1] > 180 ? f.gimbals[1] - 360 : f.gimbals[1];

  return (
    <main className="min-h-screen bg-background p-4 text-foreground">
      {/* Header */}
      <header className="mb-3 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs tracking-[0.3em] text-muted-foreground">LUMINARY 099 · YAAGC f577e3f · LM-7 SYNTHETIC MODEL</p>
          <h1 className="truncate font-display text-3xl font-bold tracking-wide">LUNAR MODULE · AGC EVIDENCE CONSOLE</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-sm border-2 border-accent px-3 py-1 font-display text-lg font-bold tracking-[0.2em] text-accent">● RECORDED REPLAY</span>
        </div>
      </header>

      <div role="alert" className="mb-3 rounded-sm border-2 border-destructive bg-destructive/10 px-4 py-2 font-display text-lg font-bold tracking-wider text-destructive">
        ⚠ POWERED DESCENT NOT VERIFIED — PROGRAM 63 BLOCKED BY ALARM 00220 (INVALID REFSMMAT).
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid min-w-0 gap-3">
          <Panel title={`Vehicle attitude · Phase 7 pitch run · ${runKey === "closed" ? "feedback connected" : "feedback disconnected"}`} tag={<Tag kind="mock" />}>
            <div className="aspect-[1000/520] w-full overflow-hidden rounded-sm bg-space">
              <LunarScene pitchDeg={pitchGimbal} jets={f.jets} />
            </div>
          </Panel>

          {/* Playback */}
          <Panel title="Playback · recorded evidence" tag={<Tag kind="rec" />}>
            <div className="grid gap-3 md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center">
              <div className="flex gap-2">
                <button onClick={() => { if (t >= t1) setT(t0); setPlaying((p) => !p); }} className="rounded-sm bg-primary px-4 py-1.5 font-display font-bold tracking-widest text-primary-foreground">
                  {playing ? "PAUSE" : "PLAY"}
                </button>
                <button onClick={() => { setPlaying(false); setT(t0); }} className="rounded-sm border border-border px-3 py-1.5 font-display tracking-widest">RESET</button>
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="rounded-sm border border-border bg-secondary px-2 font-mono text-sm" aria-label="Playback speed">
                  {[0.5, 1, 2, 4].map((s) => <option key={s} value={s}>{s}×</option>)}
                </select>
              </div>
              <input type="range" min={t0} max={t1} step={0.05} value={t} onChange={(e) => setT(Number(e.target.value))} className="w-full accent-primary" aria-label="Replay time" />
              <span className="seg font-mono text-sm text-accent">T+{t.toFixed(2)} s</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["closed", "feedback_off"] as RunKey[]).map((k) => (
                <button key={k} onClick={() => { setPlaying(false); setRunKey(k); }} className={`rounded-sm border px-3 py-1 font-mono text-xs ${runKey === k ? "border-primary text-primary" : "border-border text-muted-foreground"}`}>
                  {k === "closed" ? "CDU FEEDBACK CONNECTED" : "CDU FEEDBACK DISCONNECTED"}
                </button>
              ))}
              <span className="ml-auto self-center truncate font-mono text-[10px] text-muted-foreground">{run.source} · sha256 {run.sha256.slice(0, 12)}…</span>
            </div>
          </Panel>
        </div>

        <div className="grid min-w-0 content-start gap-3">
          <Dsky />
          <Panel title="Telemetry" tag={<Tag kind="rec" />}>
            <Readout label="Pitch rate" value={f.omega[1].toFixed(3)} unit="°/s" />
            <Readout label="Roll rate" value={f.omega[2].toFixed(4)} unit="°/s" />
            <Readout label="Yaw rate" value={f.omega[0].toFixed(3)} unit="°/s" />
            <Readout label="Model gimbal X/Y/Z" value={f.gimbals.map((g) => g.toFixed(1)).join(" / ")} unit="°" />
            <Readout label="AGC CDU X/Y/Z" value={f.cdu.map(cduSigned).join(" / ")} unit="cnt" />
            <Readout label="Jets ch005 / ch006" value={`${oct(f.jets[0], 3)} / ${oct(f.jets[1], 3)}`} />
            <Readout label="Altitude" value="NOT MODELLED" dim />
            <Readout label="Vertical velocity" value="NOT MODELLED" dim />
            <Readout label="Horizontal velocity" value="NOT MODELLED" dim />
            <Readout label="Fuel" value="NOT MODELLED" dim />
            <p className="mt-2 font-mono text-[10px] text-muted-foreground">
              Sensor pulses generated / delivered: {run.sensor_generated} / {run.sensor_delivered}
            </p>
          </Panel>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Panel title="AGC activity · Phase 7 (this run)" tag={<Tag kind="rec" />}>
          <Log events={events} empty="No AGC jet changes yet at this time." />
        </Panel>
        <Panel title="AGC activity · Phase 8 P63 attempt" tag={<Tag kind="rec" />}>
          <Log events={[...phase8.events].reverse()} />
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">{phase8.source} · sha256 {phase8.sha256.slice(0, 12)}…</p>
        </Panel>
      </div>

      <footer className="mt-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        RECORDED = copied from saved evidence logs, downsampled to 0.1 s. MOCK VISUAL = illustration only (LM shape, stars, surface; LM tilt follows recorded pitch gimbal).
        NOT MODELLED = no such data exists in this project. No live emulator connection. No landing is shown or claimed.
      </footer>
    </main>
  );
}

function Log({ events, empty }: { events: Event[]; empty?: string }) {
  const color: Record<string, string> = { alarm: "text-destructive", throttle: "text-warning", rcs: "text-accent", key: "text-foreground", state: "text-primary", input: "text-muted-foreground" };
  if (!events.length) return <p className="font-mono text-xs text-muted-foreground">{empty}</p>;
  return (
    <ol className="max-h-56 space-y-0.5 overflow-auto font-mono text-xs">
      {events.map((e, i) => (
        <li key={i} className="grid grid-cols-[80px_minmax(0,1fr)] gap-2">
          <span className="text-muted-foreground">T+{e.t.toFixed(3)}</span>
          <span className={`truncate ${color[e.kind] ?? ""}`}>{e.text}</span>
        </li>
      ))}
    </ol>
  );
}

function Dsky() {
  const f = phase8.final;
  const alarm = f.FAILREG1 || f.FAILREG0;
  const Cell = ({ label, v }: { label: string; v: string }) => (
    <div className="rounded-sm bg-space p-1.5 text-center">
      <div className="font-display text-[10px] tracking-widest text-accent/80">{label}</div>
      <div className="seg text-3xl font-semibold text-accent">{v}</div>
    </div>
  );
  return (
    <Panel title="DSKY · Phase 8 final state" tag={<Tag kind="rec" />}>
      <div className="grid grid-cols-[1fr_1.4fr] gap-3">
        <div className="grid content-start gap-1.5">
          {["UPLINK ACTY", "NO ATT", "STBY", "KEY REL", "OPR ERR"].map((l) => (
            <div key={l} className="rounded-sm border border-border px-1 py-0.5 text-center font-display text-[10px] tracking-wider text-muted-foreground">{l}</div>
          ))}
          <div className={`rounded-sm px-1 py-0.5 text-center font-display text-[10px] font-bold tracking-wider ${alarm ? "bg-warning text-primary-foreground" : "border border-border text-muted-foreground"}`}>PROG ALARM</div>
        </div>
        <div className="grid gap-1.5">
          <Cell label="PROG" v={String(f.MODREG).padStart(2, "0")} />
          <div className="grid grid-cols-2 gap-1.5"><Cell label="VERB" v="37" /><Cell label="NOUN" v="--" /></div>
          {[f.FAILREG0, f.FAILREG1, f.FAILREG2].map((r, i) => (
            <div key={i} className="seg rounded-sm bg-space px-2 text-right text-xl text-accent">{oct(r)}</div>
          ))}
        </div>
      </div>
      <p className="mt-2 font-mono text-[10px] leading-snug text-muted-foreground">
        From AGC memory, not decoded display relays: PROG = MODREG, rows = FAILREG (alarm codes), VERB = last keyed verb. PROG ALARM lamp inferred from FAILREG.
      </p>
    </Panel>
  );
}
