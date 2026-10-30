#!/usr/bin/python3 -S
"""Use Noctalia's region capture, then show its PNG in a private layer surface."""
import shlex
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    if sys.argv[1:] == ["--stdin"]:
        image = sys.stdin.buffer.read()
        if not image:
            return 0
        if len(image) < 24 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
            raise ValueError("Expected a PNG screenshot")
        output = json.loads(subprocess.check_output(["niri", "msg", "-j", "focused-output"], text=True))
        with tempfile.TemporaryDirectory(prefix="nyxuri-pin-", dir=os.environ["XDG_RUNTIME_DIR"]) as directory:
            path = Path(directory) / "region.png"
            path.write_bytes(image)
            env = dict(os.environ, NYXURI_PIN_IMAGE=path.as_uri(),
                       NYXURI_PIN_OUTPUT=output["name"], NYXURI_PIN_SCALE=str(output["logical"]["scale"]))
            return subprocess.run(["quickshell", "--path", str(Path(__file__).with_name("screenshot-pin.qml"))], env=env, check=True).returncode

    command = shlex.join([sys.executable, "-S", str(Path(__file__).resolve()), "--stdin"])
    return subprocess.run([
        "noctalia", "msg", "screenshot-region", "--no-confirm-region", "--no-annotate",
        "--no-save-to-file", "--no-copy-to-clipboard", "--pipe-to-command",
        "--format", "png", "--pipe-command", command,
    ], check=True).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Screenshot pin: {error}", file=sys.stderr)
        sys.exit(1)
