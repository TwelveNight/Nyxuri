"""Direct rendering and one-way preview contracts, isolated from the desktop."""
import json
import os
import tomllib
import unittest
from unittest.mock import Mock, patch

from personal import wallpaper, install
from tests.utils import TempEnv


class TestPersonalWallpaper(unittest.TestCase):
    def test_apply_socket_request_disables_transition_for_static_and_video(self):
        for suffix, kind in ((".png", "static"), (".mp4", "video")):
            with self.subTest(kind=kind), TempEnv() as ctx:
                image = ctx.home / ("space ; image" + suffix)
                image.write_bytes(b"image")
                client = Mock()
                socket_context = Mock(__enter__=Mock(return_value=client), __exit__=Mock(return_value=False))
                reader = Mock(readline=Mock(return_value=b'{"id":1,"result":{"applied":"ok"}}\n'))
                client.makefile.return_value = Mock(__enter__=Mock(return_value=reader), __exit__=Mock(return_value=False))
                with patch.dict(os.environ, SKWD_WALL_V2_SOCK=str(ctx.home / "wall.sock")), patch.object(wallpaper.socket, "socket", return_value=socket_context), patch.object(wallpaper.subprocess, "run") as run:
                    wallpaper.apply(str(image), "DP-1")
                client.connect.assert_called_once_with(str(ctx.home / "wall.sock"))
                self.assertEqual(json.loads(client.sendall.call_args.args[0]), {
                    "id": 1, "method": "wall.apply", "params": {
                        "path": str(image), "type": kind, "no_transition": True, "notify": False, "output": "DP-1"}})
                run.assert_not_called()

    def test_rpc_error_is_not_treated_as_success(self):
        with TempEnv() as ctx:
            image = ctx.home / "a.png"
            image.write_bytes(b"image")
            client = Mock()
            reader = Mock(readline=Mock(return_value=b'{"id":1,"error":{"message":"renderer failed"}}\n'))
            client.makefile.return_value = Mock(__enter__=Mock(return_value=reader), __exit__=Mock(return_value=False))
            with patch.object(wallpaper.socket, "socket", return_value=Mock(__enter__=Mock(return_value=client), __exit__=Mock(return_value=False))):
                with self.assertRaisesRegex(ValueError, "renderer failed"):
                    wallpaper.apply(str(image))

    def test_current_supports_named_output_maps(self):
        reply = {"outputs": {"DP-1": {"path": "/a.png"}, "DP-2": {"connected": False}}}
        with TempEnv(), patch.object(wallpaper.subprocess, "run", return_value=Mock(stdout=json.dumps(reply))) as run:
            self.assertEqual(wallpaper.current(), [{"name": "DP-1", "path": "/a.png"}])
            self.assertEqual(run.call_args.args[0], ["skwd-helm", "current", "--json"])

    def test_sync_only_updates_noctalia_and_skips_unchanged_preview(self):
        with TempEnv(), patch.object(wallpaper, "current", return_value=[{"name": "DP-1"}, {"name": "DP-2"}]), patch.object(wallpaper, "preview", return_value="/preview.png"), patch.object(wallpaper.subprocess, "run", side_effect=[Mock(returncode=0, stdout="/old.png"), Mock(returncode=0), Mock(returncode=0, stdout="/preview.png")]) as run:
            wallpaper.sync()
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ["noctalia", "msg", "wallpaper-get", "DP-1"],
            ["noctalia", "msg", "wallpaper-set", "DP-1", "/preview.png"],
            ["noctalia", "msg", "wallpaper-get", "DP-2"]])


    def test_bar_wallpaper_opens_skwd_frontend(self):
        with TempEnv() as ctx:
            source = ctx.home / "sources"
            source.mkdir()
            install.prepare_sources(source)
            policy = tomllib.loads((source / "noctalia/zz-personal.toml").read_text())
            config = tomllib.loads((source / "noctalia/noctalia-config.toml").read_text())
            self.assertEqual(policy["widget"]["wallpaper"]["actions"]["left"], "exec skwd-wall-v2")
            self.assertIn("wallpaper", config["bar"]["bar"]["start"])
            self.assertFalse(config["wallpaper"]["enabled"])
            self.assertEqual(config["hooks"]["wallpaper_changed"], ["python3 ~/.config/nyxuri-desktop/niri/scripts/wallpaper.py hook"])

    def test_hook_routes_user_choice_but_ignores_preview_echo(self):
        with TempEnv() as ctx, patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home), NOCTALIA_WALLPAPER_PATH="/new.png", NOCTALIA_WALLPAPER_CONNECTOR="DP-1"), patch.object(wallpaper, "current", return_value=[]), patch.object(wallpaper, "apply") as apply:
            wallpaper.hook()
            apply.assert_called_once_with("/new.png", "DP-1")
            apply.reset_mock()
            wallpaper.preview_marker("/new.png", "DP-1").touch()
            wallpaper.hook()
            apply.assert_not_called()
            self.assertFalse(wallpaper.preview_marker("/new.png", "DP-1").exists())

    def test_video_preview_never_becomes_wallpaper(self):
        with TempEnv() as ctx, patch.dict(os.environ, XDG_RUNTIME_DIR=str(ctx.home), XDG_CACHE_HOME=str(ctx.home / "cache"), NOCTALIA_WALLPAPER_PATH=str(ctx.home / "cache/nyxuri-desktop/thumbnails/a.jpg")), patch.object(wallpaper, "apply") as apply:
            wallpaper.hook()
            apply.assert_not_called()
