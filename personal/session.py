#!/usr/bin/env python3
"""GDM entry, mirroring the standard niri-session systemd lifecycle."""
import os
import subprocess


def main():
    unit = "nyxuri-niri.service"
    for candidate in ("niri.service", unit):
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", candidate]).returncode == 0:
            raise SystemExit("A Niri session is already running.")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "import-environment"], check=True)
    subprocess.run(["dbus-update-activation-environment", "--all"], check=True)
    try:
        return subprocess.run(["systemctl", "--user", "--wait", "start", unit]).returncode
    finally:
        subprocess.run(["systemctl", "--user", "start", "--job-mode=replace-irreversibly", "niri-shutdown.target"], check=False)
        subprocess.run(["systemctl", "--user", "unset-environment", "WAYLAND_DISPLAY", "DISPLAY", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "NIRI_SOCKET"], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
