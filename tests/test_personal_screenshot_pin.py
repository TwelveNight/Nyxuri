"""Screenshot pin command boundaries; visual layer/input checks run in-session."""
import json
import os
from pathlib import Path
import subprocess
import struct
import unittest
import zlib

from tests.utils import TempEnv
from personal import install


ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "personal/screenshot_pin.py"


class ScreenshotPinTests(unittest.TestCase):
    def test_installer_delivers_both_files_and_middle_button_binding(self):
        with TempEnv() as context:
            stage = context.home / "source"
            stage.mkdir()
            install.prepare_sources(stage)
            for name in ("screenshot_pin.py", "screenshot-pin.qml"):
                target = stage / "niri/scripts" / name
                self.assertTrue(target.is_file(), f"Pin component not deployed: {name}")
                self.assertEqual(target.read_bytes(), (ROOT / "personal" / name).read_bytes())
            self.assertTrue(os.access(stage / "niri/scripts/screenshot_pin.py", os.X_OK))
            binds = (stage / "niri/personal-binds.kdl").read_text()
            self.assertIn('Ctrl+Alt+MouseMiddle repeat=false hotkey-overlay-title="Screenshot and pin" { spawn "~/.config/niri/scripts/screenshot_pin.py"; }', binds)
            self.assertIn('Ctrl+1 repeat=false hotkey-overlay-title="Screenshot region"', binds)

    def test_png_lives_only_until_the_pin_process_exits(self):
        with TempEnv() as context:
            log = context.home / "pin.json"
            executable = context.home / "command.py"
            executable.write_text('''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
if Path(sys.argv[0]).name == "niri":
    assert sys.argv[1:] == ["msg", "-j", "focused-output"], sys.argv
    print(json.dumps({"name":"HDMI-A-1","logical":{"scale":1.5}}))
else:
    assert sys.argv[1:3] == ["--path", str(Path(os.environ["PIN_QML"]))], sys.argv
    path = Path(os.environ["NYXURI_PIN_IMAGE"].removeprefix("file://"))
    assert path.read_bytes() == bytes.fromhex(os.environ["EXPECTED_PNG"])
    Path(os.environ["PIN_LOG"]).write_text(json.dumps({"path":str(path),"mode":path.parent.stat().st_mode & 0o777,"output":os.environ["NYXURI_PIN_OUTPUT"],"scale":os.environ["NYXURI_PIN_SCALE"]}))
''')
            executable.chmod(0o755)
            for name in ("niri", "quickshell"):
                (context.home / name).symlink_to(executable)
            def chunk(name, data):
                return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
            png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\0\xff\0")) + chunk(b"IEND", b"")
            env = dict(os.environ, PATH=str(context.home) + ":" + os.environ["PATH"], XDG_RUNTIME_DIR=str(context.home), PIN_LOG=str(log), PIN_QML=str(ROOT / "personal/screenshot-pin.qml"), EXPECTED_PNG=png.hex())
            result = subprocess.run(["python3", str(HELPER), "--stdin"], input=png, env=env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(log.exists(), "PNG was not delivered to a pin surface")
            receipt = json.loads(log.read_text())
            self.assertEqual(receipt["mode"], 0o700)
            self.assertEqual(receipt["output"], "HDMI-A-1")
            self.assertEqual(float(receipt["scale"]), 1.5)
            self.assertFalse(Path(receipt["path"]).exists())
            self.assertEqual(list(context.home.glob("nyxuri-pin-*")), [])

    def test_capture_uses_native_noctalia_without_changing_output_policy(self):
        with TempEnv() as context:
            command = context.home / "noctalia"
            log = context.home / "capture.json"
            command.write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["CAPTURE_LOG"]).write_text(json.dumps(sys.argv[1:]))\n')
            command.chmod(0o755)
            env = dict(os.environ, PATH=str(context.home) + ":" + os.environ["PATH"], CAPTURE_LOG=str(log))
            self.assertTrue(HELPER.is_file(), "Screenshot pin bridge is not implemented")
            result = subprocess.run(["python3", str(HELPER)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads(log.read_text())
            self.assertEqual(args[:-1], ["msg", "screenshot-region", "--no-confirm-region", "--no-annotate", "--no-save-to-file", "--no-copy-to-clipboard", "--pipe-to-command", "--format", "png", "--pipe-command"])
            import shlex
            self.assertEqual(shlex.split(args[-1])[1:], ["-S", str(HELPER), "--stdin"])


if __name__ == "__main__":
    unittest.main()
