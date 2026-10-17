import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Nav } from "@/components/console";
import { tutorials } from "@/lib/content";

export const Route = createFileRoute("/learn/")({
  head: () => ({
    meta: [
      { title: "Learn — How Apollo Guidance Works" },
      { name: "description", content: "Beginner tutorials on the AGC, DSKY, IMU alignment, feedback control and what our Phase 9 experiment showed." },
      { property: "og:title", content: "Learn — How Apollo Guidance Works" },
      { property: "og:description", content: "Beginner tutorials on the Apollo Guidance Computer and our recorded experiments." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Learn,
});

export function useDone() {
  const [done, setDone] = useState<string[]>([]);
  useEffect(() => { try { setDone(JSON.parse(localStorage.getItem("learn-done") ?? "[]")); } catch { /* ignore */ } }, []);
  const mark = (id: string) => setDone((d) => { const n = d.includes(id) ? d : [...d, id]; localStorage.setItem("learn-done", JSON.stringify(n)); return n; });
  return { done, mark };
}

function Learn() {
  const { done } = useDone();
  return (
    <main className="min-h-screen bg-background p-4 text-foreground">
      <Nav />
      <h1 className="font-display text-4xl font-bold tracking-wide">LEARNING CENTER</h1>
      <p className="mt-1 max-w-2xl text-muted-foreground">Eight short lessons. No programming background needed. Take them in any order.</p>
      <div className="mt-3 flex items-center gap-3">
        <div className="h-1.5 w-64 overflow-hidden rounded-full bg-secondary"><div className="h-full bg-accent transition-all" style={{ width: `${(done.length / tutorials.length) * 100}%` }} /></div>
        <span className="font-mono text-xs text-muted-foreground">{done.length} / {tutorials.length} completed</span>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tutorials.map((t, i) => (
          <Link key={t.id} to="/learn/$id" params={{ id: t.id }} className="group rounded-sm border border-border bg-card p-4 transition-colors hover:border-primary">
            <div className="flex items-center justify-between font-mono text-xs text-muted-foreground"><span>LESSON {String(i + 1).padStart(2, "0")}</span>{done.includes(t.id) && <span className="text-accent">✓ DONE</span>}</div>
            <h2 className="mt-2 font-display text-xl font-semibold tracking-wide group-hover:text-primary">{t.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{t.objective}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
