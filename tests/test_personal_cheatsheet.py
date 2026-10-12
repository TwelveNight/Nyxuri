"""Cheatsheet navigation reads this desktop's configuration after deployment."""
import re
import tomllib
import unittest
from pathlib import Path

from personal import install
from personal.cheatsheet_categories import annotate, category
from nyxuri.deploy.atomic import atomic_replace_item
from tests.utils import TempEnv


class PersonalCheatsheetTests(unittest.TestCase):
    def test_generated_plugin_settings_and_bind_target_private_desktop(self):
        with TempEnv() as ctx:
            stage = ctx.home / "source"
            stage.mkdir()
            upstream = (install.ROOT / "configs/niri/binds.kdl").read_bytes()
            install.prepare_sources(stage)
            config = tomllib.loads((stage / "noctalia/zz-personal-cheatsheet.toml").read_text())
            settings = config["plugin_settings"]["kenn/keybind-cheatsheet"]
            self.assertEqual(settings["compositor"], "niri")
            self.assertEqual(settings["niri_config"], "~/.config/nyxuri-desktop/niri/config.kdl")
            # Deploy the generated settings as the installer does. The plugin
            # expands '~' itself, so the root must resolve in the target HOME.
            target = ctx.home / ".config/nyxuri-desktop"
            target.mkdir()
            atomic_replace_item(stage / "niri", target / "niri")
            atomic_replace_item(stage / "noctalia", target / "noctalia")
            deployed = tomllib.loads((target / "noctalia/zz-personal-cheatsheet.toml").read_text())
            root = Path(deployed["plugin_settings"]["kenn/keybind-cheatsheet"]["niri_config"]).expanduser()
            self.assertEqual(root, target / "niri/config.kdl")
            self.assertTrue(root.is_file())
            binds = (stage / "niri/personal-binds.kdl").read_text()
            shortcut = re.search(r'(?m)^    Mod\+Slash[^\n]*', binds).group()
            self.assertIn('repeat=false', shortcut)
            self.assertIn('spawn "noctalia" "msg" "panel-toggle" "kenn/keybind-cheatsheet:cheatsheet";', shortcut)
            self.assertIn('Ctrl+Mod+Slash', binds)
            self.assertEqual((install.ROOT / "configs/niri/binds.kdl").read_bytes(), upstream)


class CheatsheetCategoryTests(unittest.TestCase):
    def test_annotations_are_idempotent_and_preserve_binding_actions(self):
        with TempEnv():
            source = 'binds {\n    Mod+C { center-column; }\n    Mod+Shift+Q { quit; }\n}\n'
            result = annotate(source)
            self.assertEqual(annotate(result), result)
            stripped = re.sub(r'(?m)^[ \t]*// #"[^"\n]*"[ \t]*\n', '', result)
            self.assertEqual(stripped, source)
            self.assertIn('// #"窗口布局"', result)
            self.assertIn('// #"电源与会话"', result)

    def test_known_other_actions_have_specific_categories(self):
        with TempEnv():
            examples = {
                "center-column;": "窗口布局",
                "set-window-height -10%;": "窗口尺寸",
                "toggle-window-floating;": "浮动窗口",
                "switch-focus-between-floating-and-tiling;": "浮动窗口",
                "consume-or-expel-window-left;": "窗口与列移动",
                "focus-workspace 1;": "工作区切换",
                "focus-monitor-left;": "显示器焦点",
                "next-window;": "窗口焦点",
                "toggle-overview;": "概览与快捷键",
                'spawn "noctalia" "msg" "media" "toggle";': "媒体播放",
                'spawn "noctalia" "msg" "volume-up";': "音量与麦克风",
                "future-unrecognized-action;": "其他",
            }
            for action, expected in examples.items():
                with self.subTest(action=action):
                    self.assertEqual(category(action), expected)
