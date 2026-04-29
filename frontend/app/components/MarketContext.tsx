"use client";

import { useEffect, useState } from "react";
import { MarketContext as MarketContextType } from "../types";
import { getApiUrl } from "../lib/api";

const API_URL = getApiUrl();

function VixGauge({ vix, regime }: { vix: number; regime: string }) {
  const color =
    regime === "LOW"      ? "#4ade80" :
    regime === "NORMAL"   ? "#86efac" :
    regime === "ELEVATED" ? "#fde047" :
    regime === "HIGH"     ? "#fb923c" : "#ef4444";

  return (
    <div className="text-center">
      <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">VIX</p>
      <p className="text-2xl font-black" style={{ color }}>{vix}</p>
      <p className="text-[10px] mt-0.5" style={{ color }}>{regime}</p>
    </div>
  );
}

function BreadthBar({ pct }: { pct: number }) {
  const color = pct > 65 ? "#4ade80" : pct > 50 ? "#f59e0b" : "#ef4444";
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] text-gray-600 uppercase tracking-wider">
          % Tickers &gt; SMA50
        </p>
        <p className="text-xs font-bold" style={{ color }}>{pct}%</p>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: "#1a1a28" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <p className="text-[10px] text-gray-600 mt-1">
        {pct > 65 ? "Marché sain — majorité en tendance" :
         pct > 50 ? "Breadth neutre" :
         "Détérioration — peu de titres en tendance"}
      </p>
    </div>
  );
}

export function MarketContext() {
  const [data, setData]       = useState<MarketContextType | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen]       = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/market-context`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="rounded-xl px-4 py-3 mb-5 flex items-center gap-2 text-xs text-gray-600"
      style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
      <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      Analyse du contexte marché…
    </div>
  );

  if (!data) return null;

  const conditionColors = {
    FAVORABLE: { bg: "#031a0d", border: "#16a34a44", text: "#4ade80" },
    NEUTRAL:   { bg: "#1a1400", border: "#ca8a0444", text: "#fde047" },
    DANGEROUS: { bg: "#1f0909", border: "#991b1b44", text: "#f87171" },
  };
  const cc = conditionColors[data.condition] ?? conditionColors.NEUTRAL;

  // Secteurs triés par perf 1m
  const sortedSectors = Object.entries(data.sector_strength)
    .sort((a, b) => b[1].perf_1m - a[1].perf_1m);

  return (
    <div className="mb-5 rounded-xl overflow-hidden" style={{ border: `1px solid ${cc.border}` }}>
      {/* Header cliquable */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        style={{ background: cc.bg }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <span className="text-base">{data.condition_emoji}</span>
          <div>
            <p className="text-xs font-black text-white tracking-wide">{data.condition_label}</p>
            <p className="text-[10px] text-gray-500 mt-0.5">
              VIX {data.vix} · Breadth {data.market_breadth_pct}% · {data.positive_sectors}/{data.total_sectors} secteurs positifs
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data.condition === "DANGEROUS" && (
            <span className="text-[10px] font-bold text-red-400 bg-red-950 px-2 py-0.5 rounded">
              ⚠️ Réduire les positions
            </span>
          )}
          <svg
            className={`h-4 w-4 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Contenu expandable */}
      {open && (
        <div className="px-4 py-4 space-y-4" style={{ background: "#0a0a14" }}>
          {/* VIX + Breadth */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 items-center"
            style={{ borderBottom: "1px solid #1a1a28", paddingBottom: "16px" }}>
            <VixGauge vix={data.vix} regime={data.vix_regime} />
            <div className="col-span-3">
              <BreadthBar pct={data.market_breadth_pct} />
            </div>
          </div>

          {/* Secteurs */}
          <div>
            <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">
              Force des Secteurs (perf 1m)
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {sortedSectors.map(([sector, s]) => {
                const p = s.perf_1m;
                const color = p > 3 ? "#4ade80" : p > 0 ? "#86efac" : p > -3 ? "#fb923c" : "#ef4444";
                const barW  = Math.min(100, Math.abs(p) * 6);
                return (
                  <div key={sector} className="rounded-lg px-3 py-2"
                    style={{ background: "#0e0e16", border: "1px solid #1a1a28" }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-gray-400 truncate mr-2">{sector}</span>
                      <span className="text-[10px] font-bold shrink-0" style={{ color }}>
                        {p >= 0 ? "+" : ""}{p}%
                      </span>
                    </div>
                    <div className="h-1 rounded-full" style={{ background: "#1a1a28" }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${barW}%`,
                          background: color,
                          marginLeft: p < 0 ? "auto" : undefined,
                        }}
                      />
                    </div>
                    <p className="text-[9px] text-gray-700 mt-0.5">{s.etf} · RSI {s.rsi}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recommandation */}
          <div className="rounded-lg px-3 py-2 text-xs"
            style={{ background: `${cc.text}11`, border: `1px solid ${cc.text}33`, color: cc.text }}>
            {data.condition === "FAVORABLE" &&
              "✅ Conditions favorables — Prendre les setups A+ et A sans hésiter"}
            {data.condition === "NEUTRAL" &&
              "⚠️ Contexte neutre — Privilégier les A+ uniquement, positions réduites"}
            {data.condition === "DANGEROUS" &&
              "🔴 Marché dangereux — Rester en cash ou positions très limitées sur A+ uniquement"}
          </div>
        </div>
      )}
    </div>
  );
}
