"use client";

import { useState, useCallback } from "react";

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
  // Cost fields (Phase 2)
  spread_bps?: number;
  entry_fee_pct?: number;
  exit_fee_pct?: number;
  slippage_pct?: number;
  estimated_roundtrip_cost_pct?: number;
  estimated_net_rr?: number;
  // Phase 3A: Signal Quality Enhancement
  long_strength?: number;
  short_strength?: number;
  preferred_side?: "LONG" | "SHORT" | "NONE";
  signal_strength?: "STRONG" | "NORMAL" | "WEAK" | "REJECT";
  confidence_score?: number;
  signal_warnings?: string[];
  // Phase 3C: Data Quality Fields
  data_quality_blocked?: boolean;
  data_quality_status?: string;
  entry_price?: number | null;
  take_profit?: number | null;
}

// Phase 3C: Trade Refusal Explanation Types & Functions
interface RefusalExplanation {
  badgeStatus: "Tradable Paper" | "Watchlist Only" | "Blocked";
  mainCause: string;
  secondaryCauses: string[];
  technicalDetails: {
    dataQualityDivergence?: number;
    dataQualityThreshold?: number;
    confidenceActual?: number;
    confidenceRequired?: number;
    rrRatio?: number;
    spreadBps?: number;
    estimatedCostPct?: number;
    scalp_grade?: string;
  };
}

// Helper function to extract divergence percentage from data_quality_status string
function extractDivergence(status?: string): number | null {
  if (!status) return null;
  const match = status.match(/(\d+\.?\d*)\s*%/);
  return match ? parseFloat(match[1]) : null;
}

// Analyze result and generate user-friendly explanation for why trade is blocked
function generateRefusalExplanation(
  result: CryptoScalpResult
): RefusalExplanation | null {
  // Returns null if paper_allowed = true (no explanation needed)
  if (result.paper_allowed) return null;

  let badgeStatus: "Tradable Paper" | "Watchlist Only" | "Blocked" = "Blocked";
  let mainCause = "";
  const secondaryCauses: string[] = [];
  const technicalDetails: RefusalExplanation["technicalDetails"] = {};

  // CASE 1: Data Quality BLOCKED
  if (
    result.data_quality_blocked === true ||
    result.data_quality_status?.includes("BLOCKED")
  ) {
    badgeStatus = "Blocked";
    const divergence = extractDivergence(result.data_quality_status);
    mainCause =
      "Les sources de prix ne sont pas cohérentes. L'écart dépasse 10%, donc le signal est bloqué par sécurité.";
    if (divergence) {
      technicalDetails.dataQualityDivergence = divergence;
      technicalDetails.dataQualityThreshold = 10;
    }
  }
  // CASE 2: Side = NONE (no clear direction)
  else if (result.side === "NONE") {
    badgeStatus = "Watchlist Only";
    mainCause =
      "Aucune direction LONG ou SHORT assez claire pour autoriser un Paper trade.";
    secondaryCauses.push("Ajoutez ce symbole à Watchlist pour surveillance future.");
  }
  // CASE 3: Low confidence
  else if (result.confidence_score && result.confidence_score < 40) {
    badgeStatus = "Watchlist Only";
    mainCause = `La confiance est trop faible pour autoriser un Paper trade. (Confidence ${result.confidence_score}%, seuil requis 40%)`;
    technicalDetails.confidenceActual = result.confidence_score;
    technicalDetails.confidenceRequired = 40;
    secondaryCauses.push("Attendez une meilleure confirmation avant de trader.");
  }
  // CASE 4: SCALP_REJECT
  else if (result.scalp_grade === "SCALP_REJECT") {
    badgeStatus = "Watchlist Only";
    mainCause =
      "Le score technique est trop faible pour autoriser un Paper trade.";
    technicalDetails.scalp_grade = result.scalp_grade;
    secondaryCauses.push("Vérifiez les paramètres techniques du signal.");
  }
  // CASE 5: Weak R/R (< 1.0 is BLOCKED, >= 1.0 shown in warning)
  else if (result.rr_ratio && result.rr_ratio < 1.0) {
    badgeStatus = "Blocked";
    mainCause = `Le ratio risque/rendement est trop faible (${result.rr_ratio.toFixed(2)}:1). Le gain potentiel ne compense pas assez le risque.`;
    technicalDetails.rrRatio = result.rr_ratio;
  }
  // CASE 6: High spread/costs
  else if (
    result.estimated_roundtrip_cost_pct &&
    result.estimated_roundtrip_cost_pct > 0.5
  ) {
    badgeStatus = "Watchlist Only";
    mainCause = `Les coûts ou le spread peuvent réduire fortement la rentabilité. (Coût estimé: ${result.estimated_roundtrip_cost_pct.toFixed(2)}%)`;
    technicalDetails.estimatedCostPct = result.estimated_roundtrip_cost_pct;
  }
  // CASE 7: Invalid entry/SL/TP
  else if (
    result.entry === null ||
    result.stop_loss === null ||
    (result.tp1 === null && result.tp2 === null)
  ) {
    badgeStatus = "Blocked";
    mainCause =
      "Le plan de trade n'est pas complet ou pas valide. Entry, SL, ou TP manquant.";
  }
  // FALLBACK: Generic blocker
  else {
    badgeStatus = result.watchlist_allowed ? "Watchlist Only" : "Blocked";
    mainCause =
      "Ce trade ne peut pas être exécuté en Paper trading pour des raisons de sécurité.";
    if (result.blocked_reasons && result.blocked_reasons.length > 0) {
      secondaryCauses.push(...result.blocked_reasons.slice(0, 2));
    }
  }

  return {
    badgeStatus,
    mainCause,
    secondaryCauses,
    technicalDetails,
  };
}

export function CryptoScalpTradePlan({ result }: { result: CryptoScalpResult }) {
  const [toWatchlist, setToWatchlist] = useState(false);
  const [toPaper, setToPaper] = useState(false);
  const [isLoadingPaper, setIsLoadingPaper] = useState(false);
  const [paperError, setPaperError] = useState<string | null>(null);

  // Phase 3B.1: Backtest Preview
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  const handleAddToPaperJournal = useCallback(async () => {
    setIsLoadingPaper(true);
    setPaperError(null);
    try {
      const response = await fetch('/api/crypto/scalp/journal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: result.symbol.toUpperCase(),
          scalp_result: result,
          status: 'SCALP_PAPER_PLANNED'
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const data = await response.json();
      if (data.ok) {
        setToPaper(true);
      } else {
        throw new Error(data.error || 'Failed to create trade');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error('Paper Journal error:', error);
      setPaperError(message);
    } finally {
      setIsLoadingPaper(false);
    }
  }, [result]);

  // Phase 3B.1: Handle Backtest Preview
  const handleRunBacktest = useCallback(async () => {
    setBacktestLoading(true);
    setBacktestError(null);
    setBacktestResult(null);
    try {
      const response = await fetch(`/api/crypto/scalp/backtest-lite?symbol=${result.symbol.toUpperCase()}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      setBacktestResult(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error('Backtest error:', error);
      setBacktestError(message);
    } finally {
      setBacktestLoading(false);
    }
  }, [result.symbol]);

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

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-gray-600 mb-1">Gross R/R Ratio</p>
              <p className="text-lg font-black text-cyan-400">1:{result.rr_ratio?.toFixed(2) ?? "—"}</p>
            </div>
            {result.estimated_net_rr && (
              <div>
                <p className="text-[10px] text-gray-600 mb-1">Net R/R (after costs)</p>
                <p className="text-lg font-black text-green-400">1:{result.estimated_net_rr.toFixed(2)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Cost Estimate Section */}
      {result.side !== "NONE" && result.estimated_roundtrip_cost_pct !== undefined && (
        <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <h3 className="text-lg font-black text-white mb-4">💰 Cost Estimate (Paper Trading)</h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="rounded-lg p-3 bg-gray-900">
              <p className="text-[10px] font-bold text-gray-600 mb-1">Spread</p>
              <p className="text-lg font-black text-cyan-400">{(result.spread_bps ?? 0).toFixed(0)} BPS</p>
            </div>
            <div className="rounded-lg p-3 bg-gray-900">
              <p className="text-[10px] font-bold text-gray-600 mb-1">Entry Fee</p>
              <p className="text-lg font-black text-orange-400">{(result.entry_fee_pct ?? 0).toFixed(3)}%</p>
            </div>
            <div className="rounded-lg p-3 bg-gray-900">
              <p className="text-[10px] font-bold text-gray-600 mb-1">Exit Fee</p>
              <p className="text-lg font-black text-orange-400">{(result.exit_fee_pct ?? 0).toFixed(3)}%</p>
            </div>
            <div className="rounded-lg p-3 bg-gray-900">
              <p className="text-[10px] font-bold text-gray-600 mb-1">Slippage</p>
              <p className="text-lg font-black text-red-400">{(result.slippage_pct ?? 0).toFixed(3)}%</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
              <p className="text-xs text-gray-600 mb-2">Roundtrip Cost Total</p>
              <p className="text-2xl font-black text-amber-400">{(result.estimated_roundtrip_cost_pct ?? 0).toFixed(3)}%</p>
              <p className="text-[10px] text-gray-500 mt-2">Combined spread + fees + slippage</p>
            </div>
            {result.estimated_roundtrip_cost_pct && result.estimated_roundtrip_cost_pct > 0.02 && (
              <div className="rounded-lg p-4" style={{ background: "#2a1a0a", border: "1px solid #f59e0b44" }}>
                <p className="text-xs text-amber-600 font-bold mb-2">⚠️ Cost Warning</p>
                <p className="text-[11px] text-amber-400">
                  {result.estimated_roundtrip_cost_pct > 0.03
                    ? "High cost (>0.3%) may reduce profitability for small targets (<1% R)"
                    : "Moderate cost - ensure target move is >1% to maintain edge"}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PHASE 3A: Signal Quality Enhancement */}
      {(result.long_strength !== undefined || result.short_strength !== undefined) && (
        <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <h3 className="text-lg font-black text-white mb-4">⚡ Signal Quality (Phase 3A)</h3>

          {/* LONG/SHORT Strengths */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="rounded-lg p-4" style={{ background: "#1a1a2e", borderLeft: "4px solid #4ade80" }}>
              <p className="text-xs text-gray-600 mb-2 font-bold">LONG Strength</p>
              <p className="text-3xl font-black text-green-400 mb-1">{result.long_strength ?? 0}</p>
              <p className="text-[10px] text-gray-500">/100</p>
            </div>
            <div className="rounded-lg p-4" style={{ background: "#1a1a2e", borderLeft: "4px solid #ef4444" }}>
              <p className="text-xs text-gray-600 mb-2 font-bold">SHORT Strength</p>
              <p className="text-3xl font-black text-red-400 mb-1">{result.short_strength ?? 0}</p>
              <p className="text-[10px] text-gray-500">/100</p>
            </div>
          </div>

          {/* Signal Strength Badge */}
          {result.signal_strength && (
            <div className="mb-6">
              <p className="text-xs text-gray-600 mb-2 font-bold">Signal Strength Classification</p>
              <div className="inline-block rounded-lg px-4 py-2 font-black text-sm" style={{
                background: result.signal_strength === "STRONG" ? "#10b98122" :
                            result.signal_strength === "NORMAL" ? "#f59e0b22" :
                            result.signal_strength === "WEAK" ? "#ef444422" : "#6b728022",
                color: result.signal_strength === "STRONG" ? "#10b981" :
                       result.signal_strength === "NORMAL" ? "#f59e0b" :
                       result.signal_strength === "WEAK" ? "#ef4444" : "#6b7280",
                border: `1px solid ${result.signal_strength === "STRONG" ? "#10b981" :
                                   result.signal_strength === "NORMAL" ? "#f59e0b" :
                                   result.signal_strength === "WEAK" ? "#ef4444" : "#6b7280"}`
              }}>
                {result.signal_strength}
              </div>
            </div>
          )}

          {/* Confidence Score */}
          {result.confidence_score !== undefined && (
            <div className="mb-6">
              <p className="text-xs text-gray-600 mb-2 font-bold">Overall Confidence</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-900 rounded-full h-3 overflow-hidden">
                  <div
                    className="h-3 bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all"
                    style={{ width: `${result.confidence_score}%` }}
                  />
                </div>
                <p className="text-lg font-black text-blue-400" style={{ minWidth: "50px" }}>
                  {result.confidence_score}%
                </p>
              </div>
            </div>
          )}

          {/* Preferred Side */}
          {result.preferred_side && result.preferred_side !== "NONE" && (
            <div className="mb-6">
              <p className="text-xs text-gray-600 mb-2 font-bold">Preferred Side</p>
              <div style={{
                display: "inline-block",
                padding: "0.5rem 1rem",
                borderRadius: "0.5rem",
                fontWeight: "900",
                fontSize: "0.875rem",
                color: result.preferred_side === "LONG" ? "#4ade80" : "#ef4444",
                background: result.preferred_side === "LONG" ? "#4ade8022" : "#ef444422",
                border: `1px solid ${result.preferred_side === "LONG" ? "#4ade80" : "#ef4444"}`
              }}>
                {result.preferred_side}
              </div>
            </div>
          )}

          {/* Reasons (from enhancement) */}
          {result.signal_reasons && result.signal_reasons.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-gray-600 mb-2 font-bold">Why This Signal</p>
              <ul className="space-y-2">
                {result.signal_reasons.map((reason, i) => (
                  <li key={i} className="text-[11px] text-green-300 flex gap-2">
                    <span className="text-green-400 font-black">✓</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings (from enhancement) */}
          {result.signal_warnings && result.signal_warnings.length > 0 && (
            <div>
              <p className="text-xs text-gray-600 mb-2 font-bold">Cautions</p>
              <ul className="space-y-2">
                {result.signal_warnings.map((warning, i) => (
                  <li key={i} className="text-[11px] text-yellow-300 flex gap-2">
                    <span className="text-yellow-500 font-black">⚠</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
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

      {/* Phase 3C: Trade Refusal Explanation Block */}
      {!result.paper_allowed && (
        <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          {/* Title */}
          <h3 className="text-lg font-black text-white mb-4 flex items-center gap-2">
            <span>❌</span>
            <span>Pourquoi ce trade n&apos;est pas tradable ?</span>
          </h3>

          {/* Status Badge */}
          <div className="mb-4">
            <span
              className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
                (() => {
                  const explanation = generateRefusalExplanation(result);
                  if (explanation?.badgeStatus === "Tradable Paper")
                    return "bg-green-500/20 text-green-400";
                  if (explanation?.badgeStatus === "Watchlist Only")
                    return "bg-amber-500/20 text-amber-400";
                  return "bg-red-500/20 text-red-400";
                })()
              }`}
            >
              {generateRefusalExplanation(result)?.badgeStatus || "Blocked"}
            </span>
          </div>

          {/* Main Cause */}
          <div className="mb-4">
            <p className="text-sm text-white font-semibold">
              {generateRefusalExplanation(result)?.mainCause}
            </p>
          </div>

          {/* Secondary Causes */}
          {generateRefusalExplanation(result)?.secondaryCauses &&
            generateRefusalExplanation(result)!.secondaryCauses.length > 0 && (
              <div className="mb-4">
                <ul className="text-sm text-gray-400 list-disc list-inside space-y-1">
                  {generateRefusalExplanation(result)?.secondaryCauses.map(
                    (cause, idx) => (
                      <li key={idx}>{cause}</li>
                    )
                  )}
                </ul>
              </div>
            )}

          {/* Technical Details */}
          {(() => {
            const explanation = generateRefusalExplanation(result);
            if (!explanation?.technicalDetails || Object.keys(explanation.technicalDetails).length === 0) {
              return null;
            }
            return (
              <div className="text-xs text-gray-600 border-t border-gray-700 pt-3 space-y-1">
                {explanation.technicalDetails.dataQualityDivergence !== undefined && (
                  <p>
                    Divergence données: {explanation.technicalDetails.dataQualityDivergence.toFixed(1)}% (seuil: {explanation.technicalDetails.dataQualityThreshold}%)
                  </p>
                )}
                {explanation.technicalDetails.confidenceActual !== undefined && (
                  <p>
                    Confiance: {explanation.technicalDetails.confidenceActual}% (requis: {explanation.technicalDetails.confidenceRequired}%)
                  </p>
                )}
                {explanation.technicalDetails.rrRatio !== undefined && (
                  <p>Ratio R/R: 1:{explanation.technicalDetails.rrRatio.toFixed(2)}</p>
                )}
                {explanation.technicalDetails.estimatedCostPct !== undefined && (
                  <p>Coût aller-retour estimé: {explanation.technicalDetails.estimatedCostPct.toFixed(2)}%</p>
                )}
                {explanation.technicalDetails.scalp_grade && (
                  <p>Note technique: {explanation.technicalDetails.scalp_grade}</p>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* Actions */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
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
              onClick={handleAddToPaperJournal}
              disabled={isLoadingPaper}
              className="px-4 py-2 rounded-lg text-sm font-bold bg-green-900 border border-green-600 text-green-300 hover:bg-green-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoadingPaper ? "⏳ Adding..." : "📝 Add to Paper Journal (costs tracked)"}
            </button>
          )}

          {toPaper && (
            <div className="px-4 py-2 rounded-lg text-sm font-bold bg-green-900 border border-green-600 text-green-300">
              ✓ Added to Paper Journal
            </div>
          )}

          {paperError && (
            <div className="px-4 py-2 rounded-lg text-sm font-bold bg-red-900 border border-red-600 text-red-300">
              ❌ Error: {paperError}
            </div>
          )}

          {/* Low R/R Warning */}
          {result.rr_ratio && 1.0 <= result.rr_ratio && result.rr_ratio < 1.2 && (
            <div className="px-4 py-2 rounded-lg text-sm mt-3 bg-yellow-900 border border-yellow-600 text-yellow-300">
              ⚠️ Faible ratio risque/rendement ({result.rr_ratio.toFixed(2)}:1) — nécessite un excellent taux de réussite.
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

      {/* Phase 3B.1: Backtest Preview Section */}
      <div className="rounded-xl p-6" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-black text-white">🔬 Backtest Preview (7 days)</h3>
          <button
            onClick={handleRunBacktest}
            disabled={backtestLoading}
            className="px-4 py-2 rounded-lg text-sm font-bold bg-purple-900 border border-purple-600 text-purple-300 hover:bg-purple-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {backtestLoading ? "⏳ Running..." : "▶ Run 7d Preview"}
          </button>
        </div>

        {/* Backtest Error */}
        {backtestError && (
          <div className="rounded-lg p-4 mb-4" style={{ background: "#1f1f2e", border: "1px solid #ef4444" }}>
            <p className="text-sm text-red-400 font-bold">❌ Backtest Error</p>
            <p className="text-[11px] text-red-300 mt-2">{backtestError}</p>
          </div>
        )}

        {/* Backtest Results */}
        {backtestResult && !backtestError && (
          <div>
            {/* Badge */}
            <div className="mb-4">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/50">
                📊 Simulation Only — Historical Data
              </span>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Signals Detected</p>
                <p className="text-2xl font-black text-cyan-400">{backtestResult.signals_detected || 0}</p>
              </div>
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Win Count</p>
                <p className="text-2xl font-black text-green-400">{backtestResult.win_count || 0}</p>
              </div>
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Loss Count</p>
                <p className="text-2xl font-black text-red-400">{backtestResult.loss_count || 0}</p>
              </div>
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Expired</p>
                <p className="text-2xl font-black text-yellow-400">{backtestResult.expired_count || 0}</p>
              </div>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Win Rate</p>
                <p className="text-xl font-black text-green-400">{(backtestResult.win_rate || 0).toFixed(1)}%</p>
              </div>
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Loss Rate</p>
                <p className="text-xl font-black text-red-400">{(backtestResult.loss_rate || 0).toFixed(1)}%</p>
              </div>
              <div className="rounded-lg p-3 bg-gray-900">
                <p className="text-[10px] font-bold text-gray-600 mb-1">Avg R</p>
                <p className="text-xl font-black text-blue-400">{(backtestResult.avg_r || 0).toFixed(2)}</p>
              </div>
            </div>

            {/* Data Points */}
            <div className="rounded-lg p-3 bg-gray-900 mb-4">
              <p className="text-[10px] font-bold text-gray-600 mb-1">Historical Data</p>
              <p className="text-sm text-gray-400">
                {backtestResult.period_days || 7} days — {backtestResult.timeframe || "5m"} candles —
                {backtestResult.data_points || "N/A"} data points
              </p>
            </div>

            {/* Disclaimer */}
            <div className="rounded-lg p-4" style={{ background: "#1a1a2e", border: "1px solid #fbbf2444" }}>
              <p className="text-xs font-bold text-amber-300 mb-1">⚠️ Important Disclaimer</p>
              <p className="text-[11px] text-amber-200 leading-relaxed">
                {backtestResult.disclaimer || "Historical simulation only. This is not a prediction of future performance. Past results do not guarantee future results. Backtest results are for validation purposes only."}
              </p>
            </div>
          </div>
        )}

        {/* Initial State (no results yet) */}
        {!backtestResult && !backtestError && (
          <div className="rounded-lg p-4" style={{ background: "#1a1a2e", border: "1px solid #6b728044" }}>
            <p className="text-sm text-gray-400">
              Click "Run 7d Preview" to simulate this signal on 7 days of historical data.
              Simulation only — no real execution.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
