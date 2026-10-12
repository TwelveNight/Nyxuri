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
    parser.add_argument("--no-deploy", action="store_true")
    parser.add_argument("--yes", action="store_true", help="apply the installation plan after merging")
    args = parser.parse_args(argv)
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
    # No reset/stash/rebase: personal commits remain visible; conflicts stop
    # before any deployment and can be reviewed with ordinary Git tools.
    git("merge", "--no-edit", "FETCH_HEAD")
    if args.no_deploy:
        return 0
    # Fresh process loads the newly merged upstream deployment engine.
    command = [str(ROOT / "install.sh"), "install"]
    if args.yes:
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
