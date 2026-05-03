"use client";

import { useEffect, useState } from "react";
import { SignalTrackerData, TrackedSignal } from "../types";
import { EngineBanner } from "./BacktestView";
import { getApiUrl } from "../lib/api";

const API_URL = getApiUrl();

function OutcomeBadge({ outcome }: { outcome: TrackedSignal["outcome"] }) {
  if (!outcome) return (
    <span className="px-2 py-0.5 rounded text-[10px] font-bold"
      style={{ background: "#1e1e3a", color: "#818cf8" }}>OPEN</span>
  );
  const cfg = {
    TP2:  { bg: "#031a0d", color: "#4ade80", label: "TP2 ✓" },
    TP1:  { bg: "#0c1a0c", color: "#86efac", label: "TP1 ✓" },
    SL:   { bg: "#1f0909", color: "#f87171", label: "SL ✗" },
    OPEN: { bg: "#1e1e3a", color: "#818cf8", label: "OPEN" },
  };
  const c = cfg[outcome] ?? cfg.OPEN;
  return (
    <span className="px-2 py-0.5 rounded text-[10px] font-bold"
      style={{ background: c.bg, color: c.color }}>{c.label}</span>
  );
}

function GradeChip({ grade }: { grade: string }) {
  const colors: Record<string, { bg: string; color: string }> = {
    "A+": { bg: "#031a0d", color: "#4ade80" },
    "A":  { bg: "#0c1a0c", color: "#bef264" },
    "B":  { bg: "#1a1400", color: "#fde047" },
  };
  const c = colors[grade] ?? colors["B"];
  return (
    <span className="px-1.5 py-0.5 rounded text-[10px] font-black"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.color}44` }}>{grade}</span>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl p-3 text-center" style={{ background: "#0d0d18", border: `1px solid ${color ?? "#818cf8"}22` }}>
      <p className="text-[10px] font-bold mb-1" style={{ color: color ?? "#818cf8" }}>{label}</p>
      <p className="text-xl font-black text-white">{value}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source || source === "pending") return (
    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold"
      style={{ background: "#1e1e3a", color: "#6b7280" }}>PENDING</span>
  );
  if (source === "ohlc") return (
    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold"
      style={{ background: "#031a0d", color: "#4ade80", border: "1px solid #4ade8033" }}>OHLC ✓</span>
  );
  return (
    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold"
      style={{ background: "#1a1400", color: "#fde047", border: "1px solid #fde04733" }}>SNAP</span>
  );
}

export function SignalTracker() {
  const [data, setData]       = useState<SignalTrackerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState<string>("ALL");

  const load = () => {
    setLoading(true);
    fetch(`${API_URL}/api/signals?limit=200`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = data?.signals.filter(s =>
    filter === "ALL" ? true :
    filter === "OPEN" ? !s.outcome :
    filter === s.setup_grade
  ) ?? [];

  const stats = data?.stats;

  return (
    <div className="space-y-5">
      {/* Bannière cohérence moteur */}
      <EngineBanner />

      {/* Titre */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-black text-white">📈 Performance réelle des signaux</h2>
          <p className="text-xs text-gray-600 mt-0.5">
            Suivi barre-par-barre via OHLC · Outcome évalué dès le lendemain du signal · Même logique TP/SL que le Backtest
          </p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          style={{ background: "#1e1e3a", border: "1px solid #4f46e5", color: "#818cf8" }}
        >
          ↻ Actualiser
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-gray-600 py-8 justify-center">
          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Chargement…
        </div>
      )}

      {!loading && stats && (
        <>
          {/* Stats globales */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            <StatCard label="Total Signaux" value={stats.total}  color="#818cf8" />
            <StatCard label="Ouverts"       value={stats.open}   color="#f59e0b"
              sub="En attente" />
            <StatCard label="Clôturés"      value={stats.closed} color="#9ca3af"
              sub="TP1/TP2/SL" />
            <StatCard label="Win Rate"      value={`${stats.win_rate}%`}
              color={stats.win_rate >= 55 ? "#4ade80" : stats.win_rate >= 45 ? "#f59e0b" : "#ef4444"}
              sub="Clôturés uniquement" />
            <StatCard label="P&L Moy."
              value={`${stats.avg_pnl >= 0 ? "+" : ""}${stats.avg_pnl}%`}
              color={stats.avg_pnl >= 0 ? "#4ade80" : "#ef4444"}
              sub="Clôturés uniquement" />
            <StatCard label="Gains/Pertes"
              value={`${stats.wins}/${stats.losses}`}
              color="#34d399" />
          </div>

          {/* OHLC win rate — source la plus fiable */}
          {stats.ohlc_win_rate !== null && stats.ohlc_closed > 0 && (
            <div className="rounded-xl px-4 py-3 flex items-center gap-4 flex-wrap"
              style={{ background: "#031a0d", border: "1px solid #4ade8033" }}>
              <span className="text-[10px] font-bold text-green-400 uppercase tracking-widest">🟢 OHLC Confirmés</span>
              <span className="text-sm font-black text-white">{stats.ohlc_win_rate}%</span>
              <span className="text-xs text-gray-500">Win rate sur {stats.ohlc_closed} trade(s) confirmé(s) barre-par-barre</span>
              <span className="ml-auto text-[10px] text-green-700">Source la plus fiable · snapshot exclus</span>
            </div>
          )}

          {/* Stats par grade */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(["A+", "A", "B"] as const).map(grade => {
              const g = stats.by_grade[grade];
              if (!g || g.total === 0) return null;
              const gradeColor = grade === "A+" ? "#4ade80" : grade === "A" ? "#bef264" : "#fde047";
              return (
                <div key={grade} className="rounded-xl p-3"
                  style={{ background: "#0d0d18", border: `1px solid ${gradeColor}22` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <GradeChip grade={grade} />
                    <span className="text-xs text-gray-500">{g.total} signaux</span>
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Win rate</span>
                      <span className="font-bold" style={{ color: g.win_rate >= 55 ? "#4ade80" : "#f59e0b" }}>
                        {g.win_rate}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">P&L moy.</span>
                      <span className="font-bold" style={{ color: g.avg_pnl >= 0 ? "#4ade80" : "#ef4444" }}>
                        {g.avg_pnl >= 0 ? "+" : ""}{g.avg_pnl}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Clôturés</span>
                      <span className="text-gray-400">{g.closed}/{g.total}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Filtres */}
          <div className="flex gap-2 flex-wrap">
            {["ALL", "OPEN", "A+", "A", "B"].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: filter === f ? "#1e1e3a" : "#0d0d18",
                  border:     `1px solid ${filter === f ? "#4f46e5" : "#1e1e2a"}`,
                  color:      filter === f ? "#818cf8" : "#4b5563",
                }}
              >
                {f === "ALL" ? `Tous (${stats.total})` :
                 f === "OPEN" ? `Ouverts (${stats.open})` :
                 `${f} (${stats.by_grade[f]?.total ?? 0})`}
              </button>
            ))}
            <span className="ml-auto text-xs text-gray-600 self-center">{filtered.length} résultats</span>
          </div>

          {/* Table */}
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-gray-600 text-sm">
              {stats.total === 0
                ? "Aucun signal enregistré — lancez le screener pour commencer le tracking."
                : "Aucun résultat pour ce filtre."}
            </div>
          ) : (
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
                      {["Date", "Ticker", "Grade", "Prix", "Entrée", "TP2", "SL", "R/R", "Outcome", "P&L", "Jours", "Source"].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-[10px] font-bold text-gray-600 uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(s => (
                      <tr
                        key={s.id}
                        style={{ borderBottom: "1px solid #1a1a28" }}
                        className="hover:bg-white/[0.02] transition-colors"
                      >
                        <td className="px-3 py-2 text-gray-500">{s.date}</td>
                        <td className="px-3 py-2 font-bold text-white">{s.ticker}</td>
                        <td className="px-3 py-2"><GradeChip grade={s.setup_grade} /></td>
                        <td className="px-3 py-2 text-gray-300">${s.price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-gray-300">${s.entry.toFixed(2)}</td>
                        <td className="px-3 py-2" style={{ color: "#10b981" }}>${s.tp2.toFixed(2)}</td>
                        <td className="px-3 py-2" style={{ color: "#ef4444" }}>${s.stop_loss.toFixed(2)}</td>
                        <td className="px-3 py-2 text-gray-400">1:{s.rr_ratio.toFixed(1)}</td>
                        <td className="px-3 py-2"><OutcomeBadge outcome={s.outcome} /></td>
                        <td className="px-3 py-2 font-bold"
                          style={{ color: s.pnl_pct === null ? "#6b7280" : s.pnl_pct >= 0 ? "#4ade80" : "#ef4444" }}>
                          {s.pnl_pct === null ? "—" : `${s.pnl_pct >= 0 ? "+" : ""}${s.pnl_pct}%`}
                        </td>
                        <td className="px-3 py-2 text-gray-500">
                          {s.days_held !== null ? `${s.days_held}j` : "—"}
                        </td>
                        <td className="px-3 py-2">
                          <SourceBadge source={s.outcome_source} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
