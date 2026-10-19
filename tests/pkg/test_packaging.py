"""Contract test for packaging/gen-deps.py — T1 single-package dependency policy.

The AUR package is a toolbox, not a desktop:

  depends    = ENGINE_DEPENDS only ('python') — pacman must not force a
               desktop onto the user
  optdepends = every unit's manifest packages (deployable + optional,
               labeled by unit) ∪ CORE_DEPS ∪ AUR_DEPS ∪ ENGINE_OPTDEPENDS
  catalog.toml never reaches the PKGBUILD — it only feeds the
  `nyxuri deps apps` menu of recommended install shortcuts.
"""

import importlib.util
import unittest
from pathlib import Path

from tests.utils import TempEnv

_GENDEPS = Path(__file__).resolve().parents[2] / "packaging" / "gen-deps.py"


def _load_gendeps():
    spec = importlib.util.spec_from_file_location("gendeps", _GENDEPS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGenDeps(unittest.TestCase):
    """T1 policy: depends=engine-only; optdepends=units ∪ session ∪ engine bases."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()
        self.repo_root = self._ctx.env.repo_dir
        self.gendeps = _load_gendeps()
        self.depends, self.optdepends = self.gendeps.compute_depends(self.repo_root)
        self.opt_names = [p for p, _ in self.optdepends]

    def tearDown(self):
        self._ctx.__exit__()

    def test_depends_is_engine_runtime_only(self):
        # The whole tree is pure Python + QML + scripts: pacman installs the
        # toolbox, the desktop is assembled later via `nyxuri on <unit>`.
        self.assertEqual(self.depends, ["python"])

    def test_unit_packages_land_in_optdepends_labeled_by_unit(self):
        # Deployable units' packages (kitty/niri/fish/...), companion libs
        # (noctalia's python-gobject/gtk-layer-shell/wl-clipboard) and the
        # portal unit all surface as optdepends with their unit label.
        for pkg in ("kitty", "niri", "fish", "fastfetch", "noctalia",
                    "python-gobject", "gtk-layer-shell", "wl-clipboard",
                    "xdg-desktop-portal", "starship"):
            self.assertIn(pkg, self.opt_names)
        labels = dict(self.optdepends)
        self.assertEqual(labels["niri"], "niri")
        self.assertEqual(labels["python-gobject"], "noctalia")
        self.assertEqual(labels["python-cairo"], "noctalia")
        self.assertEqual(labels["xdg-desktop-portal"], "XDG Portals")

    def test_session_toolchain_lands_in_optdepends(self):
        # CORE_DEPS/AUR_DEPS are the session toolchain — optdepends, never hard.
        for pkg in ("wlsunset", "eza", "jq", "tmux", "inotify-tools", "fzf",
                    "ttf-jetbrains-mono", "ttf-jetbrains-mono-nerd",
                    "noto-fonts-cjk", "qt6-imageformats", "cliphist", "mpvpaper"):
            self.assertIn(pkg, self.opt_names)

    def test_engine_optdepends_and_known_gap(self):
        # quickshell is spawned by the shipped Shell tree → ENGINE_OPTDEPENDS.
        self.assertIn("quickshell", self.opt_names)
        self.assertEqual(
            dict(self.optdepends)["quickshell"], "Nyxuri Shell runtime")
        # 31 shell QML files import Qt5Compat.GraphicalEffects and quickshell
        # does not depend on qt6-5compat — the chroot build's namcap found it.
        self.assertIn("qt6-5compat", self.opt_names)
        # key-cli is a deliberate known gap (Clavis upstream backend, planned
        # to be brought in-repo): it must NOT silently appear here.
        self.assertNotIn("key-cli", self.opt_names)

    def test_optional_unit_packages_stay_optdepends(self):
        # Optional units (zed/fcitx5-rime/greeter/mango) are optdepends —
        # nothing they declare may re-enter hard depends.
        for pkg in ("zed", "rime-ice-git", "greetd", "noctalia-greeter", "mangowm"):
            self.assertNotIn(pkg, self.depends)
            self.assertIn(pkg, self.opt_names)

    def test_catalog_shortcut_apps_stay_out_of_pkgbuild(self):
        # catalog.toml is the `deps apps` menu — recommended install
        # shortcuts are not package dependencies and must never leak.
        for shortcut in ("nautilus", "mission-center", "kdenlive",
                         "libreoffice-fresh", "lutris", "motrix", "obs-studio",
                         "protonplus", "steam", "telegram-desktop",
                         "visual-studio-code-bin", "brave-origin-bin",
                         "flclash-bin", "shelly-bin"):
            self.assertNotIn(shortcut, self.depends, shortcut)
            self.assertNotIn(shortcut, self.opt_names, shortcut)

    def test_flatpak_ids_stay_out_of_pkgbuild(self):
        # Flathub app IDs are not pacman packages — never declared anywhere.
        for flatpak_id in ("com.qq.QQ", "com.tencent.WeChat", "com.spotify.Client"):
            self.assertNotIn(flatpak_id, self.depends)
            self.assertNotIn(flatpak_id, self.opt_names)
        for leaked in ("qq", "wechat", "spotify"):
            self.assertNotIn(leaked, self.depends, leaked)
            self.assertNotIn(leaked, self.opt_names, leaked)

    def test_optdepends_is_deduplicated_and_labeled(self):
        # Several units may declare the same package (e.g. CORE_DEPS ∩ unit
        # manifests) — first claim wins, no duplicates may survive.
        self.assertEqual(len(self.opt_names), len(set(self.opt_names)))
        for pkg, label in self.optdepends:
            self.assertTrue(label, f"optdepends entry {pkg} needs a label")

    def test_render_and_update_roundtrip(self):
        rendered = self.gendeps._render(self.depends, self.optdepends)
        self.assertIn("depends=(", rendered)
        self.assertIn("optdepends=(", rendered)
        self.assertIn("'python'", rendered)
        self.assertIn("'quickshell: Nyxuri Shell runtime'", rendered)
        # update_pkgbuild() rewrites the real PKGBUILD on disk — maintainer
        # script (gen-deps --update), not test-covered. Tests assert the
        # pure _render() output only.


if __name__ == "__main__":
    unittest.main()
