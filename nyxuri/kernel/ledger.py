"""UnitLedger — the state domain's single entry (unit-model.md §2).

The only kernel module that reads or writes ``state.json``. Generic
key/value selections (active shell, migration level) and unit records
share one atomic write path: flock, merge, tmp file, ``os.replace``.

Unit records live under the top-level ``units`` key, keyed by unit id.
Each record carries exactly five frozen fields (unit-model.md §3):
``state`` / ``preset`` / ``files`` / ``vault`` / ``updated``. Kernel
code must not invent a sixth.
"""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nyxuri.core import get_env

UNIT_STATES = ("enabled", "disabled")

# --- generic ledger primitives -------------------------------------------


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


# --- shell selection ------------------------------------------------------


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


# --- unit records (KM0 frozen five-field shape) ---------------------------


def all_units() -> dict[str, dict[str, Any]]:
    """Every unit record in the ledger, keyed by unit id."""
    units = read_ledger().get("units")
    if not isinstance(units, dict):
        return {}
    return {uid: dict(rec) for uid, rec in units.items() if isinstance(rec, dict)}


def get_unit(unit_id: str) -> dict[str, Any] | None:
    """One unit record, or None when the unit was never switched."""
    return all_units().get(unit_id)


def set_unit(
    unit_id: str,
    *,
    state: str,
    preset: str = "default",
    files: dict[str, str] | None = None,
    vault: str | None = None,
    updated: str | None = None,
) -> dict[str, Any]:
    """Upsert one unit record, enforcing the frozen five-field shape.

    ``state``: ``enabled`` / ``disabled`` (the only switch axis).
    ``preset``: current form-axis choice. ``files``: ``{relpath: sha256}``
    snapshot of managed files. ``vault``: archive location of the user's
    custom files — mandatory once the unit is ``disabled``. ``updated``:
    ISO timestamp, defaulted to now (UTC).
    """
    if state not in UNIT_STATES:
        raise ValueError(f"invalid unit state '{state}' (must be 'enabled' or 'disabled')")
    if not isinstance(preset, str) or not preset:
        raise ValueError("preset must be a non-empty string")
    if files is None:
        files = {}
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in files.items()
    ):
        raise ValueError("files must map relative paths to hash strings")
    if vault is not None and not isinstance(vault, str):
        raise ValueError("vault must be an archive path string or None")
    if state == "disabled" and not vault:
        raise ValueError(f"disabled unit '{unit_id}' requires a vault archive path")
    if updated is None:
        updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "state": state,
        "preset": preset,
        "files": dict(files),
        "vault": vault,
        "updated": updated,
    }
    data = update_ledger(units={unit_id: record})
    return dict(data["units"][unit_id])
