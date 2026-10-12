"""Personal XDG startup choices, preserving existing enabled-app entries."""
from pathlib import Path
import tempfile

from nyxuri.deploy.atomic import atomic_replace_item

ROOT = Path(__file__).resolve().parent


def disabled_entry(contents: str) -> str:
    lines = contents.splitlines(keepends=True)
    result = []
    in_entry = False
    seen = set()
    values = {"Hidden": "true", "X-GNOME-Autostart-enabled": "false"}
    def finish():
        for key, value in values.items():
            if key not in seen:
                result.append(f"{key}={value}\n")
    found = False
    for line in lines:
        if line.strip().startswith("["):
            if in_entry:
                finish()
            in_entry = line.strip() == "[Desktop Entry]"
            found |= in_entry
        key = line.split("=", 1)[0].strip()
        if in_entry and key in values:
            line = f"{key}={values[key]}\n"
            seen.add(key)
        result.append(line if line.endswith("\n") else line + "\n")
    if in_entry:
        finish()
    if not found:
        raise ValueError("ToDesk desktop entry is invalid; review before deployment")
    return "".join(result)


def disable_todesk(config_dir: Path) -> bool:
    target = config_dir / "autostart/todesk.desktop"
    source = target if target.is_file() else ROOT / "autostart/todesk.desktop"
    contents = disabled_entry(source.read_text(encoding="utf-8"))
    if target.is_file() and target.read_text(encoding="utf-8") == contents:
        return True
    with tempfile.TemporaryDirectory(prefix="nyxuri-autostart-") as directory:
        staged = Path(directory) / target.name
        staged.write_text(contents, encoding="utf-8")
        return atomic_replace_item(staged, target)
