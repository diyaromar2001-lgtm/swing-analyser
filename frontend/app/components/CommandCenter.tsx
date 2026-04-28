"use client";

import { useEffect, useState } from "react";
import { TickerResult, MarketRegime, MarketContext as MCType } from "../types";

type TradableStatus = "TRADABLE" | "À CONFIRMER" | "NON TRADABLE" | null;

interface MarketStatus {
  is_open: boolean;
  mode:    string;
  time_et: string;
  day:     string;
}

const API_URL      = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SIM_CAPITAL  = 10_000;
const RISK_PCT     = 0.01; // 1 % per trade

// ─── Decision Score ─────────────────────────────────────────────────────────

function decisionScore(
  t: TickerResult,
  regime: MarketRegime | null,
  bt: TradableStatus,
): number {
  const techMap: Record<string, number> = { "A+": 100, A: 80, B: 55, REJECT: 10 };
  const tech = techMap[t.setup_grade] ?? 10;

  const btVal =
    bt === "TRADABLE"     ? 90 :
    bt === "À CONFIRMER"  ? 55 :
    bt === "NON TRADABLE" ? 10 :
    (t.quality_score ?? 50);

  const rr     = Math.min(100, (t.rr_ratio / 3) * 100);
  const regMap: Record<string, number> = { BULL: 100, RANGE: 60, BEAR: 20, UNKNOWN: 40 };
  const reg    = regime ? (regMap[regime.regime] ?? 40) : 40;
  const execM: Record<string, number> = { READY: 100, WAIT: 50, INVALID: 0 };
  const exec   = execM[t.setup_status ?? "WAIT"] ?? 50;

  return Math.round(tech * 0.30 + btVal * 0.25 + rr * 0.20 + reg * 0.15 + exec * 0.10);
}

// ─── Badge helpers ──────────────────────────────────────────────────────────

interface Badge { label: string; color: string; bg: string }

function techBadge(t: TickerResult): Badge {
  const c =
    t.setup_grade === "A+" ? "#10b981" :
    t.setup_grade === "A"  ? "#a3e635" :
    t.setup_grade === "B"  ? "#f59e0b" : "#6b7280";
  return { label: t.setup_grade === "REJECT" ? "C" : t.setup_grade, color: c, bg: c + "18" };
}

function btBadge(t: TickerResult, bt: TradableStatus): Badge {
  if (bt === "NON TRADABLE") return { label: "NOT PROFITABLE", color: "#ef4444", bg: "#ef444418" };
  if (bt === "TRADABLE")     return { label: "VALIDATED ✓",    color: "#10b981", bg: "#10b98118" };
  if (bt === "À CONFIRMER")  return { label: "WEAK DATA",      color: "#f59e0b", bg: "#f59e0b18" };
  const qs = t.quality_score ?? 50;
  if (qs >= 70) return { label: "VALIDATED ✓",    color: "#10b981", bg: "#10b98118" };
  if (qs >= 40) return { label: "WEAK DATA",      color: "#f59e0b", bg: "#f59e0b18" };
  return         { label: "NOT PROFITABLE", color: "#ef4444", bg: "#ef444418" };
}

function execBadge(t: TickerResult, regime: MarketRegime | null, bt: TradableStatus): Badge {
  if (bt === "NON TRADABLE" || regime?.regime === "BEAR")
    return { label: "SKIP",    color: "#ef4444", bg: "#ef444418" };
  if (t.setup_status === "INVALID" || t.rr_ratio < 1.5)
    return { label: "INVALID", color: "#ef4444", bg: "#ef444418" };
  if (t.setup_status === "READY" && t.rr_ratio >= 2 && t.dist_entry_pct <= 2)
    return { label: "READY",   color: "#10b981", bg: "#10b98118" };
  return   { label: "WAIT",    color: "#f59e0b", bg: "#f59e0b18" };
}

// ─── Position size ──────────────────────────────────────────────────────────

function posSize(t: TickerResult) {
  const riskAmt      = SIM_CAPITAL * RISK_PCT;
  const riskPerShare = Math.max(0.01, t.entry - t.stop_loss);
  const shares       = Math.floor(riskAmt / riskPerShare);
  const value        = shares * t.entry;
  return {
    shares,
    value:   value.toFixed(0),
    pct:     ((value / SIM_CAPITAL) * 100).toFixed(0),
    riskAmt: riskAmt.toFixed(0),
  };
}

// ─── Daily decision ─────────────────────────────────────────────────────────

interface Decision {
  title: string; sub: string; emoji: string;
  color: string; bg: string; border: string;
}

function getDecision(
  regime:    MarketRegime | null,
  bt:        TradableStatus,
  tops:      TickerResult[],
  ms:        MarketStatus | null,
): Decision {
  if (bt === "NON TRADABLE")
    return { title: "NO TRADE",          sub: "Strategy not validated — open Strategy Lab first",      emoji: "🚫", color: "#ef4444", bg: "#130404", border: "#7f1d1d" };
  if (regime?.regime === "BEAR")
    return { title: "NO TRADE",          sub: "Bear market — SPY below SMA200 — reduce exposure",     emoji: "🐻", color: "#ef4444", bg: "#130404", border: "#7f1d1d" };
  if (regime?.data_ok === false || !regime)
    return { title: "DATA UNAVAILABLE",  sub: "Cannot verify market conditions — proceed with caution", emoji: "⚠️", color: "#f59e0b", bg: "#120d00", border: "#92400e" };
  if (tops.length === 0)
    return { title: "WAIT",              sub: "No qualified setups today — monitor watchlist",          emoji: "👁",  color: "#6b7280", bg: "#0c0c18", border: "#1e1e2a" };

  const ready = tops.filter(t => t.setup_status === "READY");

  if (ms?.is_open && ready.length > 0)
    return { title: "TRADE TODAY",       sub: `${ready.length} setup${ready.length > 1 ? "s" : ""} near entry · Execution mode active`, emoji: "⚡", color: "#10b981", bg: "#041310", border: "#065f46" };
  if (!ms?.is_open && tops.length > 0)
    return { title: "PREPARE ORDERS",   sub: `${tops.length} setup${tops.length > 1 ? "s" : ""} valid · Set limit orders before open`,  emoji: "📋", color: "#6366f1", bg: "#09091e", border: "#3730a3" };

  return   { title: "WATCH & WAIT",     sub: "Setups valid but price not yet at entry",                emoji: "⏳", color: "#f59e0b", bg: "#120d00", border: "#92400e" };
}

// ─── Pill ───────────────────────────────────────────────────────────────────

function Pill({ b }: { b: Badge }) {
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-black tracking-wider"
      style={{ background: b.bg, color: b.color, border: `1px solid ${b.color}44` }}
    >
      {b.label}
    </span>
  );
}

// ─── A. Market Regime Block ─────────────────────────────────────────────────

function MarketRegimeBlock({
  regime, vix, ms,
}: {
  regime: MarketRegime | null;
  vix:    number | null;
  ms:     MarketStatus | null;
}) {
  const rColor =
    regime?.regime === "BULL"  ? "#10b981" :
    regime?.regime === "BEAR"  ? "#ef4444" :
    regime?.regime === "RANGE" ? "#f59e0b" : "#6b7280";
  const rLabel =
    regime?.regime === "BULL"  ? "Bullish" :
    regime?.regime === "BEAR"  ? "Bearish" :
    regime?.regime === "RANGE" ? "Neutral" : "Unknown";

  const spyOk  = regime
    ? regime.spy_price > regime.spy_sma50 && regime.spy_sma50 > regime.spy_sma200
    : false;

  const vRisk  = !vix ? "—" : vix < 15 ? "Low" : vix < 25 ? "Medium" : "High";
  const vColor = !vix ? "#6b7280" : vix < 15 ? "#10b981" : vix < 25 ? "#f59e0b" : "#ef4444";

  const cells = [
    { label: "Market",    value: ms?.is_open ? "OPEN"      : "CLOSED",     color: ms?.is_open ? "#10b981" : "#9ca3af" },
    { label: "Mode",      value: ms?.is_open ? "EXECUTION" : "PREPARATION", color: ms?.is_open ? "#10b981" : "#6366f1" },
    { label: "Regime",    value: rLabel,                                     color: rColor },
    { label: "SPY Trend", value: spyOk ? "OK" : "NOT OK",                   color: spyOk ? "#10b981" : "#ef4444" },
    { label: "VIX Risk",  value: vix ? `${vix.toFixed(1)} — ${vRisk}` : "—", color: vColor },
    ...(regime && regime.data_ok !== false ? [{
      label: "SPY",
      value: `$${regime.spy_price.toFixed(2)}  ${regime.spy_perf_1m >= 0 ? "+" : ""}${regime.spy_perf_1m.toFixed(1)}%`,
      color: regime.spy_perf_1m >= 0 ? "#10b981" : "#ef4444",
    }] : []),
  ];

  return (
    <div
      className="rounded-xl px-5 py-4 flex items-center gap-5 flex-wrap"
      style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}
    >
      {/* Live dot */}
      <span
        className="w-2 h-2 rounded-full animate-pulse flex-shrink-0"
        style={{ background: ms?.is_open ? "#10b981" : "#4b5563" }}
      />

      {cells.map((c, i) => (
        <div key={c.label} className="flex items-center gap-4">
          {i > 0 && <div className="w-px h-6 hidden sm:block" style={{ background: "#1a1a2e" }} />}
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest leading-none mb-0.5">{c.label}</p>
            <p className="text-xs font-black leading-none" style={{ color: c.color }}>{c.value}</p>
          </div>
        </div>
      ))}

      {ms && (
        <span className="ml-auto text-[10px] text-gray-700 flex-shrink-0">
          {ms.time_et} · {ms.day}
        </span>
      )}
    </div>
  );
}

// ─── B. Daily Decision Block ────────────────────────────────────────────────

function DailyDecisionBlock({ decision }: { decision: Decision }) {
  return (
    <div
      className="rounded-2xl p-8 text-center"
      style={{ background: decision.bg, border: `2px solid ${decision.border}` }}
    >
      <p className="text-4xl mb-3">{decision.emoji}</p>
      <p className="text-3xl font-black tracking-widest mb-2" style={{ color: decision.color }}>
        {decision.title}
      </p>
      <p className="text-sm" style={{ color: decision.color + "99" }}>{decision.sub}</p>
    </div>
  );
}

// ─── Trade Plan Panel (slide-in) ────────────────────────────────────────────

function TradePlanPanel({
  t, regime, bt, onClose,
}: {
  t:       TickerResult;
  regime:  MarketRegime | null;
  bt:      TradableStatus;
  onClose: () => void;
}) {
  const ps   = posSize(t);
  const exec = execBadge(t, regime, bt);

  const verdict =
    bt === "NON TRADABLE"     ? "Skip — strategy not validated (open Strategy Lab)" :
    regime?.regime === "BEAR" ? "Skip — bear market conditions (wait for recovery)" :
    t.dist_entry_pct > 5     ? `Wait for pullback to $${t.entry.toFixed(2)}` :
    exec.label === "READY"    ? `Buy near $${t.entry.toFixed(2)} (at limit)` :
    `Wait for pullback to $${t.entry.toFixed(2)}`;

  const invalidations = [
    `Price closes below stop loss at $${t.stop_loss.toFixed(2)}`,
    t.sma50   ? `Price drops below SMA50 ($${t.sma50.toFixed(2)})` : null,
    "Market regime shifts to Bearish (SPY < SMA200)",
    t.earnings_warning ? `⚠️ Earnings in ${t.earnings_days} days — reduce size or avoid` : null,
  ].filter(Boolean) as string[];

  const mgmt = [
    `Take 50% off at TP1 ($${t.tp1.toFixed(2)})`,
    "Move stop to breakeven after TP1",
    `Let runner run to TP2 ($${t.tp2.toFixed(2)})`,
    t.trailing_stop ? `Trailing stop active at $${t.trailing_stop.toFixed(2)}` : null,
  ].filter(Boolean) as string[];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "rgba(0,0,0,.75)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md h-full overflow-y-auto p-6 space-y-4 flex-shrink-0"
        style={{ background: "#0a0a16", borderLeft: "1px solid #1a1a2e" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest">Trade Plan</p>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-2xl font-black text-white">{t.ticker}</p>
              <span className="text-xs text-gray-500">{t.signal_type}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 hover:text-white transition-colors"
            style={{ background: "#1a1a2e" }}
          >✕</button>
        </div>

        {/* 3 badges */}
        <div className="flex gap-1.5 flex-wrap">
          <Pill b={techBadge(t)} />
          <Pill b={btBadge(t, bt)} />
          <Pill b={exec} />
          <span className="px-2 py-0.5 rounded text-[10px] font-black"
            style={{ background: "#1a1a2e", color: "#6b7280" }}>
            Score {decisionScore(t, regime, bt)}/100
          </span>
        </div>

        {/* ① Verdict */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-2">① Verdict</p>
          <p className="text-sm font-black text-white leading-snug">{verdict}</p>
          <p className="text-[10px] text-gray-600 mt-1.5">
            {t.dist_entry_pct > 0 ? "+" : ""}{t.dist_entry_pct.toFixed(1)}% from entry ·
            {" "}Sector: {t.sector}
          </p>
        </section>

        {/* ② Orders */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-3">② Orders to Place</p>
          <div className="space-y-2.5">
            {[
              { label: "Buy Limit",     value: `$${t.entry.toFixed(2)}`,     color: "#6366f1" },
              { label: "Stop Loss",     value: `$${t.stop_loss.toFixed(2)}`, color: "#ef4444" },
              { label: "Take Profit 1", value: `$${t.tp1.toFixed(2)}`,       color: "#10b981" },
              { label: "Take Profit 2", value: `$${t.tp2.toFixed(2)}`,       color: "#34d399" },
              { label: "Position Size", value: `${ps.shares} shares (~$${ps.value})`, color: "#f59e0b" },
              { label: "Risk $",        value: `$${ps.riskAmt} — 1% of capital`,      color: "#ef4444" },
              { label: "R / R",         value: `1 : ${t.rr_ratio.toFixed(1)}`,        color: "#10b981" },
            ].map(row => (
              <div key={row.label} className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{row.label}</span>
                <span className="text-sm font-black" style={{ color: row.color }}>{row.value}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ③ Invalidations */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #ef444430" }}>
          <p className="text-[9px] font-black text-red-600 uppercase tracking-widest mb-3">③ Invalidations</p>
          <ul className="space-y-2">
            {invalidations.map((inv, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                <span className="text-red-500 mt-px flex-shrink-0">✗</span>
                {inv}
              </li>
            ))}
          </ul>
        </section>

        {/* ④ Trade Management */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #10b98130" }}>
          <p className="text-[9px] font-black text-emerald-600 uppercase tracking-widest mb-3">④ Trade Management</p>
          <ul className="space-y-2">
            {mgmt.map((step, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                <span className="text-emerald-500 mt-px flex-shrink-0">✓</span>
                {step}
              </li>
            ))}
          </ul>
        </section>

        {/* Earnings warning */}
        {t.earnings_warning && (
          <div
            className="rounded-xl px-4 py-3 flex items-center gap-2"
            style={{ background: "#120d00", border: "1px solid #92400e" }}
          >
            <span>⚠️</span>
            <p className="text-xs text-yellow-500">
              Earnings in {t.earnings_days} days — reduce position size or skip
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── C. Opportunity Card ────────────────────────────────────────────────────

function OpportunityCard({
  t, rank, regime, bt, ms, score, onClick,
}: {
  t:       TickerResult & { decisionScore?: number };
  rank:    number;
  regime:  MarketRegime | null;
  bt:      TradableStatus;
  ms:      MarketStatus | null;
  score:   number;
  onClick: () => void;
}) {
  const tech = techBadge(t);
  const bval = btBadge(t, bt);
  const exec = execBadge(t, regime, bt);
  const ps   = posSize(t);

  const action =
    bt === "NON TRADABLE" || regime?.regime === "BEAR" ? "SKIP" :
    t.dist_entry_pct > 3                               ? "WAIT" :
    exec.label === "READY"                             ? "BUY NEAR" : "WAIT";

  const aColor =
    action === "BUY NEAR" ? "#10b981" :
    action === "WAIT"     ? "#f59e0b" : "#ef4444";

  const conf      = t.confidence >= 70 ? "HIGH" : t.confidence >= 45 ? "MEDIUM" : "LOW";
  const confColor = conf === "HIGH" ? "#10b981" : conf === "MEDIUM" ? "#f59e0b" : "#ef4444";

  const borderColor =
    exec.label === "READY"   ? "#065f4680" :
    exec.label === "WAIT"    ? "#92400e60" :
    exec.label === "INVALID" ? "#7f1d1d60" : "#1a1a2e";

  const isNearEntry = ms?.is_open && t.dist_entry_pct <= 1.5;

  return (
    <div
      className="rounded-2xl p-5 cursor-pointer transition-transform hover:scale-[1.005]"
      style={{ background: "#0c0c18", border: `1px solid ${borderColor}` }}
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3 gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold text-gray-700">#{rank}</span>
          <span className="text-xl font-black text-white">{t.ticker}</span>
          <span className="text-[11px] text-gray-500">{t.signal_type}</span>
          {isNearEntry && (
            <span
              className="px-2 py-0.5 rounded text-[9px] font-black animate-pulse"
              style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}
            >
              ⚡ NEAR ENTRY
            </span>
          )}
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-sm font-black tracking-wider" style={{ color: aColor }}>{action}</p>
          <p className="text-[10px] text-gray-700">Score {score}/100</p>
        </div>
      </div>

      {/* 3 badges */}
      <div className="flex gap-1.5 flex-wrap mb-4">
        <Pill b={tech} />
        <Pill b={bval} />
        <Pill b={exec} />
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        {[
          { label: "ENTRY", value: `$${t.entry.toFixed(2)}`,     color: "#6366f1" },
          { label: "STOP",  value: `$${t.stop_loss.toFixed(2)}`, color: "#ef4444" },
          { label: "TP1",   value: `$${t.tp1.toFixed(2)}`,       color: "#10b981" },
          { label: "TP2",   value: `$${t.tp2.toFixed(2)}`,       color: "#34d399" },
        ].map(l => (
          <div
            key={l.label}
            className="rounded-lg p-2 text-center"
            style={{ background: "#07070f", border: `1px solid ${l.color}20` }}
          >
            <p className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: l.color }}>
              {l.label}
            </p>
            <p className="text-xs font-black text-white">{l.value}</p>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center gap-4 text-[10px] text-gray-700">
        <span>R/R <strong className="text-gray-500">1:{t.rr_ratio.toFixed(1)}</strong></span>
        <span>Size <strong className="text-gray-500">{ps.pct}% cap.</strong></span>
        <span>Confidence <strong style={{ color: confColor }}>{conf}</strong></span>
        <span className="ml-auto text-gray-700 text-[9px]">Tap for trade plan →</span>
      </div>
    </div>
  );
}

// ─── D. Risk Control Block ──────────────────────────────────────────────────

function RiskControlBlock({
  tops, regime, bt,
}: {
  tops:   TickerResult[];
  regime: MarketRegime | null;
  bt:     TradableStatus;
}) {
  const active   = tops.filter(t => {
    const e = execBadge(t, regime, bt);
    return e.label !== "SKIP" && e.label !== "INVALID";
  });
  const avgRisk  = active.length
    ? (active.reduce((a, t) => a + t.risk_now_pct, 0) / active.length).toFixed(1)
    : "0";
  const maxExp   = Math.min(active.length * 5, 20);
  const riskOk   = parseFloat(avgRisk) <= 5 && maxExp <= 20;

  return (
    <div
      className="rounded-2xl p-5"
      style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}
    >
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest">⚖️ Risk Control</p>
        <span
          className="px-2.5 py-1 rounded-lg text-[10px] font-black"
          style={{
            background: riskOk ? "#041310" : "#130404",
            color:      riskOk ? "#10b981" : "#ef4444",
            border:     `1px solid ${riskOk ? "#065f46" : "#7f1d1d"}`,
          }}
        >
          {riskOk ? "RISK OK ✓" : "RISK HIGH ⚠"}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Simulated Capital", value: `$${SIM_CAPITAL.toLocaleString()}`,       color: "#6b7280", sub: "Base capital" },
          { label: "Risk / Trade",      value: `$${(SIM_CAPITAL * RISK_PCT).toFixed(0)}`, color: "#f59e0b", sub: `${(RISK_PCT * 100).toFixed(0)}% — max loss/trade` },
          { label: "Active Setups",     value: active.length,                             color: "#6366f1", sub: "Positions open" },
          { label: "Max Exposure",      value: `${maxExp}%`,                              color: riskOk ? "#10b981" : "#ef4444", sub: "5% per position" },
        ].map(s => (
          <div
            key={s.label}
            className="rounded-xl p-3 text-center"
            style={{ background: "#07070f", border: `1px solid ${s.color}20` }}
          >
            <p className="text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: s.color }}>
              {s.label}
            </p>
            <p className="text-xl font-black text-white">{s.value}</p>
            <p className="text-[9px] text-gray-700 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Strategy Summary strip ─────────────────────────────────────────────────

function StrategyStrip({
  bt, onGoToLab,
}: {
  bt:        TradableStatus;
  onGoToLab: () => void;
}) {
  const color =
    bt === "TRADABLE"     ? "#10b981" :
    bt === "À CONFIRMER"  ? "#f59e0b" :
    bt === "NON TRADABLE" ? "#ef4444" : "#6b7280";

  return (
    <div
      className="flex items-center gap-4 px-4 py-3 rounded-xl flex-wrap"
      style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}
    >
      <div>
        <p className="text-[9px] text-gray-700 uppercase tracking-widest">Active Strategy</p>
        <p className="text-xs font-black" style={{ color }}>
          Standard · {bt ?? "Not tested"}
        </p>
      </div>
      <button
        onClick={onGoToLab}
        className="ml-auto text-[10px] font-bold text-gray-600 hover:text-gray-400 transition-colors"
      >
        Open Strategy Lab →
      </button>
    </div>
  );
}

// ─── Command Center ─────────────────────────────────────────────────────────

export function CommandCenter({
  data,
  regime,
  backtestStatus,
  loading,
  onRefresh,
  onAdvancedView,
  onGoToLab,
}: {
  data:           TickerResult[];
  regime:         MarketRegime | null;
  backtestStatus: TradableStatus;
  loading:        boolean;
  onRefresh:      () => void;
  onAdvancedView: () => void;
  onGoToLab:      () => void;
}) {
  const [ms,       setMs]       = useState<MarketStatus | null>(null);
  const [vix,      setVix]      = useState<number | null>(null);
  const [selected, setSelected] = useState<TickerResult | null>(null);

  useEffect(() => {
    const fetchMs  = () =>
      fetch(`${API_URL}/api/market-status`)
        .then(r => r.json()).then(setMs).catch(() => null);
    const fetchCtx = () =>
      fetch(`${API_URL}/api/market-context`)
        .then(r => r.json())
        .then((d: MCType) => setVix(d.vix))
        .catch(() => null);

    fetchMs();
    fetchCtx();
    const id = setInterval(fetchMs, 60_000);
    return () => clearInterval(id);
  }, []);

  const isNonTradable = backtestStatus === "NON TRADABLE";
  const isBear        = regime?.regime === "BEAR";

  // Score every valid ticker
  const scored = data
    .filter(r => r.setup_grade !== "REJECT")
    .map(r => ({ ...r, decisionScore: decisionScore(r, regime, backtestStatus) }))
    .sort((a, b) => b.decisionScore - a.decisionScore);

  // Top opportunities (live trades)
  const topOpps = isNonTradable || isBear
    ? []
    : scored.filter(r => r.rr_ratio >= 1.5).slice(0, 5);

  // Theoretical watchlist (shown when strategy invalid or bear)
  const theoretical = isNonTradable || isBear ? scored.slice(0, 5) : [];

  const decision = getDecision(regime, backtestStatus, topOpps, ms);

  return (
    <div className="space-y-3">

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold text-gray-700 uppercase tracking-widest">
          {data.length} setups analysed · {topOpps.length} opportunit{topOpps.length === 1 ? "y" : "ies"}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40"
            style={{ background: "#1a1a2e", border: "1px solid #2a2a4e", color: "#818cf8" }}
          >
            {loading
              ? <><svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>Loading…</>
              : "⟳ Refresh"}
          </button>
          <button
            onClick={onAdvancedView}
            className="px-3 py-1.5 rounded-lg text-xs font-medium"
            style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#4b5563" }}
          >
            Advanced View →
          </button>
        </div>
      </div>

      {/* A — Market Regime */}
      <MarketRegimeBlock regime={regime} vix={vix} ms={ms} />

      {/* B — Daily Decision */}
      <DailyDecisionBlock decision={decision} />

      {/* C — Top Opportunities */}
      {topOpps.length > 0 && (
        <div>
          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2 px-1">
            🎯 Top Opportunities
          </p>
          <div className="space-y-3">
            {topOpps.map((t, i) => (
              <OpportunityCard
                key={t.ticker}
                t={t}
                rank={i + 1}
                regime={regime}
                bt={backtestStatus}
                ms={ms}
                score={t.decisionScore}
                onClick={() => setSelected(t)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Theoretical Watchlist */}
      {theoretical.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2 px-1">
            <p className="text-[10px] font-black text-amber-600 uppercase tracking-widest">
              👁 Theoretical Watchlist
            </p>
            <span className="text-[9px] text-gray-700">not for live trading</span>
          </div>
          <div className="space-y-3">
            {theoretical.map((t, i) => (
              <OpportunityCard
                key={t.ticker}
                t={t}
                rank={i + 1}
                regime={regime}
                bt={backtestStatus}
                ms={ms}
                score={t.decisionScore}
                onClick={() => setSelected(t)}
              />
            ))}
          </div>
        </div>
      )}

      {/* D — Risk Control */}
      <RiskControlBlock
        tops={[...topOpps, ...theoretical]}
        regime={regime}
        bt={backtestStatus}
      />

      {/* Strategy strip */}
      <StrategyStrip bt={backtestStatus} onGoToLab={onGoToLab} />

      {/* Trade Plan Panel */}
      {selected && (
        <TradePlanPanel
          t={selected}
          regime={regime}
          bt={backtestStatus}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
