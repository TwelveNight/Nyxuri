"""Native screenshot copy/edit delivery with isolated compositor and tool I/O."""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import unittest

from tests.utils import TempEnv
from personal import install


HELPER = Path(__file__).resolve().parent.parent / "personal/screenshot_edit.py"
FAKE_COMMAND = '''#!/usr/bin/python3
import json, os, pathlib, socket, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps([name, args]) + "\\n")
if name == "niri":
    if args == ["msg", "-j", "layers"]:
        print("[]" if pathlib.Path(os.environ["EDITOR_RECEIPT"] + ".hidden").exists() else os.environ["LAYERS_JSON"])
    elif args == ["msg", "-j", "windows"]:
        receipt = pathlib.Path(os.environ["EDITOR_RECEIPT"])
        print(json.dumps([{"id": 42, "app_id": "swappy", "pid": json.loads(receipt.read_text())["pid"]}] if receipt.exists() else []))
    elif args[:3] == ["msg", "action", "focus-window"]:
        assert args == ["msg", "action", "focus-window", "--id", "42"], args
        pathlib.Path(os.environ["EDITOR_RECEIPT"] + ".focused").touch()
    else:
        assert args[:4] == ["msg", "action", "screenshot", "--path"] and len(args) == 5, args
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(os.environ["NIRI_SOCKET"])
            client.sendall((json.dumps(args[4]) + "\\n").encode())
elif name == "noctalia":
    if args == ["msg", "status"]:
        print(json.dumps({"locked": False, "panelOpen": os.environ["HAS_PANEL"] == "1", "activePanelId": "control-center" if os.environ["HAS_PANEL"] == "1" else None}))
    else:
        assert args == ["msg", "panel-close", "control-center"], args
elif name == "skwd-helm":
    assert args == ["ui", "hide"], args
    pathlib.Path(os.environ["EDITOR_RECEIPT"] + ".hidden").touch()
elif name == "swappy":
    assert args[0] == "-f" and len(args) == 2, args
    path = pathlib.Path(args[1])
    assert path.read_bytes() == b"test-capture-fixture"
    receipt = pathlib.Path(os.environ["EDITOR_RECEIPT"])
    receipt.write_text(json.dumps({"path": str(path), "parent_mode": path.parent.stat().st_mode & 0o777, "pid": os.getpid()}))
    for _ in range(100):
        if pathlib.Path(str(receipt) + ".focused").exists():
            break
        time.sleep(0.01)
    else:
        sys.exit("editor never received compositor focus")
'''


class PersonalScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HELPER.is_file(), "Ctrl+2 capture-to-editor bridge has not been implemented")
        self.context = self.enterContext(TempEnv())
        self.root = self.context.home
        self.bin = self.root / "bin"
        self.bin.mkdir()
        executable = self.bin / "command.py"
        executable.write_text(FAKE_COMMAND)
        executable.chmod(0o755)
        for name in ("niri", "noctalia", "skwd-helm", "swappy"):
            (self.bin / name).symlink_to(executable)
        self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"], XDG_RUNTIME_DIR=str(self.root), NIRI_SOCKET=str(self.root / "n.sock"), COMMAND_LOG=str(self.root / "commands.jsonl"), EDITOR_RECEIPT=str(self.root / "editor.json"), HAS_PANEL="1", LAYERS_JSON=json.dumps([{"namespace": "skwd-wall", "keyboard_interactivity": "Exclusive"}]), PYTHONDONTWRITEBYTECODE="1")

    def exercise(self, mode, overlays=True):
        if not overlays:
            self.env.update(HAS_PANEL="0", LAYERS_JSON="[]")
        stopped = threading.Event()
        failures = []
        server = socket.socket(socket.AF_UNIX)
        server.bind(self.env["NIRI_SOCKET"])
        server.listen()
        server.settimeout(2)

        def compositor():
            try:
                with server.accept()[0] as stream:
                    request = stream.makefile("rb").readline()
                    if json.loads(request) != "EventStream":
                        raise AssertionError(request)
                    stream.sendall(b'{"Ok":"Handled"}\n')
                    with server.accept()[0] as action:
                        path = json.loads(action.makefile("rb").readline())
                    if mode == "cancel":
                        stopped.wait(2)
                        return
                    if mode == "clipboard":
                        event = {"ScreenshotCaptured": {"path": None}}
                    else:
                        if mode == "unrelated":
                            stream.sendall(b'{"ScreenshotCaptured":{"path":"/unrelated.png"}}\n')
                        Path(path).write_bytes(b"test-capture-fixture")
                        event = {"ScreenshotCaptured": {"path": path}}
                    stream.sendall((json.dumps(event) + "\n").encode())
            except BaseException as error:
                failures.append(error)

        worker = threading.Thread(target=compositor)
        worker.start()
        code = "import runpy,sys; module=runpy.run_path(sys.argv[1]); sys.exit(module['main'](timeout=0.25))"
        try:
            result = subprocess.run(["python3", "-c", code, str(HELPER)], env=self.env, capture_output=True, text=True, timeout=5)
        finally:
            stopped.set()
            worker.join(3)
            server.close()
        self.assertFalse(worker.is_alive(), "compositor probe did not stop")
        self.assertEqual(failures, [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.root.glob("nyxuri-shot-*")), [], "temporary capture leaked")
        calls = [json.loads(line) for line in (self.root / "commands.jsonl").read_text().splitlines()]
        return calls

    def test_saved_region_opens_editor_after_hiding_captured_overlays(self):
        calls = self.exercise("save")
        receipt = json.loads((self.root / "editor.json").read_text())
        self.assertEqual(receipt["parent_mode"], 0o700)
        self.assertFalse(Path(receipt["path"]).exists())
        self.assertTrue((self.root / "editor.json.focused").exists())
        names = [call[0] for call in calls]
        self.assertLess(names.index("skwd-helm"), names.index("swappy"))
        close = calls.index(["noctalia", ["msg", "panel-close", "control-center"]])
        self.assertLess(close, names.index("swappy"))

    def test_ctrl_c_does_not_open_editor_or_close_overlays(self):
        calls = self.exercise("clipboard")
        self.assertFalse((self.root / "editor.json").exists())
        self.assertNotIn("swappy", [call[0] for call in calls])
        self.assertNotIn("skwd-helm", [call[0] for call in calls])
        self.assertNotIn(["noctalia", ["msg", "panel-close", "control-center"]], calls)

    def test_cancel_expires_without_editor_or_overlay_changes(self):
        calls = self.exercise("cancel")
        self.assertFalse((self.root / "editor.json").exists())
        self.assertNotIn("swappy", [call[0] for call in calls])
        self.assertNotIn("skwd-helm", [call[0] for call in calls])
        self.assertNotIn(["noctalia", ["msg", "panel-close", "control-center"]], calls)

    def test_unrelated_saved_screenshot_is_not_opened(self):
        self.exercise("unrelated")
        self.assertNotEqual(json.loads((self.root / "editor.json").read_text())["path"], "/unrelated.png")

    def test_without_overlays_does_not_send_close_commands(self):
        calls = self.exercise("save", overlays=False)
        self.assertIn("swappy", [call[0] for call in calls])
        self.assertNotIn("skwd-helm", [call[0] for call in calls])
        self.assertFalse(any(call[0] == "noctalia" and call[1][:2] == ["msg", "panel-close"] for call in calls))


class PersonalScreenshotDeploymentTests(unittest.TestCase):
    def test_install_copies_helper_and_keeps_ctrl1(self):
        with TempEnv() as context:
            destination = context.home / "source"
            destination.mkdir()
            install.prepare_sources(destination)
            helper = destination / "niri/scripts/screenshot_edit.py"
            self.assertTrue(helper.is_file())
            self.assertEqual(helper.read_bytes(), HELPER.read_bytes())
            self.assertTrue(os.access(helper, os.X_OK))
            binds = (destination / "niri/personal-binds.kdl").read_text()
            self.assertIn('Ctrl+2 repeat=false hotkey-overlay-title="Screenshot region (Niri / Swappy)" { spawn "~/.config/niri/scripts/screenshot_edit.py"; }', binds)
            self.assertIn('Ctrl+1 repeat=false hotkey-overlay-title="Screenshot region" { spawn "noctalia" "msg" "screenshot-region"; }', binds)


if __name__ == "__main__":
    unittest.main()
