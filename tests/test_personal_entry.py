"""The standard bootstrap installs the private desktop on fresh checkouts too."""
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from personal import entry, install, update
from tests.utils import TempEnv


class PersonalEntryTests(unittest.TestCase):
    def test_bootstrap_plans_private_install_without_installed_marker(self):
        with TempEnv() as ctx:
            for arguments in ([], ["install", "full"], ["deploy", "config"]):
                result = subprocess.run([str(install.ROOT / "install.sh"), *arguments, "--plan"],
                                        cwd=ctx.home, env=os.environ.copy(), capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(str(ctx.home / ".config/desktop-profiles/nyxuri"), result.stdout)
                self.assertIn("disable ToDesk in all desktops", result.stdout)
                self.assertIn("Register: Nyxuri GDM", result.stdout)
            self.assertFalse((ctx.home / ".config/desktop-profiles/nyxuri").exists())
            self.assertFalse((ctx.home / ".local/bin/nyxuri").exists())

    def test_explicit_install_registers_session_once(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            inir = ctx.home / ".config/niri"
            inir.mkdir()
            (inir / "config.kdl").write_text("// original iNiR\n")
            target = ctx.home / "sessions/nyxuri.desktop"
            with patch.object(entry, "GDM_ENTRY", target), patch.object(entry.sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="y"), patch.object(entry.subprocess, "run", return_value=Mock(returncode=0)) as run, patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(entry.dispatch(["install"]), 0)
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ["sudo", "-v"], ["systemctl", "--user", "daemon-reload"],
                ["sudo", "install", "-Dm644", str(ctx.home / ".config/desktop-profiles/nyxuri/nyxuri.desktop"), str(target)]])
            self.assertTrue(all(call.kwargs == {"check": True} for call in run.call_args_list))
            self.assertEqual((inir / "config.kdl").read_text(), "// original iNiR\n")
            self.assertTrue((ctx.home / ".config/desktop-profiles/nyxuri/installed").is_file())
            self.assertEqual((ctx.home / ".local/bin/nyxuri").resolve(), install.ROOT / "nyxuri/launcher.sh")

    def test_existing_session_needs_no_sudo(self):
        with TempEnv() as ctx:
            target = ctx.home / "nyxuri.desktop"
            target.write_text((install.ROOT / "personal/nyxuri.desktop").read_text().replace("/home/user", str(ctx.home)))
            with patch.object(entry, "GDM_ENTRY", target), patch.object(entry.subprocess, "run") as run:
                entry.prepare_session(ctx.env)
                entry.register_session(ctx.env)
            self.assertEqual([call.args[0] for call in run.call_args_list], [["systemctl", "--user", "daemon-reload"]])

    def test_authentication_failure_precedes_any_config_deployment(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch.object(entry, "GDM_ENTRY", ctx.home / "missing.desktop"), patch.object(entry.sys.stdin, "isatty", return_value=False), patch.object(entry.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["sudo"])) as run, patch("personal.install.shutil.which", return_value="/usr/bin/tool"):
                with self.assertRaises(subprocess.CalledProcessError):
                    entry.dispatch(["install", "--yes"])
            run.assert_called_once_with(["sudo", "-n", "-v"], check=True)
            self.assertFalse((ctx.home / ".config/desktop-profiles/nyxuri").exists())
            self.assertFalse((ctx.home / ".config/autostart").exists())

    def test_unknown_install_options_do_not_start_deployment(self):
        with TempEnv(), patch.object(install, "main") as deploy:
            for arguments in (["install", "fish"], ["deploy", "--force"]):
                with self.assertRaises(SystemExit) as result:
                    entry.dispatch(arguments)
                self.assertEqual(result.exception.code, 2)
            deploy.assert_not_called()

    def test_noninteractive_menu_does_not_deploy(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch.object(entry.sys.stdin, "isatty", return_value=False), patch.object(entry.subprocess, "run") as run, patch("personal.install.shutil.which", return_value="/usr/bin/tool"):
                self.assertEqual(entry.dispatch([]), 0)
            run.assert_not_called()
            self.assertFalse((ctx.home / ".config/desktop-profiles/nyxuri").exists())

    def test_menu_routes_install_and_update_through_private_bootstrap(self):
        with TempEnv(), patch("nyxuri.tui.Menu.run", side_effect=[0, 1, 6]), patch("nyxuri.tui.press_any_key"), patch.object(entry.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertEqual(entry.dispatch([]), 0)
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                [str(install.ROOT / "install.sh"), "install"],
                [str(install.ROOT / "install.sh"), "update"]])
            self.assertTrue(all(call.kwargs == {"cwd": install.ROOT} for call in run.call_args_list))

    def test_redeployment_preserves_remote_policy_and_another_active_profile(self):
        with TempEnv() as ctx:
            kitty = ctx.env.config_dir / "kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            inir = ctx.env.config_dir / "desktop-profiles/inir/niri"
            inir.mkdir(parents=True)
            (inir / "config.kdl").write_text('// active iNiR sentinel\n')
            canonical = ctx.env.config_dir / "niri"
            canonical.symlink_to(inir)
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
                profile = ctx.env.config_dir / "desktop-profiles/nyxuri/niri"
                remote = profile / "remote-panel__custom__.kdl"
                remote.write_text('// remote panel policy\n')
                custom = profile / "__custom__.kdl"
                custom.write_text('include "remote-panel__custom__.kdl"\n')
                monitor = profile / "monitor.kdl"
                monitor.write_text('output "eDP-2" { position x=0 y=0; }\n')
                before = {p.name: p.read_bytes() for p in (remote, custom, monitor)}
                self.assertEqual(install.main(["--yes"]), 0)
                self.assertEqual({p.name: p.read_bytes() for p in (remote, custom, monitor)}, before)
            self.assertTrue(canonical.is_symlink())
            self.assertEqual(canonical.resolve(), inir)
            self.assertEqual((canonical / "config.kdl").read_text(), '// active iNiR sentinel\n')

    def test_local_update_redeploys_without_git_or_profile_selection(self):
        with TempEnv(), patch.object(update, "git") as git, patch.object(update.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertEqual(entry.dispatch(["update", "--local", "--yes"]), 0)
            git.assert_not_called()
            run.assert_called_once_with([str(update.ROOT / "install.sh"), "install", "--yes"], cwd=update.ROOT)

    def test_local_update_cannot_be_combined_with_no_deploy(self):
        with TempEnv(), patch.object(update, "git") as git, patch.object(update.subprocess, "run") as run:
            with self.assertRaises(SystemExit) as stopped:
                update.main(["--local", "--no-deploy"])
            self.assertEqual(stopped.exception.code, 2)
            git.assert_not_called()
            run.assert_not_called()

    def test_state_commands_and_aliases_use_only_nyxuri_profile(self):
        from nyxuri import core
        with TempEnv() as ctx:
            registry = ctx.env.config_dir / "desktop-profiles/profiles.json"
            registry.parent.mkdir()
            registry.write_text('{}')
            expected = ctx.env.config_dir / "desktop-profiles/nyxuri"
            def assert_scope():
                self.assertEqual(core.get_env().config_dir, expected)
                self.assertEqual(core.get_env().nyx_dir, expected / "manager")
                self.assertEqual({p.name for p in core.get_env().units_src.iterdir()}, set(install.CONFIGS))
                self.assertEqual(core.get_env().state_dir, ctx.home / ".local/state/nyxuri-desktop/manager")
            previous = core._ENV
            with patch("nyxuri.cli.main", side_effect=assert_scope) as main, patch.object(entry.subprocess, "run") as guard:
                for command in ("snapshot", "backup", "list", "preset", "rollback", "restore", "uninstall", "remove", "purge", "BACKUP"):
                    with self.subTest(command=command):
                        arguments = [command, "niri", "list"] if command == "preset" else [command]
                        self.assertEqual(entry.dispatch(arguments), 0)
                        self.assertIs(core._ENV, previous)
                        guard.assert_called_with([str(ctx.home / ".local/bin/desktop-profile"), "guard", "nyxuri"], check=True)
                self.assertEqual(main.call_count, 10)

    def test_unit_lifecycle_cannot_modify_global_units(self):
        with TempEnv() as ctx:
            registry = ctx.env.config_dir / "desktop-profiles/profiles.json"
            registry.parent.mkdir()
            registry.write_text('{}')
            with patch("nyxuri.cli.main") as main:
                for command in ("on", "off", "enable", "disable"):
                    self.assertEqual(entry.dispatch([command, "theme"]), 2)
            main.assert_not_called()

    def test_managed_update_delegates_to_the_registered_pipeline(self):
        with TempEnv() as ctx:
            registry = ctx.env.config_dir / "desktop-profiles/profiles.json"
            registry.parent.mkdir()
            registry.write_text('{}')
            helper = ctx.home / ".local/bin/desktop-update"
            helper.write_text("#!/bin/sh\n")
            with patch.object(update.subprocess, "run", return_value=Mock(returncode=0)) as run:
                self.assertEqual(update.main(["--no-deploy"]), 0)
            run.assert_called_once_with([str(helper), "sync", "nyxuri"], check=False)

    def test_state_command_restores_environment_after_failure(self):
        from nyxuri import core
        with TempEnv() as ctx:
            registry = ctx.env.config_dir / "desktop-profiles/profiles.json"
            registry.parent.mkdir()
            registry.write_text('{}')
            previous = core._ENV
            with patch("nyxuri.cli.main", side_effect=RuntimeError("stopped")), patch.object(entry.subprocess, "run"):
                with self.assertRaisesRegex(RuntimeError, "stopped"):
                    entry.dispatch(["restore"])
            self.assertIs(core._ENV, previous)

    def test_incompatible_upstream_stops_before_merge_and_deployment(self):
        def git_result(*args):
            if args == ("status", "--porcelain"):
                return ""
            if args == ("branch", "--show-current"):
                return "night/personal-overlay"
            if args == ("remote", "get-url", "origin"):
                return "https://github.com/ech678/Nyxuri.git"
            if args[:2] == ("cat-file", "-e"):
                raise subprocess.CalledProcessError(1, ["git", *args])
            if args[0] == "merge":
                self.fail("Must not merge an incompatible unit architecture")
            return ""
        with TempEnv(), patch.object(update, "git", side_effect=git_result), patch.object(update.subprocess, "run") as run:
            self.assertEqual(update.main(["--yes"]), 1)
            run.assert_not_called()

    def test_update_yes_reenters_standard_installer(self):
        with TempEnv(), patch.object(update, "git", side_effect=["", "night/personal-overlay", "https://github.com/ech678/Nyxuri.git", "", "", "", ""]), patch.object(update.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertEqual(entry.dispatch(["update", "--yes"]), 0)
            run.assert_called_once_with([str(update.ROOT / "install.sh"), "install", "--yes"], cwd=update.ROOT)


if __name__ == "__main__":
    unittest.main()
