#!/usr/bin/env python3
"""Use the same native cliphist history as iNiR and ii."""
import fcntl
import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import tempfile
import time

PANEL_ID = "night/shared-clipboard:history"
PLUGIN_ID = "night/shared-clipboard"


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


def list_entries():
    listed = subprocess.run(["cliphist", "list"], capture_output=True, check=True)
    entries = []
    for line in listed.stdout.splitlines():
        entry_id, separator, preview = line.partition(b"\t")
        if not separator or not entry_id.isdigit():
            continue
        label = preview.decode("utf-8", "replace")
        image = bool(re.fullmatch(r"\[\[.*binary data.*\d+x\d+.*\]\]", label))
        entries.append({"id": entry_id.decode(), "text": label, "image": image})
    return entries


def decode(entry_id):
    if not re.fullmatch(r"[0-9]+", entry_id):
        raise ValueError("Invalid clipboard entry id")
    return subprocess.run(["cliphist", "decode", entry_id], capture_output=True, check=True).stdout


def copy_entry(entry_id):
    payload = decode(entry_id)
    if not is_image(payload):
        payload = clean_text(payload)
    return subprocess.run(["wl-copy"], input=payload,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def is_image(payload):
    return (payload.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a"))
            or payload.startswith(b"RIFF") and payload[8:12] == b"WEBP")


def preview_directory(session):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid clipboard preview session")
    return Path(os.environ["XDG_RUNTIME_DIR"]) / "nyxuri-clipboard-previews" / session


def preview_entry(entry_id, session="default"):
    payload = decode(entry_id)
    if is_image(payload):
        directory = preview_directory(session)
        directory.parent.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory.parent, 0o700)
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        # Only selected images are materialized; never write a history snapshot.
        descriptor, name = tempfile.mkstemp(prefix=entry_id + "-", dir=directory)
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
        return {"path": name}
    return {"text": clean_text(payload).decode("utf-8", "replace")[:16000]}


def clear_previews(session="default"):
    directory = preview_directory(session)
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file() and re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+", path.name):
                path.unlink(missing_ok=True)
        try:
            directory.rmdir()
        except OSError:
            pass


def setup_panel():
    # Adding our own named path source preserves all other enabled plugins and
    # sources in Noctalia's private GUI settings; it does not touch shared data.
    root = Path.home() / ".config/noctalia/personal-plugins"
    subprocess.run(["noctalia", "msg", "plugins", "source", "add", "nyxuri-personal", "path", str(root)],
                   capture_output=True, check=True)
    subprocess.run(["noctalia", "msg", "plugins", "enable", PLUGIN_ID], capture_output=True, check=True)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = subprocess.run(["noctalia", "msg", "plugins", "list"], capture_output=True, text=True, check=True)
        if any(line.startswith(PLUGIN_ID + " ") and re.search(r"\benabled\b", line)
               for line in result.stdout.splitlines()):
            return
        time.sleep(0.1)
    raise RuntimeError("The shared clipboard panel did not become ready")


def pick():
    command = ["noctalia", "msg", "panel-toggle", PANEL_ID]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        setup_panel()
        result = subprocess.run(command, capture_output=True, check=True)
    return result.returncode


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
    if not arguments:
        raise ValueError("Clipboard action is required")
    action = arguments[0]
    if action == "preview" and len(arguments) == 3:
        print(json.dumps(preview_entry(arguments[1], arguments[2]), ensure_ascii=False))
        return 0
    if action == "clear-preview" and len(arguments) == 2:
        clear_previews(arguments[1])
        return 0
    if action == "copy" and len(arguments) == 2:
        if action == "copy":
            return copy_entry(arguments[1])
    if len(arguments) != 1 or action not in ("pick", "watch", "store-text", "store-image", "list", "clear-preview", "setup-panel"):
        raise ValueError("Invalid clipboard action")
    if action == "list":
        print(json.dumps(list_entries(), ensure_ascii=False))
        return 0
    if action == "clear-preview":
        clear_previews()
        return 0
    if action == "setup-panel":
        setup_panel()
        return 0
    if action.startswith("store-"):
        return store(action[6:], sys.stdin.buffer.read())
    if action == "pick":
        return pick()
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
