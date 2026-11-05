"""Personal adapter follows the plugins/forms contract without shared writes."""
import unittest
from pathlib import Path
from unittest.mock import patch

from nyxuri import core
from nyxuri.kernel import registry
from personal import entry, install
from tests.utils import TempEnv


class PersonalPluginIntegrationTests(unittest.TestCase):
    def test_installer_uses_prepared_plugins_and_preserves_other_desktop(self):
        with TempEnv() as ctx:
            kitty = ctx.env.config_dir / 'kitty'
            kitty.mkdir()
            (kitty / 'kitty.conf').write_text('shell zsh\n')
            other = ctx.env.config_dir / 'desktop-profiles/inir/niri'
            other.mkdir(parents=True)
            (other / 'config.kdl').write_text('// other desktop sentinel\n')
            canonical = ctx.env.config_dir / 'niri'
            canonical.symlink_to(other)
            with patch('personal.install.shutil.which', return_value='/usr/bin/tool'), patch('personal.assets.get_pics_dir', return_value=ctx.home/'Pictures'):
                self.assertEqual(install.main(['--yes']), 0)
            private = ctx.env.config_dir / 'desktop-profiles/nyxuri'
            config = (private/'niri/config.kdl').read_text()
            self.assertIn('personal-binds.kdl', config)
            self.assertIn('personal-overview.kdl', config)
            self.assertIn('QT_QPA_PLATFORMTHEME "kde"', config)
            self.assertTrue((private/'kitty-nyxuri/kitty.conf').is_file())
            self.assertTrue((private/'noctalia/zz-personal.toml').is_file())
            self.assertEqual(canonical.resolve(), other)
            self.assertEqual((canonical/'config.kdl').read_text(), '// other desktop sentinel\n')
            self.assertFalse((ctx.env.config_dir/'kitty-nyxuri').exists())
            self.assertFalse((ctx.env.config_dir/'nyxuri').exists())

    def test_use_scopes_all_registry_roots_and_private_state(self):
        with TempEnv() as ctx:
            marker = ctx.env.config_dir/'desktop-profiles/profiles.json'
            marker.parent.mkdir()
            marker.write_text('{}')
            original = core._ENV
            def inspect():
                env = core.get_env()
                self.assertEqual(env.config_dir, ctx.env.config_dir/'desktop-profiles/nyxuri')
                self.assertEqual(env.forms_dir, env.nyx_dir/'forms')
                self.assertTrue(env.nyx_dir.is_relative_to(env.config_dir))
                self.assertEqual(env.state_dir, ctx.home/'.local/state/nyxuri-desktop/manager')
                self.assertEqual(env.data_dir, ctx.home/'.local/share/nyxuri-desktop/manager')
                self.assertEqual(set(registry.plugin_ids()), set(install.CONFIGS))
                self.assertEqual(registry.plugin_dir('niri'), env.plugins_src/'niri')
            with patch('nyxuri.cli.main', side_effect=inspect), patch.object(entry.subprocess, 'run') as run:
                self.assertEqual(entry.dispatch(['use','niri','effects','default']), 0)
                run.assert_called_once_with([str(ctx.home/'.local/bin/desktop-profile'),'guard','nyxuri'],check=True)
            self.assertIs(core._ENV, original)

    def test_new_mutating_plugin_routes_cannot_escape_personal_policy(self):
        with TempEnv() as ctx:
            marker = ctx.env.config_dir/'desktop-profiles/profiles.json'
            marker.parent.mkdir()
            marker.write_text('{}')
            with patch('nyxuri.cli.main') as main, patch.object(entry.subprocess,'run') as run:
                for args in (['use','fish','default'],['use','shell.bar','default'],['add','https://example.invalid/p'],['remove','org.example.p']):
                    with self.subTest(args=args):
                        self.assertEqual(entry.dispatch(args), 2)
                main.assert_not_called()
                run.assert_not_called()

    def test_install_lock_uses_the_private_state_root(self):
        with TempEnv() as ctx:
            original = core._ENV
            def inspect():
                self.assertEqual(core.get_env().state_dir, ctx.home/'.local/state/nyxuri-desktop/manager')
            with patch('nyxuri.core.acquire_lock', side_effect=inspect), patch('nyxuri.core.release_lock'), patch('personal.entry.install.main', return_value=1):
                self.assertEqual(entry.install_desktop(['--yes']), 1)
            self.assertIs(core._ENV, original)

    def test_use_works_without_profile_registration_and_preserves_translate(self):
        from nyxuri.deploy.forms import use_form
        with TempEnv() as ctx:
            kitty = ctx.env.config_dir/'kitty'
            kitty.mkdir()
            (kitty/'kitty.conf').write_text('shell zsh\n')
            original = core._ENV
            with patch('personal.install.shutil.which',return_value='/usr/bin/tool'), patch('personal.assets.get_pics_dir',return_value=ctx.home/'Pictures'):
                self.assertEqual(install.main(['--yes']), 0)
                private = ctx.env.config_dir/'desktop-profiles/nyxuri'
                tools = private/'noctalia/tools'
                (tools/'orbit-translate.py').write_bytes(b'preserved installed launcher\n')
                package = tools/'orbit_translate'
                package.mkdir()
                (package/'providers.py').write_bytes(b'preserved personal provider repair\n')
                custom = tools/'orbit-translate__custom__.toml'
                custom.write_text('target = "zh-CN"\n')
                self.assertEqual(install.main(['--yes']),0)
            def apply():
                self.assertEqual(set(registry.plugin_ids()),set(install.CONFIGS))
                self.assertTrue(use_form('niri',None,'default'))
                self.assertTrue(use_form('niri','effects','default'))
                self.assertTrue(use_form('noctalia',None,'default'))
                self.assertTrue(use_form('kitty-nyxuri',None,'default'))
                for name in ('noctalia/zz-personal.toml','noctalia/zz-personal-appearance.toml','noctalia/zz-personal-bongocat.toml','kitty-nyxuri/kitty.conf'):
                    self.assertNotIn('/home/user',(private/name).read_text(),name)
            with patch('nyxuri.cli.main',side_effect=apply), patch.object(entry.subprocess,'run') as run:
                self.assertEqual(entry.dispatch(['use','niri','default']),0)
                run.assert_not_called()
            self.assertEqual((tools/'orbit-translate.py').read_bytes(),b'preserved installed launcher\n')
            self.assertEqual((package/'providers.py').read_bytes(),b'preserved personal provider repair\n')
            self.assertEqual(custom.read_text(),'target = "zh-CN"\n')
            self.assertIn('personal-binds.kdl',(private/'niri/config.kdl').read_text())
            self.assertFalse((ctx.env.config_dir/'nyxuri').exists())
            self.assertIs(core._ENV, original)

    def test_registration_records_launcher_under_private_state(self):
        with TempEnv() as ctx:
            original = core._ENV
            def inspect():
                self.assertEqual(core.get_env().state_dir, ctx.home/'.local/state/nyxuri-desktop/manager')
            with patch('personal.entry.needs_session_entry',return_value=False), patch.object(entry.subprocess,'run') as run, patch('nyxuri.core.ensure_nyxuri_symlink',side_effect=inspect):
                entry.register_session(ctx.env)
                run.assert_called_once_with(['systemctl','--user','daemon-reload'],check=True)
            self.assertIs(core._ENV,original)

    def test_legacy_manager_is_a_read_only_migration_blocker(self):
        with TempEnv() as ctx:
            legacy = ctx.env.config_dir/'desktop-profiles/nyxuri/manager/presets'
            legacy.mkdir(parents=True)
            (legacy/'mine').write_text('old user form\n')
            with self.assertRaisesRegex(ValueError,'explicit migration'):
                install.scoped_environment(ctx.env)
            self.assertEqual((legacy/'mine').read_text(),'old user form\n')
            self.assertFalse((legacy.parent.parent/'nyxuri').exists())
