"use client";

import { useState } from "react";

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
}

export function CryptoScalpTradePlan({ result }: { result: CryptoScalpResult }) {
  const [toWatchlist, setToWatchlist] = useState(false);
  const [toPaper, setToPaper] = useState(false);

  const gradeColor = result.scalp_grade === "SCALP_A+" ? "#4ade80"
    : result.scalp_grade === "SCALP_A" ? "#bef264"
    : result.scalp_grade === "SCALP_B" ? "#fbbf24"
    : "#6b7280";

  const confidenceLabel = result.scalp_grade === "SCALP_A+" ? "High Confidence"
    : result.scalp_grade === "SCALP_A" ? "Good Confidence"
    : result.scalp_grade === "SCALP_B" ? "Medium Confidence (Test Setup)"
    : "Not Suitable";

  const tierColor = result.tier === 1 ? "#4ade80" : result.tier === 2 ? "#fde047" : "#6b7280";
  const sideColor = result.side === "LONG" ? "#4ade80" : result.side === "SHORT" ? "#ef4444" : "#6b7280";

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Header */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "2px solid #1e1e2a" }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-3xl font-black text-white mb-2">{result.symbol}</h2>
            <p className="text-xs text-gray-500">Crypto Scalp Analysis (Phase 1 — Paper Only) — {confidenceLabel}</p>
          </div>
          <div className="flex gap-2">
            <div className="px-3 py-2 rounded-lg text-center" style={{ background: `${tierColor}22`, border: `1px solid ${tierColor}` }}>
              <p className="text-[10px] font-bold text-gray-600">Tier</p>
              <p className="text-lg font-black" style={{ color: tierColor }}>{result.tier}</p>
            </div>
            <div className="px-3 py-2 rounded-lg text-center" style={{ background: `${gradeColor}22`, border: `1px solid ${gradeColor}` }}>
              <p className="text-[10px] font-bold text-gray-600">Grade</p>
              <p className="text-base font-black" style={{ color: gradeColor }}>{result.scalp_grade}</p>
            </div>
            <div className="px-3 py-2 rounded-lg text-center" style={{ background: `${sideColor}22`, border: `1px solid ${sideColor}` }}>
              <p className="text-[10px] font-bold text-gray-600">Side</p>
              <p className="text-base font-black" style={{ color: sideColor }}>{result.side}</p>
            </div>
          </div>
        </div>

        {/* PHASE 1 WARNING */}
        <div className="rounded-lg p-3 mb-4" style={{ background: "#1f2937", border: "1px solid #4b5563" }}>
          <p className="text-xs font-bold text-blue-300">⚡ PHASE 1: PAPER ONLY</p>
          <p className="text-[11px] text-blue-200 mt-1">Real trading is disabled in Phase 1. You can add this to Paper Journal or Watchlist only.</p>
        </div>

        {/* Scores */}
        <div className="grid grid-cols-4 gap-3">
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] font-bold text-gray-600">Scalp Score</p>
            <p className="text-2xl font-black text-cyan-400">{result.scalp_score}/100</p>
          </div>
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] font-bold text-gray-600">LONG Score</p>
            <p className="text-2xl font-black text-green-400">{result.long_score}</p>
          </div>
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] font-bold text-gray-600">SHORT Score</p>
            <p className="text-2xl font-black text-red-400">{result.short_score}</p>
          </div>
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] font-bold text-gray-600">Timeframe</p>
            <p className="text-xl font-black text-white">{result.timeframe}</p>
          </div>
        </div>
      </div>

      {/* Signal Setup (if LONG/SHORT) */}
      {result.side !== "NONE" && (
        <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <h3 className="text-lg font-black text-white mb-4">📊 {result.side} Setup</h3>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Entry Price</p>
              <p className="text-xl font-black" style={{ color: sideColor }}>{result.entry?.toFixed(4)}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Stop Loss</p>
              <p className="text-xl font-black text-red-400">{result.stop_loss?.toFixed(4)}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Target 1</p>
              <p className="text-lg font-black text-green-400">{result.tp1?.toFixed(4)}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Target 2</p>
              <p className="text-lg font-black text-green-400">{result.tp2?.toFixed(4)}</p>
            </div>
          </div>

          {result.rr_ratio && (
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Risk/Reward Ratio</p>
              <p className="text-lg font-black text-cyan-400">1:{result.rr_ratio}</p>
            </div>
          )}
        </div>
      )}

      {/* Status & Data */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
        <h3 className="text-lg font-black text-white mb-4">🔍 Analysis Status</h3>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] text-gray-600">Data Status</p>
            <p className="text-sm font-bold" style={{ color: result.data_status === "FRESH" ? "#4ade80" : "#ef4444" }}>
              {result.data_status}
            </p>
          </div>
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] text-gray-600">Spread Status</p>
            <p className="text-sm font-bold text-gray-400">{result.spread_status}</p>
          </div>
          <div className="rounded-lg p-3 bg-gray-900">
            <p className="text-[10px] text-gray-600">Volatility</p>
            <p className="text-sm font-bold text-gray-400">{result.volatility_status}</p>
          </div>
        </div>

        <div className="rounded-lg p-3 bg-gray-900">
          <p className="text-[10px] text-gray-600 mb-2">Authorization for Real Trading</p>
          <p className="text-sm font-bold text-red-400">
            ✗ DISABLED IN PHASE 1 — Real trading is not available
          </p>
          <p className="text-[10px] text-gray-500 mt-1">scalp_execution_authorized = false</p>
        </div>
      </div>

      {/* Signals & Reasons */}
      {(result.signal_reasons.length > 0 || result.blocked_reasons.length > 0) && (
        <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          {result.signal_reasons.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-bold text-green-400 mb-2">✓ Signal Reasons</h4>
              <ul className="space-y-1">
                {result.signal_reasons.map((s, i) => (
                  <li key={i} className="text-[11px] text-gray-400 flex gap-2">
                    <span>•</span> {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.blocked_reasons.length > 0 && (
            <div>
              <h4 className="text-sm font-bold text-orange-400 mb-2">⚠ Blocked Reasons</h4>
              <ul className="space-y-1">
                {result.blocked_reasons.map((b, i) => (
                  <li key={i} className="text-[11px] text-gray-500 flex gap-2">
                    <span>•</span> {b}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="rounded-xl p-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
        <div className="flex gap-3 flex-wrap">
          {result.watchlist_allowed && !toWatchlist && (
            <button
              onClick={() => setToWatchlist(true)}
              className="px-4 py-2 rounded-lg text-sm font-bold bg-blue-900 border border-blue-600 text-blue-300 hover:bg-blue-800 transition"
            >
              📌 Add to Watchlist
            </button>
          )}

          {toWatchlist && (
            <div className="px-4 py-2 rounded-lg text-sm font-bold bg-blue-900 border border-blue-600 text-blue-300">
              ✓ Added to Watchlist
            </div>
          )}

          {result.paper_allowed && !toPaper && (
            <button
              onClick={() => setToPaper(true)}
              className="px-4 py-2 rounded-lg text-sm font-bold bg-green-900 border border-green-600 text-green-300 hover:bg-green-800 transition"
            >
              📝 Add to Paper Journal
            </button>
          )}

          {toPaper && (
            <div className="px-4 py-2 rounded-lg text-sm font-bold bg-green-900 border border-green-600 text-green-300">
              ✓ Added to Paper Journal
            </div>
          )}

          {!result.paper_allowed && !result.watchlist_allowed && (
            <div className="px-4 py-2 rounded-lg text-sm font-bold bg-gray-900 border border-gray-700 text-gray-400">
              No actions available (Grade {result.scalp_grade})
            </div>
          )}
        </div>

        <p className="text-[10px] text-gray-600 mt-3">
          {result.scalp_grade === "SCALP_B"
            ? "💡 SCALP_B: Paper test setup — add to Paper Journal to validate medium-confidence setups. Real trading disabled."
            : result.paper_allowed
            ? "💡 Paper Journal tracks paper trades for performance validation. Real trading is disabled in Phase 1."
            : "💡 Grade too low for Paper trading. Add to Watchlist to monitor."}
        </p>
      </div>
    </div>
  );
}
