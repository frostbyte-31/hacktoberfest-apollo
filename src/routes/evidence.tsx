import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Nav, StatusBadge } from "@/components/console";
import { phases } from "@/lib/content";

export const Route = createFileRoute("/evidence")({
  head: () => ({
    meta: [
      { title: "Evidence Explorer — Phases 1–9" },
      { name: "description", content: "What each phase of the Apollo AGC project demonstrated, what it did not, and where the evidence lives." },
      { property: "og:title", content: "Evidence Explorer — Phases 1–9" },
      { property: "og:description", content: "Phase-by-phase status of the Apollo AGC validation project." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Evidence,
});

function Evidence() {
  const [sel, setSel] = useState("9");
  const p = phases.find((x) => x.n === sel)!;
  return (
    <main className="min-h-screen bg-background p-4 text-foreground">
      <Nav />
      <h1 className="font-display text-4xl font-bold tracking-wide">EXPERIMENT & EVIDENCE EXPLORER</h1>
      <div role="alert" className="mt-3 rounded-sm border-2 border-warning bg-warning/10 p-3 text-sm">
        <b className="font-display tracking-widest text-warning">INTEGRITY NOTICE · </b>About 30 Phase 1–6 historical log files are missing and have not been recovered or recreated. The Milestone 1 integrity suite cannot run. Not all tests pass.
      </div>
      <div className="mt-4 flex gap-1 overflow-x-auto">
        {phases.map((x) => (
          <button key={x.n} onClick={() => setSel(x.n)} className={`min-w-24 flex-1 rounded-sm border px-2 py-2 text-left transition-colors ${sel === x.n ? "border-primary bg-card" : "border-border hover:border-muted-foreground"}`}>
            <div className="font-mono text-[10px] text-muted-foreground">PHASE {x.n}</div>
            <div className="truncate font-display text-sm tracking-wide">{x.title}</div>
            <div className="mt-1"><StatusBadge s={x.status} /></div>
          </button>
        ))}
      </div>
      <section className="mt-4 rounded-sm border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3"><h2 className="font-display text-2xl font-bold">Phase {p.n} · {p.title}</h2><StatusBadge s={p.status} /></div>
        <p className="mt-1 text-muted-foreground"><b className="text-foreground">Objective:</b> {p.objective}</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div><h3 className="font-display tracking-widest text-accent">DEMONSTRATED</h3><ul className="mt-1 list-disc pl-5 text-sm">{p.shown.map((s) => <li key={s}>{s}</li>)}</ul></div>
          <div><h3 className="font-display tracking-widest text-destructive">NOT DEMONSTRATED</h3><ul className="mt-1 list-disc pl-5 text-sm">{p.notShown.map((s) => <li key={s}>{s}</li>)}</ul></div>
        </div>
        <p className="mt-3 text-sm"><b className="font-display tracking-widest text-primary">TESTS · </b>{p.tests}</p>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{p.paths.join("  ·  ")}</p>
        {p.caveat && <p className="mt-3 rounded-sm border border-warning/60 p-2 text-sm text-warning">{p.caveat}</p>}
      </section>
    </main>
  );
}
