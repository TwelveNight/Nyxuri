"""Screen search follows SekaiPop's temporary-host Google Lens workflow."""
import json
import subprocess
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class ScreenSearchTests(unittest.TestCase):
    def test_deployment_overrides_screenshot_chord_and_installs_helper(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            upstream = (install.ROOT / "units/niri/binds.kdl").read_bytes()
            install.prepare_sources(source)
            binds = (source / "niri/75-personal-binds.kdl").read_text()
            self.assertIn('Mod+Shift+S repeat=false hotkey-overlay-title="Search screenshot with Google Lens" { spawn "~/.config/niri/scripts/screen_search.py"; }', binds)
            self.assertIn('// #"截图"\n    Mod+Shift+S ', binds)
            self.assertEqual((source / "niri/scripts/screen_search.py").read_bytes(),
                             (install.ROOT / "personal/screen_search.py").read_bytes())
            self.assertEqual((install.ROOT / "units/niri/binds.kdl").read_bytes(), upstream)

    def test_selected_png_uses_sekaipop_host_and_browser_lens_import(self):
        from personal import screen_search
        image_url = "https://n.uguu.se/example.png"
        url = "https://lens.google.com/uploadbyurl?" + urlencode({"url": image_url})
        results = [subprocess.CompletedProcess([], 0, "10,20 300x100\n", ""),
                   subprocess.CompletedProcess([], 0, b"selected png", b""),
                   subprocess.CompletedProcess([], 0, json.dumps({"success": True, "files": [{"url": image_url}]}).encode(), b""),
                   subprocess.CompletedProcess([], 0)]
        with TempEnv(), patch.object(screen_search.shutil, "which", return_value="/usr/bin/tool"), \
                patch.object(screen_search.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_search.main(), 0)
        calls = run.call_args_list
        self.assertEqual(calls[0].args[0], ["slurp"])
        self.assertEqual(calls[1].args[0], ["grim", "-g", "10,20 300x100", "-"])
        self.assertEqual(calls[2].args[0], ["curl", "--silent", "--show-error", "--fail",
                         "--connect-timeout", "10", "--max-time", "45", "--form",
                         "files[]=@-;filename=screenshot.png;type=image/png",
                         "https://uguu.se/upload"])
        self.assertEqual(calls[2].kwargs["input"], b"selected png")
        self.assertEqual(calls[3].args[0], ["xdg-open", url])

    def test_cancel_never_captures_uploads_or_opens_browser(self):
        from personal import screen_search
        with TempEnv(), patch.object(screen_search.shutil, "which", return_value="/usr/bin/tool"), \
                patch.object(screen_search.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")) as run:
            self.assertEqual(screen_search.main(), 0)
        self.assertEqual([call.args[0] for call in run.call_args_list], [["slurp"]])

    def test_upload_failure_or_invalid_host_response_never_opens_browser(self):
        from personal import screen_search
        failures = [subprocess.CalledProcessError(22, ["curl"], stderr=b"private content"),
                    subprocess.TimeoutExpired(["curl"], 55),
                    subprocess.CompletedProcess([], 0, b"not json", b"")]
        for payload in ({"success": False}, {"success": True, "files": []},
                        {"success": True, "files": [{"url": None}]},
                        {"success": True, "files": [{"url": "https://untrusted.example/image.png"}]},
                        {"success": True, "files": [{"url": "http://n.uguu.se/image.png"}]},
                        {"success": True, "files": [{"url": "https://n.uguu.se@untrusted.example/image.png"}]}):
            failures.append(subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b""))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), TempEnv(), \
                    patch.object(screen_search.shutil, "which", return_value="/usr/bin/tool"), \
                    patch.object(screen_search.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, "0,0 10x10", ""),
                        subprocess.CompletedProcess([], 0, b"png", b""), failure,
                        subprocess.CompletedProcess([], 0)]) as run:
                self.assertEqual(screen_search.main(), 1)
            self.assertNotIn("xdg-open", [call.args[0][0] for call in run.call_args_list])
            self.assertEqual(run.call_args.args[0][0], "notify-send")
            self.assertNotIn("private content", run.call_args.args[0][-1])
