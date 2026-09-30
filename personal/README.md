# 双会话个人配置

此分支在 GDM 下分别运行 Hyprland + ii 和 niri + Noctalia。先安装
`niri`、`noctalia`、`kitty`、`mpvpaper`、`ffmpeg`、`jq`、`inotify-tools`、
`wlsunset`，再运行 `python3 personal/install.py`。
它部署 niri、noctalia、kitty-nyxuri，单独放入 niri 的 Portal 路由和一张离线
基础壁纸。Python 壁纸选择器另需
`python-gobject`、`gtk-layer-shell`。
不要运行上游默认的完整安装；个人部署标记创建后，CLI 会阻止误用。

Kitty 在 Hyprland 下继续读原有 `~/.config/kitty/kitty.conf`，在 niri 下通过
`KITTY_CONFIG_DIRECTORY` 读 `~/.config/kitty-nyxuri/kitty.conf`。后者继承
原有设置，Noctalia 单独渲染颜色。更改壁纸后两边各自更新颜色。

个人部署不修改 `ii-skwd-wall-theme.service`、`skwd-walld.service` 或其
用户级自启动链接。Hyprland 的 skwd-wall 保持原有启动方式。
同一用户的 systemd 服务可能跨桌面会话存活，首次进入 niri 后应检查
skwd-wall 与 Noctalia 是否在同一输出上重叠。

`nyxuri.desktop` 是 GDM 会话入口，准备好 niri 软件包后安装到
`/usr/share/wayland-sessions/nyxuri.desktop`。此步需要管理员权限：

```bash
sudo install -Dm644 personal/nyxuri.desktop /usr/share/wayland-sessions/nyxuri.desktop
```
以后更新代码用 Git 更新个人分支，重新部署用
`python3 personal/install.py`。

个人脚本不再修改本机 skwd 服务；GDM 会话入口需另行安装。
