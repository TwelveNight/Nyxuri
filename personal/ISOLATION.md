# 三套桌面的隔离检查

2026-10-12 检查。适用方式：注销当前桌面，在 GDM 选择 Hyprland、Niri 或
Nyxuri (niri + Noctalia)。同一用户同时开启多个图形会话不在隔离范围内。

| 项目 | Nyxuri | iNiR | Hyprland + II |
|---|---|---|---|
| compositor 配置 | `~/.config/nyxuri-desktop/niri` | `~/.config/niri` | `~/.config/hypr` |
| shell 配置 | `~/.config/nyxuri-desktop/noctalia` | `~/.config/inir`、`~/.config/quickshell/inir` | `~/.config/illogical-impulse`、`~/.config/quickshell/ii` |
| shell 生命周期 | `nyxuri-shell.service` 跟随 `nyxuri-niri.service` | `inir.service` 跟随 `niri.service` | Hyprland 启动钩子 |
| 配色写入 | 私有 Kitty、Niri 和色板缓存 | 沿用已有主题机制 | 沿用已有主题机制 |
| 壁纸 | 三套共用 skwd-wall 及当前壁纸选择 | 同左 | 同左 |

Nyxuri 的两个服务没有绑定 default.target 或公共 niri.service；其 Niri 单元与
公共 niri.service 互斥。登录项、服务文件、部署文件和配置解析均已检查。
审计时当前运行的是 iNiR，Nyxuri 的两个服务均 inactive，托盘总线由当前 iNiR 进程拥有。

本次收紧的边界：

- Orbit、壁纸选择器、亮度工具及 Python 兼容入口只读取私有配置。
- 键位动作不再读取公共 Nyxuri 账本中的旧 shell 选择。
- Noctalia 打开的 Kitty 与 compositor 快捷键使用同一私有配置；这些路径不发布到共享 systemd／D-Bus 环境。
- Nyxuri 启动时先停 II 配色监听，再重连 skwd；返回 iNiR／II 时，原有启动钩子恢复监听。
- 私有 shell 启动前清理上一桌面可能残留的 GPU 选择变量。

自动验证涵盖实际执行生成后的工具入口、拒绝公共路径与旧 shell 干扰、II 配色
停止／恢复命令顺序，以及三套环境六个切换方向的旧 watcher 防误清理。
原有 iNiR／II 配置、服务启用链接和 Portal 路由不需要被替换。
本次完整测试为 514 项（6 项跳过），官方 main 临时副本上的 43 项个人适配测试通过。
部署前后核对 180 个原桌面文件内容未变，当前 compositor、shell、skwd 与配色监听的
PID／运行状态保持不变。实际部署的 Niri、Noctalia 配置和 GDM 登录项校验通过。

共享资源包括当前壁纸、PipeWire 音量、网络、输入法、剪贴板历史后端和普通应用偏好。
应用自身的单实例进程也属于同一用户。原桌面的窗口不会迁移到新桌面。
安装入口自动隔离个人部署；显式调用其他官方管理命令仍遵循其公共配置语义。

真实登录验收仍需完成：Hyprland → Nyxuri → iNiR → Hyprland，以及反向顺序。
每次检查 shell、托盘、输入法、截图／屏幕共享、壁纸和终端配色；确认换壁纸不会
改写离开的桌面主题。静态校验与模拟不能替代这一步，审计没有注销当前用户。
