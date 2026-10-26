# Nyxuri 个人配色适配

> 本页约束个人分支的外观适配范围，以 `personal/install.py`、个人素材和契约测试为准。

## 私有 Niri 颜色

`personal/noctalia-appearance.toml` 作为普通仓库文件部署为私有 Noctalia 的
`zz-personal-appearance.toml`。用户模板 `nyxuri_niri_colors` 从私有素材
`templates/niri-personal.kdl` 渲染到私有 Niri 的 `appearance-colors.kdl`。
没有 apply／undo hook，不写公共 `~/.config/niri`。

主配置在布局、glow、个人覆盖之后，用户 `__custom__.kdl` 之前 optional include
生成物，首次未生成时也能启动。只跟随标签指示、插入提示和最近窗口高亮的颜色；
不启用原本关闭的焦点环，不改变固定阴影、宽度或圆角。

不要在这个私有会话启用 Noctalia 的内置 `niri` 模板：v5.3 的模板及卸载钩子
固定指向公共 Niri 目录，不识别 Nyxuri 的私有 compositor 配置。
新安装的个人策略保持 builtin_ids 为空；已有私有 GUI settings 的选择优先于它。
迁移已启用 builtin niri 的机器时，要先停止私有 Noctalia，再仅从其私有
`settings.toml` 的 builtin_ids 及 `state.toml` 的 applied_builtin_ids 中移除 niri，
再启动。不能在运行时直接取消勾选，否则卸载钩子也会修改旧桌面目录。
其他已选模板、GUI 设置与旧桌面文件不作清理。

迁移前先确认当前会话未锁屏；锁屏期间不得停止或热切换安全锁的持有进程。
重启后立即核对私有 Shell 持续 active、托盘总线拥有者是本次 Noctalia、IPC 可用，
不能将启动失败留给无限重试。KDE 的 kded6 可能抢占托盘总线；不得因此永久禁用 KDE
或改其他桌面的自启动。若锁持有者退出而 compositor 留下纯色保护画面，先恢复稳定
Shell 并重新请求原生锁屏，让用户正常认证，不绕过安全锁或重启 compositor 丢失窗口。

## 系统深浅同步

Noctalia 的 `theme_mode_changed` 继续调用上游 `nyxuri theme sync`，
但个人外观配置显式使用永久入口 `"/home/user/.local/bin/nyxuri" theme sync`；
部署时由现有模板渲染替换 HOME。systemd 启动的 Shell 不保证 PATH 包含
`~/.local/bin`，不能只靠交互终端里能找到命令来证明 hook 可执行。

## 光标

保留已有 `Bibata-Modern-Classic`，不为匹配 GTK 而替换成 Ice，
不修改全局 GSettings 或其他桌面的光标。详见 [个人光标](personal-cursor.md)。

## GTK3 兼容

个人部署只处理复制到临时目录的 GTK3 模板，去掉 GTK3 不支持的
`color-mix()` 声明，保留紧邻的纯色 fallback。仓库上游模板、GTK4 模板和
其他桌面的源文件不变。

GTK3／GTK4 的生成 CSS 仍沿用已经接受的共享应用输出路径，由当前桌面持有配色；
本修复不新建共享输出、不改 Portal 路由、GSettings 强调色或共享深浅设置，
不将其他桌面的固定应用主题改成 Nyxuri 模板。同一用户共享应用配置不是同时运行
多套桌面的并发隔离；切换登录的真实往返行为仍需实机验收。

## 验证

`tests/test_personal_appearance.py` 验证私有路径、HOME 渲染、include 优先级、
颜色模板不改变几何、旧桌面哨兵不变，以及不含用户 bin 的 PATH 下已部署主题
hook 的 HOME 展开、执行和 `theme sync` 参数。`tests/test_personal_cursor.py` 检查光标与
单元一致及共享设置不变。`tests/test_personal_gtk.py` 使用隔离子进程的 GTK3
CssProvider 解析已替换 fixture 色值的私有模板；缺少 GTK3 introspection 时跳过。

定点部署后验证私有 Niri／Noctalia 配置、生成颜色与当前调色板一致，并比对
公共 Niri、Hyprland、共享设置的受保护文件。配置加载与真实窗口重绘分别报告。
