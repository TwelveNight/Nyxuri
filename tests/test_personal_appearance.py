"""Wallpaper colors belong to the private Nyxuri compositor, not legacy Niri."""
import contextlib
import io
import unittest
import tomllib
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class PersonalAppearanceTests(unittest.TestCase):
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
