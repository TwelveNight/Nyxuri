"""Atomic swap deployment + Dunder preservation + manifest-declared snapshots.

The atomic_replace_item swap-then-preserve is the heart of Nyxuri's deploy
(§7.1). Two preserve mechanisms live here and stay deliberately separate
(§3.2): the Dunder __custom__ walk (magic filename) and the manifest
``preserve`` snapshot (files referenced by name, e.g. niri/monitor.kdl).
"""

import fnmatch
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nyxuri.core import get_env, log_msg, register_temp_path, remove_path
from nyxuri.i18n import msg


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_ASSIGN_RE = re.compile(r"^(\s*)([A-Za-z0-9_][A-Za-z0-9_-]*)(\s*=\s*)(.+?)\s*$")


def _toml_scalars(path: Path, keys: List[str]) -> Dict[Tuple[str, str], str]:
    """Read ``(section, key) -> raw value text`` for the named keys.

    Values are captured as written, so a carried-over value keeps its original
    spelling instead of being re-serialised by a TOML writer.
    """
    wanted = set(keys)
    found: Dict[Tuple[str, str], str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    section = ""
    for line in text.splitlines():
        header = _SECTION_RE.match(line)
        if header is not None:
            section = header.group(1).strip()
            continue
        if line.lstrip().startswith("#"):
            continue
        assign = _ASSIGN_RE.match(line)
        if assign is None:
            continue
        name = assign.group(2)
        if name in wanted:
            found.setdefault((section, name), assign.group(4))
    return found


def _apply_toml_scalars(path: Path, values: Dict[Tuple[str, str], str]) -> int:
    """Overwrite the named keys in ``path`` in place, returning how many landed.

    Only the matched assignment lines are rewritten, so every other byte of the
    freshly deployed file — including comments and section order — is untouched.
    """
    if not values:
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    lines = text.splitlines(keepends=True)
    section = ""
    applied = 0
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        header = _SECTION_RE.match(body)
        if header is not None:
            section = header.group(1).strip()
            continue
        if body.lstrip().startswith("#"):
            continue
        assign = _ASSIGN_RE.match(body)
        if assign is None:
            continue
        raw = values.get((section, assign.group(2)))
        if raw is None:
            continue
        lines[index] = "".join([assign.group(1), assign.group(2), assign.group(3), raw, "\n"])
        applied += 1
    if applied:
        path.write_text("".join(lines), encoding="utf-8")
    return applied


def apply_executable_permissions(dest: Path, patterns: List[str]) -> None:
    """Apply manifest executable bits without following paths out of the app."""
    if dest.is_symlink() or not dest.is_dir():
        return
    root = dest.resolve()
    for pattern in patterns:
        if not pattern or os.path.isabs(pattern) or ".." in Path(pattern).parts:
            continue
        try:
            for path in dest.glob(pattern):
                try:
                    path.resolve().relative_to(root)
                    if not path.is_symlink() and path.is_file():
                        path.chmod(0o755)
                except (OSError, RuntimeError, ValueError):
                    continue
        except (OSError, ValueError, NotImplementedError):
            continue


def _matches_pattern(rel_str: str, is_dir: bool, patterns: List[str]) -> bool:
    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        if fnmatch.fnmatch(rel_str, pat):
            return True
        name = rel_str.split("/")[-1]
        if fnmatch.fnmatch(name, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(name, pat[3:]):
            return True
        parts = rel_str.split("/")
        base_pat = pat.rstrip("/*")
        for index in range(1, len(parts)):
            if fnmatch.fnmatch("/".join(parts[:index]), base_pat):
                return True
    return False


def _include_could_match(rel_str: str, patterns: List[str]) -> bool:
    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        if "/" not in pat or pat.startswith("**/"):
            return True
        prefix = pat.rstrip("/*")
        if rel_str == prefix or prefix.startswith(rel_str + "/") or rel_str.startswith(prefix + "/"):
            return True
    return False


def _base_deploy_ignore_factory(
    root_src: Path,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
):
    """copytree ignore for base overlay: drops repo-only entries and applies whitelists/blacklists."""
    root = root_src
    inc = [p for p in (include_patterns or []) if p and p.strip()]
    exc = [p for p in (exclude_patterns or []) if p and p.strip()]

    def _ignore(src_dir, names):
        skip = {n for n in names if n in ("__pycache__", ".module.toml")}
        if Path(src_dir) == root:
            if "presets" in names:
                skip.add("presets")
            if "__presets__" in names:
                skip.add("__presets__")

        cur_dir = Path(src_dir)
        for name in names:
            if name in skip:
                continue
            item_path = cur_dir / name
            try:
                rel_str = item_path.relative_to(root).as_posix()
            except ValueError:
                rel_str = name
            is_dir = item_path.is_dir() and not item_path.is_symlink()

            # 1. Whitelist (include)
            if inc and not _matches_pattern(rel_str, is_dir, inc):
                if not is_dir or not _include_could_match(rel_str, inc):
                    skip.add(name)
                    continue

            # 2. Blacklist (exclude)
            if exc and _matches_pattern(rel_str, is_dir, exc):
                skip.add(name)
                continue

        return skip

    return _ignore


def _deploy_ignore_factory(root_src: Path):
    """copytree ignore: drop repo-only entries that must not ship to ~/.config.

    - .module.toml: self-describing manifest (Nyxuri metadata, §10.4 boundary)
    - __pycache__: bytecode cache, never user config
    - presets/ & __presets__/: top-level variant source tree (only at app root, not nested)
    """
    root = root_src

    def _ignore(src_dir, names):
        skip = {n for n in names if n in ("__pycache__", ".module.toml")}
        if Path(src_dir) == root:
            if "presets" in names:
                skip.add("presets")
            if "__presets__" in names:
                skip.add("__presets__")
        return skip

    return _ignore


def atomic_replace_item(
    src: Path, dest: Path, preserved_log: Optional[List[str]] = None,
    test_mode: bool = False, preserve: Optional[List[str]] = None,
    preserve_values: Optional[Dict[str, List[str]]] = None,
    preserve_custom: bool = True,
    base_src: Optional[Path] = None,
    base_include: Optional[List[str]] = None,
    base_exclude: Optional[List[str]] = None,
) -> bool:
    """Atomic swap deployment via sibling temp directories with Dunder Protocol preservation.

    ``preserve`` injects manifest-declared files (e.g. monitor.kdl) into tmp_new
    *before* the rename, so the swapped-in directory is already complete — no
    post-rename restore window for inotify watchers to catch a half-state.

    ``preserve_values`` carries individual keys of a deployed text config across
    the swap (e.g. noctalia's brightness.enable_ddcutil, which the user may have
    turned on and which the shipped default would otherwise reset). Values are
    read from the outgoing file and written into the staged copy, so the same
    no-restore-window property holds.
    """
    pid = os.getpid()
    dest_parent = dest.parent
    home = get_env().home

    if src.is_file():
        tmp_file = dest.with_name(f"{dest.name}.new.{pid}")
        register_temp_path(tmp_file)
        old_dest = None
        try:
            dest_parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tmp_file)
            if dest.exists() or dest.is_symlink():
                old_dest = dest.with_name(f"{dest.name}.old.{pid}")
                dest.rename(old_dest)
                tmp_file.rename(dest)
                remove_path(old_dest)
            else:
                tmp_file.rename(dest)
            return True
        except BaseException as e:
            remove_path(tmp_file)
            if old_dest is not None and old_dest.exists():
                try:
                    old_dest.rename(dest)
                except Exception:
                    pass
            log_msg("ERROR", f"Atomic replace failed for {dest}: {e}")
            return False

    tmp_new = dest.with_name(f"{dest.name}.new.{pid}")
    register_temp_path(tmp_new)

    old_dest = None
    try:
        dest_parent.mkdir(parents=True, exist_ok=True)
        if tmp_new.exists() or tmp_new.is_symlink():
            remove_path(tmp_new)
        if base_src is not None and base_src.is_dir() and base_src != src:
            shutil.copytree(
                base_src,
                tmp_new,
                symlinks=True,
                ignore=_base_deploy_ignore_factory(base_src, base_include, base_exclude),
            )
            shutil.copytree(
                src,
                tmp_new,
                symlinks=True,
                ignore=_deploy_ignore_factory(src),
                dirs_exist_ok=True,
            )
        else:
            shutil.copytree(src, tmp_new, symlinks=True, ignore=_deploy_ignore_factory(src))

        # Dunder Protocol: Scan and inherit *__custom__* files and directories
        if preserve_custom and dest.is_dir():
            preserve_entries = []
            for root, dirs, files in os.walk(dest):
                custom_dirs = [d for d in dirs if "__custom__" in d]
                for d in custom_dirs:
                    dirs.remove(d)
                    preserve_entries.append(("dir", root, d))
                for f in files:
                    if "__custom__" in f:
                        if test_mode and f in ("scratchpad-items__custom__.toml", "orbit-items__custom__.toml"):
                            continue
                        preserve_entries.append(("file", root, f))

            for entry_type, root, name in preserve_entries:
                rel_path = Path(root).relative_to(dest) / name
                src_item = dest / rel_path
                target_item = tmp_new / rel_path
                target_item.parent.mkdir(parents=True, exist_ok=True)
                if entry_type == "dir":
                    shutil.rmtree(target_item, ignore_errors=True)
                    shutil.copytree(src_item, target_item, symlinks=True)
                elif src_item.is_symlink():
                    target_item.unlink(missing_ok=True)
                    target_item.symlink_to(os.readlink(src_item))
                else:
                    shutil.copy2(src_item, target_item)
                try:
                    rel_display = str(dest.relative_to(home / ".config") / rel_path)
                except ValueError:
                    rel_display = str(dest / rel_path)
                suffix = "/" if entry_type == "dir" else ""
                print(msg("log_keep_custom_dir" if entry_type == "dir" else "log_keep_custom_file", rel_display + suffix))
                if preserved_log is not None:
                    preserved_log.append(f"~/.config/{rel_display}{suffix}")

        # Manifest-declared preserve: inject into tmp_new before swap so the
        # renamed directory is already complete (no post-rename restore window).
        # Symlinks are preserved as links (not dereferenced) so runtime link
        # state — e.g. niri/effects.kdl → effects_normal.kdl|effects_eyecare.kdl,
        # whose target encodes the EyeCare on/off state — survives deploys.
        if preserve and dest.is_dir():
            dest_root = dest.resolve()
            new_root = tmp_new.resolve()
            for rel in preserve:
                if not rel or os.path.isabs(rel):
                    continue
                src_p = dest / rel
                tgt_p = tmp_new / rel
                try:
                    src_p.resolve(strict=False).relative_to(dest_root)
                    tgt_p.resolve(strict=False).relative_to(new_root)
                except ValueError:
                    continue
                tgt_p.parent.mkdir(parents=True, exist_ok=True)
                if src_p.is_symlink():
                    tgt_p.unlink(missing_ok=True)
                    tgt_p.symlink_to(os.readlink(src_p))
                elif src_p.is_file():
                    shutil.copy2(src_p, tgt_p)
                else:
                    continue
                print(msg("log_keep_preserved_file", dest.name, rel))
                if preserved_log is not None:
                    preserved_log.append(f"~/.config/{dest.name}/{rel}")

        if preserve_values and dest.is_dir():
            dest_root = dest.resolve()
            new_root = tmp_new.resolve()
            for rel, keys in preserve_values.items():
                if not rel or os.path.isabs(rel) or not keys:
                    continue
                src_p = dest / rel
                tgt_p = tmp_new / rel
                try:
                    src_p.resolve(strict=False).relative_to(dest_root)
                    tgt_p.resolve(strict=False).relative_to(new_root)
                except ValueError:
                    continue
                if not src_p.is_file() or not tgt_p.is_file():
                    continue
                if not _apply_toml_scalars(tgt_p, _toml_scalars(src_p, keys)):
                    continue
                print(msg("log_keep_preserved_file", dest.name, rel))
                if preserved_log is not None:
                    preserved_log.append(f"~/.config/{dest.name}/{rel}")

        if dest.exists() or dest.is_symlink():
            old_dest = dest.with_name(f"{dest.name}.old.{pid}")
            dest.rename(old_dest)
            try:
                tmp_new.rename(dest)
                remove_path(old_dest)
            except Exception:
                old_dest.rename(dest)
                raise
            return True
        else:
            tmp_new.rename(dest)
            return True
    except BaseException as e:
        remove_path(tmp_new)
        if old_dest is not None and old_dest.exists() and not dest.exists():
            try:
                old_dest.rename(dest)
            except OSError:
                pass
        log_msg("ERROR", f"Atomic replace failed for directory {dest}: {e}")
        return False
