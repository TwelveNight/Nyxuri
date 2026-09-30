#!/usr/bin/env bash
set -euo pipefail

# The user manager survives compositor switches. Retire Hyprland's wallpaper
# units before Noctalia starts rendering this session's wallpaper.
systemctl --user stop hyprland-session.target ii-skwd-wall-theme.service skwd-walld.service >/dev/null 2>&1 || true
