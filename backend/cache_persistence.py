from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone

import pandas as pd
import numpy as np


LAST_SAVE_AT: str | None = None
LAST_LOAD_AT: str | None = None
LAST_SAVE_ERROR: str | None = None
LAST_LOAD_ERROR: str | None = None
LAST_LOAD_SUCCESS: bool = False
LAST_SAVE_SUCCESS: bool = False
LOAD_ATTEMPTS: int = 0
SAVE_ATTEMPTS: int = 0


def _default_state_path() -> Path:
    custom = os.environ.get("SWING_CACHE_STATE_PATH")
    if custom:
        return Path(custom)
    railway_volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_volume:
        return Path(railway_volume) / ".cache_state.json"
    railway_data = os.environ.get("RAILWAY_DATA_DIR")
    if railway_data:
        return Path(railway_data) / ".cache_state.json"
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


def _section_is_empty(section: Any) -> bool:
    if section in (None, {}, [], ""):
        return True
    if isinstance(section, dict):
        for value in section.values():
            if value not in (None, {}, [], ""):
                return False
        return True
    return False


def _merge_existing_state(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(incoming)
    for key in ("actions", "crypto"):
        incoming_section = incoming.get(key)
        existing_section = existing.get(key)
        if _section_is_empty(incoming_section) and not _section_is_empty(existing_section):
            merged[key] = existing_section
            continue
        if isinstance(incoming_section, dict) and isinstance(existing_section, dict):
            section_merged = dict(existing_section)
            section_merged.update({k: v for k, v in incoming_section.items() if v not in (None, {}, [], "")})
            merged[key] = section_merged
    return merged


def _status_payload() -> Dict[str, Any]:
    return {
        "persistence_enabled": True,
        "persistence_dir": str(STATE_PATH.parent),
        "persistence_file": str(STATE_PATH),
        "persistence_files_found": [str(STATE_PATH)] if STATE_PATH.exists() else [],
        "last_persistence_save": LAST_SAVE_AT,
        "last_persistence_load": LAST_LOAD_AT,
        "persistence_load_errors": [LAST_LOAD_ERROR] if LAST_LOAD_ERROR else [],
        "persistence_save_errors": [LAST_SAVE_ERROR] if LAST_SAVE_ERROR else [],
        "persistence_last_save_ok": LAST_SAVE_SUCCESS,
        "persistence_last_load_ok": LAST_LOAD_SUCCESS,
        "load_attempts": LOAD_ATTEMPTS,
        "save_attempts": SAVE_ATTEMPTS,
    }


def save_state(state: Dict[str, Any]) -> None:
    global LAST_SAVE_AT, LAST_SAVE_ERROR, LAST_SAVE_SUCCESS, SAVE_ATTEMPTS
    SAVE_ATTEMPTS += 1
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = _serialize_value(state)
        if STATE_PATH.exists():
            try:
                existing_raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                existing = _restore_value(existing_raw)
                if isinstance(existing, dict) and isinstance(payload, dict):
                    payload = _merge_existing_state(existing, payload)
            except Exception as exc:
                LAST_SAVE_ERROR = f"load_existing_failed: {type(exc).__name__}: {str(exc)[:120]}"
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_PATH)
        LAST_SAVE_AT = datetime.now(timezone.utc).isoformat()
        LAST_SAVE_ERROR = None
        LAST_SAVE_SUCCESS = True
    except Exception:
        LAST_SAVE_ERROR = "save_state_failed"
        LAST_SAVE_SUCCESS = False


def load_state() -> Dict[str, Any]:
    global LAST_LOAD_AT, LAST_LOAD_ERROR, LAST_LOAD_SUCCESS, LOAD_ATTEMPTS
    LOAD_ATTEMPTS += 1
    try:
        if not STATE_PATH.exists():
            LAST_LOAD_SUCCESS = False
            return {}
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        restored = _restore_value(payload)
        LAST_LOAD_AT = datetime.now(timezone.utc).isoformat()
        LAST_LOAD_ERROR = None
        LAST_LOAD_SUCCESS = True
        return restored if isinstance(restored, dict) else {}
    except Exception as exc:
        LAST_LOAD_ERROR = f"{type(exc).__name__}: {str(exc)[:120]}"
        LAST_LOAD_SUCCESS = False
        return {}


def get_status() -> Dict[str, Any]:
    return _status_payload()
