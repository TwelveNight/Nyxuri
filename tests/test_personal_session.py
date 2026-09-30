"""The personal installer must leave the existing desktop's files alone."""

import unittest
from unittest.mock import patch

from tests.utils import TempEnv


class TestPersonalSession(unittest.TestCase):
    def test_standard_install_is_blocked_after_personal_deployment(self):
        from nyxuri.cli import main

        with TempEnv() as ctx:
            marker = ctx.home / ".config/nyxuri/personal-mode"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("enabled\n", encoding="utf-8")
            with patch("sys.argv", ["nyxuri", "install", "full"]), \
                 patch("nyxuri.cli.acquire_lock"), \
                 patch("nyxuri.cli.init_logger"), \
                 patch("nyxuri.cli.ensure_nyxuri_symlink"), \
                 patch("nyxuri.cli.install_configs_workflow") as workflow:
                with self.assertRaises(SystemExit) as exit_result:
                    main()
            self.assertEqual(exit_result.exception.code, 2)
            workflow.assert_not_called()

    def test_installer_deploys_only_session_files_and_moves_wallpaper_unit(self):
        from personal.install import main

        with TempEnv() as ctx:
            config = ctx.home / ".config"
            kitty = config / "kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n", encoding="utf-8")
            old_unit = config / "systemd/user/ii-skwd-wall-theme.service"
            old_unit.parent.mkdir(parents=True)
            old_unit.write_text("[Install]\nWantedBy=default.target\n", encoding="utf-8")

            with patch("personal.install.shutil.which", return_value="/usr/bin/program"), \
                 patch("personal.install.subprocess.run") as run:
                self.assertEqual(main(), 0)

            self.assertEqual((kitty / "kitty.conf").read_text(encoding="utf-8"), "shell zsh\n")
            self.assertFalse((config / "fish").exists())
            self.assertFalse((config / "gtk-3.0").exists())
            self.assertTrue((config / "niri/config.kdl").is_file())
            self.assertTrue((config / "noctalia/noctalia-config.toml").is_file())
            self.assertTrue((config / "kitty-nyxuri/kitty.conf").is_file())
            self.assertNotIn("/home/user", (config / "kitty-nyxuri/kitty.conf").read_text(encoding="utf-8"))
            self.assertIn("WantedBy=hyprland-session.target", old_unit.read_text(encoding="utf-8"))
            self.assertEqual(
                (config / "nyxuri/personal-original/ii-skwd-wall-theme.service").read_text(encoding="utf-8"),
                "[Install]\nWantedBy=default.target\n",
            )
            self.assertTrue((config / "nyxuri/personal-mode").is_file())
            colors = config / "kitty-nyxuri/colors__custom__.conf"
            colors.write_text("background #123456\n", encoding="utf-8")
            with patch("personal.install.shutil.which", return_value="/usr/bin/program"), \
                 patch("personal.install.subprocess.run"):
                self.assertEqual(main(), 0)
            self.assertEqual(colors.read_text(encoding="utf-8"), "background #123456\n")
            self.assertEqual(
                [call.args[0] for call in run.call_args_list if call.args[0][0] == "systemctl"],
                [
                    ["systemctl", "--user", "daemon-reload"],
                    ["systemctl", "--user", "disable", "ii-skwd-wall-theme.service"],
                    ["systemctl", "--user", "enable", "ii-skwd-wall-theme.service"],
                ],
            )


if __name__ == "__main__":
    unittest.main()
