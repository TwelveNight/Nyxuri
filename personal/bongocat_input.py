#!/usr/bin/python3
"""Resolve keyd's aggregate keyboard before execing Bongo Cat's evtest reader.

No event logging, key remapping, grabbing, background loop or extra input access.
"""
import argparse
import os
from pathlib import Path
import sys

FALLBACK = "/dev/input/by-path/platform-i8042-serio-0-event-kbd"


def resolve_device(fallback, sys_root=Path("/sys/class/input"), dev_root=Path("/dev/input")):
    if fallback != FALLBACK:
        raise ValueError("unexpected keyboard selector")
    matches = []
    for event in sys_root.glob("event*"):
        if not event.name[5:].isdigit():
            continue
        try:
            name = (event / "device/name").read_text().strip()
        except OSError:
            continue
        if name == "keyd virtual keyboard":
            node = dev_root / event.name
            if node.exists() and os.access(node, os.R_OK):
                matches.append(node)
    if len(matches) > 1:
        raise ValueError("multiple keyd virtual keyboards; refusing ambiguous selection")
    if matches:
        return matches[0]
    node = dev_root / "by-path" / Path(fallback).name
    if not node.exists() or not os.access(node, os.R_OK):
        raise ValueError("no readable keyd keyboard or configured fallback")
    return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true", help="print selected path only; read no events")
    parser.add_argument("device")
    args = parser.parse_args()
    try:
        device = resolve_device(args.device)
    except (OSError, ValueError) as error:
        print(f"Bongo Cat keyboard: {error}", file=sys.stderr)
        return 1
    if args.resolve:
        print(device)
        return 0
    os.execv("/usr/bin/evtest", ["evtest", str(device)])


if __name__ == "__main__":
    raise SystemExit(main())
