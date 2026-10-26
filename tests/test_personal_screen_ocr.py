"""Screen OCR stays in the personal overlay and never logs recognized text."""
import subprocess
import unittest
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class ScreenOCRTests(unittest.TestCase):
    def test_deployment_binds_screen_ocr_and_keeps_annotation_shortcut(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            binds = (source / "niri/75-personal-binds.kdl").read_text()
            self.assertIn('Mod+Shift+X repeat=false hotkey-overlay-title="Recognize screen text" { spawn "~/.config/niri/scripts/screen_ocr.py"; }', binds)
            self.assertIn('Mod+Shift+A { spawn "noctalia" "msg" "screenshot-annotate"; }', binds)
            self.assertIn('// #"截图"\n    Mod+Shift+X ', binds)
            helper = source / "niri/scripts/screen_ocr.py"
            self.assertEqual(helper.read_bytes(), (install.ROOT / "personal/screen_ocr.py").read_bytes())

    def test_selected_region_is_recognized_locally_and_copied_as_utf8(self):
        from personal import screen_ocr
        text = "屏幕文字 Nyxuri\n第二行"
        results = [
            subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, 'List of available languages in "/tessdata/" (3):\neng\nosd\nchi_sim\n', ""),
            subprocess.CompletedProcess(["slurp"], 0, "10,20 300x100\n", ""),
            subprocess.CompletedProcess(["grim"], 0, b"screen png", b""),
            subprocess.CompletedProcess(["tesseract"], 0, (text + "\n").encode(), b""),
            subprocess.CompletedProcess(["wl-copy"], 0, b"", b""),
            subprocess.CompletedProcess(["notify-send"], 0),
        ]
        with TempEnv(), patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_ocr.main(), 0)
        calls = run.call_args_list
        self.assertEqual(calls[0].args[0], ["tesseract", "--list-langs"])
        self.assertEqual(calls[0].kwargs, {"capture_output": True, "text": True, "check": True, "timeout": 15})
        self.assertEqual(calls[1].args[0], ["slurp"])
        self.assertEqual(calls[2].args[0], ["grim", "-g", "10,20 300x100", "-"])
        self.assertEqual(calls[3].args[0], ["tesseract", "stdin", "stdout", "-l", "chi_sim+eng", "--psm", "11", "quiet"])
        self.assertEqual(calls[3].kwargs["input"], b"screen png")
        self.assertEqual(calls[4].args[0], ["wl-copy", "--type", "text/plain;charset=utf-8"])
        self.assertEqual(calls[4].kwargs["input"], text.encode())
        self.assertEqual(calls[5].args[0][:3], ["notify-send", "--app-name=Nyxuri", "屏幕文字识别"])
        self.assertNotIn(text, " ".join(calls[5].args[0]))

    def test_cancelling_selection_does_not_capture_or_change_clipboard(self):
        from personal import screen_ocr
        results = [subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, "chi_sim\neng\n", ""),
                   subprocess.CompletedProcess(["slurp"], 1, "", "")]
        with TempEnv(), patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_ocr.main(), 0)
        self.assertEqual([call.args[0] for call in run.call_args_list], [["tesseract", "--list-langs"], ["slurp"]])

    def test_tesseract_spaces_between_chinese_characters_are_removed(self):
        from personal import screen_ocr
        results = [subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, "chi_sim\neng\n", ""),
                   subprocess.CompletedProcess([], 0, "0,0 10x10", ""),
                   subprocess.CompletedProcess([], 0, b"png", b""),
                   subprocess.CompletedProcess([], 0, "NYXURI OCR 7319\n\n屏 幕 文 字 识 别\n".encode(), b""),
                   subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]
        with TempEnv(), patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_ocr.main(), 0)
        self.assertEqual(run.call_args_list[4].args[0], ["wl-copy", "--type", "text/plain;charset=utf-8"])
        self.assertEqual(run.call_args_list[4].kwargs["input"], "NYXURI OCR 7319\n\n屏幕文字识别".encode())

    def test_empty_recognition_leaves_clipboard_unchanged(self):
        from personal import screen_ocr
        results = [subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, "chi_sim\neng\n", ""),
                   subprocess.CompletedProcess([], 0, "0,0 10x10", ""),
                   subprocess.CompletedProcess([], 0, b"png", b""),
                   subprocess.CompletedProcess([], 0, b" \n\t", b""),
                   subprocess.CompletedProcess([], 0)]
        with TempEnv(), patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_ocr.main(), 0)
        self.assertEqual([call.args[0][0] for call in run.call_args_list], ["tesseract", "slurp", "grim", "tesseract", "notify-send"])
        self.assertIn("剪贴板未改动", run.call_args_list[-1].args[0][-1])

    def test_failed_capture_ocr_or_copy_never_reports_success(self):
        from personal import screen_ocr
        commands = ["grim", "tesseract", "wl-copy"]
        for stage, command in enumerate(commands):
            with self.subTest(command=command), TempEnv():
                results = [subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, "chi_sim\neng\n", ""),
                           subprocess.CompletedProcess([], 0, "0,0 10x10", ""),
                           *(subprocess.CompletedProcess([], 0, b"data", b"") for _ in range(stage)),
                           subprocess.CalledProcessError(1, [command], stderr=b"private content"),
                           subprocess.CompletedProcess([], 0)]
                with patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
                    self.assertEqual(screen_ocr.main(), 1)
                self.assertEqual(run.call_args_list[-2].args[0][0], command)
                self.assertEqual(run.call_args_list[-1].args[0][0], "notify-send")
                self.assertIn("失败", run.call_args_list[-1].args[0][-1])
                self.assertNotIn("private content", run.call_args_list[-1].args[0][-1])

    def test_missing_language_is_reported_before_selection_without_copying(self):
        from personal import screen_ocr
        for missing, available in (("chi_sim", "eng\nchi_sim_vert"), ("eng", "chi_sim\neng_custom")):
            with self.subTest(missing=missing), TempEnv():
                results = {
                    ("tesseract", "--list-langs"): subprocess.CompletedProcess([], 0, f'List of available languages in "/tessdata/" (3):\nosd\n{available}\n', ""),
                    ("slurp",): subprocess.CompletedProcess([], 0, "0,0 10x10", ""),
                    ("grim", "-g", "0,0 10x10", "-"): subprocess.CompletedProcess([], 0, b"png", b""),
                    ("tesseract", "stdin", "stdout", "-l", "chi_sim+eng", "--psm", "11", "quiet"): subprocess.CompletedProcess([], 0, b"fallback text", b"failed to load one language"),
                    ("wl-copy", "--type", "text/plain;charset=utf-8"): subprocess.CompletedProcess([], 0),
                }
                def result(args, **kwargs):
                    return subprocess.CompletedProcess(args, 0) if args[0] == "notify-send" else results[tuple(args)]

                with patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=result) as run:
                    self.assertEqual(screen_ocr.main(), 1)
                self.assertEqual([call.args[0] for call in run.call_args_list[:-1]], [["tesseract", "--list-langs"]])
                self.assertEqual(run.call_args_list[0].kwargs, {"capture_output": True, "text": True, "check": True, "timeout": 15})
                self.assertEqual(run.call_args.args[0][:3], ["notify-send", "--app-name=Nyxuri", "屏幕文字识别"])
                self.assertIn("失败", run.call_args.args[0][-1])
                self.assertIn("语言包", run.call_args.args[0][-1])
                self.assertIn(missing, run.call_args.args[0][-1])

    def test_language_query_failure_does_not_select_capture_or_copy(self):
        from personal import screen_ocr
        command = ["tesseract", "--list-langs"]
        for error in (subprocess.CalledProcessError(1, command, stderr="private content"),
                      subprocess.TimeoutExpired(command, 15), OSError("unavailable")):
            with self.subTest(error=type(error).__name__), TempEnv():
                with patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=[error, subprocess.CompletedProcess([], 0)]) as run:
                    self.assertEqual(screen_ocr.main(), 1)
                self.assertEqual(run.call_args_list[0].args[0], command)
                self.assertEqual(run.call_args_list[0].kwargs, {"capture_output": True, "text": True, "check": True, "timeout": 15})
                self.assertEqual([call.args[0][0] for call in run.call_args_list], ["tesseract", "notify-send"])
                self.assertEqual(run.call_args.args[0][:3], ["notify-send", "--app-name=Nyxuri", "屏幕文字识别"])
                self.assertIn("失败", run.call_args.args[0][-1])
                self.assertNotIn("private content", run.call_args.args[0][-1])

    def test_missing_tool_is_reported_before_selection(self):
        from personal import screen_ocr
        with TempEnv(), patch.object(screen_ocr.shutil, "which", side_effect=lambda name: None if name == "tesseract" else "/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run") as run:
            self.assertEqual(screen_ocr.main(), 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], "notify-send")
        self.assertIn("tesseract", run.call_args.args[0][-1])

    def test_selection_connection_failure_is_not_silently_treated_as_cancel(self):
        from personal import screen_ocr
        results = [subprocess.CompletedProcess(["tesseract", "--list-langs"], 0, "chi_sim\neng\n", ""),
                   subprocess.CompletedProcess(["slurp"], 1, "", "failed to connect to display"),
                   subprocess.CompletedProcess([], 0)]
        with TempEnv(), patch.object(screen_ocr.shutil, "which", return_value="/usr/bin/tool"), patch.object(screen_ocr.subprocess, "run", side_effect=results) as run:
            self.assertEqual(screen_ocr.main(), 1)
        self.assertEqual([call.args[0][0] for call in run.call_args_list], ["tesseract", "slurp", "notify-send"])
