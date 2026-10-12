#!/usr/bin/env python3
"""Complete the compositor handoff before starting this session's shell."""
import os
import json
import time
from pathlib import Path
import signal
import subprocess
import sys


def wait_for_tray(shell, timeout=30):
    """Only our Noctalia process can complete the private shell's startup."""
    deadline = time.monotonic() + timeout
    command = ["busctl", "--user", "--json=short", "--timeout=1", "call",
               "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
               "GetConnectionUnixProcessID", "s", "org.kde.StatusNotifierWatcher"]
    while shell.poll() is None:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=2, check=False)
            if result.returncode == 0 and json.loads(result.stdout).get("data") == [shell.pid]:
                # The tray bus is acquired before Noctalia opens its IPC socket.
                # Wallpaper sync and startup apps need both to be available.
                ipc = subprocess.run(["noctalia", "msg", "status"], capture_output=True,
                                     text=True, timeout=2, check=False)
                if ipc.returncode == 0 and isinstance(json.loads(ipc.stdout), dict):
                    if os.environ.get("NOTIFY_SOCKET"):
                        subprocess.run(["systemd-notify", "--ready", "--status=Noctalia tray ready"], check=True)
                    return
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Noctalia did not acquire the tray bus and IPC; refusing to start personal tray apps")
        time.sleep(0.1)
    raise RuntimeError("Noctalia exited before tray startup completed")


def main():
    scripts = Path(__file__).resolve().parent
    config = Path.home() / ".config/nyxuri-desktop"
    # Noctalia appends /noctalia to these base directories itself.
    os.environ["NOCTALIA_CONFIG_HOME"] = str(config)
    # Keep the already-used private state root so GUI preferences survive.
    os.environ["NOCTALIA_STATE_HOME"] = str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "nyxuri-desktop/noctalia")
    # Systemd does not inherit Niri's per-child environment block. Applications
    # opened by Noctalia must use the same Kitty profile as compositor bindings.
    os.environ["KITTY_CONFIG_DIRECTORY"] = str(config / "kitty-nyxuri")
    # Reuse iNiR's socket/PID validation, environment handoff and stale-watcher
    # protection. Shared runtime state is deliberate: both Niri entries agree
    # with the existing Hyprland cleanup watcher on who owns the session.
    subprocess.run([sys.executable, str(scripts / "desktop-session.py"), "start", "niri", "--no-ii-theme"], check=True)
    shell = subprocess.Popen(["noctalia"])
    bridge = None
    def stop(_signum, _frame):
        if shell.poll() is None:
            shell.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        wait_for_tray(shell)
        bridge = subprocess.Popen([sys.executable, str(scripts / "wallpaper.py"), "watch"], start_new_session=True)
        return shell.wait()
    finally:
        if bridge and bridge.poll() is None:
            os.killpg(bridge.pid, signal.SIGTERM)
            bridge.wait(timeout=5)
        if shell.poll() is None:
            shell.terminate()
            shell.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
