#!/usr/bin/python3 -S
"""Keep native copy-only capture; send saved regions to Swappy."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


def main(timeout=180):
    with tempfile.TemporaryDirectory(prefix="nyxuri-shot-", dir=os.environ["XDG_RUNTIME_DIR"]) as directory:
        path = str(Path(directory) / "region.png")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(os.environ["NIRI_SOCKET"])
            client.sendall(b'"EventStream"\n')
            with client.makefile("rb") as events:
                if json.loads(events.readline()) != {"Ok": "Handled"}:
                    raise RuntimeError("Niri event subscription failed")
                initial_panel = json.loads(subprocess.check_output(["noctalia", "msg", "status"], text=True))
                if initial_panel["locked"]:
                    return 0
                initial_layers = json.loads(subprocess.check_output(["niri", "msg", "-j", "layers"], text=True))
                subprocess.run(["niri", "msg", "action", "screenshot", "--path", path], check=True)
                deadline = time.monotonic() + timeout
                # Niri emits completion after encoding/writing, but no event on Escape.
                # The bounded one-shot listener therefore expires quietly after cancellation.
                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return 0
                        client.settimeout(remaining)
                        line = events.readline()
                        if not line:
                            raise RuntimeError("Niri event stream disconnected")
                        event = json.loads(line)
                        if "ScreenshotCaptured" not in event:
                            continue
                        captured = event["ScreenshotCaptured"]["path"]
                        if captured is None:
                            return 0  # Ctrl+C: Niri has already copied the region.
                        if captured == path:
                            break
                except TimeoutError:
                    return 0

        # Capture first, then release the captured panels' exclusive keyboard focus.
        # Copy-only and cancellation must leave these interfaces untouched.
        if initial_panel["panelOpen"]:
            current_panel = json.loads(subprocess.check_output(["noctalia", "msg", "status"], text=True))
            if current_panel["panelOpen"] and current_panel["activePanelId"] == initial_panel["activePanelId"]:
                subprocess.run(["noctalia", "msg", "panel-close", initial_panel["activePanelId"]], check=True)
        if any(layer["namespace"] == "skwd-wall" for layer in initial_layers):
            current_layers = json.loads(subprocess.check_output(["niri", "msg", "-j", "layers"], text=True))
            if any(layer["namespace"] == "skwd-wall" for layer in current_layers):
                subprocess.run(["skwd-helm", "ui", "hide"], check=True)
        with subprocess.Popen(["swappy", "-f", path]) as editor:
            deadline = time.monotonic() + 5
            # Panel close animations and focus-follows-mouse can otherwise leave
            # the new editor visible but typing directed to the previous app.
            while editor.poll() is None and time.monotonic() < deadline:
                layers = json.loads(subprocess.check_output(["niri", "msg", "-j", "layers"], text=True))
                if not any(layer["keyboard_interactivity"] == "Exclusive" for layer in layers):
                    windows = json.loads(subprocess.check_output(["niri", "msg", "-j", "windows"], text=True))
                    window = next((window for window in windows if window["pid"] == editor.pid and window["app_id"] == "swappy"), None)
                    if window is not None:
                        subprocess.run(["niri", "msg", "action", "focus-window", "--id", str(window["id"])], check=True)
                        break
                time.sleep(0.05)
            return editor.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Screenshot editor: {error}", file=sys.stderr)
        sys.exit(1)
