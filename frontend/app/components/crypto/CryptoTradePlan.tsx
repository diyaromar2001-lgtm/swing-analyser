"use client";

import { useState } from "react";
import { TickerResult } from "../../types";
import { formatCryptoPrice } from "../../lib/cryptoFormat";
import { useJournal } from "../../hooks/useJournal";
import { TakeTradeModal } from "../TakeTradeModal";
import { getCryptoResearchV2Row } from "../../lib/cryptoResearchV2";

function safeFixed(value?: number | null, digits = 1, suffix = "") {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(digits)}${suffix}`
    : "—";
}

function Row({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex items-start justify-between py-2.5" style={{ borderBottom: "1px solid #1a1a28" }}>
      <span className="text-xs text-gray-500 w-44 shrink-0">{label}</span>
      <div className="text-right">
        <div className="text-sm font-semibold text-white">{value}</div>
        {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

function ChecklistItemRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <span className={`text-xs font-black shrink-0 ${ok ? "text-emerald-400" : "text-orange-400"}`}>{ok ? "✓" : "✗"}</span>
      <span className={`text-xs ${ok ? "text-emerald-100" : "text-orange-100"}`}>{label}</span>
    </div>
  );
}

export function CryptoTradePlan({ row, onClose }: { row: TickerResult; onClose: () => void }) {
  const { isTickerActive } = useJournal();
  const alreadyTaken = isTickerActive(row.ticker, row.asset_scope ?? "CRYPTO");
  const [journalIntent, setJournalIntent] = useState<"PLANNED" | "WATCHLIST" | null>(null);
  const research = getCryptoResearchV2Row(row.ticker);

  const gradeColor =
    row.setup_grade === "A+" ? "#4ade80" :
    row.setup_grade === "A" ? "#bef264" :
    row.setup_grade === "B" ? "#f59e0b" : "#ef4444";

  // ── CRYPTO TRADABLE V1 AUTHORIZATION ──────────────────────────────────
  // Use backend-computed authorization instead of frontend logic
  const execAuthorized = row.crypto_execution_authorized === true;
  const watchlistEligible = row.crypto_watchlist_eligible === true;
  const checklist = (row.authorization_checklist || {}) as Record<string, boolean>;

  // Build readiness items from authorization checklist
  const readinessItems = [
    { label: "Régime crypto favorable", ok: checklist.regime_favorable ?? false },
    { label: "BTC/ETH compatibles", ok: checklist.btc_eth_context_ok ?? false },
    { label: "Setup grade A+ ou A", ok: checklist.setup_grade_sufficient ?? false },
    { label: "Setup status READY", ok: checklist.setup_ready ?? false },
    { label: "Prix proche entrée (≤5%)", ok: checklist.entry_near ?? false },
    { label: "Stop loss défini", ok: checklist.stop_defined ?? false },
    { label: "TP1/TP2 définis", ok: checklist.tp_defined ?? false },
    { label: "Risk/reward ≥1.5x", ok: checklist.rr_adequate ?? false },
    { label: "Volatilité acceptable (≤9%)", ok: checklist.volatility_acceptable ?? false },
    { label: "Pas d’overfit", ok: checklist.overfit_ok ?? false },
    { label: "Symbole univers tradable (BTC, ETH, SOL, BNB, LINK, AAVE, MKR)", ok: checklist.tradable_universe_symbol ?? false },
    { label: "Edge VALID_EDGE ou STRONG_EDGE", ok: checklist.edge_validated ?? false },
  ];

  const blockedReasons = row.crypto_blocked_reasons ?? [];
  const authorizedConditions = row.crypto_authorized_conditions ?? [];
  const missingCount = readinessItems.filter(item => !item.ok).length;
  const readinessConclusion =
    blockedReasons.length > 0 && !execAuthorized ? `Bloqué (${blockedReasons.length} raison${blockedReasons.length > 1 ? "s" : ""})` :
    watchlistEligible ? "Watchlist possible" :
    "Non autorisé";

  // Use backend-provided blocked reasons instead of frontend logic
  const execReasons = blockedReasons;

  const ctaText = execAuthorized
    ? "✅ Préparer ce trade (PLANNED)"
    : watchlistEligible
      ? "🟠 Ajouter à la watchlist"
      : "❌ Trade non autorisé";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "rgba(0,0,0,0.72)" }}
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-lg flex flex-col"
        style={{ background: "#0a0a14", borderLeft: "1px solid #1e1e2e" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="sticky top-0 z-10 flex items-center justify-between px-6 py-4"
          style={{ background: "#0a0a14", borderBottom: "1px solid #1e1e2e" }}
        >
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-black text-white">{row.ticker}</span>
              <span className="text-sm text-gray-500">{row.sector}</span>
            </div>
            <p className="text-xs mt-1" style={{ color: gradeColor }}>
              {row.setup_grade} · {row.signal_type} · {row.final_decision ?? "WAIT"}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-xl leading-none">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {/* Backtest Phase 1 Warning */}
          <div className="rounded-xl p-4" style={{ background: "#2a1111", border: "1px solid #ef444455" }}>
            <p className="text-xs font-black text-red-300 uppercase tracking-widest mb-1">⚠️ CRYPTO BACKTEST NON VALIDÉ</p>
            <p className="text-sm text-red-200">
              Backtest Phase 1 montre aucune stratégie crypto viable (PF max 1.01 / sample insuffisant). <strong>Trade réel non recommandé.</strong> Crypto = observation uniquement.
            </p>
          </div>

          {!execAuthorized && !watchlistEligible && (
            <div className="rounded-xl p-4" style={{ background: "#2a0d0d", border: "1px solid #ef444455" }}>
              <p className="text-xs font-black text-red-300 uppercase tracking-widest mb-1">NO TRADE CRYPTO</p>
              <p className="text-sm text-red-200">Trade non autorisé. Setup invalide ou rejeté.</p>
            </div>
          )}

          <div className="rounded-xl p-4" style={{ background: "#081018", border: `1px solid ${gradeColor}55` }}>
            <p className="text-sm font-bold text-white mb-2">Plan de trade crypto swing</p>
            <p className="text-xs text-gray-400 leading-relaxed">
              Outil swing basé sur données daily + prix actuel rafraîchi. Ce n&apos;est pas un flux tick-by-tick.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Niveaux</h3>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1a1a28" }}>
              <div className="px-4" style={{ background: "#0d0d18" }}>
                <Row label="Prix actuel" value={<span className="text-blue-400">${formatCryptoPrice(row.ticker, row.price)}</span>} sub="Prix live approximatif / différé" />
                <Row label="Entrée" value={<span className="text-white">${formatCryptoPrice(row.ticker, row.entry)}</span>} sub={`${typeof row.dist_entry_pct === "number" && Number.isFinite(row.dist_entry_pct) && row.dist_entry_pct >= 0 ? "+" : ""}${safeFixed(row.dist_entry_pct, 1, "%")} vs entrée idéale`} />
                <Row label="Stop loss" value={<span className="text-red-400">${formatCryptoPrice(row.ticker, row.stop_loss)}</span>} sub="Stop ATR crypto — levier non recommandé" />
                <Row label="TP1" value={<span className="text-emerald-300">${formatCryptoPrice(row.ticker, row.tp1)}</span>} sub="Prise partielle 40–50%" />
                <Row label="TP2" value={<span className="text-emerald-500">${formatCryptoPrice(row.ticker, row.tp2)}</span>} sub="Objectif final swing" />
                <Row label="Trailing stop" value={<span className="text-amber-400">${formatCryptoPrice(row.ticker, row.trailing_stop)}</span>} sub="À activer après TP1" />
                <Row label="Risque / rendement" value={<span style={{ color: (row.rr_ratio ?? 0) >= 2 ? "#4ade80" : "#f59e0b" }}>1:{safeFixed(row.rr_ratio, 2)}</span>} sub={`Risque actuel ${safeFixed(row.risk_now_pct, 2, "%")}`} />
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Contexte crypto</h3>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1a1a28" }}>
              <div className="px-4" style={{ background: "#0d0d18" }}>
                <Row label="Stratégie" value={row.best_strategy_name ?? "Aucune"} sub={row.best_strategy_for_ticker ?? "Pas de best strategy robuste"} />
                <Row
                  label="Edge historique"
                  value={
                    row.ticker_edge_status === "INSUFFICIENT_SAMPLE"
                      ? "Historique insuffisant"
                      : row.ticker_edge_status === "NO_EDGE"
                        ? "Edge non validé"
                        : row.ticker_edge_status === "OVERFITTED"
                          ? "Backtest suspect — éviter"
                          : row.ticker_edge_status === "WEAK_EDGE"
                            ? "Edge faible"
                            : row.ticker_edge_status === "EDGE_NOT_COMPUTED"
                              ? "Non calculé"
                              : row.ticker_edge_status ?? "NO_EDGE"
                  }
                  sub={
                    row.ticker_edge_status === "INSUFFICIENT_SAMPLE"
                      ? `Seulement ${row.edge_trades ?? 0} trades historiques (besoin ≥8)`
                      : row.overfit_warning
                        ? "Backtest suspect — éviter"
                        : "Validation historique"
                  }
                />
                <Row label="Score edge" value={row.edge_score ?? 0} sub={`Train PF ${row.edge_train_pf ?? 0} · Test PF ${row.edge_test_pf ?? 0}`} />
                <Row label="Volume 24h" value={row.volume_24h ? `$${Math.round(row.volume_24h).toLocaleString()}` : "—"} sub="Liquidité crypto spot" />
                <Row label="Market cap" value={row.market_cap ? `$${Math.round(row.market_cap).toLocaleString()}` : "—"} sub="Capitalisation approximative" />
                <Row label="Volatilité" value={safeFixed(row.volatility_pct, 2, "%")} sub="ATR / prix" />
                <Row label="Durée moy. histo" value={safeFixed(row.avg_hold_days, 1, "j")} sub="Hold time moyen de la stratégie" />
              </div>
            </div>
          </div>

          {/* FALLBACK EDGE CONTEXT (when exact edge is INSUFFICIENT_SAMPLE) */}
          {row.ticker_edge_status === "INSUFFICIENT_SAMPLE" && row.edge_fallback_search && (
            <div className="rounded-xl p-4" style={{ background: "#081f3d", border: "1px solid #1e40af55" }}>
              <p className="text-xs font-bold text-blue-300 mb-3">ℹ️ Contexte edge par fallback (Tier {row.edge_fallback_search.fallback_tier})</p>
              <div className="space-y-2 text-xs text-blue-200">
                <p>
                  <strong>Symbole fallback:</strong> {row.edge_fallback_search.fallback_symbol}
                </p>
                <p>
                  <strong>Source:</strong> {row.edge_fallback_search.fallback_source}
                </p>
                <p>
                  <strong>Edge fallback:</strong> {row.edge_fallback_search.fallback_edge_status}
                </p>
                <p className="mt-2 text-xs text-blue-300/80">
                  {row.edge_fallback_search.explanation}
                </p>
                <p className="text-xs text-blue-300/70 mt-2 italic">
                  💡 Cette information montre que des setups similaires (secteur/marché) ont une edge validée, mais votre exact edge requiert plus de données historiques.
                </p>
              </div>
            </div>
          )}

          <div className="rounded-xl p-4" style={{ background: "#0b1020", border: "1px solid #334155" }}>
            <p className="text-[10px] font-black uppercase tracking-widest text-sky-300 mb-2">Ce qu&apos;il manque pour devenir autorisé</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4">
              {readinessItems.map(item => <ChecklistItemRow key={item.label} label={item.label} ok={item.ok} />)}
            </div>
            <p className={`text-xs font-bold mt-3 ${readinessConclusion === "Bloqué par régime" || readinessConclusion === "Bloqué par edge" ? "text-orange-300" : "text-sky-300"}`}>
              {readinessConclusion}
            </p>
          </div>

          {research && (
            <div className="rounded-xl p-4" style={{ background: "#081018", border: "1px solid #1f3b5a" }}>
              <p className="text-[10px] font-black uppercase tracking-widest text-cyan-300 mb-3">Crypto Research V2</p>
              <p className="text-xs text-cyan-100/80 mb-3">Recherche uniquement — ne remplace pas l&apos;autorisation d&apos;exécution.</p>
              <div className="space-y-2">
                <Row label="Score" value={<span className="text-cyan-300">{research.score.toFixed(1)}/100</span>} sub={research.researchStatus} />
                <Row label="Bucket" value={research.bucket} sub={research.notes} />
                <Row label="Best strategy" value={research.bestStrategy} sub={research.bestRegime} />
                <Row label="Timeframe" value={research.timeframe} sub={`Weekend ${research.weekendRisk.toLowerCase()}`} />
                <Row label="RS vs BTC" value={research.rsVsBtc !== null ? `${research.rsVsBtc >= 0 ? "+" : ""}${(research.rsVsBtc * 100).toFixed(1)}%` : "—"} sub="Relative strength" />
                <Row label="RS vs ETH" value={research.rsVsEth !== null ? `${research.rsVsEth >= 0 ? "+" : ""}${(research.rsVsEth * 100).toFixed(1)}%` : "—"} sub="Relative strength" />
                <Row label="Liquidity" value={research.liquidity !== null ? research.liquidity.toFixed(0) : "—"} sub={research.sampleStatus} />
                <Row label="Overfit / sample" value={research.overfitRisk ? "Overfit risk" : "OK"} sub={research.sampleStatus} />
              </div>
            </div>
          )}

          <div className="rounded-xl p-4" style={{ background: "#120d00", border: "1px solid #92400e55" }}>
            <p className="text-xs font-bold text-amber-400 mb-2">Invalidation</p>
            <ul className="space-y-1">
              <li className="text-xs text-gray-400">• Sortie immédiate si clôture sous le stop.</li>
              <li className="text-xs text-gray-400">• Pas de trade si edge non validé ou overfit critique.</li>
              <li className="text-xs text-gray-400">• Réduire la taille si volatilité extrême.</li>
            </ul>
          </div>

          {/* BLOCKED REASONS (if trade not authorized) */}
          {!execAuthorized && execReasons.length > 0 && (
            <div className="rounded-xl p-4" style={{ background: "#2a0d0d", border: "1px solid #ef444455" }}>
              <p className="text-xs font-black text-red-300 uppercase tracking-widest mb-2">❌ TRADE NON AUTORISÉ ({execReasons.length} raison{execReasons.length > 1 ? "s" : ""})</p>
              <ul className="space-y-1">
                {execReasons.map((r, i) => (
                  <li key={i} className="text-xs text-red-200 flex gap-2">
                    <span className="shrink-0">•</span>{r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AUTHORIZED CONDITIONS (if trade authorized) */}
          {execAuthorized && authorizedConditions.length > 0 && (
            <div className="rounded-xl p-4" style={{ background: "#041310", border: "1px solid #065f46" }}>
              <p className="text-xs font-black text-emerald-300 uppercase tracking-widest mb-2">✓ CONDITIONS RÉUNIES ({authorizedConditions.length})</p>
              <ul className="space-y-1">
                {authorizedConditions.map((c, i) => (
                  <li key={i} className="text-xs text-emerald-100 flex gap-2">
                    <span className="shrink-0">•</span>{c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            disabled={alreadyTaken || (!execAuthorized && !watchlistEligible)}
            onClick={() => setJournalIntent(execAuthorized ? "PLANNED" : "WATCHLIST")}
            className="w-full py-3 rounded-xl text-sm font-black transition-all disabled:cursor-not-allowed disabled:opacity-90"
            style={{
              background: execAuthorized ? "#0f5132" : watchlistEligible ? "#2a220d" : "#2a0d0d",
              border: `1px solid ${execAuthorized ? "#22c55e" : watchlistEligible ? "#a16207" : "#7f1d1d"}`,
              color: execAuthorized ? "#86efac" : watchlistEligible ? "#fcd34d" : "#fca5a5",
            }}
          >
            {ctaText}
          </button>
          {alreadyTaken && (
            <p className="text-[10px] text-emerald-400 mt-2">Déjà présent dans le journal.</p>
          )}
        </div>

        {journalIntent && (
          <TakeTradeModal
            t={row}
            journalStatus={journalIntent}
            submitLabel={journalIntent === "PLANNED" ? "✅ Préparer ce trade" : "🟠 Ajouter à la watchlist"}
            onClose={() => setJournalIntent(null)}
          />
        )}
      </div>
    </div>
  );
}
