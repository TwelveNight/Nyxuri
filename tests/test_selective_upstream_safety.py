"""Safety boundaries for the selectively backported upstream repairs."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.utils import TempEnv


class TestSelectiveUpstreamSafety(unittest.TestCase):
    def test_long_preset_name_can_be_saved_twice(self):
        from nyxuri.desktop.presets import save_preset

        with TempEnv() as ctx:
            live = ctx.env.config_dir / "kitty"
            live.mkdir()
            (live / "kitty.conf").write_text("first\n")
            name = "n" * 229
            with patch("builtins.print"):
                self.assertTrue(save_preset("kitty", name))
                (live / "kitty.conf").write_text("second\n")
                self.assertTrue(save_preset("kitty", name))
            saved = ctx.env.presets_dir / "kitty" / name
            self.assertEqual((saved / "kitty.conf").read_text(), "second\n")
            self.assertEqual([path.name for path in saved.parent.iterdir()], [name])

    def test_manifest_chmod_stays_inside_the_deployed_tree(self):
        from nyxuri.deploy.deploy import _phase_atomic_deployment
        from nyxuri.desktop.presets import apply_preset

        for route in ("deploy", "preset"):
            with self.subTest(route=route), TempEnv() as ctx:
                ctx.env.units_src = ctx.home / "source"
                app = ctx.env.units_src / "demo"
                scripts = app / "scripts"
                scripts.mkdir(parents=True)
                (app / "config.conf").write_text("base\n")
                script = scripts / "run.sh"
                script.write_text("#!/bin/sh\n")
                script.chmod(0o600)
                victim = ctx.env.config_dir / "victim"
                victim.write_text("keep\n")
                victim.chmod(0o600)
                (scripts / "escape.sh").symlink_to(victim)
                patterns = ["", str(victim), "../victim", "scripts/*.sh"]
                (app / "manifest.toml").write_text("chmod = " + json.dumps(patterns) + "\n")
                with patch("builtins.print"):
                    if route == "deploy":
                        self.assertEqual(_phase_atomic_deployment(["demo"]), [])
                    else:
                        self.assertTrue(apply_preset("demo", "default"))
                self.assertEqual(victim.stat().st_mode & 0o777, 0o600)
                self.assertEqual(victim.read_text(), "keep\n")
                deployed = ctx.env.config_dir / "demo/scripts/run.sh"
                self.assertEqual(deployed.stat().st_mode & 0o777, 0o755)

    def test_save_promotion_failure_keeps_the_existing_preset(self):
        from nyxuri.desktop import presets as preset

        with TempEnv() as ctx:
            live = ctx.env.config_dir / "kitty"
            live.mkdir()
            (live / "kitty.conf").write_text("new\n")
            saved = ctx.env.presets_dir / "kitty/mine"
            saved.mkdir(parents=True)
            (saved / "kitty.conf").write_text("old\n")
            rename = preset.os.rename

            def fail_promotion(src, dest, **kwargs):
                if str(src).startswith(".mine.") and dest == "mine":
                    raise OSError("promotion failed")
                return rename(src, dest, **kwargs)

            with patch.object(preset.os, "rename", side_effect=fail_promotion), patch("builtins.print"):
                self.assertFalse(preset.save_preset("kitty", "mine"))
            self.assertEqual((saved / "kitty.conf").read_text(), "old\n")
            self.assertEqual([path.name for path in saved.parent.iterdir()], ["mine"])

    def test_failed_promotion_and_restore_retain_the_old_backup(self):
        from nyxuri.desktop import presets as preset

        with TempEnv() as ctx:
            live = ctx.env.config_dir / "kitty"
            live.mkdir()
            (live / "kitty.conf").write_text("new\n")
            saved = ctx.env.presets_dir / "kitty/mine"
            saved.mkdir(parents=True)
            (saved / "kitty.conf").write_text("old\n")
            rename = preset.os.rename

            def fail_destination(src, dest, **kwargs):
                if dest == "mine":
                    raise OSError("destination unavailable")
                return rename(src, dest, **kwargs)

            with patch.object(preset.os, "rename", side_effect=fail_destination), \
                 patch.object(preset, "log_msg") as log, patch("builtins.print"):
                self.assertFalse(preset.save_preset("kitty", "mine"))
            remaining = list(saved.parent.iterdir())
            self.assertEqual(len(remaining), 1)
            backup = remaining[0]
            self.assertTrue(backup.name.startswith(".previous-"))
            self.assertEqual((backup / "kitty.conf").read_text(), "old\n")
            self.assertTrue(any(str(backup) in call.args[1] for call in log.call_args_list))

    def test_save_rejects_a_symlinked_preset_without_touching_its_target(self):
        from nyxuri.desktop.presets import save_preset

        with TempEnv() as ctx:
            live = ctx.env.config_dir / "kitty"
            live.mkdir()
            (live / "kitty.conf").write_text("new\n")
            target = ctx.home / "user-preset"
            target.mkdir()
            (target / "kitty.conf").write_text("keep\n")
            saved = ctx.env.presets_dir / "kitty/mine"
            saved.parent.mkdir(parents=True)
            saved.symlink_to(target)
            with patch("builtins.print"):
                self.assertFalse(save_preset("kitty", "mine"))
            self.assertTrue(saved.is_symlink())
            self.assertEqual((target / "kitty.conf").read_text(), "keep\n")

    def test_fcitx_write_does_not_modify_a_symlink_target(self):
        import runpy
        root = Path(__file__).resolve().parent.parent
        hook = runpy.run_path(str(root / "units/fcitx5-rime/hooks/activate"))
        with TempEnv() as ctx:
            original = ctx.home / "user-owned.conf"
            original.write_text("keep\n")
            config = ctx.env.config_dir / "classicui.conf"
            config.symlink_to(original)
            hook["_atomic_write"](config, "replacement\n")
            self.assertEqual(original.read_text(), "keep\n")
            self.assertFalse(config.is_symlink())
            self.assertEqual(config.read_text(), "replacement\n")
