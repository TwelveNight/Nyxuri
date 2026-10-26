"""Wallpaper colors belong to the private Nyxuri compositor, not legacy Niri."""
import contextlib
import io
import os
import shlex
import subprocess
import unittest
import tomllib
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class PersonalAppearanceTests(unittest.TestCase):
    def test_theme_hook_runs_without_user_bin_in_path(self):
        with TempEnv() as ctx:
            kitty = ctx.home / ".config/kitty/kitty.conf"
            kitty.parent.mkdir()
            kitty.write_text("shell zsh\n")
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), \
                 patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install.main(["--yes"]), 0)
            config = ctx.home / ".config/desktop-profiles/nyxuri/noctalia"
            data = tomllib.loads((config / "noctalia-config.toml").read_text())
            personal = tomllib.loads((config / "zz-personal-appearance.toml").read_text())
            hook = personal.get("hooks", {}).get("theme_mode_changed", data["hooks"]["theme_mode_changed"])
            launcher = ctx.home / ".local/bin/nyxuri"
            self.assertEqual(shlex.split(hook), [str(launcher), "theme", "sync"])
            # Record argv without invoking the real theme writer or session IPC.
            launcher.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/hook-argv"\n')
            launcher.chmod(0o755)
            env = {**os.environ, "PATH": "/usr/bin:/bin"}
            result = subprocess.run(["/bin/sh", "-c", hook], env=env,
                                    capture_output=True, text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((ctx.home / "hook-argv").read_text(), "theme\nsync\n")


    def test_installed_palette_paths_expand_home_without_touching_legacy_niri(self):
        with TempEnv() as ctx:
            config = ctx.home / ".config"
            legacy = config / "niri/config.kdl"
            legacy.parent.mkdir()
            legacy.write_text('include "noctalia.kdl"\n')
            kitty = config / "kitty/kitty.conf"
            kitty.parent.mkdir()
            kitty.write_text("shell zsh\n")
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), \
                 patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install.main(["--yes"]), 0)
            private = config / "desktop-profiles/nyxuri"
            data = tomllib.loads((private / "noctalia/zz-personal-appearance.toml").read_text())
            entry = data["theme"]["templates"]["user"]["nyxuri_niri_colors"]
            self.assertEqual(entry["input_path"], str(config / "noctalia/templates/niri-personal.kdl"))
            self.assertEqual(entry["output_path"], str(config / "niri/appearance-colors.kdl"))
            self.assertEqual(legacy.read_text(), 'include "noctalia.kdl"\n')

    def test_niri_colors_are_private_and_keep_user_overrides_last(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            protected = {}
            for name in ("niri/config.kdl", "hypr/custom/env.lua", "quickshell/inir/config.json"):
                path = ctx.home / ".config" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("keep this desktop\n")
                protected[path] = path.read_bytes()
            upstream = install.ROOT / "units/niri/config.kdl"
            original = upstream.read_bytes()
            install.prepare_sources(source)
            config = (source / "niri/config.kdl").read_text()
            include = 'include optional=true "appearance-colors.kdl"'
            self.assertIn(include, config)
            self.assertLess(config.index('include "personal-overview.kdl"'), config.index(include))
            self.assertLess(config.index(include), config.index('include "__custom__.kdl"'))
            policy = tomllib.loads((source / "noctalia/zz-personal-appearance.toml").read_text())
            entry = policy["theme"]["templates"]["user"]["nyxuri_niri_colors"]
            self.assertTrue(entry["enabled"])
            self.assertEqual(entry["input_path"], "/home/user/.config/noctalia/templates/niri-personal.kdl")
            self.assertEqual(entry["output_path"], "/home/user/.config/niri/appearance-colors.kdl")
            self.assertNotIn("post_hook", entry)
            template = (source / "noctalia/templates/niri-personal.kdl").read_text()
            self.assertIn('active-color "{{colors.primary.default.hex}}"', template)
            self.assertIn("tab-indicator", template)
            self.assertIn("insert-hint", template)
            self.assertIn("recent-windows", template)
            for unchanged in ("focus-ring", "shadow", "border", "width", "off"):
                self.assertNotRegex(template, rf"\b{unchanged}\b")
            self.assertEqual(upstream.read_bytes(), original)
            for path, before in protected.items():
                self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
