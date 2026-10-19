#!/usr/bin/env python3
"""Merge official updates into the personal branch, then redeploy privately."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent


def conflict_help():
    message = (f"Nyxuri 上游合并冲突，live 未更新。请在 {ROOT} 打开 AI，"
               "修复 git status 中的冲突并 git commit，再运行 nyxuri update。"
               "取消可运行 git merge --abort。")
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "-a", "nyxuri", "-u", "critical",
                            "Nyxuri 更新需要 AI 修复", message], timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return message


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0")).stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local", action="store_true", help="redeploy this reviewed checkout without fetching or merging")
    mode.add_argument("--no-deploy", action="store_true")
    mode.add_argument("--check", action="store_true", help="fetch official main and report new commits without merging or deploying")
    parser.add_argument("--yes", action="store_true", help="apply the installation plan after merging")
    args = parser.parse_args(argv)
    if args.local:
        return deploy(args.yes)
    helper = Path.home() / ".local/bin/desktop-update"
    registry = Path.home() / ".config/desktop-profiles/profiles.json"
    if helper.is_file() and registry.is_file():
        action = "check" if args.check else "sync" if args.no_deploy else "update"
        return subprocess.run([str(helper), action, "nyxuri"], check=False).returncode
    if not args.check and git("status", "--porcelain"):
        print("Working tree has local changes. Finish or save them before updating.", file=sys.stderr)
        return 1
    if git("branch", "--show-current") != "night/personal-overlay":
        print("Switch to night/personal-overlay before updating.", file=sys.stderr)
        return 1
    if git("remote", "get-url", "origin") != "https://github.com/ech678/Nyxuri.git":
        print("origin must point to the official Nyxuri repository.", file=sys.stderr)
        return 1
    git("-c", "http.lowSpeedTime=15", "-c", "http.lowSpeedLimit=1000", "fetch", "origin", "main")
    if args.check:
        ahead, behind = map(int, git("rev-list", "--left-right", "--count", "HEAD...FETCH_HEAD").split())
        print(json.dumps(dict(profile="nyxuri", upstream="origin/main", ahead=ahead, behind=behind,
                              status="behind" if behind else "current")))
        return 0
    # The personal adapter consumes units/. Never merge an incompatible
    # upstream unit-layout migration and discover the mismatch during deployment.
    for source in ("units/niri/config.kdl", "units/noctalia/noctalia-config.toml"):
        try:
            git("cat-file", "-e", "FETCH_HEAD:" + source)
        except subprocess.CalledProcessError:
            print("Upstream configuration layout changed; update stopped before merge or deployment. "
                  "Review the new unit architecture in the main worktree first.", file=sys.stderr)
            return 1
    # No reset/stash/rebase: personal commits remain visible; conflicts stop
    # before any deployment and can be reviewed with ordinary Git tools.
    try:
        git("merge", "--no-edit", "FETCH_HEAD")
    except subprocess.CalledProcessError:
        if git("diff", "--name-only", "--diff-filter=U"):
            print(conflict_help(), file=sys.stderr)
            return 1
        raise
    if args.no_deploy:
        return 0
    return deploy(args.yes)


def deploy(yes=False):
    # Fresh process loads the current personal deployment engine.
    command = [str(ROOT / "install.sh"), "install"]
    if yes:
        command.append("--yes")
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.SubprocessError, OSError) as error:
        print(f"Update stopped; no configuration deployed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print((error.stdout or "") + (error.stderr or ""), file=sys.stderr)
        raise SystemExit(1)
