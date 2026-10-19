"""Deploy the offline wallpaper blueprint without selecting or replacing wallpaper."""
import shutil
from nyxuri.core import get_pics_dir
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent


def deploy_wallpapers(do_download=False):
    if do_download:
        raise ValueError("Personal updates only deploy offline fallback assets")
    destination = get_pics_dir() / "Wallpapers"
    for source in (ROOT / "units/wallpapers").iterdir():
        if source.is_file() and source.name != "manifest.toml":
            target = destination / source.name
            if not target.exists() and not target.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
