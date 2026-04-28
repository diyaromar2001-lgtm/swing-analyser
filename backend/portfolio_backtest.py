"""
Portfolio Backtest Engine — simulation réaliste avec capital management.

Capital : 10 000 $ — Risque : 1 % / trade — Max : 8 positions simultanées
Position sizing : shares = (capital × 0.01) / sl_distance
Commission     : 0.05 % aller + 0.05 % retour
"""

import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple

# ── Constantes ─────────────────────────────────────────────────────────────────

INITIAL_CAPITAL   = 10_000.0
RISK_PCT          = 0.01        # 1 % du capital risqué par trade
MAX_POSITIONS     = 8           # positions simultanées maximum
MAX_POSITION_PCT  = 0.25        # max 25 % du capital par position
COMMISSION        = 0.0005      # 0.05 % par côté (aller & retour)

# ── Critères de tradabilité ────────────────────────────────────────────────────

TRADABLE_MIN_TRADES = 50        # robustesse statistique (v2)
TRADABLE_MIN_PF     = 1.30
TRADABLE_MAX_DD     = -25.0    # max drawdown acceptable (%)
TRADABLE_MIN_SHARPE = 0.50

CONFIRM_MIN_TRADES  = 25
CONFIRM_MIN_PF      = 1.00
CONFIRM_MAX_DD      = -35.0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _empty_result(initial_capital: float = INITIAL_CAPITAL) -> Dict:
    return {
        "total_trades":             0,
        "wins":                     0,
        "losses":                   0,
        "win_rate":                 0.0,
        "expectancy":               0.0,     # % moyen / trade (pnl_pct pondéré)
        "expectancy_dollars":       0.0,     # $ moyen / trade
        "profit_factor":            0.0,
        "max_drawdown_pct":         0.0,
        "sharpe_ratio":             0.0,
        "cagr_pct":                 0.0,
        "final_capital":            initial_capital,
        "total_return_pct":         0.0,
        "time_in_market_pct":       0.0,
        "max_concurrent_positions": 0,
        "avg_duration_days":        0.0,
        "reliable_tickers":         0,
        "best_ticker":              "—",
        "worst_ticker":             "—",
        "tradable_status":          "NON TRADABLE",
        "tradable_color":           "#f87171",
        "tradable_emoji":           "🔴",
        "equity_curve":             [0.0],
        "trades":                   [],
    }


def _classify_tradability(n_trades: int, pf: float, max_dd: float, sharpe: float) -> Tuple[str, str, str]:
    """Retourne (label, couleur hex, emoji) selon les critères de tradabilité."""
    if (n_trades >= TRADABLE_MIN_TRADES
            and pf > TRADABLE_MIN_PF
            and max_dd > TRADABLE_MAX_DD
            and sharpe > TRADABLE_MIN_SHARPE):
        return "TRADABLE", "#4ade80", "🟢"

    if (n_trades >= CONFIRM_MIN_TRADES
            and pf > CONFIRM_MIN_PF
            and max_dd > CONFIRM_MAX_DD):
        return "À CONFIRMER", "#f59e0b", "🟡"

    return "NON TRADABLE", "#f87171", "🔴"


# ── Simulation principale ──────────────────────────────────────────────────────

def run_portfolio_backtest(
    all_ticker_trades: List[Dict],
    period_months: int = 12,
    initial_capital: float = INITIAL_CAPITAL,
) -> Dict:
    """
    Simule un portefeuille réaliste à partir des trades bruts du backtest.

    Paramètres
    ----------
    all_ticker_trades : trades issus de backtest_ticker_lab() pour tous les tickers.
        Chaque dict doit contenir :
          ticker, entry_date, exit_date, entry_price, exit_price,
          exit_reason, pnl_pct, duration_days, sl_pct

    period_months : durée de la fenêtre de backtest (pour CAGR / time-in-market).
    initial_capital : capital de départ en USD.

    Retourne un dict complet de métriques portfolio.
    """
    if not all_ticker_trades:
        return _empty_result(initial_capital)

    # Tri chronologique par date d'entrée (puis ticker pour stabilité)
    raw_sorted = sorted(all_ticker_trades, key=lambda t: (t["entry_date"], t["ticker"]))

    capital          = initial_capital
    open_pos: List[Dict] = []
    closed:   List[Dict] = []

    # Courbe d'équité : liste de (date_str, capital_float) après chaque clôture
    equity_pts: List[Tuple[str, float]] = []

    total_days_invested = 0
    max_concurrent      = 0
    held_tickers        = set()     # évite 2 positions simultanées sur le même ticker

    # Métriques par ticker
    ticker_pnl_dollars: Dict[str, float] = {}
    ticker_count:       Dict[str, int]   = {}

    # ── Sous-routine : fermer les positions dont exit_date ≤ cutoff ─────────
    def _flush_before(cutoff: str) -> None:
        nonlocal capital
        still_open = []
        for pos in open_pos:
            if pos["exit_date"] <= cutoff:
                capital += pos["capital_allocated"] + pos["pnl_dollars"]
                closed.append(pos)
                equity_pts.append((pos["exit_date"], capital))
                held_tickers.discard(pos["ticker"])
            else:
                still_open.append(pos)
        open_pos.clear()
        open_pos.extend(still_open)

    # ── Boucle principale ────────────────────────────────────────────────────
    for raw in raw_sorted:
        entry_date  = raw["entry_date"]
        ticker      = raw["ticker"]
        entry_price = raw["entry_price"]
        sl_pct      = raw.get("sl_pct", 0.03)

        # 1. Fermer les positions échues avant cette date d'entrée
        _flush_before(entry_date)

        # 2. Mise à jour du max concurrent après clôtures
        n_open = len(open_pos)
        if n_open > max_concurrent:
            max_concurrent = n_open

        # 3. Vérifier la capacité
        if n_open >= MAX_POSITIONS:
            continue

        # 4. Un seul trade actif par ticker à la fois
        if ticker in held_tickers:
            continue

        # 5. Données valides
        if entry_price <= 0 or sl_pct <= 0:
            continue

        # 6. Position sizing : risque 1 % du capital courant
        sl_distance    = entry_price * sl_pct
        shares         = (capital * RISK_PCT) / sl_distance
        cap_allocated  = shares * entry_price

        # Plafonner à MAX_POSITION_PCT du capital
        max_cap = capital * MAX_POSITION_PCT
        if cap_allocated > max_cap:
            shares        = max_cap / entry_price
            cap_allocated = max_cap

        # 7. Commission à l'entrée
        comm_in    = cap_allocated * COMMISSION
        total_cost = cap_allocated + comm_in

        if total_cost > capital:
            continue     # capital insuffisant

        # 8. Calculer le P&L en dollars
        pnl_pct_dec = raw["pnl_pct"] / 100.0
        comm_out    = cap_allocated * (1.0 + pnl_pct_dec) * COMMISSION
        pnl_dollars = cap_allocated * pnl_pct_dec - comm_in - comm_out

        # 9. Déduire le coût du capital
        capital -= total_cost

        position = {
            "ticker":            ticker,
            "entry_date":        entry_date,
            "exit_date":         raw["exit_date"],
            "entry_price":       round(entry_price, 2),
            "exit_price":        round(raw["exit_price"], 2),
            "exit_reason":       raw["exit_reason"],
            "shares":            round(shares, 4),
            "pnl_pct":           raw["pnl_pct"],
            "pnl_dollars":       round(pnl_dollars, 2),
            "duration_days":     raw["duration_days"],
            "capital_allocated": round(cap_allocated, 2),
        }

        open_pos.append(position)
        held_tickers.add(ticker)
        total_days_invested += raw["duration_days"]

        # Tracking par ticker
        ticker_pnl_dollars[ticker] = ticker_pnl_dollars.get(ticker, 0.0) + pnl_dollars
        ticker_count[ticker]       = ticker_count.get(ticker, 0) + 1

    # ── Fermer les positions encore ouvertes ─────────────────────────────────
    for pos in open_pos:
        capital += pos["capital_allocated"] + pos["pnl_dollars"]
        closed.append(pos)
        equity_pts.append((pos["exit_date"], capital))

    if not closed:
        return _empty_result(initial_capital)

    # ── Calcul des métriques ─────────────────────────────────────────────────

    n_trades  = len(closed)

    # Gains / pertes en % par trade (pour expectancy & score)
    pnl_pct_list   = [t["pnl_pct"] for t in closed]
    wins_pct        = [p for p in pnl_pct_list if p > 0]
    losses_pct      = [p for p in pnl_pct_list if p <= 0]

    win_rate    = len(wins_pct) / n_trades * 100 if n_trades else 0.0
    avg_win_pct = float(np.mean(wins_pct))  if wins_pct   else 0.0
    avg_los_pct = float(np.mean(losses_pct)) if losses_pct else 0.0
    expectancy  = (win_rate / 100 * avg_win_pct) + ((1 - win_rate / 100) * avg_los_pct)

    # En dollars
    pnl_dollar_list    = [t["pnl_dollars"] for t in closed]
    expectancy_dollars = float(np.mean(pnl_dollar_list)) if pnl_dollar_list else 0.0

    gross_profit  = sum(p for p in pnl_dollar_list if p > 0)
    gross_loss    = abs(sum(p for p in pnl_dollar_list if p <= 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

    # Capital final & retour total
    final_capital    = capital
    total_return_pct = (final_capital / initial_capital - 1.0) * 100.0

    # ── Courbe d'équité normalisée (% depuis le départ) ─────────────────────
    equity_sorted = sorted(equity_pts, key=lambda x: x[0])
    equity_curve  = [0.0] + [
        round((c / initial_capital - 1.0) * 100.0, 2)
        for _, c in equity_sorted
    ]

    # ── Max Drawdown (sur l'equity en $) ─────────────────────────────────────
    eq_arr      = np.array([initial_capital] + [c for _, c in equity_sorted])
    running_max = np.maximum.accumulate(eq_arr)
    drawdowns   = (eq_arr - running_max) / running_max * 100.0
    max_dd      = float(np.min(drawdowns)) if len(drawdowns) > 1 else 0.0

    # ── CAGR ─────────────────────────────────────────────────────────────────
    cagr_pct = 0.0
    if equity_sorted and final_capital > 0:
        try:
            d1     = datetime.strptime(equity_sorted[0][0][:10],  "%Y-%m-%d")
            d2     = datetime.strptime(equity_sorted[-1][0][:10], "%Y-%m-%d")
            n_days = max((d2 - d1).days, 1)
            cagr_pct = ((final_capital / initial_capital) ** (365.0 / n_days) - 1.0) * 100.0
        except Exception:
            cagr_pct = total_return_pct / max(period_months / 12.0, 1.0)

    # ── Sharpe Ratio annualisé ────────────────────────────────────────────────
    sharpe = 0.0
    if len(pnl_dollar_list) >= 2:
        avg_dur = max(float(np.mean([t["duration_days"] for t in closed])), 1.0)
        ret_arr = np.array([p / initial_capital for p in pnl_dollar_list])
        mu      = float(np.mean(ret_arr))
        sigma   = float(np.std(ret_arr, ddof=1))
        if sigma > 0:
            trades_per_year = 252.0 / avg_dur
            sharpe = mu / sigma * np.sqrt(trades_per_year)

    # ── Time in Market ────────────────────────────────────────────────────────
    period_days         = int(252 * period_months / 12)
    total_possible_days = period_days * MAX_POSITIONS
    time_in_market_pct  = min(100.0, total_days_invested / max(total_possible_days, 1) * 100.0)

    # ── Tickers fiables (≥ 3 trades) ─────────────────────────────────────────
    reliable_tickers = sum(1 for v in ticker_count.values() if v >= 3)
    best_ticker  = max(ticker_pnl_dollars, key=ticker_pnl_dollars.get) if ticker_pnl_dollars else "—"
    worst_ticker = min(ticker_pnl_dollars, key=ticker_pnl_dollars.get) if ticker_pnl_dollars else "—"

    # ── Tradabilité ───────────────────────────────────────────────────────────
    status, color, emoji = _classify_tradability(n_trades, profit_factor, max_dd, sharpe)

    avg_duration = float(np.mean([t["duration_days"] for t in closed]))

    return {
        "total_trades":             n_trades,
        "wins":                     len(wins_pct),
        "losses":                   len(losses_pct),
        "win_rate":                 round(win_rate, 1),
        "expectancy":               round(expectancy, 2),         # % moyen / trade
        "expectancy_dollars":       round(expectancy_dollars, 2), # $ moyen / trade
        "profit_factor":            profit_factor,
        "max_drawdown_pct":         round(max_dd, 2),
        "sharpe_ratio":             round(sharpe, 2),
        "cagr_pct":                 round(cagr_pct, 1),
        "final_capital":            round(final_capital, 2),
        "total_return_pct":         round(total_return_pct, 1),
        "time_in_market_pct":       round(time_in_market_pct, 1),
        "max_concurrent_positions": max_concurrent,
        "avg_duration_days":        round(avg_duration, 1),
        "reliable_tickers":         reliable_tickers,
        "best_ticker":              best_ticker,
        "worst_ticker":             worst_ticker,
        "tradable_status":          status,
        "tradable_color":           color,
        "tradable_emoji":           emoji,
        "equity_curve":             equity_curve,
        "trades":                   closed,
    }
