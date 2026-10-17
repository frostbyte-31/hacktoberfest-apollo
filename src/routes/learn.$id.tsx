import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { Diagram } from "@/components/Diagrams";
import { Nav } from "@/components/console";
import { tutorials, type Quiz } from "@/lib/content";
import { useDone } from "@/lib/progress";

export const Route = createFileRoute("/learn/$id")({
  loader: ({ params }) => {
    const i = tutorials.findIndex((t) => t.id === params.id);
    if (i < 0) throw notFound();
    return { i };
  },
  head: ({ loaderData }) => {
    const t = loaderData ? tutorials[loaderData.i]! : undefined;
    const title = t ? `${t.title} — Learn Apollo Guidance` : "Lesson — Learn Apollo Guidance";
    const desc = t ? t.objective : "Apollo guidance lesson";
    return { meta: [{ title }, { name: "description", content: desc }, { property: "og:title", content: title }, { property: "og:description", content: desc }, { property: "og:type", content: "article" }, { name: "twitter:card", content: "summary" }] };
  },
  component: Lesson,
});

function Check({ q }: { q: Quiz }) {
  const [pick, setPick] = useState<number | null>(null);
  return (
    <div className="rounded-sm border border-border p-3">
      <p className="font-medium">{q.q}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {q.options.map((o, i) => (
          <button key={o} onClick={() => setPick(i)} className={`rounded-sm border px-3 py-1 text-sm ${pick === null ? "border-border hover:border-primary" : i === q.answer ? "border-accent text-accent" : pick === i ? "border-destructive text-destructive" : "border-border text-muted-foreground"}`}>{o}</button>
        ))}
      </div>
      {pick !== null && <p className="mt-2 text-sm text-muted-foreground"><b className={pick === q.answer ? "text-accent" : "text-destructive"}>{pick === q.answer ? "Correct." : "Not quite."}</b> {q.why}</p>}
    </div>
  );
}

function Lesson() {
  const { i } = Route.useLoaderData();
  const t = tutorials[i]!; const prev = tutorials[i - 1]; const next = tutorials[i + 1];
  const { done, mark } = useDone();
  return (
    <main key={t.id} className="min-h-screen bg-background p-4 text-foreground">
      <Nav />
      <div className="mb-3 flex items-center gap-1">
        {tutorials.map((x, k) => <Link key={x.id} to="/learn/$id" params={{ id: x.id }} aria-label={x.title} className={`h-1.5 flex-1 rounded-full ${k === i ? "bg-primary" : done.includes(x.id) ? "bg-accent" : "bg-secondary"}`} />)}
      </div>
      <p className="font-mono text-xs tracking-widest text-muted-foreground">LESSON {i + 1} OF {tutorials.length}</p>
      <h1 className="font-display text-4xl font-bold tracking-wide">{t.title}</h1>
      <p className="mt-1 text-primary">Objective: {t.objective}</p>
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-3 leading-relaxed">
          {t.body.map((p) => <p key={p}>{p}</p>)}
          <div className="rounded-sm border-l-4 border-primary bg-card p-3"><p className="font-display text-xs tracking-widest text-primary">FROM OUR PROJECT</p><p className="mt-1 text-sm">{t.example}</p></div>
        </div>
        <div className="rounded-sm border border-border bg-card p-3"><Diagram kind={t.diagram} /></div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-sm border border-accent/50 bg-card p-3"><h2 className="font-display tracking-widest text-accent">WHAT WE VERIFIED</h2><ul className="mt-1 list-disc pl-5 text-sm">{t.verified.map((v) => <li key={v}>{v}</li>)}</ul></div>
        <div className="rounded-sm border border-destructive/50 bg-card p-3"><h2 className="font-display tracking-widest text-destructive">NOT YET IMPLEMENTED</h2><ul className="mt-1 list-disc pl-5 text-sm">{t.notYet.map((v) => <li key={v}>{v}</li>)}</ul></div>
      </div>
      <h2 className="mt-5 font-display text-xl tracking-widest">KNOWLEDGE CHECK</h2>
      <div className="mt-2 grid gap-2">{t.quiz.map((q) => <Check key={q.q} q={q} />)}</div>
      <div className="mt-6 flex items-center justify-between gap-2 border-t border-border pt-3">
        {prev ? <Link to="/learn/$id" params={{ id: prev.id }} className="font-mono text-sm text-muted-foreground hover:text-foreground">◂ {prev.title}</Link> : <Link to="/learn" className="font-mono text-sm text-muted-foreground">◂ All lessons</Link>}
        <button onClick={() => mark(t.id)} className="rounded-sm border border-accent px-3 py-1 font-mono text-xs text-accent">{done.includes(t.id) ? "✓ Completed" : "Mark complete"}</button>
        {next ? <Link to="/learn/$id" params={{ id: next.id }} onClick={() => mark(t.id)} className="font-mono text-sm text-primary">{next.title} ▸</Link> : <Link to="/evidence" className="font-mono text-sm text-primary">Evidence explorer ▸</Link>}
      </div>
    </main>
  );
}
