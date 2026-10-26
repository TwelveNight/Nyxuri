#!/usr/bin/env python3
"""Search a screen region through SekaiPop's Uguu-to-Google-Lens workflow."""
import json
import shutil
import subprocess
from urllib.parse import urlencode, urlsplit


def notify(message):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "--app-name=Nyxuri", "Google Lens", message],
                       capture_output=True, timeout=5)


def main():
    missing = [tool for tool in ("slurp", "grim", "curl", "xdg-open") if not shutil.which(tool)]
    if missing:
        notify("缺少工具：" + "、".join(missing))
        return 1
    try:
        region = subprocess.run(["slurp"], capture_output=True, text=True)
        if region.returncode != 0 and region.stderr.strip():
            notify("无法框选屏幕，请检查当前 Wayland 会话。")
            return 1
        if region.returncode != 0 or not region.stdout.strip():
            return 0
        image = subprocess.run(["grim", "-g", region.stdout.strip(), "-"],
                               capture_output=True, check=True, timeout=15)
        # Match SekaiPop: Lens imports the hosted image in the browser session.
        # The selected image becomes accessible through Uguu's temporary URL.
        response = subprocess.run([
            "curl", "--silent", "--show-error", "--fail",
            "--connect-timeout", "10", "--max-time", "45", "--form",
            "files[]=@-;filename=screenshot.png;type=image/png",
            "https://uguu.se/upload",
        ], input=image.stdout, capture_output=True, check=True, timeout=55)
        data = json.loads(response.stdout)
        if not isinstance(data, dict) or data.get("success") is not True:
            raise ValueError("Image upload failed")
        files = data.get("files")
        if not isinstance(files, list) or not files or not isinstance(files[0], dict):
            raise ValueError("Missing uploaded image")
        url = files[0].get("url")
        if not isinstance(url, str):
            raise ValueError("Missing image URL")
        target = urlsplit(url)
        if (target.scheme != "https" or not target.hostname or target.netloc != target.hostname
                or not (target.hostname == "uguu.se" or target.hostname.endswith(".uguu.se"))):
            raise ValueError("Unexpected image host")
        search = "https://lens.google.com/uploadbyurl?" + urlencode({"url": url})
        subprocess.run(["xdg-open", search], capture_output=True, check=True, timeout=15)
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError):
        notify("截图搜索失败，请检查屏幕捕获权限、网络和默认浏览器。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
