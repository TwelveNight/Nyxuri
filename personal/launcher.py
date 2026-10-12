#!/usr/bin/python3 -S
"""Toggle the running Noctalia launcher without loading the shell executable."""
import os
import socket
import sys


def toggle():
    # Match Noctalia 5.2's IPC framing and the compositor's current display.
    path = os.environ["XDG_RUNTIME_DIR"] + "/noctalia-" + os.environ["WAYLAND_DISPLAY"] + ".sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(path)
        client.sendall(b"panel-toggle launcher")
        client.shutdown(socket.SHUT_WR)
        response = bytearray()
        while chunk := client.recv(4096):
            response.extend(chunk)
            if len(response) > 65536:
                raise RuntimeError("Noctalia IPC response too large")
    if not response or response.startswith(b"error:"):
        raise RuntimeError(response.decode(errors="replace").strip() or "Noctalia IPC closed without a response")


def main():
    try:
        toggle()
    except (KeyError, OSError, RuntimeError) as error:
        print(f"Launcher: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
