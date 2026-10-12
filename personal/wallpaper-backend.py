"""Personal picker: skwd renders, the one-way watcher updates Noctalia."""
import importlib.util
from pathlib import Path
import sys

# Load our deployed sibling without depending on the picker's working directory.
_helper = Path(__file__).resolve().parents[3] / "niri/scripts/wallpaper.py"
_spec = importlib.util.spec_from_file_location("nyxuri_wallpaper_renderer", _helper)
_renderer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_renderer)


def apply_static_wallpaper(path):
    try:
        _renderer.apply(path)
        return True
    except (OSError, ValueError) as error:
        print(f"Wallpaper switch failed: {error}", file=sys.stderr)
        return False


def apply_dynamic_wallpaper(video_path, thumb_path=None):
    return apply_static_wallpaper(video_path)


def apply_wallpaper(item):
    return apply_static_wallpaper(item.path)
