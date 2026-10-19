#!/usr/bin/env python3
"""Merge official updates into the personal branch, then redeploy privately."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=120).stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local", action="store_true", help="redeploy this reviewed checkout without fetching or merging")
    mode.add_argument("--no-deploy", action="store_true")
    parser.add_argument("--yes", action="store_true", help="apply the installation plan after merging")
    args = parser.parse_args(argv)
    if args.local:
        return deploy(args.yes)
    if git("status", "--porcelain"):
        print("Working tree has local changes. Finish or save them before updating.", file=sys.stderr)
        return 1
    if git("branch", "--show-current") != "night/personal-overlay":
        print("Switch to night/personal-overlay before updating.", file=sys.stderr)
        return 1
    if git("remote", "get-url", "origin") != "https://github.com/ech678/Nyxuri.git":
        print("origin must point to the official Nyxuri repository.", file=sys.stderr)
        return 1
    git("-c", "http.lowSpeedTime=15", "-c", "http.lowSpeedLimit=1000", "fetch", "origin", "main")
    # The personal adapter consumes configs/. Never merge an incompatible
    # upstream unit-layout migration and discover the mismatch during deployment.
    for source in ("configs/niri/config.kdl", "configs/noctalia/noctalia-config.toml"):
        try:
            git("cat-file", "-e", "FETCH_HEAD:" + source)
        except subprocess.CalledProcessError:
            print("Upstream configuration layout changed; update stopped before merge or deployment. "
                  "Review the new unit architecture in the main worktree first.", file=sys.stderr)
            return 1
    # No reset/stash/rebase: personal commits remain visible; conflicts stop
    # before any deployment and can be reviewed with ordinary Git tools.
    git("merge", "--no-edit", "FETCH_HEAD")
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
