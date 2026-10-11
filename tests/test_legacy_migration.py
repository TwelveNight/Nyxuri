"""Legacy storage migration must never lose data.

Regression guard: when a file existed in the legacy tree and the destination
already held the same name as a BROKEN symlink, _merge_directory_contents
skipped the copy but still reported success — so _safe_migrate_storage_dir
deleted the legacy tree and the user's file was gone with no error.
"""

import tempfile
import unittest
from pathlib import Path

from nyxuri.core import _merge_directory_contents, _safe_migrate_storage_dir


class TestLegacyStorageMigration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _pair(self, name):
        legacy = self.tmp / f"{name}-legacy"
        target = self.tmp / f"{name}-target"
        legacy.mkdir()
        target.mkdir()
        return legacy, target

    def test_clean_migration_moves_and_removes_legacy(self):
        legacy, target = self._pair("clean")
        (legacy / "x.txt").write_text("X")
        _safe_migrate_storage_dir(legacy, target)
        self.assertEqual((target / "x.txt").read_text(), "X")
        self.assertFalse(legacy.exists())

    def test_existing_target_file_wins_and_legacy_is_removed(self):
        legacy, target = self._pair("existing")
        (legacy / "y.txt").write_text("Y")
        (target / "y.txt").write_text("EXISTING")
        _safe_migrate_storage_dir(legacy, target)
        self.assertEqual((target / "y.txt").read_text(), "EXISTING")
        self.assertFalse(legacy.exists())

    def test_valid_symlink_target_is_treated_as_present(self):
        legacy, target = self._pair("validlink")
        (legacy / "z.txt").write_text("Z")
        (target / "real.txt").write_text("REAL")
        (target / "z.txt").symlink_to(target / "real.txt")
        _safe_migrate_storage_dir(legacy, target)
        self.assertFalse(legacy.exists())
        self.assertEqual((target / "z.txt").read_text(), "REAL")

    def test_broken_symlink_target_keeps_legacy_tree(self):
        legacy, target = self._pair("brokenlink")
        (legacy / "a.txt").write_text("IMPORTANT USER DATA")
        (legacy / "b.txt").write_text("also important")
        (target / "a.txt").symlink_to(self.tmp / "does-not-exist")

        _safe_migrate_storage_dir(legacy, target)

        self.assertTrue(legacy.exists(), "legacy tree must survive an incomplete merge")
        self.assertEqual((legacy / "a.txt").read_text(), "IMPORTANT USER DATA")
        self.assertEqual((legacy / "b.txt").read_text(), "also important")

    def test_merge_reports_failure_for_broken_symlink_target(self):
        legacy, target = self._pair("report")
        (legacy / "a.txt").write_text("DATA")
        (target / "a.txt").symlink_to(self.tmp / "nope")
        self.assertFalse(_merge_directory_contents(legacy, target))

    def test_nested_merge_copies_missing_files(self):
        legacy, target = self._pair("nested")
        (legacy / "sub").mkdir()
        (legacy / "sub" / "deep.txt").write_text("DEEP")
        (target / "sub").mkdir()
        (target / "sub" / "old.txt").write_text("OLD")
        _safe_migrate_storage_dir(legacy, target)
        self.assertEqual((target / "sub" / "deep.txt").read_text(), "DEEP")
        self.assertEqual((target / "sub" / "old.txt").read_text(), "OLD")
        self.assertFalse(legacy.exists())

    def test_symlinked_legacy_dir_is_removed_not_followed(self):
        real = self.tmp / "real"
        real.mkdir()
        (real / "keep.txt").write_text("KEEP")
        link = self.tmp / "legacy-link"
        link.symlink_to(real)

        _safe_migrate_storage_dir(link, self.tmp / "target-link")

        self.assertFalse(link.exists())
        self.assertTrue((real / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
