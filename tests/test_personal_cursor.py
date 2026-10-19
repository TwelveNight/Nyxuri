"""Cursor deployment stays private and leaves user overrides last."""
import re
import unittest
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class PersonalCursorTests(unittest.TestCase):
    def test_redeployment_keeps_shared_settings_and_custom_cursor_override(self):
        with TempEnv() as ctx:
            originals = {}
            for name in ("niri/config.kdl", "hypr/custom/env.lua", "gtk-3.0/settings.ini",
                         "gtk-4.0/settings.ini", "kitty/kitty.conf"):
                target = ctx.home / ".config" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("original\n")
                originals[target] = target.read_bytes()
            upstream = (install.ROOT / "units/niri/config.kdl").read_bytes()
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), \
                 patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 patch("personal.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
                private = ctx.home / ".config/desktop-profiles/nyxuri/niri"
                custom = private / "__custom__.kdl"
                override = 'cursor { xcursor-size 32; }\n'
                custom.write_text(override)
                self.assertEqual(install.main(["--yes"]), 0)
            config = (private / "config.kdl").read_text()
            self.assertEqual(config.count('include "personal-cursor.kdl"'), 1)
            self.assertLess(config.index('include "personal-cursor.kdl"'),
                            config.index('include "__custom__.kdl"'))
            cursor = private / "personal-cursor.kdl"
            self.assertFalse(cursor.is_symlink())
            self.assertEqual(cursor.read_bytes(), (install.ROOT / "personal/cursor.kdl").read_bytes())
            profile = cursor.read_text()
            theme = re.search(r'xcursor-theme "([^"]+)"', profile).group(1)
            size = re.search(r'xcursor-size (\d+)', profile).group(1)
            self.assertIn(f'XCURSOR_THEME "{theme}"', profile)
            self.assertIn(f'XCURSOR_SIZE "{size}"', profile)
            for name in ("nyxuri-niri.service", "nyxuri-shell.service"):
                unit = (ctx.home / ".config/systemd/user" / name).read_text()
                self.assertIn(f'Environment=XCURSOR_THEME={theme} XCURSOR_SIZE={size}', unit)
            self.assertEqual(custom.read_text(), override)
            for path, original in originals.items():
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual((install.ROOT / "units/niri/config.kdl").read_bytes(), upstream)
