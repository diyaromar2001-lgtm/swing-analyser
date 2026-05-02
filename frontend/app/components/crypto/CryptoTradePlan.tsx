"use client";

import { TickerResult } from "../../types";
import { formatCryptoPrice } from "../../lib/cryptoFormat";

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

export function CryptoTradePlan({ row, onClose }: { row: TickerResult; onClose: () => void }) {
  const gradeColor =
    row.setup_grade === "A+" ? "#4ade80" :
    row.setup_grade === "A" ? "#bef264" :
    row.setup_grade === "B" ? "#f59e0b" : "#ef4444";
  const nonTradeWarning =
    row.ticker_edge_status === "NO_EDGE" ||
    row.ticker_edge_status === "WEAK_EDGE" ||
    row.ticker_edge_status === "OVERFITTED" ||
    row.setup_grade === "REJECT" ||
    row.setup_status === "INVALID" ||
    row.final_decision === "SKIP" ||
    row.final_decision === "NO_TRADE";

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
          {nonTradeWarning && (
            <div className="rounded-xl p-4" style={{ background: "#2a0d0d", border: "1px solid #ef444455" }}>
              <p className="text-xs font-black text-red-300 uppercase tracking-widest mb-1">NO TRADE CRYPTO</p>
              <p className="text-sm text-red-200">Pas de trade - edge non validé ou régime crypto défensif.</p>
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
                    row.ticker_edge_status === "NO_EDGE"
                      ? "Edge non validé"
                      : row.ticker_edge_status === "OVERFITTED"
                        ? "Backtest suspect — éviter"
                        : row.ticker_edge_status === "WEAK_EDGE"
                          ? "Edge faible"
                          : row.ticker_edge_status ?? "NO_EDGE"
                  }
                  sub={row.overfit_warning ? "Backtest suspect — éviter" : "Validation historique"}
                />
                <Row label="Score edge" value={row.edge_score ?? 0} sub={`Train PF ${row.edge_train_pf ?? 0} · Test PF ${row.edge_test_pf ?? 0}`} />
                <Row label="Volume 24h" value={row.volume_24h ? `$${Math.round(row.volume_24h).toLocaleString()}` : "—"} sub="Liquidité crypto spot" />
                <Row label="Market cap" value={row.market_cap ? `$${Math.round(row.market_cap).toLocaleString()}` : "—"} sub="Capitalisation approximative" />
                <Row label="Volatilité" value={safeFixed(row.volatility_pct, 2, "%")} sub="ATR / prix" />
                <Row label="Durée moy. histo" value={safeFixed(row.avg_hold_days, 1, "j")} sub="Hold time moyen de la stratégie" />
              </div>
            </div>
          </div>

          <div className="rounded-xl p-4" style={{ background: "#120d00", border: "1px solid #92400e55" }}>
            <p className="text-xs font-bold text-amber-400 mb-2">Invalidation</p>
            <ul className="space-y-1">
              <li className="text-xs text-gray-400">• Sortie immédiate si clôture sous le stop.</li>
              <li className="text-xs text-gray-400">• Pas de trade si edge non validé ou overfit critique.</li>
              <li className="text-xs text-gray-400">• Réduire la taille si volatilité extrême.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
