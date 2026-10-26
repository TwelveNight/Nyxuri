"""Personal shortcuts and XDG startup stay separate from upstream defaults."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from tests.utils import TempEnv
from personal import install, niri_actions, autostart, runtime


class PersonalPreferencesTests(unittest.TestCase):
    def test_super_shift_r_toggles_the_existing_recorder_plugin(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            binds = (source / "niri/75-personal-binds.kdl").read_text()
            self.assertIn('Mod+Shift+R repeat=false hotkey-overlay-title="Toggle screen recording" { spawn "noctalia" "msg" "plugin" "noctalia/screen_recorder:service" "all" "toggle"; }', binds)
            self.assertIn('// #"录屏"\n    Mod+Shift+R ', binds)
            config = (source / "niri/config.kdl").read_text()
            self.assertLess(config.index('include "binds.kdl"'), config.index('include "75-personal-binds.kdl"'))
            self.assertIn('Mod+Shift+X repeat=false hotkey-overlay-title="Recognize screen text"', binds)

    def test_shortcut_toggle_is_nonrepeating_and_always_reachable(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            binds = (source / "niri/75-personal-binds.kdl").read_text()
            line = next(line for line in binds.splitlines() if "Mod+Escape " in line)
            self.assertIn("repeat=false allow-inhibiting=false", line)
            self.assertIn('spawn "~/.local/libexec/win-shortcuts/control.py" "toggle"', line)

    def test_personal_keys_load_between_upstream_and_user_customs(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            config = (source / "niri/config.kdl").read_text()
            self.assertLess(config.index('include "binds.kdl"'), config.index('include "personal-binds.kdl"'))
            self.assertLess(config.index('include "personal-binds.kdl"'), config.index('include "__custom__.kdl"'))
            self.assertNotIn('spawn-at-startup "~/.config/niri/scripts/session-shell.sh"', config)
            self.assertNotIn('exec fcitx5 -d', config)
            binds = (source / "niri/personal-binds.kdl").read_text()
            self.assertNotIn('INIR_', binds)
            self.assertNotIn('/bin/inir', binds)
            self.assertIn('Mod+N repeat=false hotkey-overlay-title="Next workspace" { focus-workspace-down;', binds)
            self.assertIn('Alt+N hotkey-overlay-title="Focus right" { focus-column-or-monitor-right;', binds)
            for arrow, letter, direction, action in (
                ("Left", "H", "left", "focus-column-or-monitor-left"),
                ("Right", "L", "right", "focus-column-or-monitor-right"),
                ("Up", "K", "up", "focus-window-or-monitor-up"),
                ("Down", "J", "down", "focus-window-or-monitor-down"),
            ):
                for key in (arrow, letter):
                    self.assertIn(f'Alt+{key} hotkey-overlay-title="Focus {direction}" {{ {action}; }}', binds)
            self.assertIn('screenshot-annotate', binds)
            self.assertIn('Mod+Alt+K hotkey-overlay-title="Move window to previous workspace" { move-window-to-workspace-up; }', binds)
            self.assertIn('Mod+Alt+J hotkey-overlay-title="Move window to next workspace" { move-window-to-workspace-down; }', binds)
            self.assertNotRegex(binds, r'(?m)^\s*Mod\+Alt\+[HL]\s')
            self.assertEqual(binds.count('"control-center"'), 4)
            for key, page in (("S", "home"), ("A", "audio"), ("B", "bluetooth"), ("D", "network")):
                line = next(line for line in binds.splitlines() if line.strip().startswith(f"Mod+{key} "))
                self.assertIn(f'"panel-toggle" "control-center" "{page}"', line)
            self.assertTrue((source / "noctalia/tools/orbit-launcher.py").is_file())
            self.assertTrue((source / "niri/scripts/niri-actions.py").is_file())

    def test_inir_defaults_and_free_super_x_survive_redeployment(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            upstream = (install.ROOT / "units/niri/binds.kdl").read_bytes()
            for _ in range(2):
                if (source / "niri").exists():
                    import shutil
                    shutil.rmtree(source)
                    source.mkdir()
                install.prepare_sources(source)
                config = (source / "niri/config.kdl").read_text()
                self.assertLess(config.index('include "personal-binds.kdl"'), config.index('include "75-personal-binds.kdl"'))
                self.assertLess(config.index('include "75-personal-binds.kdl"'), config.index('include "__custom__.kdl"'))
                defaults = (source / "niri/binds.kdl").read_text()
                self.assertNotRegex(defaults, r'(?m)^\s*Mod\+X\s')
                binds = (source / "niri/75-personal-binds.kdl").read_text()
                self.assertIn('Mod+C { center-column; }', binds)
                self.assertIn('Alt+C { center-column; }', binds)
                self.assertIn('Mod+R { switch-preset-column-width; }', binds)
                self.assertIn('Mod+Ctrl+Left { focus-monitor-left; }', binds)
                for key, action in (("Left", "move-column-left"), ("Right", "move-column-right"),
                                    ("Up", "move-window-up"), ("Down", "move-window-down")):
                    self.assertIn(f'Mod+{key} {{ {action}; }}', binds)
                self.assertIn('Alt+Tab { next-window; }', binds)
                self.assertIn('Mod+Ctrl+9 { move-column-to-workspace 9; }', binds)
                self.assertIn('Mod+Alt+Delete repeat=false hotkey-overlay-title="Power menu" { spawn "noctalia" "msg" "panel-toggle" "session";', binds)
                self.assertIn('Alt+Space repeat=false hotkey-overlay-title="Search" { spawn "~/.config/niri/scripts/launcher.py";', binds)
            self.assertEqual((install.ROOT / "units/niri/binds.kdl").read_bytes(), upstream)

    def test_xdg_entries_keep_user_changes_and_disable_todesk(self):
        with TempEnv() as ctx:
            config = ctx.home / ".config"
            kitty = config / "kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text('shell zsh\n')
            apps = config / "autostart"
            apps.mkdir()
            password = apps / "com.onepassword.OnePassword.desktop"
            original = '[Desktop Entry]\nType=Application\nName=1Password\nHidden=true\nExec=my-custom-launcher\n'
            password.write_text(original)
            todesk = apps / "todesk.desktop"
            todesk.write_text('[Desktop Entry]\nType=Application\nName=ToDesk\nExec=my-custom-todesk\nHidden=false\n')
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
            self.assertEqual(password.read_text(), original)
            self.assertIn('Exec=my-custom-todesk\n', todesk.read_text())
            self.assertIn('Hidden=true\n', todesk.read_text())
            self.assertIn('X-GNOME-Autostart-enabled=false\n', todesk.read_text())
            self.assertEqual(autostart.disabled_entry(todesk.read_text()), todesk.read_text())
            self.assertTrue((apps / "clash-verge.desktop").is_file())
            order = config / "systemd/user" / (install.AUTOSTART_UNITS[0] + ".d/50-nyxuri-shell.conf")
            self.assertIn('After=nyxuri-shell.service', order.read_text())
            self.assertNotIn('Wants=', order.read_text())
            shell = (config / "systemd/user/nyxuri-shell.service").read_text()
            self.assertIn('Type=notify\nNotifyAccess=all', shell)
            self.assertNotIn('BusName=', shell)
            self.assertIn('PartOf=nyxuri-niri.service', shell)
            self.assertNotIn('Before=graphical-session.target', shell)

    def test_todesk_disable_changes_only_desktop_entry(self):
        with TempEnv():
            text = '[Desktop Entry]\nName=ToDesk\nHidden=false\n[Other]\nHidden=false\n'
            disabled = autostart.disabled_entry(text)
            self.assertIn('[Other]\nHidden=false\n', disabled)
            self.assertEqual(disabled, autostart.disabled_entry(disabled))


class PersonalTrayReadinessTests(unittest.TestCase):
    def test_only_current_shell_owner_reports_ready(self):
        shell = Mock(pid=123, poll=Mock(return_value=None))
        replies = [Mock(returncode=0, stdout='{"data": [999]}'),
                   Mock(returncode=0, stdout='{"data": [123]}'),
                   Mock(returncode=0, stdout='{"locked": false}'), Mock(returncode=0)]
        with TempEnv(), patch.dict(os.environ, NOTIFY_SOCKET="/tmp/test-notify"), patch.object(runtime.subprocess, "run", side_effect=replies) as run, patch.object(runtime.time, "sleep") as sleep:
            runtime.wait_for_tray(shell)
            command = ["busctl", "--user", "--json=short", "--timeout=1", "call",
                       "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                       "GetConnectionUnixProcessID", "s", "org.kde.StatusNotifierWatcher"]
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                command, command, ["noctalia", "msg", "status"],
                ["systemd-notify", "--ready", "--status=Noctalia tray ready"]])
            self.assertEqual(run.call_args_list[0].kwargs, dict(capture_output=True, text=True, timeout=2, check=False))
            self.assertEqual(run.call_args_list[-1].kwargs, dict(check=True))
            sleep.assert_called_once_with(0.1)

    def test_tray_owner_does_not_report_ready_before_ipc(self):
        shell = Mock(pid=123, poll=Mock(return_value=None))
        replies = [Mock(returncode=0, stdout='{"data": [123]}'),
                   Mock(returncode=1, stdout=""),
                   Mock(returncode=0, stdout='{"data": [123]}'),
                   Mock(returncode=0, stdout='{"locked": false}'), Mock(returncode=0)]
        with TempEnv(), patch.dict(os.environ, NOTIFY_SOCKET="/tmp/test-notify"), patch.object(runtime.subprocess, "run", side_effect=replies) as run, patch.object(runtime.time, "sleep") as sleep:
            runtime.wait_for_tray(shell)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[1], ["noctalia", "msg", "status"])
            self.assertEqual(commands[3], ["noctalia", "msg", "status"])
            self.assertEqual(commands[4][0], "systemd-notify")
            self.assertEqual(run.call_args_list[1].kwargs,
                             dict(capture_output=True, text=True, timeout=2, check=False))
            sleep.assert_called_once_with(0.1)

    def test_wrong_owner_times_out_without_notifying(self):
        shell = Mock(pid=123, poll=Mock(return_value=None))
        with TempEnv(), patch.object(runtime.subprocess, "run", return_value=Mock(returncode=0, stdout='{"data": [999]}')) as run:
            with self.assertRaisesRegex(RuntimeError, "did not acquire"):
                runtime.wait_for_tray(shell, timeout=0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], "busctl")

    def test_shell_exit_does_not_query_or_notify(self):
        with TempEnv(), patch.object(runtime.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "exited"):
                runtime.wait_for_tray(Mock(poll=Mock(return_value=1)))
            run.assert_not_called()


class PersonalNiriActionsTests(unittest.TestCase):
    def test_query_and_action_use_niri_argument_arrays(self):
        with TempEnv(), patch.object(niri_actions.subprocess, "check_output", return_value='[]') as query, patch.object(niri_actions.subprocess, "run") as run:
            self.assertEqual(niri_actions.query("windows"), [])
            self.assertEqual(query.call_args.args[0], ["niri", "msg", "--json", "windows"])
            niri_actions.action("focus-window", "--id", 12)
            self.assertEqual(run.call_args.args[0], ["niri", "msg", "action", "focus-window", "--id", "12"])

    def test_centered_float_keeps_target_window_id(self):
        with TempEnv(), patch.object(niri_actions, "query", return_value={"id": 71, "is_floating": False}), patch.object(niri_actions.subprocess, "run") as run:
            niri_actions.toggle_float()
            self.assertEqual([c.args[0] for c in run.call_args_list], [
                ["niri", "msg", "action", "move-window-to-floating", "--id", "71"],
                ["niri", "msg", "action", "set-window-width", "--id", "71", "50%"],
                ["niri", "msg", "action", "set-window-height", "--id", "71", "60%"],
                ["niri", "msg", "action", "center-window", "--id", "71"],
            ])

    def test_empty_workspace_uses_stable_id_on_focused_output(self):
        replies = {"workspaces": [{"id": 11, "idx": 1, "output": "DP-1", "is_focused": True}, {"id": 17, "idx": 3, "output": "DP-1"}, {"id": 90, "idx": 9, "output": "DP-2"}], "windows": [{"id": 71, "workspace_id": 11}], "focused-window": {"id": 71}}
        with TempEnv(), patch.object(niri_actions, "query", side_effect=lambda name: replies[name]), patch.object(niri_actions, "request_action") as send:
            niri_actions.empty_workspace(True)
            send.assert_called_once_with({"MoveWindowToWorkspace": {"window_id": 71, "reference": {"Id": 17}, "focus": True}})
            replies["windows"].append({"id": 72, "workspace_id": 17})
            with self.assertRaises(RuntimeError):
                niri_actions.empty_workspace(True)
            self.assertEqual(send.call_count, 1)

    def test_ipc_request_shape_and_error_response(self):
        peer = Mock()
        peer.makefile.return_value.__enter__ = Mock(return_value=Mock(readline=Mock(return_value='{"Ok": {}}')))
        peer.makefile.return_value.__exit__ = Mock(return_value=None)
        connection = Mock()
        connection.__enter__ = Mock(return_value=peer)
        connection.__exit__ = Mock(return_value=None)
        with TempEnv(), patch.dict(os.environ, NIRI_SOCKET="/tmp/test-niri.sock"), patch.object(niri_actions.socket, "socket", return_value=connection):
            request = {"FocusWorkspace": {"reference": {"Id": 17}}}
            niri_actions.request_action(request)
            self.assertEqual(peer.connect.call_args.args, ("/tmp/test-niri.sock",))
            self.assertEqual(json.loads(peer.sendall.call_args.args[0]), {"Action": request})
            peer.makefile.return_value.__enter__.return_value.readline.return_value = '{"Err": "rejected"}'
            with self.assertRaises(RuntimeError):
                niri_actions.request_action(request)

    def test_tmux_attaches_without_inir_runtime(self):
        with TempEnv(), patch.object(niri_actions.subprocess, "run", return_value=Mock(returncode=0)) as run, patch.object(niri_actions.os, "execvp") as execute:
            niri_actions.main("tmux")
            self.assertEqual(run.call_args.args[0], ["tmux", "has-session"])
            execute.assert_called_once_with("kitty", ["kitty", "tmux", "attach-session"])


if __name__ == "__main__":
    unittest.main()
