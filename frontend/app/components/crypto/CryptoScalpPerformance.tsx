"use client";

import { useState, useEffect } from "react";
import { getApiUrl } from "../../lib/api";

const API_URL = getApiUrl();

export function CryptoScalpPerformance() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  useEffect(() => {
    loadPerformance();
  }, [selectedSymbol]);

  const loadPerformance = async () => {
    try {
      const url = selectedSymbol
        ? `${API_URL}/api/crypto/scalp/journal/performance?symbol=${selectedSymbol}`
        : `${API_URL}/api/crypto/scalp/journal/performance`;
      const response = await fetch(url);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error("Failed to load performance:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-white p-4">Chargement...</div>;
  }

  if (!stats) {
    return <div className="text-gray-500 p-4">Impossible de charger les stats</div>;
  }

  const {
    total_trades = 0,
    winning_trades = 0,
    win_pct = 0,
    avg_r_winner = 0,
    avg_r_loser = 0,
    best_r = 0,
    worst_r = 0,
    net_pnl_pct = 0,
    net_pnl_usd = 0,
    symbols_traded = [],
  } = stats;

  const profitFactor = Math.abs(avg_r_winner) > 0 ? Math.abs(avg_r_winner / (avg_r_loser || 1)) : 0;
  const expectancy = (total_trades > 0) ? (avg_r_winner * win_pct / 100 - avg_r_loser * (100 - win_pct) / 100) : 0;

  return (
    <div className="w-full max-w-6xl mx-auto p-4">
      <div className="rounded-xl p-6 mb-6" style={{ background: "#0d0d18", border: "2px solid #1e1e2a" }}>
        <h2 className="text-2xl font-bold text-white mb-6">📈 Performance Paper Trading</h2>

        {/* Symbols Filter */}
        {symbols_traded.length > 0 && (
          <div className="mb-6">
            <p className="text-sm text-gray-500 mb-2">Filtre par Symbol:</p>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setSelectedSymbol(null)}
                className={`px-3 py-1 rounded text-sm font-bold ${
                  !selectedSymbol ? "bg-cyan-600 text-white" : "bg-gray-900 text-gray-400"
                }`}
              >
                Tous
              </button>
              {symbols_traded.map((sym) => (
                <button
                  key={sym}
                  onClick={() => setSelectedSymbol(sym)}
                  className={`px-3 py-1 rounded text-sm font-bold ${
                    selectedSymbol === sym ? "bg-cyan-600 text-white" : "bg-gray-900 text-gray-400"
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Total Trades</p>
            <p className="text-2xl font-bold text-cyan-400">{total_trades}</p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Win Rate</p>
            <p className="text-2xl font-bold text-green-400">{win_pct.toFixed(1)}%</p>
            <p className="text-xs text-gray-500 mt-1">{winning_trades}W / {total_trades - winning_trades}L</p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Net PnL</p>
            <p className={`text-2xl font-bold ${net_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
              {net_pnl_pct.toFixed(3)}%
            </p>
            <p className={`text-xs mt-1 ${net_pnl_usd >= 0 ? "text-green-500" : "text-red-500"}`}>
              ${net_pnl_usd.toFixed(2)}
            </p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Expectancy</p>
            <p className={`text-2xl font-bold ${expectancy >= 0 ? "text-green-400" : "text-red-400"}`}>
              {expectancy.toFixed(4)}
            </p>
          </div>
        </div>

        {/* Avg R/R */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Avg R (Winners)</p>
            <p className="text-xl font-bold text-green-400">{avg_r_winner.toFixed(4)}</p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Avg R (Losers)</p>
            <p className="text-xl font-bold text-red-400">{Math.abs(avg_r_loser).toFixed(4)}</p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Profit Factor</p>
            <p className="text-xl font-bold text-cyan-400">{profitFactor.toFixed(2)}</p>
          </div>
        </div>

        {/* Best / Worst R */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Best Trade</p>
            <p className="text-lg font-bold text-green-400">+{best_r.toFixed(4)} R</p>
          </div>

          <div className="rounded-lg p-4" style={{ background: "#1a1a2e" }}>
            <p className="text-xs text-gray-600 mb-1">Worst Trade</p>
            <p className="text-lg font-bold text-red-400">{worst_r.toFixed(4)} R</p>
          </div>
        </div>

        {total_trades === 0 && (
          <div className="text-center py-8 text-gray-500">
            <p>Pas assez de trades fermés pour les statistiques</p>
          </div>
        )}
      </div>
    </div>
  );
}
