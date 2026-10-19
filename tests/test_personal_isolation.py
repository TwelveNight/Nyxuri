"""Exercise deployed paths and handoffs without touching a live compositor."""
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from personal import install, runtime
from tests.utils import TempEnv


def handoff_helper():
    spec = importlib.util.spec_from_file_location("isolation_handoff", install.ROOT / "personal/desktop-session.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


class PersonalIsolationTests(unittest.TestCase):
    def test_translate_reads_private_config_for_popup_and_settings(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            upstream = install.ROOT / "configs/noctalia/tools/orbit_translate/config.py"
            original = upstream.read_bytes()
            install.prepare_sources(source)
            path = source / "noctalia/tools/orbit_translate/config.py"
            spec = importlib.util.spec_from_file_location("private_translate_config_test", path)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {spec.name: module}):
                spec.loader.exec_module(module)
            for config_root in (ctx.home / ".config", ctx.home / "alternate-config"):
                with self.subTest(config_root=config_root), patch.dict(os.environ, XDG_CONFIG_HOME=str(config_root)):
                    private = config_root / "nyxuri-desktop/noctalia/tools/orbit-translate__custom__.toml"
                    private.parent.mkdir(parents=True, exist_ok=True)
                    private.write_text('source = "auto"\ntarget = "zh-CN"\n')
                    public = config_root / "noctalia/tools/orbit-translate__custom__.toml"
                    public.parent.mkdir(parents=True, exist_ok=True)
                    public.write_text('source = "en"\ntarget = "fr"\n')
                    self.assertEqual(module.config_path(), private)
                    self.assertEqual(module.load_config().source, "auto")
                    self.assertEqual(module.load_config().target, "zh-CN")
            self.assertEqual(upstream.read_bytes(), original)

    def test_overview_uses_skwd_renderers_without_moving_picker_or_shell(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            original = (install.ROOT / "configs/niri/config.kdl").read_bytes()
            install.prepare_sources(source)
            config = (source / "niri/config.kdl").read_text()
            overview = (source / "niri/personal-overview.kdl").read_text()
            self.assertLess(config.index('include "personal-overview.kdl"'),
                            config.index('include "__custom__.kdl"'))
            self.assertIn('backdrop-color "transparent"', overview)
            self.assertIn('zoom 0.75', overview)
            self.assertRegex(overview, r'workspace-shadow\s*\{\s*on\s*\}')
            self.assertRegex(overview, r'overview-open-close\s*\{\s*spring damping-ratio=1\.0 stiffness=900 epsilon=0\.0001')
            self.assertIn('place-within-backdrop true', overview)
            namespace = re.search(r'match namespace="([^"]+)"', overview).group(1)
            for renderer in ("skwd-paper", "skwd-wall-vk", "skwd-wall-still"):
                self.assertRegex(renderer, namespace)
            for surface in ("skwd-wall-v2", "skwd-paper-picker", "noctalia-wallpaper", "mpvpaper", "noctalia-bar-bar", "noctalia-dock"):
                self.assertNotRegex(surface, namespace)
            self.assertEqual((install.ROOT / "configs/niri/config.kdl").read_bytes(), original)

    def test_deployed_launchers_ignore_public_tools_and_legacy_shell_selection(self):
        with TempEnv() as ctx:
            private = ctx.home / ".config/nyxuri-desktop"
            private.mkdir()
            install.prepare_sources(private)
            public = ctx.home / ".config/noctalia/tools"
            public.mkdir(parents=True)
            for name in ("orbit-launcher.py", "wallpaper-picker.py"):
                for directory, label in ((public, "public"), (private / "noctalia/tools", "private")):
                    tool = directory / name
                    tool.write_text('#!/usr/bin/env python3\nprint(' + repr(label) + ')\n')
                    tool.chmod(0o755)
            trap = ctx.home / "wrong-shell"
            trap.write_text('#!/bin/sh\necho wrong-shell\n')
            trap.chmod(0o755)
            (ctx.home / ".local/state/nyxuri/state.json").write_text(json.dumps({"active_shell": "custom", "custom_shell_bin": str(trap)}))
            commands = [["bash", str(private / "niri/scripts/shell-action.sh"), action]
                        for action in ("radial-launcher", "wallpaper-picker")]
            commands.append([sys.executable, str(private / "niri/scripts/niri-scratch-menu.py")])
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "private")

    def test_generated_cache_and_brightness_paths_are_private(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            brightness = (source / "niri/scripts/niri-brightness.sh").read_text()
            self.assertIn('$HOME/.config/nyxuri-desktop/noctalia/noctalia-config.toml', brightness)
            for name in ("noctalia/noctalia-config.toml", "noctalia/tools/orbit/palette.py", "noctalia/tools/wallpaper_picker/theme.py", "noctalia/tools/wallpaper_picker/config.py"):
                text = (source / name).read_text()
                self.assertIn(".cache/nyxuri-desktop/", text)
                self.assertNotIn(".cache/nyxuri/", text)
                self.assertNotIn(".cache/nyxniri/", text)
            self.assertNotIn('[theme.templates.user.palette]\nenabled = false', (source / "noctalia/zz-personal.toml").read_text())

    def test_brightness_reads_private_ddc_policy_instead_of_public_config(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            binaries = ctx.home / "bin"
            binaries.mkdir()
            commands = {
                "noctalia": 'exit 0\n',
                "niri": 'printf "Output (HDMI-A-1)\\n"\n',
                "ddcutil": 'printf "%s\\n" "$*" >> "$HOME/ddc-calls"\n',
            }
            for name, body in commands.items():
                tool = binaries / name
                tool.write_text("#!/bin/sh\n" + body)
                tool.chmod(0o755)
            backlight = ctx.home / "backlight"
            backlight.mkdir()
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.defpath,
                               NYXURI_BACKLIGHT_DIR=str(backlight))
            private = ctx.home / ".config/nyxuri-desktop/noctalia/noctalia-config.toml"
            public = ctx.home / ".config/noctalia/noctalia-config.toml"
            for path in (private, public):
                path.parent.mkdir(parents=True, exist_ok=True)
            for private_enabled in (True, False):
                private.write_text(f"[brightness]\nenable_ddcutil = {str(private_enabled).lower()}\n")
                public.write_text(f"[brightness]\nenable_ddcutil = {str(not private_enabled).lower()}\n")
                result = subprocess.run(["/bin/bash", str(source / "niri/scripts/niri-brightness.sh"), "up"],
                                        env=environment, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = ctx.home / "ddc-calls"
                if private_enabled:
                    # Noctalia already adjusts DDC; never apply a second step.
                    self.assertFalse(calls.exists())
                else:
                    self.assertEqual(calls.read_text(), "setvcp 10 + 10\n")

    def test_noctalia_children_inherit_private_kitty_and_wayland_input_policy(self):
        shell = Mock(poll=Mock(return_value=0), wait=Mock(return_value=0))
        bridge = Mock(poll=Mock(return_value=0))
        inherited = []
        def spawn(command, **kwargs):
            inherited.append(dict(os.environ))
            return shell if command == ["noctalia"] else bridge
        with TempEnv() as ctx, patch.dict(os.environ, KITTY_CONFIG_DIRECTORY="/old/kitty", XMODIFIERS="@im=ibus", GTK_IM_MODULE="ibus", QT_IM_MODULE="ibus", SDL_IM_MODULE="ibus"), patch.object(runtime.subprocess, "run") as run, patch.object(runtime.subprocess, "Popen", side_effect=spawn), patch.object(runtime, "wait_for_tray"):
            self.assertEqual(runtime.main(), 0)
            self.assertEqual(inherited[0]["KITTY_CONFIG_DIRECTORY"], str(ctx.home / ".config/nyxuri-desktop/kitty-nyxuri"))
            self.assertEqual(inherited[0]["NOCTALIA_CONFIG_HOME"], str(ctx.home / ".config/nyxuri-desktop"))
            self.assertEqual(inherited[0]["NOCTALIA_STATE_HOME"], str(ctx.home / ".local/state/nyxuri-desktop/noctalia"))
            self.assertEqual(len(inherited), 2)
            for environment in inherited:
                self.assertEqual(environment["XMODIFIERS"], "@im=fcitx")
                for name in ("GTK_IM_MODULE", "QT_IM_MODULE", "SDL_IM_MODULE"):
                    self.assertNotIn(name, environment)
            run.assert_called_once_with([sys.executable, str(install.ROOT / "personal/desktop-session.py"), "start", "niri", "--no-ii-theme"], check=True)

    def test_no_ii_theme_stops_writer_before_wallpaper_restart_and_default_restores_it(self):
        helper = handoff_helper()
        for no_ii in (True, False):
            with self.subTest(nyxuri=no_ii), TempEnv() as ctx:
                (ctx.home / "run").mkdir()
                hook = ctx.home / ".config/quickshell/ii/scripts/colors/skwd-wall-theme-listener.sh"
                hook.parent.mkdir(parents=True)
                hook.write_text("#!/bin/sh\n")
                identity = dict(desktop="niri", pid=os.getpid(), key="NIRI_SOCKET", value="/test.sock", wayland="wayland-test")
                args = ["desktop-session.py", "start", "niri"] + (["--no-ii-theme"] if no_ii else [])
                with patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home / "run")), patch.object(sys, "argv", args), patch.object(helper, "session_identity", return_value=identity), patch.object(helper, "unit_active", return_value=False), patch.object(helper.subprocess, "run", return_value=Mock(returncode=0, stdout="")) as run:
                    helper.main()
                commands = [tuple(call.args[0]) for call in run.call_args_list]
                stop = ("systemctl", "--user", "stop", "ii-skwd-wall-theme.service")
                start = ("systemctl", "--user", "restart", "ii-skwd-wall-theme.service")
                wall = ("systemctl", "--user", "restart", "skwd-walld.service")
                if no_ii:
                    self.assertLess(commands.index(stop), commands.index(wall))
                    self.assertNotIn(start, commands)
                else:
                    self.assertIn(start, commands)
                    self.assertNotIn(stop, commands)

    def test_no_ii_theme_stops_writer_even_for_already_active_session(self):
        helper = handoff_helper()
        with TempEnv() as ctx:
            directory = ctx.home / "run/inir"
            directory.mkdir(parents=True)
            identity = dict(desktop="niri", pid=os.getpid(), key="NIRI_SOCKET", value="/test.sock", wayland="wayland-test")
            (directory / "desktop-session.json").write_text(json.dumps(identity))
            args = ["desktop-session.py", "start", "niri", "--no-ii-theme"]
            with patch.dict(os.environ, XDG_RUNTIME_DIR=str(directory.parent)), patch.object(sys, "argv", args), patch.object(helper, "session_identity", return_value=identity), patch.object(helper, "unit_active", return_value=True), patch.object(helper.subprocess, "run", return_value=Mock(returncode=0, stdout="")) as run:
                helper.main()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands, [("systemctl", "--user", "stop", "ii-skwd-wall-theme.service")])

    def test_all_six_switch_directions_reject_stale_cleanup(self):
        helper = handoff_helper()
        sessions = {
            "ii": dict(desktop="hyprland", pid=101, key="HYPRLAND_INSTANCE_SIGNATURE", value="hypr-old", wayland="wayland-1"),
            "inir": dict(desktop="niri", pid=102, key="NIRI_SOCKET", value="/niri.102.sock", wayland="wayland-1"),
            "nyxuri": dict(desktop="niri", pid=103, key="NIRI_SOCKET", value="/niri.103.sock", wayland="wayland-1"),
        }
        with TempEnv():
            for old_name, old in sessions.items():
                for new_name, new in sessions.items():
                    if old_name == new_name:
                        continue
                    with self.subTest(old=old_name, new=new_name):
                        manager = {"XDG_CURRENT_DESKTOP": "Hyprland" if new["desktop"] == "hyprland" else "niri", new["key"]: new["value"], "WAYLAND_DISPLAY": new["wayland"]}
                        with patch.object(helper, "manager_environment", return_value=manager), patch.object(helper.subprocess, "run") as run:
                            helper.retire(old)
                        run.assert_not_called()

    def test_private_shell_clears_previous_gpu_overrides(self):
        with TempEnv():
            helper = handoff_helper()
            unit = (install.ROOT / "personal/nyxuri-shell.service").read_text()
            cleared = next(line.split("=", 1)[1].split() for line in unit.splitlines() if line.startswith("UnsetEnvironment="))
            explicit = {"__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME", "__VK_LAYER_NV_optimus"}
            self.assertTrue((set(helper.GPU) - explicit).issubset(cleared))
            self.assertTrue(explicit.isdisjoint(cleared))
            self.assertIn("Environment=__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __VK_LAYER_NV_optimus=NVIDIA_only", unit)
            self.assertNotIn("WAYLAND_DISPLAY", cleared)
            self.assertNotIn("NIRI_SOCKET", cleared)


if __name__ == "__main__":
    unittest.main()
