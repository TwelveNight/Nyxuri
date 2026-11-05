#!/usr/bin/env python3
"""Bridge skwd's images to Noctalia's palette and lockscreen, without rendering."""
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import socket
import sys
import time
import tomllib

VIDEO = {".mp4", ".webm", ".mkv", ".mov", ".gif"}


def current():
    result = subprocess.run(["skwd-helm", "current", "--json"], capture_output=True, text=True, check=True, timeout=5)
    outputs = json.loads(result.stdout).get("outputs", [])
    if isinstance(outputs, dict):
        outputs = [dict(value, name=name) for name, value in outputs.items()]
    return [output for output in outputs if output.get("connected") is not False]


def preview(output):
    if output.get("type") == "we":
        cached = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
        path = output.get("thumbnailPath") or output.get("thumb") or str(cached / "skwd-wall-v2/we-thumbs" / (str(output.get("we_id", "")) + ".webp"))
        return path if Path(path).is_file() else None
    path = output.get("path", "")
    source = Path(path)
    if not path or not source.is_file():
        return None
    if source.suffix.lower() not in VIDEO:
        return path
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "nyxuri-desktop/thumbnails"
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{path}:{source.stat().st_mtime_ns}".encode()).hexdigest()
    thumbnail = cache / f"{digest}.jpg"
    if not thumbnail.is_file():
        subprocess.run(["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(thumbnail)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=30)
    return str(thumbnail)


def preview_marker(path, connector=""):
    directory = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"nyxuri-wallpaper-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    for old in directory.iterdir():
        if old.is_file() and time.time() - old.stat().st_mtime > 60:
            old.unlink(missing_ok=True)
    key = hashlib.sha256(f"{connector}:{path}".encode()).hexdigest()
    return directory / key


def hook():
    path = os.environ.get("NOCTALIA_WALLPAPER_PATH", "")
    connector = os.environ.get("NOCTALIA_WALLPAPER_CONNECTOR", "")
    if not path:
        return
    marker = preview_marker(path, connector)
    if marker.exists():
        marker.unlink(missing_ok=True)
        return  # This event is our own preview update, never a render request.
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    source = Path(path).expanduser().resolve()
    if source.is_relative_to((cache / "nyxuri-desktop/thumbnails").resolve()):
        return  # Never replace a video with its preview image.
    for output in current():
        if connector and connector != (output.get("name") or output.get("output")):
            continue
        if path in [output.get("path"), preview(output)]:
            return
    apply(path, connector or None)


def sync():
    status = subprocess.run(["noctalia", "msg", "status"], capture_output=True,
                            text=True, check=True, timeout=3)
    if json.loads(status.stdout)["locked"]:
        return False  # Config/texture reloads can crash Noctalia's active locker.
    lock_path = None
    for output in current():
        path = preview(output)
        if not path:
            continue
        # Noctalia has one explicit lock wallpaper; prefer the first live output.
        if lock_path is None:
            lock_path = path
        connector = output.get("name") or output.get("output") or output.get("connector") or output.get("output_name")
        args = [connector] if connector else []
        saved = subprocess.run(["noctalia", "msg", "wallpaper-get", *args], capture_output=True, text=True, timeout=3)
        if saved.returncode == 0 and saved.stdout.strip() == path:
            continue
        preview_marker(path, connector or "").touch()
        subprocess.run(["noctalia", "msg", "wallpaper-set", *args, path], check=True, timeout=5)
    if lock_path is not None:
        # Since 5.4, disabling its desktop renderer also disables implicit follow.
        saved = subprocess.run(["noctalia", "msg", "config-get", "lockscreen.wallpaper"],
                               capture_output=True, text=True, check=True, timeout=3)
        if tomllib.loads("wallpaper = " + saved.stdout)["wallpaper"] != lock_path:
            subprocess.run(["noctalia", "msg", "config-set", "lockscreen.wallpaper",
                            json.dumps(lock_path, ensure_ascii=False)], check=True, timeout=5)
    return True


def apply(path, output=None):
    """Send the rendering request first; the watcher syncs Noctalia separately."""
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Wallpaper must be a file")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    address = os.environ.get("SKWD_WALL_V2_SOCK") or str(Path(runtime) / "skwd-wall-v2/wall.sock")
    request = {"id": 1, "method": "wall.apply", "params": {
        "type": "video" if source.suffix.lower() in VIDEO else "static",
        "path": str(source), "no_transition": True, "notify": False}}
    if output:
        request["params"]["output"] = output
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10)
        client.connect(address)
        client.sendall((json.dumps(request) + "\n").encode())
        with client.makefile("rb") as reply:
            response = json.loads(reply.readline(1024 * 1024))
    if response.get("id") != 1 or response.get("error") or "result" not in response:
        raise ValueError(f"skwd rejected wallpaper: {response.get('error', response)}")


def watch():
    # Start watching before reading current state so no event falls in between.
    while True:
        with subprocess.Popen(["skwd-helm", "watch"], stdout=subprocess.PIPE) as stream:
            assert stream.stdout is not None
            try:
                pending = True
                while True:
                    if pending:
                        try:
                            pending = not sync()
                        except (OSError, ValueError, subprocess.SubprocessError) as error:
                            print(f"wallpaper sync: {error}", file=sys.stderr)
                    # Retry after unlock without needing another wallpaper event.
                    ready, _, _ = select.select([stream.stdout], [], [], 2 if pending else None)
                    if ready:
                        if not os.read(stream.stdout.fileno(), 65536):
                            break
                        pending = True
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f"wallpaper sync: {error}", file=sys.stderr)
            finally:
                stream.terminate()
        time.sleep(2)


if __name__ == "__main__":
    try:
        if sys.argv[1] == "apply":
            apply(sys.argv[2])
        else:
            {"watch": watch, "sync": sync, "hook": hook}[sys.argv[1]]()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"wallpaper bridge: {error}", file=sys.stderr)
        raise SystemExit(1)
