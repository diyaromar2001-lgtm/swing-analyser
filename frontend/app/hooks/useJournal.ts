"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ensureApiResponse, getAdminApiKey, getAdminHeaders, getApiUrl, isAdminProtectedError } from "../lib/api";
import { JournalTrade } from "../types";

const JOURNAL_CACHE_KEY = "trade_journal_cache_v1";
const JOURNAL_STATS_KEY = "trade_journal_stats_v1";

export interface JournalStats {
  total_trades: number;
  open_trades: number;
  planned_trades: number;
  watchlist_trades: number;
  closed_trades: number;
  win_rate: number;
  total_pnl: number;
  average_r: number;
  best_trade: number;
  worst_trade: number;
  exposure_current: number;
  risk_open_total: number;
  pnl_latent: number | null;
  max_positions_actions: number;
  max_positions_crypto: number;
  realized_count: number;
  average_position_size: number;
}

export interface JournalTradeInput {
  id?: string;
  universe?: string;
  symbol?: string;
  sector?: string;
  setup_grade?: string;
  signal_type?: string;
  strategy_name?: string;
  edge_status?: string;
  final_decision?: string;
  execution_authorized?: boolean;
  status?: string;
  direction?: string;
  entry_plan?: number | null;
  entry_price?: number | null;
  stop_loss?: number | null;
  tp1?: number | null;
  tp2?: number | null;
  trailing_stop?: number | null;
  position_size?: string | null;
  risk_amount?: number | null;
  risk_pct?: number | null;
  quantity?: number | null;
  opened_at?: string | null;
  closed_at?: string | null;
  exit_price?: number | null;
  exit_reason?: string | null;
  pnl_amount?: number | null;
  pnl_pct?: number | null;
  r_multiple?: number | null;
  notes?: string | null;
  source_snapshot_json?: unknown;
}

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage quota / access errors
  }
}

function num(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

function str(value: unknown, fallback = ""): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function normalizeStatus(value: unknown): JournalTrade["status"] {
  const status = str(value, "WATCHLIST").toUpperCase();
  if (status === "OPEN" || status === "WATCHLIST" || status === "PLANNED" || status === "CLOSED" || status === "CANCELLED") {
    return status;
  }
  return "WATCHLIST";
}

function normalizeTrade(raw: any): JournalTrade {
  const symbol = str(raw?.symbol ?? raw?.ticker, "—").toUpperCase();
  const status = normalizeStatus(raw?.status);
  return {
    id: str(raw?.id, `${symbol}_${Date.now()}`),
    ticker: symbol,
    symbol,
    universe: str(raw?.universe ?? raw?.asset_scope, "ACTIONS").toUpperCase() as "ACTIONS" | "CRYPTO",
    sector: str(raw?.sector, "—"),
    setup_grade: str(raw?.setup_grade, "B"),
    signal_type: str(raw?.signal_type, "—"),
    strategy: str(raw?.strategy_name ?? raw?.strategy, "UNKNOWN"),
    strategy_name: str(raw?.strategy_name ?? raw?.strategy, "UNKNOWN"),
    edge_status: str(raw?.edge_status ?? raw?.ticker_edge_status, "NO_EDGE"),
    final_decision: str(raw?.final_decision, "WAIT"),
    execution_authorized: Boolean(raw?.execution_authorized),
    status,
    direction: str(raw?.direction, "LONG"),
    entry_plan: num(raw?.entry_plan ?? raw?.planned_entry),
    planned_entry: num(raw?.entry_plan ?? raw?.planned_entry),
    entry_price: num(raw?.entry_price ?? raw?.price_entry),
    price_entry: num(raw?.entry_price ?? raw?.price_entry),
    stop_loss: num(raw?.stop_loss),
    tp1: num(raw?.tp1),
    tp2: num(raw?.tp2),
    trailing_stop: num(raw?.trailing_stop),
    position_size: str(raw?.position_size, "—"),
    risk_amount: num(raw?.risk_amount),
    risk_pct: num(raw?.risk_pct),
    quantity: num(raw?.quantity),
    opened_at: raw?.opened_at ?? null,
    closed_at: raw?.closed_at ?? null,
    exit_price: raw?.exit_price ?? null,
    exit_reason: raw?.exit_reason ?? raw?.reason_exit ?? null,
    pnl_amount: raw?.pnl_amount ?? raw?.pnl_usd ?? null,
    pnl_pct: raw?.pnl_pct ?? null,
    r_multiple: raw?.r_multiple ?? null,
    notes: str(raw?.notes ?? raw?.note_entry, ""),
    note_entry: str(raw?.notes ?? raw?.note_entry, ""),
    note_exit: str(raw?.note_exit, ""),
    date_entry: raw?.opened_at ?? raw?.date_entry ?? raw?.created_at ?? null,
    date_exit: raw?.closed_at ?? raw?.date_exit ?? null,
    source_snapshot_json: raw?.source_snapshot_json ?? raw?.source_snapshot ?? null,
    confidence: num(raw?.confidence),
    score: num(raw?.score),
    regime: str(raw?.regime, "UNKNOWN"),
    rr_ratio: num(raw?.rr_ratio),
    broker: str(raw?.broker, "—"),
    fees: num(raw?.fees),
    pnl_usd: num(raw?.pnl_amount ?? raw?.pnl_usd),
    duration_days: raw?.duration_days ?? null,
    setup_status: raw?.setup_status ?? undefined,
    category: raw?.category ?? "WATCHLIST",
    error: raw?.error,
  };
}

function normalizeTrades(raw: any): JournalTrade[] {
  if (!raw) return [];
  const list = Array.isArray(raw) ? raw : Array.isArray(raw?.trades) ? raw.trades : [];
  return list.map(normalizeTrade);
}

function mergeTradeLists(prev: JournalTrade[], next: JournalTrade[]) {
  const byId = new Map<string, JournalTrade>();
  [...prev, ...next].forEach(trade => {
    if (!trade?.id) return;
    byId.set(trade.id, trade);
  });
  return Array.from(byId.values()).sort((a, b) => {
    const aDate = new Date(a.date_entry ?? a.opened_at ?? 0).getTime();
    const bDate = new Date(b.date_entry ?? b.opened_at ?? 0).getTime();
    return bDate - aDate;
  });
}

function safeStatusForDuplicate(status: string) {
  return status === "OPEN" || status === "PLANNED";
}

function makeId(prefix: string, symbol: string) {
  return `${prefix}_${symbol}_${Date.now()}`;
}

async function fetchJournal(tradeFilter?: { universe?: string; status?: string; symbol?: string }) {
  const params = new URLSearchParams();
  if (tradeFilter?.universe) params.set("universe", tradeFilter.universe);
  if (tradeFilter?.status) params.set("status", tradeFilter.status);
  if (tradeFilter?.symbol) params.set("symbol", tradeFilter.symbol);
  const url = `${getApiUrl()}/api/trade-journal${params.toString() ? `?${params.toString()}` : ""}`;
  const response = await fetch(url, { headers: { ...getAdminHeaders() }, cache: "no-store" });
  await ensureApiResponse(response);
  return normalizeTrades(await response.json());
}

async function fetchStats() {
  const response = await fetch(`${getApiUrl()}/api/trade-journal/stats`, { headers: { ...getAdminHeaders() }, cache: "no-store" });
  await ensureApiResponse(response);
  return (await response.json()) as JournalStats;
}

// ── CRYPTO TRADABLE V1 HELPER ────────────────────────────────────────────
/**
 * Check if a crypto trade can be opened (PLANNED/OPEN states).
 * Only applies to crypto assets — actions ignore this check.
 * WATCHLIST has no restrictions.
 */
export function canOpenCryptoTrade(
  row: any,
  intent: string,
): { allowed: boolean; reason?: string } {
  // Only check for PLANNED/OPEN, not WATCHLIST
  if (intent === "WATCHLIST") {
    return { allowed: true };
  }

  // Only apply crypto auth check to crypto assets
  if (row.asset_scope !== "CRYPTO") {
    return { allowed: true };
  }

  // For PLANNED/OPEN on crypto: require execution authorization
  if (row.crypto_execution_authorized !== true) {
    return {
      allowed: false,
      reason: `Crypto trade not authorized. ${
        row.crypto_blocked_reasons?.length > 0
          ? `Reasons: ${row.crypto_blocked_reasons.join("; ")}`
          : "Review setup requirements."
      }`,
    };
  }

  // For OPEN specifically: also check that decision is executable
  if (intent === "OPEN") {
    const decision = row.crypto_tradable_decision?.toUpperCase() || "";
    if (!["BUY NOW", "BUY NEAR ENTRY"].includes(decision)) {
      return {
        allowed: false,
        reason: `Setup decision is not actionable: ${row.crypto_tradable_decision || "unknown"}. Can only open if decision is BUY NOW or BUY NEAR ENTRY.`,
      };
    }
  }

  return { allowed: true };
}

export function useJournal() {
  const [trades, setTrades] = useState<JournalTrade[]>(() => readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []));
  const [stats, setStats] = useState<JournalStats>(() => readJson<JournalStats>(JOURNAL_STATS_KEY, {
    total_trades: 0,
    open_trades: 0,
    planned_trades: 0,
    watchlist_trades: 0,
    closed_trades: 0,
    win_rate: 0,
    total_pnl: 0,
    average_r: 0,
    best_trade: 0,
    worst_trade: 0,
    exposure_current: 0,
    risk_open_total: 0,
    pnl_latent: null,
    max_positions_actions: 5,
    max_positions_crypto: 3,
    realized_count: 0,
    average_position_size: 0,
  }));
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncError, setLastSyncError] = useState<string | null>(null);

  const persistTrades = useCallback((next: JournalTrade[]) => {
    setTrades(next);
    writeJson(JOURNAL_CACHE_KEY, next);
  }, []);

  const persistStats = useCallback((next: JournalStats) => {
    setStats(next);
    writeJson(JOURNAL_STATS_KEY, next);
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      const next = await fetchStats();
      persistStats(next);
      return next;
    } catch {
      return null;
    }
  }, [persistStats]);

  const refreshJournal = useCallback(async (filters?: { universe?: string; status?: string; symbol?: string }) => {
    setIsSyncing(true);
    setLastSyncError(null);
    try {
      const next = await fetchJournal(filters);
      persistTrades(next.length ? next : readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []));
      await refreshStats();
      return next;
    } catch (error) {
      if (!getAdminApiKey()) {
        setLastSyncError(null);
        return null;
      }
      if (!isAdminProtectedError(error)) {
        const fallback = readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []);
        if (fallback.length) setTrades(fallback);
      }
      const message = error instanceof Error ? error.message : "sync_failed";
      setLastSyncError(message);
      return null;
    } finally {
      setIsSyncing(false);
    }
  }, [persistTrades, refreshStats]);

  useEffect(() => {
    void refreshJournal();
  }, [refreshJournal]);

  const allTrades = trades;
  const openTrades = useMemo(() => allTrades.filter(t => t.status === "OPEN"), [allTrades]);
  const plannedTrades = useMemo(() => allTrades.filter(t => t.status === "PLANNED"), [allTrades]);
  const watchlistTrades = useMemo(() => allTrades.filter(t => t.status === "WATCHLIST"), [allTrades]);
  const closedTrades = useMemo(() => allTrades.filter(t => t.status === "CLOSED"), [allTrades]);

  const syncLocalAndRemote = useCallback(async (trade: JournalTradeInput, mutation: (id: string, payload: Record<string, unknown>) => Promise<JournalTrade | null>) => {
    const id = str(trade.id, makeId(str(trade.universe, "ACTIONS"), str(trade.symbol, "TRADE")));
    const normalized: JournalTrade = normalizeTrade({
      ...trade,
      id,
      ticker: trade.symbol ?? trade.id ?? "TRADE",
      source_snapshot_json: trade.source_snapshot_json ?? trade,
    });

    const next = mergeTradeLists(trades, [normalized]);
    persistTrades(next);

    try {
      const remote = await mutation(id, trade as Record<string, unknown>);
      if (remote) {
        const merged = mergeTradeLists(readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, next), [normalizeTrade(remote)]);
        persistTrades(merged);
      }
    } catch (error) {
      if (!isAdminProtectedError(error)) {
        // keep optimistic local state
      }
    }

    await refreshStats();
    return normalized;
  }, [persistTrades, refreshStats, trades]);

  const addTrade = useCallback(async (trade: JournalTradeInput) => {
    const symbol = str(trade.symbol, str((trade as any).ticker, "TRADE")).toUpperCase();
    const universe = str(trade.universe, "ACTIONS").toUpperCase();
    const status = normalizeStatus(trade.status);
    const duplicate = trades.find(t => t.symbol === symbol && t.universe === universe && safeStatusForDuplicate(t.status));
    const payload = {
      ...trade,
      symbol,
      ticker: symbol,
      universe,
      status,
      id: trade.id ?? duplicate?.id ?? makeId(universe, symbol),
      execution_authorized: trade.execution_authorized ?? status === "OPEN",
      source_snapshot_json: trade.source_snapshot_json ?? trade,
    };

    if (duplicate && safeStatusForDuplicate(status)) {
      const merged = normalizeTrade({ ...duplicate, ...payload, id: duplicate.id });
      persistTrades(mergeTradeLists(trades.filter(t => t.id !== duplicate.id), [merged]));
      await refreshStats();
      return merged;
    }

    const stored = await syncLocalAndRemote(payload, async (id, body) => {
      try {
        const response = await fetch(`${getApiUrl()}/api/trade-journal`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...getAdminHeaders(),
          },
          cache: "no-store",
          body: JSON.stringify(body),
        });
        await ensureApiResponse(response);
        const json = await response.json();
        return normalizeTrade(json.trade ?? json);
      } catch (error) {
        if (isAdminProtectedError(error)) throw error;
        return null;
      }
    });
    return stored;
  }, [persistTrades, refreshStats, syncLocalAndRemote, trades]);

  const updateTrade = useCallback(async (id: string, updates: Record<string, unknown>) => {
    const current = trades.find(t => t.id === id);
    if (!current) return null;
    const merged = normalizeTrade({ ...current, ...updates, id });
    persistTrades(mergeTradeLists(trades.filter(t => t.id !== id), [merged]));
    try {
      const response = await fetch(`${getApiUrl()}/api/trade-journal/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...getAdminHeaders(),
        },
        cache: "no-store",
        body: JSON.stringify(updates),
      });
      await ensureApiResponse(response);
      const json = await response.json();
      const remote = normalizeTrade(json.trade ?? json);
      persistTrades(mergeTradeLists(readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []), [remote]));
      await refreshStats();
      return remote;
    } catch (error) {
      if (!isAdminProtectedError(error)) {
        await refreshStats();
      }
      return merged;
    }
  }, [persistTrades, refreshStats, trades]);

  const openTrade = useCallback(async (id: string, payload: JournalTradeInput = {}) => {
    const current = trades.find(t => t.id === id);
    if (!current) return null;
    const next = normalizeTrade({
      ...current,
      ...payload,
      id,
      status: "OPEN",
      opened_at: payload.opened_at ?? current.opened_at ?? new Date().toISOString(),
      execution_authorized: true,
    });
    persistTrades(mergeTradeLists(trades.filter(t => t.id !== id), [next]));
    try {
      const response = await fetch(`${getApiUrl()}/api/trade-journal/${encodeURIComponent(id)}/open`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAdminHeaders(),
        },
        cache: "no-store",
        body: JSON.stringify(payload),
      });
      await ensureApiResponse(response);
      const json = await response.json();
      const remote = normalizeTrade(json.trade ?? json);
      persistTrades(mergeTradeLists(readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []), [remote]));
      await refreshStats();
      return remote;
    } catch (error) {
      if (!isAdminProtectedError(error)) {
        await refreshStats();
      }
      return next;
    }
  }, [persistTrades, refreshStats, trades]);

  const closeTrade = useCallback(async (id: string, payload: Record<string, unknown>) => {
    const current = trades.find(t => t.id === id);
    if (!current) return null;
    const next = normalizeTrade({ ...current, ...payload, id, status: "CLOSED" });
    persistTrades(mergeTradeLists(trades.filter(t => t.id !== id), [next]));
    try {
      const response = await fetch(`${getApiUrl()}/api/trade-journal/${encodeURIComponent(id)}/close`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAdminHeaders(),
        },
        cache: "no-store",
        body: JSON.stringify(payload),
      });
      await ensureApiResponse(response);
      const json = await response.json();
      const remote = normalizeTrade(json.trade ?? json);
      persistTrades(mergeTradeLists(readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []), [remote]));
      await refreshStats();
      return remote;
    } catch (error) {
      if (!isAdminProtectedError(error)) {
        await refreshStats();
      }
      return next;
    }
  }, [persistTrades, refreshStats, trades]);

  const deleteTrade = useCallback(async (id: string) => {
    const current = trades.find(t => t.id === id);
    if (!current) return null;
    const cancelled = normalizeTrade({ ...current, status: "CANCELLED", id });
    persistTrades(mergeTradeLists(trades.filter(t => t.id !== id), [cancelled]));
    try {
      const response = await fetch(`${getApiUrl()}/api/trade-journal/${encodeURIComponent(id)}`, {
        method: "DELETE",
        headers: { ...getAdminHeaders() },
        cache: "no-store",
      });
      await ensureApiResponse(response);
      const json = await response.json();
      const remote = normalizeTrade(json.trade ?? json);
      persistTrades(mergeTradeLists(readJson<JournalTrade[]>(JOURNAL_CACHE_KEY, []), [remote]));
      await refreshStats();
      return remote;
    } catch (error) {
      if (!isAdminProtectedError(error)) {
        await refreshStats();
      }
      return cancelled;
    }
  }, [persistTrades, refreshStats, trades]);

  const addNote = useCallback(async (id: string, note: string) => {
    return updateTrade(id, { notes: note });
  }, [updateTrade]);

  const isTickerActive = useCallback((ticker: string, universe?: string) => {
    const normalized = ticker.toUpperCase();
    return allTrades.some(t =>
      t.symbol === normalized
      && (!universe || t.universe === universe.toUpperCase())
      && (t.status === "OPEN" || t.status === "PLANNED"),
    );
  }, [allTrades]);

  return {
    trades: allTrades,
    activeTrades: openTrades,
    plannedTrades,
    watchlistTrades,
    closedTrades,
    stats,
    isSyncing,
    lastSyncError,
    refreshJournal,
    refreshStats,
    addTrade,
    updateTrade,
    openTrade,
    closeTrade,
    deleteTrade,
    addNote,
    isTickerActive,
  };
}
