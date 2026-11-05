"""Fresh personal processes must not migrate the public manager before scoping."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import unittest

from personal import install
from tests.utils import TempEnv


def tree(root):
    """Capture exact names, types, permissions, bytes and symlink targets."""
    result = {}
    if not root.exists() and not root.is_symlink():
        return result
    for path in [root, *root.rglob("*")]:
        mode = path.lstat().st_mode
        payload = (os.readlink(path) if stat.S_ISLNK(mode) else
                   path.read_bytes() if stat.S_ISREG(mode) else None)
        result[str(path.relative_to(root))] = (mode, payload)
    return result


class PersonalInitializationTests(unittest.TestCase):
    def seed(self, ctx, legacy=None):
        public = ctx.home / ".config/nyxuri"
        presets = public / "presets/niri/mine"
        presets.mkdir(parents=True)
        (presets / "sentinel").write_bytes(b"public form\x00\xff\n")
        (presets / "link").symlink_to("sentinel")
        (public / "keep").write_bytes(b"public manager\n")
        # Earlier upstream migrations must not run on personal entry either.
        for name in (".config/NyxNiri", ".local/state/NyxNiri", ".cache/NyxNiri"):
            path = ctx.home / name
            path.mkdir(parents=True)
            (path / "keep").write_bytes(b"older public sentinel\n")
        manager = ctx.home / ".config/desktop-profiles/nyxuri/manager"
        if legacy == "directory":
            (manager / "presets/mine").mkdir(parents=True)
            (manager / "presets/mine/keep").write_bytes(b"private legacy\x00\xff\n")
        elif legacy in ("symlink", "dangling"):
            manager.parent.mkdir(parents=True)
            target = ctx.home / "legacy-target"
            if legacy == "symlink":
                target.mkdir()
                (target / "keep").write_bytes(b"linked private legacy\n")
            manager.symlink_to(target)
        return public

    def launch(self, ctx, arguments, bootstrap=False):
        launcher = install.ROOT / ("install.sh" if bootstrap else "nyxuri/launcher.sh")
        command = [str(launcher), *arguments]
        result = subprocess.run(command, cwd=ctx.home, env=os.environ.copy(),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.args, command)
        return result

    def public_state(self, ctx):
        return {name: tree(ctx.home / name) for name in
                (".config/nyxuri", ".config/NyxNiri", ".local/state/nyxuri",
                 ".local/state/NyxNiri", ".cache/nyxuri", ".cache/NyxNiri")}

    def test_fresh_plan_preserves_public_paths_types_bytes(self):
        for bootstrap in (False, True):
            with self.subTest(bootstrap=bootstrap), TempEnv() as ctx:
                self.seed(ctx)
                before = tree(ctx.home)
                result = self.launch(ctx, ["install", "--plan"], bootstrap)
                self.assertEqual(tree(ctx.home), before, result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_list_keeps_public_store_and_uses_private_lock_and_marker(self):
        for arguments in (["use", "niri", "list"], ["list"]):
            with self.subTest(arguments=arguments), TempEnv() as ctx:
                self.seed(ctx)
                before = self.public_state(ctx)
                result = self.launch(ctx, arguments)
                self.assertEqual(self.public_state(ctx), before, result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stderr)
                private = ctx.home / ".local/state/nyxuri-desktop/manager"
                self.assertTrue((private / "nyxuri.lock").is_file())
                self.assertTrue((private / "nyxuri.link").is_file())
                self.assertFalse((ctx.home / ".local/state/nyxuri/nyxuri.lock").exists())
                self.assertFalse((ctx.home / ".local/state/nyxuri/nyxuri.link").exists())
                self.assertTrue((ctx.home / ".local/bin/nyxuri").is_symlink())

    def test_legacy_refusal_precedes_all_writes_in_fresh_processes(self):
        for legacy in ("directory", "symlink", "dangling"):
            for arguments in (["install", "--plan"], ["use", "niri", "list"],
                              ["list"], ["install", "--yes"]):
                with self.subTest(legacy=legacy, arguments=arguments), TempEnv() as ctx:
                    self.seed(ctx, legacy)
                    before = tree(ctx.home)
                    result = self.launch(ctx, arguments)
                    self.assertEqual(tree(ctx.home), before, result.stdout + result.stderr)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("explicit migration", result.stderr)

    def test_install_lock_precedes_missing_kitty_failure_without_public_writes(self):
        with TempEnv() as ctx:
            self.seed(ctx)
            before = self.public_state(ctx)
            result = self.launch(ctx, ["install", "--yes"])
            self.assertEqual(self.public_state(ctx), before, result.stdout + result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Existing Kitty settings are required", result.stderr)
            self.assertTrue((ctx.home / ".local/state/nyxuri-desktop/manager/nyxuri.lock").is_file())
            self.assertFalse((ctx.home / ".local/state/nyxuri/nyxuri.lock").exists())

    def test_direct_installer_rejects_legacy_before_preflight_or_writes(self):
        with TempEnv() as ctx:
            self.seed(ctx, "directory")
            before = tree(ctx.home)
            script = ("import sys; sys.path.insert(0, " + repr(str(install.ROOT)) + "); "
                      "from nyxuri import core; from personal import install; "
                      "assert core._ENV is None; "
                      "install.main(['--plan'], preflight=lambda env: (_ for _ in ()).throw(AssertionError('preflight'))) ")
            result = subprocess.run([sys.executable, "-I", "-S", "-c", script],
                                    env=os.environ.copy(), capture_output=True, text=True, timeout=30)
            self.assertEqual(tree(ctx.home), before, result.stdout + result.stderr)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("explicit migration", result.stderr)
            self.assertNotIn("AssertionError: preflight", result.stderr)

    def test_normal_public_environment_still_migrates_presets(self):
        with TempEnv() as ctx:
            public = self.seed(ctx)
            before = tree(public / "presets")
            script = ("import sys; sys.path.insert(0, " + repr(str(install.ROOT)) + "); "
                      "from nyxuri import core; assert core._ENV is None; core.get_env()")
            result = subprocess.run([sys.executable, "-I", "-S", "-c", script],
                                    env=os.environ.copy(), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((public / "presets").exists())
            self.assertEqual(tree(public / "forms"), before)
