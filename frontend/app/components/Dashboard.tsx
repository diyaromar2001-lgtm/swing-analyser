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
import { AdminPanel } from "./AdminPanel";
import { ensureApiResponse, getAdminApiKey, getAdminHeaders, getApiUrl, isAdminProtectedError } from "../lib/api";
import { getActionsCacheStatus, getCryptoCacheStatus } from "../lib/cacheStatus";
import { CryptoCommandCenter } from "./crypto/CryptoCommandCenter";
import { applyCryptoResearchV2Overlay } from "../lib/cryptoResearchV2";
import { CryptoResearchV2Panel } from "./crypto/CryptoResearchV2Panel";
import { formatCryptoPrice } from "../lib/cryptoFormat";

const API_URL = getApiUrl();
const SCREENER_TIMEOUT_MS = 30_000;
const ACTIONS_SCREENER_CACHE_KEY = "last_actions_screener_results";
const CRYPTO_SCREENER_CACHE_KEY = "last_crypto_screener_results";

type ScreenerCachePayload = {
  ts: number;
  data: TickerResult[];
};

function getScreenerCacheKey(scope: UniverseScope): string {
  return scope === "crypto" ? CRYPTO_SCREENER_CACHE_KEY : ACTIONS_SCREENER_CACHE_KEY;
}

function loadScreenerCache(scope: UniverseScope): ScreenerCachePayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(getScreenerCacheKey(scope));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ScreenerCachePayload>;
    if (!Array.isArray(parsed.data)) return null;
    return {
      ts: typeof parsed.ts === "number" ? parsed.ts : Date.now(),
      data: parsed.data as TickerResult[],
    };
  } catch {
    return null;
  }
}

function saveScreenerCache(scope: UniverseScope, data: TickerResult[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      getScreenerCacheKey(scope),
      JSON.stringify({ ts: Date.now(), data }),
    );
  } catch {
    // silencieux
  }
}

async function fetchJsonWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = SCREENER_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

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
type FetchDataOptions = {
  fast?: boolean;
  background?: boolean;
  strategyOverride?: Strategy;
  excludeEarningsOverride?: boolean;
};
type EdgeHorizon = 24 | 36;
type EdgeOverlay = Pick<
  TickerResult,
  | "ticker_edge_status"
  | "best_strategy_for_ticker"
  | "best_strategy_name"
  | "best_strategy_color"
  | "best_strategy_emoji"
  | "edge_score"
  | "edge_train_pf"
  | "edge_test_pf"
  | "edge_trades"
  | "edge_win_rate"
  | "edge_pf"
  | "edge_expectancy"
  | "edge_max_dd"
  | "overfit_warning"
  | "overfit_reasons"
> & {
  edge_period_months?: number;
};
type EdgeV2Overlay = Pick<
  TickerResult,
  | "edge_v2_score"
  | "edge_v2_status"
  | "edge_v2_strategy_name"
  | "edge_v2_strategy_edge"
  | "edge_v2_sector_edge"
  | "edge_v2_regime_edge"
  | "edge_v2_ticker_component"
  | "edge_v2_setup_quality"
  | "edge_v2_sample_status"
  | "edge_v2_sector_status"
  | "edge_v2_regime_status"
  | "edge_v2_allowed"
  | "edge_v2_reasons"
  | "edge_v2_warnings"
>;

function safeNumber(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function safePercent(value?: number | null, digits = 1) {
  const num = safeNumber(value);
  return num === null ? "—" : `${num.toFixed(digits)}%`;
}

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
  const initialScreenerCache = typeof window === "undefined" ? null : loadScreenerCache("actions");
  const [data, setData]             = useState<TickerResult[]>(initialScreenerCache?.data?.length ? initialScreenerCache.data : initialData);
  const [loading, setLoading]       = useState((initialScreenerCache?.data?.length ? false : initialData.length === 0));
  const [lastUpdate, setLastUpdate] = useState(() => initialScreenerCache?.ts ? new Date(initialScreenerCache.ts) : new Date());
  const [strategy, setStrategy]     = useState<Strategy>("standard");
  const [regime, setRegime]         = useState<MarketRegime | null>(null);
  const [cryptoRegime, setCryptoRegime] = useState<CryptoRegimeEngine | null>(null);
  const [freshness, setFreshness]   = useState<DataFreshness | null>(null);
  const [screenerRefreshing, setScreenerRefreshing] = useState(false);
  const [repairNotice, setRepairNotice] = useState<string | null>(null);
  const [infoNotice, setInfoNotice] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [adminErrorNotice, setAdminErrorNotice] = useState<string | null>(null);
  const [dataErrorNotice, setDataErrorNotice] = useState<string | null>(null);

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
  const screenerScope: UniverseScope = isCrypto ? "crypto" : "actions";
  const currentSectors = isCrypto ? CRYPTO_SECTORS : SECTORS;
  const currentSignals = isCrypto ? CRYPTO_SIGNALS : SIGNALS;
  const dataLengthRef = useRef(data.length);
  const strategyRef = useRef(strategy);
  const excludeEarningsRef = useRef(excludeEarnings);

  useEffect(() => {
    dataLengthRef.current = data.length;
  }, [data.length]);

  useEffect(() => {
    strategyRef.current = strategy;
  }, [strategy]);

  useEffect(() => {
    excludeEarningsRef.current = excludeEarnings;
  }, [excludeEarnings]);

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
  const fetchData = useCallback(async (opts: FetchDataOptions = {}) => {
    const fast = opts.fast ?? true;
    const background = opts.background ?? false;
    const s  = opts.strategyOverride ?? strategyRef.current;
    const ee = opts.excludeEarningsOverride ?? excludeEarningsRef.current;
    const hadVisibleData = dataLengthRef.current > 0;
    setLoading(true);
    setScreenerRefreshing(true);
    setDataErrorNotice(null);
    setRepairNotice(null);
    try {
      const screenerUrl = isCrypto
        ? `${API_URL}/api/crypto/screener${fast ? "?fast=true" : ""}`
        : `${API_URL}/api/screener?strategy=${encodeURIComponent(s)}&exclude_earnings=${ee ? "true" : "false"}${fast ? "&fast=true" : ""}`;
      const screenerPromise = fetchJsonWithTimeout(screenerUrl, { cache: "no-store" });
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
      if (!screenerRes.ok) {
        throw new Error(`HTTP ${screenerRes.status}`);
      }
      const json = await screenerRes.json();
      if (!Array.isArray(json)) {
        throw new Error("Format screener inattendu");
      }
      if (json.length > 0) {
        setData(json);
        dataLengthRef.current = json.length;
        setLastUpdate(new Date());
        saveScreenerCache(screenerScope, json);
        setDataErrorNotice(null);
      } else if (isCrypto) {
        // Cache vide côté serveur (cold-start Railway) — retry sans fast=true
        let recovered = false;
        if (fast) {
          try {
            const retryRes = await fetchJsonWithTimeout(
              `${API_URL}/api/crypto/screener`,
              { cache: "no-store" },
              20_000,
            );
            if (retryRes.ok) {
              const retryJson = await retryRes.json();
              if (Array.isArray(retryJson) && retryJson.length > 0) {
                setData(retryJson);
                dataLengthRef.current = retryJson.length;
                setLastUpdate(new Date());
                saveScreenerCache(screenerScope, retryJson);
                setDataErrorNotice(null);
                recovered = true;
              }
            }
          } catch { /* retry silencieux */ }
        }
        if (!recovered) {
          const cached = loadScreenerCache(screenerScope);
          if (cached?.data?.length || hadVisibleData) {
            setDataErrorNotice("Données précédentes — refresh échoué");
          } else {
            setData([]);
            dataLengthRef.current = 0;
            setDataErrorNotice("Aucune donnée crypto en cache. Lancez une réparation des caches.");
          }
        }
      } else {
        setData(json);
        dataLengthRef.current = json.length;
        setLastUpdate(new Date());
        saveScreenerCache(screenerScope, json);
        setDataErrorNotice(null);
      }
      await regimePromise;
      await fetchFreshness();
    } catch (e) {
      const timeout = e instanceof DOMException && e.name === "AbortError";
      setDataErrorNotice(timeout
        ? "Réparation des caches trop longue. Les dernières données disponibles restent affichées."
        : "Données précédentes — refresh échoué");
      const cached = loadScreenerCache(screenerScope);
      if (cached?.data?.length && !hadVisibleData) {
        setData(cached.data);
        dataLengthRef.current = cached.data.length;
        setLastUpdate(new Date(cached.ts));
      }
      if (!timeout) console.error(e);
    } finally {
      setScreenerRefreshing(false);
      setLoading(false);
    }
  }, [fetchFreshness, isCrypto, screenerScope]);

  // ── Strategy Edge — recalcul à la demande (après fetchData) ────────────────
  const [edgeHorizon, setEdgeHorizon] = useState<EdgeHorizon>(24);
  const [edgeCoverage, setEdgeCoverage] = useState<number>(0);
  const [edgeComputing, setEdgeComputing] = useState(false);
  const [edgeOverlayCache, setEdgeOverlayCache] = useState<Record<string, Record<string, EdgeOverlay>>>({});
  const [edgeOverlayLoading, setEdgeOverlayLoading] = useState(false);
  const [edgeOverlayNotice, setEdgeOverlayNotice] = useState<string | null>(null);
  const [edgeMode, setEdgeMode] = useState<"v1" | "v2">("v1");
  const [edgeV2OverlayCache, setEdgeV2OverlayCache] = useState<Record<string, EdgeV2Overlay>>({});
  const [edgeV2Loading, setEdgeV2Loading] = useState(false);
  const [edgeV2Notice, setEdgeV2Notice] = useState<string | null>(null);
  const lastEdgeV2FetchKeyRef = useRef<string>("");
  const [cryptoResearchMode, setCryptoResearchMode] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [adminKeyPresent, setAdminKeyPresent] = useState(() => !!getAdminApiKey());

  async function recalculateEdge() {
    setEdgeComputing(true);
    setRepairNotice(null);
    setInfoNotice(null);
    setAdminErrorNotice(null);
    try {
      const actionTickers = !isCrypto && edgeHorizon === 36
        ? data.map(row => row.ticker).join(",")
        : "";
      const edgeUrl = isCrypto
        ? `${API_URL}/api/crypto/edge/compute`
        : `${API_URL}/api/strategy-edge/compute?period=${edgeHorizon}${actionTickers ? `&tickers=${encodeURIComponent(actionTickers)}` : ""}`;
      const edgeRes = await fetchJsonWithTimeout(edgeUrl, {
        method: "POST",
        headers: getAdminHeaders(),
      }, edgeHorizon === 36 ? 120_000 : 60_000);
      await ensureApiResponse(edgeRes);
      await fetchData({ fast: true, background: true });
      if (!isCrypto && edgeHorizon === 36) {
        setEdgeOverlayCache(prev => ({ ...prev, ["36"]: {} }));
        await loadAdvancedEdgeOverlay(36, data);
        setEdgeOverlayNotice("Edge 36m recalculé pour l'analyse avancée.");
      } else {
        const r = await fetch(`${API_URL}/${isCrypto ? "api/crypto/edge/status" : "api/strategy-edge/status"}`);
        const j = await r.json();
        setEdgeCoverage(j?.coverage_pct ?? 0);
      }
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée");
        setEdgeOverlayNotice("Action admin protégée");
      }
    }
    finally { setEdgeComputing(false); }
  }

  useEffect(() => {
    fetch(`${API_URL}/${isCrypto ? "api/crypto/edge/status" : "api/strategy-edge/status"}`)
      .then(r => r.json())
      .then(j => setEdgeCoverage(j?.coverage_pct ?? 0))
      .catch(() => {});
  }, [isCrypto]);

  useEffect(() => {
    if (!isCrypto) {
      setCryptoResearchMode(false);
    }
  }, [isCrypto]);

  const handleRefreshScreener = useCallback(async () => {
    // Refresh screener data after edge compute
    try {
      const refreshedData = await fetchData({ fast: true });
      // If advanced view is active and we have fresh data, reload overlay
      if (uiMode === "pro" && !isCrypto && edgeHorizon === 36) {
        setEdgeOverlayCache(prev => ({ ...prev, ["36"]: {} }));
      }
    } catch (error) {
      console.error("Failed to refresh screener:", error);
    }
  }, [fetchData, uiMode, isCrypto, edgeHorizon]);

  useEffect(() => {
    if (!successNotice) return;
    if (!successNotice.includes("Dernières données locales") && !successNotice.startsWith("Caches prêts")) return;
    const timer = window.setTimeout(() => setSuccessNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [successNotice]);

  const loadAdvancedEdgeOverlay = useCallback(async (period: EdgeHorizon, rows: TickerResult[]) => {
    if (isCrypto || period === 24 || rows.length === 0) return;
    const tickers = rows.map(row => row.ticker).join(",");
    setEdgeOverlayLoading(true);
    setEdgeOverlayNotice(null);
    try {
      const cachedRes = await fetchJsonWithTimeout(
        `${API_URL}/api/strategy-edge/results?period=${period}&tickers=${encodeURIComponent(tickers)}`,
        { cache: "no-store" },
        30_000,
      );
      await ensureApiResponse(cachedRes);
      let json = await cachedRes.json();
      const cachedCount = Array.isArray(json?.results) ? json.results.length : 0;

      if (cachedCount < rows.length) {
        const computeRes = await fetchJsonWithTimeout(
          `${API_URL}/api/strategy-edge/compute?period=${period}&tickers=${encodeURIComponent(tickers)}`,
          { method: "POST" },
          120_000,
        );
        await ensureApiResponse(computeRes);
        const freshRes = await fetchJsonWithTimeout(
          `${API_URL}/api/strategy-edge/results?period=${period}&tickers=${encodeURIComponent(tickers)}`,
          { cache: "no-store" },
          120_000,
        );
        await ensureApiResponse(freshRes);
        json = await freshRes.json();
      }

      const next: Record<string, EdgeOverlay> = {};
      for (const row of (json?.results ?? []) as any[]) {
        if (!row?.ticker) continue;
        next[row.ticker] = {
          ticker_edge_status: row.ticker_edge_status,
          best_strategy_for_ticker: row.best_strategy,
          best_strategy_name: row.best_strategy_name,
          best_strategy_color: row.best_strategy_color,
          best_strategy_emoji: row.best_strategy_emoji,
          edge_score: row.edge_score,
          edge_train_pf: row.train_pf,
          edge_test_pf: row.test_pf,
          edge_trades: row.total_trades,
          edge_win_rate: row.win_rate,
          edge_pf: row.pf,
          edge_expectancy: row.expectancy,
          edge_max_dd: row.max_dd,
          overfit_warning: row.overfit_warning,
          overfit_reasons: row.overfit_reasons,
          edge_period_months: row.period_months,
        };
      }
      setEdgeOverlayCache(prev => ({ ...prev, [String(period)]: next }));
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée");
        setEdgeOverlayNotice("Action admin protégée");
      } else {
        setEdgeOverlayNotice("Analyse Edge 36m indisponible pour le moment. Les valeurs 24m restent affichées.");
      }
    } finally {
      setEdgeOverlayLoading(false);
    }
  }, [isCrypto]);

  const loadEdgeV2Research = useCallback(async (rows: TickerResult[], requestKey: string) => {
    if (isCrypto || rows.length === 0 || !requestKey) return;
    if (lastEdgeV2FetchKeyRef.current === requestKey) return;
    lastEdgeV2FetchKeyRef.current = requestKey;
    const tickers = rows.map(row => row.ticker).join(",");
    setEdgeV2Loading(true);
    setEdgeV2Notice(null);
    try {
      const res = await fetchJsonWithTimeout(
        `${API_URL}/api/research/edge-v2?period=36&tickers=${encodeURIComponent(tickers)}&fast=true`,
        { cache: "no-store" },
        45_000,
      );
      await ensureApiResponse(res);
      const json = await res.json();
      const next: Record<string, EdgeV2Overlay> = {};
      for (const row of (json?.results ?? []) as any[]) {
        if (!row?.ticker) continue;
        next[row.ticker] = {
          edge_v2_score: row.edge_v2_score,
          edge_v2_status: row.edge_v2_status,
          edge_v2_strategy_name: row.strategy_name,
          edge_v2_strategy_edge: row.strategy_portfolio_edge_score,
          edge_v2_sector_edge: row.sector_edge_score,
          edge_v2_regime_edge: row.regime_edge_score,
          edge_v2_ticker_component: row.ticker_edge_component,
          edge_v2_setup_quality: row.setup_quality_score,
          edge_v2_sample_status: row.sample_status,
          edge_v2_sector_status: row.sector_status,
          edge_v2_regime_status: row.regime_status,
          edge_v2_allowed: row.allowed_by_v2_research,
          edge_v2_reasons: row.reasons,
          edge_v2_warnings: row.warnings,
        };
      }
      setEdgeV2OverlayCache(next);
      setEdgeV2Notice(json?.summary?.allowed_count
        ? `Edge v2 Research prêt (${json.summary.allowed_count} setups utilisables en recherche).`
        : "Edge v2 Research prêt.");
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setEdgeV2Notice("Action admin protégée");
      } else {
        setEdgeV2Notice("Edge v2 Research indisponible pour le moment.");
      }
    } finally {
      setEdgeV2Loading(false);
    }
  }, [isCrypto]);

  // ── Refresh manuel : vide le cache prix puis recharge ────────────────────────
  const repairCaches = useCallback(async () => {
    if (!adminKeyPresent) {
      setAdminErrorNotice("Admin requis");
      return;
    }
    setRepairNotice("Réparation des caches en cours…");
    setInfoNotice("Réparation des caches en cours…");
    setSuccessNotice(null);
    setAdminErrorNotice(null);
    setDataErrorNotice(null);
    setLoading(true);
    setScreenerRefreshing(true);
    try {
      for (const batch of [1, 2, 3, 4, 5]) {
        setRepairNotice(`Réparation des caches… Actions batch ${batch}/5`);
        setInfoNotice(`Réparation des caches… Actions batch ${batch}/5`);
        const res = await fetch(`${API_URL}/api/warmup?scope=actions&batch=${batch}&batch_size=50&include_edge=false`, {
          method: "POST",
          headers: getAdminHeaders(),
        });
        await ensureApiResponse(res);
      }
      setRepairNotice("Réparation des caches… Warmup Crypto");
      setInfoNotice("Réparation des caches… Warmup Crypto");
      const cryptoRes = await fetch(`${API_URL}/api/warmup?scope=crypto&include_edge=false`, {
        method: "POST",
        headers: getAdminHeaders(),
      });
      await ensureApiResponse(cryptoRes);
      setRepairNotice("Réparation des caches… vérification finale");
      setInfoNotice("Réparation des caches… vérification finale");
      const statusRes = await fetch(`${API_URL}/api/cache-status?scope=all`, { cache: "no-store" });
      await ensureApiResponse(statusRes);
      const status = await statusRes.json();
      const actionsOk = Number(status?.actions?.ohlcv_cache_count ?? 0) > 150 && Number(status?.actions?.price_cache_count ?? 0) > 150 && Number(status?.actions?.screener_results_count ?? 0) > 0;
      const cryptoOk = Number(status?.crypto?.crypto_price_cache_count ?? 0) > 0 && Number(status?.crypto?.crypto_screener_cache_count ?? 0) > 0 && status?.crypto?.crypto_regime_cache_status === "warm";
      const overallOk = actionsOk && cryptoOk;
      if (overallOk) {
        setSuccessNotice("Caches prêts : Actions OK · Crypto OK");
        setRepairNotice("Les données sont chaudes. L'app est prête.");
        setAdminErrorNotice(null);
        setDataErrorNotice(null);
      } else {
        setInfoNotice(
          `Actions ${actionsOk ? "OK" : "à vérifier"} · Crypto ${cryptoOk ? "OK" : "à vérifier"}`
        );
      }
      await fetchData({ fast: true, background: true });
    } catch (error) {
      if (isAdminProtectedError(error)) {
        setAdminErrorNotice("Action admin protégée");
        setRepairNotice(null);
      } else {
        setDataErrorNotice("Warmup trop long ou interrompu. Vérifiez le cache-status.");
      }
    } finally {
      setScreenerRefreshing(false);
      setLoading(false);
    }
  }, [adminKeyPresent, fetchData]);

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

  const restoreFromCache = useCallback(() => {
    const cached = loadScreenerCache(screenerScope);
    if (cached?.data?.length) {
      setData(cached.data);
      dataLengthRef.current = cached.data.length;
      setLastUpdate(new Date(cached.ts));
      setLoading(false);
      setDataErrorNotice(null);
      setSuccessNotice("Dernières données locales restaurées depuis le cache");
      return;
    }
    setSuccessNotice(null);
    setDataErrorNotice("Aucune donnée en cache. Lancez une réparation des caches.");
    setLoading(false);
  }, [screenerScope]);

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

  const edgeOverlayRows = useMemo<Record<string, EdgeOverlay>>(
    () => edgeHorizon === 36 ? (edgeOverlayCache["36"] ?? {}) : {},
    [edgeHorizon, edgeOverlayCache],
  );

  const advancedEdgeData = useMemo<TickerResult[]>(() => {
    if (isCrypto || edgeHorizon === 24) return dataWithLivePrices;
    return dataWithLivePrices.map(row => {
      const overlay = edgeOverlayRows[row.ticker];
      return overlay ? { ...row, ...overlay } : row;
    });
  }, [dataWithLivePrices, edgeHorizon, edgeOverlayRows, isCrypto]);

  const edgeV2RequestKey = useMemo(() => {
    if (isCrypto || uiMode !== "pro" || view !== "table" || edgeMode !== "v2") return "";
    return `v2|36|${data.map(row => row.ticker).join(",")}`;
  }, [data, edgeMode, isCrypto, uiMode, view]);

  const advancedResearchData = useMemo<TickerResult[]>(() => {
    if (isCrypto || edgeMode === "v1") return advancedEdgeData;
    return advancedEdgeData.map(row => {
      const overlay = edgeV2OverlayCache[row.ticker];
      return overlay ? { ...row, ...overlay } : row;
    });
  }, [advancedEdgeData, edgeMode, edgeV2OverlayCache, isCrypto]);

  const cryptoResearchData = useMemo<TickerResult[]>(() => {
    if (!isCrypto) return dataWithLivePrices;
    return dataWithLivePrices.map(row => applyCryptoResearchV2Overlay(row));
  }, [dataWithLivePrices, isCrypto]);

  const activeTableData = useMemo<TickerResult[]>(
    () => {
      if (!isCrypto && uiMode === "pro" && view === "table") return advancedResearchData;
      if (isCrypto && uiMode === "pro" && view === "table") return cryptoResearchData;
      return dataWithLivePrices;
    },
    [advancedResearchData, cryptoResearchData, dataWithLivePrices, isCrypto, uiMode, view],
  );

  // Chargement initial + auto-refresh toutes les 60 secondes
  useEffect(() => {
    const cached = loadScreenerCache(screenerScope);
    if (cached?.data?.length) {
      setData(cached.data);
      setLastUpdate(new Date(cached.ts));
      dataLengthRef.current = cached.data.length;
      setLoading(false);
    } else {
      setData([]);
      dataLengthRef.current = 0;
      setLoading(true);
    }
    setPriceMap({});
    setLastPriceUpdate(null);
    setSecondsSincePrice(0);
    setRegime(null);
    setCryptoRegime(null);
    setFreshness(null);
    setDataErrorNotice(null);
    setAdminErrorNotice(null);
    setSuccessNotice(null);
    setInfoNotice(null);
    void fetchData({ fast: true, background: !!cached?.data?.length });
    fetch(isCrypto ? `${API_URL}/api/crypto/regime` : `${API_URL}/api/market-regime`)
      .then(r => r.json())
      .then(json => {
        if (isCrypto) setCryptoRegime(json);
        else setRegime(json);
      })
      .catch(() => null);
    fetchFreshness();

    // Auto-refresh toutes les 60 secondes (cache prix expire en 60s côté backend)
    const id = setInterval(() => fetchData({ fast: true, background: true }), 60_000);
    return () => clearInterval(id);
  }, [fetchData, fetchFreshness, isCrypto, screenerScope]);

  useEffect(() => {
    if (isCrypto || uiMode !== "pro" || view !== "table") return;
    if (edgeHorizon === 24) {
      setEdgeOverlayLoading(false);
      setEdgeOverlayNotice(null);
      return;
    }
    const cached = edgeOverlayCache["36"] ?? {};
    const missingRows = data.filter(row => !cached[row.ticker]);
    if (missingRows.length === 0) return;
    void loadAdvancedEdgeOverlay(36, missingRows);
  }, [data, edgeHorizon, edgeOverlayCache, isCrypto, loadAdvancedEdgeOverlay, uiMode, view]);

  useEffect(() => {
    if (isCrypto || uiMode !== "pro" || view !== "table" || edgeMode !== "v2") return;
    if (!edgeV2RequestKey) return;
    const missingRows = data.filter(row => !edgeV2OverlayCache[row.ticker]);
    if (missingRows.length === 0) return;
    void loadEdgeV2Research(missingRows, edgeV2RequestKey);
  }, [data, edgeMode, edgeV2OverlayCache, edgeV2RequestKey, isCrypto, loadEdgeV2Research, uiMode, view]);

  useEffect(() => {
    if (edgeMode === "v1") {
      setEdgeV2Notice(null);
      setEdgeV2Loading(false);
      lastEdgeV2FetchKeyRef.current = "";
    }
    if (!edgeV2RequestKey) {
      lastEdgeV2FetchKeyRef.current = "";
    }
  }, [edgeMode, edgeV2RequestKey]);

  const switchStrategy = useCallback((s: Strategy) => {
    if (isCrypto) return;
    setStrategy(s);
    void fetchData({ fast: false, background: true, strategyOverride: s, excludeEarningsOverride: excludeEarnings });
  }, [fetchData, excludeEarnings, isCrypto]);

  const toggleEarnings = useCallback((val: boolean) => {
    if (isCrypto) return;
    setExcludeEarnings(val);
    void fetchData({ fast: false, background: true, strategyOverride: strategy, excludeEarningsOverride: val });
  }, [fetchData, strategy, isCrypto]);

  const handleUseLabStrategy = useCallback((
    screenerStrategy: Strategy,
    screenerSignal: string,
    labKey: string,
    tradableStatus?: TradableStatus,
  ) => {
    setActiveLabKey(labKey);
    setStrategy(screenerStrategy);
    setSignal(screenerSignal);
    void fetchData({ fast: false, background: true, strategyOverride: screenerStrategy, excludeEarningsOverride: excludeEarnings });
    setView("table");
    if (tradableStatus) {
      setBacktestStatus(tradableStatus);
      localStorage.setItem("swing_backtest_status", tradableStatus);
    }
  }, [fetchData, excludeEarnings]);

  const filtered = useMemo(() => {
    return activeTableData.filter(r => {
      if (search   && !r.ticker.toLowerCase().includes(search.toLowerCase())) return false;
      if (sector   && r.sector !== sector)       return false;
      if (signal   && r.signal_type !== signal)  return false;
      if (grade    && r.setup_grade !== grade)   return false;
      if (minScore > 0 && r.score < minScore)    return false;
      return true;
    });
  }, [activeTableData, search, sector, signal, grade, minScore]);

  const stats = useMemo(() => {
    const d = activeTableData;
    const aPlus   = d.filter(r => r.setup_grade === "A+").length;
    const a       = d.filter(r => r.setup_grade === "A").length;
    const b       = d.filter(r => r.setup_grade === "B").length;
    const avgScore = d.length ? Math.round(d.reduce((acc, r) => acc + r.score, 0) / d.length) : 0;
    const avgRR    = d.length ? Math.round(d.reduce((acc, r) => acc + r.rr_ratio, 0) / d.length * 10) / 10 : 0;
    const avgConf  = d.length ? Math.round(d.reduce((acc, r) => acc + r.confidence, 0) / d.length) : 0;
    return { aPlus, a, b, avgScore, avgRR, avgConf };
  }, [activeTableData]);

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
  const runtimeNotice = dataErrorNotice || repairNotice || infoNotice || successNotice || adminErrorNotice;
  const screenerNotice: { kind: "timeout" | "refresh-failed" | "empty-cache"; message: string } | null = dataErrorNotice
    ? {
        kind: dataErrorNotice.toLowerCase().includes("trop longue")
          ? "timeout"
          : dataErrorNotice.toLowerCase().includes("aucune donnée")
            ? "empty-cache"
            : "refresh-failed",
        message: dataErrorNotice,
      }
    : null;

  if (loading && data.length === 0 && !runtimeNotice) {
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
      {showAdminPanel && (
        <AdminPanel
          apiUrl={API_URL}
          onClose={() => setShowAdminPanel(false)}
          onKeyChange={setAdminKeyPresent}
          onRefreshScreener={handleRefreshScreener}
        />
      )}
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
          <button
            onClick={() => setShowAdminPanel(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold transition-all"
            style={{
              background: adminKeyPresent ? "#07150f" : "#0d0d18",
              border: `1px solid ${adminKeyPresent ? "#16a34a55" : "#1e1e2a"}`,
              color: adminKeyPresent ? "#4ade80" : "#6b7280",
            }}
          >
            Admin {adminKeyPresent ? "ON" : "OFF"}
          </button>

          {/* Toggle Command / Advanced */}
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
            {(["actions", "crypto"] as const).map((u) => (
              <button key={u} onClick={() => {
                setUniverse(u);
                setEdgeHorizon(24);
                setEdgeOverlayNotice(null);
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
              <button
                onClick={() => switchStrategy("standard")}
                className="px-3 py-1.5 text-xs font-semibold transition-all"
                style={{
                  background: strategy === "standard" ? "#1e1e3a" : "#0d0d18",
                  color: strategy === "standard" ? "#818cf8" : "#4b5563",
                }}
              >
                📊 Standard
              </button>
            </div>
          )}

          {/* Onglets vue — Pro seulement */}
          {uiMode === "pro" && (
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
                {([
                  ["table", "📋 Tableau"],
                  ...(!isCrypto ? [["trades", "📌 Trades"]] as [typeof view, string][] : []),
                ] as [typeof view, string][]).map(([v, label], idx, arr) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className="px-3 py-1.5 text-xs font-medium transition-all"
                    style={{
                      background: view === v ? "#1e1e3a" : "#0d0d18",
                      color: view === v ? "#818cf8" : "#4b5563",
                      borderRight: idx < arr.length - 1 ? "1px solid #1e1e2a" : undefined,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <details className="relative">
                <summary
                  className="list-none cursor-pointer select-none px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-widest"
                  style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#a78bfa" }}
                >
                  Recherche
                </summary>
                <div
                  className="absolute right-0 mt-2 z-20 w-56 rounded-xl p-2 shadow-2xl"
                  style={{ background: "#0b0b14", border: "1px solid #1e1e2a" }}
                >
                  <div className="px-2 py-1 text-[10px] font-black uppercase tracking-widest text-gray-500">Menu</div>
                  {(!isCrypto ? [
                    ["dynamic", "⚡ Signaux"],
                    ["signals", "📈 Tracking"],
                    ["backtest", "🧪 Backtest"],
                    ["lab", "🧬 Strategy Lab"],
                    ["conservative", "🛡 Conservative"],
                    ["24", "Edge 24m"],
                    ["36", "Edge 36m"],
                  ] : [
                    ["backtest", "🧪 Backtest"],
                    ["lab", "🧬 Strategy Lab"],
                  ] as [string, string][]).map(([v, label]) => (
                    <button
                      key={v}
                      onClick={() => {
                        if (v === "24") {
                          setEdgeHorizon(24);
                          setView("table");
                        } else if (v === "36") {
                          setEdgeHorizon(36);
                          setView("table");
                        } else {
                          setView(v as typeof view);
                        }
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                      style={{ color: "#d1d5db" }}
                    >
                      {label}
                    </button>
                  ))}
                  {!isCrypto && (
                    <button
                      onClick={() => switchStrategy("conservative")}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                      style={{ color: strategy === "conservative" ? "#4ade80" : "#d1d5db" }}
                    >
                      Conservative
                    </button>
                  )}
                  {!isCrypto && (
                    <button
                      onClick={() => setEdgeMode(edgeMode === "v2" ? "v1" : "v2")}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                      style={{ color: edgeMode === "v2" ? "#60a5fa" : "#d1d5db" }}
                    >
                      Edge v2 Research
                    </button>
                  )}
                  <button
                    onClick={() => setShowApiStatus(true)}
                    className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                    style={{ color: "#d1d5db" }}
                  >
                    API
                  </button>
                  {!isCrypto && (
                    <button
                      onClick={() => setView("table")}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                      style={{ color: "#d1d5db" }}
                    >
                      Edge ?
                    </button>
                  )}
                </div>
              </details>
            </div>
          )}

          <ApiStatusDot onClick={() => setShowApiStatus(true)} />

          {!isCrypto && uiMode === "pro" && view === "table" && (
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
                {[24, 36].map(period => (
                  <button
                    key={period}
                    onClick={() => setEdgeHorizon(period as EdgeHorizon)}
                    className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                    style={{
                      background: edgeHorizon === period ? (period === 36 ? "#1a1400" : "#0a1a0a") : "#0d0d18",
                      color: edgeHorizon === period ? (period === 36 ? "#f59e0b" : "#4ade80") : "#4b5563",
                      borderRight: period === 24 ? "1px solid #1e1e2a" : undefined,
                    }}
                  >
                    Edge {period}m
                  </button>
                ))}
              </div>
              <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
                {(["v1", "v2"] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => setEdgeMode(mode)}
                    className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                    style={{
                      background: edgeMode === mode ? (mode === "v2" ? "#131f1a" : "#111120") : "#0d0d18",
                      color: edgeMode === mode ? (mode === "v2" ? "#60a5fa" : "#a5b4fc") : "#4b5563",
                      borderRight: mode === "v1" ? "1px solid #1e1e2a" : undefined,
                    }}
                  >
                    {mode === "v1" ? "Edge v1" : "Edge v2 Research"}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Bouton Recalculate Edge — mode Advanced uniquement */}
          {uiMode === "pro" && view === "table" && (
            <button
              onClick={recalculateEdge}
              disabled={edgeComputing}
              title={edgeHorizon === 36
                ? "Recalculer l'edge 36m pour l'analyse avancée visible"
                : `Recalculer l'edge historique par ticker (cache 24h)\nCouverture actuelle : ${edgeCoverage.toFixed(0)}%`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-40"
              style={{
                background: edgeHorizon === 36 ? "#1a1400" : "#0a1a0a",
                border: `1px solid ${edgeHorizon === 36 ? "#f59e0b44" : "#16a34a44"}`,
                color: edgeComputing ? (edgeHorizon === 36 ? "#f59e0b88" : "#4ade8088") : (edgeHorizon === 36 ? "#f59e0b" : "#4ade80"),
              }}
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
              onClick={() => void repairCaches()}
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
      {successNotice && (
        <div
          className="rounded-full px-3 py-2 mb-4 inline-flex items-center gap-2 max-w-full"
          style={{ background: "#07140d", border: "1px solid #10b98155" }}
        >
          <span className="text-sm">✅</span>
          <div className="min-w-0">
            <p className="text-[10px] font-black uppercase tracking-widest text-emerald-300 truncate">
              {successNotice}
            </p>
            <p className="text-[10px] text-emerald-100/70 truncate">
              Les données sont chaudes. L&apos;app est prête.
            </p>
          </div>
        </div>
      )}

      {repairNotice && !successNotice && (
        <div className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap"
          style={{ background: "#0f172a", border: "1px solid #334155" }}>
          <span className="text-sm">🛠️</span>
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-slate-200">
              {repairNotice}
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {infoNotice ?? "Réparation en cours. Les dernières données visibles restent affichées."}
            </p>
          </div>
        </div>
      )}

      {dataErrorNotice && (
        <div className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap"
          style={{ background: "#1a0f06", border: "1px solid #f59e0b55" }}>
          <span className="text-sm">⚠️</span>
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-amber-300">
              {dataErrorNotice}
            </p>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Les dernières données connues sont conservées côté navigateur.
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={repairCaches}
              disabled={!adminKeyPresent}
              className="px-3 py-1.5 rounded-lg text-xs font-bold disabled:opacity-50"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: adminKeyPresent ? "#f59e0b" : "#6b7280" }}
            >
              {adminKeyPresent ? "Réparer les caches" : "Admin requis"}
            </button>
            <button
              onClick={refreshPricesOnly}
              className="px-3 py-1.5 rounded-lg text-xs font-bold"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#10b981" }}
            >
              Rafraîchir prix seulement
            </button>
            <button
              onClick={restoreFromCache}
              className="px-3 py-1.5 rounded-lg text-xs font-bold"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#f59e0b" }}
            >
              Recharger depuis cache
            </button>
          </div>
        </div>
      )}

      {adminErrorNotice && (
        <div className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3"
          style={{ background: "#1a0a0a", border: "1px solid #7f1d1d66" }}>
          <span className="text-sm">🔒</span>
          <div>
            <p className="text-xs font-black text-red-400 uppercase tracking-widest">
              {adminErrorNotice}
            </p>
            <p className="text-[11px] text-red-200 mt-0.5">
              Cette action nécessite une clé admin côté backend. L&apos;interface reste utilisable sans recalcul protégé.
            </p>
          </div>
        </div>
      )}

        <DataFreshnessPanel
          freshness={freshness}
          onFullRefresh={() => void repairCaches()}
          onPriceRefresh={refreshPricesOnly}
          loading={loading || screenerRefreshing}
          priceRefreshing={priceRefreshing}
          adminActive={adminKeyPresent}
        />

      {uiMode === "simple" && (
        isCrypto ? (
          <CryptoCommandCenter
            data={dataWithLivePrices}
            loading={loading}
            screenerNotice={screenerNotice}
            onRefresh={() => void repairCaches()}
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
            onRefresh={() => void repairCaches()}
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
            {(!safeNumber(cryptoRegime.btc_price) || !safeNumber(cryptoRegime.eth_price)) && (
              <p className="text-[10px] text-red-300 mt-1">
                Données BTC/ETH indisponibles — régime crypto non fiable
              </p>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400 flex-wrap ml-auto">
            <span>BTC <strong className="text-white">{safeNumber(cryptoRegime.btc_price) ? `$${formatCryptoPrice("BTC", cryptoRegime.btc_price)}` : "—"}</strong></span>
            <span>ETH <strong className="text-white">{safeNumber(cryptoRegime.eth_price) ? `$${formatCryptoPrice("ETH", cryptoRegime.eth_price)}` : "—"}</strong></span>
            <span>Breadth <strong className="text-cyan-300">{safePercent(cryptoRegime.breadth_pct, 0)}</strong></span>
            <span>BTC Dom. <strong className="text-cyan-300">{safePercent(cryptoRegime.btc_dominance, 1)}</strong></span>
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
          {!isCrypto && edgeHorizon === 36 && (
            <div
              className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap"
              style={{ background: "#1a1400", border: "1px solid #f59e0b44" }}
            >
              <span className="text-xs font-black uppercase tracking-widest text-amber-400">
                Edge horizon : 36m
              </span>
              <span className="text-xs text-amber-200">
                Mode analyse avancée - horizon plus long, risque d'overfit à surveiller.
              </span>
              {edgeOverlayLoading && (
                <span className="ml-auto text-xs text-amber-300">Calcul edge 36m en cours...</span>
              )}
            </div>
          )}

          {edgeOverlayNotice && !isCrypto && edgeHorizon === 36 && (
            <div
              className="rounded-xl px-4 py-2.5 mb-4 text-xs"
              style={{ background: "#0d0d18", border: "1px solid #1e1e2a", color: "#9ca3af" }}
            >
              {edgeOverlayNotice}
            </div>
          )}

          {edgeV2Notice && !isCrypto && edgeMode === "v2" && (
            <div
              className="rounded-xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap"
              style={{ background: "#07131f", border: "1px solid #1d4ed844" }}
            >
              <span className="text-sm">🔬</span>
              <div>
                <p className="text-xs font-black uppercase tracking-widest text-sky-300">
                  {edgeV2Notice}
                </p>
                <p className="text-[11px] text-sky-100/70 mt-0.5">
                  Edge v2 est un modèle de recherche. Il n&apos;autorise pas les trades. Le Command Center reste basé sur Edge v1.
                </p>
              </div>
            </div>
          )}

          {isCrypto && uiMode === "pro" && view === "table" && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid #1e1e2a" }}>
                <button
                  onClick={() => setCryptoResearchMode(false)}
                  className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                  style={{
                    background: !cryptoResearchMode ? "#111120" : "#0d0d18",
                    color: !cryptoResearchMode ? "#a5b4fc" : "#4b5563",
                    borderRight: "1px solid #1e1e2a",
                  }}
                >
                  Edge v1
                </button>
                <button
                  onClick={() => setCryptoResearchMode(true)}
                  className="px-3 py-1.5 text-xs font-black uppercase tracking-widest transition-all"
                  style={{
                    background: cryptoResearchMode ? "#131f1a" : "#0d0d18",
                    color: cryptoResearchMode ? "#60a5fa" : "#4b5563",
                  }}
                >
                  Crypto Research V2
                </button>
              </div>
              <span className="text-[10px] font-black uppercase tracking-widest text-gray-500">
                Recherche uniquement — n&apos;autorise aucun trade
              </span>
            </div>
          )}

          {isCrypto && uiMode === "pro" && view === "table" && (
            <CryptoResearchV2Panel regime={cryptoRegime} />
          )}

          <Top5Cards data={activeTableData} scope={isCrypto ? "crypto" : "actions"} cryptoRegime={cryptoRegime} />

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
          <ScreenerTable
            data={filtered}
            showEdge={true}
            researchMode={
              (!isCrypto && uiMode === "pro" && view === "table" && edgeMode === "v2") ||
              (isCrypto && uiMode === "pro" && view === "table" && cryptoResearchMode)
            }
            scope={isCrypto ? "crypto" : "actions"}
          />
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

