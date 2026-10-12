"""Shared history, byte preservation and session-owned clipboard workers."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from personal import clipboard, install
from tests.utils import TempEnv


class PersonalClipboardTests(unittest.TestCase):
    def test_native_cliphist_roundtrip_uses_shared_database_for_text_and_png(self):
        import base64
        import shutil
        if not shutil.which("cliphist"):
            self.skipTest("cliphist is not installed")
        with TempEnv() as ctx:
            text = b"shared text\n\n"
            png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
            self.assertEqual(clipboard.store("text", text), 0)
            self.assertEqual(clipboard.store("image", png), 0)
            run_native = subprocess.run
            entries = run_native(["cliphist", "list"], capture_output=True, check=True).stdout.splitlines()
            self.assertEqual(len(entries), 2)
            self.assertTrue((ctx.home / ".cache/cliphist/db").is_file())
            copied = []
            for index, expected in ((0, png), (1, text)):
                def select_and_copy(command, **kwargs):
                    if command[0] == "fuzzel":
                        return Mock(returncode=0, stdout=str(index).encode())
                    if command[0] == "wl-copy":
                        copied.append(kwargs["input"])
                        return Mock(returncode=0)
                    return run_native(command, **kwargs)
                with patch.object(clipboard.subprocess, "run", side_effect=select_and_copy):
                    self.assertEqual(clipboard.pick(), 0)
                self.assertEqual(copied[-1], expected)

    def test_store_and_decode_preserve_text_newlines_and_image_bytes(self):
        with TempEnv(), patch.object(clipboard.subprocess, "run", return_value=Mock(returncode=0)) as run:
            for kind, payload in (("text", b"source <div>\n\n"), ("image", b"\x89PNG\r\n\x1a\n\0\xff")):
                self.assertEqual(clipboard.store(kind, payload), 0)
                self.assertEqual(run.call_args.args[0], ["cliphist", "store"])
                self.assertEqual(run.call_args.kwargs["input"], payload)
                run.reset_mock()
                entries = b"17\t[[binary data 8 B png 1x1]]\n" if kind == "image" else b"17\tsource <div>\n"
                run.side_effect = [Mock(returncode=0, stdout=entries),
                                   Mock(returncode=0, stdout=b"0\n"),
                                   Mock(returncode=0, stdout=payload), Mock(returncode=0)]
                self.assertEqual(clipboard.pick(), 0)
                self.assertEqual([call.args[0] for call in run.call_args_list], [
                    ["cliphist", "list"],
                    ["fuzzel", "--config", str(Path(clipboard.__file__).with_name("clipboard-fuzzel.ini")),
                     "--namespace=nyxuri-clipboard", "--dmenu", "--index", "--only-match",
                     "--match-mode=fzf", "--prompt=剪贴板 > "],
                    ["cliphist", "decode"], ["wl-copy"]])
                self.assertEqual(run.call_args_list[2].kwargs["input"], entries)
                self.assertEqual(run.call_args.kwargs["input"], payload)
                run.side_effect = None

    def test_browser_markup_matches_inir_without_altering_code(self):
        with TempEnv():
            payload = b'<meta http-equiv="content-type" content="text/html; charset=utf-8"><div>A &amp; B</div><p>C</p>'
            self.assertEqual(clipboard.clean_text(payload), b"A & B\nC")
            self.assertEqual(clipboard.clean_text(b'<html><body><!--StartFragment--><b>Hello</b><!--EndFragment--></body></html>'), b"Hello")
            self.assertEqual(clipboard.clean_text(b'<div>ordinary code</div>\n'), b'<div>ordinary code</div>\n')

    def test_cancel_invalid_index_and_failed_decode_never_change_clipboard(self):
        with TempEnv(), patch.object(clipboard.subprocess, "run") as run:
            for choice in (Mock(returncode=1, stdout=b""), Mock(returncode=0, stdout=b"99\n")):
                run.side_effect = [Mock(returncode=0, stdout=b"1\ttext\n"), choice]
                if choice.returncode:
                    self.assertEqual(clipboard.pick(), 0)
                else:
                    with self.assertRaises(ValueError):
                        clipboard.pick()
                self.assertEqual(run.call_count, 2)
                run.reset_mock()
            run.side_effect = [Mock(returncode=0, stdout=b"1\ttext\n"), Mock(returncode=0, stdout=b"0\n"),
                               subprocess.CalledProcessError(1, ["cliphist", "decode"])]
            with self.assertRaises(subprocess.CalledProcessError):
                clipboard.pick()
            self.assertEqual(run.call_count, 3)

    def test_sensitive_and_empty_events_are_not_stored(self):
        with TempEnv(), patch.object(clipboard.subprocess, "run") as run:
            for state in ("nil", "clear", "sensitive"):
                with patch.dict(os.environ, CLIPBOARD_STATE=state):
                    self.assertEqual(clipboard.store("text", b"private"), 0)
            self.assertEqual(clipboard.store("text", b""), 0)
            run.assert_not_called()

    def test_watch_arguments_failure_and_cleanup_own_only_private_workers(self):
        with TempEnv(), patch.object(clipboard.subprocess, "Popen") as spawn, \
             patch.object(clipboard.os, "killpg") as kill, patch.object(clipboard.threading, "Event") as event:
            workers = [Mock(pid=111, poll=Mock(return_value=1)),
                       Mock(pid=112, poll=Mock(return_value=None)), Mock(pid=113, poll=Mock(return_value=None))]
            spawn.side_effect = workers
            event.return_value.wait.return_value = False
            self.assertEqual(clipboard.watch(), 1)
            script = str(Path(clipboard.__file__).resolve())
            self.assertEqual([call.args[0] for call in spawn.call_args_list], [
                ["wl-paste", "--no-newline", "--type", "text", "--watch", sys.executable, script, "store-text"],
                ["wl-paste", "--type", "image", "--watch", sys.executable, script, "store-image"],
                ["wl-clip-persist", "--clipboard", "both"]])
            for call in spawn.call_args_list:
                self.assertTrue(call.kwargs["start_new_session"])
            self.assertEqual(kill.call_args_list, [((pid, signal.SIGTERM),) for pid in (111, 112, 113)])
            for worker in workers:
                worker.wait.assert_called_once_with(timeout=3)

    def test_partial_startup_failure_cleans_already_started_workers(self):
        with TempEnv(), patch.object(clipboard.subprocess, "Popen", side_effect=[Mock(pid=111), OSError()]), \
             patch.object(clipboard.os, "killpg") as kill:
            with self.assertRaises(OSError):
                clipboard.watch()
            kill.assert_called_once_with(111, signal.SIGTERM)

    def test_second_invocation_does_not_open_a_duplicate_picker(self):
        import fcntl
        with TempEnv() as ctx, patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home)), \
             patch.object(clipboard.subprocess, "run") as run:
            lock = ctx.home / "nyxuri-clipboard-pick.lock"
            with lock.open("a") as owner:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(clipboard.main(["pick"]), 0)
            self.assertTrue(lock.exists())
            run.assert_not_called()

    def test_redeployment_preserves_shared_history_and_installs_private_service(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            originals = {}
            for name in (".cache/cliphist/db", ".config/cliphist/config", ".config/niri/config.kdl", ".config/hypr/hyprland/execs.lua"):
                target = ctx.home / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"unchanged shared data\0")
                originals[target] = target.read_bytes()
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), \
                 patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                for _ in range(2):
                    self.assertEqual(install.main(["--yes"]), 0)
            private = ctx.home / ".config/nyxuri-desktop"
            action = (private / "niri/scripts/shell-action.sh").read_text()
            self.assertIn('exec python3 "$(dirname "$0")/clipboard.py" pick', action)
            self.assertNotIn("panel-toggle clipboard", action)
            import tomllib
            self.assertFalse(tomllib.loads((private / "noctalia/zz-personal.toml").read_text())["shell"]["clipboard_enabled"])
            unit = ctx.home / ".config/systemd/user/nyxuri-clipboard.service"
            self.assertFalse(unit.is_symlink())
            self.assertIn("BindsTo=nyxuri-niri.service", unit.read_text())
            self.assertIn("After=nyxuri-niri.service nyxuri-shell.service", unit.read_text())
            self.assertNotIn("[Install]", unit.read_text())
            self.assertIn("nyxuri-clipboard.service", (unit.with_name("nyxuri-niri.service")).read_text())
            for name in ("clipboard.py", "clipboard-fuzzel.ini"):
                deployed = private / "niri/scripts" / name
                self.assertFalse(deployed.is_symlink())
                self.assertEqual(deployed.read_bytes(), (install.ROOT / "personal" / name).read_bytes())
            for path, data in originals.items():
                self.assertEqual(path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
