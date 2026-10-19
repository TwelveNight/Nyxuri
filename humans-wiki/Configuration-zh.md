```text
Nyxuri
├── install.sh                  # 极简引导入口
├── catalog.toml                # 软件目录清单（17 款日常软件同源依赖）
├── nyxuri/                     # Python 核心引擎（零 pip 依赖）
├── shell/                      # Nyxuri Shell（自研 QML/Qt6 桌面外壳，实验性）
└── units/                      # 12 个独立原子桌面能力单元
    ├── fastfetch/              # 系统信息展示
    ├── fcitx5-rime/            # 动态 Material You 输入法皮肤与配置
    ├── fish/                   # Shell 别名与实用函数
    ├── greeter/                # Noctalia Greeter 登录界面集成
    ├── kitty/                  # 终端模拟器与透明度预设
    ├── mango/                  # MangoWM 窗口管理器与动作调度脚本
    ├── niri/                   # 窗口管理器与动作调度脚本
    ├── noctalia/               # 桌面外壳、主题同步、Orbit 星环与壁纸选择器
    ├── starship/               # 终端提示符
    ├── wallpapers/             # 配套壁纸与动态视频包下载钩子
    ├── xdg-desktop-portal/     # Portal 路由（主题与录屏分流）
    └── zed/                    # 代码编辑器配置
```

配置采用原子部署。个人改动通过 Dunder 协议保留：
- 任何含 `__custom__` 的文件（如 `__custom__.kdl`、`__custom__.conf`）与目录在更新时自动保留。
- `~/.config/niri/monitor.kdl` 在部署时保留。

---

## 如何自定义你的配置 (Dunder 协议速查)

任何文件名或目录名只要包含 `__custom__`，跨版本更新或切换预设都不会被覆盖：

- **各应用按各自方式加载**：主配置末尾通常预置了挂载入口（例如 Niri 的 `__custom__.kdl`、Kitty 的 `__custom__.conf`），Fish 则自动扫描加载 `conf.d/` 下的脚本。
- **自由拆分与引入**：想要拆分配置，直接在主自定义文件中二次引入即可（例如在 `__custom__.kdl` 中写 `include "my_rules__custom__.kdl"`，所有带 `__custom__` 的子文件同样受到完整保护）。
- **专属保留文件**：像 `~/.config/niri/monitor.kdl` 这类按名引用的文件由系统自动守护，直接编辑即可。

---

## 钩子机制与分层

Nyxuri 将自动化收尾严格区分为两个物理层级：

### 1. 用户部署后钩子 (`~/.config/nyxuri/hooks/`)
把个人的收尾脚本放进 `~/.config/nyxuri/hooks/`。每次正常部署（`nyxuri install` 或更新）完成后，会按文件名字典序执行其中的 `.sh` 脚本。单个脚本执行限时 30 秒；失败或超时仅记录警告，不阻塞后续流程。`nyxuri test` 会跳过用户钩子，常规卸载也会保留它们。

### 2. 单元生命周期钩子 (`units/<unit>/hooks/`)
单元通过自身的 `units/<unit>/manifest.toml` 声明受控副作用（如 `post_install = "setup-rime"` 或壁纸大包下载 `install-pack`）。这些钩子由单元自身持有，仅由内核事务引擎在单元启用（`nyxuri on`）、停用（`nyxuri off`）或更新重放（`replay_enabled_hooks()`）时调度执行。用户无需向此处放置文件。
