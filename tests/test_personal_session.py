"""The private desktop shares skwd, while preserving the existing desktops."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, Mock

from tests.utils import TempEnv
from personal import install, wallpaper, runtime, update, session


class TestPersonalSession(unittest.TestCase):
    def test_standard_install_is_blocked_after_legacy_personal_deployment(self):
        from nyxuri.cli import main
        with TempEnv() as ctx:
            marker = ctx.home / ".config/nyxuri/personal-mode"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("enabled\n")
            with patch("sys.argv", ["nyxuri", "install", "full"]), patch("nyxuri.cli.acquire_lock"), patch("nyxuri.cli.init_logger"), patch("nyxuri.cli.ensure_nyxuri_symlink"), patch("nyxuri.cli.install_configs_workflow") as workflow:
                with self.assertRaises(SystemExit) as result:
                    main()
            self.assertEqual(result.exception.code, 2)
            workflow.assert_not_called()

    def test_install_and_update_leave_inir_ii_and_portals_untouched(self):
        with TempEnv() as ctx:
            config = ctx.home / ".config"
            originals = {}
            for name in ("kitty/kitty.conf", "niri/config.kdl", "quickshell/inir/config.json", "quickshell/ii/config.json", "systemd/user/ii-skwd-wall-theme.service", "xdg-desktop-portal/niri-portals.conf"):
                target = config / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("original\n")
                originals[target] = target.read_bytes()
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
                private = config / "nyxuri-desktop"
                niri = (private / "niri/config.kdl").read_text()
                self.assertIn(str(private / "kitty-nyxuri"), niri)
                self.assertNotIn('"~/.config/niri/', niri)
                custom = private / "niri/__custom__.kdl"
                custom.write_text('// my custom binding\n')
                colors = private / "kitty-nyxuri/colors__custom__.conf"
                colors.write_text("background #123456\n")
                monitor = private / "niri/monitor.kdl"
                monitor.write_text('// my output\n')
                self.assertEqual(install.main(["--yes"]), 0)
                self.assertEqual(custom.read_text(), '// my custom binding\n')
                self.assertEqual(colors.read_text(), 'background #123456\n')
                self.assertEqual(monitor.read_text(), '// my output\n')
            for path, data in originals.items():
                self.assertEqual(path.read_bytes(), data)
            import tomllib
            conf = tomllib.loads((private / "noctalia/noctalia-config.toml").read_text())
            self.assertFalse(conf["wallpaper"]["enabled"])
            self.assertEqual(conf["plugins"]["enabled"], [])
            self.assertEqual(conf["theme"]["templates"]["user"]["nyxuri_niri_glow_material_you"]["output_path"], str(private / "niri/colors.kdl"))
            self.assertIn(str(config / "kitty/kitty.conf"), (private / "kitty-nyxuri/kitty.conf").read_text())
            self.assertFalse((config / "fish").exists())
            self.assertTrue((private / "installed").is_file())

    def test_generated_configs_pass_installed_parsers(self):
        import shutil
        if not all(shutil.which(name) for name in ("niri", "noctalia", "desktop-file-validate")):
            self.skipTest("desktop parsers are not installed")
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
            private = ctx.home / ".config/nyxuri-desktop"
            for command in (["niri", "validate", "--config", str(private / "niri/config.kdl")], ["noctalia", "config", "validate", str(private / "noctalia")], ["desktop-file-validate", str(private / "nyxuri.desktop")]):
                result = subprocess.run(command, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plan_does_not_write(self):
        with TempEnv() as ctx:
            self.assertEqual(install.main(["--plan"]), 0)
            self.assertFalse((ctx.home / ".config/nyxuri-desktop").exists())

    def test_handoff_failure_never_starts_shell_on_old_display(self):
        with TempEnv(), patch.dict(os.environ), patch("personal.runtime.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["helper"])), patch("personal.runtime.subprocess.Popen") as spawn:
            with self.assertRaises(subprocess.CalledProcessError):
                runtime.main()
            spawn.assert_not_called()

    def test_session_uses_private_unit_and_standard_shutdown(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            return Mock(returncode=1 if "is-active" in args else 0)
        with TempEnv(), patch("personal.session.subprocess.run", side_effect=run):
            self.assertEqual(session.main(), 0)
        self.assertIn(["systemctl", "--user", "--wait", "start", "nyxuri-niri.service"], calls)
        self.assertIn(["systemctl", "--user", "start", "--job-mode=replace-irreversibly", "niri-shutdown.target"], calls)
        self.assertNotIn(["systemctl", "--user", "--wait", "start", "niri.service"], calls)


class TestWallpaperBridge(unittest.TestCase):
    def test_current_supports_named_output_maps(self):
        reply = {"outputs": {"DP-1": {"path": "/a.png"}, "DP-2": {"connected": False}}}
        with TempEnv(), patch("personal.wallpaper.subprocess.run", return_value=Mock(stdout=json.dumps(reply))) as run:
            self.assertEqual(wallpaper.current(), [{"name": "DP-1", "path": "/a.png"}])
            self.assertEqual(run.call_args.args[0], ["skwd-helm", "current", "--json"])

    def test_native_hook_applies_output_with_argument_array(self):
        with TempEnv() as ctx:
            image = ctx.home / "space ; image.png"
            image.write_bytes(b"image")
            with patch.dict(os.environ, NOCTALIA_WALLPAPER_PATH=str(image), NOCTALIA_WALLPAPER_CONNECTOR="DP-1"), patch("personal.wallpaper.current", return_value=[]), patch("personal.wallpaper.subprocess.run") as run:
                wallpaper.hook()
            self.assertEqual(run.call_args.args[0], ["skwd-helm", "apply", str(image), "-o", "DP-1"])

    def test_preview_event_does_not_replace_video(self):
        with TempEnv() as ctx:
            image = ctx.home / "thumb.jpg"
            image.write_bytes(b"image")
            with patch.dict(os.environ, NOCTALIA_WALLPAPER_PATH=str(image), NOCTALIA_WALLPAPER_CONNECTOR="DP-1"), patch("personal.wallpaper.current", return_value=[{"name": "DP-1", "path": "movie.mp4"}]), patch("personal.wallpaper.preview", return_value=str(image)), patch("personal.wallpaper.subprocess.run") as run:
                wallpaper.hook()
            run.assert_not_called()

    def test_sync_updates_output_and_preserves_current_preview(self):
        with TempEnv(), patch("personal.wallpaper.current", return_value=[{"name": "DP-1"}, {"name": "DP-2"}]), patch("personal.wallpaper.preview", return_value="/preview.png"), patch("personal.wallpaper.subprocess.run", side_effect=[Mock(returncode=0, stdout="/old.png"), Mock(returncode=0), Mock(returncode=0, stdout="/preview.png")]) as run:
            wallpaper.sync()
        self.assertEqual([call.args[0] for call in run.call_args_list], [["noctalia", "msg", "wallpaper-get", "DP-1"], ["noctalia", "msg", "wallpaper-set", "DP-1", "/preview.png"], ["noctalia", "msg", "wallpaper-get", "DP-2"]])

    def test_picker_static_and_video_use_only_skwd(self):
        with TempEnv() as ctx:
            sources = ctx.home / "sources"
            sources.mkdir()
            install.prepare_sources(sources)
            spec = importlib.util.spec_from_file_location("personal_backend_test", sources / "noctalia/tools/wallpaper_picker/backend.py")
            backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(backend)
            with patch.object(backend.subprocess, "run", return_value=Mock(returncode=0)) as run:
                self.assertTrue(backend.apply_static_wallpaper("/a b.png"))
                self.assertTrue(backend.apply_dynamic_wallpaper("/a b.mp4", "/thumbnail.jpg"))
                self.assertEqual([c.args[0] for c in run.call_args_list], [["skwd-helm", "apply", "/a b.png"], ["skwd-helm", "apply", "/a b.mp4"]])
            with patch.object(backend.subprocess, "run", return_value=Mock(returncode=3)):
                self.assertFalse(backend.apply_static_wallpaper("/a.png"))


class TestDesktopHandoff(unittest.TestCase):
    def load_helper(self):
        spec = importlib.util.spec_from_file_location("nyxuri_desktop_session_test", install.ROOT / "personal/desktop-session.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        return helper

    def test_environment_clears_hyprland_and_imports_current_display(self):
        helper = self.load_helper()
        env = {"WAYLAND_DISPLAY": "wayland-2", "NIRI_SOCKET": "/run/new-niri.sock", "HYPRLAND_INSTANCE_SIGNATURE": "dead", "AQ_DRM_DEVICES": "/dev/dri/old"}
        with TempEnv(), patch.object(helper.subprocess, "run", return_value=Mock(stdout="")) as run:
            helper.publish_environment("niri", env)
        calls = [c.args[0] for c in run.call_args_list]
        self.assertEqual(calls[0][0], "dbus-update-activation-environment")
        self.assertIn("HYPRLAND_INSTANCE_SIGNATURE=", calls[0])
        self.assertIn("AQ_DRM_DEVICES=", calls[0])
        self.assertIn("WAYLAND_DISPLAY=wayland-2", calls[0])
        self.assertEqual(calls[1][:3], ("systemctl", "--user", "unset-environment"))
        self.assertIn("AQ_DRM_DEVICES", calls[1])
        self.assertEqual(calls[2][:3], ("systemctl", "--user", "import-environment"))
        self.assertEqual(run.call_args_list[2].kwargs["env"]["NIRI_SOCKET"], "/run/new-niri.sock")
        self.assertNotIn("HYPRLAND_INSTANCE_SIGNATURE", run.call_args_list[2].kwargs["env"])

    def test_old_watcher_cannot_stop_new_session(self):
        helper = self.load_helper()
        identity = dict(desktop="hyprland", pid=1234, key="HYPRLAND_INSTANCE_SIGNATURE", value="old", wayland="wayland-1")
        with TempEnv(), patch.object(helper, "manager_environment", return_value={"XDG_CURRENT_DESKTOP": "niri", "NIRI_SOCKET": "/new", "WAYLAND_DISPLAY": "wayland-2"}), patch.object(helper.subprocess, "run") as run:
            helper.retire(identity)
            run.assert_not_called()


class TestPersonalUpdate(unittest.TestCase):
    def test_official_merge_and_reexec_command_shape(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            text = ""
            if args[1:] == ["branch", "--show-current"]:
                text = "night/personal-overlay"
            if args[1:] == ["remote", "get-url", "origin"]:
                text = "https://github.com/ech678/Nyxuri.git"
            return Mock(stdout=text, returncode=0)
        with TempEnv(), patch("personal.update.subprocess.run", side_effect=run):
            self.assertEqual(update.main([]), 0)
        self.assertIn(["git", "-c", "http.lowSpeedTime=15", "-c", "http.lowSpeedLimit=1000", "fetch", "origin", "main"], calls)
        self.assertIn(["git", "merge", "--no-edit", "FETCH_HEAD"], calls)
        self.assertEqual(calls[-1], [str(update.ROOT / "install.sh"), "install"])

    def test_dirty_tree_and_merge_conflict_do_not_deploy(self):
        with TempEnv(), patch("personal.update.subprocess.run", return_value=Mock(stdout=" M local.py")) as run:
            self.assertEqual(update.main([]), 1)
            self.assertEqual(run.call_count, 1)
        with TempEnv(), patch("personal.update.git", side_effect=["", "night/personal-overlay", "https://github.com/ech678/Nyxuri.git", "", subprocess.CalledProcessError(1, ["merge"])]), patch("personal.update.subprocess.run") as deploy:
            with self.assertRaises(subprocess.CalledProcessError):
                update.main([])
            deploy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
