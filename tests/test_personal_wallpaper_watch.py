"""Exercise the real watcher with private external-command fixtures."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

from personal import wallpaper
from tests.utils import TempEnv


class TestPersonalWallpaperWatch(unittest.TestCase):
    def test_unlock_retries_deferred_sync_without_another_wallpaper_event(self):
        with TempEnv() as ctx:
            binary = ctx.home / "bin"
            binary.mkdir()
            image = ctx.home / "wallpaper.png"
            image.write_bytes(b"image")
            (ctx.home / "locked").touch()
            fixture = r"""#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time
home = Path.home()
args = sys.argv[1:]
if Path(sys.argv[0]).name == 'skwd-helm':
    if args == ['watch']:
        print('initial', flush=True)
        while True:
            time.sleep(60)
    assert args == ['current', '--json'], args
    print(json.dumps({'outputs': [{'name': 'DP-1', 'path': str(home / 'wallpaper.png')}]}))
elif args == ['msg', 'status']:
    print(json.dumps({'locked': (home / 'locked').exists()}), flush=True)
    with (home / 'status-read').open('a') as log:
        log.write('read\n')
elif args == ['msg', 'wallpaper-get', 'DP-1']:
    print(home / 'wallpaper.png')
elif args == ['msg', 'config-get', 'lockscreen.wallpaper']:
    print("''")
else:
    assert args == ['msg', 'config-set', 'lockscreen.wallpaper', json.dumps(str(home / 'wallpaper.png'), ensure_ascii=False)], args
    (home / 'lock-written').write_text(json.dumps(args))
"""
            for name in ("skwd-helm", "noctalia"):
                executable = binary / name
                executable.write_text(fixture)
                executable.chmod(0o755)
            env = os.environ.copy()
            env.update(PATH=str(binary) + os.pathsep + env["PATH"], XDG_RUNTIME_DIR=str(ctx.home))
            process = subprocess.Popen([sys.executable, str(Path(wallpaper.__file__)), "watch"],
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while process.poll() is None and time.monotonic() < deadline:
                    if (ctx.home / "status-read").exists() and len((ctx.home / "status-read").read_text().splitlines()) >= 2:
                        break
                    time.sleep(0.05)
                self.assertTrue((ctx.home / "status-read").exists(), "watcher never queried lock status")
                self.assertGreaterEqual(len((ctx.home / "status-read").read_text().splitlines()), 2)
                self.assertFalse((ctx.home / "lock-written").exists())
                # The skwd stream stays silent: only the deferred retry can recover.
                (ctx.home / "locked").unlink()
                deadline = time.monotonic() + 5
                while not (ctx.home / "lock-written").exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue((ctx.home / "lock-written").exists(), "unlock did not retry pending wallpaper sync")
                self.assertEqual(json.loads((ctx.home / "lock-written").read_text()), [
                    "msg", "config-set", "lockscreen.wallpaper", json.dumps(str(image), ensure_ascii=False)])
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=5)
