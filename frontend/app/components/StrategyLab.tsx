"use client";

import { useState, useCallback } from "react";
import { LabStrategyResult, LabSummary, OptimizedParamSet, OptimizerResult } from "../types";
import { Strategy } from "./Dashboard";
import { EngineBanner } from "./BacktestView";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Helpers ───────────────────────────────────────────────────────────────────

function pctColor(v: number, invert = false) {
  if (Math.abs(v) < 0.1) return "#6b7280";
  const good = invert ? v < 0 : v > 0;
  return good ? "#4ade80" : "#f87171";
}

function fmt(v: number, suffix = "%", decimals = 1) {
  return `${v > 0 ? "+" : ""}${v.toFixed(decimals)}${suffix}`;
}

// ── Score Gauge (arc SVG) ─────────────────────────────────────────────────────

function ScoreGauge({ score, color }: { score: number; color: string }) {
  const r     = 28;
  const cx    = 36;
  const cy    = 36;
  const circ  = 2 * Math.PI * r;
  const pct   = score / 100;
  const dash  = pct * circ * 0.75; // 3/4 arc
  const gap   = circ - dash;
  const rot   = -225; // start bottom-left

  const scoreColor =
    score >= 70 ? "#4ade80" :
    score >= 50 ? "#f59e0b" :
                  "#f87171";

  return (
    <div className="relative flex items-center justify-center" style={{ width: 72, height: 72 }}>
      <svg width="72" height="72" viewBox="0 0 72 72">
        {/* Track */}
        <circle cx={cx} cy={cy} r={r}
          fill="none" stroke="#1e1e2a" strokeWidth="7"
          strokeDasharray={`${circ * 0.75} ${circ}`}
          strokeDashoffset="0"
          style={{ transform: `rotate(${rot}deg)`, transformOrigin: `${cx}px ${cy}px` }}
          strokeLinecap="round"
        />
        {/* Progress */}
        <circle cx={cx} cy={cy} r={r}
          fill="none" stroke={scoreColor} strokeWidth="7"
          strokeDasharray={`${dash} ${gap + circ * 0.25}`}
          strokeDashoffset="0"
          style={{ transform: `rotate(${rot}deg)`, transformOrigin: `${cx}px ${cy}px`, transition: "stroke-dasharray 0.6s ease" }}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute text-center">
        <p className="text-sm font-black leading-none" style={{ color: scoreColor }}>{score}</p>
        <p className="text-[9px] text-gray-600 leading-none">/100</p>
      </div>
    </div>
  );
}

// ── Mini Equity Curve ─────────────────────────────────────────────────────────

function EquityCurve({ data, color, height = 50 }: { data: number[]; color: string; height?: number }) {
  if (!data || data.length < 2) return <div style={{ height }} className="flex items-center justify-center text-xs text-gray-700">Aucune donnée</div>;

  const w   = 300;
  const h   = height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const rng = max - min || 1;

  const path = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / rng) * (h - 4) - 2;
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");

  const lastVal = data[data.length - 1];
  const lineColor = lastVal >= 0 ? "#4ade80" : "#f87171";
  const zeroY = h - ((0 - min) / rng) * (h - 4) - 2;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={`lg-${color.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.35" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line x1="0" y1={zeroY} x2={w} y2={zeroY} stroke="#2a2a3a" strokeWidth="1" strokeDasharray="4 3" />
      <path d={`${path} L ${w} ${h} L 0 ${h} Z`} fill={`url(#lg-${color.slice(1)})`} />
      <path d={path} fill="none" stroke={lineColor} strokeWidth="1.5" />
    </svg>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────

function Badge({ label, bg, text }: { label: string; bg: string; text: string }) {
  return (
    <span className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider"
      style={{ background: bg, color: text, border: `1px solid ${text}44` }}>
      {label}
    </span>
  );
}

// ── Tradability Badge ─────────────────────────────────────────────────────────

function TradabilityBadge({ r }: { r: LabStrategyResult }) {
  if (!r.tradable_status) return null;
  const bgMap: Record<string, string> = {
    "TRADABLE":     "#052e16",
    "À CONFIRMER":  "#1a1000",
    "NON TRADABLE": "#1a0000",
  };
  return (
    <span
      className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider whitespace-nowrap"
      style={{
        background: bgMap[r.tradable_status] ?? "#0d0d18",
        color:      r.tradable_color,
        border:     `1px solid ${r.tradable_color}44`,
      }}
    >
      {r.tradable_emoji} {r.tradable_status}
    </span>
  );
}

// ── Capital Display ───────────────────────────────────────────────────────────

function CapitalDisplay({ r }: { r: LabStrategyResult }) {
  if (!r.final_capital) return null;
  const start = 10_000;
  const end   = r.final_capital;
  const color = end >= start ? "#4ade80" : "#f87171";

  const fmt = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M$`;
    if (v >= 1_000)     return `${(v / 1_000).toFixed(1)}k$`;
    return `${v.toFixed(0)}$`;
  };

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
      style={{ background: "#0d0d18", border: `1px solid ${color}22` }}>
      <span className="text-gray-500 font-mono">{fmt(start)}</span>
      <span className="text-gray-600">→</span>
      <span className="font-black font-mono" style={{ color }}>{fmt(end)}</span>
    </div>
  );
}

// ── Strategy Card ─────────────────────────────────────────────────────────────

function StrategyCard({
  r,
  badges,
  onUse,
  isActive,
  minTrades,
}: {
  r: LabStrategyResult;
  badges: string[];
  onUse: (r: LabStrategyResult) => void;
  isActive: boolean;
  minTrades: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const eligible = r.total_trades >= minTrades;

  const wrColor  = r.win_rate >= 60 ? "#4ade80" : r.win_rate >= 48 ? "#f59e0b" : "#f87171";
  const expColor = r.expectancy > 0 ? "#4ade80" : "#f87171";
  const retColor = r.total_return_pct > 0 ? "#4ade80" : "#f87171";

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all"
      style={{
        background: "#0a0a14",
        border: `1px solid ${isActive ? r.color : eligible ? "#1e1e2a" : "#2a1a00"}`,
        boxShadow: isActive ? `0 0 20px ${r.color}22` : undefined,
        opacity: r.total_trades === 0 ? 0.65 : 1,
      }}
    >
      {/* Header */}
      <div className="px-4 pt-4 pb-3" style={{ borderBottom: "1px solid #1a1a28" }}>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xl">{r.emoji}</span>
            <div>
              <p className="text-sm font-black text-white leading-tight">{r.name}</p>
              <p className="text-[11px] text-gray-500 mt-0.5">{r.description}</p>
            </div>
          </div>
          <ScoreGauge score={r.score} color={r.color} />
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-1 mt-1">
          {/* Tradability */}
          <TradabilityBadge r={r} />
          {/* Non-éligibilité toujours visible avec raison */}
          {!eligible && r.total_trades === 0 && (
            <Badge label="⚠️ Aucun signal détecté" bg="#1a0800" text="#f59e0b" />
          )}
          {!eligible && r.total_trades > 0 && r.total_trades < minTrades && (
            <Badge label={`⚠️ ${r.total_trades} trades < seuil ${minTrades}`} bg="#1a0800" text="#f59e0b" />
          )}
          {badges.includes("best_overall_provisional") && (
            <Badge label="🔎 Provisoire — non tradable" bg="#1a0800" text="#f59e0b" />
          )}
          {badges.includes("best_overall_confirmed") && (
            <Badge label="⚠️ Best — À confirmer" bg="#1a1000" text="#fbbf24" />
          )}
          {badges.includes("best_overall") && (
            <Badge label="🏆 Best Overall" bg="#052e16" text="#4ade80" />
          )}
          {badges.includes("best_win_rate") && (
            <Badge label="🎯 Best Win Rate" bg="#052e16" text="#4ade80" />
          )}
          {badges.includes("best_expectancy") && (
            <Badge label="⚡ Best Expectancy" bg="#0f1a3a" text="#818cf8" />
          )}
          {isActive && (
            <Badge label="✓ En cours d'utilisation" bg="#0f1a3a" text="#818cf8" />
          )}
        </div>

        {/* Raison non-éligible */}
        {!eligible && r.total_trades < minTrades && r.total_trades > 0 && (
          <p className="text-[10px] text-amber-700 mt-1.5 leading-relaxed">
            Les résultats sont disponibles mais le nombre de trades est insuffisant pour une fiabilité statistique.
            Baissez le seuil minimum ou attendez plus de données.
          </p>
        )}
        {r.total_trades === 0 && (
          <p className="text-[10px] text-gray-700 mt-1.5">
            Aucun signal généré sur la période — conditions trop strictes ou données insuffisantes.
          </p>
        )}
      </div>

      {/* Stats */}
      <div className="px-4 py-3 grid grid-cols-3 gap-2">
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Trades</p>
          <p className="text-base font-black text-white">{r.total_trades}</p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Win Rate</p>
          <p className="text-base font-black" style={{ color: wrColor }}>{r.win_rate.toFixed(1)}%</p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Expectancy</p>
          <p className="text-base font-black" style={{ color: expColor }}>
            {r.expectancy > 0 ? "+" : ""}{r.expectancy.toFixed(2)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Profit Factor</p>
          <p className="text-sm font-bold" style={{ color: r.profit_factor >= 1.5 ? "#4ade80" : r.profit_factor >= 1 ? "#f59e0b" : "#f87171" }}>
            {r.profit_factor >= 99 ? "∞" : r.profit_factor.toFixed(2)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Max DD</p>
          <p className="text-sm font-bold" style={{ color: pctColor(r.max_drawdown_pct, true) }}>
            {r.max_drawdown_pct.toFixed(1)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Retour</p>
          <p className="text-sm font-bold" style={{ color: retColor }}>
            {r.total_return_pct > 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Capital & portfolio metrics row */}
      <div className="px-4 pb-2 flex items-center gap-2 flex-wrap">
        <CapitalDisplay r={r} />
        {r.sharpe_ratio !== undefined && (
          <div className="text-xs px-2 py-1 rounded"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <span className="text-gray-600">Sharpe </span>
            <span className="font-black"
              style={{ color: r.sharpe_ratio >= 1 ? "#4ade80" : r.sharpe_ratio >= 0.5 ? "#f59e0b" : "#f87171" }}>
              {r.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        )}
        {r.cagr_pct !== undefined && (
          <div className="text-xs px-2 py-1 rounded"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <span className="text-gray-600">CAGR </span>
            <span className="font-black"
              style={{ color: r.cagr_pct >= 0 ? "#4ade80" : "#f87171" }}>
              {r.cagr_pct > 0 ? "+" : ""}{r.cagr_pct.toFixed(1)}%
            </span>
          </div>
        )}
        {r.time_in_market_pct !== undefined && (
          <div className="text-xs px-2 py-1 rounded"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <span className="text-gray-600">Marché </span>
            <span className="font-black text-gray-300">{r.time_in_market_pct.toFixed(0)}%</span>
          </div>
        )}
      </div>

      {/* Equity curve */}
      <div className="px-4 pb-2">
        <EquityCurve data={r.equity_curve} color={r.color} height={48} />
        <p className="text-[10px] text-gray-700 mt-1">
          TP +{r.tp_pct}% · SL -{r.sl_pct}% · Fiables: {r.reliable_tickers} tickers
          {r.max_concurrent_positions ? ` · Max ${r.max_concurrent_positions} pos.` : ""}
        </p>
      </div>

      {/* Détail expandable */}
      {expanded && (
        <div className="px-4 pb-3 text-[11px] text-gray-500 space-y-1"
          style={{ borderTop: "1px solid #1a1a28", paddingTop: "10px" }}>
          <p>⏱ Durée moy. : <span className="text-gray-300">{r.avg_duration_days.toFixed(1)}j</span></p>
          <p>🟢 Meilleur ticker : <span className="text-green-400 font-bold">{r.best_ticker}</span></p>
          <p>🔴 Pire ticker : <span className="text-red-400 font-bold">{r.worst_ticker}</span></p>
          <p>📊 Gains / Pertes : <span className="text-gray-300">{r.wins}W / {r.losses}L</span></p>
          {r.max_concurrent_positions !== undefined && (
            <p>🔀 Max positions simultanées : <span className="text-gray-300">{r.max_concurrent_positions}</span></p>
          )}
          {r.time_in_market_pct !== undefined && (
            <p>📈 Temps investi : <span className="text-gray-300">{r.time_in_market_pct.toFixed(1)}%</span></p>
          )}
          {r.expectancy_dollars !== undefined && (
            <p>💰 Gain moyen / trade : <span style={{ color: r.expectancy_dollars >= 0 ? "#4ade80" : "#f87171" }}>
              {r.expectancy_dollars >= 0 ? "+" : ""}${r.expectancy_dollars.toFixed(2)}
            </span></p>
          )}
        </div>
      )}

      {/* Boutons */}
      <div className="px-4 pb-4 flex gap-2">
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex-1 py-2 rounded-xl text-xs font-medium transition-all"
          style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#6b7280" }}
        >
          {expanded ? "▲ Moins" : "▼ Plus"}
        </button>
        <button
          onClick={() => onUse(r)}
          disabled={isActive}
          className="flex-1 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50"
          style={{
            background: isActive ? "#0d0d18" : r.color + "18",
            border: `1px solid ${isActive ? "#1e1e2a" : r.color}`,
            color: isActive ? "#4b5563" : r.color,
          }}
        >
          {isActive ? "✓ Actif" : "Utiliser cette stratégie →"}
        </button>
      </div>
    </div>
  );
}

// ── Tableau comparatif ────────────────────────────────────────────────────────

function CompTable({
  strategies,
  data,
  onUse,
  activeKey,
  minTrades,
}: {
  strategies: LabStrategyResult[];
  data: LabSummary;
  onUse: (r: LabStrategyResult) => void;
  activeKey: string;
  minTrades: number;
}) {
  const [sortKey, setSortKey] = useState<keyof LabStrategyResult>("score");
  const sorted = [...strategies].sort((a, b) => (b[sortKey] as number) - (a[sortKey] as number));

  type Col = { label: string; k: keyof LabStrategyResult; fmt?: (v: number) => string; invert?: boolean };
  const cols: Col[] = [
    { label: "Score /100",    k: "score",            fmt: v => v.toFixed(1) },
    { label: "Trades",        k: "total_trades",     fmt: v => String(v) },
    { label: "Win Rate",      k: "win_rate",         fmt: v => `${v.toFixed(1)}%` },
    { label: "Expectancy",    k: "expectancy",       fmt: v => `${v > 0 ? "+" : ""}${v.toFixed(2)}%` },
    { label: "Profit Factor", k: "profit_factor",    fmt: v => v >= 99 ? "∞" : v.toFixed(2) },
    { label: "Max DD",        k: "max_drawdown_pct", fmt: v => `${v.toFixed(1)}%`, invert: true },
    { label: "Retour",        k: "total_return_pct", fmt: v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%` },
    { label: "Sharpe",        k: "sharpe_ratio",     fmt: v => v.toFixed(2) },
    { label: "CAGR",          k: "cagr_pct",         fmt: v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%` },
    { label: "Fiables",       k: "reliable_tickers", fmt: v => String(v) },
  ];

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Stratégie</th>
              {cols.map(c => (
                <th
                  key={c.k}
                  onClick={() => setSortKey(c.k)}
                  className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer hover:text-gray-300 transition-colors"
                >
                  {c.label}{sortKey === c.k ? " ↓" : ""}
                </th>
              ))}
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => {
              const isActive = r.key === activeKey;
              return (
                <tr
                  key={r.key}
                  style={{
                    borderBottom: "1px solid #1a1a28",
                    background: isActive ? "#0d0d22" : "#0a0a12",
                  }}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ background: r.color }}
                      />
                      <div>
                        <p className="font-bold text-white text-sm">{r.emoji} {r.name}</p>
                        <div className="flex gap-1 mt-0.5 flex-wrap">
                          <TradabilityBadge r={r} />
                          {r.key === bestOverall?.key && isBestTradable  && <Badge label="🏆 Best"      bg="#052e16" text="#4ade80" />}
                          {r.key === bestOverall?.key && isBestConfirmed && <Badge label="⚠️ Best·À confirmer" bg="#1a1000" text="#fbbf24" />}
                          {r.key === bestOverall?.key && !isBestTradable && !isBestConfirmed && <Badge label="🔎 Provisoire" bg="#1a0800" text="#f59e0b" />}
                          {r.key === data.best_win_rate   && <Badge label="🎯 WR"   bg="#052e16" text="#4ade80" />}
                          {r.key === data.best_expectancy && <Badge label="⚡ Exp"  bg="#0f1a3a" text="#818cf8" />}
                          {r.total_trades < minTrades     && <Badge label={r.total_trades === 0 ? "0 trades" : `${r.total_trades}T < ${minTrades}`} bg="#1a0a00" text="#f59e0b" />}
                        </div>
                      </div>
                    </div>
                  </td>
                  {cols.map(c => {
                    const raw = r[c.k] as number;
                    const txt = c.fmt ? c.fmt(raw) : String(raw);
                    const col = pctColor(raw, c.invert);
                    return (
                      <td key={c.k} className="px-3 py-3 text-right font-mono tabular-nums text-sm font-bold" style={{ color: col }}>
                        {txt}
                      </td>
                    );
                  })}
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onUse(r)}
                      disabled={isActive}
                      className="px-3 py-1 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
                      style={{
                        background: isActive ? "#0d0d18" : r.color + "18",
                        border: `1px solid ${isActive ? "#1e1e2a" : r.color}`,
                        color: isActive ? "#4b5563" : r.color,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isActive ? "✓ Actif" : "Utiliser →"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Écran "Use strategy" confirmation ────────────────────────────────────────

function UseStrategyBanner({
  r,
  onClose,
}: {
  r: LabStrategyResult;
  onClose: () => void;
}) {
  return (
    <div
      className="rounded-xl p-4 flex items-center gap-3"
      style={{ background: r.color + "12", border: `1px solid ${r.color}66` }}
    >
      <span className="text-2xl">{r.emoji}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-black" style={{ color: r.color }}>
          Stratégie activée : {r.name}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          Le screener filtre maintenant sur {r.screener_strategy === "conservative" ? "Conservative" : "Standard"}
          {r.screener_signal ? ` · signal "${r.screener_signal}"` : ""}.
          Retournez à l&apos;onglet Tableau pour voir les résultats.
        </p>
      </div>
      <button onClick={onClose} className="text-gray-600 hover:text-gray-300 transition-colors text-sm">✕</button>
    </div>
  );
}

// ── Vue principale ────────────────────────────────────────────────────────────

interface StrategyLabProps {
  onUseStrategy: (screenerStrategy: Strategy, screenerSignal: string, labKey: string, tradableStatus?: string) => void;
  activeStrategyKey: string;
}

export function StrategyLab({ onUseStrategy, activeStrategyKey }: StrategyLabProps) {
  const [data, setData]         = useState<LabSummary | null>(null);
  const [loading, setLoading]   = useState(false);
  const [loaded, setLoaded]     = useState(false);
  const [period, setPeriod]     = useState<12 | 24>(12);
  const [banner, setBanner]     = useState<LabStrategyResult | null>(null);
  const [view, setView]         = useState<"cards" | "table">("cards");
  const [minTrades, setMinTrades] = useState(20);   // seuil d'éligibilité configurable

  const run = useCallback(async (p?: 12 | 24) => {
    setLoading(true);
    const per = p ?? period;
    try {
      const res  = await fetch(`${API_URL}/api/strategy-lab?period=${per}`, { cache: "no-store" });
      const json = await res.json();
      setData(json);
      setLoaded(true);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [period]);

  const handlePeriod = (p: 12 | 24) => {
    setPeriod(p);
    if (loaded) run(p);
  };

  const handleUse = (r: LabStrategyResult) => {
    onUseStrategy(r.screener_strategy, r.screener_signal, r.key, r.tradable_status);
    setBanner(r);
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 gap-5">
        <svg className="animate-spin h-10 w-10 text-indigo-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <div className="text-center">
          <p className="text-white font-bold text-lg mb-1">Strategy Lab en cours…</p>
          <p className="text-gray-500 text-sm">6 stratégies × 40 tickers × {period} mois</p>
          <p className="text-gray-600 text-xs mt-1">⏱ Durée estimée : 1 à 3 minutes</p>
        </div>
        <div className="flex gap-2 mt-2">
          {["Pullback SMA50", "Breakout 30j", "Momentum Fort", "Mean Reversion", "Low Vol Swing", "Conservative"].map((s, i) => (
            <span key={i} className="text-[10px] px-2 py-1 rounded-full text-gray-600" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              {s}
            </span>
          ))}
        </div>
      </div>
    );
  }

  // ── Écran d'accueil ──
  if (!loaded) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-8">
        <div className="text-center max-w-lg">
          <p className="text-5xl mb-4">🧬</p>
          <h2 className="text-2xl font-black text-white mb-2">Strategy Lab</h2>
          <p className="text-gray-400 text-sm leading-relaxed mb-1">
            Backteste automatiquement 6 stratégies swing trading sur l&apos;ensemble des 40 tickers et
            les classe selon un score composite : win rate, expectancy, drawdown et nombre de trades.
          </p>
          <p className="text-gray-600 text-xs">TP variable par stratégie · SL variable · Timeout 30 jours · Minimum 20 trades</p>
        </div>

        {/* Stratégies preview */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full max-w-2xl">
          {[
            ["📉", "Pullback SMA50",       "TP +7% / SL -3%"],
            ["🚀", "Breakout 30 jours",    "TP +10% / SL -4%"],
            ["⚡", "Momentum Fort",        "TP +8% / SL -3%"],
            ["🔄", "Mean Reversion",       "TP +6% / SL -3%"],
            ["🧊", "Low Volatility Swing", "TP +5% / SL -2%"],
            ["🛡", "Conservative Trend",   "TP +5% / SL -2%"],
          ].map(([em, name, params]) => (
            <div key={name} className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              <p className="text-base mb-1">{em}</p>
              <p className="text-xs font-bold text-white">{name}</p>
              <p className="text-[10px] text-gray-600">{params}</p>
            </div>
          ))}
        </div>

        {/* Période + bouton */}
        <div className="flex flex-col items-center gap-4">
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
            {([12, 24] as const).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className="px-5 py-2 text-xs font-semibold transition-all"
                style={{
                  background: period === p ? "#1e1e3a" : "#0d0d18",
                  color:      period === p ? "#818cf8" : "#4b5563",
                  borderRight: p === 12 ? "1px solid #1e1e2a" : undefined,
                }}
              >
                📅 {p} mois
              </button>
            ))}
          </div>
          <button
            onClick={() => run()}
            className="flex items-center gap-3 px-8 py-4 rounded-2xl font-black text-base transition-all hover:opacity-90 active:scale-95"
            style={{ background: "linear-gradient(135deg, #1e1e3a, #0f1a2a)", border: "1px solid #4f46e5", color: "#818cf8" }}
          >
            🧬&nbsp; Lancer le Strategy Lab
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const strategies = Array.isArray(data.strategies) ? data.strategies : [];

  // Éligibilité recalculée côté frontend selon le seuil configurable
  const eligible    = strategies.filter(r => r.total_trades >= minTrades);
  const hasEligible = eligible.length > 0;

  // Hiérarchie pour Best Overall :
  //   1. TRADABLE  2. À CONFIRMER  3. eligible sans contrainte tradability  4. any with trades
  const tradable  = eligible.filter(r => r.tradable_status === "TRADABLE");
  const confirmed = eligible.filter(r => r.tradable_status === "À CONFIRMER");
  const pool =
    tradable.length  > 0 ? tradable  :
    confirmed.length > 0 ? confirmed :
    eligible.length  > 0 ? eligible  :
    strategies.filter(r => r.total_trades > 0);

  const isBestTradable = tradable.length > 0;
  const isBestConfirmed = !isBestTradable && confirmed.length > 0;

  const bestOverall = pool.length > 0
    ? pool.reduce((a, b) => b.score > a.score ? b : a)
    : null;
  const bestWRKey   = pool.length > 0 ? pool.reduce((a, b) => b.win_rate   > a.win_rate   ? b : a).key : "";
  const bestExpKey  = pool.length > 0 ? pool.reduce((a, b) => b.expectancy > a.expectancy ? b : a).key : "";

  const getBadges = (key: string) => {
    const b: string[] = [];
    if (bestOverall?.key === key) {
      if (isBestTradable)  b.push("best_overall");
      else if (isBestConfirmed) b.push("best_overall_confirmed");
      else                 b.push("best_overall_provisional");
    }
    if (bestWRKey  === key) b.push("best_win_rate");
    if (bestExpKey === key) b.push("best_expectancy");
    return b;
  };

  return (
    <div className="space-y-6">

      {/* Bannière moteur partagé */}
      <EngineBanner />

      {/* Header toolbar */}
      <div className="flex items-center gap-3 flex-wrap">

        {/* Période */}
        <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
          {([12, 24] as const).map(p => (
            <button
              key={p}
              onClick={() => handlePeriod(p)}
              className="px-3 py-1.5 text-xs font-semibold transition-all"
              style={{
                background: period === p ? "#1e1e3a" : "#0d0d18",
                color:      period === p ? "#818cf8" : "#4b5563",
                borderRight: p === 12 ? "1px solid #1e1e2a" : undefined,
              }}
            >
              {p} mois
            </button>
          ))}
        </div>

        {/* Vue */}
        <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
          {([["cards", "🃏 Cards"], ["table", "📋 Tableau"]] as [typeof view, string][]).map(([v, l]) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1.5 text-xs font-medium transition-all"
              style={{
                background: view === v ? "#1e1e3a" : "#0d0d18",
                color:      view === v ? "#818cf8" : "#4b5563",
              }}
            >
              {l}
            </button>
          ))}
        </div>

        <button
          onClick={() => run()}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#6b7280" }}
        >
          🔄 Relancer
        </button>

        {/* Seuil min trades */}
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-gray-600">Seuil min trades</span>
          <input
            type="range" min={5} max={30} step={5} value={minTrades}
            onChange={e => setMinTrades(Number(e.target.value))}
            className="w-20 accent-amber-500"
          />
          <span className="text-xs font-bold tabular-nums w-6"
            style={{ color: hasEligible ? "#4ade80" : "#f59e0b" }}>
            {minTrades}
          </span>
        </div>

        <span className="text-xs" style={{ color: hasEligible ? "#4ade80" : "#f59e0b" }}>
          {eligible.length}/{strategies.length} éligibles · {data.period_months}m
        </span>
      </div>

      {/* Banner "stratégie activée" */}
      {banner && <UseStrategyBanner r={banner} onClose={() => setBanner(null)} />}

      {/* Avertissement si aucune stratégie éligible */}
      {!hasEligible && strategies.length > 0 && (
        <div className="rounded-xl px-4 py-3 flex items-start gap-3"
          style={{ background: "#1a1000", border: "1px solid #f59e0b33" }}>
          <span className="text-amber-500 text-lg mt-0.5">⚠️</span>
          <div>
            <p className="text-sm font-bold text-amber-400 mb-1">
              Aucune stratégie n&apos;atteint le seuil de {minTrades} trades
            </p>
            <p className="text-xs text-amber-700 leading-relaxed">
              Les résultats ci-dessous sont provisoires. Baissez le curseur &quot;Seuil min trades&quot; (à 10 par exemple)
              pour voir les meilleurs résultats disponibles, ou relancez le lab sur une période plus longue (24 mois).
            </p>
          </div>
        </div>
      )}

      {/* Best Overall highlight */}
      {bestOverall && (
        <div
          className="rounded-2xl p-5 flex items-center gap-5 flex-wrap"
          style={{
            background: bestOverall.color + "0d",
            border: `1px solid ${bestOverall.color}${hasEligible ? "55" : "33"}`,
          }}
        >
          <div className="flex items-center gap-3">
            <span className="text-4xl">{bestOverall.emoji}</span>
            <div>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-xs font-black px-2 py-0.5 rounded-full uppercase tracking-wider"
                  style={{
                    background: isBestTradable ? "#052e16" : isBestConfirmed ? "#1a1000" : "#1a0800",
                    color:      isBestTradable ? "#4ade80" : isBestConfirmed ? "#fbbf24" : "#f59e0b",
                    border:     `1px solid ${isBestTradable ? "#4ade8044" : isBestConfirmed ? "#fbbf2444" : "#f59e0b44"}`,
                  }}>
                  {isBestTradable
                    ? "🏆 Best Overall Strategy — Tradable"
                    : isBestConfirmed
                    ? "⚠️ Best — À Confirmer (non encore tradable)"
                    : "🔎 Meilleur provisoire — Non Tradable"}
                </span>
                <TradabilityBadge r={bestOverall} />
              </div>
              <p className="text-xl font-black text-white">{bestOverall.name}</p>
              <p className="text-sm text-gray-400">{bestOverall.description}</p>
              <CapitalDisplay r={bestOverall} />
            </div>
          </div>
          <div className="flex gap-6 ml-auto flex-wrap">
            {[
              ["Score",       `${bestOverall.score}/100`,
                bestOverall.color],
              ["Win Rate",    `${bestOverall.win_rate.toFixed(1)}%`,
                bestOverall.win_rate >= 55 ? "#4ade80" : "#f59e0b"],
              ["Expectancy",  `${bestOverall.expectancy > 0 ? "+" : ""}${bestOverall.expectancy.toFixed(2)}%`,
                bestOverall.expectancy > 0 ? "#4ade80" : "#f87171"],
              ["Trades",      String(bestOverall.total_trades),    "#e2e8f0"],
              ["Sharpe",      (bestOverall.sharpe_ratio ?? 0).toFixed(2),
                (bestOverall.sharpe_ratio ?? 0) >= 1 ? "#4ade80" : (bestOverall.sharpe_ratio ?? 0) >= 0.5 ? "#f59e0b" : "#f87171"],
              ["CAGR",        `${(bestOverall.cagr_pct ?? 0) > 0 ? "+" : ""}${(bestOverall.cagr_pct ?? 0).toFixed(1)}%`,
                (bestOverall.cagr_pct ?? 0) >= 0 ? "#4ade80" : "#f87171"],
            ].map(([l, v, c]) => (
              <div key={l} className="text-center">
                <p className="text-[10px] text-gray-600 uppercase tracking-wider">{l}</p>
                <p className="text-lg font-black" style={{ color: c }}>{v}</p>
              </div>
            ))}
          </div>
          <button
            onClick={() => handleUse(bestOverall)}
            disabled={bestOverall.key === activeStrategyKey}
            className="px-5 py-2.5 rounded-xl font-black text-sm transition-all hover:opacity-90 disabled:opacity-40"
            style={{
              background: bestOverall.color + "22",
              border: `1px solid ${bestOverall.color}`,
              color: bestOverall.color,
            }}
          >
            {bestOverall.key === activeStrategyKey ? "✓ Actif" : "Utiliser cette stratégie →"}
          </button>
        </div>
      )}

      {/* Cards ou tableau */}
      {view === "cards" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map(r => (
            <StrategyCard
              key={r.key}
              r={r}
              badges={getBadges(r.key)}
              onUse={handleUse}
              isActive={r.key === activeStrategyKey}
              minTrades={minTrades}
            />
          ))}
        </div>
      ) : (
        <CompTable
          strategies={strategies}
          data={data}
          onUse={handleUse}
          activeKey={activeStrategyKey}
          minTrades={minTrades}
        />
      )}

      {/* Equity curves side by side */}
      <div>
        <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
          Courbes d&apos;équité comparées
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {strategies.map(r => (
            <div key={r.key} className="rounded-xl p-3" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold" style={{ color: r.color }}>{r.emoji} {r.name}</p>
                <span className="text-xs font-black tabular-nums"
                  style={{ color: r.total_return_pct >= 0 ? "#4ade80" : "#f87171" }}>
                  {r.total_return_pct > 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
                </span>
              </div>
              <EquityCurve data={r.equity_curve} color={r.color} height={60} />
              <p className="text-[10px] text-gray-700 mt-1">{r.total_trades} trades · WR {r.win_rate.toFixed(1)}%</p>
            </div>
          ))}
        </div>
      </div>

      {/* Parameter Optimizer */}
      <OptimizerSection period={period} onUseStrategy={onUseStrategy} />

    </div>
  );
}

// ── Parameter Optimizer Section ───────────────────────────────────────────────

const FAMILY_COLORS: Record<string, string> = {
  "Pullback SMA50":  "#818cf8",
  "Breakout 30j":    "#f59e0b",
  "Momentum Fort":   "#10b981",
  "Mean Reversion":  "#06b6d4",
  "Low Vol Swing":   "#a78bfa",
};

const FAMILY_TO_SIGNAL: Record<string, string> = {
  "Pullback SMA50":  "Pullback",
  "Breakout 30j":    "Breakout",
  "Momentum Fort":   "Momentum",
  "Mean Reversion":  "Pullback",
  "Low Vol Swing":   "Pullback",
};

function ParamPill({ label, value }: { label: string; value: string | number | boolean }) {
  const v = typeof value === "boolean" ? (value ? "✓" : "✗") : String(value);
  const color = typeof value === "boolean"
    ? (value ? "#4ade80" : "#6b7280")
    : "#e2e8f0";
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded font-mono"
      style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color }}>
      <span className="text-gray-600">{label}</span>
      <span>{v}</span>
    </span>
  );
}

function OptParamCard({
  ps,
  rank,
  onUse,
}: {
  ps: OptimizedParamSet;
  rank: number;
  onUse: (ps: OptimizedParamSet) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const fColor = FAMILY_COLORS[ps.family] ?? "#818cf8";
  const medal  = rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : `#${rank}`;

  const wrColor  = ps.win_rate >= 60 ? "#4ade80" : ps.win_rate >= 48 ? "#f59e0b" : "#f87171";
  const expColor = ps.expectancy > 0 ? "#4ade80" : "#f87171";
  const pfColor  = ps.profit_factor >= 1.5 ? "#4ade80" : ps.profit_factor >= 1 ? "#f59e0b" : "#f87171";

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all"
      style={{
        background: "#0a0a14",
        border: `1px solid ${ps.eligible ? fColor + "44" : "#2a1a0044"}`,
        opacity: ps.eligible ? 1 : 0.8,
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-3" style={{ borderBottom: "1px solid #1a1a28", background: fColor + "09" }}>
        <span className="text-lg font-black" style={{ color: fColor }}>{medal}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-black px-2 py-0.5 rounded-full"
              style={{ background: fColor + "22", color: fColor, border: `1px solid ${fColor}44` }}>
              {ps.family}
            </span>
            {!ps.eligible && (
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold"
                style={{ background: "#1a0800", color: "#f59e0b", border: "1px solid #f59e0b33" }}>
                ⚠️ {ps.total_trades}T · provisoire
              </span>
            )}
          </div>
          <p className="text-[10px] text-gray-600 mt-0.5">
            TP +{ps.params.tp_pct.toFixed(1)}% · SL -{ps.params.sl_pct.toFixed(1)}% · Max {ps.params.max_days}j
            · RSI {ps.params.rsi_min}–{ps.params.rsi_max}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-black" style={{ color: fColor }}>{ps.score.toFixed(1)}</p>
          <p className="text-[10px] text-gray-600">/100</p>
        </div>
      </div>

      {/* Métriques */}
      <div className="px-4 py-3 grid grid-cols-4 gap-2">
        <div className="text-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Trades</p>
          <p className="text-sm font-black text-white">{ps.total_trades}</p>
        </div>
        <div className="text-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Win Rate</p>
          <p className="text-sm font-black" style={{ color: wrColor }}>{ps.win_rate.toFixed(1)}%</p>
        </div>
        <div className="text-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Expectancy</p>
          <p className="text-sm font-black" style={{ color: expColor }}>
            {ps.expectancy > 0 ? "+" : ""}{ps.expectancy.toFixed(2)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">PF</p>
          <p className="text-sm font-black" style={{ color: pfColor }}>
            {ps.profit_factor >= 99 ? "∞" : ps.profit_factor.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Paramètres expandable */}
      {expanded && (
        <div className="px-4 pb-3" style={{ borderTop: "1px solid #1a1a28", paddingTop: "10px" }}>
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Paramètres complets</p>
          <div className="flex flex-wrap gap-1">
            <ParamPill label="dist" value={`${ps.params.dist_min}–${ps.params.dist_max}%`} />
            <ParamPill label="RSI" value={`${ps.params.rsi_min}–${ps.params.rsi_max}`} />
            <ParamPill label="uptrend" value={ps.params.req_uptrend} />
            <ParamPill label="MACD" value={ps.params.req_macd} />
            <ParamPill label="vol" value={ps.params.req_vol} />
            {ps.params.req_vol && <ParamPill label="vol×" value={ps.params.vol_mult} />}
            <ParamPill label="new_high" value={ps.params.req_new_high} />
            <ParamPill label="perf3m≥" value={`${ps.params.perf_3m_min}%`} />
            <ParamPill label="TP" value={`+${ps.params.tp_pct.toFixed(1)}%`} />
            <ParamPill label="SL" value={`-${ps.params.sl_pct.toFixed(1)}%`} />
            <ParamPill label="max" value={`${ps.params.max_days}j`} />
          </div>
          <div className="mt-2 flex gap-4 text-[10px] text-gray-600">
            <span>Max DD: <span style={{ color: "#f87171" }}>{ps.max_drawdown_pct.toFixed(1)}%</span></span>
            <span>Retour: <span style={{ color: ps.total_return_pct >= 0 ? "#4ade80" : "#f87171" }}>
              {ps.total_return_pct > 0 ? "+" : ""}{ps.total_return_pct.toFixed(1)}%
            </span></span>
          </div>
        </div>
      )}

      {/* Boutons */}
      <div className="px-4 pb-4 flex gap-2">
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex-1 py-1.5 rounded-xl text-xs font-medium transition-all"
          style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#6b7280" }}
        >
          {expanded ? "▲ Moins" : "▼ Paramètres"}
        </button>
        <button
          onClick={() => onUse(ps)}
          className="flex-1 py-1.5 rounded-xl text-xs font-bold transition-all hover:opacity-90"
          style={{
            background: fColor + "18",
            border: `1px solid ${fColor}`,
            color: fColor,
          }}
        >
          Utiliser →
        </button>
      </div>
    </div>
  );
}

function OptimizerSection({
  period,
  onUseStrategy,
}: {
  period: 12 | 24;
  onUseStrategy: (screenerStrategy: Strategy, screenerSignal: string, labKey: string, tradableStatus?: string) => void;
}) {
  const [optData, setOptData]     = useState<OptimizerResult | null>(null);
  const [optLoading, setOptLoading] = useState(false);
  const [optLoaded, setOptLoaded] = useState(false);

  const runOptimizer = useCallback(async () => {
    setOptLoading(true);
    try {
      const res  = await fetch(`${API_URL}/api/optimizer?period=${period}`, { cache: "no-store" });
      const json = await res.json();
      setOptData(json);
      setOptLoaded(true);
    } catch (e) {
      console.error(e);
    } finally {
      setOptLoading(false);
    }
  }, [period]);

  const handleUseOptimized = (ps: OptimizedParamSet) => {
    const signal = FAMILY_TO_SIGNAL[ps.family] ?? "";
    // Low Vol Swing → conservative; others → standard
    const strategy: Strategy = ps.family === "Low Vol Swing" ? "conservative" : "standard";
    onUseStrategy(strategy, signal, `opt_${ps.family}_${ps.rank}`);
  };

  return (
    <div>
      {/* Séparateur titre */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 h-px" style={{ background: "#1e1e2a" }} />
        <p className="text-xs font-black text-gray-500 uppercase tracking-widest whitespace-nowrap">
          🔬 Parameter Optimizer
        </p>
        <div className="flex-1 h-px" style={{ background: "#1e1e2a" }} />
      </div>

      {!optLoaded && !optLoading && (
        <div className="rounded-2xl p-8 text-center" style={{ background: "#0a0a14", border: "1px solid #1e1e2a" }}>
          <p className="text-3xl mb-3">🔬</p>
          <p className="text-sm font-black text-white mb-1">Parameter Optimizer</p>
          <p className="text-xs text-gray-500 mb-1 leading-relaxed max-w-md mx-auto">
            Teste automatiquement ~200 combinaisons de paramètres sur 5 familles de stratégies
            et classe les résultats par score composite.
          </p>
          <p className="text-[11px] text-gray-600 mb-5">
            TP/SL · RSI · Distance SMA50 · Volume · Tendance · MACD · Durée max
          </p>
          <button
            onClick={runOptimizer}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-black text-sm transition-all hover:opacity-90"
            style={{ background: "linear-gradient(135deg, #1a0f2e, #0f1a3a)", border: "1px solid #7c3aed", color: "#a78bfa" }}
          >
            🔬&nbsp; Lancer l&apos;optimiseur
          </button>
          <p className="text-[10px] text-gray-700 mt-3">⏱ Durée estimée : 2 à 5 minutes</p>
        </div>
      )}

      {optLoading && (
        <div className="rounded-2xl p-10 text-center" style={{ background: "#0a0a14", border: "1px solid #1e1e2a" }}>
          <svg className="animate-spin h-8 w-8 text-violet-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-white font-bold mb-1">Optimisation en cours…</p>
          <p className="text-xs text-gray-500">~200 combinaisons × {period} mois</p>
        </div>
      )}

      {optLoaded && optData && (
        <div className="space-y-4">
          {/* Résumé */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Combinaisons testées", value: optData.total_tested, color: "#818cf8" },
              { label: "Éligibles (≥20T)",     value: optData.eligible_count, color: optData.has_eligible ? "#4ade80" : "#f59e0b" },
              { label: "Tickers utilisés",      value: optData.tickers_used,   color: "#06b6d4" },
              { label: "Période",               value: `${optData.period_months}m`, color: "#e2e8f0" },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-3 text-center" style={{ background: "#0d0d18", border: `1px solid ${s.color}22` }}>
                <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: s.color }}>{s.label}</p>
                <p className="text-xl font-black text-white">{s.value}</p>
              </div>
            ))}
          </div>

          {!optData.has_eligible && (
            <div className="rounded-xl px-4 py-3 flex items-start gap-3"
              style={{ background: "#1a1000", border: "1px solid #f59e0b33" }}>
              <span className="text-amber-500">⚠️</span>
              <p className="text-xs text-amber-600">
                Aucune combinaison n&apos;a généré ≥ 20 trades. Les résultats ci-dessous sont provisoires.
                Essayez sur 24 mois pour plus de données.
              </p>
            </div>
          )}

          {/* Toolbar optimizer */}
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">
              Top {optData.top.length} meilleures combinaisons
              {optData.from_cache && <span className="ml-2 text-gray-700">(cache)</span>}
            </p>
            <button
              onClick={runOptimizer}
              className="px-3 py-1 rounded-lg text-xs font-medium"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#6b7280" }}
            >
              🔄 Relancer
            </button>
          </div>

          {/* Grille top 10 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {optData.top.map((ps) => (
              <OptParamCard
                key={`${ps.family}-${ps.rank}`}
                ps={ps}
                rank={ps.rank}
                onUse={handleUseOptimized}
              />
            ))}
          </div>

          {/* Stats globales */}
          <div className="rounded-xl p-4 text-xs text-gray-600"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <span className="font-bold text-gray-500">Stats de l&apos;ensemble des {optData.total_tested} combinaisons :</span>
            &nbsp;Score moy. {optData.stats.avg_score.toFixed(1)} · WR moy. {optData.stats.avg_win_rate.toFixed(1)}% · Exp. moy. {optData.stats.avg_expectancy > 0 ? "+" : ""}{optData.stats.avg_expectancy.toFixed(2)}%
          </div>
        </div>
      )}
    </div>
  );
}
