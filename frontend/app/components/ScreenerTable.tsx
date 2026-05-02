"use client";

import { useState, Fragment, useEffect } from "react";
import { TickerResult } from "../types";
import { getApiUrl } from "../lib/api";
import { formatCryptoPrice } from "../lib/cryptoFormat";

const API_URL = getApiUrl();
import { ScoreBar } from "./ScoreBar";
import { SetupGradeBadge, SignalBadge, ConfidenceBadge } from "./CategoryBadge";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { TradePlan } from "./TradePlan";
import { SentimentCell } from "./SentimentPanel";
import { EdgeStatusBadge, EdgeScoreBar, BestStrategyBadge, EdgeValidationNote } from "./EdgeBadge";
import { CryptoTradePlan } from "./crypto/CryptoTradePlan";

type SortKey = "score" | "rsi_val" | "perf_3m" | "perf_6m" | "dist_entry_pct" | "risk_now_pct" | "rr_ratio" | "confidence" | "edge_score" | "final_score" | "edge_train_pf" | "edge_test_pf";

function safeFixed(value?: number | null, digits = 1, suffix = "") {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(digits)}${suffix}`
    : "—";
}

function PctCell({ val, good = "positive" }: { val: number; good?: "positive" | "negative" | "neutral" }) {
  const color =
    good === "neutral"  ? "#9ca3af" :
    good === "positive" ? (val > 1 ? "#10b981" : val < -1 ? "#ef4444" : "#9ca3af") :
                          (val < 1 ? "#10b981" : val > 3 ? "#ef4444" : "#f59e0b");
  return (
    <span className="font-mono text-xs tabular-nums" style={{ color }}>
      {val > 0 ? "+" : ""}{val.toFixed(2)}%
    </span>
  );
}

type EdgeFilter = "all" | "STRONG_EDGE" | "VALID_EDGE" | "no_no_edge";

export function ScreenerTable({
  data,
  showEdge = false,
  scope = "actions",
}: {
  data: TickerResult[];
  showEdge?: boolean;
  scope?: "actions" | "crypto";
}) {
  const [expanded, setExpanded]   = useState<string | null>(null);
  const [tradePlan, setTradePlan] = useState<TickerResult | null>(null);
  const [sortKey, setSortKey]     = useState<SortKey>("score");
  const [sortAsc, setSortAsc]     = useState(false);
  const [apisConfigured, setApisConfigured] = useState<boolean>(true);
  const [edgeFilter, setEdgeFilter] = useState<EdgeFilter>("all");
  const [hideOverfit, setHideOverfit] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/status`)
      .then(r => r.json())
      .then(d => setApisConfigured(!!d?.all_configured))
      .catch(() => {});
  }, []);

  // Filtrage edge
  const filtered = data.filter(r => {
    if (edgeFilter === "STRONG_EDGE" && r.ticker_edge_status !== "STRONG_EDGE") return false;
    if (edgeFilter === "VALID_EDGE"  && !["STRONG_EDGE", "VALID_EDGE"].includes(r.ticker_edge_status ?? "")) return false;
    if (edgeFilter === "no_no_edge"  && (r.ticker_edge_status === "NO_EDGE" || !r.ticker_edge_status)) return false;
    if (hideOverfit && r.overfit_warning) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const av = (a[sortKey] as number) ?? 0;
    const bv = (b[sortKey] as number) ?? 0;
    const diff = av - bv;
    return sortAsc ? diff : -diff;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(false); }
  };

  const Th = ({ label, k }: { label: string; k?: SortKey }) => (
    <th
      className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer select-none hover:text-gray-300 transition-colors"
      onClick={k ? () => toggleSort(k) : undefined}
    >
      {label}{k && sortKey === k ? (sortAsc ? " ↑" : " ↓") : ""}
    </th>
  );

  const gradeRowBorder: Record<string, string> = {
    "A+": "#4ade80", "A": "#bef264", "B": "#fde047",
  };

  const EdgeFilterBtn = ({ label, val }: { label: string; val: EdgeFilter }) => (
    <button
      onClick={() => setEdgeFilter(edgeFilter === val ? "all" : val)}
      className="px-2.5 py-1 rounded text-[10px] font-bold transition-all"
      style={{
        background: edgeFilter === val ? "#052e16" : "#0d0d18",
        border: `1px solid ${edgeFilter === val ? "#4ade80" : "#1e1e2a"}`,
        color: edgeFilter === val ? "#4ade80" : "#4b5563",
      }}
    >
      {label}
    </button>
  );

  return (
    <>
      {tradePlan && (
        scope === "crypto"
          ? <CryptoTradePlan row={tradePlan} onClose={() => setTradePlan(null)} />
          : <TradePlan row={tradePlan} onClose={() => setTradePlan(null)} />
      )}

      {/* ── Filtres Edge ── */}
      {showEdge && (
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Edge :</span>
          <EdgeFilterBtn label="⚡ Strong Edge only" val="STRONG_EDGE" />
          <EdgeFilterBtn label="✓ Valid+ only"       val="VALID_EDGE" />
          <EdgeFilterBtn label="Masquer NO_EDGE"      val="no_no_edge" />
          <button
            onClick={() => setHideOverfit(v => !v)}
            className="px-2.5 py-1 rounded text-[10px] font-bold transition-all"
            style={{
              background: hideOverfit ? "#1c1000" : "#0d0d18",
              border: `1px solid ${hideOverfit ? "#f59e0b" : "#1e1e2a"}`,
              color: hideOverfit ? "#f59e0b" : "#4b5563",
            }}
          >
            ⚠ Masquer Overfit
          </button>
          <span className="text-[10px] text-gray-700 ml-2">{sorted.length} résultats</span>
        </div>
      )}

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
              <tr>
                <Th label="Ticker" />
                <Th label="Secteur" />
                <Th label="Prix" />
                <Th label="Score" k="score" />
                <Th label="Grade" />
                <Th label="Signal" />
                <Th label="Conf." k="confidence" />
                {showEdge && <Th label="Final" k="final_score" />}
                {showEdge && <Th label="Edge" k="edge_score" />}
                {showEdge && <Th label="Stratégie" />}
                {showEdge && <Th label="Train PF" k="edge_train_pf" />}
                {showEdge && <Th label="Test PF" k="edge_test_pf" />}
                {showEdge && <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Overfit</th>}
                <Th label="Entree" />
                <Th label="SL" />
                <Th label="TP1" />
                <Th label="TP2" />
                <Th label="R/R" k="rr_ratio" />
                <Th label="Risque" k="risk_now_pct" />
                <Th label="Dist." k="dist_entry_pct" />
                <Th label="RSI" k="rsi_val" />
                <Th label="3m" k="perf_3m" />
                      <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                        {scope === "crypto" ? "Validation" : "Sentiment"}
                      </th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, i) => {
                const isExpanded = expanded === row.ticker;
                const rowBg      = i % 2 === 0 ? "#0a0a12" : "#0d0d18";
                const leftColor  = gradeRowBorder[row.setup_grade] ?? "#1e1e2a";

                return (
                  <Fragment key={row.ticker}>
                    <tr
                      style={{
                        background:   isExpanded ? "#111128" : rowBg,
                        borderBottom: "1px solid #1a1a28",
                        borderLeft:   `3px solid ${isExpanded ? leftColor : "transparent"}`,
                      }}
                      className="hover:bg-white/[0.03] transition-colors"
                    >
                      <td className="px-3 py-2.5"><span className="font-black text-white text-sm">{row.ticker}</span></td>
                      <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">{row.sector}</td>
                      <td className="px-3 py-2.5 tabular-nums text-xs">
                        <span className="font-mono text-gray-200">${scope === "crypto" ? formatCryptoPrice(row.ticker, row.price) : row.price.toFixed(2)}</span>
                        {row.change_pct !== undefined && (
                          <span
                            className="ml-1.5 font-semibold"
                            style={{ color: row.change_pct > 0 ? "#10b981" : row.change_pct < 0 ? "#ef4444" : "#6b7280", fontSize: "10px" }}
                          >
                            {row.change_pct > 0 ? "+" : ""}{row.change_pct.toFixed(2)}%
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5"><ScoreBar score={row.score} /></td>
                      <td className="px-3 py-2.5"><SetupGradeBadge grade={row.setup_grade} /></td>
                      <td className="px-3 py-2.5"><SignalBadge signal={row.signal_type} /></td>
                      <td className="px-3 py-2.5"><ConfidenceBadge confidence={row.confidence} /></td>
                      {showEdge && (
                        <td className="px-3 py-2.5">
                          <span className="text-xs font-black tabular-nums"
                            style={{ color: (row.final_score ?? 0) >= 70 ? "#4ade80" : (row.final_score ?? 0) >= 45 ? "#fde047" : "#6b7280" }}>
                            {row.final_score ?? "—"}
                          </span>
                        </td>
                      )}
                      {showEdge && (
                        <td className="px-3 py-2.5"><EdgeScoreBar score={row.edge_score} /></td>
                      )}
                      {showEdge && (
                        <td className="px-3 py-2.5">
                          <div className="flex flex-col gap-0.5">
                            <EdgeStatusBadge status={row.ticker_edge_status} />
                            <EdgeValidationNote status={row.ticker_edge_status} setupGrade={row.setup_grade} />
                            <BestStrategyBadge
                              name={row.best_strategy_name}
                              color={row.best_strategy_color}
                              emoji={row.best_strategy_emoji}
                            />
                          </div>
                        </td>
                      )}
                      {showEdge && (
                        <td className="px-3 py-2.5 font-mono tabular-nums text-xs"
                          style={{ color: (row.edge_train_pf ?? 0) >= 1.5 ? "#4ade80" : (row.edge_train_pf ?? 0) >= 1.2 ? "#fde047" : "#6b7280" }}>
                          {row.edge_train_pf ? row.edge_train_pf.toFixed(2) : "—"}
                        </td>
                      )}
                      {showEdge && (
                        <td className="px-3 py-2.5 font-mono tabular-nums text-xs"
                          style={{ color: (row.edge_test_pf ?? 0) >= 1.2 ? "#4ade80" : (row.edge_test_pf ?? 0) >= 1.0 ? "#fde047" : "#ef4444" }}>
                          {row.edge_test_pf ? row.edge_test_pf.toFixed(2) : "—"}
                        </td>
                      )}
                      {showEdge && (
                        <td className="px-3 py-2.5">
                          {row.overfit_warning
                            ? <span className="text-[10px] text-amber-400 font-bold">⚠ OVERFIT</span>
                            : row.ticker_edge_status && row.ticker_edge_status !== "NO_EDGE"
                              ? <span className="text-[10px] text-green-600">✓</span>
                              : <span className="text-[10px] text-gray-700">—</span>
                          }
                        </td>
                      )}
                      <td className="px-3 py-2.5 font-mono text-gray-300 tabular-nums text-xs">${scope === "crypto" ? formatCryptoPrice(row.ticker, row.entry) : row.entry.toFixed(2)}</td>
                      <td className="px-3 py-2.5">
                        <div>
                          <span className="font-mono tabular-nums text-xs" style={{ color: "#ef4444" }}>${scope === "crypto" ? formatCryptoPrice(row.ticker, row.stop_loss) : row.stop_loss.toFixed(2)}</span>
                          <span className="text-[9px] text-gray-700 ml-1">{row.sl_type}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-xs" style={{ color: "#86efac" }}>${scope === "crypto" ? formatCryptoPrice(row.ticker, row.tp1) : row.tp1.toFixed(2)}</td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-xs" style={{ color: "#10b981" }}>${scope === "crypto" ? formatCryptoPrice(row.ticker, row.tp2) : row.tp2.toFixed(2)}</td>
                      <td className="px-3 py-2.5">
                        <span className="text-xs font-bold tabular-nums"
                          style={{ color: row.rr_ratio >= 2 ? "#4ade80" : row.rr_ratio >= 1.5 ? "#f59e0b" : "#f87171" }}>
                          1:{safeFixed(row.rr_ratio, 1)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5"><PctCell val={row.risk_now_pct} good="negative" /></td>
                      <td className="px-3 py-2.5"><PctCell val={row.dist_entry_pct} good="neutral" /></td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-xs" style={{
                        color: row.rsi_val > 70 ? "#ef4444" : row.rsi_val < 30 ? "#10b981" : row.rsi_val >= 50 && row.rsi_val <= 70 ? "#4ade80" : "#9ca3af"
                      }}>
                        {row.rsi_val.toFixed(1)}
                      </td>
                      <td className="px-3 py-2.5"><PctCell val={row.perf_3m} /></td>
                      <td className="px-3 py-2.5 text-center">
                        {scope === "crypto" ? (
                          <span className="text-[10px] font-bold" style={{ color: row.ticker_edge_status === "OVERFITTED" ? "#f59e0b" : row.ticker_edge_status === "NO_EDGE" ? "#9ca3af" : "#4ade80" }}>
                            {row.ticker_edge_status === "NO_EDGE"
                              ? "Edge non validé"
                              : row.ticker_edge_status === "OVERFITTED"
                                ? "Backtest suspect — éviter"
                                : row.ticker_edge_status === "WEAK_EDGE"
                                  ? "Edge faible"
                                  : row.ticker_edge_status ?? "—"}
                          </span>
                        ) : (
                          <SentimentCell ticker={row.ticker} apisConfigured={apisConfigured} />
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => setTradePlan(row)}
                            className="text-xs px-2 py-1 rounded font-medium transition-all hover:opacity-90"
                            style={{ background: "#1e1e3a", border: "1px solid #4f46e5", color: "#818cf8" }}
                            title="Trade Plan"
                          >📋</button>
                          <button
                            onClick={() => setExpanded(isExpanded ? null : row.ticker)}
                            className="text-gray-600 hover:text-gray-300 transition-colors text-xs px-2 py-1 rounded"
                            style={{ border: "1px solid #2a2a3a" }}
                          >
                            {isExpanded ? "▲" : "▼"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr style={{ background: "#0b0b1a", borderBottom: "1px solid #1a1a28" }}>
                        <td colSpan={showEdge ? 24 : 18}>
                          <ScoreBreakdown detail={row.score_detail} ticker={row.ticker} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
