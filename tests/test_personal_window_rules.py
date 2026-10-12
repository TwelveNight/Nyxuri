"""Application rules remain private, ordered, and overridable after deployment."""
import unittest
from unittest.mock import patch

from personal import install
from tests.utils import TempEnv


class PersonalWindowRuleTests(unittest.TestCase):
    def test_redeployment_loads_rules_after_defaults_and_preserves_custom_override(self):
        with TempEnv() as ctx:
            shared = ctx.home / ".config/niri/config.kdl"
            shared.parent.mkdir(parents=True, exist_ok=True)
            shared.write_text("shared config\n")
            kitty = ctx.home / ".config/kitty/kitty.conf"
            kitty.parent.mkdir(parents=True)
            kitty.write_text("shell zsh\n")
            upstream = (install.ROOT / "configs/niri/rules.kdl").read_bytes()
            with patch("personal.install.shutil.which", return_value="/usr/bin/tool"), \
                 patch("nyxuri.deploy.templates.get_pics_dir", return_value=ctx.home / "Pictures"), \
                 patch("nyxuri.deploy.assets.get_pics_dir", return_value=ctx.home / "Pictures"):
                self.assertEqual(install.main(["--yes"]), 0)
                private = ctx.home / ".config/nyxuri-desktop/niri"
                custom = private / "__custom__.kdl"
                override = 'window-rule { match app-id="QQ"; open-floating false; }\n'
                custom.write_text(override)
                self.assertEqual(install.main(["--yes"]), 0)
            config = (private / "config.kdl").read_text()
            ordered = ['include "rules.kdl"', 'include "personal-window-rules.kdl"',
                       'include "personal-games.kdl"', 'include "__custom__.kdl"']
            offsets = [config.index(item) for item in ordered]
            self.assertEqual(offsets, sorted(offsets))
            for source, deployed in (("window-rules.kdl", "personal-window-rules.kdl"),
                                     ("games.kdl", "personal-games.kdl")):
                self.assertEqual(config.count(f'include "{deployed}"'), 1)
                self.assertFalse((private / deployed).is_symlink())
                self.assertEqual((private / deployed).read_bytes(),
                                 (install.ROOT / "personal" / source).read_bytes())
            self.assertNotIn("match is-active=", (private / "personal-window-rules.kdl").read_text())
            self.assertEqual(custom.read_text(), override)
            self.assertEqual(shared.read_text(), "shared config\n")
            self.assertEqual((install.ROOT / "configs/niri/rules.kdl").read_bytes(), upstream)
