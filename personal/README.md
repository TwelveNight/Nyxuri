# 双会话个人配置

此分支在 GDM 下分别运行 Hyprland + ii 和 niri + Noctalia。先安装
`niri`、`noctalia`、`kitty`，再运行 `python3 personal/install.py`。
它只部署 niri、noctalia、kitty-nyxuri，并配置 Hyprland 专属的用户服务。
不要运行上游默认的完整安装；个人部署标记创建后，CLI 会阻止误用。

Kitty 在 Hyprland 下继续读原有 `~/.config/kitty/kitty.conf`，在 niri 下通过
`KITTY_CONFIG_DIRECTORY` 读 `~/.config/kitty-nyxuri/kitty.conf`。后者继承
原有设置，Noctalia 单独渲染颜色。更改壁纸后两边各自更新颜色。

`systemd/ii-skwd-wall-theme.service` 是替换现有 ii 服务的模板，
`systemd/skwd-walld-session.conf` 是 skwd daemon 的 drop-in 模板。
部署时把服务从 `default.target` 移到 `hyprland-session.target`，
Hyprland 现有启动和退出钩子分别启动、停止这个 target。niri 会话会停止这些服务。
实机部署前请确认当前 Hyprland 的会话 target 启动和退出钩子仍在运行。

`nyxuri.desktop` 是 GDM 会话入口，准备好 niri 软件包后安装到
`/usr/share/wayland-sessions/nyxuri.desktop`。此步需要管理员权限：

```bash
sudo install -Dm644 personal/nyxuri.desktop /usr/share/wayland-sessions/nyxuri.desktop
```
以后更新代码用 Git 更新个人分支，重新部署用
`python3 personal/install.py`。

当前仓库改动只准备配置；本机服务、GDM 会话入口与当前桌面尚未改动。
