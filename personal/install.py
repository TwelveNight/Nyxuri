#!/usr/bin/env python3
"""Deploy a private Nyxuri desktop using the upstream atomic engine."""
import argparse
import copy
import os
import re
import tomllib
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nyxuri import core
from personal.autostart import disable_todesk
from personal.cheatsheet_categories import annotate
from nyxuri.deploy.atomic import atomic_replace_item
from nyxuri.deploy.assets import deploy_wallpapers
from nyxuri.deploy.deploy import _phase_atomic_deployment
from nyxuri.deploy.templates import _phase_render_templates
from nyxuri.modules.fcitx import FCITX_CLASSICUI_RELOAD_HOOK

CONFIGS = ("niri", "noctalia", "kitty-nyxuri")
AUTOSTART_UNITS = (
    "app-com.onepassword.OnePassword@autostart.service",
    r"app-clash\x2dverge@autostart.service",
    "app-org.fcitx.Fcitx5@autostart.service",
    "app-org.kde.kdeconnect.daemon@autostart.service",
)
SESSION_TOOLS = ("niri", "noctalia", "kitty", "skwd-helm", "ffmpeg", "jq", "inotifywait", "wlsunset", "systemctl", "dbus-update-activation-environment", "busctl", "systemd-notify", "cliphist", "wl-paste", "wl-copy", "wl-clip-persist")


def prepare_sources(destination: Path) -> None:
    for item in CONFIGS:
        shutil.copytree(ROOT / "configs" / item, destination / item, symlinks=True)
    shutil.copy2(ROOT / "personal/noctalia-keybinds.toml", destination / "noctalia/zz-personal-keybinds.toml")
    shutil.copy2(ROOT / "personal/keybind-cheatsheet.toml", destination / "noctalia/zz-personal-cheatsheet.toml")
    # Rewrite the copied templates, never the upstream sources or live iNiR tree.
    for path in destination.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for app in ("niri", "noctalia", "kitty-nyxuri"):
            content = content.replace(f".config/{app}", f".config/nyxuri-desktop/{app}")
            content = content.replace('${XDG_CONFIG_HOME:-$HOME/.config}/' + app,
                                      '${XDG_CONFIG_HOME:-$HOME/.config}/nyxuri-desktop/' + app)
        for name in ("nyxuri", "nyxniri"):
            content = content.replace(f".cache/{name}/", ".cache/nyxuri-desktop/")
        content = content.replace(".local/state/noctalia/mpvpaper", ".local/state/nyxuri-desktop/noctalia/mpvpaper")
        content = content.replace(".cache/noctalia/mpvpaper", ".cache/nyxuri-desktop/mpvpaper")
        content = content.replace('cache_base .. "/noctalia/mpvpaper"', 'cache_base .. "/nyxuri-desktop/mpvpaper"')
        path.write_text(content, encoding="utf-8")
    effects = destination / "niri/effects.kdl"
    if not effects.exists() and not effects.is_symlink():
        effects.symlink_to("effects_normal.kdl")
    niri = destination / "niri/config.kdl"
    niri.write_text(niri.read_text().replace('environment {', 'environment {\n    NOCTALIA_CONFIG_HOME "/home/user/.config/nyxuri-desktop"\n    NOCTALIA_STATE_HOME "/home/user/.local/state/nyxuri-desktop/noctalia"'))
    content = niri.read_text()
    content = re.sub(r'QT_QPA_PLATFORMTHEME "[^"]*"', 'QT_QPA_PLATFORMTHEME "kde"', content)
    if "KITTY_CONFIG_DIRECTORY" not in content:
        content = content.replace('environment {', 'environment {\n    KITTY_CONFIG_DIRECTORY "/home/user/.config/nyxuri-desktop/kitty-nyxuri"')
    # The ordered shell unit owns startup; don't spawn a second shell or IME.
    content = re.sub(r'^spawn-at-startup .*session-shell\.sh".*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^spawn-at-startup .*fcitx5.*\n', '', content, flags=re.MULTILINE)
    custom_include = 'include "__custom__.kdl"'
    if custom_include not in content:
        raise ValueError("Upstream Niri custom include contract changed; review before deployment")
    content = content.replace(custom_include, 'include "personal-binds.kdl"\ninclude "75-personal-binds.kdl"\ninclude "personal-startup.kdl"\ninclude "personal-overview.kdl"\ninclude "personal-cursor.kdl"\ninclude "personal-gpu.kdl"\ninclude "personal-window-rules.kdl"\ninclude "personal-games.kdl"\n' + custom_include)
    niri.write_text(content)
    shutil.copy2(ROOT / "personal/binds.kdl", destination / "niri/personal-binds.kdl")
    shutil.copy2(ROOT / "personal/75-personal-binds.kdl", destination / "niri/75-personal-binds.kdl")
    # Remove the inherited chord so Super+X reaches applications again.
    binds = destination / "niri/binds.kdl"
    binds.write_text(re.sub(r'^    Mod\+X\s[^\n]*\n', "", binds.read_text(), flags=re.MULTILINE))
    binds.write_text(binds.read_text().replace('Mod+V { spawn', 'Mod+V repeat=false { spawn'))
    shutil.copy2(ROOT / "personal/startup.kdl", destination / "niri/personal-startup.kdl")
    shutil.copy2(ROOT / "personal/overview.kdl", destination / "niri/personal-overview.kdl")
    shutil.copy2(ROOT / "personal/cursor.kdl", destination / "niri/personal-cursor.kdl")
    shutil.copy2(ROOT / "personal/gpu.kdl", destination / "niri/personal-gpu.kdl")
    shutil.copy2(ROOT / "personal/window-rules.kdl", destination / "niri/personal-window-rules.kdl")
    shutil.copy2(ROOT / "personal/games.kdl", destination / "niri/personal-games.kdl")
    shutil.copy2(ROOT / "personal/monitor.kdl", destination / "niri/monitor.kdl")
    scripts = destination / "niri/scripts"
    for name in ("desktop-session.py", "runtime.py", "session.py", "wallpaper.py", "clipboard.py"):
        shutil.copy2(ROOT / "personal" / name, scripts / name)
    plugin = destination / "noctalia/personal-plugins/shared-clipboard"
    shutil.copytree(ROOT / "personal/clipboard-panel", plugin)
    shutil.copy2(ROOT / "personal/clipboard.py", plugin / "backend.py")
    shutil.copy2(ROOT / "personal/niri_actions.py", scripts / "niri-actions.py")
    (scripts / "session-shell.sh").write_text(
        '#!/bin/sh\nexec python3 "$(dirname "$0")/runtime.py"\n', encoding="utf-8")
    action = scripts / "shell-action.sh"
    content = action.read_text()
    content = content.replace('action="${1:-}"', 'action="${1:-}"\nexport NOCTALIA_CONFIG_HOME="$HOME/.config/nyxuri-desktop"\nexport NOCTALIA_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/nyxuri-desktop/noctalia"')
    # This session always runs Noctalia. A legacy public shell selection must
    # never send its keyboard actions to a different desktop's executable.
    start = content.index('state_root=')
    end = content.index('case "$action" in')
    content = content[:start] + content[end:]
    content = content.replace("exec noctalia msg wallpaper-random", 'exec skwd-helm random')
    content = content.replace("exec noctalia msg panel-toggle clipboard",
                              'exec python3 "$(dirname "$0")/clipboard.py" pick')
    action.write_text(content)
    orbit = scripts / "niri-scratch-menu.py"
    orbit.write_text(orbit.read_text().replace('os.path.join(CONFIG_HOME, "noctalia",',
                                             'os.path.join(CONFIG_HOME, "nyxuri-desktop", "noctalia",'))
    # Request the renderer directly; preview synchronization never calls it back.
    shutil.copy2(ROOT / "personal/wallpaper-backend.py", destination / "noctalia/tools/wallpaper_picker/backend.py")
    conf = destination / "noctalia/noctalia-config.toml"
    text = conf.read_text().replace('[wallpaper]\n', '[wallpaper]\nenabled = false\ntransition = []\ntransition_duration = 0\n')
    text = text.replace('[shell.greeter_sync]\nauto_sync = true', '[shell.greeter_sync]\nauto_sync = false')
    text = text.replace('wallpaper_changed = ["~/.config/nyxuri-desktop/noctalia/wallpaper-hook.sh"]', 'wallpaper_changed = ["python3 ~/.config/nyxuri-desktop/niri/scripts/wallpaper.py hook"]')
    text = text.replace('enabled = ["noctalia/mpvpaper"]', 'enabled = []')
    text = re.sub(r'\n\[widget\.mpvpaper\][\s\S]*?(?=\n\[|\Z)', '', text)
    text = re.sub(r'\n\[plugin_settings\."noctalia/mpvpaper"\][\s\S]*?(?=\n\[|\Z)', '', text)
    text = text.replace('start = ["launcher", "workspaces", "group:g1"]',
                        'start = ["launcher", "wallpaper", "workspaces", "group:g1"]')
    conf.write_text(text)
    # Reassert the personal output boundary against fresh upstream defaults.
    data = tomllib.loads(text)
    fcitx_names = {f"nyxmellow_{suffix}" for suffix in ("theme", "panel", "highlight")}
    policy = ['[shell]', 'clipboard_enabled = false', '[theme.templates]', 'builtin_ids = []', 'community_ids = []',
              '[theme.templates.user.nyxuri_kitty]', 'index = 7',
              'input_path = "/home/user/.config/nyxuri-desktop/noctalia/templates/kitty-nyxuri.conf"',
              'output_path = "/home/user/.config/nyxuri-desktop/kitty-nyxuri/colors__custom__.conf"',
              "post_hook = 'pkill -SIGUSR1 -x kitty >/dev/null 2>&1 || true'"]
    for name, template in data.get("theme", {}).get("templates", {}).get("user", {}).items():
        output = template.get("output_path", "")
        if name not in fcitx_names and "/.config/nyxuri-desktop/" not in output and "/.cache/nyxuri-desktop/" not in output:
            policy += [f"[theme.templates.user.{name}]", "enabled = false"]
    # Fcitx is an explicitly shared application theme, owned by the current desktop.
    fcitx_templates = destination / "noctalia/templates/fcitx5"
    shutil.copytree(ROOT / "assets/fcitx5/nyxmellow/templates", fcitx_templates, dirs_exist_ok=True)
    for index, (suffix, filename) in enumerate((("theme", "theme.conf"), ("panel", "panel.svg"), ("highlight", "highlight.svg")), 8):
        policy += [f"[theme.templates.user.nyxmellow_{suffix}]", "enabled = true", f"index = {index}",
                   f'input_path = "/home/user/.config/nyxuri-desktop/noctalia/templates/fcitx5/{filename}"',
                   f'output_path = "/home/user/.local/share/fcitx5/themes/nyxmellow/{filename}"']
        if suffix == "highlight":
            policy += [f"post_hook = '{FCITX_CLASSICUI_RELOAD_HOOK}'"]
    policy += ['[widget.wallpaper.actions]', 'left = "exec skwd-wall-v2"']
    (destination / "noctalia/zz-personal.toml").write_text("\n".join(policy) + "\n")
    for name in ("config.kdl", "binds.kdl", "personal-binds.kdl", "75-personal-binds.kdl"):
        target = destination / "niri" / name
        target.write_text(annotate(target.read_text()))


def main(argv=None, preflight=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="apply the printed deployment plan")
    parser.add_argument("--plan", action="store_true", help="show the deployment without writing files")
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        print("Run this installer as your desktop user.", file=sys.stderr)
        return 1
    env = core.get_env()
    private = env.config_dir / "nyxuri-desktop"
    print(f"Deploy: {private}/{{niri,noctalia,kitty-nyxuri}}")
    print(f"User services: {env.config_dir}/systemd/user/nyxuri-{{niri,shell,clipboard}}.service")
    print("Personal shortcuts and startup; create absent XDG entries: 1Password, Clash Verge; disable ToDesk in all desktops")
    print("Startup ordering: 1Password, Clash Verge, Fcitx5, KDE Connect wait for the private shell")
    print("Wallpaper: direct skwd switching; one-way Noctalia preview and private colors.")
    print("Clipboard: share iNiR/ii text and image history; Super+V opens the shared picker.")
    if preflight is not None:
        print("Register: Nyxuri GDM login entry; reload user service definitions.")
    if args.plan:
        return 0
    if not (env.config_dir / "kitty/kitty.conf").is_file():
        print("Existing Kitty settings are required.", file=sys.stderr)
        return 1
    missing = [name for name in SESSION_TOOLS if not shutil.which(name)]
    if missing:
        print(f"Install session tools first: {', '.join(missing)}", file=sys.stderr)
        return 1
    if private.is_symlink() or private.exists() and not (private / "installed").is_file():
        print(f"Existing private directory needs review: {private}", file=sys.stderr)
        return 1
    if not args.yes:
        if not sys.stdin.isatty() or input("Apply this plan? [y/N] ").strip().lower() != "y":
            return 2
    if preflight is not None:
        preflight(env)
    scoped = copy.copy(env)
    scoped.config_dir = private
    scoped.nyx_dir = private / "manager"
    scoped.presets_dir = scoped.nyx_dir / "presets"
    scoped.state_dir = env.home / ".local/state/nyxuri-desktop/manager"
    previous = core._ENV
    try:
        with tempfile.TemporaryDirectory(prefix="nyxuri-personal-") as temporary:
            scoped.configs_src = Path(temporary)
            prepare_sources(scoped.configs_src)
            core._ENV = scoped
            if _phase_atomic_deployment(list(CONFIGS)):
                return 1
            for item in CONFIGS:
                _phase_render_templates(only_app=item)
            kitty = private / "kitty-nyxuri/kitty.conf"
            kitty.write_text(kitty.read_text().replace("/home/user", str(env.home)))
            policy = private / "noctalia/zz-personal.toml"
            policy.write_text(policy.read_text().replace("/home/user", str(env.home)))
        # Wallpaper assets keep the upstream no-clobber contract.
        core._ENV = env
        deploy_wallpapers(do_download=False)
        for name in ("nyxuri-niri.service", "nyxuri-shell.service", "nyxuri-clipboard.service"):
            if not atomic_replace_item(ROOT / "personal" / name, env.config_dir / "systemd/user" / name):
                return 1
        for unit in AUTOSTART_UNITS:
            target = env.config_dir / "systemd/user" / (unit + ".d") / "50-nyxuri-shell.conf"
            if not atomic_replace_item(ROOT / "personal/autostart-order.conf", target):
                return 1
        # Shared XDG startup choices stay user-owned. Only create absent entries;
        # never re-enable a Hidden entry or replace an existing app command.
        if not disable_todesk(env.config_dir):
            return 1
        for source in sorted((ROOT / "personal/autostart").glob("*.desktop")):
            if source.name == "todesk.desktop":
                continue
            target = env.config_dir / "autostart" / source.name
            if target.exists() or target.is_symlink():
                continue
            if not atomic_replace_item(source, target):
                return 1
        with tempfile.TemporaryDirectory(prefix="nyxuri-entry-") as temporary:
            desktop = Path(temporary) / "nyxuri.desktop"
            desktop.write_text((ROOT / "personal/nyxuri.desktop").read_text().replace("/home/user", str(env.home)))
            if not atomic_replace_item(desktop, private / "nyxuri.desktop"):
                return 1
        if not atomic_replace_item(ROOT / "personal/mode-enabled", private / "installed"):
            return 1
    finally:
        core._ENV = previous
    if preflight is None:
        print("Files ready. Run systemctl --user daemon-reload, then install the GDM entry described in personal/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
