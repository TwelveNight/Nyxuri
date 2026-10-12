#!/usr/bin/env python3
"""Use the same native cliphist history as iNiR and ii."""
import fcntl
import html
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading


def clean_text(payload):
    # Match iNiR's browser-markup filter; ordinary text stays byte-for-byte.
    if not (payload.startswith(b'<meta http-equiv="content-type" content="text/html')
            or b"<!--StartFragment-->" in payload):
        return payload
    markup = payload.decode("utf-8", "replace")
    markup = re.sub(r"^<meta[^>]*>", "", markup, count=1)
    markup = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", markup)
    markup = re.sub(r"(?s)<!--.*?-->", "", markup)
    markup = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    markup = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|blockquote|pre)>", "\n", markup)
    markup = re.sub(r'''(?i)<img[^>]*\bsrc=["']([^"']+)["'][^>]*>''', r"\1", markup)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip().encode("utf-8")


def store(kind, payload):
    if os.environ.get("CLIPBOARD_STATE") in ("nil", "clear", "sensitive"):
        return 0
    if kind == "text":
        payload = clean_text(payload)
    if not payload:
        return 0
    # No private -db-path or -config-path: share native cliphist settings too.
    return subprocess.run(["cliphist", "store"], input=payload,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def pick():
    listed = subprocess.run(["cliphist", "list"], capture_output=True, check=True)
    entries = listed.stdout.splitlines()
    if not entries:
        return 0
    config = Path(__file__).resolve().with_name("clipboard-fuzzel.ini")
    chosen = subprocess.run(["fuzzel", "--config", str(config), "--namespace=nyxuri-clipboard",
                             "--dmenu", "--index", "--only-match", "--match-mode=fzf",
                             "--prompt=剪贴板 > "], input=listed.stdout, capture_output=True)
    if chosen.returncode != 0:
        return 0 if chosen.returncode == 1 else chosen.returncode
    index = int(chosen.stdout.strip())
    if not 0 <= index < len(entries):
        raise ValueError("Clipboard selection is outside the displayed history")
    decoded = subprocess.run(["cliphist", "decode"], input=entries[index] + b"\n",
                             capture_output=True, check=True)
    payload = decoded.stdout
    # Old browser-markup entries need the same cleanup iNiR applies on decode.
    if b"\t[[" not in entries[index]:
        payload = clean_text(payload)
    return subprocess.run(["wl-copy"], input=payload,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def stop_workers(workers):
    # Each worker owns a process group, including its currently storing child.
    for worker in workers:
        try:
            os.killpg(worker.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for worker in workers:
        try:
            worker.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            worker.wait()


def watch():
    script = str(Path(__file__).resolve())
    commands = [
        ["wl-paste", "--no-newline", "--type", "text", "--watch", sys.executable, script, "store-text"],
        ["wl-paste", "--type", "image", "--watch", sys.executable, script, "store-image"],
        ["wl-clip-persist", "--clipboard", "both"],
    ]
    stopped = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: stopped.set())
                for sig in (signal.SIGTERM, signal.SIGINT)}
    workers = []
    try:
        for command in commands:
            workers.append(subprocess.Popen(command, start_new_session=True,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        while not stopped.wait(0.25):
            if any(worker.poll() is not None for worker in workers):
                print("A Nyxuri clipboard worker stopped; restarting the private service.", file=sys.stderr)
                return 1
        return 0
    finally:
        stop_workers(workers)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1 or arguments[0] not in ("pick", "watch", "store-text", "store-image"):
        raise ValueError("Usage: clipboard.py {pick|watch|store-text|store-image}")
    action = arguments[0]
    if action.startswith("store-"):
        return store(action[6:], sys.stdin.buffer.read())
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    # Keep lock files in place; unlinking a locked inode allows two owners.
    with (runtime / f"nyxuri-clipboard-{action}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        return pick() if action == "pick" else watch()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never include command output or clipboard payloads in the journal.
        print("Nyxuri clipboard action failed; check the session tools and history database.", file=sys.stderr)
        raise SystemExit(1)
