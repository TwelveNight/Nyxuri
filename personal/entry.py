"""Personal install/update policy behind the ordinary install.sh bootstrap."""
import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from nyxuri import core
from personal import gtk3, install, update

GDM_ENTRY = Path("/usr/share/wayland-sessions/nyxuri.desktop")


def needs_session_entry(env):
    expected = (install.ROOT / "personal/nyxuri.desktop").read_text().replace("/home/user", str(env.home))
    return not GDM_ENTRY.is_file() or GDM_ENTRY.read_text() != expected


def prepare_session(env):
    # Authenticate once, after the deployment confirmation but before writing
    # any configs. An already registered session needs no administrator access.
    if needs_session_entry(env):
        command = ["sudo", "-v"] if sys.stdin.isatty() else ["sudo", "-n", "-v"]
        subprocess.run(command, check=True)


def register_session(env):
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    if needs_session_entry(env):
        source = env.config_dir / "desktop-profiles/nyxuri/nyxuri.desktop"
        subprocess.run(["sudo", "install", "-Dm644", str(source), str(GDM_ENTRY)], check=True)
    core.ensure_nyxuri_symlink()
    print("Nyxuri installed. Log out and choose Nyxuri · Niri.")


def install_desktop(arguments):
    parser = argparse.ArgumentParser(prog="./install.sh install")
    parser.add_argument("mode", nargs="?", choices=("full", "config"))
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(arguments)
    forwarded = [flag for flag in ("--plan", "--yes") if getattr(args, flag[2:])]
    if args.plan:
        return install.main(forwarded, preflight=prepare_session)
    core.acquire_lock()
    try:
        result = install.main(forwarded, preflight=prepare_session)
        if result == 0:
            register_session(core.get_env())
        return result
    finally:
        core.release_lock()


def management_menu():
    from nyxuri.core import text
    from nyxuri.tui import Menu, MenuItem, press_any_key

    actions = (
        (text("部署个人桌面", "Deploy personal desktop"), ["install"]),
        (text("同步上游并更新", "Sync upstream and update"), ["update"]),
        (text("系统诊断", "System diagnostics"), ["doctor"]),
        (text("查看已安装软件", "List installed packages"), ["pkg", "installed"]),
        (text("预览缓存清理", "Preview cache cleanup"), ["clean", "-n"]),
        (text("命令帮助", "Command help"), ["help"]),
    )
    items = [MenuItem(label=label) for label, _ in actions]
    items.append(MenuItem(label=text("退出", "Exit"), style="subtle"))
    while True:
        choice = Menu("menu_title", items).run()
        if choice < 0 or choice >= len(actions):
            return 0
        # Fresh processes release command locks and load updated code separately.
        subprocess.run([str(install.ROOT / "install.sh"), *actions[choice][1]], cwd=install.ROOT)
        press_any_key()


def dispatch(arguments):
    if not arguments:
        return management_menu()
    if arguments[0] in ("--plan", "--yes"):
        return install_desktop(arguments)
    command, *rest = arguments
    command = command.lower()
    if command.lower() in ("install", "deploy"):
        return install_desktop(rest)
    if command.lower() == "update":
        return update.main(rest)
    if command in ("help", "--help", "-h"):
        if rest:
            raise ValueError("Usage: ./install.sh help")
        print("Nyxuri personal overlay (nyxuri)\n"
              "  nyxuri                         Open the management menu\n"
              "  nyxuri [install|deploy] [full|config] [--plan] [--yes]\n"
              "  ./install.sh update [--check | --local | --no-deploy] [--yes]\n"
              "  ./install.sh doctor | test | pkg ...\n\n"
              "Install and deploy use the same private desktop scope.\n"
              "Other explicit commands use the upstream CLI.")
        return 0
    managed = (core.get_env().config_dir / "desktop-profiles/profiles.json").is_file()
    if managed and command in ("on", "off", "enable", "disable"):
        print("Personal profile units are deployed together; use nyxuri install/update.", file=sys.stderr)
        return 2
    if managed and command == "preset" and (not rest or rest[0] not in install.CONFIGS):
        print("Personal presets support niri, noctalia and kitty-nyxuri.", file=sys.stderr)
        return 2
    if managed and command not in ("doctor", "test", "pkg", "help", "--help", "-h"):
        subprocess.run([str(core.get_env().home / ".local/bin/desktop-profile"), "guard", "nyxuri"], check=True)
    from nyxuri.cli import main as upstream_main
    sys.argv = [sys.argv[0], *arguments]
    previous = core._ENV
    if managed and command in ("snapshot", "backup", "list", "preset", "rollback", "restore", "uninstall", "remove", "purge"):
        scoped = copy.copy(core.get_env())
        scoped.config_dir = scoped.config_dir / "desktop-profiles/nyxuri"
        scoped.nyx_dir = scoped.config_dir / "manager"
        scoped.presets_dir = scoped.nyx_dir / "presets"
        scoped.state_dir = scoped.home / ".local/state/nyxuri-desktop/manager"
        core._ENV = scoped
    try:
        if core._ENV is not previous:
            with tempfile.TemporaryDirectory(prefix="nyxuri-personal-state-") as temporary:
                scoped.units_src = Path(temporary)
                scoped.shell_units_src = Path(temporary) / "unused-shell-units"
                install.prepare_sources(scoped.units_src)
                upstream_main()
        elif command == "theme" and (not rest or len(rest) == 1 and rest[0] in ("toggle", "dark", "light", "sync")):
            with gtk3.environment():
                upstream_main()
        else:
            upstream_main()
    finally:
        core._ENV = previous
    return 0


def main():
    if os.getuid() == 0 or os.geteuid() == 0:
        print("Run ./install.sh as your desktop user.", file=sys.stderr)
        raise SystemExit(1)
    try:
        result = dispatch(sys.argv[1:])
    except ValueError as error:
        print(error, file=sys.stderr)
        result = 2
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Personal operation stopped: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print((error.stdout or "") + (error.stderr or ""), file=sys.stderr)
        result = 1
    raise SystemExit(result)
