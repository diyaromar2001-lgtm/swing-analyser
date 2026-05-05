"use client";

import { useState, useEffect } from "react";

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

export function CryptoScalpPaperJournal() {
  const [trades, setTrades] = useState<ScalpTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("all");

  useEffect(() => {
    loadTrades();
  }, []);

  const loadTrades = async () => {
    try {
      const response = await fetch("/api/crypto/scalp/journal/trades");
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
      const response = await fetch(`/api/crypto/scalp/journal/close/${tradeId}`, {
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
    if (filterStatus === "all") return true;
    return t.status === filterStatus;
  });

  const openTrades = filteredTrades.filter((t) => t.status === "SCALP_PAPER_PLANNED");
  const closedTrades = filteredTrades.filter((t) => t.status === "SCALP_PAPER_CLOSED");

  return (
    <div className="w-full max-w-6xl mx-auto p-4">
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "2px solid #1e1e2a" }}>
        <h2 className="text-2xl font-bold text-white mb-4">📓 Paper Journal</h2>

        {/* Filters */}
        <div className="flex gap-2 mb-4">
          {["all", "SCALP_PAPER_PLANNED", "SCALP_PAPER_CLOSED"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
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
                  </tr>
                </thead>
                <tbody>
                  {closedTrades.map((trade) => (
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
                    </tr>
                  ))}
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
