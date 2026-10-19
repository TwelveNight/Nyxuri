"""Only the Nyxuri deployment copy gets GTK3-compatible hover colors."""
import re
import subprocess
import sys
import unittest

from personal import install
from tests.utils import TempEnv


class PersonalGtkTests(unittest.TestCase):
    def test_private_gtk3_copy_keeps_fallbacks_without_gtk4_color_mix(self):
        with TempEnv() as ctx:
            source = ctx.home / "source"
            source.mkdir()
            originals = {name: (install.ROOT / "units/theme" / name).read_bytes()
                         for name in ("gtk-3.0.css", "gtk-4.0.css")}
            install.prepare_sources(source)
            template = source / "noctalia/templates/gtk-3.0.css"
            css = template.read_text()
            css = re.sub(r"\{\{\s*colors\.\w+\.default\.hex\s*\}\}", "#123456", css)
            css = re.sub(r"\{\{\s*colors\.\w+\.default\.rgb_csv\s*\}\}", "18,52,86", css)
            self.assertNotIn("{{", css)
            rendered = ctx.home / "rendered.css"
            rendered.write_text(css)
            probe = '''import sys
from pathlib import Path
try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
except (ImportError, ValueError):
    sys.exit(77)
errors = []
provider = Gtk.CssProvider()
provider.connect("parsing-error", lambda _provider, _section, error: errors.append(str(error)))
try:
    provider.load_from_data(Path(sys.argv[1]).read_bytes())
except Exception as error:
    errors.append(str(error))
print("\\n".join(errors))
sys.exit(bool(errors))
'''
            command = [sys.executable, "-c", probe, str(rendered)]
            self.assertEqual(command[-1], str(ctx.home / "rendered.css"))
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            if result.returncode == 77:
                self.skipTest("GTK3 introspection is not installed")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for selector in (".navigation-sidebar row:active", "switch:hover"):
                self.assertRegex(css, re.escape(selector) + r"\s*\{\s*background-color: #[0-9a-f]{6};\s*\}")
            for name, original in originals.items():
                self.assertEqual((install.ROOT / "units/theme" / name).read_bytes(), original)
            self.assertEqual((source / "noctalia/templates/gtk-4.0.css").read_bytes(), originals["gtk-4.0.css"])


if __name__ == "__main__":
    unittest.main()
