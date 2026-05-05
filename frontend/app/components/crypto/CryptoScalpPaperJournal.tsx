"use client";

import { useState, useEffect } from "react";
import { getApiUrl } from "../../lib/api";

const API_URL = getApiUrl();

export interface ScalpTrade {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  entry_price: number;
  exit_price?: number;
  stop_loss: number;
  tp1: number;
  tp2?: number;
  status: "SCALP_PAPER_PLANNED" | "SCALP_PAPER_CLOSED" | "SCALP_WATCHLIST";
  created_at: string;
  closed_at?: string;
  entry_fee_pct?: number;
  exit_fee_pct?: number;
  slippage_pct?: number;
  spread_bps?: number;
  pnl_pct?: number;
  actual_pnl_pct_net?: number;
  r_multiple?: number;
  closure_reason?: string;
  estimated_roundtrip_cost_pct?: number;
}

function exportTradesToCSV(trades: ScalpTrade[]) {
  if (trades.length === 0) {
    alert("Aucun trade à exporter");
    return;
  }

  const headers = ["Symbol", "Side", "Status", "Entry Price", "Exit Price", "Stop Loss", "TP1", "Entry Fee %", "Exit Fee %", "Slippage %", "Spread BPS", "Roundtrip Cost %", "Gross PnL %", "Net PnL %", "R Multiple", "Hold Time (min)", "Closure Reason", "Created", "Closed"];
  const rows = trades.map(t => [
    t.symbol,
    t.direction,
    t.status,
    t.entry_price.toFixed(4),
    t.exit_price ? t.exit_price.toFixed(4) : "—",
    t.stop_loss.toFixed(4),
    t.tp1.toFixed(4),
    (t.entry_fee_pct ?? 0).toFixed(3),
    (t.exit_fee_pct ?? 0).toFixed(3),
    (t.slippage_pct ?? 0).toFixed(3),
    (t.spread_bps ?? 0).toString(),
    (t.estimated_roundtrip_cost_pct ?? 0).toFixed(3),
    (t.pnl_pct ?? 0).toFixed(3),
    (t.actual_pnl_pct_net ?? 0).toFixed(3),
    (t.r_multiple ?? 0).toFixed(2),
    (t.r_multiple && t.closed_at ? ((new Date(t.closed_at).getTime() - new Date(t.created_at).getTime()) / 60000).toFixed(2) : "—"),
    t.closure_reason ?? "—",
    new Date(t.created_at).toLocaleString("fr-FR"),
    t.closed_at ? new Date(t.closed_at).toLocaleString("fr-FR") : "—",
  ]);

  const csvContent = [
    headers.join(","),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(",")),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", `scalp-paper-journal-${new Date().toISOString().split("T")[0]}.csv`);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function CryptoScalpPaperJournal() {
  const [trades, setTrades] = useState<ScalpTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterSymbol, setFilterSymbol] = useState("");
  const [filterSide, setFilterSide] = useState<"" | "LONG" | "SHORT">("");

  // Unique symbols for filter dropdown
  const uniqueSymbols = Array.from(new Set(trades.map(t => t.symbol))).sort();

  useEffect(() => {
    loadTrades();
  }, []);

  const loadTrades = async () => {
    try {
      const response = await fetch(`${API_URL}/api/crypto/scalp/journal/trades`);
      const data = await response.json();
      setTrades(data.trades || []);
    } catch (error) {
      console.error("Failed to load trades:", error);
    } finally {
      setLoading(false);
    }
  };

  const closeTrade = async (tradeId: string) => {
    const exitPrice = prompt("Entrez le prix de sortie:");
    if (!exitPrice) return;

    try {
      const response = await fetch(`${API_URL}/api/crypto/scalp/journal/close/${tradeId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exit_price: parseFloat(exitPrice),
          closure_reason: "MANUAL_EXIT",
        }),
      });
      const result = await response.json();
      if (result.ok) {
        alert(`Trade fermé: PnL net ${result.net_pnl_pct}%`);
        loadTrades();
      } else {
        alert(`Erreur: ${result.error}`);
      }
    } catch (error) {
      alert(`Erreur: ${error}`);
    }
  };

  const filteredTrades = trades.filter((t) => {
    if (filterStatus !== "all" && t.status !== filterStatus) return false;
    if (filterSymbol && t.symbol !== filterSymbol) return false;
    if (filterSide && t.direction !== filterSide) return false;
    return true;
  });

  const openTrades = filteredTrades.filter((t) => t.status === "SCALP_PAPER_PLANNED");
  const closedTrades = filteredTrades.filter((t) => t.status === "SCALP_PAPER_CLOSED");

  return (
    <div className="w-full max-w-6xl mx-auto p-4">
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "2px solid #1e1e2a" }}>
        <h2 className="text-2xl font-bold text-white mb-4">📓 Paper Journal</h2>

        {/* Filters */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {/* Status Filter */}
          <div className="flex gap-1">
            {["all", "SCALP_PAPER_PLANNED", "SCALP_PAPER_CLOSED"].map((status) => (
              <button
                key={status}
                onClick={() => setFilterStatus(status as any)}
                className={`px-4 py-2 rounded-lg font-bold text-sm ${
                  filterStatus === status
                    ? "bg-cyan-600 text-white"
                    : "bg-gray-900 text-gray-400 hover:bg-gray-800"
                }`}
              >
                {status === "all" ? "Tous" : status === "SCALP_PAPER_PLANNED" ? "Ouverts" : "Fermés"}
              </button>
            ))}
          </div>

          {/* Symbol Filter */}
          <select
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm bg-gray-900 border border-gray-700 text-white"
          >
            <option value="">Tous symboles</option>
            {uniqueSymbols.map((sym) => (
              <option key={sym} value={sym}>{sym}</option>
            ))}
          </select>

          {/* Side Filter */}
          <select
            value={filterSide}
            onChange={(e) => setFilterSide(e.target.value as any)}
            className="px-3 py-2 rounded-lg text-sm bg-gray-900 border border-gray-700 text-white"
          >
            <option value="">Tous côtés</option>
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>

          {/* Export CSV Button */}
          <button
            onClick={() => exportTradesToCSV(filteredTrades)}
            className="px-4 py-2 rounded-lg font-bold text-sm bg-green-900 border border-green-600 text-green-300 hover:bg-green-800 transition"
          >
            📥 Export CSV
          </button>
        </div>

        {/* Open Trades */}
        {openTrades.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-bold text-green-400 mb-3">Trades Ouverts ({openTrades.length})</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e1e2a" }}>
                    <th className="text-left p-2 text-gray-500">Symbol</th>
                    <th className="text-left p-2 text-gray-500">Side</th>
                    <th className="text-right p-2 text-gray-500">Entry</th>
                    <th className="text-right p-2 text-gray-500">TP1</th>
                    <th className="text-right p-2 text-gray-500">SL</th>
                    <th className="text-right p-2 text-gray-500">Coût</th>
                    <th className="text-center p-2 text-gray-500">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {openTrades.map((trade) => (
                    <tr key={trade.id} style={{ borderBottom: "1px solid #1e1e2a" }}>
                      <td className="p-2 font-bold text-white">{trade.symbol}</td>
                      <td className={`p-2 font-bold ${trade.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>
                        {trade.direction}
                      </td>
                      <td className="text-right p-2 text-gray-300">${trade.entry_price?.toFixed(2)}</td>
                      <td className="text-right p-2 text-gray-300">${trade.tp1?.toFixed(2)}</td>
                      <td className="text-right p-2 text-gray-300">${trade.stop_loss?.toFixed(2)}</td>
                      <td className="text-right p-2 text-orange-400">{trade.estimated_roundtrip_cost_pct?.toFixed(3)}%</td>
                      <td className="text-center p-2">
                        <button
                          onClick={() => closeTrade(trade.id)}
                          className="px-2 py-1 bg-blue-700 text-blue-200 rounded text-xs hover:bg-blue-600"
                        >
                          Fermer
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Closed Trades */}
        {closedTrades.length > 0 && (
          <div>
            <h3 className="text-lg font-bold text-blue-400 mb-3">Trades Fermés ({closedTrades.length})</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e1e2a" }}>
                    <th className="text-left p-2 text-gray-500">Symbol</th>
                    <th className="text-left p-2 text-gray-500">Side</th>
                    <th className="text-right p-2 text-gray-500">Entry</th>
                    <th className="text-right p-2 text-gray-500">Exit</th>
                    <th className="text-right p-2 text-gray-500">PnL Brut</th>
                    <th className="text-right p-2 text-gray-500">PnL Net</th>
                    <th className="text-right p-2 text-gray-500">R/R</th>
                    <th className="text-right p-2 text-gray-500">Hold (min)</th>
                  </tr>
                </thead>
                <tbody>
                  {closedTrades.map((trade) => {
                    const holdTimeMinutes = trade.closed_at && trade.created_at
                      ? ((new Date(trade.closed_at).getTime() - new Date(trade.created_at).getTime()) / 60000).toFixed(2)
                      : null;
                    return (
                      <tr key={trade.id} style={{ borderBottom: "1px solid #1e1e2a" }}>
                        <td className="p-2 font-bold text-white">{trade.symbol}</td>
                        <td className={`p-2 font-bold ${trade.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>
                          {trade.direction}
                        </td>
                        <td className="text-right p-2 text-gray-300">${trade.entry_price?.toFixed(2)}</td>
                        <td className="text-right p-2 text-gray-300">${trade.exit_price?.toFixed(2)}</td>
                        <td className={`text-right p-2 font-bold ${(trade.pnl_pct || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {trade.pnl_pct?.toFixed(3)}%
                        </td>
                        <td className={`text-right p-2 font-bold ${(trade.actual_pnl_pct_net || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {trade.actual_pnl_pct_net?.toFixed(3)}%
                        </td>
                        <td className="text-right p-2 text-cyan-400">{trade.r_multiple?.toFixed(2)}</td>
                        <td className="text-right p-2 text-orange-400">{holdTimeMinutes ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {filteredTrades.length === 0 && !loading && (
          <p className="text-gray-500 text-center py-4">Aucun trade paper scalp pour l'instant</p>
        )}
      </div>
    </div>
  );
}
