# 本地桌面适配

`night/personal-overlay` 保留 Hyprland + ii 和现有 iNiR，另加一个
**Nyxuri (niri + Noctalia)** 登录项。桌面壁纸共用 skwd-wall。

## 安装

先准备 `niri`、`noctalia`、`kitty`、`skwd-helm`、`skwd-walld`、`ffmpeg`、
`jq`、`inotify-tools`、`wlsunset`、`python-gobject` 和 `gtk-layer-shell`。
当前机器沿用 iNiR 已配置好的 Hyprland 会话交接、skwd 用户服务、
共享配色监听和 Niri Portal 路由。原有 Kitty 配置必须存在。

```bash
python3 personal/install.py --plan
python3 personal/install.py
```

入口先列出变更，再确认。自动化已审阅清单后可用 `--yes`。
配置部署到 `~/.config/nyxuri-desktop/{niri,noctalia,kitty-nyxuri}`，
独立用户服务为 `nyxuri-niri.service` 和 `nyxuri-shell.service`；只随 Nyxuri 登录启动。
`~/.config/niri` 和 `niri.service` 继续属于 iNiR。

确认部署成功后，安装生成的 GDM 入口：

```bash
systemctl --user daemon-reload
sudo install -Dm644 ~/.config/nyxuri-desktop/nyxuri.desktop /usr/share/wayland-sessions/nyxuri.desktop
```

注销后选择 Nyxuri。不要在当前图形会话中手动启动它的 Niri 服务。
此前的 `personal/install.py` 曾部署到公共 Niri 目录；新版不会搬迁或删除
旧文件，现有 iNiR 原样保留。旧的 `nyxuri/personal-mode` 标记也保留。

## 更新

```bash
python3 personal/update.py
```

更新要求干净的个人分支和官方 `origin`。它 fetch 官方 `main`，merge 到
`night/personal-overlay`，然后用新进程运行相同的个人安装入口，再列清单确认。
不 push，不丢弃本地提交。官方已改写过 main 历史，首次合并可能需要人工解决冲突。遇到冲突立即停止，解决冲突并完成 Git 合并后，
重新运行 `python3 personal/install.py`。只更新源码可用 `--no-deploy`。
普通 `nyxuri install/update` 仍是官方完整桌面入口，不用于这套共存适配。

个人入口从最新 `configs/` 制作临时副本，只替换私有路径和壁纸接口，再调用
官方原子部署、模板渲染和素材补齐。没有第二份永久配置副本。
`__custom__` 文件和 manifest 的 preserve 项沿用官方规则保留。
私有预设状态在 `nyxuri-desktop/manager`，不使用现有公共 Niri 的预设记录。

## 壁纸与会话

静态图片、视频和 GIF 选择统一调用 `skwd-helm apply`，随机快捷键调用
`skwd-helm random`。Noctalia 原生壁纸面板的选择也通过 hook 交给 skwd。
Noctalia 的桌面壁纸绘制、mpvpaper 插件及自动 Greeter 同步默认关闭。
请保持 Noctalia 的壁纸绘制关闭，不在 GUI 中启用第二个桌面后端。

skwd 外部切换通过 `watch` 同步到 Noctalia。视频取首帧、Wallpaper Engine
读取已有缩略图，供 Noctalia 配色和锁屏使用；不会将预览图反向设成桌面壁纸。
Kitty 继承原有设置，Nyxuri 颜色写入私有目录。共享 II 配色监听仍照常工作。
多套桌面按顺序登录；共享 skwd 和用户 D-Bus 不支持同一用户同时运行它们。

GDM 入口按标准 `niri-session` 的用户服务启动／关闭顺序运行，但使用独立服务。
Niri 启动前清除旧桌面显示地址与 GPU 选择变量；shell 启动前调用随适配携带的
`desktop-session.py`，验证真实 compositor IPC、PID 和 Wayland socket，
完成 systemd／D-Bus 环境交接，再重连 skwd 和启动 Noctalia。
Shell 单元验证 `org.kde.StatusNotifierWatcher` 的拥有者是本次 Noctalia，再报告就绪；
个人 XDG 应用的排序 drop-in 等待此单元，不会主动拉起它。
该 helper 来源于 iNiR 的个人适配，与现有 Hyprland watcher 共用
`$XDG_RUNTIME_DIR/inir` 的归属记录；旧 watcher 不会停止新会话。

## 验收与撤回

隔离测试、配置校验只能证明部署文件和调用契约。实机应按
Hyprland → Nyxuri → iNiR → Hyprland 往返登录，检查 shell、托盘、输入法、
壁纸和配色；视频及 skwd 外部换图也要分别确认。

若登录失败，回 GDM 选择原有 Hyprland 或 Niri，查看：

```bash
journalctl --user -b -u nyxuri-niri.service
journalctl --user -b -u skwd-walld.service
```

撤回独立入口时，在已退出 Nyxuri 的情况下删除
`/usr/share/wayland-sessions/nyxuri.desktop` 和
`~/.config/systemd/user/nyxuri-niri.service`、`nyxuri-shell.service` 及个人应用
`.service.d/50-nyxuri-shell.conf`，再 `systemctl --user daemon-reload`。
私有配置可留作备份；保留共享 skwd 服务及 iNiR 的全部文件。

本次兼容验证使用官方 `origin/main` 的 `ebafe03` 临时副本，未合并进当前分支；
覆盖最新部署引擎和配置校验，未启动 alpha 自研 Shell。

## 个人快捷键与自启动

`personal/binds.kdl` 从当前个人 Niri 键位迁入，部署为私有
`niri/personal-binds.kdl`，在上游 `binds.kdl` 之后、`__custom__.kdl` 之前加载。
应用、窗口、工作区、媒体和放大镜键位保持原习惯；HUD 聚焦、居中浮动、
空工作区与 tmux 使用携带的 Niri helper，不调用 iNiR 或 ii。

- Mod+Tab：Nyxuri Orbit；Mod+S / A / B：Noctalia 控制中心。
- Ctrl+Alt+Delete：电源菜单；Mod+BackSpace：锁屏；Mod+I：设置。
- Mod+Ctrl+W：skwd 选择器；Mod+F：Firefox；Mod+E：文件管理器；Mod+W：居中浮动。
- Ctrl+1 / Ctrl+Alt+左键：区域截图；原 OCR 菜单键打开截图编辑，不提供 OCR。
- Mod+N/P：上下工作区；Alt+N/P：直接向右/左聚焦，原生切换器内仍切换窗口。
- Ctrl+Mod+Slash：编辑私有 Noctalia 配置；Ctrl+Mod+Alt+Slash：打开更新保留的 `__custom__.kdl`。

屏幕键盘键暂为空操作；原 iNiR 的剪贴板监听不迁入，Noctalia 管理自己的历史。
`personal/startup.kdl` 启动现有的可选 `niri-zoomd`，缺失时跳过。

`personal/autostart/` 记录 1Password、Clash Verge 的 XDG 条目，安装只补齐缺失文件，
不会覆盖已有命令或重新启用用户隐藏的条目。Fcitx5 与 KDE Connect 使用系统
XDG 条目，不额外 spawn；CC Switch 继续手动启动。
**ToDesk 在所有桌面禁止自启动**：安装会将已有 XDG 条目的 Hidden 设为 true、
X-GNOME-Autostart-enabled 设为 false，保留其他字段；缺失时安装禁用条目。
共享 XDG 选择对该用户的所有桌面生效。排序 drop-in 只有 Nyxuri shell 被安排
启动时参与等待；其他桌面不会因此启动 Nyxuri。
