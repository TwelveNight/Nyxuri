"""Keep the Xwayland workaround narrower than normal WPS dialogs/windows."""
import unittest
from personal import wps_toolbar


class ToolbarTests(unittest.TestCase):
    def test_only_fixed_undecorated_mini_toolbar_is_reclassified(self):
        toolbar = dict(app='wps', title='wps', size=(334, 62),
                       minimum=(334, 62), maximum=(334, 62),
                       decorations=0, transient=False,
                       types=('_KDE_NET_WM_WINDOW_TYPE_OVERRIDE', '_NET_WM_WINDOW_TYPE_NORMAL'))
        self.assertTrue(wps_toolbar.is_toolbar(**toolbar))
        for change in (
            dict(app='firefox'), dict(title='字体'), dict(title='report.doc - WPS 文字'),
            dict(minimum=None), dict(maximum=(1200, 800)), dict(decorations=1),
            dict(transient=True), dict(size=(1200, 800)),
            dict(types=('_NET_WM_WINDOW_TYPE_DIALOG',)),
            dict(types=('_NET_WM_WINDOW_TYPE_POPUP_MENU',)),
        ):
            with self.subTest(change=change):
                self.assertFalse(wps_toolbar.is_toolbar(**(toolbar | change)))

    def test_installer_deploys_helper_and_startup(self):
        from personal import install
        from tests.utils import TempEnv
        with TempEnv() as ctx:
            install.prepare_sources(ctx.home / 'configs')
            niri = ctx.home / 'configs/niri'
            self.assertEqual((niri / 'scripts/wps_toolbar.py').read_bytes(),
                             (install.ROOT / 'personal/wps_toolbar.py').read_bytes())
            self.assertIn('wps_toolbar.py', (niri / 'personal-startup.kdl').read_text())
