import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { help } from "@/lib/content";
import { two, oct } from "@/lib/replay";

export function Nav() {
  const items = [["/", "Mission Control"], ["/learn", "Learn"], ["/evidence", "Evidence"], ["/present", "Present"]] as const;
  return (
    <nav className="mb-4 flex flex-wrap items-center gap-1 border-b border-border pb-2">
      <span className="mr-4 font-display text-lg font-bold tracking-[0.2em] text-primary">AGC · LM</span>
      {items.map(([to, l]) => (
        <Link key={to} to={to} activeOptions={{ exact: to === "/" }} className="rounded-sm px-3 py-1 font-display text-sm tracking-widest text-muted-foreground uppercase transition-colors hover:text-foreground" activeProps={{ className: "bg-secondary text-primary" }}>{l}</Link>
      ))}
      <span className="ml-auto rounded-sm border border-accent px-2 py-0.5 font-mono text-[10px] tracking-widest text-accent">RECORDED REPLAY · NO LIVE AGC</span>
    </nav>
  );
}

export function Panel({ title, tag, helpKey, children, className = "" }: { title: string; tag?: ReactNode; helpKey?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-sm border border-border bg-card ${className}`}>
      <header className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5">
        <h2 className="truncate font-display text-sm font-semibold tracking-[0.2em] text-muted-foreground uppercase">{title}</h2>
        <div className="flex shrink-0 items-center gap-1.5">{tag}{helpKey && <HelpButton k={helpKey} />}</div>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export type TagKind = "rec" | "none" | "mock" | "assumed";
export const Tag = ({ kind }: { kind: TagKind }) => {
  const map = {
    rec: ["RECORDED", "border-accent text-accent"],
    none: ["NOT MODELLED", "border-muted-foreground text-muted-foreground"],
    mock: ["MOCK VISUAL", "border-mock text-mock"],
    assumed: ["ASSUMED", "border-warning text-warning"],
  } as const;
  return <span className={`shrink-0 rounded-sm border px-1.5 font-mono text-[10px] tracking-widest ${map[kind][1]}`}>{map[kind][0]}</span>;
};

export function StatusBadge({ s }: { s: string }) {
  const c = s === "VERIFIED" ? "border-accent text-accent" : s === "BLOCKED" ? "border-destructive text-destructive" : s === "NOT RUN" ? "border-muted-foreground text-muted-foreground" : "border-warning text-warning";
  return <span className={`rounded-sm border px-1.5 font-mono text-[10px] tracking-widest ${c}`}>{s}</span>;
}

export function HelpButton({ k }: { k: string }) {
  const h = help[k]; const [tech, setTech] = useState(false);
  if (!h) return null;
  return (
    <Dialog>
      <DialogTrigger aria-label={`Explain ${h.title}`} className="grid h-5 w-5 place-items-center rounded-full border border-border font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary hover:text-primary">?</DialogTrigger>
      <DialogContent className="max-w-lg border-border bg-card">
        <DialogHeader><DialogTitle className="font-display text-xl tracking-wide">{h.title}</DialogTitle></DialogHeader>
        <dl className="space-y-3 text-sm">
          {([["What it is", h.what], ["In the real Apollo system", h.real], ["In our simulator", h.sim], ["Evidence", h.evidence], ["Not yet implemented", h.missing]] as const).map(([l, v]) => (
            <div key={l}><dt className="font-display text-xs tracking-widest text-primary uppercase">{l}</dt><dd className={l === "Evidence" ? "font-mono text-xs" : ""}>{v}</dd></div>
          ))}
        </dl>
        {h.tech && <div><button onClick={() => setTech((v) => !v)} className="font-mono text-xs text-accent">{tech ? "▾" : "▸"} Technical details</button>{tech && <p className="mt-1 font-mono text-xs text-muted-foreground">{h.tech}</p>}</div>}
      </DialogContent>
    </Dialog>
  );
}

/** Pure display of recorded AGC register values. */
export function DskyFace({ prog, verb, noun, regs, alarm, caption }: { prog: number; verb: number; noun: number; regs: number[]; alarm: boolean; caption?: string }) {
  const Cell = ({ label, v }: { label: string; v: string }) => (
    <div className="rounded-sm bg-space p-1.5 text-center">
      <div className="font-display text-[10px] tracking-widest text-accent/80">{label}</div>
      <div className="seg text-3xl font-semibold text-accent">{v}</div>
    </div>
  );
  return (
    <div>
      <div className="grid grid-cols-[1fr_1.4fr] gap-3">
        <div className="grid content-start gap-1.5">
          {["UPLINK ACTY", "NO ATT", "STBY", "KEY REL", "OPR ERR"].map((l) => (
            <div key={l} className="rounded-sm border border-border px-1 py-0.5 text-center font-display text-[10px] tracking-wider text-muted-foreground">{l}</div>
          ))}
          <div className={`rounded-sm px-1 py-0.5 text-center font-display text-[10px] font-bold tracking-wider transition-colors ${alarm ? "bg-warning text-primary-foreground" : "border border-border text-muted-foreground"}`}>PROG ALARM</div>
        </div>
        <div className="grid gap-1.5">
          <Cell label="PROG" v={two(prog)} />
          <div className="grid grid-cols-2 gap-1.5"><Cell label="VERB" v={two(verb)} /><Cell label="NOUN" v={two(noun)} /></div>
          {regs.map((r, i) => <div key={i} className="seg rounded-sm bg-space px-2 text-right text-xl text-accent">{oct(r)}</div>)}
        </div>
      </div>
      {caption && <p className="mt-2 font-mono text-[10px] leading-snug text-muted-foreground">{caption}</p>}
    </div>
  );
}
