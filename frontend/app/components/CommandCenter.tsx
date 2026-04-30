"use client";

import { useEffect, useState } from "react";
import { TickerResult, MarketRegime, MarketContext as MCType, RegimeEngine } from "../types";
import { useJournal } from "../hooks/useJournal";
import { TakeTradeModal } from "./TakeTradeModal";
import { getApiUrl } from "../lib/api";

type TradableStatus = "TRADABLE" | "À CONFIRMER" | "NON TRADABLE" | null;

interface MarketStatus {
  is_open: boolean;
  mode:    string;
  time_et: string;
  day:     string;
}

const API_URL     = getApiUrl();
const SIM_CAPITAL = 10_000;
const RISK_PCT    = 0.01;

function hasValidatedEdge(t: TickerResult): boolean {
  return t.ticker_edge_status === "STRONG_EDGE" || t.ticker_edge_status === "VALID_EDGE";
}

function hasCriticalOverfit(t: TickerResult): boolean {
  return t.ticker_edge_status === "OVERFITTED" || !!t.overfit_warning;
}

function isTradeCandidate(
  t: TickerResult,
  engine: RegimeEngine | null,
  signalFilter: string[],
): boolean {
  if (!hasValidatedEdge(t)) return false;
  if (hasCriticalOverfit(t)) return false;
  if (t.setup_grade === "REJECT") return false;
  if (t.setup_status === "INVALID") return false;
  if (t.final_decision === "SKIP") return false;
  if (t.tradable === false) return false;
  if (engine?.can_trade === false) return false;
  if (signalFilter.length > 0 && !signalFilter.includes(t.signal_type ?? "")) return false;
  return true;
}

function isTechnicalWatchlistCandidate(
  t: TickerResult,
  engine: RegimeEngine | null,
  signalFilter: string[],
): boolean {
  if (signalFilter.length > 0 && !signalFilter.includes(t.signal_type ?? "")) return false;
  if (hasValidatedEdge(t)) return false;
  if (hasCriticalOverfit(t)) return false;
  if (t.setup_grade === "REJECT") return false;
  if (t.setup_status === "INVALID") return false;
  if ((t.final_decision ?? "WAIT") === "SKIP") return false;
  if (engine?.can_trade === false) return false;
  return true;
}

// ─── Decision Score ─────────────────────────────────────────────────────────

function decisionScore(
  t: TickerResult,
  engine: RegimeEngine | null,
  bt: TradableStatus,
): number {
  const techMap: Record<string, number> = { "A+": 100, A: 80, B: 55, REJECT: 10 };
  const tech = techMap[t.setup_grade] ?? 10;
  const btVal =
    bt === "TRADABLE"     ? 90 :
    bt === "À CONFIRMER"  ? 55 :
    bt === "NON TRADABLE" ? 10 : (t.quality_score ?? 50);
  const rr    = Math.min(100, (t.rr_ratio / 3) * 100);
  const reg   = engine ? (engine.can_trade ? Math.min(100, engine.confidence) : 10) : 40;
  const execM: Record<string, number> = { READY: 100, WAIT: 50, INVALID: 0 };
  const exec  = execM[t.setup_status ?? "WAIT"] ?? 50;
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

function execBadge(t: TickerResult): Badge {
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
  return { shares, value: value.toFixed(0), pct: ((value / SIM_CAPITAL) * 100).toFixed(0), riskAmt: riskAmt.toFixed(0) };
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

// ─── A. Regime Bar ───────────────────────────────────────────────────────────

function RegimeBar({
  engine, ms,
}: {
  engine: RegimeEngine | null;
  ms:     MarketStatus | null;
}) {
  const rColor = engine?.regime_color ?? "#6b7280";
  const vix    = engine?.vix ?? 0;
  const vColor = vix > 28 ? "#ef4444" : vix > 22 ? "#f59e0b" : "#10b981";

  const cells = [
    { label: "Marché",   value: ms?.is_open ? "OUVERT" : "FERMÉ",           color: ms?.is_open ? "#10b981" : "#9ca3af" },
    { label: "Mode",     value: ms?.is_open ? "EXÉCUTION" : "PRÉPARATION",  color: ms?.is_open ? "#10b981" : "#6366f1" },
    { label: "Régime",   value: engine?.regime_label ?? "—",                color: rColor },
    { label: "SPY",      value: engine ? `$${engine.spy_price.toFixed(0)}` : "—",  color: "#e2e8f0" },
    { label: "VIX",      value: engine ? `${engine.vix.toFixed(1)}` : "—",  color: vColor },
    { label: "RSI(SPY)", value: engine ? `${engine.spy_rsi.toFixed(0)}` : "—",     color: engine && engine.spy_rsi > 70 ? "#ef4444" : engine && engine.spy_rsi > 55 ? "#10b981" : "#f59e0b" },
  ];

  return (
    <div
      className="rounded-xl px-5 py-3 flex items-center gap-5 flex-wrap"
      style={{ background: "#0c0c18", border: `1px solid ${rColor}30` }}
    >
      <span
        className="w-2 h-2 rounded-full animate-pulse flex-shrink-0"
        style={{ background: ms?.is_open ? "#10b981" : "#4b5563" }}
      />
      {cells.map((c, i) => (
        <div key={c.label} className="flex items-center gap-4">
          {i > 0 && <div className="w-px h-5 hidden sm:block" style={{ background: "#1a1a2e" }} />}
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest leading-none mb-0.5">{c.label}</p>
            <p className="text-xs font-black leading-none" style={{ color: c.color }}>{c.value}</p>
          </div>
        </div>
      ))}
      {ms && <span className="ml-auto text-[10px] text-gray-700 flex-shrink-0">{ms.time_et} · {ms.day}</span>}
    </div>
  );
}

// ─── B. Active Strategy Block ────────────────────────────────────────────────

function ActiveStrategyBlock({ engine }: { engine: RegimeEngine | null }) {
  const color = engine?.strategy_color ?? "#6b7280";
  const conf  = engine?.confidence ?? 0;

  const regimeBg: Record<string, string> = {
    BULL_TREND:      "#041310",
    PULLBACK_TREND:  "#07071e",
    RANGE:           "#120d00",
    HIGH_VOLATILITY: "#130800",
    BEAR_TREND:      "#130404",
    UNKNOWN:         "#0c0c18",
  };
  const bg     = regimeBg[engine?.regime ?? "UNKNOWN"] ?? "#0c0c18";

  return (
    <div className="rounded-2xl p-5 flex flex-col gap-3" style={{ background: bg, border: `1px solid ${color}40` }}>
      <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest">Stratégie Active</p>

      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-4xl leading-none">{engine?.strategy_emoji ?? "—"}</span>
        <div className="flex-1">
          <p className="text-xl font-black leading-tight" style={{ color }}>
            {engine?.active_strategy?.replace("_", " ") ?? "NO TRADE"}
          </p>
          <p className="text-xs text-gray-500">{engine?.strategy_name}</p>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-3xl font-black text-white leading-none">{conf}<span className="text-lg text-gray-600">%</span></p>
          <p className="text-[9px] text-gray-700 uppercase tracking-widest">confiance</p>
        </div>
      </div>

      {/* Reasons */}
      <div className="space-y-1">
        {(engine?.activation_reason ?? []).map((r, i) => (
          <p key={i} className="text-[10px] text-gray-500 flex items-start gap-1.5">
            <span className="flex-shrink-0 mt-px" style={{ color }}>▸</span>{r}
          </p>
        ))}
      </div>

      {/* Confidence bar */}
      <div className="h-1 rounded-full" style={{ background: "#1a1a2e" }}>
        <div
          className="h-1 rounded-full transition-all duration-500"
          style={{ width: `${conf}%`, background: color }}
        />
      </div>

      {/* Description */}
      {engine?.strategy_description && (
        <p className="text-[10px] text-gray-600 italic border-t border-gray-800 pt-2 mt-1">
          {engine.strategy_description}
        </p>
      )}
    </div>
  );
}

// ─── C. Daily Decision Block ────────────────────────────────────────────────

interface Decision {
  title: string; sub: string; emoji: string;
  color: string; bg: string; border: string;
}

function getDecision(
  engine: RegimeEngine | null,
  bt:     TradableStatus,
  tops:   TickerResult[],
  ms:     MarketStatus | null,
): Decision {
  if (!engine || engine.active_strategy === "NO_TRADE") {
    const isHighVol = engine?.regime === "HIGH_VOLATILITY";
    return {
      title: "PAS DE TRADE",
      sub:   isHighVol
        ? `VIX ${engine?.vix.toFixed(1)} — volatilité excessive, préserver le capital`
        : "Marché baissier — SPY sous la SMA200, aucune position longue",
      emoji: isHighVol ? "⚡" : "🐻",
      color: "#ef4444", bg: "#130404", border: "#7f1d1d",
    };
  }
  if (bt === "NON TRADABLE")
    return { title: "PAS DE TRADE", sub: "Stratégie non validée — ouvrir le Strategy Lab d'abord", emoji: "🚫", color: "#ef4444", bg: "#130404", border: "#7f1d1d" };
  if (tops.length === 0)
    return {
      title: "NO TRADE",
      sub: "Aucun setup avec edge validé aujourd'hui. Le screener détecte des setups techniques, mais aucun n'a une validation historique suffisante pour être proposé en trade.",
      emoji: "🛑",
      color: "#ef4444",
      bg: "#130404",
      border: "#7f1d1d",
    };

  const ready = tops.filter(t => t.setup_status === "READY");
  if (ms?.is_open && ready.length > 0)
    return { title: "TRADER AUJOURD'HUI", sub: `${ready.length} setup${ready.length > 1 ? "s" : ""} ${engine.strategy_name} en zone d'entrée — mode exécution actif`, emoji: "⚡", color: "#10b981", bg: "#041310", border: "#065f46" };
  if (!ms?.is_open && tops.length > 0)
    return { title: "PRÉPARER LES ORDRES", sub: `${tops.length} setup${tops.length > 1 ? "s" : ""} validé${tops.length > 1 ? "s" : ""} · Placer les ordres limite avant l'ouverture`, emoji: "📋", color: "#6366f1", bg: "#09091e", border: "#3730a3" };

  return { title: "SURVEILLER", sub: "Setups valides mais prix pas encore en zone d'entrée", emoji: "⏳", color: "#f59e0b", bg: "#120d00", border: "#92400e" };
}

function DailyDecisionBlock({ decision }: { decision: Decision }) {
  return (
    <div className="rounded-2xl p-8 text-center" style={{ background: decision.bg, border: `2px solid ${decision.border}` }}>
      <p className="text-4xl mb-3">{decision.emoji}</p>
      <p className="text-3xl font-black tracking-widest mb-2" style={{ color: decision.color }}>{decision.title}</p>
      <p className="text-sm" style={{ color: decision.color + "99" }}>{decision.sub}</p>
    </div>
  );
}

// ─── Block Reasons ────────────────────────────────────────────────────────────

function getBlockReasons(
  t:              TickerResult,
  engine:         RegimeEngine | null,
  isAlreadyTaken: boolean,
  activeCount:    number,
): string[] {
  const reasons: string[] = [];
  if (isAlreadyTaken)          reasons.push("Déjà en portefeuille");
  if (activeCount >= 3)        reasons.push("Maximum 3 positions simultanées atteint");
  if (!hasValidatedEdge(t))    reasons.push("Edge historique non validé");
  if (hasCriticalOverfit(t))   reasons.push("Overfit critique — éviter");
  // Backend rejection reason (highest priority — most specific)
  if (t.tradable === false && t.rejection_reason)
    reasons.push(t.rejection_reason);
  if (!engine?.can_trade)      reasons.push(`Stratégie inactive : ${engine?.active_strategy ?? "NO_TRADE"}`);
  if (t.earnings_warning)      reasons.push(`Résultats dans ${t.earnings_days}j — risque élevé`);
  if (t.risk_filters_status === "BLOCKED")
    (t.risk_filter_reasons ?? []).forEach(r => reasons.push(r));
  return reasons;
}

// ─── Trade Plan Panel ────────────────────────────────────────────────────────

function TradePlanPanel({
  t, engine, bt, onClose, isAlreadyTaken, activeCount, onTakeTrade,
}: {
  t:              TickerResult;
  engine:         RegimeEngine | null;
  bt:             TradableStatus;
  onClose:        () => void;
  isAlreadyTaken: boolean;
  activeCount:    number;
  onTakeTrade:    () => void;
}) {
  const ps   = posSize(t);
  const exec = execBadge(t);
  const fd   = t.final_decision ?? "WAIT";
  const blockReasons = getBlockReasons(t, engine, isAlreadyTaken, activeCount);
  const isBlocked    = blockReasons.length > 0;

  const verdict =
    fd === "SKIP" && t.risk_filters_status === "BLOCKED"
      ? `Ignorer — filtre risque BLOQUÉ (${(t.risk_filter_reasons ?? [])[0] ?? "risque fondamental"})` :
    fd === "SKIP" && bt === "NON TRADABLE"
      ? "Ignorer — stratégie non validée (ouvrir le Strategy Lab)" :
    fd === "SKIP" && !engine?.can_trade
      ? `Ignorer — régime de marché défavorable (${engine?.regime_label ?? "inconnu"})` :
    fd === "SKIP"
      ? "Ignorer — setup invalide ou R/R insuffisant" :
    fd === "BUY"
      ? `Acheter près de $${t.entry.toFixed(2)} (ordre limite)` :
    t.dist_entry_pct > 5
      ? `Attendre un repli vers $${t.entry.toFixed(2)}` :
    "Attendre — conditions pas encore totalement alignées";

  const invalidations = [
    `Le prix clôture sous le stop loss à $${t.stop_loss.toFixed(2)}`,
    t.sma50 ? `Le prix passe sous la SMA50 ($${t.sma50.toFixed(2)})` : null,
    `Le régime de marché bascule en Baissier ou Haute Volatilité`,
    t.earnings_warning ? `⚠️ Résultats dans ${t.earnings_days} jours — réduire la taille ou éviter` : null,
  ].filter(Boolean) as string[];

  const mgmt = [
    `Prendre 50% des profits au TP1 ($${t.tp1.toFixed(2)})`,
    "Déplacer le stop au point mort après TP1",
    `Laisser courir le solde jusqu'au TP2 ($${t.tp2.toFixed(2)})`,
    t.trailing_stop ? `Trailing stop activé à $${t.trailing_stop.toFixed(2)}` : null,
  ].filter(Boolean) as string[];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "rgba(0,0,0,.75)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md h-full flex flex-col"
        style={{ background: "#0a0a16", borderLeft: "1px solid #1a1a2e" }}
      >
        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 pb-2">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest">Plan de Trade</p>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-2xl font-black text-white">{t.ticker}</p>
              <span className="text-xs text-gray-500">{t.signal_type}</span>
              {engine && (
                <span className="text-[9px] px-1.5 py-0.5 rounded font-black"
                  style={{ background: engine.strategy_color + "18", color: engine.strategy_color }}>
                  {engine.strategy_emoji} {engine.active_strategy.replace("_", " ")}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 hover:text-white"
            style={{ background: "#1a1a2e" }}
          >✕</button>
        </div>

        {/* Badges */}
        <div className="flex gap-1.5 flex-wrap">
          <Pill b={techBadge(t)} />
          <Pill b={btBadge(t, bt)} />
          <Pill b={exec} />
          <span className="px-2 py-0.5 rounded text-[10px] font-black"
            style={{ background: "#1a1a2e", color: "#6b7280" }}>
            Score {decisionScore(t, engine, bt)}/100
          </span>
        </div>

        {/* ① Verdict */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-2">① Verdict</p>
          <p className="text-sm font-black text-white leading-snug">{verdict}</p>
          <p className="text-[10px] text-gray-600 mt-1.5">
            {t.dist_entry_pct > 0 ? "+" : ""}{t.dist_entry_pct.toFixed(1)}% depuis l'entrée · Secteur : {t.sector}
          </p>
        </section>

        {/* ② Orders */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-3">② Ordres à Passer</p>
          <div className="space-y-2.5">
            {[
              { label: "Achat Limite",    value: `$${t.entry.toFixed(2)}`,     color: "#6366f1" },
              { label: "Stop Loss",       value: `$${t.stop_loss.toFixed(2)}`, color: "#ef4444" },
              { label: "Objectif 1 (TP1)",value: `$${t.tp1.toFixed(2)}`,       color: "#10b981" },
              { label: "Objectif 2 (TP2)",value: `$${t.tp2.toFixed(2)}`,       color: "#34d399" },
              { label: "Taille Position", value: `${ps.shares} actions (~$${ps.value})`, color: "#f59e0b" },
              { label: "Risque $",        value: `$${ps.riskAmt} — 1% du capital`,       color: "#ef4444" },
              { label: "R / R",           value: `1 : ${t.rr_ratio.toFixed(1)}`,         color: "#10b981" },
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
          <p className="text-[9px] font-black text-red-600 uppercase tracking-widest mb-3">③ Invalidations du Setup</p>
          <ul className="space-y-2">
            {invalidations.map((inv, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                <span className="text-red-500 mt-px flex-shrink-0">✗</span>{inv}
              </li>
            ))}
          </ul>
        </section>

        {/* ④ Trade Management */}
        <section className="rounded-xl p-4" style={{ background: "#07070f", border: "1px solid #10b98130" }}>
          <p className="text-[9px] font-black text-emerald-600 uppercase tracking-widest mb-3">④ Gestion du Trade</p>
          <ul className="space-y-2">
            {mgmt.map((step, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                <span className="text-emerald-500 mt-px flex-shrink-0">✓</span>{step}
              </li>
            ))}
          </ul>
        </section>

        {/* ⑤ Risk Filters */}
        {t.risk_filters_status && (
          <section className="rounded-xl p-4" style={{
            background: "#07070f",
            border: `1px solid ${t.risk_filters_status === "BLOCKED" ? "#ef444440" : t.risk_filters_status === "CAUTION" ? "#f59e0b40" : "#10b98130"}`
          }}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[9px] font-black uppercase tracking-widest"
                style={{ color: t.risk_filters_status === "BLOCKED" ? "#ef4444" : t.risk_filters_status === "CAUTION" ? "#f59e0b" : "#10b981" }}>
                ⑤ Filtres de Risque
              </p>
              <span className="text-[10px] font-black px-2 py-0.5 rounded"
                style={{
                  background: t.risk_filters_status === "BLOCKED" ? "#130404" : t.risk_filters_status === "CAUTION" ? "#120d00" : "#041310",
                  color: t.risk_filters_status === "BLOCKED" ? "#ef4444" : t.risk_filters_status === "CAUTION" ? "#f59e0b" : "#10b981",
                }}>
                {t.risk_filters_status}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-2">
              {[
                { label: "News",   val: t.news_risk   ?? "—" },
                { label: "Sector", val: t.sector_rank ?? "—" },
                { label: "VIX",    val: t.vix_risk    ?? "—" },
              ].map(row => {
                const c = row.val === "HIGH" || row.val === "WEAK" ? "#ef4444"
                        : row.val === "MEDIUM" || row.val === "NEUTRAL" ? "#f59e0b" : "#10b981";
                return (
                  <div key={row.label} className="text-center rounded-lg p-1.5" style={{ background: "#0c0c18" }}>
                    <p className="text-[8px] text-gray-700 uppercase tracking-widest">{row.label}</p>
                    <p className="text-[10px] font-black" style={{ color: c }}>{row.val}</p>
                  </div>
                );
              })}
            </div>
            {(t.risk_filter_reasons ?? []).length > 0 && (
              <ul className="space-y-1">
                {(t.risk_filter_reasons ?? []).map((r, i) => (
                  <li key={i} className="text-[10px] text-gray-500 flex items-start gap-1.5">
                    <span className="text-yellow-600 mt-px flex-shrink-0">!</span>{r}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* ⑥ Strategy Edge */}
        {t.ticker_edge_status && (
          <section className="rounded-xl p-4" style={{
            background: "#07070f",
            border: `1px solid ${
              t.ticker_edge_status === "STRONG_EDGE" ? "#16a34a40" :
              t.ticker_edge_status === "VALID_EDGE"  ? "#16a34a20" :
              t.ticker_edge_status === "NO_EDGE"     ? "#1e1e2a"   : "#92400e40"
            }`
          }}>
            <p className="text-[9px] font-black uppercase tracking-widest mb-2"
              style={{ color: t.ticker_edge_status === "STRONG_EDGE" ? "#4ade80" : t.ticker_edge_status === "VALID_EDGE" ? "#86efac" : "#6b7280" }}>
              ⑥ Strategy Edge Historique
            </p>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-[10px] font-black px-1.5 py-0.5 rounded"
                style={{
                  background: t.ticker_edge_status === "STRONG_EDGE" ? "#052e16" : t.ticker_edge_status === "VALID_EDGE" ? "#031a0d" : "#111118",
                  color: t.ticker_edge_status === "STRONG_EDGE" ? "#4ade80" : t.ticker_edge_status === "VALID_EDGE" ? "#86efac" : "#6b7280",
                }}>
                {t.ticker_edge_status === "STRONG_EDGE" ? "⚡ STRONG EDGE"
                 : t.ticker_edge_status === "VALID_EDGE" ? "✓ VALID EDGE"
                 : t.ticker_edge_status === "WEAK_EDGE"  ? "~ WEAK EDGE"
                 : t.ticker_edge_status === "OVERFITTED" ? "⚠ OVERFITTED"
                 : "— PAS D'EDGE CALCULÉ"}
              </span>
              {t.best_strategy_name && (
                <span className="text-[10px]" style={{ color: t.best_strategy_color ?? "#6b7280" }}>
                  {t.best_strategy_emoji} {t.best_strategy_name}
                </span>
              )}
            </div>
            {t.ticker_edge_status !== "NO_EDGE" && (
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: "Trades",    val: t.edge_trades   ?? "—" },
                  { label: "Win Rate",  val: t.edge_win_rate ? `${t.edge_win_rate.toFixed(0)}%` : "—" },
                  { label: "Train PF",  val: t.edge_train_pf ? t.edge_train_pf.toFixed(2) : "—" },
                  { label: "Test PF",   val: t.edge_test_pf  ? t.edge_test_pf.toFixed(2)  : "—" },
                ].map(m => (
                  <div key={m.label} className="text-center rounded-lg p-1.5" style={{ background: "#0c0c18" }}>
                    <p className="text-[8px] text-gray-700 uppercase tracking-widest">{m.label}</p>
                    <p className="text-[10px] font-black text-gray-300">{m.val}</p>
                  </div>
                ))}
              </div>
            )}
            {t.ticker_edge_status === "NO_EDGE" && (
              <p className="text-[10px] text-gray-700">
                Aucun edge historique calculé — cliquez sur ⚡ Edge dans l&apos;Advanced View pour calculer.
              </p>
            )}
            {t.overfit_warning && (
              <p className="text-[10px] text-amber-500 mt-1.5">⚠ {(t.overfit_reasons ?? [])[0]}</p>
            )}
          </section>
        )}

        {/* Earnings warning */}
        {t.earnings_warning && (
          <div className="rounded-xl px-4 py-3 flex items-center gap-2"
            style={{ background: "#120d00", border: "1px solid #92400e" }}>
            <span>⚠️</span>
            <p className="text-xs text-yellow-500">
              Résultats dans {t.earnings_days} jours — réduire la taille ou ignorer
            </p>
          </div>
        )}

        {/* ⑦ Pourquoi ce trade est bloqué */}
        {isBlocked && (
          <section className="rounded-xl p-4" style={{ background: "#0d0400", border: "1px solid #92400e60" }}>
            <p className="text-[9px] font-black text-orange-600 uppercase tracking-widest mb-3">
              ⑦ Pourquoi ce trade est bloqué
            </p>
            <ul className="space-y-2 mb-3">
              {blockReasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-orange-300">
                  <span className="text-orange-500 mt-px flex-shrink-0">▸</span>{r}
                </li>
              ))}
            </ul>
            <p className="text-[9px] text-gray-600 italic border-t border-orange-900 pt-2">
              Conditions pour débloquer : attendre que le prix revienne en zone, que le régime s'améliore ou que les résultats soient passés.
            </p>
          </section>
        )}

        </div>{/* end scrollable body */}

        {/* ── Sticky CTA — always visible ── */}
        <div className="p-4 border-t" style={{ borderColor: "#1a1a2e", background: "#0a0a16" }}>
          {isAlreadyTaken ? (
            <div className="w-full py-3 rounded-xl text-sm font-black text-center"
              style={{ background: "#0c1a10", border: "1px solid #065f46", color: "#10b981" }}>
              ✅ Déjà en portefeuille
            </div>
          ) : (
            <button
              onClick={onTakeTrade}
              className="w-full py-3 rounded-xl text-sm font-black transition-all hover:opacity-90 active:scale-95"
              style={{
                background: isBlocked
                  ? "linear-gradient(135deg, #374151, #1f2937)"
                  : "linear-gradient(135deg, #10b981, #059669)",
                color: isBlocked ? "#9ca3af" : "#fff",
                border: isBlocked ? "1px solid #4b5563" : "none",
              }}
            >
              {isBlocked ? "⚠️ Prendre quand même" : "✅ Prendre ce trade"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── D. Opportunity Card ─────────────────────────────────────────────────────

function OpportunityCard({
  t, rank, engine, bt, ms, score, onClick, isAlreadyTaken, activeCount,
}: {
  t:              TickerResult;
  rank:           number;
  engine:         RegimeEngine | null;
  bt:             TradableStatus;
  ms:             MarketStatus | null;
  score:          number;
  onClick:        () => void;
  isAlreadyTaken: boolean;
  activeCount:    number;
}) {
  const tech = techBadge(t);
  const bval = btBadge(t, bt);
  const exec = execBadge(t);
  const ps   = posSize(t);
  const blockReasons = getBlockReasons(t, engine, isAlreadyTaken, activeCount);
  const isBlocked    = blockReasons.length > 0;

  const fd = t.final_decision ?? (
    !engine?.can_trade ? "SKIP" :
    !hasValidatedEdge(t) ? "WAIT" :
    hasCriticalOverfit(t) ? "SKIP" :
    t.dist_entry_pct > 3 ? "WAIT" :
    exec.label === "READY" ? "BUY" : "WAIT"
  );
  const action = isAlreadyTaken ? "PRIS ✓"
    : fd === "BUY" ? "BUY NEAR" : fd === "SKIP" ? "SKIP" : "WAIT";
  const aColor =
    isAlreadyTaken      ? "#10b981" :
    action === "BUY NEAR" ? "#10b981" :
    action === "WAIT"     ? "#f59e0b" : "#ef4444";

  const conf      = t.confidence >= 70 ? "HIGH" : t.confidence >= 45 ? "MEDIUM" : "LOW";
  const confColor = conf === "HIGH" ? "#10b981" : conf === "MEDIUM" ? "#f59e0b" : "#ef4444";
  const isNearEntry = ms?.is_open && t.dist_entry_pct <= 1.5;

  const borderColor =
    exec.label === "READY"   ? "#065f4680" :
    exec.label === "WAIT"    ? "#92400e60" : "#1a1a2e";

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
          {isNearEntry && !isAlreadyTaken && (
            <span className="px-2 py-0.5 rounded text-[9px] font-black animate-pulse"
              style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}>
              ⚡ NEAR ENTRY
            </span>
          )}
          {isAlreadyTaken && (
            <span className="px-2 py-0.5 rounded text-[9px] font-black"
              style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}>
              ✅ DÉJÀ PRIS
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
          <div key={l.label} className="rounded-lg p-2 text-center"
            style={{ background: "#07070f", border: `1px solid ${l.color}20` }}>
            <p className="text-[8px] font-bold uppercase tracking-widest mb-1" style={{ color: l.color }}>{l.label}</p>
            <p className="text-xs font-black text-white">{l.value}</p>
          </div>
        ))}
      </div>

      {/* Edge Info */}
      {t.ticker_edge_status && (
        <div className="flex items-center gap-2 mb-2.5 px-2 py-1.5 rounded-lg flex-wrap"
          style={{
            background: hasValidatedEdge(t) ? "#040d04" : "#111118",
            border: `1px solid ${hasValidatedEdge(t) ? "#16a34a22" : "#2a2a3a"}`,
          }}>
          <span className="text-[9px] font-black text-gray-600 uppercase tracking-widest">Edge :</span>
          {t.ticker_edge_status === "STRONG_EDGE" && (
            <span className="text-[9px] font-black text-green-400">⚡ STRONG EDGE</span>
          )}
          {t.ticker_edge_status === "VALID_EDGE" && (
            <span className="text-[9px] font-black text-green-600">✓ VALID EDGE</span>
          )}
          {t.ticker_edge_status === "WEAK_EDGE" && (
            <span className="text-[9px] font-black text-yellow-500">~ WEAK EDGE</span>
          )}
          {t.ticker_edge_status === "NO_EDGE" && (
            <span className="text-[9px] font-black text-gray-500">○ EDGE NON VALIDÉ</span>
          )}
          {t.ticker_edge_status === "OVERFITTED" && (
            <span className="text-[9px] font-black text-amber-400">⚠ OVERFIT — ÉVITER</span>
          )}
          {t.best_strategy_name && (
            <span className="text-[9px]" style={{ color: t.best_strategy_color ?? "#6b7280" }}>
              {t.best_strategy_emoji} {t.best_strategy_name}
            </span>
          )}
          {t.edge_score && t.edge_score > 0 && (
            <span className="ml-auto text-[9px] font-black text-gray-600">
              Score edge: <strong className="text-gray-400">{t.edge_score}/100</strong>
            </span>
          )}
          {t.overfit_warning && (
            <span className="text-[9px] text-amber-400">⚠ overfit</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center gap-4 text-[10px] text-gray-700 flex-wrap">
        <span>R/R <strong className="text-gray-500">1:{t.rr_ratio.toFixed(1)}</strong></span>
        <span>Size <strong className="text-gray-500">{ps.pct}% cap.</strong></span>
        <span>Conf <strong style={{ color: confColor }}>{conf}</strong></span>
        {isBlocked && !isAlreadyTaken && (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-black" style={{ background: "#130a00", color: "#f97316" }}>
            🚫 BLOQUÉ: {blockReasons[0]}
          </span>
        )}
        {!isBlocked && t.risk_filters_status === "CAUTION" && (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-black" style={{ background: "#120d00", color: "#f59e0b" }}>⚠ CAUTION</span>
        )}
        <span className="ml-auto text-[9px] text-gray-700">Voir le plan →</span>
      </div>
    </div>
  );
}

// ─── E. Risk Control Block ───────────────────────────────────────────────────

function RiskControlBlock({ tops, engine }: { tops: TickerResult[]; engine: RegimeEngine | null }) {
  const active  = tops.filter(t => execBadge(t).label !== "INVALID");
  const avgRisk = active.length
    ? (active.reduce((a, t) => a + t.risk_now_pct, 0) / active.length).toFixed(1)
    : "0";
  const maxExp  = Math.min(active.length * 5, 20);
  const riskOk  = parseFloat(avgRisk) <= 5 && maxExp <= 20;

  return (
    <div className="rounded-2xl p-5" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest">⚖️ Contrôle du Risque</p>
        <span className="px-2.5 py-1 rounded-lg text-[10px] font-black"
          style={{
            background: riskOk ? "#041310" : "#130404",
            color:      riskOk ? "#10b981" : "#ef4444",
            border:     `1px solid ${riskOk ? "#065f46" : "#7f1d1d"}`,
          }}>
          {riskOk ? "RISQUE OK ✓" : "RISQUE ÉLEVÉ ⚠"}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Capital",        value: `$${SIM_CAPITAL.toLocaleString()}`,        color: "#6b7280", sub: "Simulé" },
          { label: "Risque / Trade", value: `$${(SIM_CAPITAL * RISK_PCT).toFixed(0)}`, color: "#f59e0b", sub: "1% perte max" },
          { label: "Setups Actifs", value: active.length,                              color: "#6366f1", sub: "Positions" },
          { label: "Exposition Max", value: `${maxExp}%`,                              color: riskOk ? "#10b981" : "#ef4444", sub: "5% par trade" },
        ].map(s => (
          <div key={s.label} className="rounded-xl p-3 text-center"
            style={{ background: "#07070f", border: `1px solid ${s.color}20` }}>
            <p className="text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: s.color }}>{s.label}</p>
            <p className="text-xl font-black text-white">{s.value}</p>
            <p className="text-[9px] text-gray-700 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Command Center ──────────────────────────────────────────────────────────

export function CommandCenter({
  data,
  regime,
  backtestStatus,
  loading,
  onRefresh,
  onRefreshPrices,
  onAdvancedView,
  onGoToLab,
}: {
  data:           TickerResult[];
  regime:         MarketRegime | null;
  backtestStatus: TradableStatus;
  loading:        boolean;
  onRefresh:      () => void;
  onRefreshPrices: () => void;
  onAdvancedView: () => void;
  onGoToLab:      () => void;
}) {
  const [ms,          setMs]          = useState<MarketStatus | null>(null);
  const [engine,      setEngine]      = useState<RegimeEngine | null>(null);
  const [selected,    setSelected]    = useState<TickerResult | null>(null);
  const [takingTrade, setTakingTrade] = useState<TickerResult | null>(null);

  const { activeTrades, isTickerActive } = useJournal();

  useEffect(() => {
    const fetchMs = () =>
      fetch(`${API_URL}/api/market-status`).then(r => r.json()).then(setMs).catch(() => null);
    const fetchEngine = () =>
      fetch(`${API_URL}/api/regime-engine`).then(r => r.json()).then(setEngine).catch(() => null);

    fetchMs();
    fetchEngine();
    const id = setInterval(fetchMs, 60_000);
    return () => clearInterval(id);
  }, []);

  // ── Filter opportunities by active strategy ───────────────────────────────
  const signalFilter: string[] = engine?.signal_filter ?? [];

  const scored = data
    .filter(r => r.rr_ratio >= 1.5)
    .filter(r => isTradeCandidate(r, engine, signalFilter))
    .map(r => ({ ...r, _score: decisionScore(r, engine, backtestStatus) }))
    .sort((a, b) => b._score - a._score);

  // TOP 3 ONLY — one clear action per day
  const topOpps = scored.slice(0, 3);

  const technicalWatchlist = data
    .filter(r => isTechnicalWatchlistCandidate(r, engine, signalFilter))
    .map(r => ({ ...r, _score: decisionScore(r, engine, backtestStatus) }))
    .sort((a, b) => b._score - a._score)
    .slice(0, 8);

  const decision = getDecision(engine, backtestStatus, topOpps, ms);

  const cannotTrade = !engine?.can_trade || backtestStatus === "NON TRADABLE";

  return (
    <div className="space-y-3">

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold text-gray-700 uppercase tracking-widest">
          {data.length} setups analysés · {topOpps.length} setup{topOpps.length > 1 ? "s" : ""} avec edge validé
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefreshPrices}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#10b981" }}
          >
            Prix seulement
          </button>
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
            Advanced →
          </button>
        </div>
      </div>

      {/* A — Regime Bar */}
      <RegimeBar engine={engine} ms={ms} />

      {/* B + C — Strategy + Decision (two columns on md+) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ActiveStrategyBlock engine={engine} />
        <DailyDecisionBlock  decision={decision} />
      </div>

      {/* D — Top Opportunities */}
      {topOpps.length > 0 && (
        <div>
          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2 px-1">
            🎯 Meilleures actions à trader aujourd'hui — edge validé uniquement
          </p>
          <div className="space-y-3">
            {topOpps.map((t, i) => (
              <OpportunityCard
                key={t.ticker}
                t={t}
                rank={i + 1}
                engine={engine}
                bt={backtestStatus}
                ms={ms}
                score={(t as any)._score}
                onClick={() => setSelected(t)}
                isAlreadyTaken={isTickerActive(t.ticker)}
                activeCount={activeTrades.length}
              />
            ))}
          </div>
        </div>
      )}

      {/* No trade / technical watchlist */}
      {(topOpps.length === 0 || cannotTrade) && (
        <div className="rounded-xl px-5 py-4" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-2">
            🛑 NO TRADE — aucun setup avec edge validé aujourd'hui
          </p>
          <p className="text-[10px] text-gray-500 mb-3">
            Le screener détecte des setups techniques, mais aucun n&apos;a une validation historique suffisante pour être proposé en trade.
          </p>
          {technicalWatchlist.length > 0 && (
            <>
              <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-2">
                👁 Watchlist technique — à surveiller, pas trade
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {technicalWatchlist.map(t => (
                  <button
                    key={t.ticker}
                    className="text-left px-3 py-2 rounded-lg transition-colors hover:bg-white/[0.03]"
                    style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
                    onClick={() => setSelected(t)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-black text-white">{t.ticker}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded font-black" style={{ background: "#052e16", color: "#4ade80" }}>
                          Technique OK
                        </span>
                        <span
                          className="text-[9px] px-1.5 py-0.5 rounded font-black"
                          style={{
                            background: t.ticker_edge_status === "OVERFITTED" ? "#1c1000" : "#111118",
                            color: t.ticker_edge_status === "OVERFITTED" ? "#f59e0b" : "#9ca3af",
                          }}
                        >
                          {t.ticker_edge_status === "OVERFITTED" ? "Overfit — éviter" : "Edge non validé"}
                        </span>
                      </div>
                      <span className="text-xs font-black text-gray-400">{t.score}</span>
                    </div>
                    <p className="text-[10px] text-gray-600 mt-1">
                      {t.signal_type} · {t.setup_grade} · final {t.final_decision ?? "WAIT"}
                    </p>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* E — Risk Control */}
      <RiskControlBlock tops={topOpps} engine={engine} />

      {/* Strategy Lab link */}
      <div className="flex items-center justify-between px-4 py-3 rounded-xl"
        style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
        <div>
          <p className="text-[9px] text-gray-700 uppercase tracking-widest">Validation Stratégie</p>
          <p className="text-xs font-black" style={{
            color: backtestStatus === "TRADABLE" ? "#10b981" : backtestStatus === "À CONFIRMER" ? "#f59e0b" : "#ef4444"
          }}>
            {backtestStatus ?? "Non testé"} · Lancer le Strategy Lab pour valider
          </p>
        </div>
        <button
          onClick={onGoToLab}
          className="text-[10px] font-bold text-gray-600 hover:text-gray-400 transition-colors"
        >
          Ouvrir le Lab →
        </button>
      </div>

      {/* Trade Plan Panel */}
      {selected && (
        <TradePlanPanel
          t={selected}
          engine={engine}
          bt={backtestStatus}
          onClose={() => setSelected(null)}
          isAlreadyTaken={isTickerActive(selected.ticker)}
          activeCount={activeTrades.length}
          onTakeTrade={() => { setTakingTrade(selected); }}
        />
      )}

      {takingTrade && (
        <TakeTradeModal
          t={takingTrade}
          engine={engine}
          onClose={() => { setTakingTrade(null); setSelected(null); }}
        />
      )}
    </div>
  );
}
