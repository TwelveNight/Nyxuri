"""Personal install/update policy behind the ordinary install.sh bootstrap."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from nyxuri import core
from personal import install, update

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
        source = env.config_dir / "nyxuri-desktop/nyxuri.desktop"
        subprocess.run(["sudo", "install", "-Dm644", str(source), str(GDM_ENTRY)], check=True)
    core.ensure_nyxuri_symlink()
    print("Nyxuri installed. Log out and choose Nyxuri (niri + Noctalia).")


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
    from nyxuri.i18n import text
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
              "  ./install.sh update [--no-deploy] [--yes]\n"
              "  ./install.sh doctor | test | pkg ...\n\n"
              "Install and deploy use the same private desktop scope.\n"
              "Other explicit commands use the upstream CLI.")
        return 0
    from nyxuri.cli import main as upstream_main
    sys.argv = [sys.argv[0], *arguments]
    upstream_main()
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
