"use client";

export type EdgeStatus =
  | "STRONG_EDGE"
  | "VALID_EDGE"
  | "WEAK_EDGE"
  | "NO_EDGE"
  | "OVERFITTED";

const EDGE_CFG: Record<EdgeStatus, { label: string; color: string; bg: string }> = {
  STRONG_EDGE: { label: "⚡ STRONG",   color: "#4ade80", bg: "#052e16" },
  VALID_EDGE:  { label: "✓ VALID",    color: "#86efac", bg: "#031a0d" },
  WEAK_EDGE:   { label: "~ WEAK",     color: "#fde047", bg: "#1c1500" },
  NO_EDGE:     { label: "— NO EDGE",  color: "#6b7280", bg: "#111118" },
  OVERFITTED:  { label: "⚠ OVERFIT",  color: "#f59e0b", bg: "#1c1000" },
};

export function EdgeStatusBadge({ status }: { status?: EdgeStatus | string | null }) {
  const s = (status as EdgeStatus) ?? "NO_EDGE";
  const c = EDGE_CFG[s] ?? EDGE_CFG["NO_EDGE"];
  return (
    <span
      className="text-[10px] font-black px-1.5 py-0.5 rounded whitespace-nowrap"
      style={{ color: c.color, background: c.bg, border: `1px solid ${c.color}33` }}
    >
      {c.label}
    </span>
  );
}

export function EdgeScoreBar({ score }: { score?: number }) {
  const s = score ?? 0;
  const color = s >= 70 ? "#4ade80" : s >= 45 ? "#fde047" : "#6b7280";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-14 h-1.5 rounded-full" style={{ background: "#1e1e2a" }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${s}%`, background: color }}
        />
      </div>
      <span className="text-[10px] font-bold tabular-nums" style={{ color }}>
        {s}
      </span>
    </div>
  );
}

/** Petit badge pour la stratégie avec son emoji + nom court */
export function BestStrategyBadge({
  name,
  color,
  emoji,
}: {
  name?: string | null;
  color?: string;
  emoji?: string;
}) {
  if (!name) return <span className="text-[10px] text-gray-700">—</span>;
  const c = color ?? "#6b7280";
  // Abréger le nom
  const short = name
    .replace("Pullback Trend", "Pullback")
    .replace("Breakout Quality", "Breakout")
    .replace("Relative Strength Leader", "Rel. Strength")
    .replace("Low Volatility Compounder", "Low Vol")
    .replace("Mean Reversion in Uptrend", "Mean Rev.");
  return (
    <span
      className="text-[10px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap"
      style={{ color: c, background: `${c}18`, border: `1px solid ${c}33` }}
    >
      {emoji} {short}
    </span>
  );
}
