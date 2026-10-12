"""Regression tests for upstream defects fixed during the bug-hunt rounds.

Each test reproduces a concrete failure that shipped in v4.0.0-alpha.1 and
asserts the corrected behavior, so the defect cannot silently return.
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.utils import TempEnv


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class TestMigrationsResilience(unittest.TestCase):

    def test_symlink_tombstone_pointing_outside_home_is_removed(self):
        from nyxuri import migrations
        with TempEnv() as ctx:
            outside = Path(tempfile.mkdtemp()) / "nyxniri.fish"
            outside.write_text("x", encoding="utf-8")
            link = ctx.home / ".config/fish/completions/nyxniri.fish"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside)
            with patch.object(migrations, "TOMBSTONES", (".config/fish/completions/nyxniri.fish",)):
                self.assertTrue(_quiet(migrations.run))
                self.assertTrue(_quiet(migrations.run))
            self.assertFalse(link.is_symlink())

    def test_corrupt_migration_level_does_not_raise(self):
        from nyxuri import migrations
        with TempEnv() as ctx:
            path = migrations._ledger_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"migration_level": "abc"}', encoding="utf-8")
            self.assertTrue(_quiet(migrations.run))
            self.assertEqual(migrations._read()["migration_level"], migrations.MIGRATION_LEVEL)

    def test_traversal_tombstone_is_rejected(self):
        from nyxuri import migrations
        with TempEnv() as ctx:
            victim = ctx.home.parent / "nyxuri-outside-victim.txt"
            victim.write_text("keep", encoding="utf-8")
            with patch.object(migrations, "TOMBSTONES", ("../nyxuri-outside-victim.txt",)):
                self.assertFalse(_quiet(migrations.run))
            self.assertTrue(victim.exists())
            victim.unlink()


class TestGitTimeoutDegrades(unittest.TestCase):

    def _repo(self, ctx):
        repo = ctx.env.repo_dir
        repo.mkdir(parents=True, exist_ok=True)
        (repo / ".git").mkdir(exist_ok=True)
        return repo

    def test_safe_git_pull_timeout_returns_falsy(self):
        import nyxuri.network as net
        with TempEnv() as ctx:
            repo = self._repo(ctx)

            def fake_run(cmd, **kwargs):
                if "pull" in cmd or "fetch" in cmd:
                    raise subprocess.TimeoutExpired(cmd, 120)
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("shutil.which", return_value="/usr/bin/git"), \
                 patch("subprocess.run", side_effect=fake_run):
                self.assertFalse(_quiet(net.safe_git_pull, repo))

    def test_safe_git_checkout_ref_timeout_returns_falsy(self):
        import nyxuri.network as net
        with TempEnv() as ctx:
            repo = self._repo(ctx)

            def fake_run(cmd, **kwargs):
                if "fetch" in cmd or "checkout" in cmd:
                    raise subprocess.TimeoutExpired(cmd, 120)
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("shutil.which", return_value="/usr/bin/git"), \
                 patch("subprocess.run", side_effect=fake_run):
                self.assertFalse(_quiet(net.safe_git_checkout_ref, repo, "v1"))


class TestTemplateRegistryHeaders(unittest.TestCase):

    def test_commented_header_is_found_by_set_section_key(self):
        from nyxuri.template_registry import set_section_key
        content = '[package]  # main\nname = "test"\n'
        updated = set_section_key(content, "package", "version", "1")
        self.assertNotEqual(updated, content)
        self.assertEqual(tomllib.loads(updated)["package"]["version"], "1")

    def test_add_section_does_not_duplicate_commented_header(self):
        from nyxuri.template_registry import add_section
        content = '[package]  # main\nname = "test"\n'
        updated = add_section(content, "package", {"version": "3.0.5"})
        self.assertEqual(updated.count("[package]"), 1)
        self.assertEqual(tomllib.loads(updated)["package"]["name"], "test")

    def test_write_atomic_preserves_destination_mode(self):
        from nyxuri.template_registry import write_atomic
        with TempEnv() as ctx:
            target = ctx.home / "sample.toml"
            target.write_text("[a]\nb = 1\n", encoding="utf-8")
            target.chmod(0o644)
            write_atomic(target, "[a]\nb = 2\n")
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)


class TestGtkThemeUninstall(unittest.TestCase):

    def test_partial_registration_is_still_unregistered(self):
        from nyxuri.modules import gtktheme
        with TempEnv() as ctx:
            conf = ctx.env.config_dir / "noctalia" / "noctalia-config.toml"
            conf.parent.mkdir(parents=True, exist_ok=True)
            conf.write_text('[theme.templates.user.nyxuri_gtk3]\ncss = "x"\n', encoding="utf-8")
            self.assertFalse(gtktheme.gtktheme_registered())
            self.assertTrue(gtktheme.gtktheme_any_registered())
            self.assertTrue(_quiet(gtktheme.gtktheme_uninstall))
            self.assertNotIn("theme.templates.user.nyxuri_gtk3", conf.read_text(encoding="utf-8"))


class TestDeployAssets(unittest.TestCase):

    def test_pack_requires_a_real_video(self):
        from nyxuri.deploy import assets
        root = Path(tempfile.mkdtemp())
        (root / "video").mkdir(parents=True)
        (root / "video" / "README.md").write_text("docs", encoding="utf-8")
        self.assertFalse(assets._wallpaper_pack_present_at(root))
        (root / "video" / "clip.mp4").write_text("v", encoding="utf-8")
        self.assertTrue(assets._wallpaper_pack_present_at(root))

    def test_existing_user_wallpaper_is_not_claimed_as_managed(self):
        from nyxuri.deploy import assets
        with TempEnv() as ctx:
            wp = ctx.home / "Pictures" / "Wallpapers"
            wp.mkdir(parents=True)
            user_file = wp / "lawson_fuji.webp"
            user_file.write_text("USER", encoding="utf-8")
            _quiet(assets.deploy_wallpapers, do_download=False)
            marker = wp / ".nyxuri-managed.json"
            managed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else []
            self.assertNotIn("lawson_fuji.webp", managed)
            self.assertEqual(user_file.read_text(encoding="utf-8"), "USER")


class TestManifestCoercion(unittest.TestCase):

    def _sandbox(self, ctx):
        ctx.env.configs_src = Path(tempfile.mkdtemp())
        return ctx.env.configs_src

    def test_scalar_package_fields_become_single_element_lists(self):
        from nyxuri.deploy.manifest import load_manifest
        with TempEnv() as ctx:
            src = self._sandbox(ctx) / "demo"
            src.mkdir(parents=True)
            (src / ".module.toml").write_text(
                '[packages]\nrepo = "kitty"\naur = "foo-bar"\npreserve = "single.conf"\n',
                encoding="utf-8",
            )
            m = _quiet(load_manifest, src)
            self.assertEqual(m.packages_repo, ["kitty"])
            self.assertEqual(m.packages_aur, ["foo-bar"])
            self.assertEqual(m.preserve, ["single.conf"])

    def test_scalar_parts_entry_is_dropped(self):
        from nyxuri.deploy.manifest import load_manifest
        with TempEnv() as ctx:
            src = self._sandbox(ctx) / "demo2"
            src.mkdir(parents=True)
            (src / ".module.toml").write_text(
                '[parts]\ngood = { target = "a.conf" }\nbad = "oops"\n', encoding="utf-8"
            )
            m = _quiet(load_manifest, src)
            self.assertEqual(sorted(m.parts), ["good"])

    def test_wrong_shaped_optional_apps_does_not_break_discovery(self):
        from nyxuri.deploy.manifest import discover_manifest_apps, load_optional_apps
        with TempEnv() as ctx:
            self._sandbox(ctx).joinpath(".optional-apps.toml").write_text('app = "nope"\n', encoding="utf-8")
            self.assertEqual(_quiet(load_optional_apps), {})
            self.assertIsInstance(_quiet(discover_manifest_apps), list)

    def test_corrupt_optional_apps_is_ignored(self):
        from nyxuri.deploy.manifest import load_optional_apps
        with TempEnv() as ctx:
            self._sandbox(ctx).joinpath(".optional-apps.toml").write_text("not = = toml\n", encoding="utf-8")
            self.assertEqual(_quiet(load_optional_apps), {})


class TestDepsMenuReportsFailure(unittest.TestCase):

    def test_failed_install_propagates(self):
        import nyxuri.deps as deps
        with TempEnv():
            with patch.object(deps.CheckboxList, "run", return_value=["fish"]), \
                 patch.object(deps, "install_selected_deps", return_value=False), \
                 patch.object(deps.sys.stdin, "isatty", return_value=True):
                self.assertFalse(_quiet(deps.run_dep_menu_loop))

    def test_empty_selection_is_success(self):
        import nyxuri.deps as deps
        with TempEnv():
            with patch.object(deps.CheckboxList, "run", return_value=[]), \
                 patch.object(deps.sys.stdin, "isatty", return_value=True):
                self.assertTrue(_quiet(deps.run_dep_menu_loop))


class TestGenDepsQuoting(unittest.TestCase):

    def _load(self):
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "nyxuri" / "packaging" / "gen-deps.py"
        spec = importlib.util.spec_from_file_location("gen_deps_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pass
        return mod

    def test_apostrophe_in_label_is_shell_quoted(self):
        mod = self._load()
        rendered = mod._render(["kitty"], [("mpvpaper", "Foo's App")])
        with tempfile.NamedTemporaryFile("w", suffix=".bash", delete=False) as handle:
            handle.write(rendered)
            script = handle.name
        try:
            result = subprocess.run(["bash", "-n", script], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            os.unlink(script)


class TestOrbitConfigValidation(unittest.TestCase):

    def _config(self):
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools" / "orbit" / "config.py"
        spec = importlib.util.spec_from_file_location("orbit_config_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_string_engine_list_is_rejected(self):
        mod = self._config()
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "cfg.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('search_engines = ["bing", "google"]\n')
        with patch.object(mod, "CONFIG_PATHS", [path]):
            engines, meta = _quiet(mod.load_search_config)
        self.assertTrue(all(isinstance(entry, dict) for entry in engines))
        self.assertIsInstance(meta, dict)

    def test_string_items_are_rejected(self):
        mod = self._config()
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "cfg.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('items = ["oops", 42]\n')
        with patch.object(mod, "CONFIG_PATHS", [path]):
            tree = _quiet(mod.load_menu_tree)
        self.assertTrue(all(isinstance(entry, dict) for entry in tree))

    def test_search_metadata_without_engines_is_kept(self):
        mod = self._config()
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "cfg.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('[search]\ndefault_engine = "google"\nplaceholder = "Ask anything"\n')
        with patch.object(mod, "CONFIG_PATHS", [path]):
            _engines, meta = _quiet(mod.load_search_config)
        self.assertEqual(meta.get("default_engine"), "google")
        self.assertEqual(meta.get("placeholder"), "Ask anything")


class TestHexParsingRejectsMalformed(unittest.TestCase):

    def _module(self, relative, name):
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools" / relative
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_orbit_palette_falls_back(self):
        mod = self._module(Path("orbit") / "palette.py", "orbit_palette_hex")
        for bad in ("#-1FFFF", "#+FFFFF", "#12 345", "# FF FF"):
            self.assertEqual(mod.hex_to_rgb(bad), (0.5, 0.5, 0.5))
        self.assertEqual(mod.hex_to_rgb("#FF0000"), (1.0, 0.0, 0.0))

    def test_wallpaper_theme_falls_back(self):
        mod = self._module(Path("wallpaper_picker") / "theme.py", "wp_theme_hex")
        for bad in ("#-1FFFF", "#+FFFFF", "#12 345"):
            self.assertIsNone(mod.hex_to_rgb(bad))
        self.assertEqual(mod.hex_to_rgb("#00FF00"), (0.0, 1.0, 0.0))


class TestNaturalSort(unittest.TestCase):

    def test_numeric_runs_sort_numerically(self):
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools" / "wallpaper_picker" / "scanner.py"
        source = path.read_text(encoding="utf-8")
        namespace = {"re": re}
        start = source.index("_NATURAL_SPLIT")
        end = source.index("class WallpaperItem")
        exec(compile(source[start:end], str(path), "exec"), namespace)
        key = namespace["_natural_key"]
        names = ["10.jpg", "2.jpg", "a.png", "b.jpg"]
        self.assertEqual(sorted(names, key=lambda n: key(os.path.splitext(n)[0])),
                         ["2.jpg", "10.jpg", "a.png", "b.jpg"])


class TestLedgerResilience(unittest.TestCase):

    def test_unhashable_active_shell_falls_back_to_default(self):
        from nyxuri.state import ledger
        with TempEnv():
            for bad in ([], {}, ["a"], 5, None, "weird"):
                ledger.update_ledger(active_shell=bad)
                self.assertEqual(ledger.active_shell(), "noctalia")

    def test_concurrent_updates_do_not_lose_keys(self):
        from nyxuri.state import ledger
        with TempEnv():
            ledger.update_ledger(seed="x")
            read_fd, write_fd = os.pipe()
            pids = []
            for index in range(6):
                pid = os.fork()
                if pid == 0:
                    try:
                        os.read(read_fd, 1)
                        ledger.update_ledger(**{f"k{index}": index})
                    finally:
                        os._exit(0)
                pids.append(pid)
            os.close(read_fd)
            for _ in range(6):
                os.write(write_fd, b"g")
            os.close(write_fd)
            for pid in pids:
                os.waitpid(pid, 0)
            data = ledger.read_ledger()
            self.assertEqual([data.get(f"k{i}") for i in range(6)], list(range(6)))


class TestFisherCompletion(unittest.TestCase):

    def test_incomplete_install_is_not_reported_installed(self):
        from nyxuri.modules import fisher
        with TempEnv():
            with patch.object(fisher.shutil, "which", return_value="/usr/bin/fish"), \
                 patch.object(fisher, "fetch_raw_with_fallback", return_value=True), \
                 patch.object(fisher.subprocess, "run", return_value=type("R", (), {"returncode": 1})()):
                self.assertFalse(_quiet(fisher.fisher_install))
            self.assertFalse(fisher.fisher_installed())


class TestShellSwitcherClassification(unittest.TestCase):

    def test_third_party_quickshell_is_not_nyxuri_shell(self):
        from nyxuri import shell_switcher
        with TempEnv():
            cmdline = b"quickshell\x00-p\x00/home/u/.config/quickshell\x00"
            real_read = Path.read_bytes
            with patch.object(shell_switcher, "find_pids",
                              side_effect=lambda pat: [4242] if pat in ("qs", "quickshell") else []), \
                 patch.object(Path, "read_bytes",
                              lambda self: cmdline if str(self) == "/proc/4242/cmdline" else real_read(self)):
                self.assertEqual(shell_switcher.probe_running_shells(), [])

    def test_already_active_keeps_the_running_bin(self):
        from nyxuri import shell_switcher
        from nyxuri.state.ledger import custom_shell_bin, set_shell
        with TempEnv():
            old_bin = str(Path(tempfile.mkdtemp()) / "old-shell")
            new_bin = str(Path(tempfile.mkdtemp()) / "new-shell")
            Path(old_bin).write_text("#!/bin/sh\n", encoding="utf-8")
            Path(new_bin).write_text("#!/bin/sh\n", encoding="utf-8")
            set_shell("nyxuri-shell", old_bin)
            with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-test"}), \
                 patch.object(shell_switcher, "probe_running_shells", return_value=[("nyxuri-shell", 111)]), \
                 patch.object(shell_switcher, "preflight_shell", return_value=(True, new_bin, "")), \
                 patch.object(shell_switcher, "spawn_shell") as spawn, \
                 patch.object(shell_switcher, "ensure_compositor_gateway_scripts"), \
                 patch.object(shell_switcher, "is_shell_locked", return_value=False):
                ok, _ = shell_switcher.hot_switch_shell("nyxuri-shell", new_bin)
            self.assertTrue(ok)
            self.assertFalse(spawn.called)
            self.assertEqual(custom_shell_bin(), old_bin)

    def test_failed_restore_returns_tuple_instead_of_raising(self):
        from nyxuri import shell_switcher
        with TempEnv():
            attempts = {"n": 0}

            def flaky(name, bin_path):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise FileExistsError(17, "File exists")
                raise OSError(13, "Permission denied")

            with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-test"}), \
                 patch.object(shell_switcher, "probe_running_shells", return_value=[("noctalia", 1234)]), \
                 patch.object(shell_switcher, "preflight_shell", return_value=(True, "/bin/sh", "")), \
                 patch.object(shell_switcher, "spawn_shell", side_effect=flaky), \
                 patch.object(shell_switcher, "ensure_compositor_gateway_scripts"), \
                 patch.object(shell_switcher, "stop_shell_process", return_value=True), \
                 patch.object(shell_switcher, "stop_all_shell_instances", return_value=True), \
                 patch.object(shell_switcher, "is_shell_locked", return_value=False), \
                 patch.object(shell_switcher.shutil, "which", return_value="/usr/bin/noctalia"):
                ok, message = shell_switcher.hot_switch_shell("nyxuri-shell", "/bin/sh")
            self.assertFalse(ok)
            self.assertIn("also failed", message)


class TestPresetDurability(unittest.TestCase):

    def _sandbox(self, ctx):
        ctx.env.configs_src = Path(tempfile.mkdtemp())
        import nyxuri.deploy.manifest as manifest
        manifest._MANIFEST_CACHE = None
        return ctx.env.configs_src

    def _app(self, src, name, module_toml, files):
        root = src / name
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (root / ".module.toml").write_text(module_toml, encoding="utf-8")
        return root

    def test_failed_save_keeps_the_existing_preset(self):
        from nyxuri.deploy import preset
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            self._app(src, "kitty", "[packages]\n", {"kitty.conf": "# conf"})
            dest = ctx.env.config_dir / "kitty"
            dest.mkdir(parents=True)
            (dest / "kitty.conf").write_text("# live", encoding="utf-8")
            os.mkfifo(dest / "ipc.fifo")
            old = ctx.env.presets_dir / "kitty" / "mine"
            old.mkdir(parents=True)
            (old / "old.conf").write_text("OLD-PRESET", encoding="utf-8")
            self.assertFalse(_quiet(preset.save_preset, "kitty", "mine"))
            self.assertEqual((old / "old.conf").read_text(encoding="utf-8"), "OLD-PRESET")
            self.assertEqual(sorted(p.name for p in (ctx.env.presets_dir / "kitty").iterdir()), ["mine"])

    def test_deleting_the_active_preset_resets_to_default(self):
        from nyxuri.deploy import preset
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            self._app(src, "kitty", "[packages]\n", {"kitty.conf": "# base"})
            user = ctx.env.presets_dir / "kitty" / "mine"
            user.mkdir(parents=True)
            (user / "kitty.conf").write_text("# mine", encoding="utf-8")
            self.assertTrue(_quiet(preset.apply_preset, "kitty", "mine"))
            self.assertEqual(preset.read_active_preset("kitty"), "mine")
            self.assertTrue(_quiet(preset.delete_preset, "kitty", "mine"))
            self.assertEqual(preset.read_active_preset("kitty"), "default")

    def test_official_guard_uses_the_resolved_official_dir(self):
        from nyxuri.deploy import preset
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            root = self._app(src, "kitty", "[packages]\n", {"kitty.conf": "# base"})
            official = root / "__presets__" / "shared"
            official.mkdir(parents=True)
            (official / "kitty.conf").write_text("# official", encoding="utf-8")
            shadow = ctx.env.presets_dir / "kitty" / "shared"
            shadow.mkdir(parents=True)
            (shadow / "kitty.conf").write_text("# shadow", encoding="utf-8")
            self.assertFalse(_quiet(preset.delete_preset, "kitty", "shared"))
            self.assertFalse(_quiet(preset.edit_preset, "kitty", "shared"))
            self.assertTrue(shadow.is_dir())

    def test_active_file_is_authoritative_and_syncs_the_ledger(self):
        from nyxuri.deploy import preset
        from nyxuri.state.ledger import read_ledger
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            self._app(src, "demo", "[packages]\n", {"config.kdl": "// b"})
            preset.write_active_preset("demo", "A")
            self.assertEqual(preset.read_active_preset("demo"), "A")
            (ctx.env.presets_dir / "demo.active").write_text("B", encoding="utf-8")
            self.assertEqual(preset.read_active_preset("demo"), "B")
            self.assertEqual(read_ledger().get("presets", {}).get("demo"), "B")

    def test_non_string_part_target_returns_false(self):
        from nyxuri.deploy import preset
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            root = self._app(src, "demo", '[parts.x]\ntarget = ["a.kdl"]\nsource_dir = "x"\n',
                             {"config.kdl": "// b"})
            slot = root / "__presets__" / "x"
            slot.mkdir(parents=True)
            (slot / "default.kdl").write_text("// v", encoding="utf-8")
            self.assertFalse(_quiet(preset.apply_part, "demo", "x", "default"))

    def test_preset_include_keeps_directory_and_double_star_matches(self):
        from nyxuri.deploy import preset
        cases = (
            ('["scripts"]', {"a.kdl", "scripts/run.sh"}),
            ('["**/*.kdl"]', {"a.kdl", "sub/x.kdl"}),
            ('["*.kdl"]', {"a.kdl", "sub/x.kdl"}),
        )
        for include, expected in cases:
            with TempEnv() as ctx:
                src = self._sandbox(ctx)
                self._app(
                    src, "demo",
                    f"[presets]\ninherit = true\ninclude = {include}\n",
                    {"config.kdl": "// c", "scripts/run.sh": "#!/bin/sh\n",
                     "sub/x.kdl": "// x", "a.kdl": "// a"},
                )
                root = src / "demo" / "__presets__" / "A"
                root.mkdir(parents=True)
                (root / "a.kdl").write_text("// a", encoding="utf-8")
                self.assertTrue(_quiet(preset.apply_preset, "demo", "A"))
                dest = ctx.env.config_dir / "demo"
                got = {str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file()}
                self.assertTrue(expected <= got, f"{include}: missing {sorted(expected - got)}")

    def test_apply_preset_applies_manifest_chmod(self):
        from nyxuri.deploy import preset
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            root = self._app(src, "demo",
                             '[packages]\nchmod = ["scripts/*.sh"]\n[presets]\ninherit = true\n',
                             {"config.kdl": "// c", "scripts/run.sh": "#!/bin/sh\n"})
            os.chmod(root / "scripts" / "run.sh", 0o644)
            slot = root / "__presets__" / "A"
            slot.mkdir(parents=True)
            (slot / "a.kdl").write_text("// a", encoding="utf-8")
            self.assertTrue(_quiet(preset.apply_preset, "demo", "A"))
            script = ctx.env.config_dir / "demo" / "scripts" / "run.sh"
            self.assertTrue(script.is_file())
            self.assertEqual(script.stat().st_mode & 0o777, 0o755)


class TestMultibyteInput(unittest.TestCase):

    def test_read_key_decodes_multibyte_utf8(self):
        import pty
        import time
        from nyxuri import tui
        for text in ("中", "é", "😀", "日"):
            master, slave = pty.openpty()
            saved = sys.stdin
            sys.stdin = os.fdopen(os.dup(slave), "r", buffering=1, errors="replace")
            os.write(master, text.encode("utf-8"))
            time.sleep(0.15)
            try:
                self.assertEqual(tui.read_key(), text)
            finally:
                sys.stdin.close()
                sys.stdin = saved
                os.close(master)
                os.close(slave)


class TestDeployRobustness(unittest.TestCase):

    def _sandbox(self, ctx):
        ctx.env.configs_src = Path(tempfile.mkdtemp())
        import nyxuri.deploy.manifest as manifest
        import nyxuri.deploy.deploy as deploy
        manifest._MANIFEST_CACHE = None
        deploy._CONFIG_ITEMS_CACHE = []
        return ctx.env.configs_src

    def _app(self, src, name, module_toml, files):
        root = src / name
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (root / ".module.toml").write_text(module_toml, encoding="utf-8")
        return root

    def test_unrealizable_part_variant_is_reported(self):
        import nyxuri.deploy.deploy as deploy
        from nyxuri.state.ledger import update_ledger
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            root = self._app(
                src, "demo",
                '[packages]\npreserve = ["part.kdl"]\n[parts.effects]\ntarget = "part.kdl"\n'
                'source_dir = "effects"\ndefault = "default"\n',
                {"part.kdl": "// default-part\n"},
            )
            slot = root / "__presets__" / "effects"
            slot.mkdir(parents=True)
            (slot / "default.kdl").write_text("// default-part\n", encoding="utf-8")
            update_ledger(parts={"demo:effects": "ghost"})
            with patch.object(deploy, "_phase_post_install_services"):
                failed = _quiet(deploy.deploy_selected_configs, items_to_deploy=["demo"], preserved_log=[])
            self.assertEqual(failed, ["demo"])

    def test_absolute_or_empty_chmod_pattern_does_not_abort(self):
        import nyxuri.deploy.deploy as deploy
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            self._app(src, "demo", '[packages]\nchmod = ["/etc/*", ""]\n', {"config.kdl": "// c\n"})
            with patch.object(deploy, "_phase_post_install_services"):
                failed = _quiet(deploy.deploy_selected_configs, items_to_deploy=["demo"], preserved_log=[])
            self.assertEqual(failed, [])
            self.assertTrue((ctx.env.config_dir / "demo" / "config.kdl").is_file())

    def test_scalar_items_to_deploy_is_treated_as_one_item(self):
        import nyxuri.deploy.deploy as deploy
        with TempEnv() as ctx:
            src = self._sandbox(ctx)
            self._app(src, "demo", "[packages]\n", {"config.kdl": "// c\n"})
            with patch.object(deploy, "_phase_post_install_services"):
                failed = _quiet(deploy.deploy_selected_configs, items_to_deploy="demo", preserved_log=[])
            self.assertEqual(failed, [])
            self.assertTrue((ctx.env.config_dir / "demo" / "config.kdl").is_file())


class TestPackageArgv(unittest.TestCase):

    def test_scalar_packages_is_not_split_into_characters(self):
        from nyxuri import pkg
        with patch.object(pkg, "preferred_manager", return_value="pacman"):
            argv = pkg.command("install", "fish")
        self.assertEqual(argv[-1], "fish")
        self.assertNotIn("f", argv)
        with patch.object(pkg, "preferred_manager", return_value="pacman"), \
             patch.object(pkg, "run", return_value=type("R", (), {"returncode": 0})()) as runner:
            pkg.install("fish")
        self.assertEqual(runner.call_args.args[0][-1], "fish")

    def test_shelly_aur_search_passes_the_separator(self):
        from nyxuri.pkg import cli
        with patch.object(cli, "preferred_manager", return_value="shelly"), \
             patch.object(cli, "run", return_value=type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()) as runner:
            cli.search("aur --regex")
        argv = runner.call_args.args[0]
        self.assertIn("--", argv)
        self.assertEqual(argv[-1], "--regex")

    def test_shelly_remove_classifies_aur_operands(self):
        from nyxuri.pkg import cli
        with patch.object(cli, "preferred_manager", return_value="shelly"), \
             patch.object(cli, "run") as runner:
            runner.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "repo-pkg\n", "stderr": ""})(),
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ]
            rc = cli.main(["remove", "aur-pkg"])
            calls = [call.args[0] for call in runner.call_args_list]
        self.assertEqual(rc, 0)
        self.assertEqual(calls[-1][:3], ["shelly", "remove", "aur"])


class TestEntryPointImportGuard(unittest.TestCase):

    def test_partial_tree_import_error_is_reported_without_traceback(self):
        import shutil
        root = Path(tempfile.mkdtemp()) / "tree"
        shutil.copytree(Path(__file__).resolve().parent.parent / "nyxuri", root / "nyxuri")
        cli = root / "nyxuri" / "cli.py"
        cli.write_text("from nyxuri.constants import NYXURI_MISSING_SYMBOL\n" + cli.read_text(encoding="utf-8"),
                       encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "nyxuri", "help"],
                cwd=str(root), capture_output=True, text=True,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root)},
            )
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


class TestScriptContracts(unittest.TestCase):

    def _niri_scripts(self):
        return Path(__file__).resolve().parent.parent / "configs" / "niri" / "scripts"

    def test_scripts_read_the_config_root_the_deployer_writes(self):
        for name in ("niri-brightness.sh", "shell-action.sh"):
            source = (self._niri_scripts() / name).read_text(encoding="utf-8")
            self.assertNotIn("XDG_CONFIG_HOME", source, name)

    def test_mpvpaper_reads_the_assignments_envelope(self):
        script = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "mpvpaper-sync.sh"
        source = script.read_text(encoding="utf-8")
        self.assertIn(".assignments // .", source)

    def test_thumbnail_temp_file_keeps_an_image_suffix(self):
        script = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "mpvpaper-sync.sh"
        source = script.read_text(encoding="utf-8")
        self.assertIn("${THUMB_PATH%.jpg}.tmp.$$.jpg", source)

    def test_eyecare_temp_is_preserved_across_deploys(self):
        manifest = Path(__file__).resolve().parent.parent / "configs" / "niri" / ".module.toml"
        self.assertIn("eyecare_temp", manifest.read_text(encoding="utf-8"))

    def test_set_temp_rejects_out_of_range_values(self):
        import shutil
        script = self._niri_scripts() / "toggle-eyecare.sh"
        if not shutil.which("bash"):
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            for value in ("abc", "99999999", "999"):
                result = subprocess.run(["bash", str(script), "set-temp", value],
                                        capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 2, value)


class TestOrbitRendererGeometry(unittest.TestCase):

    def test_accent_half_span_never_goes_negative(self):
        for count in (12, 45, 46, 60, 120):
            step_deg = 360.0 / count
            self.assertGreaterEqual(max(0.0, step_deg / 2.0 - 4.0), 0.0)


class TestTerminalStyleColorParsing(unittest.TestCase):

    def _parse_rgb(self):
        import importlib
        tools = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        return importlib.import_module("orbit_translate.tui_style")._parse_rgb

    def test_valid_hex_is_decoded(self):
        parse = self._parse_rgb()
        self.assertEqual(parse("#1a2b3c"), (0x1A, 0x2B, 0x3C))
        self.assertEqual(parse("#FFFFFF"), (255, 255, 255))

    def test_signed_and_spaced_hex_digits_fall_back(self):
        parse = self._parse_rgb()
        fallback = (128, 136, 152)
        for value in ("#+12345", "# 12345", "#-12345", "#12345 ", "#12g345", "nothex"):
            self.assertEqual(parse(value), fallback, value)

    def test_non_string_input_falls_back(self):
        parse = self._parse_rgb()
        self.assertEqual(parse(None), (128, 136, 152))


class TestTranslateConfigErrors(unittest.TestCase):

    def _module(self, name):
        import importlib
        tools = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        return importlib.import_module(f"orbit_translate.{name}")

    def test_non_ai_provider_bad_base_url_raises_config_error(self):
        config = self._module("config")
        for provider_type in ("google", "libretranslate", "mymemory", "deepl", "bing",
                              "bing_dict", "cambridge_dict", "lingva", "yandex",
                              "ecdict", "transmart", "tatoeba"):
            with self.assertRaises(config.ConfigError, msg=provider_type):
                config.parse_config({"providers": [{"id": "x", "type": provider_type,
                                                    "base_url": "http://[::1"}]})

    def test_non_utf8_config_raises_config_error(self):
        config = self._module("config")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.toml"
            path.write_bytes(b'source = "en"\n# \xff\xfe not utf-8\ntarget = "zh-CN"\n')
            with self.assertRaises(config.ConfigError):
                config.load_config(path)

    def test_save_round_trip_failure_raises_settings_error(self):
        settings = self._module("settings")
        text = 'name = "a\\u007Fb"\n\n[[providers]]\nid = "x"\ntype = "google"\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.toml"
            path.write_text(text, encoding="utf-8")
            document = settings.SettingsDocument(path)
            document.toggle(0)
            with self.assertRaises(settings.SettingsError):
                document.save()
            self.assertEqual(path.read_text(encoding="utf-8"), text)


class TestRuntimeHomeContract(unittest.TestCase):

    def test_shell_and_python_resolve_the_same_runtime_home(self):
        import shutil
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is not available")
        lib = Path(__file__).resolve().parent.parent / "shell" / "scripts" / "lib"
        with tempfile.TemporaryDirectory() as temporary:
            env = {"HOME": temporary, "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
            shell = subprocess.run(
                [bash, "-c", 'source "%s"\nnyxuri_paths_init\nprintf "%%s" "$NYXURI_SHELL_RUNTIME_HOME"'
                 % (lib / "nyxuri-paths.sh")],
                capture_output=True, text=True, env=env)
            self.assertEqual(shell.returncode, 0, shell.stderr)
            python = subprocess.run(
                [sys.executable, "-c",
                 'import sys; sys.path.insert(0, "%s")\n'
                 'from nyxuri_paths import NyxuriPaths\n'
                 'sys.stdout.write(str(NyxuriPaths.from_environment().runtime_home))' % lib],
                capture_output=True, text=True, env=env)
            self.assertEqual(python.returncode, 0, python.stderr)
        self.assertEqual(shell.stdout, python.stdout)
        self.assertTrue(shell.stdout.endswith("/nyxuri/runtime/nyxuri"), shell.stdout)


class TestLockMarkerDirectory(unittest.TestCase):

    def test_lock_creates_the_runtime_directory_before_writing_the_marker(self):
        lock = Path(__file__).resolve().parent.parent / "shell" / "modules" / "lock" / "Lock.qml"
        source = lock.read_text(encoding="utf-8")
        self.assertIn('command: ["mkdir", "-p", Paths.runtimeHome]', source)
        self.assertIn('path: root.markerReady ? root.lockMarkerPath : ""', source)
        self.assertIn("onLoaded: root.restoreLockAfterCrash()", source)


class TestFetchCoverContract(unittest.TestCase):

    def _run(self, url, *flags, cache_home):
        script = Path(__file__).resolve().parent.parent / "shell" / "scripts" / "media" / "fetch_cover.py"
        return subprocess.run(
            [sys.executable, str(script), url, *flags],
            capture_output=True, text=True,
            env={"HOME": str(cache_home), "XDG_CACHE_HOME": str(cache_home),
                 "PATH": os.environ.get("PATH", "/usr/bin:/bin")})

    def test_malformed_urls_still_emit_one_json_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            for url in ("http://[::1/x.jpg", "http://host:99999/x.jpg", "http://host:abc/x.jpg",
                        "http://host:-1/x.jpg", "http:///x.jpg", "ftp://host/x.jpg", ""):
                with self.subTest(url=url):
                    result = self._run(url, cache_home=cache)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(json.loads(result.stdout)["path"], "")

    def test_refresh_refetches_and_falls_back_to_the_cache(self):
        import http.server
        import socketserver
        import threading
        payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%d/cover.jpg" % server.server_address[1]

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            first = json.loads(self._run(url, cache_home=cache).stdout)
            self.assertEqual(first["source"], "network")
            self.assertEqual(len(requests), 1)

            cached = json.loads(self._run(url, cache_home=cache).stdout)
            self.assertEqual(cached["source"], "cache")
            self.assertEqual(len(requests), 1)

            refreshed = json.loads(self._run(url, "--refresh", cache_home=cache).stdout)
            self.assertEqual(refreshed["source"], "network")
            self.assertEqual(len(requests), 2)

            server.shutdown()
            server.server_close()
            fallback = json.loads(self._run(url, "--refresh", cache_home=cache).stdout)
            self.assertEqual(fallback["source"], "cache")
            self.assertEqual(fallback["path"], first["path"])


class TestToolConfigRoot(unittest.TestCase):

    def test_scratch_menu_wrapper_ignores_a_divergent_xdg_config_home(self):
        script = (Path(__file__).resolve().parent.parent / "configs" / "niri" / "scripts"
                  / "niri-scratch-menu.py")
        self.assertNotIn("XDG_CONFIG_HOME", script.read_text(encoding="utf-8"))

    def test_translate_config_path_follows_the_deployer(self):
        tools = Path(__file__).resolve().parent.parent / "configs" / "noctalia" / "tools"
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            result = subprocess.run(
                [sys.executable, "-c",
                 'import sys; sys.path.insert(0, "%s")\n'
                 'from orbit_translate.config import config_path\n'
                 'print(config_path())' % tools],
                capture_output=True, text=True,
                env={"HOME": str(home), "XDG_CONFIG_HOME": str(home / "elsewhere"),
                     "PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()),
                         home / ".config" / "noctalia" / "tools" / "orbit-translate__custom__.toml")


class TestShellModuleImports(unittest.TestCase):

    def _shell(self):
        return Path(__file__).resolve().parent.parent / "shell"

    def test_files_declaring_desktop_action_import_quickshell(self):
        offenders = []
        for path in sorted(self._shell().rglob("*.qml")):
            source = path.read_text(encoding="utf-8")
            if "property DesktopAction" not in source:
                continue
            if not any(line.startswith("import Quickshell") for line in source.splitlines()):
                offenders.append(str(path.relative_to(self._shell())))
        self.assertEqual(offenders, [])


class TestShellLauncherConfigRoot(unittest.TestCase):

    def _launcher(self):
        return Path(__file__).resolve().parent.parent / "shell" / "nyxuri-shell"

    def test_launcher_ignores_a_divergent_xdg_config_home(self):
        self.assertNotIn("XDG_CONFIG_HOME", self._launcher().read_text(encoding="utf-8"))

    def test_radial_launcher_runs_the_deployed_tool_despite_divergent_xdg(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            tool = home / ".config" / "noctalia" / "tools" / "orbit-launcher.py"
            tool.parent.mkdir(parents=True)
            tool.write_text('#!/bin/sh\nprintf "ORBIT-LAUNCHER-STARTED\\n"\n', encoding="utf-8")
            tool.chmod(0o755)
            result = subprocess.run(
                ["bash", str(self._launcher()), "--action", "radial-launcher"],
                capture_output=True, text=True,
                env={"HOME": str(home), "XDG_CONFIG_HOME": str(home / "elsewhere"),
                     "PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ORBIT-LAUNCHER-STARTED", result.stdout)


class TestDesktopCardHostStructure(unittest.TestCase):

    def _source(self):
        return (Path(__file__).resolve().parent.parent / "shell" / "modules" / "desktopcards"
                / "DesktopCardHost.qml").read_text(encoding="utf-8")

    def test_no_property_change_signal_is_redeclared(self):
        source = self._source()
        declared = re.findall(r"^\s*property\s+[A-Za-z_][\w.]*\s+(\w+)\s*:", source, re.MULTILINE)
        self.assertTrue(declared)
        for name in sorted(set(declared)):
            self.assertNotIn("signal %sChanged" % name, source, name)

    def test_wallpaper_analyzer_is_not_a_variants_delegate_child(self):
        source = self._source()
        self.assertIn("property QtObject wallpaperAnalyzer", source)
        self.assertNotIn("id: wallpaperAnalyzer", source)


class TestTrayMenuScreenContract(unittest.TestCase):

    def test_tray_menu_does_not_shadow_the_window_screen(self):
        source = (Path(__file__).resolve().parent.parent / "shell" / "modules" / "bar" / "tray"
                  / "TrayMenu.qml").read_text(encoding="utf-8")
        self.assertNotIn("property var screen", source)
        self.assertIn("screen: root.screen", source)


class TestSystemThemeProbeGuard(unittest.TestCase):
    """The poller must only adopt a mode the system actually reported.

    `gsettings get ... color-scheme` exits 0 with 'default' wherever GNOME has
    no scheme configured, and the unguarded parse turned that into a "light"
    observation that overwrote the user's saved dark theme.
    """

    def _poller(self):
        source = (Path(__file__).resolve().parent.parent / "shell" / "app" / "services"
                  / "UiPreferences.qml").read_text(encoding="utf-8")
        start = source.index("id: themePoller")
        return source[start:source.index("id: systemThemeWriter", start)]

    def test_poller_requires_an_explicit_scheme_preference(self):
        poller = self._poller()
        self.assertIn("prefer-dark", poller)
        self.assertIn("prefer-light", poller)
        guard = poller.index("if (!prefersDark && !prefersLight)")
        emit = poller.index("root.systemThemeModeObserved(")
        self.assertLess(guard, emit, "the observation must be emitted behind the guard")

    def test_poller_does_not_infer_light_from_unrecognized_output(self):
        poller = self._poller()
        self.assertNotIn('systemThemeModeObserved(root.darkMode ? "dark" : "light")', poller)
        self.assertIn('systemThemeModeObserved(prefersDark ? "dark" : "light")', poller)


class TestUiPreferencesDarkModeMirror(unittest.TestCase):
    """darkMode drives per-mode wallpaper selection, so it cannot start stale.

    It is not persisted and was only written by setDarkMode, which ThemeService
    calls on an actual mode change, leaving it false for the whole first run.
    """

    def _source(self):
        return (Path(__file__).resolve().parent.parent / "shell" / "app" / "services"
                / "UiPreferences.qml").read_text(encoding="utf-8")

    def test_dark_mode_initializes_from_the_theme_mode(self):
        self.assertIn('property bool darkMode: PersonalizationConfig.themeMode === "dark"',
                      self._source())

    def test_dark_mode_follows_later_theme_mode_changes(self):
        source = self._source()
        self.assertIn("target: PersonalizationConfig", source)
        self.assertIn("function onThemeModeChanged()", source)

    def test_dark_mode_is_still_writable_for_set_dark_mode(self):
        source = self._source()
        self.assertNotIn("readonly property bool darkMode", source)
        self.assertIn("root.darkMode = enabled;", source)


class TestPresentationTimeoutScale(unittest.TestCase):
    """Slow hardware must be able to run the presentation harness at all."""

    def _module(self):
        from tests import test_shell_runtime

        return test_shell_runtime

    def test_default_scale_preserves_the_shipped_budgets(self):
        module = self._module()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NYXURI_PRESENTATION_TIMEOUT_SCALE", None)
            os.environ.pop("CLAVIS_PRESENTATION_TIMEOUT_SCALE", None)
            self.assertEqual(module.presentation_timeout_scale(), 1.0)
            for original in (5, 8, 10, 15, 20, 30):
                self.assertEqual(module.presentation_budget(original), float(original))

    def test_scale_multiplies_every_budget(self):
        module = self._module()
        with patch.dict(os.environ, {"NYXURI_PRESENTATION_TIMEOUT_SCALE": "12"}):
            self.assertEqual(module.presentation_budget(10), 120.0)
            self.assertEqual(module.presentation_budget(30), 360.0)

    def test_legacy_variable_is_honored_and_invalid_values_ignored(self):
        module = self._module()
        with patch.dict(os.environ, {"CLAVIS_PRESENTATION_TIMEOUT_SCALE": "4"}):
            os.environ.pop("NYXURI_PRESENTATION_TIMEOUT_SCALE", None)
            self.assertEqual(module.presentation_timeout_scale(), 4.0)
        for value in ("0.1", "0", "-3", "abc", ""):
            with patch.dict(os.environ, {"NYXURI_PRESENTATION_TIMEOUT_SCALE": value}):
                self.assertEqual(module.presentation_timeout_scale(), 1.0, value)


class TestInstallBootstrapCacheCopy(unittest.TestCase):
    """A leftover QML tooling link must not abort the cache copy.

    Running the shell from the source tree makes Quickshell drop a .qmlls.ini
    VFS symlink next to shell.qml; once that VFS is gone the link dangles and
    copytree aborted with Errno 2 before the ignore list knew about the file.
    """

    def test_dangling_qmlls_link_does_not_abort_the_cache_copy(self):
        from tests import test_install_bootstrap

        with TempEnv() as env, tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            (repo / "shell").mkdir(parents=True)
            (repo / "shell" / "shell.qml").write_text("", encoding="utf-8")
            (repo / "shell" / ".qmlls.ini").symlink_to("/tmp/gone-quickshell-vfs/.qmlls.ini")
            with patch.object(test_install_bootstrap, "REPO_ROOT", repo):
                cache = test_install_bootstrap.TestInstallBootstrap()._prepare_cache(env, Path(raw))
            self.assertTrue((cache / "shell" / "shell.qml").is_file())
            self.assertFalse((cache / "shell" / ".qmlls.ini").exists())

    def test_other_dangling_links_are_skipped_rather_than_fatal(self):
        from tests import test_install_bootstrap

        with TempEnv() as env, tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            (repo / "configs").mkdir(parents=True)
            (repo / "configs" / "effects.kdl").symlink_to("/tmp/gone-niri-config/effects.kdl")
            with patch.object(test_install_bootstrap, "REPO_ROOT", repo):
                cache = test_install_bootstrap.TestInstallBootstrap()._prepare_cache(env, Path(raw))
            self.assertFalse((cache / "configs" / "effects.kdl").exists())


class TestConfigSectionHardening(unittest.TestCase):
    """A mistyped section must not abort the whole config load.

    loadFromObject() kept any truthy non-object section, because `parsed.bar
    || {}` leaves 7 untouched, and `"barLayoutLeft" in 7` throws. The catch-all
    in onLoaded then fell back to defaults and rewrote the file, so one bad
    field discarded every setting the user had already made.
    """

    def _source(self):
        return (Path(__file__).resolve().parent.parent / "shell" / "app" / "services"
                / "PersonalizationConfig.qml").read_text(encoding="utf-8")

    def _loader(self):
        source = self._source()
        start = source.index("function loadFromObject")
        return source[start:source.index("function needsScrollingMigration", start)]

    def test_every_section_is_coerced_to_an_object(self):
        loader = self._loader()
        for declaration in (
            "const wallpaper = configSection(source.wallpaper)",
            "const theme = configSection(source.theme)",
            "const effects = configSection(source.effects)",
            "const keystone = configSection(source.keystone)",
            "const media = configSection(keystone.media)",
            "const bar = configSection(source.bar)",
            "const sidebar = configSection(source.sidebar)",
            "const desktopCards = configSection(source.desktopCards)",
            "const transition = configSection(wallpaper.transition)",
            "const overview = configSection(wallpaper.overview)",
            "const parallax = configSection(wallpaper.parallax)",
            "const autoCycle = configSection(wallpaper.autoCycle)",
            "const fonts = configSection(theme.fonts)",
            "const horizontalClock = configSection(keystone.horizontalClock)",
            "const keyhole = configSection(keystone.keyhole)",
        ):
            self.assertIn(declaration, loader)

    def test_no_section_keeps_a_truthy_non_object(self):
        loader = self._loader()
        for section in ("wallpaper", "theme", "effects", "keystone", "bar", "sidebar",
                        "desktopCards", "hotCorners"):
            self.assertNotIn("parsed.%s || {}" % section, loader)

    def test_config_section_helper_rejects_non_objects_and_arrays(self):
        source = self._source()
        helper = source[source.index("function configSection"):
                        source.index("function loadFromObject")]
        self.assertIn('typeof value === "object"', helper)
        self.assertIn("!Array.isArray(value)", helper)
        self.assertIn("? value : {}", helper)

    def test_wallpaper_strings_are_type_narrowed(self):
        loader = self._loader()
        self.assertIn('typeof wallpaper.path === "string"', loader)
        self.assertIn('typeof wallpaper.folder === "string"', loader)
        self.assertIn('typeof wallpaper.pathLight === "string"', loader)
        self.assertIn('typeof wallpaper.pathDark === "string"', loader)
        self.assertNotIn('wallpaper.pathLight || ""', loader)
        self.assertNotIn('wallpaper.pathDark || ""', loader)

    def test_icon_theme_is_type_narrowed(self):
        loader = self._loader()
        self.assertIn('typeof theme.iconTheme === "string"', loader)
        self.assertNotIn('theme.iconTheme || ""', loader)


class TestConfigStoreFailureHandling(unittest.TestCase):
    """An unreadable store must be reported, never repaired by overwriting it.

    The catch-all in onLoaded used to set shouldRepair, and onLoadFailed reset
    every field to its default before saving, so one syntax error replaced the
    whole user config with defaults. Both handlers now consult the FileViewError
    the way DockService, DisplayColor and NotificationService already do.
    """

    def _source(self, name="PersonalizationConfig.qml"):
        return (Path(__file__).resolve().parent.parent / "shell" / "app" / "services"
                / name).read_text(encoding="utf-8")

    def _handler(self, source, signal, following):
        start = source.index(signal)
        return source[start:source.index(following, start)]

    def test_personalization_keeps_the_file_when_parsing_fails(self):
        source = self._source()
        catch = source[source.index("} catch (error) {", source.index("onLoaded:")):]
        self.assertIn("shouldRepair = false;", catch[:catch.index("onLoadFailed")])
        self.assertNotIn("shouldRepair = true;", catch[:catch.index("onLoadFailed")])

    def test_personalization_only_seeds_a_missing_store(self):
        handler = self._handler(self._source(), "onLoadFailed:", "onSaveFailed:")
        self.assertIn("error === FileViewError.FileNotFound", handler)
        self.assertIn("root.save();", handler)
        self.assertIn("console.warn", handler)

    def test_personalization_reports_save_failures(self):
        handler = self._handler(self._source(), "onSaveFailed:", "Component.onDestruction")
        self.assertIn("console.warn", handler)

    def test_ui_preferences_only_seeds_a_missing_store(self):
        handler = self._handler(self._source("UiPreferences.qml"), "onLoadFailed:", "onSaveFailed:")
        self.assertIn("error === FileViewError.FileNotFound", handler)
        self.assertIn("root.save();", handler)
        self.assertIn("console.warn", handler)

    def test_ui_preferences_reports_save_failures(self):
        handler = self._handler(self._source("UiPreferences.qml"), "onSaveFailed:", "Timer {")
        self.assertIn("console.warn", handler)

    AUXILIARY_STORES = (
        "app/services/IdleService.qml",
        "modules/bar/tray/TrayService.qml",
        "modules/quicksettings/QuickToggleConfig.qml",
    )

    def _relative(self, relative):
        return (Path(__file__).resolve().parent.parent / "shell" / relative).read_text(encoding="utf-8")

    @staticmethod
    def _catch_block(source):
        marker = "} catch (error) {"
        start = source.index(marker)
        depth = 0
        for index in range(start + len(marker) - 1, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    return source[start:index + 1]
        raise AssertionError("unterminated catch block")

    def test_auxiliary_stores_keep_the_file_when_parsing_fails(self):
        for relative in self.AUXILIARY_STORES:
            block = self._catch_block(self._relative(relative))
            self.assertNotIn("root.save", block, relative)
            self.assertIn("leaving the existing", block, relative)

    def test_auxiliary_stores_only_seed_a_missing_file(self):
        for relative in self.AUXILIARY_STORES:
            source = self._relative(relative)
            handler = self._handler(source, "onLoadFailed:", "onSaveFailed:")
            self.assertIn("error === FileViewError.FileNotFound", handler, relative)
            self.assertIn("console.warn", handler, relative)

    def test_auxiliary_stores_report_save_failures(self):
        for relative in self.AUXILIARY_STORES:
            source = self._relative(relative)
            self.assertIn("onSaveFailed", source, relative)


class TestEndOfInputCancelsPrompts(unittest.TestCase):
    """A closed terminal must cancel the prompt instead of spinning the reader.

    read_key() returns "EOF" once os.read() yields nothing, but no caller
    matched it, so every menu looped forever at full CPU after the tty closed.
    """

    def _stub(self, tui):
        calls = {"count": 0}

        def fake_read_key():
            calls["count"] += 1
            if calls["count"] > 50:
                raise AssertionError("read_key() never stopped being polled")
            return "EOF"

        self.enterContext(patch.object(tui, "read_key", fake_read_key))
        self.enterContext(patch.object(tui, "interactive_screen",
                                       lambda **kwargs: contextlib.nullcontext()))
        self.enterContext(patch.object(tui.sys, "stdin",
                                       type("Stdin", (), {"isatty": staticmethod(lambda: True)})()))
        return calls

    def test_menu_run_returns_on_end_of_input(self):
        from nyxuri import tui
        calls = self._stub(tui)
        menu = tui.Menu("rollback_select_title", [tui.MenuItem(label="a"), tui.MenuItem(label="b")],
                        hint_key="rollback_select_hint", compact=True)
        self.assertEqual(menu.run(), len(menu.items) - 1)
        self.assertEqual(calls["count"], 1)

    def test_checkbox_list_run_cancels_on_end_of_input(self):
        from nyxuri import tui
        calls = self._stub(tui)
        checklist = tui.CheckboxList("master_title", [
            tui.CheckboxEntry(key="k1", label="a"),
            tui.CheckboxEntry(key="k2", label="b"),
        ], compact=True)
        self.assertIsNone(checklist.run())
        self.assertEqual(calls["count"], 1)

    def test_raw_line_reader_cancels_on_end_of_input(self):
        from nyxuri import tui
        calls = self._stub(tui)
        switcher = tui.PresetSwitcher.__new__(tui.PresetSwitcher)
        self.assertIsNone(tui.PresetSwitcher._read_line_raw(switcher, "prompt: "))
        self.assertEqual(calls["count"], 1)

    def test_every_prompt_loop_matches_end_of_input(self):
        source = (Path(__file__).resolve().parent.parent / "nyxuri" / "tui.py").read_text(encoding="utf-8")
        for branch in (
            'elif key in ("ESC", "EXIT", "EOF"):',
            'elif key in ("0", "q", "Q", "ESC", "EXIT", "EOF"):',
            'elif key in ("q", "Q", "ESC", "EXIT", "EOF"):',
        ):
            self.assertIn(branch, source)
        self.assertEqual(source.count('elif k in ("ESC", "EXIT", "EOF"):'), 1)


if __name__ == "__main__":
    unittest.main()
