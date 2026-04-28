"use client";

export function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 85 ? "#10b981" :
    score >= 70 ? "#34d399" :
    score >= 50 ? "#f59e0b" :
    score >= 40 ? "#f97316" : "#ef4444";

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "#2a2a3a" }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="text-sm font-bold tabular-nums" style={{ color }}>{score}</span>
    </div>
  );
}
