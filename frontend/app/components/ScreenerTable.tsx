"use client";

import { useState, Fragment, useEffect } from "react";
import { TickerResult } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { ScoreBar } from "./ScoreBar";
import { SetupGradeBadge, SignalBadge, ConfidenceBadge } from "./CategoryBadge";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { TradePlan } from "./TradePlan";
import { SentimentCell } from "./SentimentPanel";

type SortKey = "score" | "rsi_val" | "perf_3m" | "perf_6m" | "dist_entry_pct" | "risk_now_pct" | "rr_ratio" | "confidence";

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

export function ScreenerTable({ data }: { data: TickerResult[] }) {
  const [expanded, setExpanded]   = useState<string | null>(null);
  const [tradePlan, setTradePlan] = useState<TickerResult | null>(null);
  const [sortKey, setSortKey]     = useState<SortKey>("score");
  const [sortAsc, setSortAsc]     = useState(false);
  const [apisConfigured, setApisConfigured] = useState<boolean>(true);

  useEffect(() => {
    fetch(`${API_URL}/api/status`)
      .then(r => r.json())
      .then(d => setApisConfigured(!!d?.all_configured))
      .catch(() => {});
  }, []);

  const sorted = [...data].sort((a, b) => {
    const diff = (a[sortKey] as number) - (b[sortKey] as number);
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

  return (
    <>
      {tradePlan && <TradePlan row={tradePlan} onClose={() => setTradePlan(null)} />}
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
                <Th label="Entree" />
                <Th label="SL" />
                <Th label="TP1" />
                <Th label="TP2" />
                <Th label="R/R" k="rr_ratio" />
                <Th label="Risque" k="risk_now_pct" />
                <Th label="Dist." k="dist_entry_pct" />
                <Th label="RSI" k="rsi_val" />
                <Th label="3m" k="perf_3m" />
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Sentiment</th>
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
                      <td className="px-3 py-2.5 font-mono text-gray-200 tabular-nums text-xs">${row.price.toFixed(2)}</td>
                      <td className="px-3 py-2.5"><ScoreBar score={row.score} /></td>
                      <td className="px-3 py-2.5"><SetupGradeBadge grade={row.setup_grade} /></td>
                      <td className="px-3 py-2.5"><SignalBadge signal={row.signal_type} /></td>
                      <td className="px-3 py-2.5"><ConfidenceBadge confidence={row.confidence} /></td>
                      <td className="px-3 py-2.5 font-mono text-gray-300 tabular-nums text-xs">${row.entry.toFixed(2)}</td>
                      <td className="px-3 py-2.5">
                        <div>
                          <span className="font-mono tabular-nums text-xs" style={{ color: "#ef4444" }}>${row.stop_loss.toFixed(2)}</span>
                          <span className="text-[9px] text-gray-700 ml-1">{row.sl_type}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-xs" style={{ color: "#86efac" }}>${row.tp1.toFixed(2)}</td>
                      <td className="px-3 py-2.5 font-mono tabular-nums text-xs" style={{ color: "#10b981" }}>${row.tp2.toFixed(2)}</td>
                      <td className="px-3 py-2.5">
                        <span className="text-xs font-bold tabular-nums"
                          style={{ color: row.rr_ratio >= 2 ? "#4ade80" : row.rr_ratio >= 1.5 ? "#f59e0b" : "#f87171" }}>
                          1:{row.rr_ratio.toFixed(1)}
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
                        <SentimentCell ticker={row.ticker} apisConfigured={apisConfigured} />
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
                        <td colSpan={18}>
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