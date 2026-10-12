# Runtime Topology — 进程树、IPC 管道与信号链路

> Nyxuri 桌面运行时：合成器会话启动、常驻进程、快捷键脚本与跨应用 IPC 信号流。
> 源码：`configs/niri/config.kdl`、`configs/niri/scripts/`、`configs/noctalia/`。

---

## 1. 运行时架构

个人分支的双会话配置：niri 设置 `KITTY_CONFIG_DIRECTORY` 指向
`~/.config/nyxuri-desktop/kitty-nyxuri`。该入口先读用户原有 Kitty 设置，再由 Noctalia
渲染的 `colors__custom__.conf` 覆盖颜色；Hyprland 仍由 ii 生成原有颜色文件。
Noctalia 关闭共享 GTK、Qt、Starship、Fcitx 模板。runtime 也设置同一 Kitty 路径，
供 Noctalia 启动的应用继承；Nyxuri 登录时停止 II 配色监听，返回其他桌面时恢复。
个人部署通过 `nyxuri-shell.service` 调用 runtime：先交接会话环境并重启 skwd，再启动 Noctalia 和单向预览监听；
主配置不重复 spawn shell。应用的排序 drop-in 等 Noctalia 托盘总线就绪。
私有目录、独立 Niri 单元和壁纸桥接见 [dual-session](dual-session.md)。

```
[ Niri Compositor 会话 (Wayland) ]
  │
  ├── 1. 启动阶段 (spawn-at-startup)
  │     ├── nyxuri-shell.service ────► 个人 runtime / Noctalia / skwd 单向预览 (After compositor)
  │     ├── XDG autostart        ────► Fcitx5 / 1Password / Clash Verge / KDE Connect
  │     └── toggle-eyecare.sh --sync ─► 同步护眼模式状态与色温
  │
  ├── 2. 交互脚本层 (Keybindings 触发)
  │     ├── shell-action.sh    ───────► 统一动作网关 (8大动作: launcher/session/settings/clipboard/lock/wallpaper-random/wallpaper-picker/radial-launcher)
  │     │     ├── launcher (Alt+Space)       ───────► Noctalia 面板: noctalia msg panel-toggle launcher
  │     │     ├── radial-launcher (Mod+Tab) ────► Orbit 星环: orbit-launcher.py (~/.config/nyxuri-desktop/noctalia/tools/)
  │     │     ├── wallpaper-picker ────────────► 壁纸选择器: wallpaper-picker.py (~/.config/nyxuri-desktop/noctalia/tools/)
  │     │     └── session (Mod+Alt+Delete) / 等 ────────► 分发至 Shell IPC (noctalia msg / 未来自研 Shell)
  │     ├── Super + ~          ───────► niri-scratch-toggle.sh (Kitty 浮动终端切换)
  │     ├── Super + N          ───────► toggle-eyecare.sh (护眼色温与着色器切换)
  │     └── 亮度快捷键         ───────► niri-brightness.sh (内屏背光 / 外接 DDC 分流)
  │
  └── 3. 主题与色彩调度层
        ├── nyxuri theme toggle / dark / light / sync
        │     ▼
        │   nyxuri.theme.sync (fcntl 排他 flock 保护)
        │     ├── gsettings color-scheme ──► xdg-desktop-portal ──► GTK4/libadwaita & Brave
        │     ├── gtk-{3,4}.0/settings.ini 写入 ─────────────────► Chromium 启动读
        │     ├── noctalia msg theme-mode-* ─────────────────────► 通知 Noctalia 切换色板与状态
        │     └── pkill -SIGUSR1 kitty ──────────────────────────► Kitty 终端秒跟
        │
        └── 壁纸切换事件 (wallpaper_changed hook)
              ▼
            原版：视频缩略图；个人层：关闭 hook，由 skwd 单向同步预览
              ▼
            Noctalia Material You 调色算法
              ▼ (~6s 自动触发)
            渲染私有 Kitty / Niri 配色 + ~/.cache/nyxuri-desktop/palette.toml (个人分支关闭 GTK 输出)
```

---

## 2. 核心守护进程与生命周期

| 进程 | 职责 | 拉起方式 | 存活策略 |
|---|---|---|---|
| **`niri`** | Wayland 合成器内核 | 登录管理器 (greetd / tty) | 根进程；退出即结束会话 |
| **`noctalia`** | 状态栏、桌面部件、调色引擎、OSD | `nyxuri-shell.service` | PartOf=nyxuri-niri.service，托盘总线就绪后应用启动 |
| **`fcitx5`** | 中文与多语言输入法框架 | 系统 XDG autostart 条目 | 图形会话服务生命周期 |
| **`xdg-desktop-portal`** | 桌面 Portal（文件、截图、色彩外观） | D-Bus 按需激活 / session 激活 | 由 `configs/xdg-desktop-portal/portals.conf` 分流路由 |
| **`skwd-walld`** | 三套桌面共用壁纸渲染 | 当前桌面 helper 交接显示环境并重启 | Nyxuri 单向同步 Noctalia，不改启用关系 |

---

## 3. IPC 通讯总线与协议

应用之间不通过轮询通讯，全部基于轻量 IPC 或信号广播：

| 通讯通道 | 协议 / 载体 | 典型调用示例 | 接收方响应 |
|---|---|---|---|
| **Niri IPC** | Unix Domain Socket | `niri msg action close-window` | Niri 执行窗口管理动作 |
| **Noctalia IPC** | Unix Domain Socket | `noctalia msg theme-mode-toggle` | 触发明暗模式反转、重算色板 |
| **Portal 外观信号** | D-Bus `org.freedesktop.appearance` | `gsettings set ... color-scheme` | GTK4 `AdwStyleManager`、Brave 即时重求值 |
| **进程信号 (Signal)** | POSIX `SIGUSR1` | `pkill -SIGUSR1 kitty` | Kitty 进程内存中重新加载配置与色彩 |
| **着色器动态热插拔** | KDL 文件软链接 | `effects.kdl` -> `effects_eyecare.kdl` | Niri inotify 监听并在下一帧应用着色器 |

---

## 4. 故障隔离与退化保护

1. **亮度调节降级 (`niri-brightness.sh`)**：
   - 内置屏幕优先调用 Noctalia D-Bus 背光服务（毫秒级、无卡顿）；
   - 外接显示器使用 `ddcutil`，且带超时拦截，防止 I2C 总线挂起冻结 UI。
2. **主题同步防抖竞态 (`nyxuri.theme.sync`)**：
   - 使用 `fcntl.flock` 锁定运行时文件（优先 `${XDG_RUNTIME_DIR}/nyxuri-${UID}-theme-sync.lock`），瞬时多次触发非阻塞快速丢弃，杜绝状态竞争。
3. **Orbit 启动器单实例锁 (`orbit/lock.py` / `/proc` 检测)**：
   - 防止重复唤起创建多个重叠悬浮窗；再次触发时关闭现有窗口。

---

## 5. 引擎宿主拓扑与 Environment 数据类

Python 管理引擎在启动时由 `nyxuri.core.get_env()` 构建全局只读 `Environment` 单例：

| 属性 | 解析路径 | 职责与生命周期 |
|---|---|---|
| `home` | `$HOME` | 用户家目录根基 |
| `config_dir` | `~/.config` | dotfiles 目标部署目录 |
| `nyx_dir` | `~/.config/nyxuri` | 用户数据（backups、presets 目录） |
| `state_dir` | `~/.local/state/nyxuri` | 运行时临时目录（`state.json` 账本、进程锁、易失日志） |
| `cache_dir` | `~/.cache/nyxuri` | 缓存目录（standalone 模式代码镜像；另含 `~/.cache/nyxuri/palette.toml` 动态色板） |
| `run_mode` | `"system"` / `"repo"` / `"standalone"` | 判定执行模式（`.system-install` 标记优先） |

两域绝对物理隔离：`state_dir` 放运行时瞬态与账本数据，`nyx_dir` 放持久化用户配置，互不渗透。
