# Personal desktop coexistence

此页描述 `night/personal-overlay`；操作见
[`personal/README.md`](../personal/README.md)。Hyprland + ii、iNiR 和
Nyxuri + Noctalia 使用同一用户，按顺序登录。三套桌面共用 skwd 渲染，
各自维护 shell 预览与配色。

## 部署与更新

本分支的 `./install.sh` 保留官方引导校验，在 `exec_python_engine` 中检测目标源码的
`personal/entry.py`，从隔离 Python 进程进入个人命令分发。没有该文件的源码仍走
官方 CLI，不以用户安装标记或 cwd 判断。无参数打开个人快捷管理菜单，install、deploy 调用个人部署，
兼容 full/config 参数但范围相同；--plan 只读，--yes 用于已审阅自动化。
菜单沿用官方 Menu 界面；安装／更新通过独立进程调用个人入口，诊断、软件列表和
缓存清理预览使用显式命令。菜单本身不部署，非交互调用直接退出。

`personal/install.py` 列清单并确认后部署到
`~/.config/nyxuri-desktop/{niri,noctalia,kitty-nyxuri}`。
它也可供测试独立调用，不注册 GDM 或 CLI 链接。
它把 `configs/` 的相关目录复制到临时目录，替换私有路径、shell 入口和壁纸
请求后，在局部 Environment 下调用 `_phase_atomic_deployment` 和
`_phase_render_templates`。官方 Dunder／manifest 保留语义继续适用。
首次部署副本含内部 `effects.kdl → effects_normal.kdl` 链接；更新保留现有链接。
公共 `~/.config/niri`、ii/iNiR、用户 Portal 路由及 Kitty 基础配置均不部署。

私有管理状态在 `nyxuri-desktop/manager`，运行账本在
`~/.local/state/nyxuri-desktop/manager`。标记为 `nyxuri-desktop/installed`。
旧 `nyxuri/personal-mode` 标记仍让公共 CLI 拒绝完整 install/deploy/update，
新部署不创建它。本分支的标准 bootstrap 先走个人入口，避免触发旧标记的拒绝。
直接 `python3 -m nyxuri` 仍是公共引擎入口，不用于个人安装更新。

`personal/update.py` 要求干净的 `night/personal-overlay` 和官方 HTTPS origin。
fetch `origin main` 后 merge `FETCH_HEAD`，失败不部署，不自动 stash/reset/push。
成功后新进程调用 `./install.sh install`，`--yes` 传给该进程；`--no-deploy` 只合并源码。
不会自动同步本次开发修改或绕过未提交改动检查。

## 会话

部署 `nyxuri-niri.service`、`nyxuri-shell.service`、`nyxuri-clipboard.service` 和带目标 HOME 的
`nyxuri-desktop/nyxuri.desktop`。
标准入口在清单确认后，若 GDM 条目缺失或不同，先执行 sudo -v（非交互为 sudo -n -v）。
认证失败不部署配置。文件部署成功后执行 systemctl --user daemon-reload，再用 sudo install
注册生成的 desktop 文件到 GDM 系统目录；条目已匹配时跳过 sudo。最后沿用官方
ensure_nyxuri_symlink 注册命令链接。安装期间不启动或重启 compositor/shell。
安装部署持有官方进程锁；--plan 不获取锁或写链接。
`personal/session.py` 采用标准 Niri 用户服务生命周期，但启动独立单元，
使用私有 `--config`；它和 `niri.service` 互斥，避免启动 iNiR 的 shell。
退出经过标准 `niri-shutdown.target` 释放图形会话。

Niri 单元 Wants 私有 Shell 单元，后者 After Niri、Before XDG autostart target，
用 Type=notify，runtime 验证托盘总线拥有者 PID 是本次 Noctalia 且 IPC 可用后报告就绪；不排在 graphical-session.target
之前，避免阻塞 Noctalia 所需的 Portal。部署副本移除原 shell 和 Fcitx spawn，避免重复。

`personal/runtime.py` 先运行携带的 iNiR 个人 `desktop-session.py`，
验证 IPC 对端 PID／UID／compositor 名称和 Wayland socket，发布当前会话环境，
通过 --no-ii-theme 停止 II 配色监听，完成环境交接并重启 skwd 后启动 Noctalia。
托盘与 IPC 就绪后启动 wallpaper.py watch，只把 skwd 当前状态同步给 Noctalia。
返回 iNiR／Hyprland 时，它们原有 helper 会恢复 II 配色监听；共享服务的启用链接不改。
旧 display／GPU 变量在启动 compositor 时清除，私有 shell 单元也用 UnsetEnvironment
清除旧 GPU 变量，个人 NVIDIA 三项选择由单元显式设置（见下节）。helper 的锁、pidfd watcher 和会话记录与现有
Hyprland helper 共用 `$XDG_RUNTIME_DIR/inir`，防止旧会话清理伤及新会话。
Noctalia 会在 `NOCTALIA_CONFIG_HOME`／`NOCTALIA_STATE_HOME` 后自行追加 `noctalia`。
配置根变量设为 `~/.config/nyxuri-desktop`，实际读取其 `noctalia/*.toml`。
状态根变量继续设为 `~/.local/state/nyxuri-desktop/noctalia`，实际 GUI 状态在
其 `noctalia/settings.toml`，沿用已生成的私有状态以保留用户偏好。
runtime 同时确认本次 Shell 拥有托盘总线且 IPC status 返回成功后才报告就绪，
避免初次同步抢在 IPC 前面。
runtime 同时设置 KITTY_CONFIG_DIRECTORY，确保 Noctalia 打开的终端
与 Niri 键位打开的终端一致。这些私有路径只传给本会话子进程，不导入共享用户管理器。
不改变所有应用的 XDG_CONFIG_HOME。

## 壁纸和颜色

按用户选择保留上游 theme_mode_changed = "nyxuri theme sync"，切换深浅主题时
同步共享应用主题；三套桌面共用 skwd 壁纸，此处允许全局配色同步。
`zz-personal.toml` 再次关闭 builtin/community 配色模板，禁用输出到私有目录和
`~/.cache/nyxuri-desktop/` 缓存之外的用户模板，防止更新上游默认值重新写入公共配置。
部署副本关闭 Noctalia 桌面绘制、mpvpaper 插件；wallpaper_changed 调用个人 wallpaper.py hook。
自定义 Python 选择器的个人 backend 加载部署的 wallpaper.py，直接调用 apply，通过 skwd
Unix socket 的 wall.apply 请求切换，单次请求 no_transition=true，不改共享过渡配置。
请求失败返回非零；成功应答只代表后端接受请求，不保证画面已经显示。
wallpaper.py watch 独立同步各输出的图片或视频缩略图到 Noctalia，用于取色与锁屏预览。
同步写入 Noctalia 前在私有运行目录标记该预览事件；hook 消费标记而不请求 skwd。
用户在内置面板选图时 hook 请求 skwd，指定目标输出；当前壁纸和视频预览均跳过，
运行标记最长保留 60 秒，避免过期同步事件回写渲染器。
Super+Ctrl+W 打开 skwd-wall-v2 前端，沿用其自身过渡设置；
Ctrl+Alt+T 打开 Nyxuri 自定义选择器；随机切换使用 skwd-helm random。
bar 的 wallpaper 组件左键通过 `[widget.wallpaper.actions]` 打开 `skwd-wall-v2`，
默认个人 bar 包含该组件；已有 GUI 布局保留，可在状态栏设置添加。
控制中心的大预览卡片和底部 wallpaper 快捷按钮继续打开内置面板；选图由
个人 hook 交给 skwd 渲染，Noctalia 不绘制第二层壁纸。
外部 skwd 选择器的状态变化同样由单向监听同步。

`personal/overview.kdl` 部署为私有 Niri 的 `personal-overview.kdl`，在用户
`__custom__.kdl` 前加载。仅 skwd 渲染图层使用 place-within-backdrop，
选择器和 shell 图层不匹配；overview 背景透明，缩放 0.75，保留工作区阴影与开合动画。

Kitty 基础设置仍来自原有 Kitty，颜色、Niri glow 和 Noctalia 模板路径在私有
目录；Nyxuri 会话中 II 配色监听保持停止，壁纸取色仍走私有模板。
显式深浅主题切换允许上游 theme sync 写入共享 GTK／Qt 设置，不修改 II shell 配置。
不安装 GTK/Fcitx/Fisher/Greeter。
此适配不修改共享用户服务的启用关系及已有 Portal 路由。

复制模板时同时处理绝对路径、`${XDG_CONFIG_HOME:-$HOME/.config}` 拼接路径和 Orbit
兼容 Python wrapper 的路径。私有 shell-action 直接控制 Noctalia，不读取公共
nyxuri/NyxNiri 的 active_shell 账本。Orbit、壁纸选择器与模板色板缓存使用同一私有缓存目录。

## 验证边界

TempEnv 测试覆盖重复部署、公共配置不变、文件保留、参数数组、更新失败和
启动顺序。隔离测试实际执行部署后的 shell／Python 工具入口，验证不会使用公共工具
或旧 shell 选择；覆盖三环境六个方向的迟到 watcher 清理，以及 II 配色停止／恢复参数。
另运行生成后的 Niri／Noctalia 配置校验及 desktop-file 校验。
真正的往返登录、shell／托盘／输入法和动态壁纸仍须实机验收；共享用户
服务不承诺同一用户多图形会话并发隔离。
媒体音量、输入法与普通应用配置仍是同一用户共享资源；
skwd 的当前壁纸状态是三套桌面共享的；Nyxuri 不写 iNiR／Hyprland 的 shell 配色配置。
切换指注销后在 GDM 选择另一登录项，不意味着保留原桌面窗口或同时运行三套 compositor。
本次审计的证据与待验项见 [personal/ISOLATION.md](../personal/ISOLATION.md)。

个人分支已合并官方 `origin/main` `ebafe03`（v4.0.0-alpha.1 后）。
历史改写的冲突采用新版上游实现，保留个人入口、公共部署保护与私有配置层。

## 个人键位与自启动

`personal/binds.kdl`、`personal/75-personal-binds.kdl`、`personal/startup.kdl` 作为普通受仓库管理的文件复制到部署副本，
主配置在默认 binds 后、用户 __custom__ 前 include。自定义覆盖仍由 Dunder 保留，
不把个人键位内容塞进上游 binds 或仅存在实机的文件中。
75-personal-binds 在 personal-binds 之后加载，补齐 iNiR 默认层的居中、列宽、
显示器／工作区移动、原生 Alt+Tab 与媒体键；Alt+Space 调用 Noctalia 搜索。
`personal/noctalia-keybinds.toml` 复制为私有 Noctalia 的 `zz-personal-keybinds.toml`，
通过原生 `[keybinds]` 给 down/up 添加 Ctrl+J/Ctrl+K，保留方向键；搜索和其他
使用通用上下导航的内置列表均生效，不注册 compositor 全局键位。
部署副本移除默认 Super+X，使其可供应用使用；电源菜单改用 Super+Alt+Delete，
Ctrl+Alt+Delete 保留。仓库默认 binds 不变；个人文件随仓库部署更新，
实机覆盖写入最后加载且受 Dunder 保留的 __custom__.kdl。
`personal/niri_actions.py` 部署为 scripts/niri-actions.py，提供当前个人键位的稳定 ID
工作区操作、居中浮动、Hermes HUD 聚焦、tmux 和文件管理器，不依赖 INIR_* 环境。
Super+Q 与 Alt+Q 通过个人 niri-actions 的 close 动作捕获窗口 ID；Folia 主窗口调用同进程
托盘的隐藏菜单，托盘缺失、菜单不可用或进程不匹配时保留播放器，不退回关闭。
已隐藏时不重复切回显示；其他应用按捕获 ID 原生关闭。两键行为一致，均只对 Folia 主窗口作特殊处理。
Super+S 使用 control-center home，Super+B／D 分别指定 bluetooth／network 上下文。
Super+A 恢复上游 radial-launcher 网关，Super+Tab 保留同一星环入口；在星环中直接输入
或按 Tab 进入内置多引擎／AI 搜索，不添加独立搜索程序或改动上游工具。OCR 菜单键映射截图编辑，OSK 暂为空操作。

`personal/autostart/` 记录个人 XDG 选择。1Password／Clash Verge 仅在公共 autostart
条目缺失时原子补齐；已存在的命令与 Hidden 状态保持用户选择。
ToDesk 是明确的禁用策略：`personal/autostart.py` 在原条目中仅更新 Hidden=true 和
X-GNOME-Autostart-enabled=false；缺失时用禁用模板。此选择对所有桌面生效。
Fcitx5／KDE Connect 使用系统 XDG 条目，CC Switch 不自启动。可选放大镜由 startup.kdl
启动；剪贴板历史使用与 iNiR／ii 相同的 cliphist，生命周期与界面见
[personal-clipboard](personal-clipboard.md)。不启动其他桌面的 shell 或调用它们的 IPC。
四个启用应用单元的 `50-nyxuri-shell.conf` 仅声明 After=nyxuri-shell.service，
让当前 Nyxuri 启动事务中的应用等托盘就绪；没有 Wants/Requires，不会在其他桌面
拉起 Nyxuri。它们同时沿用既有 iNiR 的 compositor ready ExecStartPre。

## 个人屏幕与显卡

个人部署副本加入 `personal-gpu.kdl`，沿用 iNiR 的稳定 NVIDIA PCI render 路径
`/dev/dri/by-path/pci-0000:01:00.0-render`，并为 GLX／Vulkan 应用声明 NVIDIA
选择变量。私有 shell 单元显式设置相同三项变量，不继承旧会话选择；不使用
iNiR 专属的 shell 变量，不改变公共默认配置或系统驱动。渲染设备在重新登录后生效。

`personal/monitor.kdl` 是首次部署的个人屏幕默认值：HDMI-A-1 为
2560×1440 @ 143.995 Hz、缩放 1、位置 (-2560, 80)，eDP-2 关闭。
已有私有 `niri/monitor.kdl` 继续由 manifest 保留，后续安装不强制恢复这套默认值。
持久修改使用 `~/.config/nyxuri-desktop/niri/monitor.kdl`；Niri Displays 插件
只通过 IPC 临时调整。`nwg-displays` 默认重载公共配置，不能直接用于本隔离会话。

## 个人窗口规则

`personal/window-rules.kdl` 和 `personal/games.kdl` 复制为私有 Niri 的
`personal-window-rules.kdl`／`personal-games.kdl`，在上游 rules、effects、个人覆盖
之后且用户 `__custom__.kdl` 之前加载；不修改公共 Niri 或仓库上游规则。
来源是当前 iNiR 实机的 35-personal-window-rules 与 96-personal-games。
实机已注释掉的全局透明度不迁移，普通窗口透明度沿用 Nyxuri 当前 effects。
个人规则额外按精确 app-id `folia-major` 关闭 Folia 的 background-effect blur，
不修改透明度或全局 blur；该动态属性可随配置热加载生效。

应用规则保留通讯软件、1Password、WPS、scrcpy、音量与代理工具等浮动偏好，
Portal 初始尺寸 960×700、Waydroid 540×960、代理工具 40%×60%，
Firefox Nightly／Brave 与 JetBrains 按原有标题限定；Hermes pet 只匹配独有标题，
关闭其装饰、阴影与模糊，不扩大到主窗口。浮动／尺寸／初始焦点在新窗口创建时应用，
热加载不强制改动已打开窗口，也没有模拟 pin 或全生命周期焦点锁定。

明日方舟以 app-id 和主窗口标题共同匹配，优先 HDMI-A-1，保留不透明、无圆角裁剪
与无装饰；输出不可用时由 Niri 回退。游戏自行控制全屏，不强制 Heroic 或全部 Wine
窗口全屏。窗口规则不覆盖已有上游游戏行为，只覆盖该规则明确声明的属性。
这两个文件由仓库部署更新；实机额外覆盖仍放在最后加载、受保留的 __custom__.kdl。

## 快捷键速查插件

Super+/ 在个人 binds 中覆盖上游 show-hotkey-overlay，打开社区插件
`kenn/keybind-cheatsheet:cheatsheet`。`personal/keybind-cheatsheet.toml` 复制为
私有 Noctalia 的 `zz-personal-cheatsheet.toml`，指定 compositor=niri 及私有
`~/.config/nyxuri-desktop/niri/config.kdl`，由插件展开 `~` 为当前用户主目录，
避免遗留 `/home/user` 占位符或读取公共 iNiR 快捷键。插件跟随递归 include
解析分拆配置；缓存刷新命令为 `noctalia msg plugin kenn/keybind-cheatsheet:data all refresh`。

插件源码由 Noctalia 自己的 community 源下载管理，不在仓库内复制第三方代码。
当前实例已通过 `noctalia msg plugins enable kenn/keybind-cheatsheet` 安装启用，
启用状态由私有 GUI 状态保存。首次新安装需同样启用一次；个人安装只部署键位和
插件设置，不在部署循环里下载插件。Ctrl+Super+/ 编辑配置的键位不变。

部署时 `personal/cheatsheet_categories.py` 只为私有副本的 config、binds 和两份
个人 binds 添加插件支持的 `// #"分类"` 注释，不改快捷键动作或第三方插件源码。
按动作区分窗口焦点、显示器／工作区、移动、尺寸、布局、浮动、全屏、音量、媒体、
截图、壁纸、电源、终端及设置等用途。插件未知动作才落入“其他”；用户自定义文件
仍原样保留，可用同样注释指定分类。
