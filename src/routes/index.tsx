import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { LunarScene } from "@/components/LunarScene";
import { DskyFace, Nav, Panel, Tag } from "@/components/console";
import { milestones } from "@/lib/milestones";
import { cduSigned, frameAt, oct, phase9, REFSMFLG, runs, stateAt, type Event } from "@/lib/replay";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Mission Control — Apollo LM AGC Replay" },
      { name: "description", content: "Replay recorded Luminary 099 runs: P51 alignment, P63 selection and alarm 01406, and RCS attitude feedback." },
      { property: "og:title", content: "Mission Control — Apollo LM AGC Replay" },
      { property: "og:description", content: "Replay recorded Luminary 099 runs: P51 alignment, P63 selection and alarm 01406." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Console,
});

type RunKey = "p9" | "closed" | "feedback_off";
const RUN_LABEL: Record<RunKey, string> = { p9: "PHASE 9 · P51 ALIGNMENT → P63", closed: "PHASE 7 · PITCH, FEEDBACK CONNECTED", feedback_off: "PHASE 7 · PITCH, FEEDBACK DISCONNECTED" };

function Readout({ label, value, unit, dim }: { label: string; value: string; unit?: string; dim?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/50 py-1.5 last:border-0">
      <span className="font-display text-xs tracking-widest text-muted-foreground uppercase">{label}</span>
      <span className={`font-mono text-sm ${dim ? "text-muted-foreground" : "seg text-accent"}`}>{value} {unit && <span className="text-xs text-muted-foreground">{unit}</span>}</span>
    </div>
  );
}

function usePlayback(t0: number, t1: number, base: number) {
  const [t, setT] = useState(t0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  useEffect(() => { setT(t0); setPlaying(false); }, [t0]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT((v) => { const n = v + base * speed; if (n >= t1) { setPlaying(false); return t1; } return n; }), 50);
    return () => clearInterval(id);
  }, [playing, speed, t1, base]);
  return { t, setT, playing, setPlaying, speed, setSpeed };
}

function Console() {
  const [runKey, setRunKey] = useState<RunKey>("p9");
  const p9 = runKey === "p9";
  const run7 = runs[p9 ? "closed" : runKey];
  const t0 = p9 ? phase9.states[0]!.t : run7.frames[0]!.t;
  const t1 = p9 ? phase9.states[phase9.states.length - 1]!.t : run7.frames[run7.frames.length - 1]!.t;
  const pb = usePlayback(t0, t1, p9 ? 0.5 : 0.05);
  const { t } = pb;
  const f = frameAt(run7, t);
  const s = stateAt(phase9, t);
  const srcEvents = p9 ? phase9.events : run7.events;
  const events = useMemo(() => srcEvents.filter((e) => e.t <= t).slice(-16).reverse(), [srcEvents, t]);
  const g1 = f.gimbals[1] ?? 0;
  const pitch = p9 ? 0 : g1 > 180 ? g1 - 360 : g1;
  const src = p9 ? phase9 : run7;

  return (
    <main className="min-h-screen bg-background p-4 text-foreground">
      <Nav />
      <header className="mb-3">
        <p className="font-mono text-xs tracking-[0.3em] text-muted-foreground">LUMINARY 099 · YAAGC f577e3f · LM-7 SYNTHETIC MODEL</p>
        <h1 className="font-display text-3xl font-bold tracking-wide">LUNAR MODULE · AGC MISSION CONTROL</h1>
      </header>

      <div role="status" className="mb-3 grid gap-2 md:grid-cols-2">
        <div className="rounded-sm border border-accent/60 bg-accent/5 px-4 py-2 font-display tracking-wider text-accent">✓ PHASE 9: P51 ALIGNMENT COMPLETED BY ORIGINAL SOFTWARE · P63 PASSED R02 (NO 00220)</div>
        <div className="rounded-sm border-2 border-destructive bg-destructive/10 px-4 py-2 font-display font-bold tracking-wider text-destructive">⚠ POWERED DESCENT NOT VERIFIED — P63 ABORTED, ALARM 01406</div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid min-w-0 content-start gap-3">
          <Panel title={`Vehicle · ${RUN_LABEL[runKey]}`} tag={<Tag kind="mock" />} helpKey="lm">
            <div className="relative aspect-[1000/520] w-full overflow-hidden rounded-sm bg-space">
              <LunarScene pitchDeg={pitch} jets={p9 ? [0] : f.jets} />
              {p9 && <p className="absolute top-2 left-2 rounded-sm border border-border bg-space/80 px-2 py-1 font-mono text-[10px] text-muted-foreground">Attitude not recorded in this run — LM shown static</p>}
            </div>
          </Panel>

          <Panel title="Playback · recorded evidence" tag={<Tag kind="rec" />} helpKey="playback">
            <div className="grid gap-3 md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center">
              <div className="flex gap-2">
                <button onClick={() => { if (t >= t1) pb.setT(t0); pb.setPlaying((p) => !p); }} className="rounded-sm bg-primary px-4 py-1.5 font-display font-bold tracking-widest text-primary-foreground">{pb.playing ? "PAUSE" : "PLAY"}</button>
                <button onClick={() => { pb.setPlaying(false); pb.setT(t0); }} className="rounded-sm border border-border px-3 py-1.5 font-display tracking-widest">RESET</button>
                <select value={pb.speed} onChange={(e) => pb.setSpeed(Number(e.target.value))} className="rounded-sm border border-border bg-secondary px-2 font-mono text-sm" aria-label="Playback speed">
                  {[0.5, 1, 2, 4, 8].map((v) => <option key={v} value={v}>{v}×</option>)}
                </select>
              </div>
              <input type="range" min={t0} max={t1} step={0.05} value={t} onChange={(e) => pb.setT(Number(e.target.value))} className="w-full accent-primary" aria-label="Replay time" />
              <span className="seg font-mono text-sm text-accent">T+{t.toFixed(2)} s</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(Object.keys(RUN_LABEL) as RunKey[]).map((k) => (
                <button key={k} onClick={() => setRunKey(k)} className={`rounded-sm border px-3 py-1 font-mono text-xs ${runKey === k ? "border-primary text-primary" : "border-border text-muted-foreground"}`}>{RUN_LABEL[k]}</button>
              ))}
            </div>
            <p className="mt-2 truncate font-mono text-[10px] text-muted-foreground">Source: {src.source} · sha256 {src.sha256.slice(0, 16)}… · {p9 ? "1 s replay ≈ 10 s AGC time at 1×" : "real-time at 1×"}</p>
          </Panel>

          {p9 && (
            <Panel title="Phase 9 milestones · chronological" tag={<Tag kind="rec" />} helpKey="timeline">
              <ol className="grid gap-1 sm:grid-cols-2">
                {milestones.map((m, i) => {
                  const done = t >= m.t; const bad = i === 5;
                  return (
                    <li key={m.label} className={`flex items-center justify-between gap-2 rounded-sm border px-2 py-1 font-mono text-xs transition-colors ${done ? (bad ? "border-destructive text-destructive" : "border-accent text-accent") : "border-border text-muted-foreground"}`}>
                      <span>{done ? (bad ? "✕" : "✓") : "○"} {m.label}</span><span>T+{m.t.toFixed(1)}</span>
                    </li>
                  );
                })}
              </ol>
              <p className="mt-2 text-xs text-muted-foreground">A successful <b className="text-foreground">alignment</b> means the computer knows which way its gyro platform points. A successful <b className="text-foreground">landing</b> would also need ignition, descent guidance, engine physics and radar — none of which ran. Star angles were synthetic (<span className="text-warning">ASSUMED</span>).</p>
            </Panel>
          )}
        </div>

        <div className="grid min-w-0 content-start gap-3">
          {p9 ? (
            <Panel title="DSKY · Phase 9 at this time" tag={<Tag kind="rec" />} helpKey="dsky">
              <DskyFace prog={s.prog} verb={s.verb} noun={s.noun} regs={[s.f0, s.f1, s.f2]} alarm={s.f1 !== 0} caption="From AGC memory: PROG=MODREG, VERB/NOUN=VERBREG/NOUNREG, rows=FAILREG0/1/2 (octal). FAILREG0 01520 predates P51 (Phase 5 startup). PROG ALARM shown when FAILREG1 nonzero." />
              <div className="mt-2 grid grid-cols-2 gap-1.5 font-mono text-[11px]">
                <span className={`rounded-sm border px-2 py-1 text-center ${s.flag3 & REFSMFLG ? "border-accent text-accent" : "border-border text-muted-foreground"}`}>REFSMFLG {s.flag3 & REFSMFLG ? "SET" : "CLEAR"}</span>
                <span className={`rounded-sm border px-2 py-1 text-center ${s.refs ? "border-accent text-accent" : "border-border text-muted-foreground"}`}>REFSMMAT {s.refs ? "POPULATED" : "ZERO"}</span>
              </div>
            </Panel>
          ) : (
            <Panel title="Telemetry" tag={<Tag kind="rec" />} helpKey="telemetry">
              <Readout label="Pitch rate" value={(f.omega[1] ?? 0).toFixed(3)} unit="°/s" />
              <Readout label="Roll rate" value={(f.omega[2] ?? 0).toFixed(4)} unit="°/s" />
              <Readout label="Yaw rate" value={(f.omega[0] ?? 0).toFixed(3)} unit="°/s" />
              <Readout label="Model gimbal X/Y/Z" value={f.gimbals.map((g) => g.toFixed(1)).join(" / ")} unit="°" />
              <Readout label="AGC CDU X/Y/Z" value={f.cdu.map(cduSigned).join(" / ")} unit="cnt" />
              <Readout label="Jets ch005 / ch006" value={`${oct(f.jets[0] ?? 0, 3)} / ${oct(f.jets[1] ?? 0, 3)}`} />
              <p className="mt-2 font-mono text-[10px] text-muted-foreground">Sensor pulses generated / delivered: {run7.sensor_generated} / {run7.sensor_delivered}</p>
            </Panel>
          )}
          <Panel title="Not modelled" tag={<Tag kind="none" />} helpKey="telemetry">
            {["Altitude", "Vertical velocity", "Horizontal velocity", "Fuel", "Engine thrust", "Distance to touchdown"].map((l) => <Readout key={l} label={l} value="NOT MODELLED" dim />)}
            {p9 && <p className="mt-2 font-mono text-[10px] text-muted-foreground">Phase 9 recorded no vehicle attitude, rates or jets. Switch to a Phase 7 run for those.</p>}
          </Panel>
        </div>
      </div>

      <div className="mt-3">
        <Panel title={`AGC activity · ${RUN_LABEL[runKey]}`} tag={<Tag kind="rec" />} helpKey="timeline">
          <Log events={events} empty="No recorded events yet at this time." />
        </Panel>
      </div>

      <footer className="mt-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        RECORDED = copied from saved evidence logs. MOCK VISUAL = illustration only. ASSUMED = experimental assumption. NOT MODELLED = no such data exists. No live emulator connection. No landing is shown or claimed.
      </footer>
    </main>
  );
}

function Log({ events, empty }: { events: Event[]; empty?: string }) {
  const color: Record<string, string> = { alarm: "text-destructive", throttle: "text-warning", rcs: "text-accent", key: "text-foreground", state: "text-primary", input: "text-muted-foreground" };
  if (!events.length) return <p className="font-mono text-xs text-muted-foreground">{empty}</p>;
  return (
    <ol className="max-h-64 space-y-0.5 overflow-auto font-mono text-xs">
      {events.map((e, i) => (
        <li key={`${e.t}-${i}`} className="grid grid-cols-[90px_minmax(0,1fr)] gap-2 animate-in fade-in">
          <span className="text-muted-foreground">T+{e.t.toFixed(3)}</span>
          <span className={`truncate ${color[e.kind] ?? ""}`}>{e.text}</span>
        </li>
      ))}
    </ol>
  );
}
