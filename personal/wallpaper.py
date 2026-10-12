#!/usr/bin/env python3
"""Bridge skwd's active images to Noctalia's palette, without another renderer."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

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


def sync():
    for output in current():
        path = preview(output)
        if not path:
            continue
        connector = output.get("name") or output.get("output") or output.get("connector") or output.get("output_name")
        args = [connector] if connector else []
        saved = subprocess.run(["noctalia", "msg", "wallpaper-get", *args], capture_output=True, text=True, timeout=3)
        if saved.returncode == 0 and saved.stdout.strip() == path:
            continue
        subprocess.run(["noctalia", "msg", "wallpaper-set", *args, path], check=True, timeout=5)


def hook():
    path = os.environ.get("NOCTALIA_WALLPAPER_PATH", "")
    if not path or not Path(path).is_file():
        return
    outputs = current()
    connector = os.environ.get("NOCTALIA_WALLPAPER_CONNECTOR", "")
    relevant = [o for o in outputs if not connector or connector in (o.get("name"), o.get("output"), o.get("connector"), o.get("output_name"))]
    # Our preview updates also emit wallpaper_changed. Never send thumbnails
    # back as a new desktop wallpaper, or a video would turn into its first frame.
    if any(path in (o.get("path"), preview(o)) for o in relevant):
        return
    args = ["-o", connector] if connector else []
    subprocess.run(["skwd-helm", "apply", path, *args], check=True, timeout=30)


def watch():
    # Start watching before reading current state so no event falls in between.
    while True:
        with subprocess.Popen(["skwd-helm", "watch"], stdout=subprocess.PIPE, text=True) as stream:
            try:
                sync()
                for _ in stream.stdout:
                    try:
                        sync()
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        print(f"wallpaper sync: {error}", file=sys.stderr)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f"wallpaper sync: {error}", file=sys.stderr)
            finally:
                stream.terminate()
        time.sleep(2)


if __name__ == "__main__":
    try:
        {"watch": watch, "hook": hook, "sync": sync}[sys.argv[1]]()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"wallpaper bridge: {error}", file=sys.stderr)
        raise SystemExit(1)
