"use client";
import { useState } from "react";
import { TickerResult } from "../types";
import { ScoreBar } from "./ScoreBar";
import { SetupGradeBadge, SignalBadge } from "./CategoryBadge";
import { TradePlan } from "./TradePlan";

export function Top5Cards({ data }: { data: TickerResult[] }) {
  const [tradePlan, setTradePlan] = useState<TickerResult | null>(null);

  // Top 3 A+ d'abord, complété par A si besoin, puis B
  const ranked = [
    ...data.filter(r => r.setup_grade === "A+"),
    ...data.filter(r => r.setup_grade === "A"),
    ...data.filter(r => r.setup_grade === "B"),
  ].slice(0, 5);

  if (ranked.length === 0) return null;

  const top3 = ranked.slice(0, 3);

  const gradeGlow: Record<string, string> = {
    "A+": "#4ade80",
    "A":  "#bef264",
    "B":  "#fde047",
  };

  return (
    <>
      {tradePlan && <TradePlan row={tradePlan} onClose={() => setTradePlan(null)} />}

      {/* ── Question centrale ── */}
      <div className="mb-6 rounded-2xl p-5" style={{ background: "linear-gradient(135deg, #0a0a1a, #0d0d22)", border: "1px solid #2a2a4a" }}>
        <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-2">
          Réponse du jour
        </p>
        <p className="text-lg font-black text-white mb-4">
          🎯 Quelles sont les meilleures actions à trader aujourd&apos;hui ?
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {top3.map((row, i) => {
            const glow = gradeGlow[row.setup_grade] ?? "#818cf8";
            const medals = ["🥇", "🥈", "🥉"];
            return (
              <div
                key={row.ticker}
                className="rounded-xl p-4 relative overflow-hidden cursor-pointer hover:opacity-90 transition-all"
                style={{
                  background:  "#0a0a14",
                  border:      `1px solid ${glow}44`,
                  boxShadow:   `0 0 20px ${glow}11`,
                }}
                onClick={() => setTradePlan(row)}
              >
                <div className="absolute top-2 right-3 text-5xl font-black opacity-[0.06]" style={{ color: glow }}>
                  {i + 1}
                </div>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="text-base mr-1">{medals[i]}</span>
                    <span className="text-xl font-black text-white">{row.ticker}</span>
                    <p className="text-[11px] text-gray-500 mt-0.5">{row.sector}</p>
                  </div>
                  <SetupGradeBadge grade={row.setup_grade} />
                </div>
                <ScoreBar score={row.score} />
                <div className="mt-3 grid grid-cols-3 gap-1.5 text-center">
                  <div>
                    <p className="text-[9px] text-gray-600 uppercase">Entrée</p>
                    <p className="text-xs font-bold text-gray-300">${row.entry.toFixed(0)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-gray-600 uppercase">TP2</p>
                    <p className="text-xs font-bold" style={{ color: "#10b981" }}>${row.tp2.toFixed(0)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-gray-600 uppercase">SL</p>
                    <p className="text-xs font-bold" style={{ color: "#ef4444" }}>${row.stop_loss.toFixed(0)}</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <SignalBadge signal={row.signal_type} />
                    <span className="text-[10px] text-gray-600">
                      R/R&nbsp;<span className="font-bold" style={{ color: row.rr_ratio >= 2 ? "#4ade80" : "#f59e0b" }}>
                        1:{row.rr_ratio.toFixed(1)}
                      </span>
                    </span>
                  </div>
                  <span
                    className="text-[10px] font-bold tabular-nums"
                    style={{ color: row.perf_3m > 0 ? "#10b981" : "#ef4444" }}
                  >
                    {row.perf_3m > 0 ? "+" : ""}{row.perf_3m.toFixed(1)}% 3m
                  </span>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); setTradePlan(row); }}
                  className="w-full mt-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-90"
                  style={{ background: "#1e1e3a", border: "1px solid #4f46e5", color: "#818cf8" }}
                >
                  📋 Voir le Trade Plan complet
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Watchlist (rang 4–5) ── */}
      {ranked.length > 3 && (
        <div className="mb-6">
          <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
            👁 Watchlist — Prochaines opportunités
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {ranked.slice(3, 5).map((row, i) => (
              <div
                key={row.ticker}
                className="rounded-xl p-3 flex items-center gap-3 cursor-pointer hover:bg-white/[0.02] transition-all"
                style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}
                onClick={() => setTradePlan(row)}
              >
                <div className="text-sm font-black text-gray-600 w-4">#{i + 4}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-black text-white text-sm">{row.ticker}</span>
                    <SetupGradeBadge grade={row.setup_grade} />
                    <SignalBadge signal={row.signal_type} />
                  </div>
                  <p className="text-[10px] text-gray-600">{row.sector} · Score {row.score}/100 · R/R 1:{row.rr_ratio.toFixed(1)}</p>
                </div>
                <ScoreBar score={row.score} />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
