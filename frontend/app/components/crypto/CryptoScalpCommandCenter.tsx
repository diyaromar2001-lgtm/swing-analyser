"use client";

import { useState, useEffect } from "react";
import { getApiUrl } from "../../lib/api";
import { CryptoScalpTradePlan } from "./CryptoScalpTradePlan";
import { CryptoScalpPaperJournal } from "./CryptoScalpPaperJournal";
import { CryptoScalpPerformance } from "./CryptoScalpPerformance";

const API_URL = getApiUrl();

export interface CryptoScalpResult {
  symbol: string;
  tier: number;
  side: "LONG" | "SHORT" | "NONE";
  scalp_score: number;
  scalp_grade: string;
  long_score: number;
  short_score: number;
  strategy_name: string | null;
  timeframe: string;
  entry: number | null;
  stop_loss: number | null;
  tp1: number | null;
  tp2: number | null;
  rr_ratio: number | null;
  spread_status: string;
  data_status: string;
  volatility_status: string;
  scalp_execution_authorized: boolean;
  paper_allowed: boolean;
  watchlist_allowed: boolean;
  blocked_reasons: string[];
  signal_reasons: string[];
  spread_bps?: number;
  entry_fee_pct?: number;
  exit_fee_pct?: number;
  slippage_pct?: number;
  estimated_roundtrip_cost_pct?: number;
  estimated_net_rr?: number;
}

export function CryptoScalpCommandCenter({ loading }: { loading: boolean }) {
  const [results, setResults] = useState<CryptoScalpResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [tierFilter, setTierFilter] = useState<number | null>(null);
  const [view, setView] = useState<"screener" | "analysis" | "journal" | "performance">("screener");
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [selectedResult, setSelectedResult] = useState<CryptoScalpResult | null>(null);

  useEffect(() => {
    const fetchScalp = async () => {
      setIsLoading(true);
      try {
        const params = new URLSearchParams({
          sort_by: "scalp_score",
          reverse: "true",
          limit: "50",
          min_score: minScore.toString(),
        });
        if (tierFilter) params.append("tier_filter", tierFilter.toString());

        const res = await fetch(`${API_URL}/api/crypto/scalp/screener?${params}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();
        setResults(json.symbols || []);
      } catch (err) {
        console.error("Scalp screener error:", err);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchScalp();
  }, [minScore, tierFilter]);

  const fetchAnalysis = async (symbol: string) => {
    try {
      const res = await fetch(`${API_URL}/api/crypto/scalp/analyze/${symbol}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();
      setSelectedResult(result);
      setSelectedSymbol(symbol);
      setView("analysis");
    } catch (err) {
      console.error("Analysis fetch error:", err);
    }
  };

  return (
    <div className="w-full">
      {/* Header & Tabs */}
      <div className="rounded-xl p-4 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
        <h2 className="text-lg font-black text-white mb-3">🎯 Crypto Scalp (Phase 1 — Paper Only)</h2>
        <p className="text-xs text-gray-500 mb-4">Intraday signals LONG/SHORT. Real trading disabled in Phase 1.</p>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 flex-wrap">
          {["screener", "analysis", "journal", "performance"].map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setView(tab as typeof view);
                if (tab === "screener") setSelectedSymbol(null);
              }}
              className="px-4 py-2 rounded-lg text-xs font-bold transition-all"
              style={{
                background: view === tab ? "#1e1e3a" : "#0d0d18",
                border: `1px solid ${view === tab ? "#818cf8" : "#1e1e2a"}`,
                color: view === tab ? "#818cf8" : "#4b5563",
              }}
            >
              {tab === "screener" ? "📡 Screener" : tab === "analysis" ? "📊 Analysis" : tab === "journal" ? "📓 Journal" : "📈 Performance"}
            </button>
          ))}
        </div>

        {/* Filters (screener only) */}
        {view === "screener" && (
          <div className="flex gap-3 flex-wrap">
            <div>
              <label className="block text-[10px] font-bold text-gray-600 mb-1">Min Score</label>
              <input
                type="range"
                min="0"
                max="100"
                value={minScore}
                onChange={(e) => setMinScore(parseInt(e.target.value))}
                className="w-32 h-1 rounded-lg"
              />
              <span className="text-xs text-gray-400">{minScore}</span>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-gray-600 mb-1">Tier</label>
              <select
                value={tierFilter ?? "all"}
                onChange={(e) => setTierFilter(e.target.value === "all" ? null : parseInt(e.target.value))}
                className="px-2 py-1 rounded-lg text-xs bg-gray-900 border border-gray-700 text-white"
              >
                <option value="all">All</option>
                <option value="1">Tier 1</option>
                <option value="2">Tier 2</option>
                <option value="3">Tier 3</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Content based on view */}
      {view === "screener" && (
        <>
          {isLoading ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              <p className="text-sm text-gray-600">Loading...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              <p className="text-sm text-gray-600">No signals found</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.map((r) => (
                <CryptoScalpCard key={r.symbol} result={r} onSelect={() => fetchAnalysis(r.symbol)} />
              ))}
            </div>
          )}
        </>
      )}

      {view === "analysis" && selectedResult && (
        <div>
          <button
            onClick={() => {
              setView("screener");
              setSelectedSymbol(null);
              setSelectedResult(null);
            }}
            className="mb-4 px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-900 border border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-300 transition"
          >
            ← Back to Screener
          </button>
          <CryptoScalpTradePlan result={selectedResult} />
        </div>
      )}

      {view === "journal" && <CryptoScalpPaperJournal />}

      {view === "performance" && <CryptoScalpPerformance />}
    </div>
  );
}

function CryptoScalpCard({ result, onSelect }: { result: CryptoScalpResult; onSelect: () => void }) {
  const tierColor = result.tier === 1 ? "#4ade80" : result.tier === 2 ? "#fde047" : "#6b7280";
  const sideColor = result.side === "LONG" ? "#4ade80" : result.side === "SHORT" ? "#ef4444" : "#6b7280";
  const gradeColor = result.scalp_grade === "SCALP_A+" ? "#4ade80"
    : result.scalp_grade === "SCALP_A" ? "#bef264"
    : result.scalp_grade === "SCALP_B" ? "#fde047"
    : "#6b7280";

  return (
    <div className="rounded-lg p-4" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg font-black text-white">{result.symbol}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${tierColor}22`, color: tierColor }}>
          Tier {result.tier}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${sideColor}22`, color: sideColor }}>
          {result.side}
        </span>
      </div>

      {/* Score & Grade */}
      <div className="mb-3 pb-3 border-b border-gray-800">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-600">Score</span>
          <span className="text-sm font-bold" style={{ color: "#818cf8" }}>{result.scalp_score}/100</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-600">Grade</span>
          <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: `${gradeColor}22`, color: gradeColor }}>
            {result.scalp_grade}
          </span>
        </div>
      </div>

      {/* Scores */}
      <div className="grid grid-cols-2 gap-2 mb-3 pb-3 border-b border-gray-800 text-[10px]">
        <div>
          <p className="text-gray-600">LONG</p>
          <p className="text-sm font-bold text-green-400">{result.long_score}</p>
        </div>
        <div>
          <p className="text-gray-600">SHORT</p>
          <p className="text-sm font-bold text-red-400">{result.short_score}</p>
        </div>
      </div>

      {/* Entry/Stop/TP */}
      {result.side !== "NONE" && (
        <div className="mb-3 pb-3 border-b border-gray-800 text-[10px]">
          <p className="text-gray-600 mb-1">Entry: <span className="text-white font-bold">{result.entry?.toFixed(4)}</span></p>
          <p className="text-gray-600 mb-1">Stop: <span className="text-red-400 font-bold">{result.stop_loss?.toFixed(4)}</span></p>
          <p className="text-gray-600">TP: <span className="text-green-400 font-bold">{result.tp1?.toFixed(4)}</span> / <span className="text-green-400 font-bold">{result.tp2?.toFixed(4)}</span></p>
          {result.rr_ratio && <p className="text-gray-600 mt-1">R/R: <span className="text-cyan-400 font-bold">1:{result.rr_ratio}</span></p>}
        </div>
      )}

      {/* Status */}
      <div className="text-[10px] space-y-1">
        <p className="text-gray-600">Data: <span style={{ color: result.data_status === "FRESH" ? "#4ade80" : "#ef4444" }} className="font-bold">{result.data_status}</span></p>
        <p className="text-gray-600">Spread: <span style={{ color: result.spread_status === "OK" ? "#4ade80" : "#f59e0b" }} className="font-bold">{result.spread_status}</span></p>
        <p className="text-gray-600">Paper: <span style={{ color: result.paper_allowed ? "#4ade80" : "#ef4444" }} className="font-bold">{result.paper_allowed ? "✓" : "✗"}</span></p>
      </div>

      {/* Signals/Warnings */}
      {result.signal_reasons.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <p className="text-[9px] font-bold text-green-400 mb-1">Signals:</p>
          {result.signal_reasons.map((s, i) => (
            <p key={i} className="text-[9px] text-gray-500">• {s}</p>
          ))}
        </div>
      )}

      {result.blocked_reasons.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-800">
          <p className="text-[9px] font-bold text-red-400 mb-1">Blocked:</p>
          {result.blocked_reasons.map((b, i) => (
            <p key={i} className="text-[9px] text-gray-500">• {b}</p>
          ))}
        </div>
      )}

      {/* Action Button */}
      <button
        onClick={onSelect}
        className="w-full mt-4 px-3 py-2 rounded-lg text-xs font-bold bg-cyan-900 border border-cyan-600 text-cyan-300 hover:bg-cyan-800 transition"
      >
        View Analysis →
      </button>
    </div>
  );
}
