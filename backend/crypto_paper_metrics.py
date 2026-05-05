"""
Performance Metrics for Crypto Scalp Paper Trading

Aggregates statistics from closed paper trades:
- Win percentage, average R/R for winners and losers
- Net PnL calculation and tracking
- Segmentation by symbol, timeframe, date range
"""

from typing import Dict, List, Optional, Any
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "trade_journal.db")


def _connect() -> sqlite3.Connection:
    """Open database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def compute_paper_portfolio_stats(symbol_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute performance stats for all closed SCALP_PAPER trades.

    Args:
        symbol_filter: Optional symbol to filter by (e.g., "BTC", "MKR")

    Returns:
        {
            "total_trades": int,
            "winning_trades": int,
            "losing_trades": int,
            "win_pct": float,
            "avg_r_winner": float,
            "avg_r_loser": float,
            "best_r": float,
            "worst_r": float,
            "net_pnl_usd": float,
            "net_pnl_pct": float,
            "symbols_traded": list,
            "data_points": int (for validation),
        }
    """
    conn = _connect()
    try:
        query = """
            SELECT
                id,
                symbol,
                direction,
                entry_price,
                exit_price,
                pnl_pct,
                r_multiple
            FROM trades
            WHERE status = 'SCALP_PAPER_CLOSED'
            AND entry_price IS NOT NULL
            AND exit_price IS NOT NULL
        """
        params = []

        if symbol_filter:
            query += " AND symbol = ?"
            params.append(symbol_filter.upper())

        query += " ORDER BY closed_at DESC"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_pct": 0.0,
                "avg_r_winner": 0.0,
                "avg_r_loser": 0.0,
                "best_r": 0.0,
                "worst_r": 0.0,
                "net_pnl_usd": 0.0,
                "net_pnl_pct": 0.0,
                "symbols_traded": [],
                "data_points": 0,
            }

        total = len(rows)
        winners = [r for r in rows if (r["pnl_pct"] or 0) > 0]
        losers = [r for r in rows if (r["pnl_pct"] or 0) <= 0]

        win_count = len(winners)
        loss_count = len(losers)
        win_pct = (win_count / total * 100) if total > 0 else 0.0

        # Average R/R for winners and losers
        winner_r_values = [r["r_multiple"] or 0 for r in winners if r["r_multiple"]]
        loser_r_values = [r["r_multiple"] or 0 for r in losers if r["r_multiple"]]

        avg_r_winner = (sum(winner_r_values) / len(winner_r_values)) if winner_r_values else 0.0
        avg_r_loser = (sum(loser_r_values) / len(loser_r_values)) if loser_r_values else 0.0

        # Best and worst R/R
        all_r_values = winner_r_values + loser_r_values
        best_r = max(all_r_values) if all_r_values else 0.0
        worst_r = min(all_r_values) if all_r_values else 0.0

        # Net PnL (in USD, approximate from percentages)
        net_pnl_pct = sum([r["pnl_pct"] or 0 for r in rows]) / total if total > 0 else 0.0
        net_pnl_usd = sum([r["entry_price"] * (r["pnl_pct"] or 0) / 100.0 for r in rows])

        # Unique symbols
        symbols_traded = list(set([r["symbol"] for r in rows]))
        symbols_traded.sort()

        return {
            "total_trades": total,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_pct": round(win_pct, 2),
            "avg_r_winner": round(avg_r_winner, 4),
            "avg_r_loser": round(avg_r_loser, 4),
            "best_r": round(best_r, 4),
            "worst_r": round(worst_r, 4),
            "net_pnl_usd": round(net_pnl_usd, 2),
            "net_pnl_pct": round(net_pnl_pct, 4),
            "symbols_traded": symbols_traded,
            "data_points": len(all_r_values),
        }

    finally:
        conn.close()


def get_symbol_performance(symbol: str) -> Dict[str, Any]:
    """
    Get performance stats for a specific symbol's closed paper trades.

    Args:
        symbol: Crypto symbol (BTC, ETH, MKR, etc.)

    Returns:
        Same format as compute_paper_portfolio_stats, filtered by symbol
    """
    return compute_paper_portfolio_stats(symbol_filter=symbol)


def get_timeframe_performance(timeframe: str = "5m") -> Dict[str, Any]:
    """
    Get performance stats for a specific timeframe's closed paper trades.

    Args:
        timeframe: "5m" or "15m"

    Returns:
        Performance stats for trades in that timeframe
    """
    conn = _connect()
    try:
        query = """
            SELECT
                id,
                symbol,
                direction,
                entry_price,
                exit_price,
                pnl_pct,
                r_multiple,
                source_snapshot_json
            FROM trades
            WHERE status = 'SCALP_PAPER_CLOSED'
            AND entry_price IS NOT NULL
            AND exit_price IS NOT NULL
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        # Filter by timeframe from source_snapshot_json
        filtered_rows = []
        for row in rows:
            try:
                import json
                snapshot = json.loads(row["source_snapshot_json"]) if row["source_snapshot_json"] else {}
                if snapshot.get("timeframe") == timeframe:
                    filtered_rows.append(row)
            except:
                pass

        if not filtered_rows:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_pct": 0.0,
                "avg_r_winner": 0.0,
                "avg_r_loser": 0.0,
                "best_r": 0.0,
                "worst_r": 0.0,
                "net_pnl_usd": 0.0,
                "net_pnl_pct": 0.0,
                "symbols_traded": [],
                "timeframe": timeframe,
                "data_points": 0,
            }

        total = len(filtered_rows)
        winners = [r for r in filtered_rows if (r["pnl_pct"] or 0) > 0]
        losers = [r for r in filtered_rows if (r["pnl_pct"] or 0) <= 0]

        win_count = len(winners)
        loss_count = len(losers)
        win_pct = (win_count / total * 100) if total > 0 else 0.0

        winner_r_values = [r["r_multiple"] or 0 for r in winners if r["r_multiple"]]
        loser_r_values = [r["r_multiple"] or 0 for r in losers if r["r_multiple"]]

        avg_r_winner = (sum(winner_r_values) / len(winner_r_values)) if winner_r_values else 0.0
        avg_r_loser = (sum(loser_r_values) / len(loser_r_values)) if loser_r_values else 0.0

        all_r_values = winner_r_values + loser_r_values
        best_r = max(all_r_values) if all_r_values else 0.0
        worst_r = min(all_r_values) if all_r_values else 0.0

        net_pnl_pct = sum([r["pnl_pct"] or 0 for r in filtered_rows]) / total if total > 0 else 0.0
        net_pnl_usd = sum([r["entry_price"] * (r["pnl_pct"] or 0) / 100.0 for r in filtered_rows])

        symbols_traded = list(set([r["symbol"] for r in filtered_rows]))
        symbols_traded.sort()

        return {
            "total_trades": total,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_pct": round(win_pct, 2),
            "avg_r_winner": round(avg_r_winner, 4),
            "avg_r_loser": round(avg_r_loser, 4),
            "best_r": round(best_r, 4),
            "worst_r": round(worst_r, 4),
            "net_pnl_usd": round(net_pnl_usd, 2),
            "net_pnl_pct": round(net_pnl_pct, 4),
            "symbols_traded": symbols_traded,
            "timeframe": timeframe,
            "data_points": len(all_r_values),
        }

    finally:
        conn.close()
