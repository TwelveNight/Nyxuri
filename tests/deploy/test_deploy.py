"""Behavior contracts for deploy: atomic replace rollback, broken symlink, no-clobber.

Safety: all tests use tempfile.TemporaryDirectory for filesystem operations.
No test touches the real ~/.config or the real repo configs/ directory.
"""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.utils import TempEnv


class TestAtomicReplaceFileRollback(unittest.TestCase):
    """If the 2nd rename fails, dest must be restored from old_dest."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__()

    def test_file_replace_rollback_on_second_rename_failure(self):
        """If tmp_file.rename(dest) fails, dest must be restored from old_dest."""
        from nyxuri.deploy.atomic import atomic_replace_item

        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            src = workdir / "src.txt"
            src.write_text("new")
            dest = workdir / "dest.txt"
            dest.write_text("original")

            original_rename = Path.rename

            def fail_second_rename(self_path, target):
                if ".new." in self_path.name and target == dest:
                    raise OSError("simulated rename failure")
                return original_rename(self_path, target)

            with patch.object(Path, "rename", fail_second_rename):
                result = atomic_replace_item(src, dest)

            self.assertFalse(result, "Should return False on failure")
            self.assertTrue(dest.exists(), "dest must still exist (restored)")
            self.assertEqual(dest.read_text(), "original",
                             "dest content must be the original, not 'new'")

    def test_file_replace_normal_success(self):
        """Normal file replace should succeed."""
        from nyxuri.deploy.atomic import atomic_replace_item

        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            src = workdir / "src.txt"
            src.write_text("new content")
            dest = workdir / "dest.txt"
            dest.write_text("old content")

            result = atomic_replace_item(src, dest)
            self.assertTrue(result)
            self.assertEqual(dest.read_text(), "new content")


class TestAtomicReplaceDirRollback(unittest.TestCase):
    """Directory atomic replace must also rollback on failure."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__()

    def test_dir_replace_rollback_on_rename_failure(self):
        """If tmp_new.rename(dest) fails, dest must be restored from old_dest."""
        from nyxuri.deploy.atomic import atomic_replace_item

        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            src = workdir / "srcdir"
            src.mkdir()
            (src / "file.txt").write_text("new")
            dest = workdir / "dest_dir"
            dest.mkdir()
            (dest / "old.txt").write_text("original")

            original_rename = Path.rename

            def fail_final_rename(self_path, target):
                if ".new." in self_path.name and target == dest:
                    raise OSError("simulated dir rename failure")
                return original_rename(self_path, target)

            with patch.object(Path, "rename", fail_final_rename):
                result = atomic_replace_item(src, dest)

            self.assertFalse(result)
            self.assertTrue(dest.exists(), "dest must be restored")
            self.assertTrue((dest / "old.txt").exists(),
                            "Original content must survive rollback")


class TestEffectsSymlinkBroken(unittest.TestCase):
    """A broken effects.kdl symlink should be detected and recreated."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__()

    def test_broken_symlink_condition(self):
        """The deploy condition for broken symlinks must fire correctly.

        Tests in a temp directory — never touches the real repo.
        """
        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            effects_normal = workdir / "effects_normal.kdl"
            effects_normal.write_text("// normal")
            effects_sym = workdir / "effects.kdl"

            effects_sym.symlink_to(workdir / "effects_eyecare.kdl")

            self.assertTrue(effects_normal.is_file())
            self.assertFalse(effects_sym.exists(),
                             "Broken symlink should not exist() — triggers recreation")
            self.assertTrue(effects_sym.is_symlink())

            if effects_normal.is_file() and not effects_sym.exists():
                effects_sym.unlink(missing_ok=True)
                effects_sym.symlink_to(effects_normal)

            self.assertTrue(effects_sym.exists())
            self.assertEqual(effects_sym.resolve(), effects_normal.resolve())


class TestPreserveInjectionBeforeSwap(unittest.TestCase):
    """manifest preserve files must be in tmp_new BEFORE rename — no post-swap window."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__()

    def test_preserve_file_survives_swap_with_user_content(self):
        """preserve=["monitor.kdl"] → dest/monitor.kdl keeps user's content, not repo's."""
        from nyxuri.deploy.atomic import atomic_replace_item

        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            src = workdir / "srcdir"
            src.mkdir()
            (src / "config.kdl").write_text("new config")
            (src / "monitor.kdl").write_text("repo default")  # would clobber user's

            dest = workdir / "dest_dir"
            dest.mkdir()
            (dest / "config.kdl").write_text("old config")
            (dest / "monitor.kdl").write_text("user monitors")  # must survive

            result = atomic_replace_item(src, dest, preserve=["monitor.kdl"])

            self.assertTrue(result)
            self.assertEqual((dest / "config.kdl").read_text(), "new config")
            self.assertEqual((dest / "monitor.kdl").read_text(), "user monitors",
                             "preserve file must keep user content, not repo default")

    def test_preserve_skipped_when_dest_file_missing(self):
        """preserve on a non-existent file is a no-op, swap still succeeds."""
        from nyxuri.deploy.atomic import atomic_replace_item

        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            src = workdir / "srcdir"
            src.mkdir()
            (src / "config.kdl").write_text("new")

            dest = workdir / "dest_dir"
            dest.mkdir()
            (dest / "config.kdl").write_text("old")

            result = atomic_replace_item(src, dest, preserve=["monitor.kdl"])

            self.assertTrue(result)
            self.assertFalse((dest / "monitor.kdl").exists(),
                             "No monitor.kdl in dest → repo's (absent) ships, no crash")


class TestPreserveValuesAcrossSwap(unittest.TestCase):
    """manifest preserve_values must carry individual keys into the staged tree."""

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__()

    def _swap(self, src_text, dest_text, keys, rel="app-config.toml"):
        from nyxuri.deploy.atomic import atomic_replace_item

        workdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, workdir, True)
        src = workdir / "srcdir"
        src.mkdir()
        (src / rel).write_text(src_text)
        (src / "extra.conf").write_text("shipped")
        dest = workdir / "dest_dir"
        dest.mkdir()
        if dest_text is not None:
            (dest / rel).write_text(dest_text)
        result = atomic_replace_item(src, dest, preserve_values={rel: keys})
        self.assertTrue(result)
        return (dest / rel).read_text()

    def test_user_value_survives_swap(self):
        """The shipped default must not clobber a value the user turned on."""
        text = self._swap(
            "[brightness]\nenable_ddcutil = false\nother = 2\n",
            "[brightness]\nenable_ddcutil = true\nother = 1\n",
            ["enable_ddcutil"],
        )
        self.assertIn("enable_ddcutil = true", text)
        self.assertNotIn("enable_ddcutil = false", text)

    def test_missing_key_falls_back_to_shipped_default(self):
        """A key the user never set must keep the shipped value."""
        text = self._swap(
            "[brightness]\nenable_ddcutil = false\n",
            "[brightness]\nother = 1\n",
            ["enable_ddcutil"],
        )
        self.assertIn("enable_ddcutil = false", text)

    def test_missing_dest_file_falls_back_to_shipped_default(self):
        """First deploy has nothing to carry → the shipped value ships."""
        text = self._swap(
            "[brightness]\nenable_ddcutil = false\n",
            None,
            ["enable_ddcutil"],
        )
        self.assertIn("enable_ddcutil = false", text)

    def test_undeclared_keys_still_come_from_the_shipped_file(self):
        """Only declared keys carry over; every other line updates normally."""
        text = self._swap(
            "[brightness]\nenable_ddcutil = false\nother = 2\n",
            "[brightness]\nenable_ddcutil = true\nother = 1\n",
            ["enable_ddcutil"],
        )
        self.assertIn("other = 2", text)
        self.assertNotIn("other = 1", text)

    def test_comment_and_formatting_of_shipped_file_are_kept(self):
        """The swap must not graft the outgoing file's comments onto the new one."""
        text = self._swap(
            "[brightness]\n# shipped note\nenable_ddcutil = false\n",
            "[brightness]\n# user note\nenable_ddcutil = true\n",
            ["enable_ddcutil"],
        )
        self.assertIn("# shipped note", text)
        self.assertNotIn("# user note", text)

    def test_same_key_name_in_another_section_is_untouched(self):
        """Carrying is section-scoped, so an unrelated homonym cannot be rewritten."""
        text = self._swap(
            "[a]\nenabled = false\n\n[b]\nenabled = false\n",
            "[a]\nenabled = true\n\n[b]\nenabled = false\n",
            ["enabled"],
        )
        self.assertIn("[a]\nenabled = true", text)
        self.assertIn("[b]\nenabled = false", text)

    def test_absent_key_in_shipped_file_is_not_appended(self):
        """A key the shipped file dropped stays dropped instead of being re-added."""
        text = self._swap(
            "[brightness]\nremoved = true\n",
            "[brightness]\nenable_ddcutil = true\n",
            ["enable_ddcutil"],
        )
        self.assertNotIn("enable_ddcutil", text)

    def test_declared_target_absent_from_staged_tree_is_skipped(self):
        """A declared path that the shipped tree does not contain is ignored."""
        from nyxuri.deploy.atomic import atomic_replace_item

        workdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, workdir, True)
        src = workdir / "srcdir"
        src.mkdir()
        (src / "app-config.toml").write_text("[brightness]\nenable_ddcutil = false\n")
        dest = workdir / "dest_dir"
        dest.mkdir()
        (dest / "app-config.toml").write_text("[brightness]\nenable_ddcutil = true\n")

        result = atomic_replace_item(
            src, dest, preserve_values={"gone.toml": ["enable_ddcutil"]})

        self.assertTrue(result)
        self.assertEqual((dest / "app-config.toml").read_text(),
                         "[brightness]\nenable_ddcutil = false\n")

    def test_declared_target_cannot_escape_the_staged_tree(self):
        """A traversal path must be refused rather than read from outside."""
        from nyxuri.deploy.atomic import atomic_replace_item

        workdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, workdir, True)
        src = workdir / "srcdir"
        src.mkdir()
        (src / "app-config.toml").write_text("[brightness]\nenable_ddcutil = false\n")
        dest = workdir / "dest_dir"
        dest.mkdir()
        (dest / "app-config.toml").write_text("[brightness]\nenable_ddcutil = true\n")
        (workdir / "outside.toml").write_text("[brightness]\nenable_ddcutil = true\n")

        result = atomic_replace_item(
            src, dest, preserve_values={"../outside.toml": ["enable_ddcutil"]})

        self.assertTrue(result)
        self.assertEqual((dest / "app-config.toml").read_text(),
                         "[brightness]\nenable_ddcutil = false\n")


class TestNiriRequiredIncludes(unittest.TestCase):
    """Every non-optional include in niri's config.kdl must exist in the repo.

    niri fails to load the whole config when a required include is missing, so a
    fresh install would break on a file the repo never shipped.
    """

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()
        self.env = self._ctx.env
        self.niri_src = self.env.units_src / "niri"

    def tearDown(self):
        self._ctx.__exit__()

    def _required_includes(self):
        text = (self.niri_src / "config.kdl").read_text(encoding="utf-8")
        return [
            m.group(1)
            for m in re.finditer(r'include\s+(?:optional=true\s+)?"([^"]+)"', text)
            if "optional=true" not in m.group(0)
        ]

    def test_all_required_includes_exist_in_source(self):
        required = self._required_includes()
        self.assertIn("effects.kdl", required)
        for name in required:
            self.assertTrue(
                (self.niri_src / name).exists(),
                f"config.kdl requires {name} but the repo does not ship it",
            )

    def test_effects_kdl_is_eyecare_symlink(self):
        link = self.niri_src / "effects.kdl"
        self.assertTrue(link.is_symlink(), "effects.kdl must stay a runtime-managed symlink")
        self.assertEqual(os.readlink(link), "effects_normal.kdl")
        self.assertTrue(link.exists(), "symlink must resolve to a shipped file")

    def test_required_includes_survive_fresh_deploy(self):
        from nyxuri.deploy.deploy import deploy_selected_configs

        # A temporary HOME does not isolate the login session's D-Bus settings.
        # Keep a command guard so this filesystem test cannot change its theme.
        with patch("builtins.print"), \
             patch("nyxuri.deploy.deploy._phase_post_install_services") as services, \
             patch("nyxuri.desktop.theme.timed_run", return_value=None) as theme_command:
            deploy_selected_configs(do_backup=False, items_to_deploy=["niri"])
        services.assert_called_once_with()
        theme_command.assert_not_called()

        dest = self.env.config_dir / "niri"
        for name in self._required_includes():
            self.assertTrue(
                (dest / name).exists(),
                f"fresh deploy left {name} missing; niri would fail to load",
            )
        deployed = dest / "effects.kdl"
        self.assertTrue(deployed.is_symlink())
        self.assertEqual(os.readlink(deployed), "effects_normal.kdl")


class TestWallpapersUnit(unittest.TestCase):
    """The wallpapers unit: merge semantics over a shared living area.

    on = no-clobber blueprint fallback; off = withdraw only laid files;
    the pack and the user's own wallpapers are never eaten, never tracked.
    """

    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()
        self.env = self._ctx.env

    def tearDown(self):
        self._ctx.__exit__()

    def _wp_dest(self):
        return self.env.home / "Pictures" / "Wallpapers"

    def test_on_lays_fallback_and_records_ledger(self):
        from nyxuri.kernel import ledger, transaction

        steps = transaction.unit_on("wallpapers")
        self.assertTrue(all(s.ok for s in steps), steps)
        dest = self._wp_dest()
        self.assertTrue((dest / "lawson_fuji.webp").is_file())
        rec = ledger.get_unit("wallpapers")
        self.assertEqual(rec["state"], "enabled")
        self.assertIn("lawson_fuji.webp", rec["files"])

    def test_on_never_clobbers_user_content(self):
        from nyxuri.kernel import ledger, transaction

        dest = self._wp_dest()
        dest.mkdir(parents=True, exist_ok=True)
        user_wp = dest / "lawson_fuji.webp"
        user_wp.write_bytes(b"USER OWN IMAGE")

        steps = transaction.unit_on("wallpapers")
        self.assertTrue(all(s.ok for s in steps), steps)
        self.assertEqual(user_wp.read_bytes(), b"USER OWN IMAGE",
                         "merge deploy must never overwrite existing files")
        # The blocked file is not ours: not in the laid snapshot.
        self.assertNotIn("lawson_fuji.webp", ledger.get_unit("wallpapers")["files"])

    def test_off_withdraws_only_laid_files(self):
        from nyxuri.kernel import transaction

        dest = self._wp_dest()
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "my_own.webp").write_bytes(b"USER")
        transaction.unit_on("wallpapers")
        (dest / "pack_video.mp4").write_bytes(b"PACK")  # arrives after on

        steps = transaction.unit_off("wallpapers")
        self.assertTrue(all(s.ok for s in steps), steps)
        self.assertFalse((dest / "lawson_fuji.webp").exists(),
                         "laid fallback must be withdrawn")
        self.assertEqual((dest / "my_own.webp").read_bytes(), b"USER")
        self.assertTrue((dest / "pack_video.mp4").exists(),
                        "pack content is user-domain and survives off")
        self.assertIn("pack_video.mp4", steps[-1].detail,
                      "foreign survivors must be reported")

    def test_disabled_shared_area_is_not_ghost(self):
        from nyxuri.kernel import transaction

        dest = self._wp_dest()
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "my_own.webp").write_bytes(b"USER")
        transaction.unit_on("wallpapers")
        transaction.unit_off("wallpapers")

        report = transaction.audit_units("wallpapers")
        self.assertEqual(report.get("wallpapers"), transaction.STATE_SYNCED,
                         "user content in a shared area is not residue")

    def test_blueprint_named_residue_is_ghost(self):
        from nyxuri.kernel import transaction

        dest = self._wp_dest()
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "lawson_fuji.webp").write_bytes(b"OLD FALLBACK RESIDUE")

        report = transaction.audit_units("wallpapers")
        self.assertEqual(report.get("wallpapers"), transaction.STATE_GHOST)


if __name__ == "__main__":
    unittest.main()
