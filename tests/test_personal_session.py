"""The private desktop uses direct skwd requests, while preserving the existing desktops."""
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import unittest
import tomllib
from unittest.mock import patch, Mock

from tests.utils import TempEnv
from personal import install, runtime, update, session


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
                private = config / "desktop-profiles/nyxuri"
                niri = (private / "niri/config.kdl").read_text()
                self.assertIn(str(config / "kitty-nyxuri"), niri)
                self.assertNotIn(".config/nyxuri-desktop", niri)
                self.assertIn('XMODIFIERS "@im=fcitx"', niri)
                for name in ("GTK_IM_MODULE", "QT_IM_MODULE", "SDL_IM_MODULE"):
                    self.assertIn(f'{name} null', niri)
                self.assertLess(niri.index('include "personal-gpu.kdl"'), niri.index('include "__custom__.kdl"'))
                self.assertIn('pci-0000:01:00.0-render', (private / "niri/personal-gpu.kdl").read_text())
                self.assertIn('2560x1440@143.995', (private / "niri/monitor.kdl").read_text())
                shell = (config / "systemd/user/nyxuri-shell.service").read_text()
                self.assertIn('Environment=__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __VK_LAYER_NV_optimus=NVIDIA_only', shell)
                unset = next(line for line in shell.splitlines() if line.startswith('UnsetEnvironment='))
                self.assertNotIn('__NV_PRIME_RENDER_OFFLOAD', unset)
                self.assertIn('DRI_PRIME', unset)
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
            self.assertEqual(conf["theme"]["templates"]["user"]["nyxuri_niri_glow_material_you"]["output_path"], str(config / "niri/colors.kdl"))
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
            private = ctx.home / ".config/desktop-profiles/nyxuri"
            for app in ("niri", "noctalia", "kitty-nyxuri"):
                (ctx.home / ".config" / app).symlink_to(private / app)
            for command in (["niri", "validate", "--config", str(private / "niri/config.kdl")], ["noctalia", "config", "validate", str(private / "noctalia")], ["desktop-file-validate", str(private / "nyxuri.desktop")]):
                result = subprocess.run(command, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_noctalia_environment_loads_hooks_and_private_theme_policy(self):
        import shutil
        import tomllib
        if not shutil.which("noctalia"):
            self.skipTest("Noctalia is not installed")
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
            private = ctx.home / ".config/desktop-profiles/nyxuri"
            for app in ("niri", "noctalia", "kitty-nyxuri"):
                (ctx.home / ".config" / app).symlink_to(private / app)
            niri = (private / "niri/config.kdl").read_text()
            environment = dict(os.environ)
            environment.update(re.findall(r'(NOCTALIA_(?:CONFIG|STATE)_HOME) "([^"]+)"', niri))
            # A validator accepts an empty directory too. Export through the
            # actual launch environment to prove the intended files are read.
            result = subprocess.run(["noctalia", "config", "export"], env=environment,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = tomllib.loads(result.stdout)
            self.assertFalse(config["wallpaper"]["enabled"])
            self.assertFalse(config["shell"]["clipboard_enabled"])
            self.assertEqual(config["hooks"]["theme_mode_changed"], "nyxuri theme sync")
            self.assertEqual(config["hooks"]["wallpaper_changed"],
                             ["python3 ~/.config/niri/scripts/wallpaper.py hook"])
            self.assertIn("bar", config["bar"])
            self.assertEqual(config["theme"]["templates"]["builtin_ids"], [])
            self.assertEqual(config["plugins"]["enabled"], [])
            templates = config["theme"]["templates"]["user"]
            for suffix, filename in (("theme", "theme.conf"), ("panel", "panel.svg"), ("highlight", "highlight.svg")):
                entry = templates[f"nyxmellow_{suffix}"]
                self.assertTrue(entry["enabled"])
                self.assertEqual(entry["input_path"], str(ctx.home / ".config/noctalia/templates/fcitx5" / filename))
                self.assertEqual(entry["output_path"], str(ctx.home / ".local/share/fcitx5/themes/nyxmellow" / filename))
                self.assertEqual((private / "noctalia/templates/fcitx5" / filename).read_bytes(), (install.ROOT / "assets/fcitx5/nyxmellow/templates" / filename).read_bytes())
            self.assertIn("ReloadAddonConfig s classicui", templates["nyxmellow_highlight"]["post_hook"])
            self.assertNotIn("pkill", templates["nyxmellow_highlight"]["post_hook"])
            for version in (3, 4):
                entry = templates[f"nyxuri_gtk{version}"]
                self.assertTrue(entry["enabled"])
                self.assertEqual(entry["input_path"], str(ctx.home / f".config/noctalia/templates/gtk-{version}.0.css"))
                self.assertEqual(entry["output_path"], str(ctx.home / f".config/gtk-{version}.0/gtk.css"))



    def test_plan_does_not_write(self):
        with TempEnv() as ctx:
            self.assertEqual(install.main(["--plan"]), 0)
            self.assertFalse((ctx.home / ".config/desktop-profiles/nyxuri").exists())

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


class TestDirectWallpaperBackend(unittest.TestCase):
    def test_picker_commands_bypass_noctalia_and_report_failure(self):
        with TempEnv() as ctx:
            sources = ctx.home / "sources"
            sources.mkdir()
            install.prepare_sources(sources)
            spec = importlib.util.spec_from_file_location("direct_backend_test", sources / "noctalia/tools/wallpaper_picker/backend.py")
            backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(backend)
            with patch.object(backend._renderer, "apply") as apply, patch.object(backend._renderer.subprocess, "run") as run:
                self.assertTrue(backend.apply_static_wallpaper("/a b.png"))
                self.assertTrue(backend.apply_dynamic_wallpaper("/a b.mp4", "/thumbnail.jpg"))
            self.assertEqual([call.args[0] for call in apply.call_args_list], ["/a b.png", "/a b.mp4"])
            run.assert_not_called()
            with patch.object(backend._renderer, "apply", side_effect=ValueError("renderer failed")):
                self.assertFalse(backend.apply_static_wallpaper("/a.png"))
            values = tomllib.loads((sources / "noctalia/noctalia-config.toml").read_text())
            self.assertFalse(values["wallpaper"]["enabled"])
            self.assertEqual(values["hooks"]["wallpaper_changed"], ["python3 ~/.config/niri/scripts/wallpaper.py hook"])
            self.assertEqual(values["plugins"]["enabled"], [])
            self.assertTrue((sources / "niri/scripts/wallpaper.py").exists())


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
        self.assertIn("XMODIFIERS=@im=fcitx", calls[0])
        self.assertEqual(calls[1][:3], ("systemctl", "--user", "unset-environment"))
        self.assertIn("AQ_DRM_DEVICES", calls[1])
        self.assertEqual(calls[2][:3], ("systemctl", "--user", "import-environment"))
        self.assertEqual(run.call_args_list[2].kwargs["env"]["NIRI_SOCKET"], "/run/new-niri.sock")
        self.assertEqual(run.call_args_list[2].kwargs["env"]["XMODIFIERS"], "@im=fcitx")
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
        with TempEnv(), patch("personal.update.git", side_effect=["", "night/personal-overlay", "https://github.com/ech678/Nyxuri.git", "", "", "", subprocess.CalledProcessError(1, ["merge"])]), patch("personal.update.subprocess.run") as deploy:
            with self.assertRaises(subprocess.CalledProcessError):
                update.main([])
            deploy.assert_not_called()


    def test_incompatible_upstream_layout_stops_before_merge_or_deploy(self):
        with TempEnv(), patch("personal.update.git", side_effect=["", "night/personal-overlay", "https://github.com/ech678/Nyxuri.git", "", subprocess.CalledProcessError(1, ["git", "cat-file", "-e", "FETCH_HEAD:configs/niri/config.kdl"])]) as git, patch("personal.update.subprocess.run") as deploy:
            self.assertEqual(update.main([]), 1)
            self.assertEqual(git.call_args.args, ("cat-file", "-e", "FETCH_HEAD:configs/niri/config.kdl"))
            self.assertFalse(any(call.args[:1] == ("merge",) for call in git.call_args_list))
            deploy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
