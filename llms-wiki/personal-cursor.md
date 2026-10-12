# 个人光标

个人分支的 Nyxuri 沿用现有 iNiR 与 Hyprland + ii 的
`Bibata-Modern-Classic` 黑色光标，大小为 24。使用本机已安装的主题，
不另行下载或安装光标包。

`personal/cursor.kdl` 通过个人安装入口复制到私有 Niri 的
`personal-cursor.kdl`，在 `__custom__.kdl` 前 include。它同时声明 compositor
光标与 Niri 子进程的 `XCURSOR_THEME`／`XCURSOR_SIZE`；用户最后加载的
自定义文件仍可以覆盖它。该文件随 `./install.sh` 安装和更新原子部署。

同一文件启用 Niri 原生 `focus-follows-mouse max-scroll-amount="100%"`，
鼠标移入窗口时自动聚焦，部分露出的列也可滚入视野，沿用现有 iNiR 的行为。
不启用将鼠标移到焦点窗口的 `warp-mouse-to-focus`。其他键盘、鼠标与触摸板
设置继续由原有输入配置声明；最后加载的用户自定义仍优先。

`nyxuri-niri.service` 与 `nyxuri-shell.service` 也声明相同的环境变量，
避免依赖上一次登录残留的主题，并覆盖不由 Niri 直接 spawn 的 Noctalia 子进程。
两单元只在 Nyxuri 会话中启动，不改变其他桌面的服务设置。

光标配置可用 Niri 热加载立即应用；单元定义中的环境变量在下一次启动时生效。
已有应用自行持有的光标不承诺随热加载刷新。共享 GTK／Qt、GSettings 和图标默认
主题保持用户已有设置，应用的专用光标设置仍由应用决定。
