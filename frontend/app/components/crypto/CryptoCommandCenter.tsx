"use client";

import { useEffect, useMemo, useState } from "react";
import { CryptoRegimeEngine, TickerResult } from "../../types";
import { getApiUrl } from "../../lib/api";
import { formatCryptoPrice, isCryptoDefensiveRegime } from "../../lib/cryptoFormat";
import { CryptoTradePlan } from "./CryptoTradePlan";

const API_URL = getApiUrl();

function hasValidatedEdge(row: TickerResult) {
  return row.ticker_edge_status === "STRONG_EDGE" || row.ticker_edge_status === "VALID_EDGE";
}

function isCritical(row: TickerResult) {
  return row.ticker_edge_status === "OVERFITTED" || row.overfit_warning || row.setup_grade === "REJECT" || row.setup_status === "INVALID";
}

function edgeLabel(status?: string | null) {
  if (status === "NO_EDGE") return "Edge non validé";
  if (status === "OVERFITTED") return "Backtest suspect — éviter";
  if (status === "WEAK_EDGE") return "Edge faible";
  if (status === "STRONG_EDGE") return "Edge robuste";
  if (status === "VALID_EDGE") return "Edge validé";
  return status ?? "—";
}

function safeNumber(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function safePercent(value?: number | null, digits = 1) {
  const num = safeNumber(value);
  return num === null ? "—" : `${num.toFixed(digits)}%`;
}

export function CryptoCommandCenter({
  data,
  loading,
  screenerNotice,
  onRefresh,
  onRefreshPrices,
  onAdvancedView,
  onGoToLab,
}: {
  data: TickerResult[];
  loading: boolean;
  screenerNotice?: { kind: "timeout" | "refresh-failed" | "empty-cache"; message: string } | null;
  onRefresh: () => void;
  onRefreshPrices: () => void;
  onAdvancedView: () => void;
  onGoToLab: () => void;
}) {
  const [regime, setRegime] = useState<CryptoRegimeEngine | null>(null);
  const [selected, setSelected] = useState<TickerResult | null>(null);
  const [marketPrices, setMarketPrices] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch(`${API_URL}/api/crypto/regime`, { cache: "no-store" })
      .then((r) => r.json())
      .then(setRegime)
      .catch(() => null);
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/api/crypto/prices?symbols=BTC,ETH`, { cache: "no-store" })
      .then((r) => r.json())
      .then((list: Array<{ ticker: string; price: number }>) => {
        const next: Record<string, number> = {};
        for (const item of list ?? []) next[item.ticker] = item.price;
        setMarketPrices(next);
      })
      .catch(() => null);
  }, []);

  const tradeable = useMemo(() => {
    return data
      .filter((row) => hasValidatedEdge(row))
      .filter((row) => !isCritical(row))
      .filter((row) => !["SKIP", "NO_TRADE", "WATCHLIST"].includes(row.final_decision ?? "WAIT"))
      .sort((a, b) => (b.final_score ?? b.score) - (a.final_score ?? a.score))
      .slice(0, 3);
  }, [data]);

  const technicalWatchlist = useMemo(() => {
    return data
      .filter((row) => !hasValidatedEdge(row))
      .filter((row) => !isCritical(row))
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);
  }, [data]);

  const noTrade = tradeable.length === 0 || !regime || ["CRYPTO_BEAR", "CRYPTO_HIGH_VOLATILITY", "CRYPTO_NO_TRADE"].includes(regime.crypto_regime);
  const defensiveRegime = isCryptoDefensiveRegime(regime?.crypto_regime);
  const activeLabel = regime?.active_strategy === "NO_TRADE" ? "NO TRADE" : regime?.active_crypto_strategies?.[0]?.replaceAll("_", " ") ?? "—";
  const primaryCards = defensiveRegime ? technicalWatchlist : tradeable;
  const btcDisplay = regime && safeNumber(regime.btc_price) && regime.btc_price > 0 ? regime.btc_price : safeNumber(marketPrices.BTC);
  const ethDisplay = regime && safeNumber(regime.eth_price) && regime.eth_price > 0 ? regime.eth_price : safeNumber(marketPrices.ETH);
  const missingBtcEth = !btcDisplay || !ethDisplay;
  const regimeTrustWarning = missingBtcEth ? "Données BTC/ETH indisponibles — régime crypto non fiable" : null;
  const hasPreviousData = screenerNotice?.kind === "refresh-failed" || screenerNotice?.kind === "timeout";
  const emptyCacheMessage = screenerNotice?.kind === "empty-cache"
    ? screenerNotice.message
    : "Aucune donnée crypto en cache. Lancez une réparation des caches.";
  const effectiveNoTrade = noTrade || missingBtcEth;

  if (!loading && data.length === 0) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-bold text-gray-700 uppercase tracking-widest">
            0 cryptos analysées · aucun cache exploitable
          </p>
          <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full" style={{ background: "#130404", border: "1px solid #7f1d1d", color: "#fca5a5" }}>
          Crypto = surveillance uniquement si r?gime d?fensif
        </span>
        <div className="flex items-center gap-2">
            <button onClick={onRefreshPrices} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#10b981" }}>
              Prix seulement
            </button>
            <button onClick={onRefresh} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40" style={{ background: "#1a1a2e", border: "1px solid #2a2a4e", color: "#818cf8" }}>
              {loading ? "Loading…" : "Réessayer depuis cache"}
            </button>
            <button onClick={onAdvancedView} className="px-3 py-1.5 rounded-lg text-xs font-medium" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#4b5563" }}>
              Advanced →
            </button>
          </div>
        </div>

        <div className="rounded-2xl p-6" style={{ background: "#120a0a", border: "1px solid #7f1d1d66" }}>
          <p className="text-[10px] font-black text-red-400 uppercase tracking-widest mb-2">
            {emptyCacheMessage}
          </p>
          <p className="text-sm text-red-200">
            Le fast screener Crypto n&apos;a pas renvoyé de liste exploitable. Vous pouvez lancer une réparation des caches pour récupérer les dernières données disponibles.
          </p>
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <button onClick={onRefresh} className="px-3 py-1.5 rounded-lg text-xs font-bold" style={{ background: "#2a1220", border: "1px solid #ef444455", color: "#fca5a5" }}>
              Réparer les caches
            </button>
            <button onClick={onRefreshPrices} className="px-3 py-1.5 rounded-lg text-xs font-bold" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#10b981" }}>
              Rafraîchir prix seulement
            </button>
            <button onClick={onGoToLab} className="px-3 py-1.5 rounded-lg text-xs font-bold" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#4b5563" }}>
              Ouvrir le Lab
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {selected && <CryptoTradePlan row={selected} onClose={() => setSelected(null)} />}

      {/* Avertissement global: Aucune stratégie crypto validée */}
      <div className="rounded-xl p-4" style={{ background: "#2a1111", border: "1px solid #ef444455" }}>
        <p className="text-xs font-black text-red-300 uppercase tracking-widest mb-1">⚠️ NO VALIDATED CRYPTO EDGE</p>
        <p className="text-sm text-red-200">
          Aucune stratégie crypto n&apos;est actuellement validée par backtest Phase 1. <strong>Crypto = observation uniquement.</strong> Les données sont disponibles à titre informatif. Aucun trade crypto n&apos;est autorisé.
        </p>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold text-gray-700 uppercase tracking-widest">
          {data.length} cryptos analysées · {tradeable.length} setup{tradeable.length > 1 ? "s" : ""} avec edge validé
        </p>
        <div className="flex items-center gap-2">
          <button onClick={onRefreshPrices} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#10b981" }}>
            Prix seulement
          </button>
          <button onClick={onRefresh} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40" style={{ background: "#1a1a2e", border: "1px solid #2a2a4e", color: "#818cf8" }}>
            {loading ? "Loading…" : "Réessayer depuis cache"}
          </button>
          <button onClick={onAdvancedView} className="px-3 py-1.5 rounded-lg text-xs font-medium" style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#4b5563" }}>
            Advanced →
          </button>
        </div>
      </div>

        <div className="rounded-xl px-5 py-3 flex items-center gap-5 flex-wrap" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Marché</p>
          <p className="text-xs font-black" style={{ color: effectiveNoTrade ? "#ef4444" : "#10b981" }}>24/7 Crypto</p>
        </div>
        <div className="w-px h-5 hidden sm:block" style={{ background: "#1a1a2e" }} />
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Régime</p>
          <p className="text-xs font-black text-white">{regime?.regime_label ?? "—"}</p>
        </div>
        <div className="w-px h-5 hidden sm:block" style={{ background: "#1a1a2e" }} />
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">BTC</p>
          <p className="text-xs font-black text-white">{btcDisplay ? `$${formatCryptoPrice("BTC", btcDisplay)}` : "—"}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">ETH</p>
          <p className="text-xs font-black text-white">{ethDisplay ? `$${formatCryptoPrice("ETH", ethDisplay)}` : "—"}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Breadth</p>
          <p className="text-xs font-black text-white">{safePercent(regime?.breadth_pct, 0)}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">BTC dom.</p>
          <p className="text-xs font-black text-white">{safePercent(regime?.btc_dominance, 1)}</p>
        </div>
      </div>

      {regimeTrustWarning && (
        <div className="rounded-xl px-4 py-3 flex items-center gap-3"
          style={{ background: "#1a0a0a", border: "1px solid #7f1d1d66" }}>
          <span className="text-sm">⚠</span>
          <div>
            <p className="text-[10px] font-black text-red-400 uppercase tracking-widest">
              {regimeTrustWarning}
            </p>
            <p className="text-xs text-red-200 mt-0.5">
              NO TRADE crypto forcé tant que le contexte BTC/ETH reste incomplet.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-2xl p-5 flex flex-col gap-3" style={{ background: "#09091e", border: "1px solid #3730a355" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest">Stratégie crypto active</p>
          <p className="text-xl font-black text-indigo-300">{activeLabel}</p>
          <p className="text-xs text-gray-500">{regime?.reasons?.join(" · ") || "Analyse du régime crypto"}</p>
        </div>
        <div className="rounded-2xl p-8 text-center" style={{ background: effectiveNoTrade ? "#130404" : "#041310", border: `2px solid ${effectiveNoTrade ? "#7f1d1d" : "#065f46"}` }}>
          <p className="text-3xl mb-3">{effectiveNoTrade ? "🛑" : "⚡"}</p>
          <p className="text-2xl font-black tracking-widest mb-2" style={{ color: effectiveNoTrade ? "#ef4444" : "#10b981" }}>
            {effectiveNoTrade ? "NO TRADE CRYPTO" : "CRYPTO TRADE READY"}
          </p>
          <p className="text-sm" style={{ color: effectiveNoTrade ? "#fca5a5" : "#86efac" }}>
            {effectiveNoTrade
              ? missingBtcEth
                ? "Contexte BTC/ETH incomplet — aucune autorisation de trade crypto."
                : "Aucun setup crypto avec edge robuste aujourd’hui."
              : `${tradeable.length} setup${tradeable.length > 1 ? "s" : ""} crypto avec edge validé.`}
          </p>
        </div>
      </div>

      {primaryCards.length > 0 && (
        <div>
          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2 px-1">
            {defensiveRegime
              ? "👁 Watchlist technique crypto — surveillance uniquement, aucun achat autorisé"
              : "🎯 Meilleures cryptos à trader aujourd'hui — edge validé uniquement"}
          </p>
          {defensiveRegime && (
            <div className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest"
              style={{ background: "#2b0f0f", border: "1px solid #ef444455", color: "#fca5a5" }}>
              Régime crypto défensif — surveillance seulement
            </div>
          )}
          {defensiveRegime && (
            <p className="mb-3 text-xs text-red-300">
              Le régime crypto actuel bloque les achats. Ces setups sont affichés pour suivi, pas pour exécution.
            </p>
          )}
          {hasPreviousData && (
            <div className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest"
              style={{ background: "#111118", border: "1px solid #f59e0b55", color: "#fcd34d" }}>
              Données précédentes
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {primaryCards.map((row) => (
              <button
                key={row.ticker}
                onClick={() => setSelected(row)}
                className="rounded-xl p-4 text-left transition-all hover:opacity-90"
                style={{ background: "#0d0d18", border: "1px solid #1e1e2a" }}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xl font-black text-white">{row.ticker}</span>
                  {defensiveRegime ? (
                    <span className="text-[10px] px-2 py-0.5 rounded font-black" style={{ background: "#3b1d07", color: "#fdba74" }}>
                      Achat interdit par régime
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded font-black" style={{ background: "#052e16", color: "#4ade80" }}>
                      {row.ticker_edge_status}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-gray-500">{row.signal_type} · {row.best_strategy_name ?? "Best strategy"}</p>
                <div className="grid grid-cols-3 gap-1.5 mt-3 text-center">
                  <div><p className="text-[9px] text-gray-600 uppercase">Entrée</p><p className="text-xs font-bold text-gray-300">${formatCryptoPrice(row.ticker, row.entry)}</p></div>
                  <div><p className="text-[9px] text-gray-600 uppercase">TP2</p><p className="text-xs font-bold text-emerald-400">${formatCryptoPrice(row.ticker, row.tp2)}</p></div>
                  <div><p className="text-[9px] text-gray-600 uppercase">SL</p><p className="text-xs font-bold text-red-400">${formatCryptoPrice(row.ticker, row.stop_loss)}</p></div>
                </div>
                {defensiveRegime && (
                  <div className="mt-3 rounded-lg px-3 py-2 text-[10px] font-bold text-red-300"
                    style={{ background: "#2a0d0d", border: "1px solid #ef444440" }}>
                    Pas de trade — régime crypto défensif
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {technicalWatchlist.length > 0 && (
        <div className="rounded-xl px-5 py-4" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
          <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-2">
            👁 Watchlist technique — à surveiller, pas trade
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {technicalWatchlist.map((row) => (
              <button
                key={row.ticker}
                className="text-left px-3 py-2 rounded-lg transition-colors hover:bg-white/[0.03]"
                style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
                onClick={() => setSelected(row)}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-black text-white">{row.ticker}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-black" style={{ background: "#052e16", color: "#4ade80" }}>Technique OK</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-black" style={{ background: "#111118", color: "#9ca3af" }}>
                      {edgeLabel(row.ticker_edge_status)}
                    </span>
                  </div>
                  <span className="text-xs font-black text-gray-400">{row.score}</span>
                </div>
                <p className="text-[10px] text-gray-600 mt-1">
                  {row.signal_type} · {row.setup_grade} · {row.final_decision ?? "WATCHLIST"}
                </p>
                {defensiveRegime && (
                  <p className="text-[10px] text-red-400 mt-1 font-bold">Pas de trade — régime crypto défensif</p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between px-4 py-3 rounded-xl" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
        <div>
          <p className="text-[9px] text-gray-700 uppercase tracking-widest">Validation stratégie crypto</p>
          <p className="text-xs font-black text-gray-400">Ouvrir le Crypto Strategy Lab pour vérifier les edges robustes</p>
        </div>
        <button onClick={onGoToLab} className="text-[10px] font-bold text-gray-600 hover:text-gray-400 transition-colors">
          Ouvrir le Lab →
        </button>
      </div>
    </div>
  );
}

