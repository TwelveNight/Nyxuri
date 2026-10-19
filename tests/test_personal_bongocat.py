"""Bongo Cat follows keyboard identity, without probing real input events."""
import importlib.util
from pathlib import Path
import sys
import tomllib
import unittest
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "personal/bongocat_input.py"


class PersonalBongocatTests(unittest.TestCase):
    def load_helper(self):
        self.assertTrue(HELPER.is_file(), "The verified input resolver must be tracked")
        spec = importlib.util.spec_from_file_location("personal_bongocat_test", HELPER)
        if spec is None or spec.loader is None:
            self.fail("Unable to load the tracked resolver")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def make_device(self, sys_root, dev_root, number, name):
        event = f"event{number}"
        directory = sys_root / event / "device"
        directory.mkdir(parents=True)
        (directory / "name").write_text(name)
        (dev_root / event).touch()
        return dev_root / event

    def test_prepare_sources_carries_resolver_and_scoped_plugin_settings(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            install.prepare_sources(source)
            target = source / "niri/scripts/bongocat_input.py"
            self.assertTrue(target.is_file(), "Personal deployment must include the resolver")
            self.assertTrue(target.stat().st_mode & 0o111)
            config = tomllib.loads((source / "noctalia/zz-personal-bongocat.toml").read_text())
            self.assertEqual(set(config), {"widget"})
            self.assertEqual(set(config["widget"]), {"cat", "atelier-cat", "atelier-split-cat"})
            for widget in config["widget"].values():
                self.assertEqual(widget["input_devices"], ["/dev/input/by-path/platform-i8042-serio-0-event-kbd"])
                self.assertEqual(widget["executable_path"], "/home/user/.config/niri/scripts/bongocat_input.py")

    def test_sandbox_deployment_renders_target_home(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty"
            kitty.mkdir()
            (kitty / "kitty.conf").write_text("shell zsh\n")
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
            private = ctx.home / ".config/desktop-profiles/nyxuri"
            helper = private / "niri/scripts/bongocat_input.py"
            config = tomllib.loads((private / "noctalia/zz-personal-bongocat.toml").read_text())
            for widget in config["widget"].values():
                self.assertEqual(widget["executable_path"], str(ctx.home / ".config/niri/scripts/bongocat_input.py"))
            self.assertTrue(helper.stat().st_mode & 0o111)
            self.assertFalse((ctx.home / ".config/niri").exists())

    def test_keyd_identity_survives_event_renumbering(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            sys_root, dev_root = ctx.home / "sys", ctx.home / "dev"
            dev_root.mkdir()
            self.make_device(sys_root, dev_root, 21, "HD-Audio Generic Mic")
            expected = self.make_device(sys_root, dev_root, 47, "keyd virtual keyboard")
            self.assertEqual(module.resolve_device(module.FALLBACK, sys_root, dev_root), expected)

    def test_missing_keyd_uses_only_stable_keyboard_fallback(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            sys_root, dev_root = ctx.home / "sys", ctx.home / "dev"
            (dev_root / "by-path").mkdir(parents=True)
            expected = dev_root / "by-path" / Path(module.FALLBACK).name
            expected.touch()
            self.assertEqual(module.resolve_device(module.FALLBACK, sys_root, dev_root), expected)
            expected.unlink()
            with self.assertRaisesRegex(ValueError, "no readable"):
                module.resolve_device(module.FALLBACK, sys_root, dev_root)

    def test_ambiguous_keyd_devices_fail_closed(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            sys_root, dev_root = ctx.home / "sys", ctx.home / "dev"
            dev_root.mkdir()
            for number in (47, 48):
                self.make_device(sys_root, dev_root, number, "keyd virtual keyboard")
            with self.assertRaisesRegex(ValueError, "multiple keyd"):
                module.resolve_device(module.FALLBACK, sys_root, dev_root)

    def test_arbitrary_device_selector_is_rejected(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            for selector in ("/dev/input/event21", "/dev/input/*", "../event0"):
                with self.subTest(selector=selector), self.assertRaisesRegex(ValueError, "unexpected"):
                    module.resolve_device(selector, ctx.home / "sys", ctx.home / "dev")

    def test_reader_exec_has_exact_arguments(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            selected = ctx.home / "dev/event47"
            with patch.object(sys, "argv", ["bongocat_input.py", module.FALLBACK]), patch.object(module, "resolve_device", return_value=selected) as resolve, patch.object(module.os, "execv", side_effect=RuntimeError("exec intercepted")) as execute:
                with self.assertRaisesRegex(RuntimeError, "exec intercepted"):
                    module.main()
            resolve.assert_called_once_with(module.FALLBACK)
            execute.assert_called_once_with("/usr/bin/evtest", ["evtest", str(selected)])

    def test_dry_run_reads_no_events(self):
        with TempEnv() as ctx:
            module = self.load_helper()
            selected = ctx.home / "dev/event47"
            with patch.object(sys, "argv", ["bongocat_input.py", "--resolve", module.FALLBACK]), patch.object(module, "resolve_device", return_value=selected), patch.object(module.os, "execv") as execute, patch("builtins.print") as output:
                self.assertEqual(module.main(), 0)
            execute.assert_not_called()
            output.assert_called_once_with(selected)


if __name__ == "__main__":
    unittest.main()
