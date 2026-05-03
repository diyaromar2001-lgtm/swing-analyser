from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import numpy as np


def _default_state_path() -> Path:
    custom = os.environ.get("SWING_CACHE_STATE_PATH")
    if custom:
        return Path(custom)
    return Path(__file__).with_name(".cache_state.json")


STATE_PATH = _default_state_path()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.DataFrame):
        index_name = value.index.name or "index"
        records = value.reset_index().to_dict(orient="records")
        return {
            "__type__": "dataframe",
            "index_name": index_name,
            "records": _serialize_value(records),
        }
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, set):
        return [_serialize_value(v) for v in sorted(value, key=lambda x: str(x))]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        try:
            return _serialize_value(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _serialize_value(value.dict())
        except Exception:
            pass
    return str(value)


def _restore_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("__type__") == "dataframe":
            records = _restore_value(value.get("records", []))
            df = pd.DataFrame.from_records(records)
            index_name = value.get("index_name") or "index"
            if index_name in df.columns:
                try:
                    df[index_name] = pd.to_datetime(df[index_name], errors="ignore")
                    df = df.set_index(index_name)
                except Exception:
                    pass
            return df
        return {k: _restore_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_restore_value(v) for v in value]
    return value


def save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = _serialize_value(state)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except Exception:
        pass


def load_state() -> Dict[str, Any]:
    try:
        if not STATE_PATH.exists():
            return {}
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        restored = _restore_value(payload)
        return restored if isinstance(restored, dict) else {}
    except Exception:
        return {}
