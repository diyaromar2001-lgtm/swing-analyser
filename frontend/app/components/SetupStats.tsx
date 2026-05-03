"use client";

import { useEffect, useState } from "react";
import { SetupStats as SetupStatsType } from "../types";
import { getApiUrl } from "../lib/api";

const API_URL = getApiUrl();

function StatBox({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg p-3 text-center" style={{ background: "#0e0e16", border: "1px solid #1a1a28" }}>
      <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-sm font-black" style={{ color: color ?? "#e2e8f0" }}>{value}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

export function SetupStats({ ticker, grade }: { ticker: string; grade: string }) {
  const [data, setData]     = useState<SetupStatsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_URL}/api/setup-stats/${ticker}?grade=${encodeURIComponent(grade)}&period=24`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [ticker, grade]);

  const gradeColors: Record<string, string> = {
    "A+": "#4ade80",
    "A":  "#bef264",
    "B":  "#fde047",
  };
  const gc = gradeColors[grade] ?? "#818cf8";

  return (
    <div className="rounded-xl p-4" style={{ background: "#0d0d18", border: "1px solid #1a1a28" }}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">
          📊 Statistiques historiques — Setup {grade}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${gc}22`, color: gc }}>
          24 mois
        </span>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-gray-600 py-3">
          <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Calcul en cours (mêmes règles que le screener)…
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 py-2">Erreur : {error}</p>
      )}

      {!loading && !error && data && (
        <>
          {/* Avertissement échantillon faible */}
          {!data.sample_ok && data.n_trades > 0 && (
            <div className="mb-3 px-3 py-2 rounded-lg text-xs flex items-center gap-2"
              style={{ background: "#1a1000", border: "1px solid #ca8a0444", color: "#fde047" }}>
              ⚠️ Échantillon faible ({data.n_trades} occurrences) — statistiques peu significatives
            </div>
          )}

          {data.n_trades === 0 && (
            <div className="text-xs text-gray-600 py-2">
              {data.warning ?? `Aucun setup ${grade} trouvé sur 24 mois`}
            </div>
          )}

          {data.n_trades > 0 && data.win_rate !== undefined && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
                <StatBox
                  label="Win Rate"
                  value={`${data.win_rate}%`}
                  color={data.win_rate >= 55 ? "#4ade80" : data.win_rate >= 45 ? "#f59e0b" : "#ef4444"}
                />
                <StatBox
                  label="Expectancy"
                  value={`${data.expectancy! >= 0 ? "+" : ""}${data.expectancy}%`}
                  color={data.expectancy! >= 0 ? "#4ade80" : "#ef4444"}
                />
                <StatBox
                  label="Profit Factor"
                  value={data.profit_factor! >= 99 ? "∞" : `${data.profit_factor}x`}
                  color={data.profit_factor! >= 1.5 ? "#4ade80" : data.profit_factor! >= 1 ? "#f59e0b" : "#ef4444"}
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatBox
                  label="Occurrences"
                  value={`${data.n_trades}`}
                  sub="24 mois"
                  color={data.sample_ok ? "#e2e8f0" : "#f59e0b"}
                />
                <StatBox
                  label="Max Drawdown"
                  value={`${data.max_drawdown_pct}%`}
                  color={Math.abs(data.max_drawdown_pct ?? 0) < 10 ? "#4ade80" : "#ef4444"}
                />
                <StatBox
                  label="Durée moy."
                  value={`${data.avg_duration_days}j`}
                />
              </div>

              {/* Barre visuelle win rate */}
              <div className="mt-3">
                <div className="flex items-center justify-between text-[10px] text-gray-600 mb-1">
                  <span>Gains ({Math.round((data.win_rate / 100) * data.n_trades)} trades)</span>
                  <span>Pertes ({data.n_trades - Math.round((data.win_rate / 100) * data.n_trades)} trades)</span>
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ background: "#1a1a28" }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${data.win_rate}%`,
                      background: data.win_rate >= 55 ? "#4ade80" : data.win_rate >= 45 ? "#f59e0b" : "#ef4444",
                    }}
                  />
                </div>
                <p className="text-[10px] text-gray-600 mt-1 text-center">
                  Gain moy. <span className="text-green-400">+{data.avg_gain_pct}%</span>
                  {" · "}
                  Perte moy. <span className="text-red-400">-{data.avg_loss_pct}%</span>
                </p>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
