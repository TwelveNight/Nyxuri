"""Market ↔ Shell event bridge — the unit-changed delivery.

The kernel freezes an abstract event port (unit-model.md §6): after every
transaction lands, ONE ``unit-changed`` event fires. This module is the
outer layer's injection point: it delivers the event over the Shell's
EXISTING Quickshell IPC channel (``qs -p <shell> ipc call unit reload``)
and never opens a second channel. No subscriber (tests, headless machines,
Noctalia sessions) → plain no-op; a failing delivery never fails the unit.
"""

import subprocess
from pathlib import Path
from typing import Optional

from nyxuri.core import log_msg
from nyxuri.desktop.shell_switcher import probe_running_shells, resolve_custom_bin
from nyxuri.kernel import transaction


def _shell_ipc_dir() -> Optional[Path]:
    """The shell config dir a Quickshell IPC call must target (marker: shell.qml)."""
    bin_path = resolve_custom_bin()
    if not bin_path:
        return None
    try:
        resolved = Path(bin_path).resolve()
    except OSError:
        return None
    for candidate in (resolved.parent, resolved.parent.parent):
        if (candidate / "shell.qml").is_file():
            return candidate
    return None


def notify_unit_changed(unit_id: str, state: str) -> None:
    """Deliver one unit-changed event; best-effort by contract (§6).

    The event carries no payload — the Shell re-reads the ledger as the
    single source of truth and projects it. Without a running nyxuri-shell
    this is a no-op returning before any subprocess is spawned.
    """
    running = [pid for name, pid in probe_running_shells() if name == "nyxuri-shell"]
    if not running:
        return
    shell_dir = _shell_ipc_dir()
    if shell_dir is None:
        log_msg("WARN", f"unit-changed for {unit_id}: shell dir not resolvable")
        return
    subprocess.run(
        ["qs", "-p", str(shell_dir), "ipc", "call", "unit", "reload"],
        timeout=1.5, capture_output=True, check=False,
    )


def wire() -> None:
    """Inject the delivery into the kernel's event port (outer layer's job)."""
    transaction.set_event_sink(notify_unit_changed)
