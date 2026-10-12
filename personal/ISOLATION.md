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

## Noctalia 壁纸入口实机复核

2026-10-12，用户登录 Nyxuri 后复核。Noctalia 会在专用配置根变量后追加
`noctalia`；旧变量指向最终应用目录，实际加载了默认配置而没有壁纸 hook。
个人安装、Niri 子进程和 Shell runtime 现使用同一正确根目录；现有私有 GUI
状态目录继续沿用，用户设置不搬迁。重启 Noctalia 后日志确认个人栏 `bar`、
两种 hook 和关闭桌面绘制的配置已加载，Niri PID 保持不变。

原生 `wallpaper-set` 请求经过 hook 到达 skwd；skwd 外部切换又同步回 Noctalia。
核对 7,614 个现有 iNiR／II／Hyprland、Kitty 和 GTK 文件未变。用户随后成功
选择 `HK.mp4` 动态壁纸，skwd 保持 video，Noctalia 使用私有视频预览；独立计算
的主色和实际色板都是 `#6fe075`。没有手动重渲染全部模板。

检查时另观察到两次 skwd 视频冷启动未通过约三秒的就绪等待；受控独立渲染器
在约 3.25 秒提交首帧，清理测试进程后用户再次切换成功。该瞬时失败发生在直接
skwd 调用中，未改共享渲染器设置；视频冷启动并非已保证每次通过。

新增的启动等待同时检查本次托盘拥有者与 Noctalia IPC，壁纸监听在就绪后启动。
本次 516 项测试通过（6 项跳过），包括实际配置导出验证，避免空目录也通过语法
验证而漏掉加载失败。该等待在下一次 Shell 启动生效，无需再次中断当前视频。

## Niri 概览实机复核

2026-10-12，个人概览规则让 skwd 渲染器留在全屏背景，已分别截图核对
`HK.mp4` 动态壁纸与当前 `3.jpg` 静态壁纸；静态渲染器实际图层名为
`skwd-paper`，也在匹配范围内。缩放使用 iNiR 的 0.75，开启工作区阴影，
开合动画参数沿用当前 iNiR 原生概览配置。

通过标准安装入口部署并热加载，Niri、Noctalia、skwd 的 PID 保持不变；
未主动切换壁纸，截图后恢复概览原状态。核对 8,107 个原桌面配置文件内容未变。
完整测试为 518 项（6 项跳过），沙箱部署及实际 Niri 配置校验通过。
