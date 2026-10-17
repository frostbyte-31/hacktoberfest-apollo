import { useMemo } from "react";

/** Visual only. Pitch angle comes from recorded model gimbal; altitude/position are NOT data (fixed hover pose). */
export function LunarScene({ pitchDeg, jets }: { pitchDeg: number; jets: number[] }) {
  const stars = useMemo(
    () => Array.from({ length: 90 }, (_, i) => ({ x: (i * 137.5) % 1000, y: (i * 61.7) % 330, r: (i % 3) * 0.4 + 0.4, d: (i % 7) * 0.6 })),
    [],
  );
  const firing = jets[0] !== 0;
  return (
    <svg viewBox="0 0 1000 520" className="h-full w-full" role="img" aria-label="Lunar Module attitude visualization">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--space)" />
          <stop offset="1" stopColor="var(--background)" />
        </linearGradient>
        <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--lunar)" />
          <stop offset="1" stopColor="var(--lunar-dark)" />
        </linearGradient>
      </defs>
      <rect width="1000" height="520" fill="url(#sky)" />
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="var(--foreground)" style={{ animation: `twinkle ${4 + s.d}s ease-in-out infinite` }} />
      ))}
      <path d="M0 410 Q 180 392 360 404 T 700 398 T 1000 406 L1000 520 L0 520 Z" fill="url(#ground)" />
      {[[120, 450, 30], [420, 470, 18], [760, 445, 40], [610, 490, 12], [880, 480, 20]].map(([x, y, r], i) => (
        <ellipse key={i} cx={x} cy={y} rx={r} ry={r / 3.2} fill="var(--lunar-dark)" opacity={0.7} />
      ))}
      <g transform={`translate(500 230) rotate(${-pitchDeg})`}>
        {/* Descent stage */}
        <polygon points="-55,10 55,10 45,55 -45,55" fill="var(--warning)" opacity={0.85} />
        <line x1="-45" y1="50" x2="-80" y2="95" stroke="var(--muted-foreground)" strokeWidth="4" />
        <line x1="45" y1="50" x2="80" y2="95" stroke="var(--muted-foreground)" strokeWidth="4" />
        <line x1="-92" y1="95" x2="-68" y2="95" stroke="var(--muted-foreground)" strokeWidth="4" />
        <line x1="68" y1="95" x2="92" y2="95" stroke="var(--muted-foreground)" strokeWidth="4" />
        <polygon points="-14,55 14,55 20,72 -20,72" fill="var(--lunar-dark)" />
        {/* Ascent stage */}
        <polygon points="-40,10 40,10 34,-34 10,-48 -26,-44 -40,-20" fill="var(--secondary-foreground)" opacity={0.9} />
        <rect x="-18" y="-28" width="16" height="14" fill="var(--space)" />
        <line x1="22" y1="-48" x2="30" y2="-66" stroke="var(--muted-foreground)" strokeWidth="2" />
        {/* RCS quads */}
        {[-46, 46].map((x) => (
          <g key={x}>
            <rect x={x - 4} y="-14" width="8" height="8" fill="var(--muted-foreground)" />
            {firing && <polygon points={`${x},-6 ${x - 5},${x > 0 ? 16 : 16} ${x + 5},16`} fill="var(--accent)" opacity={0.75} />}
          </g>
        ))}
      </g>
      <text x="20" y="505" fill="var(--muted-foreground)" fontFamily="IBM Plex Mono" fontSize="12">
        Illustration · attitude from recorded model pitch gimbal · altitude/position NOT modelled
      </text>
    </svg>
  );
}
