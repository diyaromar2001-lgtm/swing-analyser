"use client";
import { TickerResult } from "../types";
import { ScoreBar } from "./ScoreBar";
import { SignalBadge } from "./CategoryBadge";

function MiniRow({ row }: { row: TickerResult }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/[0.03] transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <span className="font-bold text-white text-sm w-14 shrink-0">{row.ticker}</span>
        <ScoreBar score={row.score} />
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span className="text-xs font-mono tabular-nums" style={{ color: row.perf_3m > 0 ? "#10b981" : "#ef4444" }}>
          {row.perf_3m > 0 ? "+" : ""}{row.perf_3m.toFixed(1)}%
        </span>
        <SignalBadge signal={row.signal_type} />
      </div>
    </div>
  );
}

export function DynamicCategories({ data }: { data: TickerResult[] }) {
  const momentum = data.filter(r => r.signal_type === "Momentum").slice(0, 5);
  const pullback = data.filter(r => r.signal_type === "Pullback").slice(0, 5);
  const breakout = data.filter(r => r.signal_type === "Breakout").slice(0, 5);

  const cats = [
    { label: "🚀 Top Momentum", color: "#818cf8", items: momentum },
    { label: "📉 Top Pullback", color: "#fb923c", items: pullback },
    { label: "💥 Top Breakout", color: "#34d399", items: breakout },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {cats.map(cat => (
        <div
          key={cat.label}
          className="rounded-xl overflow-hidden"
          style={{ background: "#0d0d18", border: `1px solid ${cat.color}33` }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: "#1e1e2a" }}>
            <h3 className="text-sm font-bold" style={{ color: cat.color }}>{cat.label}</h3>
          </div>
          <div className="p-2">
            {cat.items.length === 0 ? (
              <p className="text-xs text-gray-600 text-center py-4">Aucun signal détecté</p>
            ) : (
              cat.items.map(r => <MiniRow key={r.ticker} row={r} />)
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
