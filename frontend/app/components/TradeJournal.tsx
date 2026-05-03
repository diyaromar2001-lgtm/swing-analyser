"use client";

import { useMemo, useState } from "react";
import { useJournal } from "../hooks/useJournal";
import { JournalTrade } from "../types";

const SIM_CAPITAL = 10_000;
const DEFAULT_RISK_PCT = 0.01;

function fmt(value?: number | null, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function money(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `$${Math.abs(value).toFixed(2)}`;
}

function statusLabel(status: JournalTrade["status"]) {
  switch (status) {
    case "OPEN":
      return { label: "OPEN", color: "#10b981", bg: "#041310" };
    case "PLANNED":
      return { label: "PLANNED", color: "#818cf8", bg: "#0b1020" };
    case "WATCHLIST":
      return { label: "WATCHLIST", color: "#f59e0b", bg: "#20150a" };
    case "CLOSED":
      return { label: "CLOSED", color: "#6b7280", bg: "#0f0f1a" };
    case "CANCELLED":
      return { label: "CANCELLED", color: "#ef4444", bg: "#1a0d0d" };
    default:
      return { label: status, color: "#9ca3af", bg: "#111118" };
  }
}

function pnlColor(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "#9ca3af";
  return value > 0 ? "#10b981" : value < 0 ? "#ef4444" : "#6b7280";
}

function normalizeText(value?: unknown) {
  return String(value ?? "").trim().toUpperCase();
}

function canOpenTrade(trade: JournalTrade) {
  return (
    trade.status === "PLANNED" &&
    trade.execution_authorized === true &&
    (normalizeText(trade.edge_status) === "STRONG_EDGE" || normalizeText(trade.edge_status) === "VALID_EDGE") &&
    (normalizeText(trade.final_decision) === "BUY" || normalizeText(trade.final_decision) === "BUY NOW" || normalizeText(trade.final_decision) === "BUY NEAR ENTRY") &&
    trade.setup_status !== "INVALID" &&
    trade.overfit_warning !== true
  );
}

function openBlockReason(trade: JournalTrade) {
  if (trade.status === "WATCHLIST") return "WATCHLIST";
  if (trade.execution_authorized !== true) return "Trade opening blocked: execution not authorized";
  if (normalizeText(trade.edge_status) === "NO_EDGE" || normalizeText(trade.edge_status) === "WEAK_EDGE" || normalizeText(trade.edge_status) === "OVERFITTED") {
    return "Ouverture bloquée — edge non validé";
  }
  if (!(normalizeText(trade.final_decision) === "BUY" || normalizeText(trade.final_decision) === "BUY NOW" || normalizeText(trade.final_decision) === "BUY NEAR ENTRY")) {
    return "Ouverture bloquée — décision finale non autorisée";
  }
  if (trade.setup_status === "INVALID") return "Ouverture bloquée — setup invalide";
  if (trade.overfit_warning === true) return "Ouverture bloquée — backtest suspect";
  if (trade.status !== "PLANNED") return "Ouverture bloquée — statut non planifié";
  return null;
}

function isNonConformingOpen(trade: JournalTrade) {
  return trade.status === "OPEN" && !canOpenTrade({ ...trade, status: "PLANNED" });
}

function Section({
  title,
  items,
  onEdit,
  onOpen,
  onCloseTrade,
  onCancel,
  onAddNote,
}: {
  title: string;
  items: JournalTrade[];
  onEdit: (trade: JournalTrade) => void;
  onOpen: (trade: JournalTrade) => void;
  onCloseTrade: (trade: JournalTrade) => void;
  onCancel: (trade: JournalTrade) => void;
  onAddNote: (trade: JournalTrade) => void;
}) {
  return (
    <div className="rounded-2xl p-4 space-y-3" style={{ background: "#0c0c18", border: "1px solid #1a1a2e" }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] text-gray-600 uppercase tracking-widest">{title}</p>
          <p className="text-xs text-gray-500">{items.length} trade{items.length > 1 ? "s" : ""}</p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="py-8 text-center text-gray-600 text-sm">Aucun élément</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1200px] text-left border-collapse">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                {["Universe", "Symbol", "Status", "Grade", "Edge", "Strategy", "Entry", "Stop", "TP1", "TP2", "Risk", "Qty", "PnL", "R", "Date", "Actions"].map(col => (
                  <th key={col} className="py-2 pr-3 border-b border-[#1a1a2e]">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(trade => {
                const badge = statusLabel(trade.status);
                const pnl = trade.pnl_usd ?? 0;
                const riskPct = trade.risk_pct ?? DEFAULT_RISK_PCT * 100;
                const openAllowed = canOpenTrade(trade);
                const blockedReason = openBlockReason(trade);
                const nonConformingOpen = isNonConformingOpen(trade);
                return (
                  <tr key={trade.id} className="align-top hover:bg-white/[0.02]">
                    <td className="py-3 pr-3 text-xs text-gray-400 border-b border-[#141425]">{trade.universe ?? "ACTIONS"}</td>
                    <td className="py-3 pr-3 text-sm font-black text-white border-b border-[#141425]">{trade.symbol ?? trade.ticker}</td>
                    <td className="py-3 pr-3 border-b border-[#141425]">
                      <span className="px-2 py-1 rounded text-[10px] font-black" style={{ color: badge.color, background: badge.bg }}>{badge.label}</span>
                    </td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{trade.setup_grade ?? "—"}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{trade.edge_status ?? "—"}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{(trade.strategy_name ?? trade.strategy ?? "—").replaceAll("_", " ")}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{money(trade.entry_price ?? trade.entry_plan)}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{money(trade.stop_loss)}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{money(trade.tp1)}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{money(trade.tp2)}</td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">
                      {money(trade.risk_amount)} <span className="text-gray-600">({fmt(riskPct, 1)}%)</span>
                    </td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{fmt(trade.quantity, 4)}</td>
                    <td className="py-3 pr-3 text-xs font-black border-b border-[#141425]" style={{ color: pnlColor(pnl) }}>
                      {pnl >= 0 ? "+" : ""}{money(pnl)}
                    </td>
                    <td className="py-3 pr-3 text-xs text-gray-300 border-b border-[#141425]">{trade.r_multiple != null ? `${trade.r_multiple >= 0 ? "+" : ""}${fmt(trade.r_multiple, 2)}R` : "—"}</td>
                    <td className="py-3 pr-3 text-xs text-gray-400 border-b border-[#141425]">{trade.date_entry ?? trade.opened_at ?? "—"}</td>
                    <td className="py-3 pr-3 text-xs border-b border-[#141425]">
                      {nonConformingOpen && (
                        <div className="mb-2 rounded-lg px-2 py-1 text-[10px] font-bold" style={{ background: "#2a0d0d", border: "1px solid #7f1d1d", color: "#fca5a5" }}>
                          Position ouverte non conforme
                        </div>
                      )}
                      {trade.status === "PLANNED" && !openAllowed && blockedReason && (
                        <div className="mb-2 rounded-lg px-2 py-1 text-[10px] font-bold" style={{ background: "#20150a", border: "1px solid #f59e0b55", color: "#fcd34d" }}>
                          {blockedReason}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {trade.status === "PLANNED" && openAllowed && (
                          <button onClick={() => onOpen(trade)} className="px-2 py-1 rounded text-[10px] font-black" style={{ background: "#041310", color: "#10b981", border: "1px solid #065f46" }}>
                            Ouvrir
                          </button>
                        )}
                        {trade.status === "PLANNED" && !openAllowed && (
                          <button disabled className="px-2 py-1 rounded text-[10px] font-black opacity-60" style={{ background: "#1a0d0d", color: "#fca5a5", border: "1px solid #7f1d1d" }}>
                            Ouvrir bloqu?
                          </button>
                        )}
                        {trade.status === "OPEN" && (
                          <button onClick={() => onCloseTrade(trade)} className="px-2 py-1 rounded text-[10px] font-black" style={{ background: "#0b1020", color: "#818cf8", border: "1px solid #3b82f6" }}>
                            Fermer
                          </button>
                        )}
                        <button onClick={() => onEdit(trade)} className="px-2 py-1 rounded text-[10px] font-black" style={{ background: "#0c0c18", color: "#f59e0b", border: "1px solid #a16207" }}>
                          Modifier
                        </button>
                        <button onClick={() => onAddNote(trade)} className="px-2 py-1 rounded text-[10px] font-black" style={{ background: "#0c0c18", color: "#cbd5e1", border: "1px solid #1f2937" }}>
                          Ajouter note
                        </button>
                        <button onClick={() => onCancel(trade)} className="px-2 py-1 rounded text-[10px] font-black" style={{ background: "#1a0d0d", color: "#fca5a5", border: "1px solid #7f1d1d" }}>
                          Annuler
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PortfolioRiskCard({ openTrades, plannedTrades, watchlistTrades, stats }: {
  openTrades: JournalTrade[];
  plannedTrades: JournalTrade[];
  watchlistTrades: JournalTrade[];
  stats: ReturnType<typeof useJournal>["stats"];
}) {
  const riskOpenTotal = stats?.risk_open_total ?? openTrades.reduce((sum, t) => sum + (t.risk_amount ?? 0), 0);
  const exposure = stats?.exposure_current ?? openTrades.reduce((sum, t) => sum + (t.entry_price ?? t.entry_plan ?? 0) * (t.quantity ?? 0), 0);
  const openCount = openTrades.length;
  const pctRisk = (riskOpenTotal / SIM_CAPITAL) * 100;
  const riskColor = pctRisk > 5 ? "#ef4444" : pctRisk > 3 ? "#f59e0b" : "#10b981";

  return (
    <div className="rounded-2xl p-4 space-y-3" style={{ background: "#0c0c18", border: `1px solid ${riskColor}33` }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] text-gray-600 uppercase tracking-widest">Portfolio Risk</p>
          <p className="text-xs text-gray-500">Capital simulé: ${SIM_CAPITAL.toLocaleString()}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">Risque ouvert</p>
          <p className="text-lg font-black" style={{ color: riskColor }}>{fmt(pctRisk, 1)}%</p>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Trades ouverts</p>
          <p className="text-lg font-black text-white">{openCount}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Planifiés</p>
          <p className="text-lg font-black text-white">{plannedTrades.length}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Watchlist</p>
          <p className="text-lg font-black text-white">{watchlistTrades.length}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Exposition estimée</p>
          <p className="text-lg font-black text-white">${Math.round(exposure).toLocaleString()}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Risque ouvert total</p>
          <p className="text-lg font-black text-white">${riskOpenTotal.toFixed(2)}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">PnL réalisé</p>
          <p className="text-lg font-black text-white">${(stats?.total_pnl ?? 0).toFixed(2)}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">R moyen</p>
          <p className="text-lg font-black text-white">{fmt(stats?.average_r ?? 0, 2)}R</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
          <p className="text-gray-500">Max positions</p>
          <p className="text-lg font-black text-white">A {stats?.max_positions_actions ?? 5} / C {stats?.max_positions_crypto ?? 3}</p>
        </div>
      </div>
      {pctRisk > 5 && (
        <div className="rounded-xl px-3 py-2 text-sm font-bold" style={{ background: "#2a0d0d", border: "1px solid #7f1d1d", color: "#fca5a5" }}>
          Risque total supérieur à 5% : réduire l&apos;exposition.
        </div>
      )}
      {pctRisk > 3 && pctRisk <= 5 && (
        <div className="rounded-xl px-3 py-2 text-sm font-bold" style={{ background: "#2a220d", border: "1px solid #a16207", color: "#fcd34d" }}>
          Risque total supérieur à 3% : surveiller le portefeuille.
        </div>
      )}
    </div>
  );
}

function TradeEditor({
  trade,
  mode,
  onClose,
  onSave,
}: {
  trade: JournalTrade | null;
  mode: "EDIT" | "NOTE" | "OPEN";
  onClose: () => void;
  onSave: (updates: Partial<JournalTrade>) => void;
}) {
  const [form, setForm] = useState({
    status: trade?.status ?? "WATCHLIST",
    entry_price: trade?.entry_price ?? trade?.planned_entry ?? 0,
    stop_loss: trade?.stop_loss ?? 0,
    tp1: trade?.tp1 ?? 0,
    tp2: trade?.tp2 ?? 0,
    quantity: trade?.quantity ?? 0,
    risk_amount: trade?.risk_amount ?? 0,
    notes: trade?.notes ?? trade?.note_entry ?? "",
    final_decision: trade?.final_decision ?? "WAIT",
    edge_status: trade?.edge_status ?? "NO_EDGE",
  });

  if (!trade) return null;

  const set = (key: string, value: string | number) => setForm(prev => ({ ...prev, [key]: value }));

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center" style={{ background: "rgba(0,0,0,.85)" }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-xl rounded-2xl p-6 space-y-4" style={{ background: "#0e0e1c", border: "1px solid #2a2a4e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] text-gray-600 uppercase tracking-widest">{mode === "NOTE" ? "Ajouter une note" : "Modifier le trade"}</p>
            <p className="text-xl font-black text-white">{trade.symbol ?? trade.ticker}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white">✕</button>
        </div>
        {mode !== "NOTE" && (
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Status", key: "status", type: "text", value: form.status },
              { label: "Entry", key: "entry_price", type: "number", value: form.entry_price },
              { label: "Stop", key: "stop_loss", type: "number", value: form.stop_loss },
              { label: "TP1", key: "tp1", type: "number", value: form.tp1 },
              { label: "TP2", key: "tp2", type: "number", value: form.tp2 },
              { label: "Qty", key: "quantity", type: "number", value: form.quantity },
              { label: "Risk $", key: "risk_amount", type: "number", value: form.risk_amount },
              { label: "Edge", key: "edge_status", type: "text", value: form.edge_status },
            ].map(field => (
              <div key={field.key}>
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">{field.label}</p>
                <input
                  type={field.type}
                  value={field.value as any}
                  step={field.type === "number" ? "0.01" : undefined}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                  style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
                  onChange={e => set(field.key, field.type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)}
                />
              </div>
            ))}
          </div>
        )}
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Note</p>
          <textarea
            value={form.notes}
            onChange={e => set("notes", e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none resize-none"
            style={{ background: "#07070f", border: "1px solid #1a1a2e" }}
          />
        </div>
        <button
          onClick={() => onSave(form)}
          className="w-full py-3 rounded-xl text-sm font-black"
          style={{ background: "#10b981", color: "#fff" }}
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}

function CloseModal({
  trade,
  onClose,
  onConfirm,
}: {
  trade: JournalTrade | null;
  onClose: () => void;
  onConfirm: (payload: { exit_price: number; exit_reason: string; notes?: string; closed_at?: string }) => void;
}) {
  const [exitPrice, setExitPrice] = useState(trade?.entry_price ?? trade?.planned_entry ?? 0);
  const [reason, setReason] = useState("MANUAL");
  const [notes, setNotes] = useState("");
  if (!trade) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center" style={{ background: "rgba(0,0,0,.85)" }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-4" style={{ background: "#0e0e1c", border: "1px solid #2a2a4e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="font-black text-white">Fermer {trade.symbol ?? trade.ticker}</p>
          <button onClick={onClose} className="text-gray-500 hover:text-white">✕</button>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Prix de sortie</p>
          <input value={exitPrice} onChange={e => setExitPrice(parseFloat(e.target.value) || 0)} type="number" step="0.01" className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none" style={{ background: "#07070f", border: "1px solid #1a1a2e" }} />
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Raison</p>
          <select value={reason} onChange={e => setReason(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none" style={{ background: "#07070f", border: "1px solid #1a1a2e" }}>
            {["TP1", "TP2", "SL", "MANUAL"].map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Note</p>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3} className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none resize-none" style={{ background: "#07070f", border: "1px solid #1a1a2e" }} />
        </div>
        <button onClick={() => onConfirm({ exit_price: exitPrice, exit_reason: reason, notes, closed_at: new Date().toISOString() })} className="w-full py-3 rounded-xl text-sm font-black" style={{ background: "#10b981", color: "#fff" }}>
          Confirmer la clôture
        </button>
      </div>
    </div>
  );
}

export function TradeJournal() {
  const { trades, stats, openTrade, closeTrade, deleteTrade, updateTrade, refreshJournal, isSyncing, lastSyncError } = useJournal();
  const [editTrade, setEditTrade] = useState<JournalTrade | null>(null);
  const [editMode, setEditMode] = useState<"EDIT" | "NOTE" | "OPEN">("EDIT");
  const [closeTradeItem, setCloseTradeItem] = useState<JournalTrade | null>(null);

  const openTrades = useMemo(() => trades.filter(t => t.status === "OPEN"), [trades]);
  const plannedTrades = useMemo(() => trades.filter(t => t.status === "PLANNED"), [trades]);
  const watchlistTrades = useMemo(() => trades.filter(t => t.status === "WATCHLIST"), [trades]);
  const closedTrades = useMemo(() => trades.filter(t => t.status === "CLOSED"), [trades]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[10px] text-gray-600 uppercase tracking-widest">Trade Journal</p>
          <p className="text-xs text-gray-500">Journal persistant Actions / Crypto</p>
        </div>
        <button
          onClick={() => void refreshJournal()}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          style={{ background: "#0c0c18", border: "1px solid #1a1a2e", color: "#818cf8" }}
        >
          {isSyncing ? "Synchronisation…" : "Rafraîchir"}
        </button>
      </div>

      {lastSyncError && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "#130404", border: "1px solid #7f1d1d", color: "#fca5a5" }}>
          Synchronisation journal: {lastSyncError}
        </div>
      )}

      <PortfolioRiskCard openTrades={openTrades} plannedTrades={plannedTrades} watchlistTrades={watchlistTrades} stats={stats} />

      <Section
        title="Positions ouvertes"
        items={openTrades}
        onEdit={trade => { setEditMode("EDIT"); setEditTrade(trade); }}
        onOpen={trade => {
          void openTrade(trade.id, {
            entry_price: trade.entry_price ?? trade.planned_entry,
            quantity: trade.quantity,
            risk_amount: trade.risk_amount,
            opened_at: new Date().toISOString(),
            notes: trade.notes ?? trade.note_entry,
          });
        }}
        onCloseTrade={trade => setCloseTradeItem(trade)}
        onCancel={trade => void deleteTrade(trade.id)}
        onAddNote={trade => { setEditMode("NOTE"); setEditTrade(trade); }}
      />

      <Section
        title="Trades planifiés"
        items={plannedTrades}
        onEdit={trade => { setEditMode("EDIT"); setEditTrade(trade); }}
        onOpen={trade => {
          void openTrade(trade.id, {
            entry_price: trade.entry_price ?? trade.planned_entry,
            quantity: trade.quantity,
            risk_amount: trade.risk_amount,
            opened_at: new Date().toISOString(),
            notes: trade.notes ?? trade.note_entry,
          });
        }}
        onCloseTrade={trade => setCloseTradeItem(trade)}
        onCancel={trade => void deleteTrade(trade.id)}
        onAddNote={trade => { setEditMode("NOTE"); setEditTrade(trade); }}
      />

      <Section
        title="Watchlist"
        items={watchlistTrades}
        onEdit={trade => { setEditMode("EDIT"); setEditTrade(trade); }}
        onOpen={trade => {
          void openTrade(trade.id, {
            entry_price: trade.entry_price ?? trade.planned_entry,
            quantity: trade.quantity,
            risk_amount: trade.risk_amount,
            opened_at: new Date().toISOString(),
            notes: trade.notes ?? trade.note_entry,
          });
        }}
        onCloseTrade={trade => setCloseTradeItem(trade)}
        onCancel={trade => void deleteTrade(trade.id)}
        onAddNote={trade => { setEditMode("NOTE"); setEditTrade(trade); }}
      />

      <Section
        title="Trades fermés"
        items={closedTrades}
        onEdit={trade => { setEditMode("EDIT"); setEditTrade(trade); }}
        onOpen={trade => {
          void openTrade(trade.id, {
            entry_price: trade.entry_price ?? trade.planned_entry,
            quantity: trade.quantity,
            risk_amount: trade.risk_amount,
            opened_at: new Date().toISOString(),
            notes: trade.notes ?? trade.note_entry,
          });
        }}
        onCloseTrade={trade => setCloseTradeItem(trade)}
        onCancel={trade => void deleteTrade(trade.id)}
        onAddNote={trade => { setEditMode("NOTE"); setEditTrade(trade); }}
      />

      {editTrade && (
        <TradeEditor
          trade={editTrade}
          mode={editMode}
          onClose={() => setEditTrade(null)}
          onSave={updates => {
            void updateTrade(editTrade.id, updates);
            setEditTrade(null);
          }}
        />
      )}

      {closeTradeItem && (
        <CloseModal
          trade={closeTradeItem}
          onClose={() => setCloseTradeItem(null)}
          onConfirm={payload => {
            void closeTrade(closeTradeItem.id, payload);
            setCloseTradeItem(null);
          }}
        />
      )}

      <div className="text-[10px] text-gray-600">
        Conseils portefeuille: risque par trade 1% par défaut, max 5 positions Actions et 3 positions Crypto.
      </div>
    </div>
  );
}
