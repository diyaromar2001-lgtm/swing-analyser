"""
Signal Tracker — SQLite persistence
Enregistre chaque setup détecté par le screener et suit sa performance réelle.

Règles de cohérence (alignées sur le Portfolio Backtest Engine) :
- Outcome évalué barre par barre sur les OHLC (pas snapshot instantané)
- Si SL et TP touchés le même jour → SL prioritaire (pire cas conservateur)
- Un signal reste OPEN tant qu'aucune barre ne déclenche TP1/TP2/SL
- Win rate affiché = trades CLÔTURÉS uniquement (OPEN exclus)
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker         TEXT    NOT NULL,
            date           TEXT    NOT NULL,
            price          REAL    NOT NULL,
            entry          REAL    NOT NULL,
            stop_loss      REAL    NOT NULL,
            tp1            REAL    NOT NULL,
            tp2            REAL    NOT NULL,
            setup_grade    TEXT    NOT NULL,
            score          INTEGER NOT NULL,
            confidence     INTEGER NOT NULL,
            rr_ratio       REAL    NOT NULL,
            signal_type    TEXT    NOT NULL,
            strategy       TEXT    NOT NULL DEFAULT 'standard',
            outcome        TEXT    DEFAULT NULL,
            pnl_pct        REAL    DEFAULT NULL,
            days_held      INTEGER DEFAULT NULL,
            updated_at     TEXT    DEFAULT NULL,
            outcome_source TEXT    DEFAULT 'pending',
            UNIQUE(ticker, date)
        )
    """)
    # Migration: ajouter la colonne si elle n'existe pas encore (base existante)
    try:
        conn.execute("ALTER TABLE signals ADD COLUMN outcome_source TEXT DEFAULT 'pending'")
        conn.commit()
    except Exception:
        pass  # colonne déjà présente
    conn.commit()
    conn.close()


def log_signal(
    ticker: str,
    price: float,
    entry: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    grade: str,
    score: int,
    confidence: int,
    rr: float,
    signal_type: str,
    strategy: str = "standard",
):
    """Insère un signal (ignore si déjà enregistré aujourd'hui pour ce ticker)."""
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO signals
                (ticker, date, price, entry, stop_loss, tp1, tp2,
                 setup_grade, score, confidence, rr_ratio, signal_type, strategy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (ticker, today, price, entry, stop_loss, tp1, tp2,
             grade, score, confidence, rr, signal_type, strategy),
        )
        conn.commit()
    finally:
        conn.close()


def update_outcomes(current_prices: dict[str, float]):
    """
    Compatibilité amont — préférer update_outcomes_ohlc() quand les DataFrames
    OHLC sont disponibles (plus précis, évite les faux positifs).
    Utilisé en fallback si les OHLC ne sont pas encore dans le cache.
    """
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM signals WHERE outcome IS NULL"
        ).fetchall()

        for row in rows:
            ticker = row["ticker"]
            if ticker not in current_prices:
                continue

            curr        = current_prices[ticker]
            entry_price = row["entry"]
            signal_date = row["date"]
            tp1         = row["tp1"]
            tp2         = row["tp2"]
            sl          = row["stop_loss"]

            # Ne pas clore un signal le jour même de son émission
            try:
                if datetime.strptime(signal_date, "%Y-%m-%d").date() >= datetime.now().date():
                    continue
                days = (datetime.now() - datetime.strptime(signal_date, "%Y-%m-%d")).days
            except Exception:
                days = 0

            outcome = None
            pnl     = None

            if curr >= tp2:
                outcome = "TP2"
                pnl = round((tp2 - entry_price) / entry_price * 100, 2)
            elif curr >= tp1:
                outcome = "TP1"
                pnl = round((tp1 - entry_price) / entry_price * 100, 2)
            elif curr <= sl:
                outcome = "SL"
                pnl = round((sl - entry_price) / entry_price * 100, 2)

            if outcome:
                conn.execute(
                    "UPDATE signals SET outcome=?, pnl_pct=?, days_held=?, updated_at=?, outcome_source=? WHERE id=?",
                    (outcome, pnl, days, today, "snapshot", row["id"]),
                )

        conn.commit()
    finally:
        conn.close()


def update_outcomes_ohlc(ticker_ohlc: dict):
    """
    Met à jour les signaux OUVERTS en rejouant les barres OHLC jour par jour.

    Logique identique au Portfolio Backtest Engine :
    - Replay commence le lendemain du signal (jamais le jour même)
    - Si SL et TP touchés le même jour → SL prioritaire (pire cas)
    - Un trade reste OPEN tant qu'aucune barre ne déclenche une sortie

    ticker_ohlc : {ticker: pd.DataFrame} avec colonnes High / Low au moins.
    Typiquement alimenté depuis le cache OHLCV de main.py.
    """
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn  = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM signals WHERE outcome IS NULL"
        ).fetchall()

        updates = []

        for row in rows:
            ticker      = row["ticker"]
            signal_date = row["date"]
            entry       = row["entry"]
            sl          = row["stop_loss"]
            tp1         = row["tp1"]
            tp2         = row["tp2"]

            df = ticker_ohlc.get(ticker)
            if df is None or df.empty:
                continue

            outcome   = None
            pnl       = None
            exit_date = None

            try:
                high_s = df["High"].squeeze()
                low_s  = df["Low"].squeeze()
            except Exception:
                continue

            for dt_idx in df.index:
                date_str = str(dt_idx)[:10]
                # Rejouer uniquement à partir du lendemain du signal
                if date_str <= signal_date:
                    continue

                try:
                    h = float(high_s.loc[dt_idx])
                    l = float(low_s.loc[dt_idx])
                except Exception:
                    continue

                hit_sl  = l <= sl
                hit_tp2 = h >= tp2
                hit_tp1 = h >= tp1

                if hit_sl and (hit_tp2 or hit_tp1):
                    # TP et SL tous deux touchés la même barre → SL (pire cas)
                    outcome   = "SL"
                    pnl       = round((sl - entry) / entry * 100, 2)
                    exit_date = date_str
                    break
                elif hit_tp2:
                    outcome   = "TP2"
                    pnl       = round((tp2 - entry) / entry * 100, 2)
                    exit_date = date_str
                    break
                elif hit_tp1:
                    outcome   = "TP1"
                    pnl       = round((tp1 - entry) / entry * 100, 2)
                    exit_date = date_str
                    break
                elif hit_sl:
                    outcome   = "SL"
                    pnl       = round((sl - entry) / entry * 100, 2)
                    exit_date = date_str
                    break

            if outcome and exit_date:
                try:
                    days = (
                        datetime.strptime(exit_date, "%Y-%m-%d") -
                        datetime.strptime(signal_date, "%Y-%m-%d")
                    ).days
                except Exception:
                    days = 0
                updates.append((outcome, pnl, days, today, "ohlc", row["id"]))

        for upd in updates:
            conn.execute(
                "UPDATE signals SET outcome=?, pnl_pct=?, days_held=?, updated_at=?, outcome_source=? WHERE id=?",
                upd,
            )
        conn.commit()
    finally:
        conn.close()


def get_signals(limit: int = 200) -> list[dict]:
    """Retourne les derniers signaux enregistrés."""
    init_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_signal_stats() -> dict:
    """
    Statistiques globales de tracking.

    Win rate et avg_pnl calculés sur trades CLÔTURÉS uniquement (OPEN exclus).
    Aligné avec le Portfolio Backtest Engine.
    """
    init_db()
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        # "Clôturé" = outcome IN (TP1, TP2, SL) — jamais OPEN ni NULL
        closed = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IN ('TP1','TP2','SL')"
        ).fetchone()[0]
        open_count = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IS NULL"
        ).fetchone()[0]
        wins = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IN ('TP1','TP2')"
        ).fetchone()[0]
        losses = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome = 'SL'"
        ).fetchone()[0]
        # avg_pnl uniquement sur trades clôturés (pas les OPEN)
        avg_pnl_row = conn.execute(
            "SELECT AVG(pnl_pct) FROM signals WHERE outcome IN ('TP1','TP2','SL') AND pnl_pct IS NOT NULL"
        ).fetchone()[0]

        win_rate = round(wins / closed * 100, 1) if closed > 0 else 0.0
        avg_pnl  = round(avg_pnl_row or 0.0, 2)

        # Win rate OHLC uniquement (source la plus fiable)
        ohlc_closed = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IN ('TP1','TP2','SL') AND outcome_source='ohlc'"
        ).fetchone()[0]
        ohlc_wins = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IN ('TP1','TP2') AND outcome_source='ohlc'"
        ).fetchone()[0]
        ohlc_win_rate = round(ohlc_wins / ohlc_closed * 100, 1) if ohlc_closed > 0 else None

        by_grade = {}
        for grade in ("A+", "A", "B"):
            g_total = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE setup_grade=?", (grade,)
            ).fetchone()[0]
            g_wins = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE setup_grade=? AND outcome IN ('TP1','TP2')",
                (grade,)
            ).fetchone()[0]
            g_closed = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE setup_grade=? AND outcome IN ('TP1','TP2','SL')",
                (grade,)
            ).fetchone()[0]
            g_avg_pnl = conn.execute(
                "SELECT AVG(pnl_pct) FROM signals "
                "WHERE setup_grade=? AND outcome IN ('TP1','TP2','SL') AND pnl_pct IS NOT NULL",
                (grade,)
            ).fetchone()[0]
            by_grade[grade] = {
                "total":    g_total,
                "closed":   g_closed,
                "wins":     g_wins,
                "win_rate": round(g_wins / g_closed * 100, 1) if g_closed > 0 else 0.0,
                "avg_pnl":  round(g_avg_pnl or 0.0, 2),
            }

        return {
            "total":          total,
            "closed":         closed,
            "open":           open_count,
            "wins":           wins,
            "losses":         losses,
            "win_rate":       win_rate,       # clôturés uniquement
            "avg_pnl":        avg_pnl,        # clôturés uniquement
            "ohlc_win_rate":  ohlc_win_rate,  # OHLC confirmés uniquement (None si aucun)
            "ohlc_closed":    ohlc_closed,
            "by_grade":       by_grade,
        }
    finally:
        conn.close()
