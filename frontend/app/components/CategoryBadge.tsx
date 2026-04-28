"use client";

// ── Setup Grade Badge (A+ / A / B / REJECT) ───────────────────────────────────

const GRADE_CONFIG: Record<string, {
  bg: string; border: string; text: string; label: string; glow?: string;
}> = {
  "A+":     { bg: "#031a0d", border: "#16a34a", text: "#4ade80", label: "A+ SETUP",  glow: "#4ade8022" },
  "A":      { bg: "#0c1a0c", border: "#65a30d", text: "#bef264", label: "A  SETUP" },
  "B":      { bg: "#1a1400", border: "#ca8a04", text: "#fde047", label: "B  SETUP" },
  "REJECT": { bg: "#1f0909", border: "#991b1b", text: "#f87171", label: "REJECT" },
};

export function SetupGradeBadge({ grade }: { grade: string }) {
  const c = GRADE_CONFIG[grade] ?? GRADE_CONFIG["REJECT"];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-black whitespace-nowrap tracking-wide"
      style={{
        background:  c.bg,
        border:      `1px solid ${c.border}`,
        color:       c.text,
        boxShadow:   c.glow ? `0 0 8px ${c.glow}` : undefined,
      }}
    >
      {c.label}
    </span>
  );
}

// ── Category Badge (rétrocompat) ──────────────────────────────────────────────

const CAT_CONFIG: Record<string, { bg: string; border: string; text: string; label: string }> = {
  "BUY NOW":               { bg: "#052e16", border: "#16a34a", text: "#4ade80", label: "🟢 BUY NOW" },
  "WAIT / SMALL POSITION": { bg: "#0c1a0c", border: "#65a30d", text: "#bef264", label: "🟡 SMALL POS." },
  "WAIT PULLBACK":         { bg: "#1c1500", border: "#ca8a04", text: "#fde047", label: "🟡 WAIT PULLBACK" },
  "WATCHLIST":             { bg: "#1a0e00", border: "#ea580c", text: "#fb923c", label: "🟠 WATCHLIST" },
  "AVOID":                 { bg: "#1f0909", border: "#991b1b", text: "#f87171", label: "🔴 AVOID" },
};

export function CategoryBadge({ category }: { category: string }) {
  const c = CAT_CONFIG[category] ?? CAT_CONFIG["AVOID"];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold whitespace-nowrap"
      style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.text }}
    >
      {c.label}
    </span>
  );
}

// ── Signal Badge ──────────────────────────────────────────────────────────────

const SIGNAL_CONFIG = {
  "Momentum": { color: "#818cf8", bg: "#1e1b4b" },
  "Pullback":  { color: "#fb923c", bg: "#1c0d00" },
  "Breakout":  { color: "#34d399", bg: "#022c22" },
  "Neutral":   { color: "#6b7280", bg: "#111118" },
};

export function SignalBadge({ signal }: { signal: string }) {
  const c = SIGNAL_CONFIG[signal as keyof typeof SIGNAL_CONFIG] ?? SIGNAL_CONFIG["Neutral"];
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.color}33` }}
    >
      {signal}
    </span>
  );
}

// ── Confidence Badge ──────────────────────────────────────────────────────────

export function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color =
    confidence >= 75 ? "#4ade80" :
    confidence >= 50 ? "#f59e0b" : "#f87171";
  const bg =
    confidence >= 75 ? "#052e16" :
    confidence >= 50 ? "#1a1000" : "#1f0909";
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold tabular-nums"
      style={{ background: bg, border: `1px solid ${color}44`, color }}
    >
      <span className="text-[9px]">⬡</span>{confidence}%
    </span>
  );
}
