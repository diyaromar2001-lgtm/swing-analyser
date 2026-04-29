"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { TickerResult, MarketRegime } from "../types";
import { ScreenerTable } from "./ScreenerTable";
import { Top5Cards } from "./Top5Cards";
import { DynamicCategories } from "./DynamicCategories";
import { BacktestView } from "./BacktestView";
import { StrategyLab } from "./StrategyLab";
import { ApiStatusDot, ApiStatusPanel } from "./ApiStatus";
import { MarketContext } from "./MarketContext";
import { SignalTracker } from "./SignalTracker";
import { CommandCenter } from "./CommandCenter";
import { TradeJournal } from "./TradeJournal";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SECTORS = [
  "Technology", "Healthcare", "Financials",
  "Consumer Discretionary", "Consumer Staples",
  "Energy", "Industrials", "Materials",
  "Communication", "Real Estate", "Utilities",
  "Growth / Innovation",
];
const SIGNALS = ["Momentum", "Pullback", "Breakout"];
const GRADES  = ["A+", "A", "B"] as const;

export type Strategy = "standard" | "conservative";

// ── Market Regime Banner ────────────────────────────────────────────────────

function MarketRegimeBanner({ regime }: { regime: MarketRegime | null }) {
  if (!regime) return null;

  // Données indisponibles → bannière d'avertissement explicite
  if (regime.data_ok === false) {
    return (
      <div className="rounded-xl px-4 py-3 mb-5 flex items-center gap-3 flex-wrap"
        style={{ background: "#1a0a0a", border: "1px solid #7f1d1d66" }}>
        <span className="text-sm">⚠️</span>
        <span className="text-xs font-black text-red-400 uppercase tracking-widest">Données marché indisponibles</span>
        {regime.data_warning && (
          <span className="text-xs text-red-600">{regime.data_warning}</span>
        )}
        <span className="ml-auto text-xs text-red-500 font-bold">
          Les signaux A+ ne peuvent pas être validés — vérifiez la connexion
        </span>
      </div>
    );
  }

  const cfg: Record<string, { bg: string; border: string; dot: string; label: string; emoji: string }> = {
    BULL:    { bg: "#031a0d", border: "#16a34a44", dot: "#4ade80", label: "Marché Haussier",  emoji: "🟢" },
    RANGE:   { bg: "#1a1400", border: "#ca8a0444", dot: "#fde047", label: "Marché Latéral",   emoji: "🟡" },
    BEAR:    { bg: "#1f0909", border: "#991b1b44", dot: "#f87171", label: "Marché Baissier",  emoji: "🔴" },
    UNKNOWN: { bg: "#0d0d18", border: "#1e1e2a",   dot: "#6b7280", label: "Régime Inconnu",   emoji: "⚪" },
  };

  const c = cfg[regime.regime] ?? cfg["UNKNOWN"];

  return (
    <div
      className="rounded-xl px-4 py-3 mb-5 flex items-center gap-4 flex-wrap"
      style={{ background: c.bg, border: `1px solid ${c.border}` }}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm">{c.emoji}</span>
        <span className="text-xs font-black text-white uppercase tracking-widest">{c.label}</span>
        <span
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ background: c.dot }}
        />
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
        <span>SPY <strong className="text-white">${regime.spy_price.toFixed(2)}</strong></span>
        <span>SMA50 <strong className="text-gray-300">${regime.spy_sma50.toFixed(2)}</strong></span>
        <span>SMA200 <strong className="text-gray-300">${regime.spy_sma200.toFixed(2)}</strong></span>
        <span>
          RSI{" "}
          <strong style={{ color: regime.spy_rsi >= 50 && regime.spy_rsi <= 70 ? "#4ade80" : regime.spy_rsi > 70 ? "#ef4444" : "#9ca3af" }}>
            {regime.spy_rsi.toFixed(1)}
          </strong>
        </span>
        <span>
          1m{" "}
          <strong style={{ color: regime.spy_perf_1m >= 0 ? "#4ade80" : "#ef4444" }}>
            {regime.spy_perf_1m >= 0 ? "+" : ""}{regime.spy_perf_1m.toFixed(1)}%
          </strong>
        </span>
      </div>

      {regime.regime === "BEAR" && (
        <span className="ml-auto text-xs font-bold text-red-400 bg-red-950 px-2 py-0.5 rounded">
          ⚠️ Réduire exposition — marché sous SMA200
        </span>
      )}
    </div>
  );
}

// ── Global Status Bar ───────────────────────────────────────────────────────

type TradableStatus = "TRADABLE" | "À CONFIRMER" | "NON TRADABLE" | null;

function GlobalStatusBar({
  regime,
  backtestStatus,
}: {
  regime: MarketRegime | null;
  backtestStatus: TradableStatus;
}) {
  const marketOk = regime?.data_ok !== false && !!regime;
  const marketLabel = !regime ? "—"
    : regime.data_ok === false ? "Indisponible"
    : regime.regime === "BULL" ? "Haussier" : regime.regime === "BEAR" ? "Baissier" : "Latéral";
  const marketColor = !regime ? "#6b7280"
    : regime.data_ok === false ? "#ef4444"
    : regime.regime === "BULL" ? "#4ade80" : regime.regime === "BEAR" ? "#f87171" : "#fde047";

  const btColor = backtestStatus === "TRADABLE" ? "#4ade80"
    : backtestStatus === "À CONFIRMER" ? "#fde047"
    : backtestStatus === "NON TRADABLE" ? "#ef4444"
    : "#6b7280";
  const btLabel = backtestStatus ?? "Non testé";

  return (
    <div className="flex items-center gap-3 px-4 py-2 rounded-xl mb-4 flex-wrap"
      style={{ background: "#0a0a14", border: "1px solid #1e1e2a" }}>
      <span className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Statut Système</span>
      <div className="h-3 w-px" style={{ background: "#1e1e2a" }} />

      {/* Données marché */}
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: marketColor }} />
        <span className="text-[10px] text-gray-600">Données marché :</span>
        <span className="text-[10px] font-bold" style={{ color: marketColor }}>{marketLabel}</span>
      </div>

      <div className="h-3 w-px" style={{ background: "#1e1e2a" }} />

      {/* Backtest */}
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: btColor }} />
        <span className="text-[10px] text-gray-600">Stratégie validée :</span>
        <span className="text-[10px] font-bold" style={{ color: btColor }}>{btLabel}</span>
      </div>

      {backtestStatus === "NON TRADABLE" && (
        <span className="ml-auto text-[10px] text-red-400 font-bold">
          ⚠️ Stratégie non validée — signaux théoriques uniquement
        </span>
      )}
    </div>
  );
}

// ── Dashboard ───────────────────────────────────────────────────────────────

export function Dashboard({ initialData }: { initialData: TickerResult[] }) {
  const [data, setData]             = useState(initialData);
  const [loading, setLoading]       = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [strategy, setStrategy]     = useState<Strategy>("standard");
  const [regime, setRegime]         = useState<MarketRegime | null>(null);

  // Filtres
  const [search, setSearch]         = useState("");
  const [sector, setSector]         = useState("");
  const [signal, setSignal]         = useState("");
  const [grade, setGrade]           = useState("");
  const [minScore, setMinScore]     = useState(0);
  const [excludeEarnings, setExcludeEarnings] = useState(false);
  const [view, setView]             = useState<"table" | "dynamic" | "backtest" | "lab" | "signals" | "trades">("table");
  const [uiMode, setUiMode]         = useState<"simple" | "pro">(() => {
    if (typeof window === "undefined") return "simple";
    return (localStorage.getItem("swing_ui_mode") as "simple" | "pro") ?? "simple";
  });

  // Strategy Lab
  const [activeLabKey, setActiveLabKey] = useState<string>("");
  const [backtestStatus, setBacktestStatus] = useState<TradableStatus>(() => {
    if (typeof window === "undefined") return null;
    return (localStorage.getItem("swing_backtest_status") as TradableStatus) ?? null;
  });
  // API Status modal
  const [showApiStatus, setShowApiStatus] = useState(false);

  // Chargement initial des données au montage (client-side)
  useEffect(() => {
    if (initialData.length === 0) {
      refresh();
    }
    fetch(`${API_URL}/api/market-regime`)
      .then(r => r.json())
      .then(setRegime)
      .catch(() => null);
  }, []);

  const refresh = useCallback(async (strat?: Strategy, excEarnings?: boolean) => {
    setLoading(true);
    const s  = strat      ?? strategy;
    const ee = excEarnings ?? excludeEarnings;
    try {
      // Vider le cache backend pour obtenir les prix frais
      await fetch(`${API_URL}/api/clear-cache`, { method: "POST" }).catch(() => {});

      const [screenerRes, regimeRes] = await Promise.all([
        fetch(`${API_URL}/api/screener?strategy=${s}&exclude_earnings=${ee}`, { cache: "no-store" }),
        fetch(`${API_URL}/api/market-regime`),
      ]);
      const json = await screenerRes.json();
      setData(json);
      setLastUpdate(new Date());
      const regimeJson = await regimeRes.json();
      setRegime(regimeJson);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [strategy]);

  const switchStrategy = useCallback((s: Strategy) => {
    setStrategy(s);
    refresh(s, excludeEarnings);
  }, [refresh, excludeEarnings]);

  const toggleEarnings = useCallback((val: boolean) => {
    setExcludeEarnings(val);
    refresh(strategy, val);
  }, [refresh, strategy]);

  const handleUseLabStrategy = useCallback((
    screenerStrategy: Strategy,
    screenerSignal: string,
    labKey: string,
    tradableStatus?: TradableStatus,
  ) => {
    setActiveLabKey(labKey);
    setStrategy(screenerStrategy);
    setSignal(screenerSignal);
    refresh(screenerStrategy);
    setView("table");
    if (tradableStatus) {
      setBacktestStatus(tradableStatus);
      localStorage.setItem("swing_backtest_status", tradableStatus);
    }
  }, [refresh]);

  const filtered = useMemo(() => {
    return data.filter(r => {
      if (search   && !r.ticker.toLowerCase().includes(search.toLowerCase())) return false;
      if (sector   && r.sector !== sector)       return false;
      if (signal   && r.signal_type !== signal)  return false;
      if (grade    && r.setup_grade !== grade)   return false;
      if (minScore > 0 && r.score < minScore)    return false;
      return true;
    });
  }, [data, search, sector, signal, grade, minScore]);

  const stats = useMemo(() => {
    const aPlus   = data.filter(r => r.setup_grade === "A+").length;
    const a       = data.filter(r => r.setup_grade === "A").length;
    const b       = data.filter(r => r.setup_grade === "B").length;
    const avgScore = data.length
      ? Math.round(data.reduce((acc, r) => acc + r.score, 0) / data.length)
      : 0;
    const avgRR = data.length
      ? Math.round(data.reduce((acc, r) => acc + r.rr_ratio, 0) / data.length * 10) / 10
      : 0;
    const avgConf = data.length
      ? Math.round(data.reduce((acc, r) => acc + r.confidence, 0) / data.length)
      : 0;
    return { aPlus, a, b, avgScore, avgRR, avgConf };
  }, [data]);

  const FilterBtn = ({
    label, active, onClick, color,
  }: { label: string; active: boolean; onClick: () => void; color?: string }) => (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
      style={{
        background: active ? (color ? `${color}22` : "#1e1e3a") : "#0d0d18",
        border:     `1px solid ${active ? (color ?? "#4f46e5") : "#1e1e2a"}`,
        color:      active ? (color ?? "#818cf8") : "#4b5563",
      }}
    >
      {label}
    </button>
  );

  const gradeColors: Record<string, string> = {
    "A+": "#4ade80",
    "A":  "#bef264",
    "B":  "#fde047",
  };

  // Écran de chargement initial
  if (loading && data.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#070710" }}>
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center gap-3">
            <svg className="animate-spin h-6 w-6 text-indigo-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <p className="text-white font-bold text-lg">Analyse en cours…</p>
          </div>
          <p className="text-gray-600 text-sm">Récupération des données marché · 20-30 sec</p>
          <div className="flex gap-1 justify-center mt-2">
            {[0,1,2,3,4].map(i => (
              <div key={i} className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"
                style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-5" style={{ background: "#070710" }}>
      {showApiStatus && <ApiStatusPanel onClose={() => setShowApiStatus(false)} />}

      {/* HEADER */}
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-2 h-8 rounded-full" style={{ background: "linear-gradient(to bottom, #818cf8, #10b981)" }} />
            <h1 className="text-2xl font-black text-white tracking-tight">
              {uiMode === "simple" ? "Command Center" : "Advanced View"}
            </h1>
          </div>
          <p className="text-gray-600 text-xs ml-5" suppressHydrationWarning>
            {data.length} setups qualifiés · mis à jour {lastUpdate.toLocaleTimeString("fr-FR")}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">

          {/* Toggle Command / Advanced */}
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
            {(["simple", "pro"] as const).map(m => (
              <button key={m} onClick={() => {
                setUiMode(m);
                localStorage.setItem("swing_ui_mode", m);
              }}
                className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                style={{
                  background: uiMode === m ? (m === "simple" ? "#041310" : "#1e1e3a") : "#0d0d18",
                  color:      uiMode === m ? (m === "simple" ? "#10b981" : "#818cf8") : "#4b5563",
                  borderRight: m === "simple" ? "1px solid #1e1e2a" : undefined,
                }}>
                {m === "simple" ? "⚡ Command" : "🔬 Advanced"}
              </button>
            ))}
          </div>

          {/* Toggle Stratégie screener */}
          {uiMode === "pro" && view !== "lab" && view !== "signals" && view !== "trades" && (
            <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
              {([["standard", "📊 Standard"], ["conservative", "🛡 Conservative"]] as [Strategy, string][]).map(([s, label]) => (
                <button key={s} onClick={() => switchStrategy(s)}
                  className="px-3 py-1.5 text-xs font-semibold transition-all"
                  style={{
                    background: strategy === s ? (s === "conservative" ? "#0f2a1a" : "#1e1e3a") : "#0d0d18",
                    color:      strategy === s ? (s === "conservative" ? "#4ade80" : "#818cf8") : "#4b5563",
                    borderRight: s === "standard" ? "1px solid #1e1e2a" : undefined,
                  }}>
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Onglets vue — Pro seulement */}
          {uiMode === "pro" && <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
            {([
              ["table",    "📋 Tableau"],
              ["dynamic",  "⚡ Signaux"],
              ["signals",  "📈 Tracking"],
              ["backtest", "🧪 Backtest"],
              ["lab",      "🧬 Strategy Lab"],
              ["trades",   "📌 Trades"],
            ] as [typeof view, string][]).map(([v, label]) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 text-xs font-medium transition-all"
                style={{
                  background: view === v ? "#1e1e3a" : "#0d0d18",
                  color:      view === v ? "#818cf8" : "#4b5563",
                  borderRight: v !== "trades" ? "1px solid #1e1e2a" : undefined,

                }}
              >
                {label}
              </button>
            ))}
          </div>}

          <ApiStatusDot onClick={() => setShowApiStatus(true)} />

          {uiMode === "pro" && view !== "lab" && view !== "signals" && view !== "trades" && (
            <button
              onClick={() => refresh()}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-40"
              style={{ background: "#1e1e3a", border: "1px solid #2a2a4a", color: "#818cf8" }}
            >
              {loading ? (
                <><svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>Analyse...</>
              ) : (
                <><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>Rafraîchir</>
              )}
            </button>
          )}
        </div>
      </div>

      {/* ── COMMAND CENTER ───────────────────────────────────────────────── */}
      {uiMode === "simple" && (
        <CommandCenter
          data={data}
          regime={regime}
          backtestStatus={backtestStatus}
          loading={loading}
          onRefresh={() => refresh()}
          onAdvancedView={() => {
            setUiMode("pro");
            localStorage.setItem("swing_ui_mode", "pro");
          }}
          onGoToLab={() => {
            setUiMode("pro");
            setView("lab");
            localStorage.setItem("swing_ui_mode", "pro");
          }}
        />
      )}

      {/* ── MODE PRO ────────────────────────────────────────────────────── */}
      {uiMode === "pro" && <>

      {/* GLOBAL STATUS BAR */}
      {view !== "lab" && view !== "signals" && view !== "trades" && (
        <GlobalStatusBar regime={regime} backtestStatus={backtestStatus} />
      )}

      {/* NON TRADABLE gating banner */}
      {view !== "lab" && view !== "signals" && view !== "trades" && backtestStatus === "NON TRADABLE" && (
        <div className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap"
          style={{ background: "#1a0a0a", border: "1px solid #7f1d1d66" }}>
          <span>🚫</span>
          <div>
            <p className="text-xs font-black text-red-400">Stratégie NON TRADABLE</p>
            <p className="text-[11px] text-red-700 mt-0.5">
              La stratégie active n&apos;a pas passé les critères de validation (backtest insuffisant).
              Les signaux affichés sont <strong>théoriques uniquement</strong> — ne pas trader en live.
            </p>
          </div>
          <button
            onClick={() => setView("lab")}
            className="ml-auto px-3 py-1.5 rounded-lg text-xs font-bold"
            style={{ background: "#3b0f0f", border: "1px solid #7f1d1d", color: "#f87171" }}>
            Voir Strategy Lab →
          </button>
        </div>
      )}

      {/* MARKET REGIME BANNER */}
      {view !== "lab" && view !== "signals" && view !== "trades" && <MarketRegimeBanner regime={regime} />}

      {/* MARKET CONTEXT (VIX + Breadth + Sectors) */}
      {view === "table" && <MarketContext />}

      {/* STATS ROW */}
      {view !== "lab" && view !== "signals" && view !== "trades" && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-6">
          {[
            {
              label: backtestStatus === "NON TRADABLE" ? "A+ Théorique" : "A+ Setups",
              value: stats.aPlus,
              color: backtestStatus === "NON TRADABLE" ? "#f87171" : "#4ade80",
            },
            { label: "A Setups",     value: stats.a,       color: "#bef264" },
            { label: "B Setups",     value: stats.b,       color: "#fde047" },
            { label: "Score Moy.",   value: stats.avgScore, color: "#818cf8" },
            { label: "R/R Moy.",     value: `1:${stats.avgRR}`, color: "#34d399" },
            { label: "Confiance",    value: `${stats.avgConf}%`, color: "#f59e0b" },
          ].map(s => (
            <div
              key={s.label}
              className="rounded-xl p-3 text-center"
              style={{ background: "#0d0d18", border: `1px solid ${s.color}22` }}
            >
              <p className="text-xs font-bold mb-1" style={{ color: s.color }}>{s.label}</p>
              <p className="text-xl font-black text-white">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* CONTENU */}
      {view === "table" ? (
        <>
          <Top5Cards data={data} />

          {/* FILTRES */}
          <div className="rounded-xl p-4 mb-4" style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}>
            <div className="flex flex-wrap gap-3 items-center">

              {/* Search */}
              <div className="relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Ticker..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
                  style={{ background: "#070710", border: "1px solid #1e1e2a", color: "#e2e8f0", width: "130px" }}
                />
              </div>

              {/* Score min */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-600">Score min</span>
                <input
                  type="range" min={0} max={100} step={5} value={minScore}
                  onChange={e => setMinScore(Number(e.target.value))}
                  className="w-20 accent-indigo-500"
                />
                <span className="text-xs font-bold text-indigo-400 w-8">{minScore}</span>
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Grade filter */}
              <div className="flex gap-1.5">
                <FilterBtn label="Tous" active={grade === ""} onClick={() => setGrade("")} />
                {GRADES.map(g => (
                  <FilterBtn
                    key={g}
                    label={g}
                    active={grade === g}
                    onClick={() => setGrade(grade === g ? "" : g)}
                    color={gradeColors[g]}
                  />
                ))}
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Secteurs */}
              <div className="flex gap-1.5 flex-wrap">
                <FilterBtn label="Tous secteurs" active={sector === ""} onClick={() => setSector("")} />
                {SECTORS.map(s => (
                  <FilterBtn key={s} label={s} active={sector === s} onClick={() => setSector(sector === s ? "" : s)} />
                ))}
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Signaux */}
              <div className="flex gap-1.5">
                {SIGNALS.map(s => (
                  <FilterBtn key={s} label={s} active={signal === s} onClick={() => setSignal(signal === s ? "" : s)} />
                ))}
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Filtre earnings */}
              <button
                onClick={() => toggleEarnings(!excludeEarnings)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: excludeEarnings ? "#1a0e00" : "#0d0d18",
                  border:     `1px solid ${excludeEarnings ? "#ca8a04" : "#1e1e2a"}`,
                  color:      excludeEarnings ? "#fde047" : "#4b5563",
                }}
                title="Exclure les actions avec des résultats financiers dans les 5 prochains jours"
              >
                {excludeEarnings ? "⚠️" : "📅"} Earnings {excludeEarnings ? "exclus" : "inclus"}
              </button>

              <span className="ml-auto text-xs text-gray-600">{filtered.length} résultats</span>
            </div>
          </div>

          {/* Bandeau stratégie lab active */}
          {activeLabKey && signal && (
            <div className="mb-4 px-4 py-2 rounded-xl text-xs flex items-center gap-2"
              style={{ background: "#0d1a0d", border: "1px solid #16a34a33", color: "#4ade80" }}>
              <span>🧬</span>
              <span>
                Filtre Strategy Lab actif — signal :&nbsp;<strong>{signal}</strong>
              </span>
              <button
                onClick={() => { setActiveLabKey(""); setSignal(""); }}
                className="ml-auto text-gray-600 hover:text-gray-300 transition-colors"
              >✕</button>
            </div>
          )}

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-600 text-sm">
              Aucun résultat pour ces filtres.
            </div>
          ) : (
            <ScreenerTable data={filtered} />
          )}
        </>
      ) : view === "dynamic" ? (
        <DynamicCategories data={data} />
      ) : view === "signals" ? (
        <SignalTracker />
      ) : view === "backtest" ? (
        <BacktestView strategy={strategy} />
      ) : view === "trades" ? (
        <TradeJournal />
      ) : (
        <StrategyLab
          activeStrategyKey={activeLabKey}
          onUseStrategy={(screenerStrategy, screenerSignal, labKey, tradableStatus) =>
            handleUseLabStrategy(screenerStrategy, screenerSignal, labKey, tradableStatus as TradableStatus)
          }
        />
      )}

      </> /* fin uiMode === "pro" */}
    </div>
  );
}
