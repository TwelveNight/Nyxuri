"""Load personal GTK3 palettes through reloadable theme names, not user CSS."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

from nyxuri import core

USER_CSS_MARKER = "/* Nyxuri GTK3 colors are loaded from named themes. */\n"
WRAPPER_MARKER = "/* Nyxuri managed GTK3 theme wrapper. */\n"


def _write_wrapper(path, content):
    if path.is_symlink():
        raise ValueError(f"Refusing to replace an unowned GTK theme symlink: {path}")
    if path.exists():
        old = path.read_text()
        if old == content:
            return
        if not old.startswith(WRAPPER_MARKER):
            raise ValueError(f"Refusing to replace an unowned GTK theme file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content)
    os.replace(temporary, path)


def _base_css(home, mode):
    name = "adw-gtk3" if mode == "light" else "adw-gtk3-dark"
    roots = [home / ".local/share/themes", home / ".themes"]
    roots += [Path(p) / "themes" for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    return next((path for root in roots if (path := root / name / "gtk-3.0/gtk.css").is_file()), None)


def _retire_user_css(env):
    css = env.config_dir / "gtk-3.0/gtk.css"
    if css.is_symlink():
        raise ValueError(f"Refusing to replace a GTK user stylesheet symlink: {css}")
    content = css.read_text() if css.exists() else ""
    if content == USER_CSS_MARKER:
        return
    if content.strip():
        template = env.config_dir / "noctalia/templates/gtk-3.0.css"
        if not template.is_file():
            raise ValueError("The previous GTK3 template is missing; user CSS left unchanged")
        parts = re.split(r"{{.*?}}", template.read_text(), flags=re.DOTALL)
        pattern = r"[^\n;{}]*".join(re.escape(part) for part in parts)
        if re.fullmatch(pattern + r"\s*", content) is None:
            raise ValueError(f"GTK3 user CSS contains unowned changes; preserved: {css}")
    if css.exists():
        backup = env.home / ".local/state/nyxuri-desktop/gtk3/gtk.css.before-named-themes"
        backup.parent.mkdir(parents=True, exist_ok=True)
        try:
            with backup.open("xb") as stream:
                stream.write(css.read_bytes())
        except FileExistsError:
            pass
    css.parent.mkdir(parents=True, exist_ok=True)
    temporary = css.with_name(f".gtk.css.{os.getpid()}.tmp")
    temporary.write_text(USER_CSS_MARKER)
    os.replace(temporary, css)


@contextmanager
def environment():
    """Scope the existing theme writer to generated palettes, once both exist."""
    env = core.get_env()
    themes = env.home / ".local/share/themes"
    names = {mode: f"Nyxuri-M3-{mode.title()}" for mode in ("light", "dark")}
    palettes = {mode: themes / name / "gtk-3.0/gtk.css" for mode, name in names.items()}
    bases = {mode: _base_css(env.home, mode) for mode in names}
    if not all(path.is_file() for path in palettes.values()) or not all(bases.values()):
        yield
        return
    for path in palettes.values():
        if path.is_symlink() or not path.read_text().startswith('@import url("base.css");\n'):
            raise ValueError(f"Refusing to select an unowned GTK palette: {path}")
    for mode, name in names.items():
        base = bases[mode]
        if base is None:
            raise ValueError(f"The {mode} GTK base theme is unavailable")
        _write_wrapper(themes / name / "gtk-3.0/base.css",
                       WRAPPER_MARKER + f"@import url({json.dumps(base.as_uri())});\n")
        _write_wrapper(themes / f"{name}-Alt/gtk-3.0/gtk.css",
                       WRAPPER_MARKER + f"@import url({json.dumps(palettes[mode].as_uri())});\n")
    _retire_user_css(env)
    current = ""
    if os.environ.get("NYXURI_GTK3_REFRESH") == "1":
        result = core.timed_run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                                3, capture_output=True, text=True, check=False)
        if result is not None and result.returncode == 0:
            current = result.stdout.strip().strip("'")
    keys = {f"NYXURI_GTK_THEME_{mode.upper()}": f"{name}-Alt" if current == name else name
            for mode, name in names.items()}
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key, value in keys.items():
            os.environ.setdefault(key, value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
