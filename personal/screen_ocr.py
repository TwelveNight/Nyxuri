#!/usr/bin/env python3
"""Recognize a selected Wayland screen region locally and copy its text."""
import re
import shutil
import subprocess


def notify(message):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "--app-name=Nyxuri", "屏幕文字识别", message],
                       capture_output=True, timeout=5)


def main():
    missing = [tool for tool in ("slurp", "grim", "tesseract", "wl-copy") if not shutil.which(tool)]
    if missing:
        notify("缺少工具：" + "、".join(missing))
        return 1
    try:
        languages = subprocess.run(["tesseract", "--list-langs"],
                                   capture_output=True, text=True, check=True, timeout=15)
        missing = [language for language in ("chi_sim", "eng") if language not in languages.stdout.splitlines()]
        if missing:
            notify("识别失败，缺少 Tesseract 语言包：" + "、".join(missing))
            return 1
        region = subprocess.run(["slurp"], capture_output=True, text=True)
        if region.returncode != 0 and region.stderr.strip():
            notify("无法框选屏幕，请检查当前 Wayland 会话。")
            return 1
        if region.returncode != 0 or not region.stdout.strip():
            return 0
        image = subprocess.run(["grim", "-g", region.stdout.strip(), "-"],
                               capture_output=True, check=True, timeout=15)
        result = subprocess.run(["tesseract", "stdin", "stdout", "-l", "chi_sim+eng", "--psm", "11", "quiet"],
                                input=image.stdout, capture_output=True, check=True, timeout=120)
        # Tesseract inserts word separators between recognized Han characters.
        text = re.sub(r"(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])", "", result.stdout.decode("utf-8").strip())
        if not text:
            notify("没有识别到文字，剪贴板未改动。")
            return 0
        subprocess.run(["wl-copy", "--type", "text/plain;charset=utf-8"],
                       input=text.encode("utf-8"), capture_output=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        notify("识别或复制失败。请检查屏幕捕获权限和 Tesseract 中英文语言包。")
        return 1
    notify("文字已复制，可直接粘贴。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
