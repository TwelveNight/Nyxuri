"""Folia keeps playing when Super+Q hides its owned tray window."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest.mock import patch
from personal import niri_actions as actions
from personal import install
from tests.utils import TempEnv


class FoliaCloseTests(unittest.TestCase):
    window = {"id": 20, "app_id": "folia-major", "pid": 12081, "title": "Folia"}
    service = "org.freedesktop.StatusNotifierItem-12081-1"

    def test_void_dbus_reply_is_success(self):
        with TempEnv(), patch.object(actions.subprocess, "check_output", return_value=""):
            self.assertEqual(actions.bus_call("call", "fixture", "/menu", "fixture", "Event"), [])

    def run_hide(self, label="隐藏窗口", owner_pid=12081, enabled=True, windows=None):
        calls = []

        def reply(command, **kwargs):
            calls.append(command)
            if command[0] == "niri":
                return json.dumps([self.window] if windows is None else windows)
            if "ListNames" in command:
                result = [[self.service]]
            elif "GetNameOwner" in command:
                result = [":1.486"]
            elif "GetConnectionUnixProcessID" in command:
                result = [owner_pid]
            elif "get-property" in command:
                result = "/org/chromium/DbusMenu"
            elif "GetLayout" in command:
                item = {"type": "(ia{sv}av)", "data": [589, {
                    "label": {"type": "s", "data": label},
                    "enabled": {"type": "b", "data": enabled},
                }, []]}
                result = [42, [0, {}, [item]]]
            elif "Event" in command:
                result = []
            else:
                raise AssertionError(command)
            return json.dumps({"data": result})

        with TempEnv(), patch.object(actions.subprocess, "check_output", side_effect=reply):
            actions.hide_folia("20")
        return calls

    def test_hide_invokes_owned_tray_item_not_close_or_quit(self):
        calls = self.run_hide()
        event = next(c for c in calls if "Event" in c)
        self.assertEqual(event[-6:], ["isvu", "589", "clicked", "s", "", "0"])
        self.assertIn(":1.486", event)
        self.assertFalse(any("close-window" in c or "Quit" in c for c in calls))

    def test_repeated_hide_does_not_show_the_window(self):
        self.assertFalse(any("Event" in c for c in self.run_hide(label="显示窗口")))

    def test_missing_hide_item_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.run_hide(label="退出")

    def test_disabled_hide_item_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.run_hide(enabled=False)

    def test_wrong_tray_owner_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_hide(owner_pid=999)

    def test_closed_window_is_noop(self):
        self.assertEqual(len(self.run_hide(windows=[])), 1)

    def test_remote_control_window_is_not_hidden(self):
        with self.assertRaises(RuntimeError):
            self.run_hide(windows=[dict(self.window, title="Folia Remote")])


class CloseWindowTests(unittest.TestCase):
    def test_other_app_closes_captured_id(self):
        with TempEnv(), patch.object(actions.subprocess, "check_output", return_value='{"id": 42, "app_id": "kitty"}') as query, patch.object(actions.subprocess, "run") as run:
            actions.main("close")
        query.assert_called_once_with(["niri", "msg", "--json", "focused-window"], text=True)
        run.assert_called_once_with(["niri", "msg", "action", "close-window", "--id", "42"], check=True)

    def test_folia_tray_failure_never_closes_window(self):
        with TempEnv(), patch.object(actions, "query", return_value={"id": 20, "app_id": "folia-major", "title": "Folia"}), patch.object(actions, "hide_folia", side_effect=RuntimeError("no tray")) as hide, patch.object(actions.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                actions.main("close")
            hide.assert_called_once_with(20)
            run.assert_not_called()

    def test_no_focus_does_nothing(self):
        with TempEnv(), patch.object(actions, "query", return_value=None), patch.object(actions.subprocess, "run") as run:
            actions.main("close")
            run.assert_not_called()

    def test_folia_other_window_closes_normally(self):
        with TempEnv(), patch.object(actions, "query", return_value={"id": 21, "app_id": "folia-major", "title": "Folia Remote"}), patch.object(actions.subprocess, "run") as run:
            actions.main("close")
        run.assert_called_once_with(["niri", "msg", "action", "close-window", "--id", "21"], check=True)

    def test_both_bindings_launch_executable_and_close_other_app(self):
        with TempEnv() as ctx:
            sources = ctx.home / "sources"
            sources.mkdir()
            install.prepare_sources(sources)
            commands = []
            for filename, chord in [("75-personal-binds.kdl", "Mod+Q"), ("personal-binds.kdl", "Alt+Q")]:
                line = next(line for line in (sources / "niri" / filename).read_text().splitlines() if re.match(r"\s*" + re.escape(chord) + r"\s", line))
                self.assertIn("repeat=false allow-inhibiting=false", line)
                commands.append(re.findall(r'spawn "([^"\n]+)" "([^"\n]+)"', line)[0])
            self.assertEqual(commands[0], commands[1])
            tools = ctx.home / "bin"
            tools.mkdir()
            log = ctx.home / "calls.jsonl"
            niri = tools / "niri"
            niri.write_text("#!/usr/bin/env python3\nimport json,os,sys\nwith open(os.environ['ACTION_LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\nif sys.argv[1:]==['msg','--json','focused-window']: print(json.dumps({'id':42,'app_id':'kitty'}))\n")
            niri.chmod(0o755)
            script = sources / "niri/scripts/niri-actions.py"
            self.assertTrue(os.access(script, os.X_OK))
            env = os.environ.copy()
            env.update(PATH=str(tools) + os.pathsep + env['PATH'], ACTION_LOG=str(log))
            for _, command in commands:
                subprocess.run([str(script), command], env=env, check=True, capture_output=True, text=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(calls, [["msg", "--json", "focused-window"], ["msg", "action", "close-window", "--id", "42"]] * 2)
