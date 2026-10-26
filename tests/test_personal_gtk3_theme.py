"""Named GTK3 palettes must stay reloadable without touching user-owned CSS."""
import os

import subprocess
import unittest
from unittest.mock import patch

from personal import entry, gtk3
from tests.utils import TempEnv


class PersonalGtk3ThemeTests(unittest.TestCase):
    def prepare_palettes(self, ctx):
        themes = ctx.home / ".local/share/themes"
        for mode in ("light", "dark"):
            base = themes / ("adw-gtk3" if mode == "light" else "adw-gtk3-dark") / "gtk-3.0/gtk.css"
            base.parent.mkdir(parents=True)
            base.write_text("/* base theme fixture */\n")
            palette = themes / f"Nyxuri-M3-{mode.title()}/gtk-3.0/gtk.css"
            palette.parent.mkdir(parents=True)
            palette.write_text('@import url("base.css");\n/* palette fixture */\n')
        template = ctx.home / ".config/noctalia/templates/gtk-3.0.css"
        template.parent.mkdir(parents=True)
        template.write_text("/* GTK3 Material You 主题模板 */\n@define-color window_bg_color {{ colors.background.default.hex }};\n")
        css = ctx.home / ".config/gtk-3.0/gtk.css"
        css.parent.mkdir()
        css.write_text(template.read_text().replace("{{ colors.background.default.hex }}", "#123456"))
        return themes, css

    def test_theme_command_selects_named_palettes_and_restores_environment(self):
        with TempEnv() as ctx:
            themes, css = self.prepare_palettes(ctx)
            before = css.read_bytes()
            expected = {"NYXURI_GTK_THEME_LIGHT": "Nyxuri-M3-Light",
                        "NYXURI_GTK_THEME_DARK": "Nyxuri-M3-Dark"}
            old = {key: os.environ.get(key) for key in expected}
            def assert_theme_environment():
                self.assertEqual({key: os.environ.get(key) for key in expected}, expected)
            with patch("nyxuri.cli.main", side_effect=assert_theme_environment) as main:
                self.assertEqual(entry.dispatch(["theme", "sync"]), 0)
            main.assert_called_once_with()
            self.assertEqual({key: os.environ.get(key) for key in expected}, old)
            self.assertEqual(css.read_text(), "/* Nyxuri GTK3 colors are loaded from named themes. */\n")
            backup = ctx.home / ".local/state/nyxuri-desktop/gtk3/gtk.css.before-named-themes"
            self.assertEqual(backup.read_bytes(), before)
            for mode in ("Light", "Dark"):
                base = themes / f"Nyxuri-M3-{mode}/gtk-3.0/base.css"
                self.assertIn("adw-gtk3", base.read_text())
                alias = themes / f"Nyxuri-M3-{mode}-Alt/gtk-3.0/gtk.css"
                self.assertIn(f"Nyxuri-M3-{mode}/gtk-3.0/gtk.css", alias.read_text())

    def test_refresh_alternates_theme_names_without_replacing_the_palette(self):
        with TempEnv() as ctx:
            themes, _ = self.prepare_palettes(ctx)
            palette = themes / "Nyxuri-M3-Dark/gtk-3.0/gtk.css"
            before = palette.read_bytes()
            result = subprocess.CompletedProcess([], 0, "'Nyxuri-M3-Dark'\n")
            with patch.dict(os.environ, {"NYXURI_GTK3_REFRESH": "1"}), \
                 patch("personal.gtk3.core.timed_run", return_value=result) as run:
                with gtk3.environment():
                    self.assertEqual(os.environ["NYXURI_GTK_THEME_DARK"], "Nyxuri-M3-Dark-Alt")
                    self.assertEqual(os.environ["NYXURI_GTK_THEME_LIGHT"], "Nyxuri-M3-Light")
            run.assert_called_once_with(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                                        3, capture_output=True, text=True, check=False)
            self.assertEqual(palette.read_bytes(), before)

    def test_unowned_user_css_is_not_overwritten(self):
        with TempEnv() as ctx:
            _, css = self.prepare_palettes(ctx)
            css.write_text("/* my independent stylesheet */\n")
            with self.assertRaisesRegex(ValueError, "unowned changes"):
                with gtk3.environment():
                    self.fail("Unowned CSS must not be migrated")
            self.assertEqual(css.read_text(), "/* my independent stylesheet */\n")

    def test_unowned_theme_wrapper_does_not_retire_user_css(self):
        with TempEnv() as ctx:
            themes, css = self.prepare_palettes(ctx)
            before = css.read_bytes()
            base = themes / "Nyxuri-M3-Dark/gtk-3.0/base.css"
            base.write_text("/* independent file */\n")
            with self.assertRaisesRegex(ValueError, "unowned GTK theme"):
                with gtk3.environment():
                    self.fail("Unowned theme files must not be replaced")
            self.assertEqual(css.read_bytes(), before)
            self.assertEqual(base.read_text(), "/* independent file */\n")

    def test_missing_palette_does_not_migrate_or_override(self):
        with TempEnv() as ctx:
            themes, css = self.prepare_palettes(ctx)
            before = css.read_bytes()
            (themes / "Nyxuri-M3-Light/gtk-3.0/gtk.css").unlink()
            with gtk3.environment():
                self.assertNotIn("NYXURI_GTK_THEME_LIGHT", os.environ)
                self.assertNotIn("NYXURI_GTK_THEME_DARK", os.environ)
            self.assertEqual(css.read_bytes(), before)

    def test_theme_status_and_invalid_arguments_do_not_migrate(self):
        with TempEnv() as ctx:
            _, css = self.prepare_palettes(ctx)
            before = css.read_bytes()
            with patch("nyxuri.cli.main") as main, patch("personal.gtk3.environment") as bridge:
                for arguments in (["theme", "status"], ["theme", "unknown"], ["theme", "sync", "extra"]):
                    self.assertEqual(entry.dispatch(arguments), 0)
            self.assertEqual(main.call_count, 3)
            bridge.assert_not_called()
            self.assertEqual(css.read_bytes(), before)

    def test_explicit_theme_override_survives_failed_upstream_call(self):
        with TempEnv() as ctx:
            self.prepare_palettes(ctx)
            with patch.dict(os.environ, {"NYXURI_GTK_THEME_DARK": "UserDark"}), \
                 patch("nyxuri.cli.main", side_effect=RuntimeError("upstream stopped")):
                with self.assertRaisesRegex(RuntimeError, "upstream stopped"):
                    entry.dispatch(["theme", "sync"])
                self.assertEqual(os.environ["NYXURI_GTK_THEME_DARK"], "UserDark")
                self.assertNotIn("NYXURI_GTK_THEME_LIGHT", os.environ)


if __name__ == "__main__":
    unittest.main()
