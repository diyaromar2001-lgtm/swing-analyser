"use client";

import { useState } from "react";
import { JournalTrade } from "../types";
import { useJournal } from "../hooks/useJournal";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v: number, decimals = 2) {
  return v.toFixed(decimals);
}

function pnlColor(v: number) {
  return v > 0 ? "#10b981" : v < 0 ? "#ef4444" : "#6b7280";
}

function gradeColor(g: string) {
  return g === "A+" ? "#10b981" : g === "A" ? "#a3e635" : g === "B" ? "#f59e0b" : "#6b7280";
}

function reasonColor(r: string) {
  if (r === "TP1" || r === "TP2") return "#10b981";
  if (r === "SL") return "#ef4444";
  return "#6b7280";
}

function daysAgo(dateStr: string) {
  const diff = Math.round((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return "Hier";
  return `${diff}j`;
}

// ─── Close Trade Modal ────────────────────────────────────────────────────────

function CloseModal({
  trade, onClose, onConfirm,
}: {
  trade:     JournalTrade;
  onClose:   () => void;
  onConfirm: (data: { date_exit: string; price_exit: number; reason_exit: "TP1" | "TP2" | "SL" | "MANUAL"; note_exit?: string }) => void;
}) {
  const today = new Date().toISOString().split("T")[0];
  const [form, setForm] = useState({
    date_exit:   today,
    price_exit:  trade.tp1,
    reason_exit: "TP1" as "TP1" | "TP2" | "SL" | "MANUAL",
    note_exit:   "",
  });

  // Live preview
  const pnlUsd = (form.price_exit - trade.price_entry) * trade.quantity - trade.fees;
  const pnlPct = ((form.price_exit - trade.price_entry) / trade.price_entry) * 100;
  const riskPerShare = trade.price_entry - trade.stop_loss;
  const rMultiple = riskPerShare > 0 ? pnlUsd / (riskPerShare * trade.quantity) : 0;

  const set = (k: string, v: string | number) => setForm(f => ({ ...f, [k]: v }));

  // When reason changes, auto-fill price
  const setReason = (r: typeof form.reason_exit) => {
    const prices: Record<string, number> = {
      TP1: trade.tp1, TP2: trade.tp2, SL: trade.stop_loss, MANUAL: trade.price_entry,
    };
    setForm(f => ({ ...f, reason_exit: r, price_exit: prices[r] ?? f.price_exit }));
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,.85)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-4"
        style={{ background: "#0e0e1c", border: "1px solid #2a2a4e" }}>

        <div className="flex items-center justify-between">
          <p className="font-black text-white">Clôturer {trade.ticker}</p>
          <button onClick={onClose} className="text-gray-600 hover:text-white">✕</button>
        </div>

        {/* Reason buttons */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1.5">Raison</p>
          <div className="grid grid-cols-4 gap-1.5">
            {(["TP1", "TP2", "SL", "MANUAL"] as const).map(r => (
              <button key={r} onClick={() => setReason(r)}
                className="py-1.5 rounded-lg text-xs font-black transition-all"
                style={{
                  background: form.reason_exit === r ? (r === "SL" ? "#130404" : "#041310") : "#0c0c18",
                  color:      form.reason_exit === r ? reasonColor(r) : "#4b5563",
                  border:     `1px solid ${form.reason_exit === r ? reasonColor(r) + "60" : "#1a1a2e"}`,
                }}>
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Fields */}
        {[
          { label: "Date sortie", key: "date_exit", type: "date", value: form.date_exit },
          { label: "Prix sortie ($)", key: "price_exit", type: "number", value: form.price_exit },
        ].map(f => (
          <div key={f.key}>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">{f.label}</p>
            <input
              type={f.type}
              value={f.value}
              step={f.type === "number" ? "0.01" : undefined}
              onChange={e => set(f.key, f.type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
              style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
            />
          </div>
        ))}

        {/* Note */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Note (optionnelle)</p>
          <input
            type="text"
            value={form.note_exit}
            onChange={e => set("note_exit", e.target.value)}
            placeholder="Ex: target atteint en préouverture"
            className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
            style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
          />
        </div>

        {/* Live P&L preview */}
        <div className="rounded-xl p-3 grid grid-cols-3 gap-2 text-center"
          style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          {[
            { label: "P&L $", value: `${pnlUsd >= 0 ? "+" : ""}$${fmt(pnlUsd)}` },
            { label: "P&L %", value: `${pnlPct >= 0 ? "+" : ""}${fmt(pnlPct)}%` },
            { label: "R Multiple", value: `${rMultiple >= 0 ? "+" : ""}${fmt(rMultiple, 1)}R` },
          ].map(s => (
            <div key={s.label}>
              <p className="text-[8px] text-gray-700 uppercase tracking-widest mb-0.5">{s.label}</p>
              <p className="text-sm font-black" style={{ color: pnlColor(pnlUsd) }}>{s.value}</p>
            </div>
          ))}
        </div>

        <button
          onClick={() => onConfirm(form)}
          className="w-full py-2.5 rounded-xl text-sm font-black transition-all"
          style={{ background: "#10b981", color: "#fff" }}
        >
          Confirmer la clôture
        </button>
      </div>
    </div>
  );
}

// ─── Delete Confirm ───────────────────────────────────────────────────────────

function DeleteConfirm({
  ticker, onCancel, onConfirm,
}: { ticker: string; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,.85)" }}
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="rounded-2xl p-6 space-y-4 max-w-xs w-full"
        style={{ background: "#0e0e1c", border: "1px solid #7f1d1d" }}>
        <p className="font-black text-white">Supprimer {ticker} ?</p>
        <p className="text-xs text-gray-500">Ce trade ne comptera pas dans les statistiques.</p>
        <div className="flex gap-2">
          <button onClick={onCancel} className="flex-1 py-2 rounded-lg text-xs text-gray-500"
            style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>Annuler</button>
          <button onClick={onConfirm} className="flex-1 py-2 rounded-lg text-xs font-black text-white"
            style={{ background: "#7f1d1d" }}>Supprimer</button>
        </div>
      </div>
    </div>
  );
}

// ─── Stats Panel ──────────────────────────────────────────────────────────────

function StatsPanel({ closed }: { closed: JournalTrade[] }) {
  if (closed.length === 0) return null;

  const wins      = closed.filter(t => (t.pnl_usd ?? 0) > 0);
  const losses    = closed.filter(t => (t.pnl_usd ?? 0) <= 0);
  const winRate   = closed.length ? (wins.length / closed.length) * 100 : 0;
  const totalPnl  = closed.reduce((s, t) => s + (t.pnl_usd ?? 0), 0);
  const avgGain   = wins.length ? wins.reduce((s, t) => s + (t.pnl_usd ?? 0), 0) / wins.length : 0;
  const avgLoss   = losses.length ? Math.abs(losses.reduce((s, t) => s + (t.pnl_usd ?? 0), 0) / losses.length) : 0;
  const pf        = avgLoss > 0 ? (avgGain * wins.length) / (avgLoss * losses.length) : 0;
  const avgR      = closed.reduce((s, t) => s + (t.r_multiple ?? 0), 0) / closed.length;

  const byStrategy: Record<string, { wins: number; total: number; pnl: number }> = {};
  closed.forEach(t => {
    if (!byStrategy[t.strategy]) byStrategy[t.strategy] = { wins: 0, total: 0, pnl: 0 };
    byStrategy[t.strategy].total++;
    byStrategy[t.strategy].pnl += t.pnl_usd ?? 0;
    if ((t.pnl_usd ?? 0) > 0) byStrategy[t.strategy].wins++;
  });

  const bestStrat = Object.entries(byStrategy).sort((a, b) => b[1].pnl - a[1].pnl)[0];

  return (
    <div className="rounded-2xl p-5 space-y-4" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
      <p className="text-[9px] font-black text-gray-600 uppercase tracking-widest">📊 Statistiques Réelles</p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Win Rate",      value: `${winRate.toFixed(0)}%`,   color: winRate >= 50 ? "#10b981" : "#ef4444" },
          { label: "P&L Total",     value: `${totalPnl >= 0 ? "+" : ""}$${fmt(totalPnl)}`, color: pnlColor(totalPnl) },
          { label: "Profit Factor", value: pf > 0 ? fmt(pf, 1) : "—", color: pf >= 1.5 ? "#10b981" : pf >= 1 ? "#f59e0b" : "#ef4444" },
          { label: "R Moyen",       value: `${avgR >= 0 ? "+" : ""}${fmt(avgR, 1)}R`,      color: pnlColor(avgR) },
        ].map(s => (
          <div key={s.label} className="rounded-xl p-3 text-center" style={{ background: "#07070f", border: `1px solid ${s.color}20` }}>
            <p className="text-[9px] uppercase tracking-widest mb-1" style={{ color: s.color }}>{s.label}</p>
            <p className="text-xl font-black text-white">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2 text-[10px] text-gray-600">
        <span>Gains moy. <strong className="text-emerald-400">+${fmt(avgGain)}</strong></span>
        <span>Pertes moy. <strong className="text-red-400">-${fmt(avgLoss)}</strong></span>
        {bestStrat && (
          <span>Meilleure strat. <strong className="text-gray-300">{bestStrat[0].replace("_", " ")}</strong></span>
        )}
      </div>
    </div>
  );
}

// ─── Active Trade Row ────────────────────────────────────────────────────────

function ActiveRow({
  trade, onClose, onDelete,
}: {
  trade:    JournalTrade;
  onClose:  (t: JournalTrade) => void;
  onDelete: (t: JournalTrade) => void;
}) {
  const entryTotal = trade.price_entry * trade.quantity;
  return (
    <div className="rounded-xl p-4 space-y-3" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-lg font-black text-white">{trade.ticker}</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] font-black"
            style={{ background: gradeColor(trade.setup_grade) + "18", color: gradeColor(trade.setup_grade) }}>
            {trade.setup_grade}
          </span>
          <span className="text-[10px] text-gray-600">{trade.strategy.replace("_", " ")}</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] animate-pulse"
            style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}>
            OPEN
          </span>
        </div>
        <span className="text-[10px] text-gray-700 flex-shrink-0">{daysAgo(trade.date_entry)}</span>
      </div>

      {/* Levels */}
      <div className="grid grid-cols-5 gap-1.5 text-center">
        {[
          { label: "ENTRÉE",  value: `$${fmt(trade.price_entry)}`, color: "#6366f1" },
          { label: "STOP",    value: `$${fmt(trade.stop_loss)}`,   color: "#ef4444" },
          { label: "TP1",     value: `$${fmt(trade.tp1)}`,          color: "#10b981" },
          { label: "TP2",     value: `$${fmt(trade.tp2)}`,          color: "#34d399" },
          { label: "QTÉ",     value: `${trade.quantity}`,           color: "#f59e0b" },
        ].map(l => (
          <div key={l.label} className="rounded-lg p-1.5" style={{ background: "#07070f", border: `1px solid ${l.color}15` }}>
            <p className="text-[7px] uppercase tracking-widest mb-0.5" style={{ color: l.color }}>{l.label}</p>
            <p className="text-xs font-black text-white">{l.value}</p>
          </div>
        ))}
      </div>

      {/* Meta + actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[10px] text-gray-700">Capital: <strong className="text-gray-500">${Math.round(entryTotal).toLocaleString()}</strong></span>
        <span className="text-[10px] text-gray-700">Broker: <strong className="text-gray-500">{trade.broker}</strong></span>
        {trade.note_entry && (
          <span className="text-[10px] text-gray-600 italic">{trade.note_entry}</span>
        )}
        <div className="ml-auto flex gap-1.5">
          <button
            onClick={() => onClose(trade)}
            className="px-2.5 py-1 rounded-lg text-[10px] font-black transition-all"
            style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}
          >
            Clôturer
          </button>
          <button
            onClick={() => onDelete(trade)}
            className="px-2 py-1 rounded-lg text-[10px] text-gray-600 hover:text-red-400 transition-colors"
            style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Closed Trade Row ─────────────────────────────────────────────────────────

function ClosedRow({
  trade, onDelete,
}: {
  trade:    JournalTrade;
  onDelete: (t: JournalTrade) => void;
}) {
  const pnl = trade.pnl_usd ?? 0;
  const pc  = pnlColor(pnl);
  return (
    <div className="rounded-xl p-4" style={{ background: "#0c0c18", border: `1px solid ${pc}18` }}>
      <div className="flex items-center gap-3 flex-wrap">
        {/* Ticker + grade */}
        <span className="text-base font-black text-white w-14">{trade.ticker}</span>
        <span className="px-1.5 py-0.5 rounded text-[9px] font-black"
          style={{ background: gradeColor(trade.setup_grade) + "18", color: gradeColor(trade.setup_grade) }}>
          {trade.setup_grade}
        </span>
        {/* Reason badge */}
        <span className="px-1.5 py-0.5 rounded text-[9px] font-black"
          style={{ background: reasonColor(trade.reason_exit ?? "MANUAL") + "18", color: reasonColor(trade.reason_exit ?? "MANUAL") }}>
          {trade.reason_exit ?? "MANUAL"}
        </span>
        {/* Strategy */}
        <span className="text-[10px] text-gray-600">{trade.strategy.replace("_", " ")}</span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Prices */}
        <span className="text-[10px] text-gray-600">
          ${fmt(trade.price_entry)} → ${fmt(trade.price_exit ?? 0)}
        </span>
        {/* P&L */}
        <span className="text-sm font-black" style={{ color: pc }}>
          {pnl >= 0 ? "+" : ""}${fmt(pnl)}
        </span>
        <span className="text-[10px] font-black" style={{ color: pc }}>
          {(trade.pnl_pct ?? 0) >= 0 ? "+" : ""}{fmt(trade.pnl_pct ?? 0)}%
        </span>
        {/* R */}
        <span className="text-[10px] font-black px-1.5 py-0.5 rounded"
          style={{ background: pc + "18", color: pc }}>
          {(trade.r_multiple ?? 0) >= 0 ? "+" : ""}{fmt(trade.r_multiple ?? 0, 1)}R
        </span>
        {/* Duration */}
        <span className="text-[10px] text-gray-600">{trade.duration_days}j</span>
        {/* Delete */}
        <button onClick={() => onDelete(trade)}
          className="text-[10px] text-gray-700 hover:text-red-400 transition-colors px-1">✕</button>
      </div>
      {trade.note_exit && (
        <p className="text-[9px] text-gray-600 italic mt-1.5 ml-1">📝 {trade.note_exit}</p>
      )}
    </div>
  );
}

// ─── Main Journal Component ───────────────────────────────────────────────────

export function TradeJournal() {
  const { activeTrades, closedTrades, closeTrade, deleteTrade } = useJournal();

  const [tab,          setTab]          = useState<"active" | "closed">("active");
  const [toClose,      setToClose]      = useState<JournalTrade | null>(null);
  const [toDelete,     setToDelete]     = useState<{ trade: JournalTrade; fromActive: boolean } | null>(null);

  return (
    <div className="space-y-4">

      {/* Stats panel (from closed trades only) */}
      <StatsPanel closed={closedTrades} />

      {/* Tab bar */}
      <div className="flex rounded-xl overflow-hidden" style={{ border: "1px solid #1a1a2e", display: "inline-flex" }}>
        {([["active", `📌 En cours (${activeTrades.length})`], ["closed", `✅ Historique (${closedTrades.length})`]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className="px-4 py-2 text-xs font-black uppercase tracking-widest transition-all"
            style={{
              background: tab === k ? (k === "active" ? "#041a10" : "#0a0a1e") : "#0c0c18",
              color:      tab === k ? (k === "active" ? "#10b981" : "#818cf8") : "#4b5563",
              borderRight: k === "active" ? "1px solid #1a1a2e" : undefined,
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* Active trades */}
      {tab === "active" && (
        <div className="space-y-3">
          {activeTrades.length === 0 ? (
            <div className="text-center py-16 text-gray-600 text-sm">
              Aucun trade en cours — prenez un trade depuis le Command Center ⚡
            </div>
          ) : (
            activeTrades.map(t => (
              <ActiveRow
                key={t.id}
                trade={t}
                onClose={setToClose}
                onDelete={tr => setToDelete({ trade: tr, fromActive: true })}
              />
            ))
          )}
        </div>
      )}

      {/* Closed trades */}
      {tab === "closed" && (
        <div className="space-y-2">
          {closedTrades.length === 0 ? (
            <div className="text-center py-16 text-gray-600 text-sm">
              Aucun trade clôturé pour l'instant.
            </div>
          ) : (
            closedTrades.map(t => (
              <ClosedRow
                key={t.id}
                trade={t}
                onDelete={tr => setToDelete({ trade: tr, fromActive: false })}
              />
            ))
          )}
        </div>
      )}

      {/* Close modal */}
      {toClose && (
        <CloseModal
          trade={toClose}
          onClose={() => setToClose(null)}
          onConfirm={data => {
            closeTrade(toClose.id, data);
            setToClose(null);
          }}
        />
      )}

      {/* Delete confirmation */}
      {toDelete && (
        <DeleteConfirm
          ticker={toDelete.trade.ticker}
          onCancel={() => setToDelete(null)}
          onConfirm={() => {
            deleteTrade(toDelete.trade.id, toDelete.fromActive);
            setToDelete(null);
          }}
        />
      )}
    </div>
  );
}
