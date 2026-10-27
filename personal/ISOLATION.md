# 三套桌面的隔离检查

本文保留三套桌面的历史检查范围，不代表当前全部已注册 profile。
当前登录名为 **Nyxuri · Niri**；八套 profile 的现行清单与隔离边界见
`~/.local/lib/desktop-profiles/README.md`。

2026-10-19 补充：配置实体已统一到 desktop-profiles，标准目录由登录入口选择软链接。
新路径、维护保护与保留边界见 [个人适配说明](README.md#2026-10-19会话入口选择配置)。
下面保留早期检查记录，原 nyxuri-desktop 配置目录路径不再适用。

2026-10-12 检查。适用方式：注销当前桌面，在 GDM 选择 Hyprland、Niri 或
Nyxuri (niri + Noctalia)。同一用户同时开启多个图形会话不在隔离范围内。

| 项目 | Nyxuri | iNiR | Hyprland + II |
|---|---|---|---|
| compositor 配置 | `~/.config/nyxuri-desktop/niri` | `~/.config/niri` | `~/.config/hypr` |
| shell 配置 | `~/.config/nyxuri-desktop/noctalia` | `~/.config/inir`、`~/.config/quickshell/inir` | `~/.config/illogical-impulse`、`~/.config/quickshell/ii` |
| shell 生命周期 | `nyxuri-shell.service` 跟随 `nyxuri-niri.service` | `inir.service` 跟随 `niri.service` | Hyprland 启动钩子 |
| 剪贴板历史 | 私有服务记录共享 cliphist，Super+V 开关 Noctalia 个人原生面板 | 原监听和面板使用 cliphist | 原监听和面板使用 cliphist |
| 配色写入 | 私有 Kitty、Niri 和色板缓存 | 沿用已有主题机制 | 沿用已有主题机制 |
| 壁纸 | skwd 直接切换，Noctalia 单向预览 | skwd-wall | skwd-wall |

Nyxuri 的三个服务没有绑定 default.target 或公共 niri.service；其 Niri 单元与
公共 niri.service 互斥。登录项、服务文件、部署文件和配置解析均已检查。
审计时当前运行的是 iNiR，Nyxuri 的两个服务均 inactive，托盘总线由当前 iNiR 进程拥有。

本次收紧的边界：

- Orbit、壁纸选择器、亮度工具及 Python 兼容入口只读取私有配置。
- 键位动作不再读取公共 Nyxuri 账本中的旧 shell 选择。
- Noctalia 打开的 Kitty 与 compositor 快捷键使用同一私有配置；这些路径不发布到共享 systemd／D-Bus 环境。
- Nyxuri 启动时停止 II 配色监听并交接 skwd；返回 iNiR／II 时恢复各自配色监听。
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

## 迁移前的 Noctalia 壁纸桥接复核（历史记录）

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

## 原生壁纸试用（历史）

2026-10-12，用户要求 Nyxuri 恢复原来的 Noctalia 管理方式，进入该桌面时停止
skwd。当时使用原生静态壁纸与原配置的 mpvpaper，关闭静态过渡，移除 skwd
桥接监听；共享服务不 disable，返回 iNiR／Hyprland 仍由原启动流程恢复。
随后用户选择保留 skwd，当前实现改为直接请求后端、单向同步 Noctalia。
自定义选择器使用无过渡 RPC，Noctalia hook 不再反向切换；请求应答时间不代表首帧时间。

## skwd 直接切换实机复核

2026-10-12，私有 shell 已重启，skwd-walld 与单向 wallpaper.py watch 在运行；
Noctalia wallpaper.enabled=false、wallpaper_changed=[]，实际背景图层为 skwd-paper。
II 配色监听保持停止，共享 skwd 服务仍 enabled。自定义选择器直接调用 socket，
两次静态请求应答为 31／36 ms；换图日志观察到约 623／809 ms，预览同步约
592／779 ms。这些是日志和状态观测，不是屏幕首帧计时；测试后恢复原图。
519 项契约测试通过（6 项跳过），沙箱部署、Niri 与 Noctalia 配置校验通过。
动态壁纸和快速连续点击的视觉表现仍需验收。

## 共享剪贴板实机复核

2026-10-12，通过标准安装入口部署个人剪贴板适配，当前 Nyxuri 的私有记录服务
已启动，使用与 iNiR／ii 相同的原生 cliphist 配置和历史库。服务是 static，
没有启用到公共 target；Noctalia 有效配置关闭原生独立历史面板。

实际通过个人 clipboard 网关打开 Fuzzel，并选回临时文字与 PNG：文字原始换行、
图片字节和 image/png MIME 均一致。测试条目已删除，原剪贴板图片恢复；原历史保留。
停止私有服务后确认其三个工作进程全部退出，随后重新启动；Niri／Shell PID 未变。
核对 8,109 个原桌面配置文件内容未变，528 项测试通过（6 项跳过），
沙箱部署、Niri／Noctalia 配置、Fuzzel 配置及三个服务依赖校验通过。
实际注销后在三套桌面往返登录尚未执行。

## 个人屏幕与显卡配置复核

2026-10-12，读取运行中 Nyxuri 的 Niri IPC，将 HDMI-A-1 的
2560×1440 @ 143.995 Hz、缩放 1、位置 (-2560, 80)，以及 eDP-2 关闭状态
原样保存到私有 monitor.kdl。按原子替换写入，并备份至私有 manager/backups。
写入后 IPC 状态完全一致，Niri PID 4380 与 shell runtime PID 4476 未变。

个人 GPU 配置沿用 iNiR 的 NVIDIA PCI render 路径与三项应用选择变量，
私有 shell 单元显式设置同样的值。只重载服务定义，未重启桌面；当前渲染节点
仍是 AMD renderD128，NVIDIA 是否实际用于 Niri／Noctalia 须重新登录后验证。
528 项测试通过（6 项跳过），静态检查、沙箱部署及私有 Niri 配置校验通过。

## Folia 关闭行为复核

2026-10-12，个人 Super+Q 使用已捕获窗口 ID。Folia 主窗口通过同 PID 的
托盘隐藏菜单处理，不发送关闭或退出；其他应用仍按窗口 ID 原生关闭。
私有绑定与脚本已原子部署并重载。实机调用同一隐藏函数后，窗口从 Niri
列表消失，播放器进程保留，MPRIS 播放状态前后均为 Playing；随后通过托盘
显示菜单恢复窗口。实际键盘按键仍由用户验收。
539 项测试通过（6 项跳过），静态检查、私有配置校验和沙箱部署通过。

## 关闭快捷键启动验证

后续纠正单文件部署遗漏的执行权限：个人 niri_actions.py 在仓库和实机均为
755，确保直接 spawn 可执行。Super+Q 与 Alt+Q 使用相同 close 命令，
只有 app_id=folia-major 且标题为 Folia 的主窗口走托盘隐藏；其余窗口原生关闭。
TempEnv 测试实际启动生成副本的脚本并验证两个绑定、关闭命令参数及执行权限。
实机使用两个临时 Kitty 窗口执行同一绑定命令，均关闭成功，随后恢复原窗口焦点；
没有关闭用户原有窗口。544 项测试通过（6 项跳过），静态检查、私有配置校验
和沙箱部署通过。两个实际物理按键仍由用户验收。

## 原生共享历史面板复核

2026-10-12，个人共享历史改由 Noctalia 插件绘制，使用当前绿色主题和字体，
在合成数据截图中确认图片预览。连续四次原生 toggle 的图层状态为开／关／开／关；
方向键与 Enter 恢复文字的原始换行，图片字节与 image/png MIME 保持一致，Esc 关闭。
测试后恢复原剪贴板、删除合成历史并恢复生产后端，保留所有既有启用插件。
本次只原子替换剪贴板相关私有文件，没有部署并行的 GPU／显示器／键位修改，
没有重启 Niri、Noctalia 或记录服务。跨桌面往返登录仍未执行。

## 状态栏壁纸入口复核

2026-10-12，个人 wallpaper 组件左键改为 exec skwd-wall-v2，默认个人
bar 包含壁纸按钮。实机在当前 default bar 的 control-center 前插入该组件，
保留已有组件和 GUI 偏好，只原子替换私有策略及 settings.toml 并热重载。
有效配置确认按钮动作指向 skwd 前端；实际执行同一命令后出现 skwd-wall Overlay 图层，
通过 skwd-helm ui hide 收起，没有换壁纸。546 项测试通过（6 项跳过），
静态检查、Noctalia 配置校验和沙箱部署通过；实际鼠标点击仍由用户验收。

## 控制中心壁纸转发复核

控制中心预览卡片与 wallpaper 快捷按钮继续使用 Noctalia 内置选择器，
wallpaper_changed 转发用户选择到 skwd 指定输出。同步前写入短期预览标记，
hook 消费标记而不重复渲染，视频缩略图路径也不会触发切换。
实机通过内置面板同一 wallpaper-set 路径选择临时图片，确认 HDMI-A-1 的
skwd 状态变为该图片；随后恢复 HK.mp4，确认视频未被预览 hook 覆盖。
只热重载 Noctalia 配置并刷新预览监听，临时监听单元跟随私有 shell 生命周期。
548 项测试通过（6 项跳过），配置校验与沙箱部署通过；实际鼠标点击待用户验收。
