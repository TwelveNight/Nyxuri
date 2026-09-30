#!/usr/bin/env python3
"""Install only the personal niri session and its Hyprland wallpaper units."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nyxuri.core import get_env  # noqa: E402
from nyxuri.deploy.atomic import atomic_replace_item  # noqa: E402
from nyxuri.deploy.deploy import _phase_atomic_deployment  # noqa: E402
from nyxuri.deploy.templates import _phase_render_templates  # noqa: E402

CONFIGS = ("niri", "noctalia", "kitty-nyxuri")


def main() -> int:
    if os.geteuid() == 0:
        print("Run this installer as your desktop user.", file=sys.stderr)
        return 1
    env = get_env()
    marker_path = env.nyx_dir / "personal-mode"
    if not marker_path.is_file() and any((env.config_dir / item).exists() for item in CONFIGS):
        print("A session config already exists. Review it before the first personal deployment.", file=sys.stderr)
        return 1
    if not (env.config_dir / "kitty" / "kitty.conf").is_file():
        print("Existing Kitty settings are required.", file=sys.stderr)
        return 1
    if not all(shutil.which(binary) for binary in ("niri", "noctalia", "kitty")):
        print("Install niri, noctalia and kitty before deploying the session.", file=sys.stderr)
        return 1

    units_dir = env.config_dir / "systemd" / "user"
    units = (
        (ROOT / "personal/systemd/hyprland-session.target", units_dir / "hyprland-session.target"),
        (ROOT / "personal/systemd/ii-skwd-wall-theme.service", units_dir / "ii-skwd-wall-theme.service"),
        (ROOT / "personal/systemd/skwd-walld-session.conf", units_dir / "skwd-walld.service.d" / "session.conf"),
    )
    old_unit = units_dir / "ii-skwd-wall-theme.service"
    for source, target in units:
        if not source.is_file() or (target.is_symlink() and not target.resolve().is_relative_to(env.home)):
            print(f"Unsafe unit destination: {target}", file=sys.stderr)
            return 1
        if not marker_path.is_file() and target != old_unit and (target.exists() or target.is_symlink()):
            print(f"Existing user unit needs review: {target}", file=sys.stderr)
            return 1

    print("Deploy: niri, noctalia, kitty-nyxuri")
    print("User units: hyprland-session.target, ii-skwd-wall-theme.service, skwd-walld drop-in")
    print("Enable wallpaper services only for the Hyprland session")
    backup = env.nyx_dir / "personal-original" / old_unit.name
    if old_unit.is_file() and not backup.exists():
        if not atomic_replace_item(old_unit, backup):
            return 1
    if _phase_atomic_deployment(list(CONFIGS)):
        return 1
    for item in CONFIGS:
        _phase_render_templates(only_app=item)
    for source, target in units:
        if not atomic_replace_item(source, target):
            return 1

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "disable", "ii-skwd-wall-theme.service"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "ii-skwd-wall-theme.service"], check=True)
    marker = ROOT / "personal" / "mode-enabled"
    if not atomic_replace_item(marker, marker_path):
        return 1
    print("Session files installed. Log out and choose niri in GDM for the first session test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
