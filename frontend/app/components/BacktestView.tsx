"use client";

import { useState, useCallback } from "react";
import { BacktestSummary, BacktestResult, BacktestTrade, PortfolioMetrics } from "../types";
import { Strategy } from "./Dashboard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Bannière de cohérence moteur ──────────────────────────────────────────────

export function EngineBanner() {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs flex-wrap"
      style={{ background: "#0a0f1a", border: "1px solid #1e2a3a" }}>
      <span className="font-black text-indigo-400">📊 Moteur Portfolio Réaliste</span>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">Capital <span className="text-gray-300 font-semibold">10 000 $</span></span>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">Risque <span className="text-gray-300 font-semibold">1 % / trade</span></span>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">Max <span className="text-gray-300 font-semibold">8 positions</span></span>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">Commission <span className="text-gray-300 font-semibold">0.05 %</span></span>
      <span className="text-gray-600">·</span>
      <span className="text-amber-600 font-semibold">Win rate = trades clôturés uniquement</span>
    </div>
  );
}

// ── Panneau portfolio réaliste ────────────────────────────────────────────────

function TradabilityPill({ status, color, emoji }: { status: string; color: string; emoji: string }) {
  const bg: Record<string, string> = {
    "TRADABLE":     "#052e16",
    "À CONFIRMER":  "#1a1000",
    "NON TRADABLE": "#1a0000",
  };
  return (
    <span className="text-xs font-black px-3 py-1 rounded-full"
      style={{ background: bg[status] ?? "#0d0d18", color, border: `1px solid ${color}44` }}>
      {emoji} {status}
    </span>
  );
}

function PortfolioPanel({ p }: { p: PortfolioMetrics }) {
  const retColor  = p.total_return_pct >= 0 ? "#4ade80" : "#f87171";
  const ddColor   = p.max_drawdown_pct <= -20 ? "#f87171" : p.max_drawdown_pct <= -10 ? "#f59e0b" : "#4ade80";
  const shrColor  = p.sharpe_ratio >= 1 ? "#4ade80" : p.sharpe_ratio >= 0.5 ? "#f59e0b" : "#f87171";
  const wrColor   = p.win_rate >= 55 ? "#4ade80" : p.win_rate >= 45 ? "#f59e0b" : "#f87171";

  const fmtCap = (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k$` : `${v.toFixed(0)}$`;

  // mini equity curve SVG
  const pts = p.equity_curve ?? [0];
  const w = 280, h = 56;
  const mn = Math.min(...pts), mx = Math.max(...pts), rng = mx - mn || 1;
  const path = pts.map((v, i) => {
    const x = (i / Math.max(pts.length - 1, 1)) * w;
    const y = h - ((v - mn) / rng) * (h - 4) - 2;
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  const lineColor = (pts[pts.length - 1] ?? 0) >= 0 ? "#4ade80" : "#f87171";
  const zeroY = h - ((0 - mn) / rng) * (h - 4) - 2;

  return (
    <div className="rounded-2xl overflow-hidden mb-4"
      style={{ background: "#08080f", border: `2px solid ${p.tradable_color}44` }}>

      {/* Header */}
      <div className="px-5 py-3 flex items-center gap-3 flex-wrap"
        style={{ background: "#0d0d1a", borderBottom: "1px solid #1e1e2a" }}>
        <TradabilityPill status={p.tradable_status} color={p.tradable_color} emoji={p.tradable_emoji} />
        <span className="text-xs text-gray-500">Simulation portfolio — même moteur que Strategy Lab</span>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <span className="text-gray-600 font-mono">10.0k$</span>
          <span className="text-gray-600">→</span>
          <span className="font-black font-mono" style={{ color: retColor }}>{fmtCap(p.final_capital)}</span>
        </div>
      </div>

      {/* Metrics grid + equity curve */}
      <div className="px-5 py-4 flex gap-6 flex-wrap">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-x-6 gap-y-3 flex-1 min-w-0">
          {[
            ["Trades",        String(p.total_trades),                                "#e2e8f0"],
            ["Win Rate",      `${p.win_rate.toFixed(1)}%`,                           wrColor],
            ["Profit Factor", p.profit_factor >= 99 ? "∞" : p.profit_factor.toFixed(2),
              p.profit_factor >= 1.3 ? "#4ade80" : p.profit_factor >= 1 ? "#f59e0b" : "#f87171"],
            ["Max DD",        `${p.max_drawdown_pct.toFixed(1)}%`,                   ddColor],
            ["Sharpe",        p.sharpe_ratio.toFixed(2),                             shrColor],
            ["CAGR",          `${p.cagr_pct > 0 ? "+" : ""}${p.cagr_pct.toFixed(1)}%`, retColor],
            ["Retour total",  `${p.total_return_pct > 0 ? "+" : ""}${p.total_return_pct.toFixed(1)}%`, retColor],
            ["Durée moy.",    `${p.avg_duration_days.toFixed(1)}j`,                  "#9ca3af"],
            ["Temps investi", `${p.time_in_market_pct.toFixed(0)}%`,                 "#9ca3af"],
          ].map(([label, val, color]) => (
            <div key={label}>
              <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">{label}</p>
              <p className="text-sm font-black" style={{ color }}>{val}</p>
            </div>
          ))}
        </div>

        {/* Mini equity curve */}
        {pts.length > 1 && (
          <div className="flex-shrink-0" style={{ width: w }}>
            <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">Courbe d&apos;équité</p>
            <svg viewBox={`0 0 ${w} ${h}`} style={{ width: w, height: h }}>
              <line x1="0" y1={zeroY} x2={w} y2={zeroY}
                stroke="#2a2a3a" strokeWidth="1" strokeDasharray="4 3" />
              <path d={`${path} L ${w} ${h} L 0 ${h} Z`}
                fill={lineColor} fillOpacity="0.12" />
              <path d={path} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <p className="text-[10px] text-gray-700 mt-1">
              {p.max_concurrent_positions} positions max · {p.total_trades} trades simulés
            </p>
          </div>
        )}
      </div>

      {/* Tradability criteria */}
      <div className="px-5 pb-3 text-[10px] text-gray-600">
        Critères : PF &gt; 1.3 · DD &gt; -25 % · Trades ≥ 30 · Sharpe &gt; 0.5
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Pct({ v, invert = false }: { v: number; invert?: boolean }) {
  const good   = invert ? v < 0 : v > 0;
  const color  = Math.abs(v) < 0.1 ? "#6b7280" : good ? "#4ade80" : "#f87171";
  return (
    <span className="font-mono tabular-nums text-sm" style={{ color }}>
      {v > 0 ? "+" : ""}{v.toFixed(2)}%
    </span>
  );
}

function StatBox({ label, value, sub, color = "#e2e8f0" }: {
  label: string; value: React.ReactNode; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-xl p-4" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-black" style={{ color }}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  );
}

// ── Trades détail ─────────────────────────────────────────────────────────────

function TradeRow({ t }: { t: BacktestTrade }) {
  const color = t.pnl_pct > 0 ? "#4ade80" : "#f87171";
  const reasonColor = t.exit_reason === "TP" ? "#4ade80" : t.exit_reason === "SL" ? "#f87171" : "#9ca3af";
  return (
    <tr style={{ borderBottom: "1px solid #1a1a28" }}>
      <td className="px-3 py-2 text-xs text-gray-400 font-mono">{t.entry_date}</td>
      <td className="px-3 py-2 text-xs text-gray-400 font-mono">{t.exit_date}</td>
      <td className="px-3 py-2 text-xs font-mono text-gray-300">${t.entry_price.toFixed(2)}</td>
      <td className="px-3 py-2 text-xs font-mono text-gray-300">${t.exit_price.toFixed(2)}</td>
      <td className="px-3 py-2">
        <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ color: reasonColor, background: reasonColor + "15" }}>
          {t.exit_reason}
        </span>
      </td>
      <td className="px-3 py-2 text-xs font-bold tabular-nums font-mono" style={{ color }}>
        {t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
      </td>
      <td className="px-3 py-2 text-xs text-gray-500 tabular-nums">{t.duration_days}j</td>
    </tr>
  );
}

// ── Ligne ticker ──────────────────────────────────────────────────────────────

function TickerRow({ r }: { r: BacktestResult }) {
  const [open, setOpen] = useState(false);

  if (r.error || r.total_trades === 0) {
    return (
      <tr style={{ borderBottom: "1px solid #1a1a28", background: "#0a0a12" }}>
        <td className="px-4 py-3 font-bold text-gray-500">{r.ticker}</td>
        <td colSpan={9} className="px-4 py-3 text-xs text-gray-600 italic">
          {r.error || "Aucun signal détecté sur la période"}
        </td>
      </tr>
    );
  }

  const returnColor = r.total_return_pct > 0 ? "#4ade80" : "#f87171";
  const wrColor     = r.win_rate >= 60 ? "#4ade80" : r.win_rate >= 45 ? "#f59e0b" : "#f87171";
  const expColor    = r.expectancy > 0 ? "#4ade80" : "#f87171";

  return (
    <>
      <tr
        onClick={() => setOpen(o => !o)}
        className="cursor-pointer hover:bg-white/[0.02] transition-colors"
        style={{ borderBottom: "1px solid #1a1a28", background: open ? "#0d0d1e" : "#0a0a12" }}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white text-sm">{r.ticker}</span>
            {r.reliable ? (
              <span className="text-xs px-1.5 py-0.5 rounded font-bold" style={{ background: "#052e16", color: "#4ade80", border: "1px solid #166534" }}>
                ✓ Fiable
              </span>
            ) : (
              <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "#1a1000", color: "#9ca3af", border: "1px solid #2a2a00" }}>
                {r.total_trades} trade{r.total_trades > 1 ? "s" : ""}
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-sm text-gray-300 tabular-nums">{r.total_trades}</td>
        <td className="px-4 py-3 text-sm font-bold tabular-nums" style={{ color: wrColor }}>{r.win_rate.toFixed(1)}%</td>
        <td className="px-4 py-3"><Pct v={r.avg_gain_pct} /></td>
        <td className="px-4 py-3"><Pct v={r.avg_loss_pct} invert /></td>
        <td className="px-4 py-3 text-sm font-bold tabular-nums" style={{ color: expColor }}>
          {r.expectancy > 0 ? "+" : ""}{r.expectancy.toFixed(2)}%
        </td>
        <td className="px-4 py-3"><Pct v={r.max_drawdown_pct} invert /></td>
        <td className="px-4 py-3"><Pct v={r.best_trade_pct} /></td>
        <td className="px-4 py-3"><Pct v={r.worst_trade_pct} invert /></td>
        <td className="px-4 py-3 text-xl font-black tabular-nums" style={{ color: returnColor }}>
          {r.total_return_pct > 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
        </td>
        <td className="px-4 py-3 text-gray-600 text-xs">{open ? "▲" : "▼"}</td>
      </tr>

      {open && r.trades.length > 0 && (
        <tr style={{ background: "#08080f", borderBottom: "1px solid #1a1a28" }}>
          <td colSpan={11} className="px-4 py-4">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              Détail des {r.trades.length} trades — {r.ticker}
            </p>
            <div className="overflow-x-auto rounded-lg" style={{ border: "1px solid #1e1e2a" }}>
              <table className="w-full">
                <thead style={{ background: "#0d0d18" }}>
                  <tr>
                    {["Entrée", "Sortie", "Prix entrée", "Prix sortie", "Raison", "P&L", "Durée"].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.trades.map((t, i) => <TradeRow key={i} t={t} />)}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Equity Curve simple ───────────────────────────────────────────────────────

function MiniEquityCurve({ trades, label }: { trades: BacktestResult[]; label?: string }) {
  if (!Array.isArray(trades)) return null;
  const validTrades = trades.filter(r => r.total_trades > 0 && !r.error);
  if (validTrades.length === 0) return null;

  const allTrades = validTrades
    .flatMap(r => r.trades.map(t => ({ ...t, ticker: r.ticker })))
    .sort((a, b) => a.entry_date.localeCompare(b.entry_date));

  if (allTrades.length === 0) return null;

  let cum = 0;
  const points = [0, ...allTrades.map(t => { cum += t.pnl_pct; return cum; })];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 600;
  const h = 80;

  const path = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");

  const lastVal = points[points.length - 1];
  const color = lastVal >= 0 ? "#4ade80" : "#f87171";

  return (
    <div className="rounded-xl p-5" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">
          {label || "Courbe d'équité cumulée (tous trades)"}
        </p>
        <span className="text-sm font-black" style={{ color }}>
          {lastVal > 0 ? "+" : ""}{lastVal.toFixed(1)}%
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 80 }}>
        <defs>
          <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L ${w} ${h} L 0 ${h} Z`} fill={`url(#grad-${label})`} />
        <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
        <line x1="0" y1={((0 - min) / range * h)} x2={w} y2={((0 - min) / range * h)}
          stroke="#2a2a3a" strokeWidth="1" strokeDasharray="4 4" />
      </svg>
      <p className="text-xs text-gray-600 mt-2">{allTrades.length} trades simulés sur 12 mois</p>
    </div>
  );
}

// ── Comparaison côte à côte ───────────────────────────────────────────────────

function ComparisonRow({
  label,
  stdVal,
  conVal,
  format,
  higherIsBetter = true,
}: {
  label: string;
  stdVal: number;
  conVal: number;
  format: (v: number) => string;
  higherIsBetter?: boolean;
}) {
  const stdWins = higherIsBetter ? stdVal >= conVal : stdVal <= conVal;
  const conWins = higherIsBetter ? conVal >= stdVal : conVal <= stdVal;
  const tie = stdVal === conVal;

  const stdColor = tie ? "#e2e8f0" : stdWins ? "#4ade80" : "#f87171";
  const conColor = tie ? "#e2e8f0" : conWins ? "#4ade80" : "#f87171";

  return (
    <tr style={{ borderBottom: "1px solid #1a1a28" }}>
      <td className="px-4 py-3 text-xs text-gray-400">{label}</td>
      <td className="px-4 py-3 text-sm font-bold tabular-nums text-center" style={{ color: stdColor }}>
        {format(stdVal)}
      </td>
      <td className="px-4 py-3 text-sm font-bold tabular-nums text-center" style={{ color: conColor }}>
        {format(conVal)}
      </td>
    </tr>
  );
}

function ComparisonPanel({ std, con }: { std: BacktestSummary; con: BacktestSummary }) {
  return (
    <div className="rounded-xl overflow-hidden mb-6" style={{ border: "1px solid #4f46e5" }}>
      <div className="px-4 py-3 flex items-center gap-3" style={{ background: "#0f0f24", borderBottom: "1px solid #1e1e3a" }}>
        <span className="text-lg">⚖️</span>
        <p className="text-sm font-bold text-indigo-300">Comparaison Standard vs Conservative</p>
      </div>
      <table className="w-full" style={{ background: "#0a0a14" }}>
        <thead style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Métrique</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-indigo-400 uppercase tracking-wider">📊 Standard</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-green-400 uppercase tracking-wider">🛡 Conservative</th>
          </tr>
        </thead>
        <tbody>
          <ComparisonRow label="Trades totaux"    stdVal={std.global_total_trades} conVal={con.global_total_trades} format={v => String(v)} />
          <ComparisonRow label="Win rate global"  stdVal={std.global_win_rate}     conVal={con.global_win_rate}     format={v => `${v.toFixed(1)}%`} />
          <ComparisonRow label="Expectancy moy."  stdVal={std.global_expectancy}   conVal={con.global_expectancy}   format={v => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`} />
          <ComparisonRow label="Tickers fiables"  stdVal={std.global_reliable_count} conVal={con.global_reliable_count} format={v => String(v)} />
          <ComparisonRow label="Retour total"
            stdVal={Array.isArray(std.results) ? std.results.reduce((a, r) => a + r.total_return_pct, 0) : 0}
            conVal={Array.isArray(con.results) ? con.results.reduce((a, r) => a + r.total_return_pct, 0) : 0}
            format={v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
          />
          <ComparisonRow label="Max Drawdown moy."
            stdVal={Array.isArray(std.results) ? std.results.filter(r => r.total_trades > 0).reduce((a, r) => a + r.max_drawdown_pct, 0) / (std.global_reliable_count || 1) : 0}
            conVal={Array.isArray(con.results) ? con.results.filter(r => r.total_trades > 0).reduce((a, r) => a + r.max_drawdown_pct, 0) / (con.global_reliable_count || 1) : 0}
            format={v => `${v.toFixed(2)}%`}
            higherIsBetter={false}
          />
        </tbody>
      </table>
    </div>
  );
}

// ── Panel de résultats pour une stratégie ────────────────────────────────────

function StrategyPanel({
  data,
  strategyLabel,
  accent,
  onRerun,
}: {
  data: BacktestSummary;
  strategyLabel: string;
  accent: string;
  onRerun: () => void;
}) {
  const [sortBy, setSortBy] = useState<"total_return_pct" | "win_rate" | "expectancy" | "total_trades">("total_return_pct");
  const [filterReliable, setFilterReliable] = useState(false);

  const results = Array.isArray(data.results) ? data.results : [];
  const sorted = [...results].sort((a, b) => {
    if (sortBy === "win_rate")     return b.win_rate - a.win_rate;
    if (sortBy === "expectancy")   return b.expectancy - a.expectancy;
    if (sortBy === "total_trades") return b.total_trades - a.total_trades;
    return b.total_return_pct - a.total_return_pct;
  });
  const displayed = filterReliable ? sorted.filter(r => r.reliable) : sorted;

  const Th = ({ label, k }: { label: string; k?: typeof sortBy }) => (
    <th
      className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer hover:text-gray-300 transition-colors"
      onClick={k ? () => setSortBy(k) : undefined}
    >
      {label}{k && sortBy === k ? " ↓" : ""}
    </th>
  );

  return (
    <div className="space-y-4">
      {/* Header stratégie */}
      <div className="flex items-center gap-2 pb-1" style={{ borderBottom: `2px solid ${accent}33` }}>
        <span className="text-sm font-black" style={{ color: accent }}>{strategyLabel}</span>
      </div>

      {/* Portfolio réaliste — affiché en premier si disponible */}
      {data.portfolio && <PortfolioPanel p={data.portfolio} />}

      {/* Stats globales par ticker (drill-down) */}
      <p className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">
        Détail par ticker
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <StatBox label="Trades totaux"   value={data.global_total_trades} />
        <StatBox label="Win rate"        value={`${data.global_win_rate}%`}
          color={data.global_win_rate >= 55 ? "#4ade80" : data.global_win_rate >= 45 ? "#f59e0b" : "#f87171"} />
        <StatBox label="Expectancy"      value={`${data.global_expectancy > 0 ? "+" : ""}${data.global_expectancy.toFixed(2)}%`}
          color={data.global_expectancy > 0 ? "#4ade80" : "#f87171"} />
        <StatBox label="Fiables"         value={`${data.global_reliable_count} / ${results.length}`} color="#818cf8" sub="≥ 5 trades" />
        <StatBox label="Meilleur"        value={data.best_ticker} color="#4ade80" />
        <StatBox label="Pire"            value={data.worst_ticker} color="#f87171" />
      </div>

      {/* Courbe */}
      <MiniEquityCurve trades={results} label={`Équité — ${strategyLabel}`} />

      {/* Filtres */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => setFilterReliable(f => !f)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          style={{
            background: filterReliable ? "#052e16" : "#0d0d18",
            border: `1px solid ${filterReliable ? "#166534" : "#1e1e2a"}`,
            color: filterReliable ? "#4ade80" : "#6b7280",
          }}
        >
          ✓ Fiables seulement ({data.global_reliable_count})
        </button>
        <button
          onClick={onRerun}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#6b7280" }}
        >
          🔄 Relancer
        </button>
        <span className="text-xs text-gray-600 ml-auto">{displayed.length} tickers</span>
      </div>

      {/* Tableau */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead style={{ background: "#0d0d18", borderBottom: "1px solid #1e1e2a" }}>
              <tr>
                <Th label="Ticker" />
                <Th label="Trades" k="total_trades" />
                <Th label="Win Rate" k="win_rate" />
                <Th label="Gain moy." />
                <Th label="Perte moy." />
                <Th label="Expectancy" k="expectancy" />
                <Th label="Max DD" />
                <Th label="Meilleur" />
                <Th label="Pire" />
                <Th label="Retour total" k="total_return_pct" />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {Array.isArray(displayed) && displayed.map(r => <TickerRow key={r.ticker} r={r} />)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Vue principale ────────────────────────────────────────────────────────────

export function BacktestView({ strategy }: { strategy: Strategy }) {
  const [mode, setMode] = useState<"single" | "compare">("single");

  // Single strategy data
  const [data, setData]       = useState<BacktestSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded]   = useState(false);

  // Comparison data
  const [stdData, setStdData]   = useState<BacktestSummary | null>(null);
  const [conData, setConData]   = useState<BacktestSummary | null>(null);
  const [cmpLoading, setCmpLoading] = useState(false);
  const [cmpLoaded, setCmpLoaded]   = useState(false);

  const run = useCallback(async (strat?: string) => {
    setLoading(true);
    try {
      const s = strat ?? strategy;
      const res  = await fetch(`${API_URL}/api/backtest?strategy=${s}`, { cache: "no-store" });
      const json = await res.json();
      setData(json);
      setLoaded(true);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [strategy]);

  const runComparison = useCallback(async () => {
    setCmpLoading(true);
    try {
      const [stdRes, conRes] = await Promise.all([
        fetch(`${API_URL}/api/backtest?strategy=standard`, { cache: "no-store" }),
        fetch(`${API_URL}/api/backtest?strategy=conservative`, { cache: "no-store" }),
      ]);
      const [stdJson, conJson] = await Promise.all([stdRes.json(), conRes.json()]);
      setStdData(stdJson);
      setConData(conJson);
      setCmpLoaded(true);
    } catch (e) {
      console.error(e);
    } finally {
      setCmpLoading(false);
    }
  }, []);

  // ── Mode tabs ──
  return (
    <div className="space-y-6">

      {/* Bannière moteur */}
      <EngineBanner />

      {/* Mode toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
          {([["single", "🧪 Backtest simple"], ["compare", "⚖️ Comparer Standard vs Conservative"]] as [typeof mode, string][]).map(([m, label]) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="px-4 py-2 text-xs font-medium transition-all"
              style={{
                background: mode === m ? "#1e1e3a" : "#0d0d18",
                color: mode === m ? "#818cf8" : "#4b5563",
              }}
            >
              {label}
            </button>
          ))}
        </div>
        {mode === "single" && (
          <span className="text-xs text-gray-600">
            Stratégie active : <span className="font-bold" style={{ color: strategy === "conservative" ? "#4ade80" : "#818cf8" }}>
              {strategy === "conservative" ? "🛡 Conservative" : "📊 Standard"}
            </span>
          </span>
        )}
      </div>

      {/* ── SINGLE MODE ── */}
      {mode === "single" && (
        <>
          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <svg className="animate-spin h-8 w-8 text-indigo-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <p className="text-gray-400 text-sm font-medium">Simulation en cours…</p>
              <p className="text-gray-600 text-xs">TP +5% · SL -2% · Timeout 30j · 40 tickers</p>
              <p className="text-gray-700 text-xs">⏱ Durée estimée : 2 à 3 minutes</p>
            </div>
          ) : !loaded ? (
            <div className="flex flex-col items-center justify-center py-24 gap-6">
              <div className="text-center">
                <p className="text-4xl mb-3">📊</p>
                <p className="text-white font-bold text-lg mb-1">Backtest sur 12 mois</p>
                <p className="text-gray-500 text-sm mb-1">Simule les signaux BUY NOW sur l&apos;historique complet</p>
                <p className="text-gray-600 text-xs">TP +5% · SL -2% · Durée max 30 jours</p>
              </div>
              <button
                onClick={() => run()}
                className="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm transition-all hover:opacity-90 active:scale-95"
                style={{ background: "#1e1e3a", border: "1px solid #4f46e5", color: "#818cf8" }}
              >
                ▶&nbsp; Lancer le backtest (~2-3 min)
              </button>
            </div>
          ) : data ? (
            <StrategyPanel
              data={data}
              strategyLabel={strategy === "conservative" ? "🛡 Conservative" : "📊 Standard"}
              accent={strategy === "conservative" ? "#4ade80" : "#818cf8"}
              onRerun={() => run()}
            />
          ) : null}
        </>
      )}

      {/* ── COMPARE MODE ── */}
      {mode === "compare" && (
        <>
          {cmpLoading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <svg className="animate-spin h-8 w-8 text-indigo-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <p className="text-gray-400 text-sm font-medium">Simulation des deux stratégies en parallèle…</p>
              <p className="text-gray-600 text-xs">TP +5% · SL -2% · Timeout 30j · 40 tickers × 2</p>
              <p className="text-gray-700 text-xs">⏱ Durée estimée : 3 à 5 minutes</p>
            </div>
          ) : !cmpLoaded ? (
            <div className="flex flex-col items-center justify-center py-24 gap-6">
              <div className="text-center">
                <p className="text-4xl mb-3">⚖️</p>
                <p className="text-white font-bold text-lg mb-1">Comparaison Standard vs Conservative</p>
                <p className="text-gray-500 text-sm mb-1">Lance les deux backtests en parallèle et compare les résultats</p>
                <p className="text-gray-600 text-xs">Win rate · Expectancy · Max Drawdown · Retour total</p>
              </div>
              <button
                onClick={runComparison}
                className="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm transition-all hover:opacity-90 active:scale-95"
                style={{ background: "#1e1e3a", border: "1px solid #4f46e5", color: "#818cf8" }}
              >
                ▶&nbsp; Lancer la comparaison (~3-5 min)
              </button>
            </div>
          ) : stdData && conData ? (
            <>
              {/* Tableau comparaison */}
              <ComparisonPanel std={stdData} con={conData} />

              {/* Courbes côte à côte */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-2">
                <MiniEquityCurve trades={Array.isArray(stdData.results) ? stdData.results : []} label="Équité — Standard" />
                <MiniEquityCurve trades={Array.isArray(conData.results) ? conData.results : []} label="Équité — Conservative" />
              </div>

              {/* Détail par stratégie */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <StrategyPanel
                  data={stdData}
                  strategyLabel="📊 Standard"
                  accent="#818cf8"
                  onRerun={runComparison}
                />
                <StrategyPanel
                  data={conData}
                  strategyLabel="🛡 Conservative"
                  accent="#4ade80"
                  onRerun={runComparison}
                />
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
