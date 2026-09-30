#!/usr/bin/env python3
"""Install only the personal niri session files."""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nyxuri.core import get_env  # noqa: E402
from nyxuri.deploy.atomic import atomic_replace_item  # noqa: E402
from nyxuri.deploy.assets import deploy_wallpapers  # noqa: E402
from nyxuri.deploy.deploy import _phase_atomic_deployment  # noqa: E402
from nyxuri.deploy.templates import _phase_render_templates  # noqa: E402

CONFIGS = ("niri", "noctalia", "kitty-nyxuri")
SESSION_TOOLS = ("niri", "noctalia", "kitty", "mpvpaper", "ffmpeg", "jq", "inotifywait", "wlsunset")


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
    missing = [binary for binary in SESSION_TOOLS if not shutil.which(binary)]
    if missing:
        print(f"Install session tools before deploying: {', '.join(missing)}", file=sys.stderr)
        return 1

    portal_source = ROOT / "configs/xdg-desktop-portal/niri-portals.conf"
    portal_target = env.config_dir / "xdg-desktop-portal" / "niri-portals.conf"
    if not portal_source.is_file() or (portal_target.is_symlink() and not portal_target.resolve().is_relative_to(env.home)):
        print(f"Unsafe portal destination: {portal_target}", file=sys.stderr)
        return 1
    if not marker_path.is_file() and (portal_target.exists() or portal_target.is_symlink()):
        print(f"Existing portal config needs review: {portal_target}", file=sys.stderr)
        return 1

    print("Deploy: niri, noctalia, kitty-nyxuri")
    print("Portal: niri-portals.conf; wallpaper: offline starter image")
    if _phase_atomic_deployment(list(CONFIGS)):
        return 1
    for item in CONFIGS:
        _phase_render_templates(only_app=item)
    deploy_wallpapers(do_download=False)
    if not atomic_replace_item(portal_source, portal_target):
        return 1
    marker = ROOT / "personal" / "mode-enabled"
    if not atomic_replace_item(marker, marker_path):
        return 1
    print("Session files installed. Log out and choose niri in GDM for the first session test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
