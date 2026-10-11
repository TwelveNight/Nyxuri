"""Small atomic JSON ledger for runtime selections and module state."""

import fcntl
import json
import os
from pathlib import Path
from typing import Any

from nyxuri.core import get_env


def ledger_path() -> Path:
    return get_env().state_dir / "state.json"


def read_ledger() -> dict[str, Any]:
    try:
        data = json.loads(ledger_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def update_ledger(**changes: Any) -> dict[str, Any]:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = None
    try:
        lock_handle = open(path.with_name(f".{path.name}.lock"), "a+")
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
    except OSError:
        if lock_handle is not None:
            lock_handle.close()
        lock_handle = None
    try:
        data = read_ledger()
        for key, value in changes.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if lock_handle is not None:
            lock_handle.close()
    return data


def active_shell(default: str = "noctalia") -> str:
    value = read_ledger().get("active_shell", default)
    if not isinstance(value, str):
        return default
    if value in {"nyxuri-shell", "nyxuri", "custom"}:
        return "nyxuri-shell"
    if value == "noctalia":
        return "noctalia"
    return default


def custom_shell_bin() -> str:
    ledger = read_ledger()
    val = ledger.get("custom_shell_bin") or ledger.get("nyxuri_shell_bin", "")
    return str(val) if isinstance(val, str) else ""


def nyxuri_shell_bin() -> str:
    return custom_shell_bin()


def set_shell(shell_name: str, bin_path: str | None = None) -> dict[str, Any]:
    s = str(shell_name).strip().lower()
    if s in {"nyxuri-shell", "nyxuri", "custom"}:
        canonical = "nyxuri-shell"
    elif s == "noctalia":
        canonical = "noctalia"
    else:
        raise ValueError(f"Invalid shell: {shell_name} (must be 'noctalia' or 'nyxuri-shell')")
    changes: dict[str, Any] = {"active_shell": canonical}
    if bin_path is not None:
        changes["custom_shell_bin"] = bin_path
    return update_ledger(**changes)
