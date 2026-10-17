import { useState } from "react";
import type { Tutorial } from "@/lib/content";

type Node = { id: string; label: string; x: number; y: number; info: string };
function Clickable({ nodes, edges }: { nodes: Node[]; edges: [string, string, string?][] }) {
  const [sel, setSel] = useState(nodes[0]!.id);
  const by = Object.fromEntries(nodes.map((n) => [n.id, n]));
  return (
    <div>
      <svg viewBox="0 0 600 240" className="w-full" role="img" aria-label="Interactive diagram">
        {edges.map(([a, b, l], i) => {
          const A = by[a]!, B = by[b]!;
          return (
            <g key={i}>
              <line x1={A.x} y1={A.y} x2={B.x} y2={B.y} stroke="var(--border)" strokeWidth="2" strokeDasharray="5 4" style={{ animation: "dash 1.6s linear infinite" }} />
              {l && <text x={(A.x + B.x) / 2} y={(A.y + B.y) / 2 - 6} textAnchor="middle" fill="var(--muted-foreground)" fontSize="11" fontFamily="IBM Plex Mono">{l}</text>}
            </g>
          );
        })}
        {nodes.map((n) => (
          <g key={n.id} onClick={() => setSel(n.id)} className="cursor-pointer">
            <rect x={n.x - 62} y={n.y - 20} width="124" height="40" rx="3" fill="var(--space)" stroke={sel === n.id ? "var(--primary)" : "var(--border)"} strokeWidth="2" />
            <text x={n.x} y={n.y + 5} textAnchor="middle" fill={sel === n.id ? "var(--primary)" : "var(--foreground)"} fontSize="14" fontFamily="Barlow Condensed" letterSpacing="1.5">{n.label}</text>
          </g>
        ))}
      </svg>
      <p className="mt-2 rounded-sm border border-border bg-space p-3 text-sm"><span className="font-display tracking-widest text-primary">{by[sel]!.label}: </span>{by[sel]!.info}</p>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground">Click a box to learn about it.</p>
    </div>
  );
}

function Steps({ steps, warn }: { steps: string[]; warn?: number }) {
  const [i, setI] = useState(0);
  return (
    <div>
      <ol className="grid gap-1.5">
        {steps.map((s, k) => (
          <li key={k} onClick={() => setI(k)} className={`cursor-pointer rounded-sm border px-3 py-2 text-sm transition-colors ${k === i ? (k === warn ? "border-destructive text-destructive" : "border-primary text-foreground") : k < i ? "border-border text-muted-foreground" : "border-border/50 text-muted-foreground/60"}`}>
            <span className="mr-2 font-mono text-xs">{String(k + 1).padStart(2, "0")}</span>{s}
          </li>
        ))}
      </ol>
      <div className="mt-2 flex gap-2">
        <button onClick={() => setI((v) => Math.max(0, v - 1))} className="rounded-sm border border-border px-3 py-1 font-mono text-xs">◂ Back</button>
        <button onClick={() => setI((v) => Math.min(steps.length - 1, v + 1))} className="rounded-sm bg-primary px-3 py-1 font-mono text-xs text-primary-foreground">Step ▸</button>
      </div>
    </div>
  );
}

export function Diagram({ kind }: { kind: Tutorial["diagram"] }) {
  switch (kind) {
    case "arch":
      return <Clickable edges={[["cm", "lm", "docked / separate"], ["lm", "agc"], ["agc", "dsky", "keys / display"], ["agc", "imu", "angles"], ["agc", "lum", "runs"]]} nodes={[
        { id: "cm", label: "COMMAND MODULE", x: 90, y: 40, info: "Stayed in lunar orbit; had its own AGC running Colossus. Not used in this project." },
        { id: "lm", label: "LUNAR MODULE", x: 300, y: 40, info: "The landing craft. Our vehicle model is a synthetic LM-7 attitude model (ASSUMED fidelity)." },
        { id: "agc", label: "AGC", x: 300, y: 130, info: "The guidance computer. We run it in the yaAGC emulator." },
        { id: "lum", label: "LUMINARY 099", x: 520, y: 130, info: "The LM flight program flown on Apollo 11. Assembled byte-identical to the reference." },
        { id: "dsky", label: "DSKY", x: 140, y: 205, info: "Display and keyboard. Our driver presses keys through the emulator's input channels." },
        { id: "imu", label: "IMU", x: 460, y: 205, info: "Gyro platform measuring orientation. Ours is the upstream simulator's IMU model." },
      ]} />;
    case "agc":
      return <Steps steps={["Source code (Luminary 099 .agc files)", "Assembler yaYUL → machine instructions", "Binary rope image (byte-identical to reference)", "Emulator yaAGC loads the image", "Program executes; erasable memory changes", "DSKY keys arrive on channel 015 / 032; display goes out on channel 010"]} />;
    case "gnc":
      return <Clickable edges={[["nav", "gui", "state"], ["gui", "ctl", "desired"], ["ctl", "veh", "jets"], ["veh", "nav", "IMU angles"]]} nodes={[
        { id: "nav", label: "NAVIGATION", x: 110, y: 60, info: "Where and how am I? In our runs: IMU gimbal angles fed back as CDU counts." },
        { id: "gui", label: "GUIDANCE", x: 490, y: 60, info: "What should I do? Descent guidance (P63) never ran past ignition: alarm 01406." },
        { id: "ctl", label: "CONTROL", x: 490, y: 190, info: "Do it. The AGC's autopilot (DAP) issued RCS jet commands — verified for yaw and pitch." },
        { id: "veh", label: "VEHICLE", x: 110, y: 190, info: "Simulated LM attitude dynamics (ASSUMED fidelity). No translation or gravity." },
      ]} />;
    case "dsky":
      return <Clickable edges={[["verb", "noun"], ["noun", "ent"], ["prog", "verb"], ["pro", "ent"]]} nodes={[
        { id: "prog", label: "PROG", x: 100, y: 60, info: "Major mode number (stored in MODREG). 51 = IMU alignment, 63 = descent braking phase." },
        { id: "verb", label: "VERB", x: 300, y: 60, info: "The action. Verb 37 = change major mode. Verbs 21/22 load data components." },
        { id: "noun", label: "NOUN", x: 500, y: 60, info: "The data. Noun 71 = AOT detent/star code, noun 87 = AOT azimuth/elevation (as used in P51)." },
        { id: "ent", label: "ENTER", x: 500, y: 190, info: "Completes a verb, noun, or number entry." },
        { id: "pro", label: "PROCEED", x: 300, y: 190, info: "Tells a waiting (flashing) program to continue. Reaches the AGC as channel 032 bit 14." },
      ]} />;
    case "imu":
      return <Steps steps={["Platform orientation unknown → REFSMFLG clear", "Star 1: load star code, AOT angles; press mark (ASSUMED synthetic angles)", "Star 2: same", "P51 compares measured vs catalog directions", "AGC computes REFSMMAT (3×3 matrix) and sets REFSMFLG", "R02 check in P63 now passes"]} />;
    case "loop":
      return <Clickable edges={[["agc", "rcs", "ch005/006"], ["rcs", "veh", "torque"], ["veh", "imu", "rotation"], ["imu", "agc", "CDU counts"]]} nodes={[
        { id: "agc", label: "AGC / DAP", x: 110, y: 60, info: "Decides jet firings from measured attitude error." },
        { id: "rcs", label: "RCS JETS", x: 490, y: 60, info: "Small thrusters. Commands recorded on channels 005/006." },
        { id: "veh", label: "VEHICLE", x: 490, y: 190, info: "Synthetic LM-7 rotation model (ASSUMED fidelity)." },
        { id: "imu", label: "IMU / CDU", x: 110, y: 190, info: "Measures the rotation and returns counts. Cut this and the loop is open (feedback-off runs)." },
      ]} />;
    case "phase9":
      return <Steps warn={5} steps={["V37E51E — select P51", "PROCEED at V50N25", "Star 1 and star 2: code, angles, AOT marks", "AGC sets REFSMFLG; REFSMMAT populated (T+180.4 s)", "V37E63E — P63 selected, no alarm 00220 (T+221.7 s)", "POODOO alarm 01406: ignition algorithm, targeting not loaded (T+222.7 s)"]} />;
    case "remaining":
      return <Steps steps={["Descent-targeting data", "Resolve 01406", "Thrust model", "Lunar-gravity dynamics", "Landing radar feedback", "Descent loop validation", "Browser vs native"]} />;
  }
}
