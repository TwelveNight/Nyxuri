# 本地桌面适配

`night/personal-overlay` 保留 Hyprland + ii 和现有 iNiR，另加一个
**Nyxuri (niri + Noctalia)** 登录项。Nyxuri、iNiR／Hyprland 共用 skwd-wall，Noctalia 保留私有取色与预览。

## 安装

先准备 `niri`、`noctalia`、`kitty`、`mpvpaper`、`ffmpeg`、
`jq`、`inotify-tools`、`wlsunset`、`python-gobject` 和 `gtk-layer-shell`。
当前机器沿用 iNiR 已配置好的 Hyprland 会话交接、skwd 用户服务、
共享配色监听和 Niri Portal 路由。原有 Kitty 配置必须存在。

```bash
cd ~/Template/github/niri-dots/Nyxuri
./install.sh install --plan
./install.sh install
```

入口先列出变更，再确认。自动化已审阅清单后可用 `--yes`。
配置部署到 `~/.config/nyxuri-desktop/{niri,noctalia,kitty-nyxuri}`，
独立用户服务为 `nyxuri-niri.service`、`nyxuri-shell.service` 和 `nyxuri-clipboard.service`；只随 Nyxuri 登录启动。
`~/.config/niri` 和 `niri.service` 继续属于 iNiR。

同一入口支持 `./install.sh install`、`deploy` 以及兼容的 `full` / `config` 参数，
它们都使用相同的个人部署范围。安装成功后自动重载用户服务并注册 GDM 登录项，
不会启动当前桌面之外的会话。登录项已匹配时不需要 sudo；需要新增或更新时，
在确认清单后、写入任何配置前验证 sudo 权限，非交互运行使用 `sudo -n`。
成功后沿用官方规则让 `~/.local/bin/nyxuri` 指向本仓库入口。
运行 `nyxuri` 打开快捷管理菜单；部署请用 `nyxuri install`，同步更新用 `nyxuri update`。

注销后选择 Nyxuri。不要在当前图形会话中手动启动它的 Niri 服务。
此前的 `personal/install.py` 曾部署到公共 Niri 目录；新版不会搬迁或删除
旧文件，现有 iNiR 原样保留。旧的 `nyxuri/personal-mode` 标记也保留。

## 更新

```bash
./install.sh update
```

更新要求干净的个人分支和官方 `origin`。它 fetch 官方 `main`，merge 到
`night/personal-overlay`，然后用新进程运行 `./install.sh install`，再列清单确认。
不 push，不丢弃本地提交。当前已合并官方 main 的 `ebafe03`。遇到冲突立即停止，解决冲突并完成 Git 合并后，
重新运行 `./install.sh install`。只更新源码可用 `--no-deploy`，已审阅的自动化可用 `--yes`。
本仓库的 `nyxuri install/update` 也会进入个人部署；其他仓库、官方远程安装和系统包
仍使用各自入口，不会因为本机的安装标记切换到个人适配。

`install.sh` 保留官方的 Python 版本检查、隔离启动和源码完整性校验，只在目标源码
包含 `personal/entry.py` 时交接给个人命令入口。首次克隆无需已有安装标记。
`doctor`、`test`、`pkg` 等其他显式命令仍交给官方 CLI；直接运行 Python 引擎不会经过此交接。
`personal/install.py` 保留为底层文件部署工具，测试可独立调用它，不会注册系统登录项。

个人入口从最新 `configs/` 制作临时副本，只替换私有路径和壁纸接口，再调用
官方原子部署、模板渲染和素材补齐。没有第二份永久配置副本。
`__custom__` 文件和 manifest 的 preserve 项沿用官方规则保留。
私有预设状态在 `nyxuri-desktop/manager`，不使用现有公共 Niri 的预设记录。

## 壁纸与会话

Super+Ctrl+W 打开 skwd-wall 前端；Ctrl+Alt+T 打开 Nyxuri 自定义选择器，
后者直接请求 skwd-wall 切换并取消本次过渡。skwd 前端沿用自身过渡设置。
Noctalia 的取色、锁屏预览和私有 Kitty/Niri 模板由单向状态监听同步，不阻塞切换请求。
Noctalia 桌面绘制、壁纸 hook 和 mpvpaper 插件关闭，Greeter 自动同步仍关闭。
bar 的壁纸按钮直接打开 skwd-wall 选择器；已有 bar 布局可在设置中添加 wallpaper 组件。
控制中心的壁纸预览卡片和快捷按钮仍打开 Noctalia 选择器，选图会交给 skwd 渲染。
同步回来的预览事件不再触发切图，视频也不会被缩略图覆盖。
Nyxuri 启动时先停止 II 配色监听，再把 skwd 交接到当前桌面；iNiR 同样停止 II 监听，由自身生成共享 Kitty 配色；返回 Hyprland
时由原有 helper 恢复 II 配色监听。共享服务启用关系和过渡配置不改。

Niri overview 保留 iNiR 的 0.75 缩放、工作区阴影和开合动画；skwd 渲染图层留在 backdrop。

Noctalia 会给专用配置根变量追加 `noctalia`：`NOCTALIA_CONFIG_HOME` 使用
`~/.config/nyxuri-desktop`，不是最终应用目录。GUI 状态继续沿用
`~/.local/state/nyxuri-desktop/noctalia/noctalia/`，保留已有设置。

Kitty 继承原有设置，Nyxuri 颜色写入私有目录，Noctalia 和 Niri 键位启动终端时均使用此配置。
Nyxuri 登录时先停止 II 配色监听，避免换壁纸串改共享主题；iNiR 自行取色，返回 II 后由其
原有的启动钩子恢复监听。壁纸预览、色板和缩略图缓存位于 `~/.cache/nyxuri-desktop/`。
深浅主题切换沿用上游 `nyxuri theme sync`，同步共享 GTK／Qt 应用主题；三套桌面仍共用 skwd 壁纸。
iNiR 和 II 也接入 NyxMellow 的动态 Fcitx 模板，由当前会话随壁纸取色；输入法只重载 Classic UI。Nyxuri 私有配置也显式注册三个 Fcitx 模板，切换桌面后由当前会话继续取色。
多套桌面按顺序登录；共享用户 D-Bus 不支持同一用户同时运行它们。

GDM 入口按标准 `niri-session` 的用户服务启动／关闭顺序运行，但使用独立服务。
Niri 启动前清除旧桌面显示地址与 GPU 选择变量；shell 启动前调用随适配携带的
`desktop-session.py`，验证真实 compositor IPC、PID 和 Wayland socket，
完成 systemd／D-Bus 环境交接，重启 skwd 到本会话，再启动 Noctalia 与单向预览监听。
私有 shell 也清除上个桌面遗留的 GPU 变量；终端与 Noctalia 的私有路径只传给本会话子进程。
Shell 单元验证 `org.kde.StatusNotifierWatcher` 的拥有者是本次 Noctalia，且 IPC 可用后再报告就绪；
个人 XDG 应用的排序 drop-in 等待此单元，不会主动拉起它。
该 helper 来源于 iNiR 的个人适配，与现有 Hyprland watcher 共用
`$XDG_RUNTIME_DIR/inir` 的归属记录；旧 watcher 不会停止新会话。

## 验收与撤回

三套环境的隔离范围、共享资源和最近一次验证见 [ISOLATION.md](ISOLATION.md)。

隔离测试、配置校验只能证明部署文件和调用契约。实机应按
Hyprland → Nyxuri → iNiR → Hyprland 往返登录，检查 shell、托盘、输入法、
壁纸和配色；视频壁纸也要分别确认。

若登录失败，回 GDM 选择原有 Hyprland 或 Niri，查看：

```bash
journalctl --user -b -u nyxuri-niri.service
journalctl --user -b -u skwd-walld.service
```

撤回独立入口时，在已退出 Nyxuri 的情况下删除
`/usr/share/wayland-sessions/nyxuri.desktop` 和
`~/.config/systemd/user/nyxuri-niri.service`、`nyxuri-shell.service`、`nyxuri-clipboard.service` 及个人应用
`.service.d/50-nyxuri-shell.conf`，再 `systemctl --user daemon-reload`。
私有配置可留作备份；保留共享 skwd 服务及 iNiR 的全部文件。

本次兼容验证使用官方 `origin/main` 的 `ebafe03` 临时副本，未合并进当前分支；
覆盖最新部署引擎和配置校验，未启动 alpha 自研 Shell。

## 个人快捷键与自启动

`personal/binds.kdl` 从当前个人 Niri 键位迁入，部署为私有
`niri/personal-binds.kdl`。新增的 `personal/75-personal-binds.kdl` 补齐 iNiR 默认层，
部署为同名文件；顺序为上游 binds → personal-binds → 75-personal-binds → __custom__。
仓库中的个人文件随部署更新；实机临时调整仍写进更新保留的 `__custom__.kdl`。
应用、窗口、工作区、媒体和放大镜键位保持原习惯；HUD 聚焦、居中浮动、
空工作区与 tmux 使用携带的 Niri helper，不调用 iNiR 或 ii。

- Super+C / Alt+C：居中当前列；Alt+Space：Noctalia 搜索；Super+Space：Niri overview。
- Super+Esc：Windows 快捷键归属切换；需另行部署个人 win 辅助层，契约见 [个人键位](../llms-wiki/dual-session.md#个人键位与自启动)。
- 搜索列表中 Ctrl+J 选择下一项，Ctrl+K 选择上一项，方向键仍可用；同样适用于 Noctalia 的其他内置列表。
- Super+R：切换列宽；Super+Ctrl+R：恢复窗口高度；Super+Ctrl+方向键：切换显示器。
- Super+方向键：移动窗口；平铺时左右移动整列、上下调整列内顺序，浮动时向对应方向移动。
- Alt+方向键：移动焦点，与 Alt+H/J/K/L 相同；到布局边缘后切换到对应方向的显示器。
- Super+Ctrl+1–9：移动整列到工作区；Page Up/Down 组合与 Alt+Tab 沿用 iNiR；媒体键交给 Noctalia。
- Mod+Tab：Nyxuri Orbit；Mod+S：控制中心首页；Mod+A：音频设置；Mod+B：蓝牙；Mod+D：网络／Wi-Fi。Orbit 中直接输入或按 Tab 进入多引擎／AI 搜索。
- Super+X：留给应用；Super+Alt+Delete / Ctrl+Alt+Delete：电源菜单；Mod+BackSpace：锁屏；Mod+I：设置。
- Mod+Ctrl+W：skwd-wall 前端；Ctrl+Alt+T：Nyxuri 壁纸选择器；Mod+F：Firefox；Mod+E：文件管理器；Mod+W：居中浮动；Alt+W：浮动/平铺切换。
- Ctrl+1 / Ctrl+Alt+左键：区域截图；原 OCR 菜单键打开截图编辑，不提供 OCR。
- Mod+N/P：上下工作区；Alt+N/P：直接向右/左聚焦，原生切换器内仍切换窗口。
- Ctrl+Mod+Slash：编辑私有 Noctalia 配置；Ctrl+Mod+Alt+Slash：打开更新保留的 `__custom__.kdl`。

Noctalia 没有对应的 iNiR 十字准星、面板家族切换和 OCR／搜索截图；
截图菜单键映射截图编辑，录屏插件未启用，Super+Shift+R 暂保留重新加载配置。
屏幕键盘键暂为空操作；Super+V 使用三套桌面共用的 cliphist 历史，详见下节。
`personal/startup.kdl` 启动现有的可选 `niri-zoomd`，缺失时跳过。

`personal/autostart/` 记录 1Password、Clash Verge 的 XDG 条目，安装只补齐缺失文件，
不会覆盖已有命令或重新启用用户隐藏的条目。Fcitx5 与 KDE Connect 使用系统
XDG 条目，不额外 spawn；CC Switch 继续手动启动。
输入法沿用 iNiR：Niri 与 Noctalia 的父进程都设置 `XMODIFIERS=@im=fcitx`，
原生 Wayland 应用不全局强制 GTK／Qt／SDL 输入模块。微信 Universal 根据该变量
为自身启用 Fcitx 模块。部署后重启私有 shell 和微信即可更新启动环境。
**ToDesk 在所有桌面禁止自启动**：安装会将已有 XDG 条目的 Hidden 设为 true、
X-GNOME-Autostart-enabled 设为 false，保留其他字段；缺失时安装禁用条目。
共享 XDG 选择对该用户的所有桌面生效。排序 drop-in 只有 Nyxuri shell 被安排
启动时参与等待；其他桌面不会因此启动 Nyxuri。

## 共享剪贴板

Super+V 开关 Noctalia 原生的个人共享历史面板，再按一次关闭；Esc 或点击外部也能关闭。
方向键选择、Enter 或点击条目复制，再用 Ctrl+V 粘贴。面板沿用当前 Noctalia
字体、圆角、透明度和壁纸配色，右侧预览文字或图片；翻页按钮可浏览全部历史。
它读取 iNiR、ii 使用的原生 cliphist 配置和数据库（默认 `~/.cache/cliphist/db`），
不导入、复制或清空现有历史。文字和图片都能恢复，普通文本与换行保留，
浏览器 HTML 按 iNiR 的规则转成纯文字。图片预览只放入私有运行目录，关闭面板时清理。

`nyxuri-clipboard.service` 在私有 shell 完成显示连接交接后启动，记录文字和图片，
并用 wl-clip-persist 保留应用关闭后的当前内容。退出私有 Niri 时自动停止，
只清理自己启动的进程，不停止 iNiR／ii 的监听；不 enable 到公共用户 target。
安装与更新会部署服务、脚本及个人插件，依赖 cliphist、wl-clipboard 和 wl-clip-persist，
缺失时安装预检会列出，不在安装时启动监听。

Noctalia 内置剪贴板面板使用另一份历史，个人配置将其关闭；旧历史文件保留，
不会自动合入 cliphist。共享面板插件放在私有 Noctalia 配置目录，首次按 Super+V
通过 Noctalia 自身接口添加个人 path 源并启用，保留已有插件和源；以后直接 toggle。

### 显示器与显卡

本机三套桌面共用 [NVIDIA 插电时钟策略](../llms-wiki/personal-nvidia-clock-policy.md)，
解决空闲后首次切换的升频停顿；它是独立的系统服务，不随普通桌面安装自动部署。

显示器持久设置在 `~/.config/nyxuri-desktop/niri/monitor.kdl`，安装更新会保留。
首次部署沿用当前外屏 144 Hz、内屏关闭的布局。个人显卡配置与 iNiR 一致，
由 NVIDIA 渲染 Niri，并为 Noctalia 启动的应用设置 NVIDIA 选择变量；重新登录生效。
Niri Displays 插件的调整仍只临时生效。

Super+Q 与 Alt+Q 沿用 iNiR 的 Folia 行为：隐藏主窗口到自身托盘，继续播放；托盘不可用时保留播放器。其他应用正常关闭，两键行为一致。

## 个人窗口规则

`personal/window-rules.kdl` 与 `personal/games.kdl` 沿用 iNiR 当前的应用浮动、
初始尺寸、JetBrains 辅助窗口、Hermes pet 和明日方舟规则，单独部署到私有 Niri。
不启用 iNiR 已关闭的全局透明度覆盖。浮动和初始尺寸需重新打开应用窗口才生效。
临时个人覆盖仍可写入最后加载的 `__custom__.kdl`，安装更新会保留它。

Super+/ 打开社区 Keybind Cheatsheet 的可搜索快捷键面板，读取本桌面的私有 Niri 配置。
新安装首次需在 Noctalia 插件设置中启用 `kenn/keybind-cheatsheet`；
更新键位后可执行 `noctalia msg plugin kenn/keybind-cheatsheet:data all refresh` 刷新缓存。

GTK3／GTK4 的动态模板在个人配置中显式启用，读取私有 Noctalia 素材，输出共享 `~/.config/gtk-3.0/gtk.css` 与 `gtk-4.0/gtk.css`。壁纸变化渲染当前色板；`theme sync` 仍负责深浅模式。已打开的 GTK 应用可能需要重新打开才能加载新 CSS。
