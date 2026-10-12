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
                self.assertIn(str(ctx.home / ".config/nyxuri-desktop"), result.stdout)
                self.assertIn("disable ToDesk in all desktops", result.stdout)
                self.assertIn("Register: Nyxuri GDM", result.stdout)
            self.assertFalse((ctx.home / ".config/nyxuri-desktop").exists())
            self.assertFalse((ctx.home / ".local/bin/nyxuri").exists())

    def test_default_installs_privately_and_registers_session_once(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            inir = ctx.home / ".config/niri"
            inir.mkdir()
            (inir / "config.kdl").write_text("// original iNiR\n")
            target = ctx.home / "sessions/nyxuri.desktop"
            with patch.object(entry, "GDM_ENTRY", target), patch.object(entry.sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="y"), patch.object(entry.subprocess, "run", return_value=Mock(returncode=0)) as run, patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(entry.dispatch([]), 0)
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ["sudo", "-v"], ["systemctl", "--user", "daemon-reload"],
                ["sudo", "install", "-Dm644", str(ctx.home / ".config/nyxuri-desktop/nyxuri.desktop"), str(target)]])
            self.assertTrue(all(call.kwargs == {"check": True} for call in run.call_args_list))
            self.assertEqual((inir / "config.kdl").read_text(), "// original iNiR\n")
            self.assertTrue((ctx.home / ".config/nyxuri-desktop/installed").is_file())
            self.assertEqual((ctx.home / ".local/bin/nyxuri").resolve(), install.ROOT / "install.sh")

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
            self.assertFalse((ctx.home / ".config/nyxuri-desktop").exists())
            self.assertFalse((ctx.home / ".config/autostart").exists())

    def test_unknown_install_options_do_not_start_deployment(self):
        with TempEnv(), patch.object(install, "main") as deploy:
            for arguments in (["install", "fish"], ["deploy", "--force"]):
                with self.assertRaises(SystemExit) as result:
                    entry.dispatch(arguments)
                self.assertEqual(result.exception.code, 2)
            deploy.assert_not_called()

    def test_unconfirmed_default_does_not_authenticate_or_deploy(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch.object(entry.sys.stdin, "isatty", return_value=False), patch.object(entry.subprocess, "run") as run, patch("personal.install.shutil.which", return_value="/usr/bin/tool"):
                self.assertEqual(entry.dispatch([]), 2)
            run.assert_not_called()
            self.assertFalse((ctx.home / ".config/nyxuri-desktop").exists())

    def test_update_yes_reenters_standard_installer(self):
        with TempEnv(), patch.object(update, "git", side_effect=["", "night/personal-overlay", "https://github.com/ech678/Nyxuri.git", "", ""]), patch.object(update.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertEqual(entry.dispatch(["update", "--yes"]), 0)
            run.assert_called_once_with([str(update.ROOT / "install.sh"), "install", "--yes"], cwd=update.ROOT)


if __name__ == "__main__":
    unittest.main()
