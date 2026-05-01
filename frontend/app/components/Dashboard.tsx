"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { TickerResult, MarketRegime, DataFreshness, UniverseScope, CryptoRegimeEngine } from "../types";
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
import { DataFreshnessPanel } from "./DataFreshnessPanel";
import { getApiUrl } from "../lib/api";
import { CryptoCommandCenter } from "./crypto/CryptoCommandCenter";

const API_URL = getApiUrl();

const SECTORS = [
  "Technology", "Healthcare", "Financials",
  "Consumer Discretionary", "Consumer Staples",
  "Energy", "Industrials", "Materials",
  "Communication", "Real Estate", "Utilities",
  "Growth / Innovation",
];
const SIGNALS = ["Momentum", "Pullback", "Breakout"];
const CRYPTO_SECTORS = [
  "Store of Value", "Smart Contracts", "Layer 1", "Exchange", "Payments",
  "Meme", "Oracle", "Layer 0", "Layer 2", "DeFi", "Infra", "Storage",
];
const CRYPTO_SIGNALS = ["Momentum", "Pullback", "Breakout", "Neutral"];
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
  const [universe, setUniverse]     = useState<UniverseScope>("actions");
  const [data, setData]             = useState(initialData);
  const [loading, setLoading]       = useState(initialData.length === 0);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [strategy, setStrategy]     = useState<Strategy>("standard");
  const [regime, setRegime]         = useState<MarketRegime | null>(null);
  const [cryptoRegime, setCryptoRegime] = useState<CryptoRegimeEngine | null>(null);
  const [freshness, setFreshness]   = useState<DataFreshness | null>(null);

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

  // ── Real-time price polling ──────────────────────────────────────────────────
  const [priceMap, setPriceMap] = useState<Record<string, { price: number; change_pct: number; change_abs: number }>>({});
  const [lastPriceUpdate, setLastPriceUpdate] = useState<Date | null>(null);
  const [secondsSincePrice, setSecondsSincePrice] = useState(0);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const priceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Strategy Lab
  const [activeLabKey, setActiveLabKey] = useState<string>("");
  const [backtestStatus, setBacktestStatus] = useState<TradableStatus>(() => {
    if (typeof window === "undefined") return null;
    return (localStorage.getItem("swing_backtest_status") as TradableStatus) ?? null;
  });
  // API Status modal
  const [showApiStatus, setShowApiStatus] = useState(false);
  const isCrypto = universe === "crypto";
  const currentSectors = isCrypto ? CRYPTO_SECTORS : SECTORS;
  const currentSignals = isCrypto ? CRYPTO_SIGNALS : SIGNALS;

  const fetchFreshness = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/data-freshness?scope=${isCrypto ? "crypto" : "actions"}`, { cache: "no-store" });
      const json = await res.json();
      setFreshness(json);
    } catch {
      // silencieux
    }
  }, [isCrypto]);

  // ── Fetch sans vider le cache (auto-refresh toutes les 60s) ─────────────────
  const fetchData = useCallback(async (strat?: Strategy, excEarnings?: boolean) => {
    setLoading(true);
    const s  = strat      ?? strategy;
    const ee = excEarnings ?? excludeEarnings;
    try {
      const screenerPromise = fetch(
        isCrypto
          ? `${API_URL}/api/crypto/screener`
          : `${API_URL}/api/screener?strategy=${s}&exclude_earnings=${ee}`,
        { cache: "no-store" }
      );
      const regimePromise = fetch(
        isCrypto ? `${API_URL}/api/crypto/regime` : `${API_URL}/api/market-regime`,
        { cache: "no-store" }
      )
        .then(r => r.json())
        .then(json => {
          if (isCrypto) setCryptoRegime(json);
          else setRegime(json);
        })
        .catch(() => null);

      const screenerRes = await screenerPromise;
      const json = await screenerRes.json();
      setData(json);
      setLastUpdate(new Date());
      await regimePromise;
      await fetchFreshness();
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [strategy, excludeEarnings, fetchFreshness, isCrypto]);

  // ── Strategy Edge — recalcul à la demande (après fetchData) ────────────────
  const [edgeCoverage, setEdgeCoverage] = useState<number>(0);
  const [edgeComputing, setEdgeComputing] = useState(false);

  const recalculateEdge = useCallback(async () => {
    setEdgeComputing(true);
    try {
      await fetch(`${API_URL}/${isCrypto ? "api/crypto/edge/compute" : "api/strategy-edge/compute"}`, { method: "POST" });
      await fetchData();
      const r = await fetch(`${API_URL}/${isCrypto ? "api/crypto/edge/status" : "api/strategy-edge/status"}`);
      const j = await r.json();
      setEdgeCoverage(j?.coverage_pct ?? 0);
    } catch { /* silencieux */ }
    finally { setEdgeComputing(false); }
  }, [fetchData, isCrypto]);

  useEffect(() => {
    fetch(`${API_URL}/${isCrypto ? "api/crypto/edge/status" : "api/strategy-edge/status"}`)
      .then(r => r.json())
      .then(j => setEdgeCoverage(j?.coverage_pct ?? 0))
      .catch(() => {});
  }, [isCrypto]);

  // ── Refresh manuel : vide le cache prix puis recharge ────────────────────────
  const refresh = useCallback(async (strat?: Strategy, excEarnings?: boolean) => {
    await fetch(`${API_URL}/api/clear-cache`, { method: "POST" }).catch(() => {});
    await fetchData(strat, excEarnings);
  }, [fetchData]);

  // ── Polling prix léger toutes les 15 secondes ────────────────────────────────
  const pollPrices = useCallback(async (rows: TickerResult[]) => {
    if (rows.length === 0) return;
    const tickers = rows.map(r => r.ticker).join(",");
    try {
      const res  = await fetch(
        isCrypto ? `${API_URL}/api/crypto/prices?symbols=${tickers}` : `${API_URL}/api/prices?tickers=${tickers}`,
        { cache: "no-store" }
      );
      const list = await res.json() as { ticker: string; price: number; change_pct: number; change_abs: number }[];
      setPriceMap(prev => {
        const next = { ...prev };
        for (const p of list) next[p.ticker] = { price: p.price, change_pct: p.change_pct, change_abs: p.change_abs };
        return next;
      });
      setLastPriceUpdate(new Date());
      setSecondsSincePrice(0);
    } catch { /* silencieux */ }
  }, [isCrypto]);

  const refreshPricesOnly = useCallback(async () => {
    setPriceRefreshing(true);
    try {
      setPriceMap({});
      await pollPrices(data);
      await fetchFreshness();
    } finally {
      setPriceRefreshing(false);
    }
  }, [data, pollPrices, fetchFreshness]);

  // Lance + relance le polling quand `data` change
  useEffect(() => {
    if (data.length === 0) return;
    pollPrices(data);
    if (priceTimerRef.current) clearInterval(priceTimerRef.current);
    priceTimerRef.current = setInterval(() => pollPrices(data), 15_000);
    return () => { if (priceTimerRef.current) clearInterval(priceTimerRef.current); };
  }, [data, pollPrices]);

  // Compteur "il y a X sec"
  useEffect(() => {
    const id = setInterval(() => {
      setSecondsSincePrice(prev => prev + 1);
    }, 1_000);
    return () => clearInterval(id);
  }, []);

  // Fusionne les prix temps réel dans les données screener
  const dataWithLivePrices = useMemo<TickerResult[]>(() => {
    if (Object.keys(priceMap).length === 0) return data;
    return data.map(r => {
      const p = priceMap[r.ticker];
      if (!p) return r;
      const dist_entry_pct = r.entry > 0 ? ((p.price - r.entry) / r.entry) * 100 : r.dist_entry_pct;
      return { ...r, price: p.price, change_pct: p.change_pct, change_abs: p.change_abs, dist_entry_pct };
    });
  }, [data, priceMap]);

  // Chargement initial + auto-refresh toutes les 60 secondes
  useEffect(() => {
    fetchData();
    fetch(isCrypto ? `${API_URL}/api/crypto/regime` : `${API_URL}/api/market-regime`)
      .then(r => r.json())
      .then(json => {
        if (isCrypto) setCryptoRegime(json);
        else setRegime(json);
      })
      .catch(() => null);
    fetchFreshness();

    // Auto-refresh toutes les 60 secondes (cache prix expire en 60s côté backend)
    const id = setInterval(() => fetchData(), 60_000);
    return () => clearInterval(id);
  }, [fetchData, fetchFreshness, isCrypto]);

  const switchStrategy = useCallback((s: Strategy) => {
    if (isCrypto) return;
    setStrategy(s);
    refresh(s, excludeEarnings);
  }, [refresh, excludeEarnings, isCrypto]);

  const toggleEarnings = useCallback((val: boolean) => {
    if (isCrypto) return;
    setExcludeEarnings(val);
    refresh(strategy, val);
  }, [refresh, strategy, isCrypto]);

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
    return dataWithLivePrices.filter(r => {
      if (search   && !r.ticker.toLowerCase().includes(search.toLowerCase())) return false;
      if (sector   && r.sector !== sector)       return false;
      if (signal   && r.signal_type !== signal)  return false;
      if (grade    && r.setup_grade !== grade)   return false;
      if (minScore > 0 && r.score < minScore)    return false;
      return true;
    });
  }, [dataWithLivePrices, search, sector, signal, grade, minScore]);

  const stats = useMemo(() => {
    const d = dataWithLivePrices;
    const aPlus   = d.filter(r => r.setup_grade === "A+").length;
    const a       = d.filter(r => r.setup_grade === "A").length;
    const b       = d.filter(r => r.setup_grade === "B").length;
    const avgScore = d.length ? Math.round(d.reduce((acc, r) => acc + r.score, 0) / d.length) : 0;
    const avgRR    = d.length ? Math.round(d.reduce((acc, r) => acc + r.rr_ratio, 0) / d.length * 10) / 10 : 0;
    const avgConf  = d.length ? Math.round(d.reduce((acc, r) => acc + r.confidence, 0) / d.length) : 0;
    return { aPlus, a, b, avgScore, avgRR, avgConf };
  }, [dataWithLivePrices]);

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
            {dataWithLivePrices.length} {isCrypto ? "cryptos qualifiées" : "setups qualifiés"} · screener {lastUpdate.toLocaleTimeString("fr-FR")}
            {lastPriceUpdate && (
              <span className="ml-2 text-emerald-700">
                · prix{" "}
                <span style={{ color: secondsSincePrice < 20 ? "#10b981" : "#6b7280" }}>
                  {secondsSincePrice < 60
                    ? `il y a ${secondsSincePrice}s`
                    : `il y a ${Math.floor(secondsSincePrice / 60)}m`}
                </span>
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">

          {/* Toggle Command / Advanced */}
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
            {(["actions", "crypto"] as const).map((u) => (
              <button key={u} onClick={() => {
                setUniverse(u);
                setSector("");
                setSignal("");
                setGrade("");
                setSearch("");
                setMinScore(0);
                setView("table");
              }}
                className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                style={{
                  background: universe === u ? (u === "actions" ? "#041310" : "#101025") : "#0d0d18",
                  color: universe === u ? (u === "actions" ? "#10b981" : "#60a5fa") : "#4b5563",
                  borderRight: u === "actions" ? "1px solid #1e1e2a" : undefined,
                }}>
                {u === "actions" ? "Actions" : "Crypto"}
              </button>
            ))}
          </div>

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
          {!isCrypto && uiMode === "pro" && view !== "lab" && view !== "signals" && view !== "trades" && (
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
            {((isCrypto
              ? ([
                  ["table", "📋 Tableau"],
                  ["backtest", "🧪 Backtest"],
                  ["lab", "🧬 Strategy Lab"],
                ] as [typeof view, string][])
              : ([
                  ["table",    "📋 Tableau"],
                  ["dynamic",  "⚡ Signaux"],
                  ["signals",  "📈 Tracking"],
                  ["backtest", "🧪 Backtest"],
                  ["lab",      "🧬 Strategy Lab"],
                  ["trades",   "📌 Trades"],
                ] as [typeof view, string][]))).map(([v, label]) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 text-xs font-medium transition-all"
                style={{
                  background: view === v ? "#1e1e3a" : "#0d0d18",
                  color:      view === v ? "#818cf8" : "#4b5563",
                  borderRight: (!isCrypto && v !== "trades") || (isCrypto && v !== "lab") ? "1px solid #1e1e2a" : undefined,

                }}
              >
                {label}
              </button>
            ))}
          </div>}

          <ApiStatusDot onClick={() => setShowApiStatus(true)} />

          {/* Bouton Recalculate Edge — mode Advanced uniquement */}
          {uiMode === "pro" && view === "table" && (
            <button
              onClick={recalculateEdge}
              disabled={edgeComputing}
              title={`Recalculer l'edge historique par ticker (cache 24h)\nCouverture actuelle : ${edgeCoverage.toFixed(0)}%`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-40"
              style={{ background: "#0a1a0a", border: "1px solid #16a34a44", color: edgeComputing ? "#4ade8088" : "#4ade80" }}
            >
              {edgeComputing ? (
                <><svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>Edge…</>
              ) : (
                <>⚡ Edge {edgeCoverage > 0 ? `${edgeCoverage.toFixed(0)}%` : "?"}</>
              )}
            </button>
          )}

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
      <DataFreshnessPanel
        freshness={freshness}
        onFullRefresh={() => refresh()}
        onPriceRefresh={refreshPricesOnly}
        loading={loading}
        priceRefreshing={priceRefreshing}
      />

      {uiMode === "simple" && (
        isCrypto ? (
          <CryptoCommandCenter
            data={dataWithLivePrices}
            loading={loading}
            onRefresh={() => refresh()}
            onRefreshPrices={refreshPricesOnly}
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
        ) : (
          <CommandCenter
            data={dataWithLivePrices}
            regime={regime}
            backtestStatus={backtestStatus}
            loading={loading}
            onRefresh={() => refresh()}
            onRefreshPrices={refreshPricesOnly}
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
        )
      )}

      {/* ── MODE PRO ────────────────────────────────────────────────────── */}
      {uiMode === "pro" && <>

      {/* GLOBAL STATUS BAR */}
      {!isCrypto && view !== "lab" && view !== "signals" && view !== "trades" && (
        <GlobalStatusBar regime={regime} backtestStatus={backtestStatus} />
      )}

      {/* NON TRADABLE gating banner */}
      {!isCrypto && view !== "lab" && view !== "signals" && view !== "trades" && backtestStatus === "NON TRADABLE" && (
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
      {!isCrypto && view !== "lab" && view !== "signals" && view !== "trades" && <MarketRegimeBanner regime={regime} />}

      {isCrypto && view !== "lab" && view !== "backtest" && cryptoRegime && (
        <div className="rounded-xl px-4 py-3 mb-5 flex items-center gap-4 flex-wrap" style={{ background: "#081018", border: "1px solid #1f3b5a" }}>
          <div>
            <p className="text-xs font-black text-cyan-300 uppercase tracking-widest">{cryptoRegime.regime_label}</p>
            <p className="text-[10px] text-gray-500 mt-0.5">{cryptoRegime.reasons.join(" · ")}</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400 flex-wrap ml-auto">
            <span>BTC <strong className="text-white">${cryptoRegime.btc_price.toFixed(0)}</strong></span>
            <span>ETH <strong className="text-white">${cryptoRegime.eth_price.toFixed(0)}</strong></span>
            <span>Breadth <strong className="text-cyan-300">{cryptoRegime.breadth_pct}%</strong></span>
            <span>BTC Dom. <strong className="text-cyan-300">{cryptoRegime.btc_dominance.toFixed(1)}%</strong></span>
          </div>
        </div>
      )}

      {/* MARKET CONTEXT (VIX + Breadth + Sectors) */}
      {!isCrypto && view === "table" && <MarketContext />}

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
          <Top5Cards data={dataWithLivePrices} scope={isCrypto ? "crypto" : "actions"} />

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
                {currentSectors.map(s => (
                  <FilterBtn key={s} label={s} active={sector === s} onClick={() => setSector(sector === s ? "" : s)} />
                ))}
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Signaux */}
              <div className="flex gap-1.5">
                {currentSignals.map(s => (
                  <FilterBtn key={s} label={s} active={signal === s} onClick={() => setSignal(signal === s ? "" : s)} />
                ))}
              </div>

              <div className="h-4 w-px" style={{ background: "#1e1e2a" }} />

              {/* Filtre earnings */}
              {!isCrypto && <button
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
              </button>}

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
            <ScreenerTable data={filtered} showEdge={true} scope={isCrypto ? "crypto" : "actions"} />
          )}
        </>
      ) : view === "dynamic" ? (
        <DynamicCategories data={data} />
      ) : view === "signals" ? (
        <SignalTracker />
      ) : view === "backtest" ? (
        <BacktestView strategy={strategy} scope={isCrypto ? "crypto" : "actions"} />
      ) : view === "trades" ? (
        <TradeJournal />
      ) : (
        <StrategyLab
          activeStrategyKey={activeLabKey}
          scope={isCrypto ? "crypto" : "actions"}
          onUseStrategy={(screenerStrategy, screenerSignal, labKey, tradableStatus) =>
            handleUseLabStrategy(screenerStrategy, screenerSignal, labKey, tradableStatus as TradableStatus)
          }
        />
      )}

      </> /* fin uiMode === "pro" */}
    </div>
  );
}
