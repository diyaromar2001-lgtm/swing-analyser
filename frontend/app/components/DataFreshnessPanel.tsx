"use client";

import { DataFreshness } from "../types";

function formatTime(ts?: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("fr-FR");
}

function formatAgo(ts?: string | null): string {
  if (!ts) return "jamais";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "jamais";
  const diff = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (diff < 60) return `il y a ${diff}s`;
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)}m`;
  return `il y a ${Math.floor(diff / 3600)}h`;
}

function ttlLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${Math.round(seconds / 3600)}h`;
}

export function DataFreshnessPanel({
  freshness,
  onFullRefresh,
  onPriceRefresh,
  loading,
  priceRefreshing,
}: {
  freshness: DataFreshness | null;
  onFullRefresh: () => void;
  onPriceRefresh: () => void;
  loading: boolean;
  priceRefreshing: boolean;
}) {
  const rows = [
    {
      title: "Prix actuel",
      subtitle: freshness?.price_label ?? "Prix live approximatif / différé",
      ttl: freshness?.price_ttl_seconds ?? 60,
      ts: freshness?.last_price_update,
      accent: "#10b981",
    },
    {
      title: "Screener / indicateurs",
      subtitle: freshness?.screener_label ?? "Analyse daily",
      ttl: freshness?.screener_ttl_seconds ?? 14400,
      ts: freshness?.last_screener_update,
      accent: "#818cf8",
    },
    {
      title: "Market regime",
      subtitle: freshness?.regime_label ?? "Cache 1h",
      ttl: freshness?.regime_ttl_seconds ?? 3600,
      ts: freshness?.last_regime_update,
      accent: "#f59e0b",
    },
    {
      title: "Market context",
      subtitle: freshness?.market_context_label ?? "Cache 5min",
      ttl: freshness?.market_context_ttl_seconds ?? 300,
      ts: freshness?.last_market_context_update,
      accent: "#34d399",
    },
    {
      title: "Strategy Edge",
      subtitle: freshness?.edge_label ?? "Cache 24h",
      ttl: freshness?.edge_ttl_seconds ?? 86400,
      ts: freshness?.last_edge_update,
      accent: "#f97316",
    },
  ];

  return (
    <div className="rounded-2xl p-4 mb-4" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div>
          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest">Data Freshness</p>
          <p className="text-xs text-gray-500 mt-1">
            Outil swing trading basé sur <strong className="text-gray-300">analyse daily</strong> + <strong className="text-gray-300">prix actuel rafraîchi</strong>.
            Pas de tick-by-tick.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={onPriceRefresh}
            disabled={priceRefreshing}
            className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#10b981" }}
          >
            {priceRefreshing ? "Prix…" : "Rafraîchir prix seulement"}
          </button>
          <button
            onClick={onFullRefresh}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
            style={{ background: "#1e1e3a", border: "1px solid #2a2a4a", color: "#818cf8" }}
          >
            {loading ? "Analyse…" : "Recalculer l’analyse complète"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        {rows.map((row) => (
          <div
            key={row.title}
            className="rounded-xl p-3"
            style={{ background: "#07070f", border: `1px solid ${row.accent}22` }}
          >
            <p className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color: row.accent }}>
              {row.title}
            </p>
            <p className="text-[11px] text-gray-400 mb-2">{row.subtitle}</p>
            <p className="text-sm font-black text-white">{formatTime(row.ts)}</p>
            <p className="text-[10px] text-gray-600">{formatAgo(row.ts)}</p>
            <p className="text-[10px] text-gray-700 mt-2">TTL: {ttlLabel(row.ttl)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
