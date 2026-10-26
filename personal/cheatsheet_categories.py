"""Annotate deployed KDL with the community cheatsheet's category comments."""
import re

_HEADER = re.compile(r'^(\s*)((?:\S*\+\S+|XF86\S+|Print))\s[^\n]*?\{')
_MARKER = re.compile(r'^[ \t]*// #"[^"\n]*"[ \t]*(?:\n|$)', re.MULTILINE)


def category(action):
    value = action.lower()
    native = value.split()[0].rstrip(";") if value.split() else ""
    if native.startswith(("next-window", "previous-window", "focus-window", "focus-column")):
        return "窗口焦点"
    if native.startswith("focus-monitor"):
        return "显示器焦点"
    if native.startswith("focus-workspace") or '"empty-focus"' in value:
        return "工作区切换"
    if "to-monitor" in native:
        return "移至显示器"
    if "to-workspace" in native or '"empty-move"' in value:
        return "移至工作区"
    if native.startswith(("move-column", "move-window", "consume", "expel")):
        return "窗口与列移动"
    if native.startswith(("set-window", "set-column", "reset-window", "switch-preset")):
        return "窗口尺寸"
    if native.startswith(("center-", "maximize-", "toggle-column")):
        return "窗口布局"
    if "floating" in native or '"float"' in value:
        return "浮动窗口"
    if "fullscreen" in native:
        return "全屏"
    if "toggle-overview" in value or "show-hotkey-overlay" in value or "keybind-cheatsheet" in value:
        return "概览与快捷键"
    if "noctalia/screen_recorder:" in value:
        return "录屏"
    if "screenshot" in value or "screen_ocr.py" in value or "screen_search.py" in value:
        return "截图"
    if "brightness" in value or "eyecare" in value or "zoomctl" in value:
        return "屏幕显示"
    if "power-off-monitors" in value or native == "quit" or "systemctl" in value or '"session"' in value or '"lock"' in value:
        return "电源与会话"
    if "volume" in value or "set-mute" in value or "mic-mute" in value:
        return "音量与麦克风"
    if '"media"' in value or "playerctl" in value:
        return "媒体播放"
    if "wallpaper" in value or "skwd-wall" in value:
        return "壁纸"
    if '"clipboard"' in value:
        return "剪贴板"
    if "settings" in value or "control-center" in value or "control_center" in value or "gnome-control-center" in value:
        return "设置与控制中心"
    if "nvim" in value or "__custom__" in value or "load-config-file" in value:
        return "配置编辑与重载"
    if "keyboard-shortcuts-inhibit" in value or "fcitx5" in value:
        return "输入与快捷键控制"
    if "close-window" in value or '"close"' in value:
        return "关闭窗口"
    if "1password" in value:
        return "密码管理"
    if "filebrowser" in value or "nautilus" in value or "pcmanfm" in value or '"files"' in value:
        return "文件管理"
    if "btop" in value:
        return "系统监控"
    if "scratch" in value or '"tmux"' in value or '"kitty"' in value:
        return "终端"
    if "bar-toggle" in value or '"hud-focus"' in value:
        return "桌面面板"
    if "launcher" in value:
        return "搜索与启动器"
    if '"true"' in value or '"/usr/bin/true"' in value:
        return "保留键位"
    if native == "spawn":
        return "应用启动"
    return "其他"


def annotate(content):
    """Add metadata only. Repeated deployment never accumulates headings."""
    content = _MARKER.sub("", content)
    lines = content.splitlines(keepends=True)
    result = []
    for index, line in enumerate(lines):
        match = _HEADER.match(line)
        if match:
            body = line.split("{", 1)[1]
            # Native bindings are normally single-line. Multiline spawn/action
            # bodies still need their first action, not the binding header.
            if not body.strip():
                for following in lines[index + 1:]:
                    if following.strip() and not following.lstrip().startswith("//"):
                        body = following.strip()
                        break
            result.append(f'{match.group(1)}// #"{category(body.strip())}"\n')
        result.append(line)
    return "".join(result)
