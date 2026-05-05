from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


DB_PATH = os.path.join(os.path.dirname(__file__), "trade_journal.db")
_LOCK = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_not_exists(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Helper to add column if it doesn't exist (SQLite safe)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        # Column already exists, silently continue
        pass


def init_db() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    sector TEXT,
                    setup_grade TEXT,
                    signal_type TEXT,
                    strategy_name TEXT,
                    edge_status TEXT,
                    final_decision TEXT,
                    execution_authorized INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    direction TEXT NOT NULL DEFAULT 'LONG',
                    entry_plan TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    tp1 REAL,
                    tp2 REAL,
                    trailing_stop REAL,
                    position_size TEXT,
                    risk_amount REAL,
                    risk_pct REAL,
                    quantity REAL,
                    opened_at TEXT,
                    closed_at TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    pnl_amount REAL,
                    pnl_pct REAL,
                    r_multiple REAL,
                    notes TEXT,
                    source_snapshot_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT,
                    payload_json TEXT,
                    FOREIGN KEY(trade_id) REFERENCES trades(id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_universe ON trades(universe)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_events_trade_id ON trade_events(trade_id)")

            # Phase 2 cost fields (Paper Trading Enhancement)
            _add_column_if_not_exists(conn, "trades", "entry_fee_pct", "REAL")
            _add_column_if_not_exists(conn, "trades", "exit_fee_pct", "REAL")
            _add_column_if_not_exists(conn, "trades", "slippage_pct", "REAL")
            _add_column_if_not_exists(conn, "trades", "spread_bps", "INTEGER")
            _add_column_if_not_exists(conn, "trades", "estimated_roundtrip_cost_pct", "REAL")
            _add_column_if_not_exists(conn, "trades", "simulated_entry_price", "REAL")
            _add_column_if_not_exists(conn, "trades", "simulated_exit_price", "REAL")
            _add_column_if_not_exists(conn, "trades", "filled_quantity", "REAL")
            _add_column_if_not_exists(conn, "trades", "closure_reason", "TEXT")
            _add_column_if_not_exists(conn, "trades", "actual_pnl_pct_net", "REAL")

            conn.commit()
        finally:
            conn.close()


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None


def _json_loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        num = float(value)
        return num if num == num else None
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _row_to_trade(row: sqlite3.Row) -> Dict[str, Any]:
    trade = dict(row)
    trade["execution_authorized"] = bool(trade.get("execution_authorized"))
    trade["source_snapshot_json"] = _json_loads(trade.get("source_snapshot_json"))
    trade.setdefault("direction", "LONG")
    trade["status"] = trade.get("status") or "WATCHLIST"
    trade["universe"] = trade.get("universe") or "ACTIONS"
    trade["symbol"] = trade.get("symbol") or trade.get("ticker")
    trade["ticker"] = trade.get("symbol")
    trade["strategy"] = trade.get("strategy_name")
    trade["planned_entry"] = _to_float(trade.get("entry_plan") or trade.get("entry_price"))
    trade["price_entry"] = _to_float(trade.get("entry_price") or trade.get("planned_entry"))
    trade["date_entry"] = trade.get("opened_at") or trade.get("created_at")
    trade["reason_exit"] = trade.get("exit_reason")
    trade["note_entry"] = trade.get("notes") or ""
    trade["note_exit"] = trade.get("notes_exit")
    trade["pnl_usd"] = _to_float(trade.get("pnl_amount"))
    trade["pnl_pct"] = _to_float(trade.get("pnl_pct"))
    trade["r_multiple"] = _to_float(trade.get("r_multiple"))
    trade["duration_days"] = None
    if trade.get("opened_at") and trade.get("closed_at"):
        try:
            opened = datetime.fromisoformat(str(trade["opened_at"]))
            closed = datetime.fromisoformat(str(trade["closed_at"]))
            trade["duration_days"] = max(0, round((closed - opened).total_seconds() / 86400))
        except Exception:
            trade["duration_days"] = None
    return trade


def _fetch_all(where: str = "", params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            query = "SELECT * FROM trades"
            if where:
                query += f" WHERE {where}"
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [_row_to_trade(row) for row in rows]
        finally:
            conn.close()


def list_trades(universe: Optional[str] = None, status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    filters: List[str] = []
    params: List[Any] = []
    if universe:
        filters.append("universe = ?")
        params.append(universe.upper())
    if status:
        filters.append("status = ?")
        params.append(status.upper())
    if symbol:
        filters.append("symbol = ?")
        params.append(symbol.upper())
    where = " AND ".join(filters)
    return _fetch_all(where, params)


def get_trade(trade_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
            return _row_to_trade(row) if row else None
        finally:
            conn.close()


def _effective_execution_authorized(status: str, execution_authorized: bool) -> bool:
    if status.upper() == "WATCHLIST":
        return False
    return execution_authorized


def _compute_quantity(entry_price: Optional[float], stop_loss: Optional[float], risk_amount: Optional[float]) -> Optional[float]:
    if entry_price is None or stop_loss is None:
        return None
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit <= 0:
        return None
    if risk_amount is None:
        risk_amount = 100.0
    return risk_amount / risk_per_unit


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().upper()


def _snapshot_lookup(trade: Dict[str, Any], *keys: str) -> Any:
    snapshot = trade.get("source_snapshot_json")
    if isinstance(snapshot, dict):
      for key in keys:
        if key in snapshot and snapshot.get(key) not in (None, ""):
          return snapshot.get(key)
    for key in keys:
        if trade.get(key) not in (None, ""):
            return trade.get(key)
    return None


def _truthy_snapshot(trade: Dict[str, Any], *keys: str) -> bool:
    value = _snapshot_lookup(trade, *keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _normalize_text(value) in {"TRUE", "1", "YES", "Y"}


def _trade_open_block_reason(trade: Dict[str, Any]) -> Optional[str]:
    status = _normalize_text(trade.get("status"))
    if status != "PLANNED":
        return "status must be PLANNED"
    if not bool(trade.get("execution_authorized")):
        return "execution not authorized"
    edge_status = _normalize_text(trade.get("edge_status"))
    if edge_status not in {"STRONG_EDGE", "VALID_EDGE"}:
        return "edge not validated"
    final_decision = _normalize_text(trade.get("final_decision"))
    if final_decision not in {"BUY", "BUY NOW", "BUY NEAR ENTRY"}:
        return "final decision not tradable"
    if _normalize_text(_snapshot_lookup(trade, "setup_status")) == "INVALID":
        return "setup invalid"
    if _truthy_snapshot(trade, "overfit_warning"):
        return "overfit warning present"
    return None


def _trade_payload_from_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    trade_id = str(payload.get("id") or payload.get("trade_id") or payload.get("symbol") or payload.get("ticker") or f"trade_{int(datetime.now().timestamp() * 1000)}")
    symbol = str(payload.get("symbol") or payload.get("ticker") or "").upper()
    universe = str(payload.get("universe") or payload.get("asset_scope") or "ACTIONS").upper()
    status = str(payload.get("status") or "WATCHLIST").upper()
    execution_authorized = bool(payload.get("execution_authorized", payload.get("execution_authorized", False)))
    if status == "OPEN" and not execution_authorized:
        status = "WATCHLIST"

    entry_plan = _to_float(payload.get("entry_plan"))
    entry_price = _to_float(payload.get("entry_price"))
    stop_loss = _to_float(payload.get("stop_loss"))
    tp1 = _to_float(payload.get("tp1"))
    tp2 = _to_float(payload.get("tp2"))
    trailing_stop = _to_float(payload.get("trailing_stop"))
    risk_amount = _to_float(payload.get("risk_amount"))
    risk_pct = _to_float(payload.get("risk_pct"))
    quantity = _to_float(payload.get("quantity"))
    if quantity is None:
        quantity = _compute_quantity(entry_price or entry_plan, stop_loss, risk_amount)
    notes = payload.get("notes") or payload.get("note_entry")
    strategy_name = payload.get("strategy_name") or payload.get("strategy")
    edge_status = payload.get("edge_status") or payload.get("ticker_edge_status")
    final_decision = payload.get("final_decision")
    opened_at = payload.get("opened_at") or (utc_now_iso() if status == "OPEN" else None)
    created_at = payload.get("created_at") or utc_now_iso()
    updated_at = payload.get("updated_at") or created_at
    source_snapshot_json = _json_dumps(payload.get("source_snapshot_json") or payload.get("source_snapshot") or payload)

    return {
        "id": trade_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "universe": universe,
        "symbol": symbol,
        "sector": payload.get("sector"),
        "setup_grade": payload.get("setup_grade"),
        "signal_type": payload.get("signal_type"),
        "strategy_name": strategy_name,
        "edge_status": edge_status,
        "final_decision": final_decision,
        "execution_authorized": 1 if _effective_execution_authorized(status, execution_authorized) else 0,
        "status": status,
        "direction": payload.get("direction") or "LONG",
        "entry_plan": payload.get("entry_plan") or payload.get("planned_entry") or entry_plan,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "trailing_stop": trailing_stop,
        "position_size": payload.get("position_size"),
        "risk_amount": risk_amount,
        "risk_pct": risk_pct,
        "quantity": quantity,
        "opened_at": opened_at,
        "closed_at": payload.get("closed_at"),
        "exit_price": _to_float(payload.get("exit_price")),
        "exit_reason": payload.get("exit_reason"),
        "pnl_amount": _to_float(payload.get("pnl_amount")),
        "pnl_pct": _to_float(payload.get("pnl_pct")),
        "r_multiple": _to_float(payload.get("r_multiple")),
        "notes": notes,
        "source_snapshot_json": source_snapshot_json,
    }


def create_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
    trade = _trade_payload_from_input(payload)
    with _LOCK:
        conn = _connect()
        try:
            existing = conn.execute("SELECT id FROM trades WHERE id = ?", (trade["id"],)).fetchone()
            if existing:
                raise ValueError("duplicate_trade_id")
            columns = ", ".join(trade.keys())
            placeholders = ", ".join(["?"] * len(trade))
            conn.execute(f"INSERT INTO trades ({columns}) VALUES ({placeholders})", tuple(trade.values()))
            conn.execute(
                """
                INSERT INTO trade_events (trade_id, created_at, event_type, message, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trade["id"], utc_now_iso(), "CREATE", f"Trade created: {trade['symbol']}", _json_dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()
    return get_trade(trade["id"]) or trade


def _update_fields(trade: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if key in {"id", "created_at"}:
            continue
        if key == "symbol" or key == "ticker":
            trade["symbol"] = str(value).upper()
        elif key == "universe":
            trade["universe"] = str(value).upper()
        elif key in {"entry_plan", "planned_entry"}:
            trade["entry_plan"] = _to_float(value)
        elif key in {"entry_price", "price_entry"}:
            trade["entry_price"] = _to_float(value)
        elif key in {"stop_loss", "tp1", "tp2", "trailing_stop", "risk_amount", "risk_pct", "quantity", "exit_price", "pnl_amount", "pnl_pct", "r_multiple"}:
            trade[key] = _to_float(value)
        elif key in {"execution_authorized"}:
            trade[key] = 1 if bool(value) else 0
        elif key in {"status", "direction", "setup_grade", "signal_type", "strategy_name", "edge_status", "final_decision", "position_size", "exit_reason", "notes", "opened_at", "closed_at", "sector"}:
            trade[key] = value
        elif key in {"source_snapshot", "source_snapshot_json"}:
            trade["source_snapshot_json"] = _json_dumps(value)
        else:
            trade[key] = value
    if "quantity" not in updates and trade.get("quantity") in (None, 0):
        trade["quantity"] = _compute_quantity(
            _to_float(trade.get("entry_price")) or _to_float(trade.get("entry_plan")),
            _to_float(trade.get("stop_loss")),
            _to_float(trade.get("risk_amount")),
        )
    if trade.get("status", "").upper() == "OPEN":
        trade["opened_at"] = trade.get("opened_at") or utc_now_iso()
    trade["updated_at"] = utc_now_iso()
    return trade


def update_trade(trade_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    current = get_trade(trade_id)
    if not current:
        raise KeyError("trade_not_found")
    merged = _update_fields(current, updates)
    with _LOCK:
        conn = _connect()
        try:
            allowed_cols = {
                "id", "created_at", "updated_at", "universe", "symbol", "sector", "setup_grade",
                "signal_type", "strategy_name", "edge_status", "final_decision", "execution_authorized",
                "status", "direction", "entry_plan", "entry_price", "stop_loss", "tp1", "tp2",
                "trailing_stop", "position_size", "risk_amount", "risk_pct", "quantity", "opened_at",
                "closed_at", "exit_price", "exit_reason", "pnl_amount", "pnl_pct", "r_multiple",
                "notes", "source_snapshot_json",
            }
            cols = [k for k in merged.keys() if k in allowed_cols and k != "id"]
            conn.execute(
                f"UPDATE trades SET {', '.join([f'{col} = ?' for col in cols])} WHERE id = ?",
                tuple(merged.get(col) for col in cols) + (trade_id,),
            )
            conn.execute(
                """
                INSERT INTO trade_events (trade_id, created_at, event_type, message, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trade_id, utc_now_iso(), "UPDATE", "Trade updated", _json_dumps(updates)),
            )
            conn.commit()
        finally:
            conn.close()
    return get_trade(trade_id) or merged


def open_trade(trade_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    current = get_trade(trade_id)
    if not current:
        raise KeyError("trade_not_found")
    block_reason = _trade_open_block_reason(current)
    if block_reason:
        raise ValueError(f"Trade opening blocked: execution not authorized ({block_reason})")
    updates = dict(payload)
    updates["status"] = "OPEN"
    updates["opened_at"] = updates.get("opened_at") or utc_now_iso()
    if updates.get("entry_price") is None:
        updates["entry_price"] = current.get("entry_price") or current.get("entry_plan")
    if updates.get("quantity") is None:
        updates["quantity"] = _compute_quantity(
            _to_float(updates.get("entry_price")) or _to_float(current.get("entry_price")) or _to_float(current.get("entry_plan")),
            _to_float(updates.get("stop_loss")) or _to_float(current.get("stop_loss")),
            _to_float(updates.get("risk_amount")) or _to_float(current.get("risk_amount")),
        )
    updates["execution_authorized"] = True if current.get("execution_authorized") else bool(payload.get("execution_authorized", True))
    trade = update_trade(trade_id, updates)
    add_event(trade_id, "OPEN", "Trade opened", payload)
    return trade


def close_trade(trade_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    current = get_trade(trade_id)
    if not current:
        raise KeyError("trade_not_found")
    exit_price = _to_float(payload.get("exit_price"))
    if exit_price is None:
        raise ValueError("exit_price_required")
    entry_price = _to_float(current.get("entry_price") or current.get("entry_plan"))
    quantity = _to_float(current.get("quantity")) or 0.0
    risk_amount = _to_float(current.get("risk_amount"))
    stop_loss = _to_float(current.get("stop_loss"))
    pnl_amount = (exit_price - (entry_price or 0.0)) * quantity
    pnl_pct = ((exit_price - (entry_price or 0.0)) / (entry_price or 1.0)) * 100 if entry_price else None
    r_multiple = pnl_amount / risk_amount if risk_amount and risk_amount > 0 else None
    updates = {
        "status": "CLOSED",
        "closed_at": payload.get("closed_at") or utc_now_iso(),
        "exit_price": exit_price,
        "exit_reason": payload.get("exit_reason") or "MANUAL",
        "pnl_amount": pnl_amount,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,
        "notes": payload.get("notes") or current.get("notes"),
    }
    if stop_loss is not None and entry_price is not None and quantity:
        updates["risk_amount"] = risk_amount or abs(entry_price - stop_loss) * quantity
    trade = update_trade(trade_id, updates)
    add_event(trade_id, "CLOSE", f"Trade closed via {updates['exit_reason']}", payload)
    return trade


def cancel_trade(trade_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    updates = {
        "status": "CANCELLED",
        "notes": (payload or {}).get("notes"),
    }
    trade = update_trade(trade_id, updates)
    add_event(trade_id, "CANCEL", "Trade cancelled", payload)
    return trade


def delete_trade(trade_id: str) -> Dict[str, Any]:
    return cancel_trade(trade_id)


def add_event(trade_id: str, event_type: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO trade_events (trade_id, created_at, event_type, message, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trade_id, utc_now_iso(), event_type, message, _json_dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()


def list_events(trade_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            if trade_id:
                rows = conn.execute("SELECT * FROM trade_events WHERE trade_id = ? ORDER BY created_at DESC", (trade_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM trade_events ORDER BY created_at DESC").fetchall()
            return [dict(row) | {"payload_json": _json_loads(row["payload_json"])} for row in rows]
        finally:
            conn.close()


def stats() -> Dict[str, Any]:
    trades = _fetch_all("status != 'CANCELLED'")
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    planned_trades = [t for t in trades if t["status"] == "PLANNED"]
    watchlist_trades = [t for t in trades if t["status"] == "WATCHLIST"]
    closed_trades = [t for t in trades if t["status"] == "CLOSED"]
    real_closed = [t for t in closed_trades if isinstance(t.get("pnl_usd"), (int, float))]
    wins = [t for t in real_closed if (t.get("pnl_usd") or 0) > 0]
    losses = [t for t in real_closed if (t.get("pnl_usd") or 0) <= 0]
    total_pnl = round(sum((t.get("pnl_usd") or 0) for t in real_closed), 2)
    avg_r = round(sum((t.get("r_multiple") or 0) for t in real_closed) / len(real_closed), 2) if real_closed else 0.0
    best_trade = max((t.get("pnl_usd") or 0) for t in real_closed) if real_closed else 0.0
    worst_trade = min((t.get("pnl_usd") or 0) for t in real_closed) if real_closed else 0.0
    exposure = round(sum((t.get("entry_price") or 0) * (t.get("quantity") or 0) for t in open_trades), 2)
    risk_open = round(sum((t.get("risk_amount") or 0) for t in open_trades), 2)
    pnl_latent = None
    return {
        "total_trades": len(trades),
        "open_trades": len(open_trades),
        "planned_trades": len(planned_trades),
        "watchlist_trades": len(watchlist_trades),
        "closed_trades": len(closed_trades),
        "win_rate": round((len(wins) / len(real_closed) * 100) if real_closed else 0.0, 2),
        "total_pnl": total_pnl,
        "average_r": avg_r,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "exposure_current": exposure,
        "risk_open_total": risk_open,
        "pnl_latent": pnl_latent,
        "max_positions_actions": 5,
        "max_positions_crypto": 3,
        "realized_count": len(real_closed),
        "average_position_size": round(sum((t.get("quantity") or 0) for t in open_trades), 4) if open_trades else 0,
    }


def create_scalp_trade(
    symbol: str,
    scalp_result: Dict[str, Any],
    status: str = "SCALP_WATCHLIST",
) -> Dict[str, Any]:
    """
    Create a SCALP trade entry from CryptoScalpResult.

    Args:
        symbol: Crypto symbol (BTC, ETH, etc.)
        scalp_result: CryptoScalpResult dict from crypto_scalp_service
        status: Trade status (SCALP_WATCHLIST or SCALP_PAPER_PLANNED)

    Returns:
        Created trade dict
    """
    if status not in ("SCALP_WATCHLIST", "SCALP_PAPER_PLANNED"):
        status = "SCALP_WATCHLIST"

    trade_id = f"scalp_{symbol.upper()}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    payload = {
        "id": trade_id,
        "symbol": symbol.upper(),
        "universe": "CRYPTO",
        "status": status,
        "direction": scalp_result.get("side", "NONE"),
        "setup_grade": scalp_result.get("scalp_grade"),
        "signal_type": "SCALP",
        "strategy_name": scalp_result.get("strategy_name"),
        "entry_price": scalp_result.get("entry"),
        "stop_loss": scalp_result.get("stop_loss"),
        "tp1": scalp_result.get("tp1"),
        "tp2": scalp_result.get("tp2"),
        "execution_authorized": False,
        # Cost fields (Phase 2 enhancement)
        "entry_fee_pct": scalp_result.get("entry_fee_pct"),
        "exit_fee_pct": scalp_result.get("exit_fee_pct"),
        "slippage_pct": scalp_result.get("slippage_pct"),
        "spread_bps": scalp_result.get("spread_bps"),
        "estimated_roundtrip_cost_pct": scalp_result.get("estimated_roundtrip_cost_pct"),
        "notes": f"Scalp {scalp_result.get('side')} — Score: {scalp_result.get('scalp_score')}, Grade: {scalp_result.get('scalp_grade')}, Timeframe: {scalp_result.get('timeframe')}",
        "source_snapshot_json": scalp_result,
    }

    return create_trade(payload)


init_db()
