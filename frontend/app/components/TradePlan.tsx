"use client";

import { useState } from "react";
import { TickerResult } from "../types";
import { SetupGradeBadge, SignalBadge, ConfidenceBadge } from "./CategoryBadge";
import { SentimentPanel } from "./SentimentPanel";
import { SetupStats } from "./SetupStats";
import { TakeTradeModal } from "./TakeTradeModal";
import { useJournal } from "../hooks/useJournal";

// ── Quality Score ring ────────────────────────────────────────────────────────

function QualityRing({ score }: { score: number }) {
  const color =
    score >= 75 ? "#4ade80" :
    score >= 55 ? "#f59e0b" : "#ef4444";
  const label =
    score >= 75 ? "Timing Optimal" :
    score >= 55 ? "Timing Correct" : "Timing Faible";

  const r = 20;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl"
      style={{ background: `${color}11`, border: `1px solid ${color}33` }}>
      <svg width="52" height="52" viewBox="0 0 52 52" className="shrink-0">
        <circle cx="26" cy="26" r={r} fill="none" stroke="#1a1a28" strokeWidth="4" />
        <circle
          cx="26" cy="26" r={r} fill="none"
          stroke={color} strokeWidth="4"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 26 26)"
        />
        <text x="26" y="31" textAnchor="middle" fontSize="11" fontWeight="900" fill={color}>{score}</text>
      </svg>
      <div>
        <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-0.5">🎯 Quality Score</p>
        <p className="text-xs font-bold text-white">{label}</p>
        <p className="text-[10px] text-gray-600 mt-0.5">Distance · RSI · Pente SMA50 · Volatilité</p>
      </div>
    </div>
  );
}

// ── Earnings warning ──────────────────────────────────────────────────────────

function EarningsWarning({ date, days }: { date: string; days: number }) {
  const urgent = days <= 3;
  return (
    <div className="rounded-xl px-4 py-3 flex items-center gap-3"
      style={{
        background: urgent ? "#1f0909" : "#1a1000",
        border: `1px solid ${urgent ? "#991b1b" : "#ca8a04"}55`,
      }}>
      <span className="text-base shrink-0">{urgent ? "🚨" : "⚠️"}</span>
      <div>
        <p className="text-xs font-bold" style={{ color: urgent ? "#f87171" : "#fde047" }}>
          Résultats financiers dans {days === 0 ? "aujourd'hui" : `${days} jour${days > 1 ? "s" : ""}`}
        </p>
        <p className="text-[10px] text-gray-500 mt-0.5">
          {date} — {urgent
            ? "Position à risque : volatilité élevée probable. Éviter ou fermer avant."
            : "Considérer une réduction de position avant les earnings."}
        </p>
      </div>
    </div>
  );
}

// ── Build reason text ─────────────────────────────────────────────────────────

function buildReason(row: TickerResult) {
  const d = row.score_detail.details;
  const bulls: string[] = [];
  const waits: string[] = [];

  if (d.prix_above_sma200)    bulls.push("Prix au-dessus de la SMA200 → tendance de fond haussière");
  if (d.sma50_above_sma200)   bulls.push("SMA50 > SMA200 → structure technique solide");
  if (d.sma50_slope_positive) bulls.push("Pente SMA50 positive → momentum de tendance intacte");
  if (d.near_52w_high)        bulls.push(`Dans les 15% du plus haut 52 semaines ($${row.high_52w.toFixed(0)}) → force relative élevée`);
  if (d.rsi_ideal_zone)       bulls.push(`RSI à ${row.rsi_val.toFixed(1)} → zone momentum idéale (50–70)`);
  if (d.macd_positif)         bulls.push("MACD positif → pression acheteuse dominante");
  if (d.perf_3m_positive)     bulls.push(`Performance 3 mois positive (+${row.perf_3m.toFixed(1)}%)`);
  if (d.outperforms_sp500)    bulls.push("Surperforme le S&P500 sur 3m et 6m → force relative confirmée");
  if (d.volume_eleve)         bulls.push("Volume supérieur à la moyenne (+30%) → intérêt institutionnel");
  if (d.rr_suffisant)         bulls.push(`Ratio R/R de 1:${row.rr_ratio.toFixed(1)} → risque/rendement favorable`);

  if (!d.prix_above_sma200)   waits.push("Prix sous la SMA200 → tendance baissière — filtré normalement");
  if (!d.rsi_ideal_zone)      waits.push(`RSI à ${row.rsi_val.toFixed(1)} → hors zone idéale (50–70)`);
  if (!d.macd_positif)        waits.push("MACD négatif → momentum vendeur encore présent");
  if (row.dist_entry_pct > 5) waits.push(`Prix ${row.dist_entry_pct.toFixed(1)}% au-dessus de l'entrée idéale — attendre repli`);

  const headlines: Record<string, string> = {
    "A+":    "🟢 Setup A+ — Entrée immédiate possible",
    "A":     "🟡 Setup A — Confirmation conseillée",
    "B":     "🟠 Setup B — Watchlist",
    "REJECT":"🔴 REJECT — Éviter",
  };

  const whys: Record<string, string> = {
    "A+":    `${row.ticker} réunit toutes les conditions d'un setup swing de haute qualité. Score ${row.score}/100, R/R 1:${row.rr_ratio.toFixed(1)}, RSI en zone idéale et entrée proche.`,
    "A":     `${row.ticker} présente un bon setup (score ${row.score}/100) avec un R/R de 1:${row.rr_ratio.toFixed(1)}. Une légère confirmation ou un micro-repli vers l'entrée améliorerait le timing.`,
    "B":     `${row.ticker} est en formation (score ${row.score}/100). Les conditions ne sont pas encore réunies — mettre en watchlist et surveiller.`,
    "REJECT":`${row.ticker} ne remplit pas les critères de qualité minimum.`,
  };

  return {
    headline: headlines[row.setup_grade] ?? headlines["REJECT"],
    why:      whys[row.setup_grade]      ?? whys["REJECT"],
    details:  row.setup_grade === "A+" || row.setup_grade === "A" ? bulls : waits,
  };
}

// ── Row helper ────────────────────────────────────────────────────────────────

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

// ── Main component ────────────────────────────────────────────────────────────

export function TradePlan({ row, onClose }: { row: TickerResult; onClose: () => void }) {
  const reason     = buildReason(row);
  const scoreColor = row.score >= 80 ? "#10b981" : row.score >= 65 ? "#f59e0b" : "#ef4444";
  const [showTakeModal, setShowTakeModal] = useState(false);
  const { isTickerActive } = useJournal();
  const alreadyTaken = isTickerActive(row.ticker);
  const strategyName = row.best_strategy_name === "Pullback Confirmed"
    ? "Pullback confirme"
    : row.best_strategy_name ?? "Aucune";
  const edgeLabel =
    row.setup_grade === "REJECT" || row.setup_status === "INVALID"
      ? "Setup invalide"
      : row.ticker_edge_status === "STRONG_EDGE"
        ? "Edge robuste"
        : row.ticker_edge_status === "VALID_EDGE"
          ? "Edge valide"
          : row.ticker_edge_status === "WEAK_EDGE"
            ? "Edge faible"
            : row.ticker_edge_status === "OVERFITTED"
              ? "Backtest suspect - eviter"
              : "Edge non valide";
  const edgeColor =
    row.ticker_edge_status === "STRONG_EDGE" ? "#4ade80" :
    row.ticker_edge_status === "VALID_EDGE"  ? "#86efac" :
    row.ticker_edge_status === "WEAK_EDGE"   ? "#fde047" :
    row.ticker_edge_status === "OVERFITTED"  ? "#f59e0b" : "#9ca3af";

  const gradeColors: Record<string, { bg: string; border: string }> = {
    "A+":    { bg: "#031a0d", border: "#16a34a" },
    "A":     { bg: "#0c1a0c", border: "#65a30d" },
    "B":     { bg: "#1c1500", border: "#ca8a04" },
    "REJECT":{ bg: "#100a0a", border: "#7f1d1d" },
  };
  const gc = gradeColors[row.setup_grade] ?? gradeColors["REJECT"];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-lg flex flex-col"
        style={{ background: "#0a0a14", borderLeft: "1px solid #1e1e2e" }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div
          className="sticky top-0 z-10 flex items-center justify-between px-6 py-4"
          style={{ background: "#0a0a14", borderBottom: "1px solid #1e1e2e" }}
        >
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-black text-white">{row.ticker}</span>
              <span className="text-sm text-gray-500">{row.sector}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-bold" style={{ color: scoreColor }}>Score {row.score}/100</span>
              <SignalBadge signal={row.signal_type} />
              <ConfidenceBadge confidence={row.confidence} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <SetupGradeBadge grade={row.setup_grade} />
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors text-xl leading-none ml-2"
            >✕</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* ── Earnings Warning ── */}
          {row.earnings_warning && row.earnings_date && row.earnings_days !== null && row.earnings_days !== undefined && (
            <EarningsWarning date={row.earnings_date} days={row.earnings_days} />
          )}

          {/* ── Quality Score ── */}
          {typeof row.quality_score === "number" && (
            <QualityRing score={row.quality_score} />
          )}

          {/* ── Verdict ── */}
          <div className="rounded-xl p-4" style={{ background: gc.bg, border: `1px solid ${gc.border}` }}>
            <p className="text-sm font-bold text-white mb-2">{reason.headline}</p>
            <p className="text-xs text-gray-400 leading-relaxed">{reason.why}</p>
            {reason.details.length > 0 && (
              <ul className="mt-3 space-y-1">
                {reason.details.map((d, i) => (
                  <li key={i} className="text-xs text-gray-300 flex gap-2">
                    <span className="text-emerald-500 shrink-0">→</span>{d}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* ── Niveaux ── */}
          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              📊 Niveaux de Trade Dynamiques
            </h3>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1a1a28" }}>
              <div className="px-4" style={{ background: "#0d0d18" }}>
                <Row
                  label="Prix actuel"
                  value={<span className="text-blue-400">${row.price.toFixed(2)}</span>}
                  sub={`${row.dist_entry_pct > 0 ? "+" : ""}${row.dist_entry_pct.toFixed(1)}% vs entrée idéale`}
                />
                <Row
                  label="Entrée idéale"
                  value={<span className="text-white">${row.entry.toFixed(2)}</span>}
                  sub="SMA50 — pullback optimal"
                />
                <Row
                  label="Zone d'achat"
                  value={<span className="text-indigo-400">${(row.entry * 0.995).toFixed(2)} – ${(row.entry * 1.015).toFixed(2)}</span>}
                  sub="±1.5% autour de l'entrée"
                />
                <Row
                  label={`Stop Loss (${row.sl_type})`}
                  value={<span style={{ color: "#ef4444" }}>${row.stop_loss.toFixed(2)}</span>}
                  sub={`-${((row.entry - row.stop_loss) / row.entry * 100).toFixed(1)}% depuis l'entrée · ${row.sl_type}`}
                />
                <Row
                  label="TP1 — Prise partielle (1.5R)"
                  value={<span style={{ color: "#86efac" }}>${row.tp1.toFixed(2)}</span>}
                  sub={`+${((row.tp1 / row.entry - 1) * 100).toFixed(1)}% · sortir 40–50% de la position`}
                />
                <Row
                  label="TP2 — Objectif final (3R)"
                  value={<span style={{ color: "#10b981" }}>${row.tp2.toFixed(2)}</span>}
                  sub={`+${((row.tp2 / row.entry - 1) * 100).toFixed(1)}% · résistance ou 3R`}
                />
                <Row
                  label="Trailing Stop (après TP1)"
                  value={<span style={{ color: "#f59e0b" }}>${row.trailing_stop.toFixed(2)}</span>}
                  sub="Activer après avoir atteint TP1 — protège les gains"
                />
                <Row
                  label="Ratio Risque / Rendement"
                  value={<span style={{ color: row.rr_ratio >= 2 ? "#4ade80" : "#f59e0b" }}>1 : {row.rr_ratio.toFixed(2)}</span>}
                  sub={`Résistance 60j : $${row.resistance.toFixed(2)} · Support 20j : $${row.support.toFixed(2)}`}
                />
                <Row
                  label="Risque actuel"
                  value={
                    <span style={{ color: row.risk_now_pct > 5 ? "#ef4444" : row.risk_now_pct > 3 ? "#f59e0b" : "#10b981" }}>
                      {row.risk_now_pct.toFixed(2)}%
                    </span>
                  }
                  sub="Distance prix actuel → stop loss"
                />
              </div>
            </div>
          </div>

          {/* ── Stratégie position ── */}
          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              📋 Stratégie de Position
            </h3>
            <div className="rounded-xl p-4 space-y-3" style={{ background: "#0d0d18", border: "1px solid #1a1a28" }}>
              <div
                className="flex items-center justify-between gap-3 flex-wrap rounded-lg px-3 py-2"
                style={{ background: "#111120", border: `1px solid ${edgeColor}33` }}
              >
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-gray-600">StratÃ©gie Edge</p>
                  <p className="text-sm font-semibold text-white">{strategyName}</p>
                </div>
                <div className="text-right">
                  <p className="text-[11px] font-black" style={{ color: edgeColor }}>{edgeLabel}</p>
                  {row.overfit_warning && (
                    <p className="text-[10px] text-amber-400">Backtest suspect - prudence</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <SetupGradeBadge grade={row.setup_grade} />
                <span className="text-sm text-white font-medium">{row.position_size}</span>
              </div>
              <div className="text-xs text-gray-400 space-y-1 leading-relaxed">
                {row.setup_grade === "A+" && (
                  <>
                    <p>① Entrer à <strong className="text-white">${row.entry.toFixed(2)}</strong> (ou zone -1.5%)</p>
                    <p>② À <strong className="text-green-400">TP1 ${row.tp1.toFixed(2)}</strong> : vendre 40–50%, activer trailing à <strong>${row.trailing_stop.toFixed(2)}</strong></p>
                    <p>③ Laisser courir jusqu&apos;à <strong className="text-green-500">TP2 ${row.tp2.toFixed(2)}</strong></p>
                    <p>④ Si prix passe sous <strong className="text-red-400">${row.stop_loss.toFixed(2)}</strong> → sortie immédiate</p>
                  </>
                )}
                {row.setup_grade === "A" && (
                  <>
                    <p>① Attendre repli vers <strong className="text-white">${row.entry.toFixed(2)}</strong></p>
                    <p>② Entrer en 2 fois (50% maintenant si proche, 50% au repli)</p>
                    <p>③ Même gestion TP1 / TP2 / trailing qu&apos;un A+</p>
                  </>
                )}
                {row.setup_grade === "B" && (
                  <p>Watchlist. Attendre score &gt; 65 et prix proche de l&apos;entrée idéale.</p>
                )}
              </div>
            </div>
          </div>

          {/* ── Indicateurs ── */}
          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              📡 Indicateurs Clés
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "RSI 14",   value: row.rsi_val.toFixed(1),       color: row.rsi_val >= 50 && row.rsi_val <= 70 ? "#4ade80" : row.rsi_val > 70 ? "#ef4444" : "#9ca3af" },
                { label: "MACD",     value: row.macd_val > 0 ? "↑ Pos" : "↓ Nég", color: row.macd_val > 0 ? "#4ade80" : "#ef4444" },
                { label: "ATR 14",   value: `$${row.atr_val.toFixed(2)}`,  color: "#9ca3af" },
                { label: "Perf 3m",  value: `${row.perf_3m > 0 ? "+" : ""}${row.perf_3m.toFixed(1)}%`, color: row.perf_3m > 0 ? "#4ade80" : "#ef4444" },
                { label: "Perf 6m",  value: `${row.perf_6m > 0 ? "+" : ""}${row.perf_6m.toFixed(1)}%`, color: row.perf_6m > 0 ? "#4ade80" : "#ef4444" },
                { label: "52W High", value: `$${row.high_52w.toFixed(0)}`, color: row.price >= row.high_52w * 0.85 ? "#4ade80" : "#9ca3af" },
              ].map(item => (
                <div key={item.label} className="rounded-lg p-3 text-center"
                  style={{ background: "#111120", border: "1px solid #1a1a28" }}>
                  <p className="text-xs text-gray-600 mb-1">{item.label}</p>
                  <p className="text-sm font-bold" style={{ color: item.color }}>{item.value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* ── Validation historique ── */}
          <SetupStats ticker={row.ticker} grade={row.setup_grade} />

          {/* ── Sortir si ── */}
          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">⚠️ Sortir si…</h3>
            <div className="rounded-xl p-4 space-y-2"
              style={{ background: "#140808", border: "1px solid #7f1d1d44" }}>
              {[
                `Clôture sous le stop loss (${row.stop_loss.toFixed(2)}$) → sortie immédiate, sans exception`,
                `Clôture sous la SMA200 (${row.sma200.toFixed(2)}$) → tendance principale cassée`,
                "RSI dépasse 80 sans prise de profit → réduire la position de 50%",
                "Volume anormalement élevé à la baisse → signal de distribution institutionnelle",
                ...(row.earnings_warning
                  ? [`Résultats imminents (${row.earnings_date}) → fermer ou réduire avant`]
                  : []),
              ].map((s, i) => (
                <div key={i} className="flex gap-2 text-xs text-gray-400">
                  <span className="text-red-500 shrink-0">✗</span>{s}
                </div>
              ))}
            </div>
          </div>

          {/* ── Social Sentiment ── */}
          <div>
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">💬 Social Sentiment</h3>
            <SentimentPanel ticker={row.ticker} />
          </div>

        </div>{/* end scrollable */}

        {/* ── Sticky CTA ── */}
        <div className="p-4 border-t shrink-0" style={{ borderColor: "#1e1e2e", background: "#0a0a14" }}>
          {alreadyTaken ? (
            <div className="w-full py-3 rounded-xl text-sm font-black text-center"
              style={{ background: "#0c1a10", border: "1px solid #065f46", color: "#10b981" }}>
              ✅ Déjà en portefeuille
            </div>
          ) : (
            <button
              onClick={() => setShowTakeModal(true)}
              className="w-full py-3 rounded-xl text-sm font-black transition-all hover:opacity-90 active:scale-95"
              style={{ background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff" }}
            >
              ✅ Prendre ce trade
            </button>
          )}
        </div>

        {showTakeModal && (
          <TakeTradeModal t={row} onClose={() => setShowTakeModal(false)} />
        )}
      </div>
    </div>
  );
}
