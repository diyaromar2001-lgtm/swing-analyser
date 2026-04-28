"use client";
import { ScoreDetail } from "../types";

function Block({ label, score, max, checks }: {
  label: string; score: number; max: number;
  checks: { label: string; ok: boolean }[];
}) {
  const pct   = (score / max) * 100;
  const color = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="rounded-lg p-3" style={{ background: "#0e0e16", border: "1px solid #2a2a3a" }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold text-gray-300 uppercase tracking-wider">{label}</span>
        <span className="text-sm font-bold" style={{ color }}>{score}/{max}</span>
      </div>
      <div className="space-y-1">
        {checks.map(c => (
          <div key={c.label} className="flex items-center gap-2 text-xs">
            <span>{c.ok ? "✅" : "❌"}</span>
            <span className={c.ok ? "text-gray-300" : "text-gray-600"}>{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ScoreBreakdown({ detail, ticker }: { detail: ScoreDetail; ticker: string }) {
  const d = detail.details;
  return (
    <div className="p-4">
      <p className="text-xs text-gray-500 mb-3 font-medium">Détail du score — {ticker}</p>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Block label="📈 Tendance" score={detail.trend} max={30} checks={[
          { label: "Prix > SMA200",          ok: d.prix_above_sma200 },
          { label: "SMA50 > SMA200",         ok: d.sma50_above_sma200 },
          { label: "Pente SMA50 positive",   ok: d.sma50_slope_positive },
          { label: "Dans les 15% du 52W high", ok: d.near_52w_high },
        ]} />
        <Block label="⚡ Momentum" score={detail.momentum} max={25} checks={[
          { label: "RSI en zone idéale (50–70)", ok: d.rsi_ideal_zone },
          { label: "MACD positif",               ok: d.macd_positif },
          { label: "Perf 3m positive",           ok: d.perf_3m_positive },
        ]} />
        <Block label="🎯 Risk / Reward" score={detail.risk_reward} max={20} checks={[
          { label: "R/R ≥ 1.5 (SL/TP dynamiques)", ok: d.rr_suffisant },
        ]} />
        <Block label="💪 Force Relative" score={detail.relative_strength} max={15} checks={[
          { label: "Surperforme le S&P500", ok: d.outperforms_sp500 },
        ]} />
        <Block label="📊 Volume" score={detail.volume_quality} max={10} checks={[
          { label: "Volume > moyenne 30j (+30%)", ok: d.volume_eleve },
        ]} />
      </div>
    </div>
  );
}
