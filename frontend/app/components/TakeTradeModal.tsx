"use client";

import { useState } from "react";
import { TickerResult, JournalTrade, RegimeEngine } from "../types";
import { useJournal, canOpenCryptoTrade } from "../hooks/useJournal";

const SIM_CAPITAL = 10_000;
const RISK_PCT    = 0.01;

function posSize(t: TickerResult) {
  const riskAmt      = SIM_CAPITAL * RISK_PCT;
  const riskPerShare = Math.max(0.01, t.entry - t.stop_loss);
  return Math.max(1, Math.floor(riskAmt / riskPerShare));
}

export function TakeTradeModal({
  t,
  engine,
  journalStatus = "PLANNED",
  submitLabel,
  onClose,
}: {
  t:       TickerResult;
  engine?: RegimeEngine | null;
  journalStatus?: "PLANNED" | "WATCHLIST";
  submitLabel?: string;
  onClose: () => void;
}) {
  const { addTrade, isTickerActive } = useJournal();
  const alreadyTaken = isTickerActive(t.ticker, t.asset_scope);

  const today = new Date().toISOString().split("T")[0];
  const [form, setForm] = useState({
    date_entry:  today,
    price_entry: t.entry,
    quantity:    posSize(t),
    fees:        0,
    broker:      "IBKR",
      note_entry:  "",
    });

  // ── CRYPTO TRADABLE V1 WARNING MODAL ────────────────────────────────────
  const [cryptoWarning, setCryptoWarning] = useState<{ shown: boolean; reason?: string }>({ shown: false });

  const set = (k: string, v: string | number) => setForm(f => ({ ...f, [k]: v }));

  const riskUsd    = Math.max(0, (form.price_entry - t.stop_loss) * form.quantity + form.fees);
  const capitalUsd = form.price_entry * form.quantity;

  const handleSave = () => {
      // ── CRYPTO TRADABLE V1 GATE ──────────────────────────────────────────
      // Check if crypto trade is authorized (only applies to PLANNED/OPEN, not WATCHLIST)
      const cryptoCheckResult = canOpenCryptoTrade(t, journalStatus);
      if (!cryptoCheckResult.allowed) {
        // Trade not authorized — show warning and return without submitting
        setCryptoWarning({ shown: true, reason: cryptoCheckResult.reason });
        return;
      }

      const trade: JournalTrade = {
        id:            `${t.ticker}_${Date.now()}`,
        ticker:        t.ticker,
        symbol:        t.ticker,
        universe:      (t.asset_scope ?? "ACTIONS") as "ACTIONS" | "CRYPTO",
        strategy:      engine?.active_strategy ?? "UNKNOWN",
        strategy_name: engine?.strategy_name ?? engine?.active_strategy ?? "UNKNOWN",
        signal_type:   t.signal_type ?? "",
        setup_grade:   t.setup_grade,
        score:         t.score,
        regime:        engine?.regime ?? "UNKNOWN",
        confidence:    t.confidence,
        sector:        t.sector,
        edge_status:   t.ticker_edge_status ?? "NO_EDGE",
        final_decision: t.final_decision ?? "WAIT",
        execution_authorized: journalStatus === "PLANNED",
        planned_entry: t.entry,
        entry_plan:    t.entry,
        stop_loss:     t.stop_loss,
        tp1:           t.tp1,
        tp2:           t.tp2,
        rr_ratio:      t.rr_ratio,
        date_entry:    form.date_entry,
        price_entry:   form.price_entry,
        quantity:      form.quantity,
        fees:          form.fees,
        broker:        form.broker,
        note_entry:    form.note_entry,
        notes:         form.note_entry,
        status:        journalStatus,
        opened_at:     journalStatus === "PLANNED" ? null : form.date_entry,
      };
      addTrade(trade);
      onClose();
    };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,.85)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-sm rounded-2xl p-6 space-y-4 overflow-y-auto"
        style={{ background: "#0e0e1c", border: "1px solid #2a2a4e", maxHeight: "90vh" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest">
              {journalStatus === "PLANNED" ? "Préparer ce trade" : "Ajouter à la watchlist"}
            </p>
            <p className="text-xl font-black text-white">
              {t.ticker}
              <span className="text-sm text-gray-500 ml-2">{t.signal_type}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-white text-lg">✕</button>
        </div>

        {/* Already taken */}
        {alreadyTaken && (
          <div className="rounded-xl px-4 py-3 text-center"
            style={{ background: "#0c1a10", border: "1px solid #065f46" }}>
            <p className="text-sm font-black text-emerald-400">✅ Déjà en portefeuille</p>
            <p className="text-[10px] text-gray-600 mt-1">Ce ticker est déjà dans vos trades actifs.</p>
          </div>
        )}

        {/* Auto-filled summary */}
        <div className="rounded-xl p-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[10px]"
          style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          {[
            { label: "Stratégie",  value: (engine?.active_strategy ?? "—").replace("_", " ") },
            { label: "Grade",      value: t.setup_grade },
            { label: "Régime",     value: engine?.regime_label ?? "—" },
            { label: "R/R",        value: `1 : ${t.rr_ratio.toFixed(1)}` },
            { label: "SL prévu",   value: `$${t.stop_loss.toFixed(2)}` },
            { label: "TP1 / TP2",  value: `$${t.tp1.toFixed(2)} / $${t.tp2.toFixed(2)}` },
          ].map(r => (
            <div key={r.label} className="flex items-center gap-1.5">
              <span className="text-gray-700">{r.label}:</span>
              <span className="text-gray-300 font-black">{r.value}</span>
            </div>
          ))}
        </div>

        {/* User fields */}
        {[
          { label: "Date d'entrée",       key: "date_entry",  type: "date",   value: form.date_entry  },
          { label: "Prix réel ($)",        key: "price_entry", type: "number", value: form.price_entry },
          { label: "Quantité (actions)",   key: "quantity",    type: "number", value: form.quantity    },
          { label: "Frais ($)",            key: "fees",        type: "number", value: form.fees        },
        ].map(f => (
          <div key={f.key}>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">{f.label}</p>
            <input
              type={f.type}
              value={f.value}
              step={f.type === "number" ? "0.01" : undefined}
              min={f.type === "number" ? "0" : undefined}
              onChange={e => set(f.key, f.type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
              style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
            />
          </div>
        ))}

        {/* Broker */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Broker</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5">
            {["IBKR", "Degiro", "Saxo", "Autre"].map(b => (
              <button key={b} onClick={() => set("broker", b)}
                className="py-1.5 rounded-lg text-xs font-black transition-all"
                style={{
                  background: form.broker === b ? "#07071e" : "#07070f",
                  color:      form.broker === b ? "#818cf8" : "#4b5563",
                  border:     `1px solid ${form.broker === b ? "#818cf8" : "#1a1a2e"}`,
                }}>
                {b}
              </button>
            ))}
          </div>
        </div>

        {/* Note */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Note (optionnelle)</p>
          <input
            type="text"
            value={form.note_entry}
            onChange={e => set("note_entry", e.target.value)}
            placeholder="Ex: achat à l'ouverture, gap up…"
            className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
            style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
          />
        </div>

        {/* Risk preview */}
        <div className="rounded-xl p-3 grid grid-cols-2 gap-2 text-center"
          style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          {[
            { label: "Capital investi", value: `$${Math.round(capitalUsd).toLocaleString()}` },
            { label: "Risque max $",    value: `$${riskUsd.toFixed(2)}` },
          ].map(s => (
            <div key={s.label}>
              <p className="text-[8px] text-gray-700 uppercase tracking-widest mb-0.5">{s.label}</p>
              <p className="text-sm font-black text-white">{s.value}</p>
            </div>
          ))}
        </div>

        <button
          onClick={handleSave}
          disabled={alreadyTaken}
          className="w-full py-3 rounded-xl text-sm font-black transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff" }}
        >
          {submitLabel ?? (journalStatus === "PLANNED" ? "✅ Préparer ce trade" : "🟠 Ajouter à la watchlist")}
        </button>

        {/* CRYPTO TRADABLE V1 WARNING MODAL */}
        {cryptoWarning.shown && (
          <div
            className="fixed inset-0 z-[70] flex items-center justify-center"
            style={{ background: "rgba(0,0,0,.9)" }}
            onClick={() => setCryptoWarning({ shown: false })}
          >
            <div
              className="w-full max-w-sm rounded-2xl p-6 space-y-4"
              style={{ background: "#2a0d0d", border: "1px solid #ef444455" }}
              onClick={e => e.stopPropagation()}
            >
              <p className="text-sm font-black text-red-300 uppercase tracking-widest">⚠️ Crypto Trade Not Authorized</p>
              <p className="text-xs text-red-200">{cryptoWarning.reason || "This crypto trade cannot be executed at this time. Please review the setup requirements."}</p>
              <button
                onClick={() => setCryptoWarning({ shown: false })}
                className="w-full py-2 rounded-lg text-sm font-black text-white transition-all"
                style={{ background: "#7f1d1d", border: "1px solid #ef4444" }}
              >
                Understood
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
