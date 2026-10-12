"""Launcher IPC stays display-scoped and never toggles twice after a failure."""
import os
import unittest
from unittest.mock import Mock, patch

from personal import install, launcher
from tests.utils import TempEnv


class PersonalLauncherTests(unittest.TestCase):
    def test_installed_entry_is_executable_and_uses_no_site_startup(self):
        with TempEnv() as ctx:
            stage = ctx.home / "source"
            stage.mkdir()
            install.prepare_sources(stage)
            entry = stage / "niri/scripts/launcher.py"
            self.assertTrue(os.access(entry, os.X_OK))
            self.assertEqual(entry.read_text().splitlines()[0], "#!/usr/bin/python3 -S")

    def test_display_scoped_request_reads_fragmented_reply(self):
        with TempEnv() as ctx:
            client = Mock()
            client.recv.side_effect = [b"o", b"k\n", b""]
            connection = Mock(__enter__=Mock(return_value=client), __exit__=Mock(return_value=False))
            with patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home), WAYLAND_DISPLAY="wayland-9"), patch.object(launcher.socket, "socket", return_value=connection) as create:
                self.assertEqual(launcher.main(), 0)
            create.assert_called_once_with(launcher.socket.AF_UNIX, launcher.socket.SOCK_STREAM)
            client.connect.assert_called_once_with(str(ctx.home / "noctalia-wayland-9.sock"))
            client.settimeout.assert_called_once_with(2)
            client.sendall.assert_called_once_with(b"panel-toggle launcher")
            client.shutdown.assert_called_once_with(launcher.socket.SHUT_WR)

    def test_failed_or_missing_reply_does_not_resend_toggle(self):
        for reply in ([b"err", b"or: unknown command\n", b""], [b""], [TimeoutError("timeout")]):
            with self.subTest(reply=reply), TempEnv() as ctx:
                client = Mock()
                client.recv.side_effect = reply
                connection = Mock(__enter__=Mock(return_value=client), __exit__=Mock(return_value=False))
                with patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home), WAYLAND_DISPLAY="wayland-9"), patch.object(launcher.socket, "socket", return_value=connection), patch.object(launcher.sys, "stderr"):
                    self.assertEqual(launcher.main(), 1)
                client.sendall.assert_called_once_with(b"panel-toggle launcher")
