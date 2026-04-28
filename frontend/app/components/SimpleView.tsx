"use client";

import { TickerResult, MarketRegime } from "../types";

type TradableStatus = "TRADABLE" | "À CONFIRMER" | "NON TRADABLE" | null;

// ── Helpers ──────────────────────────────────────────────────────────────────

function actionPhrase(r: TickerResult): string {
  if (r.dist_entry_pct > 3)   return "Wait — too extended from entry";
  if (r.risk_now_pct > 8)     return "Skip — risk too high";
  if (r.setup_grade === "A+") return `Buy near $${r.entry.toFixed(2)}`;
  if (r.setup_grade === "A")  return `Buy near $${r.entry.toFixed(2)}`;
  return `Consider entry near $${r.entry.toFixed(2)}`;
}

function confidenceLabel(r: TickerResult, backtestStatus: TradableStatus): {
  label: string; color: string; bg: string;
} {
  if (backtestStatus === "NON TRADABLE")
    return { label: "NOT PROFITABLE", color: "#f87171", bg: "#1a0505" };
  if (backtestStatus === "TRADABLE" && r.setup_grade === "A+")
    return { label: "VALIDATED ✓",    color: "#4ade80", bg: "#031a0d" };
  if (backtestStatus === "TRADABLE")
    return { label: "VALIDATED ✓",    color: "#4ade80", bg: "#031a0d" };
  if (backtestStatus === "À CONFIRMER")
    return { label: "WEAK DATA",      color: "#fbbf24", bg: "#1a1000" };
  return { label: "WEAK DATA",        color: "#fbbf24", bg: "#1a1000" };
}

// ── Decision Banner ───────────────────────────────────────────────────────────

function DecisionBanner({
  regime,
  backtestStatus,
  topSetups,
}: {
  regime: MarketRegime | null;
  backtestStatus: TradableStatus;
  topSetups: TickerResult[];
}) {
  const isNonTradable  = backtestStatus === "NON TRADABLE";
  const isBearMarket   = regime?.regime === "BEAR";
  const noSetups       = topSetups.length === 0;
  const dataUnavail    = regime?.data_ok === false;

  const canTrade = !isNonTradable && !isBearMarket && !noSetups && !dataUnavail && regime !== null;

  if (isNonTradable) {
    return (
      <div className="rounded-2xl p-6 text-center mb-6"
        style={{ background: "#1a0505", border: "2px solid #7f1d1d" }}>
        <p className="text-5xl mb-3">🚫</p>
        <p className="text-2xl font-black text-red-400 tracking-widest mb-2">NO TRADE TODAY</p>
        <p className="text-sm text-red-600">Strategy not profitable — backtesting failed</p>
        <p className="text-xs text-gray-600 mt-1">Go to Strategy Lab to find a validated strategy</p>
      </div>
    );
  }

  if (isBearMarket) {
    return (
      <div className="rounded-2xl p-6 text-center mb-6"
        style={{ background: "#1a0505", border: "2px solid #7f1d1d" }}>
        <p className="text-5xl mb-3">🐻</p>
        <p className="text-2xl font-black text-red-400 tracking-widest mb-2">NO TRADE TODAY</p>
        <p className="text-sm text-red-600">SPY below SMA200 — Bear market conditions</p>
        <p className="text-xs text-gray-600 mt-1">Reduce exposure — wait for market to recover</p>
      </div>
    );
  }

  if (dataUnavail || !regime) {
    return (
      <div className="rounded-2xl p-6 text-center mb-6"
        style={{ background: "#1a0a00", border: "2px solid #92400e" }}>
        <p className="text-5xl mb-3">⚠️</p>
        <p className="text-2xl font-black text-yellow-400 tracking-widest mb-2">DATA UNAVAILABLE</p>
        <p className="text-sm text-yellow-600">Market data cannot be verified — trade with caution</p>
      </div>
    );
  }

  if (noSetups) {
    return (
      <div className="rounded-2xl p-6 text-center mb-6"
        style={{ background: "#0d1a0d", border: "2px solid #16a34a44" }}>
        <p className="text-5xl mb-3">👀</p>
        <p className="text-2xl font-black text-gray-400 tracking-widest mb-2">WATCH & WAIT</p>
        <p className="text-sm text-gray-600">No A+/A setups available today — run the screener</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl p-6 text-center mb-6"
      style={{ background: "#031a0d", border: "2px solid #16a34a" }}>
      <p className="text-5xl mb-3">🟢</p>
      <p className="text-3xl font-black text-green-400 tracking-widest mb-2">TRADE TODAY</p>
      <p className="text-sm text-gray-400">
        {regime.regime === "BULL" ? "Bull market · " : ""}
        {topSetups.length} setup{topSetups.length > 1 ? "s" : ""} available
        {backtestStatus === "TRADABLE" ? " · Strategy validated ✓" : " · Weak data ⚠️"}
      </p>
    </div>
  );
}

// ── Setup Card ────────────────────────────────────────────────────────────────

function SetupCard({
  r,
  backtestStatus,
  rank,
}: {
  r: TickerResult;
  backtestStatus: TradableStatus;
  rank: number;
}) {
  const conf    = confidenceLabel(r, backtestStatus);
  const phrase  = actionPhrase(r);
  const gradeColor = r.setup_grade === "A+" ? "#4ade80" : r.setup_grade === "A" ? "#bef264" : "#fde047";

  return (
    <div className="rounded-2xl p-5"
      style={{ background: "#0d0d18", border: `1px solid ${gradeColor}33` }}>

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-gray-600">#{rank}</span>
          <span className="text-xl font-black text-white">{r.ticker}</span>
          <span className="px-2 py-0.5 rounded text-[10px] font-black"
            style={{ background: `${gradeColor}22`, color: gradeColor, border: `1px solid ${gradeColor}44` }}>
            {r.setup_grade}
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-medium"
            style={{ background: "#1e1e2a", color: "#9ca3af" }}>
            {r.signal_type}
          </span>
        </div>
        {/* Confidence badge */}
        <span className="px-2 py-0.5 rounded text-[10px] font-black"
          style={{ background: conf.bg, color: conf.color, border: `1px solid ${conf.color}33` }}>
          {conf.label}
        </span>
      </div>

      {/* Levels */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { label: "ENTRY",    value: `$${r.entry.toFixed(2)}`,     color: "#818cf8" },
          { label: "STOP",     value: `$${r.stop_loss.toFixed(2)}`, color: "#f87171" },
          { label: "TARGET",   value: `$${r.tp2.toFixed(2)}`,       color: "#4ade80" },
          { label: "R/R",      value: `1:${r.rr_ratio.toFixed(1)}`, color: "#34d399" },
        ].map(l => (
          <div key={l.label} className="rounded-xl p-3 text-center"
            style={{ background: "#070710", border: `1px solid ${l.color}22` }}>
            <p className="text-[9px] font-bold mb-1 uppercase tracking-widest" style={{ color: l.color }}>{l.label}</p>
            <p className="text-sm font-black text-white">{l.value}</p>
          </div>
        ))}
      </div>

      {/* Action phrase */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl"
        style={{ background: "#070710", border: "1px solid #1e1e2a" }}>
        <span className="text-sm">
          {phrase.startsWith("Buy") ? "🎯" : phrase.startsWith("Wait") ? "⏳" : phrase.startsWith("Skip") ? "❌" : "💡"}
        </span>
        <span className="text-xs font-bold text-gray-300">{phrase}</span>
        <span className="ml-auto text-[10px] text-gray-600">
          Dist. entry: {r.dist_entry_pct > 0 ? "+" : ""}{r.dist_entry_pct.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

// ── Risk Panel ────────────────────────────────────────────────────────────────

function RiskPanel({ data }: { data: TickerResult[] }) {
  const topSetups   = data.filter(r => r.setup_grade === "A+" || r.setup_grade === "A").slice(0, 3);
  const avgRisk     = topSetups.length
    ? (topSetups.reduce((a, r) => a + r.risk_now_pct, 0) / topSetups.length).toFixed(1)
    : "—";
  const maxPositions = topSetups.length;

  return (
    <div className="rounded-2xl p-5 mt-4"
      style={{ background: "#0d0d18", border: "1px solid #f59e0b22" }}>
      <p className="text-[10px] font-black text-yellow-500 uppercase tracking-widest mb-4">⚠️ Gestion du Risque</p>
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Risque / Trade", value: `${avgRisk}%`,   color: "#f59e0b", sub: "Basé sur SL actuel" },
          { label: "Positions Max",  value: maxPositions,     color: "#818cf8", sub: "Setups disponibles" },
          { label: "Exposure Max",   value: `${Math.min(maxPositions * 5, 20)}%`, color: "#34d399", sub: "5% par position" },
        ].map(s => (
          <div key={s.label} className="rounded-xl p-3 text-center"
            style={{ background: "#070710", border: `1px solid ${s.color}22` }}>
            <p className="text-[10px] font-bold mb-1 uppercase tracking-widest" style={{ color: s.color }}>{s.label}</p>
            <p className="text-xl font-black text-white">{s.value}</p>
            <p className="text-[9px] text-gray-600 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Simple View ───────────────────────────────────────────────────────────────

export function SimpleView({
  data,
  regime,
  backtestStatus,
  loading,
  onRefresh,
  onAdvanced,
}: {
  data: TickerResult[];
  regime: MarketRegime | null;
  backtestStatus: TradableStatus;
  loading: boolean;
  onRefresh: () => void;
  onAdvanced: () => void;
}) {
  const isNonTradable = backtestStatus === "NON TRADABLE";
  const isBear        = regime?.regime === "BEAR";

  // Top 3 setups — A+ en premier, puis A
  const topSetups = data
    .filter(r => (r.setup_grade === "A+" || r.setup_grade === "A") && !isNonTradable && !isBear)
    .sort((a, b) => {
      const gradeScore = (g: string) => g === "A+" ? 2 : g === "A" ? 1 : 0;
      return gradeScore(b.setup_grade) - gradeScore(a.setup_grade) || b.score - a.score;
    })
    .slice(0, 3);

  return (
    <div className="space-y-2">

      {/* Toolbar simple */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {/* SPY pill */}
          {regime && regime.data_ok !== false && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
              <span className="w-1.5 h-1.5 rounded-full"
                style={{ background: regime.regime === "BULL" ? "#4ade80" : regime.regime === "BEAR" ? "#f87171" : "#fde047" }} />
              <span className="text-gray-400">SPY</span>
              <span className="font-bold text-white">${regime.spy_price.toFixed(2)}</span>
              <span style={{ color: regime.spy_perf_1m >= 0 ? "#4ade80" : "#f87171" }}>
                {regime.spy_perf_1m >= 0 ? "+" : ""}{regime.spy_perf_1m.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40"
            style={{ background: "#1e1e3a", border: "1px solid #2a2a4a", color: "#818cf8" }}>
            {loading ? "⟳ Analyse..." : "⟳ Rafraîchir"}
          </button>
          <button
            onClick={onAdvanced}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#4b5563" }}>
            Advanced View →
          </button>
        </div>
      </div>

      {/* Section 1 — Decision */}
      <DecisionBanner regime={regime} backtestStatus={backtestStatus} topSetups={topSetups} />

      {/* Section 2 — Top setups */}
      {topSetups.length > 0 && (
        <div className="space-y-3">
          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest px-1">
            🎯 Top {topSetups.length} Setup{topSetups.length > 1 ? "s" : ""} du Jour
          </p>
          {topSetups.map((r, i) => (
            <SetupCard key={r.ticker} r={r} backtestStatus={backtestStatus} rank={i + 1} />
          ))}
        </div>
      )}

      {/* Section 3 — Risk */}
      {topSetups.length > 0 && <RiskPanel data={data} />}

      {/* Si NON TRADABLE → message */}
      {isNonTradable && (
        <div className="rounded-2xl p-5 text-center"
          style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
          <p className="text-sm text-gray-600">
            Ouvre le <strong className="text-gray-400">Strategy Lab</strong> pour trouver une stratégie validée,
            puis reviens ici.
          </p>
        </div>
      )}
    </div>
  );
}
