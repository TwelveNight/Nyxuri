# WPS 迷你格式工具栏（Xwayland）

`wps_toolbar.py` 只修正 WPS 选中文字后的迷你格式工具栏。xwayland-satellite 0.8.3
把它声明的 `_KDE_NET_WM_WINDOW_TYPE_OVERRIDE` + `_NET_WM_WINDOW_TYPE_NORMAL`
识别成顶层窗口，Niri 将其居中；从选区移向工具栏时可能导致小窗消失。

已实测：把其 `_NET_WM_WINDOW_TYPE` 改为 `_NET_WM_WINDOW_TYPE_POPUP_MENU`，
下一次自然打开时由 satellite 创建真正的 popup，保留 WPS 请求的位置。
鼠标移入并停留后工具栏仍可见。无需重启 WPS/Niri，不改主窗口布局。

## 部署与依赖

- 依赖 Arch 包 `python-xlib`，脚本显式使用 `/usr/bin/python3`。
- 个人安装器将脚本复制到 `~/.config/nyxuri-desktop/niri/scripts/`。
- `personal/startup.kdl` 在 Niri 登录时启动；运行时文件锁阻止重复实例。
- 初始扫描和 X11 CreateNotify / PropertyNotify / MapNotify 监听覆盖已有、
  新建和属性延迟到达的小窗，不轮询桌面。
- 仅当 app-id/class 和标题均恰为 `wps` / `et` / `wpp` / `pdf`，无 transient
  parent、无边框、固定小尺寸（80–600 × 16–120）、且类型列表含 KDE_OVERRIDE
  和 NORMAL 时修改；不改变普通文档、“字体”等对话框、焦点或文字内容。
- 不强制重新映射窗口。如果工具栏首次被发现时已映射为错误角色，属性修正
  在下一次自然打开时生效。应用若重建小窗，同样由监听器处理。

## 检查

```sh
/usr/bin/python3 -m unittest tests.test_wps_toolbar -v
niri validate --config ~/.config/nyxuri-desktop/niri/config.kdl
```

当前会话可用带 `PartOf=graphical-session.target` 的临时用户单元
`nyxuri-wps-toolbar.service` 启动同一脚本；下次登录由 Niri 的启动项接管。

回退：移除个人启动文件中的 `wps_toolbar.py` 行，停止当前辅助进程；
然后重新打开 WPS（或仅恢复目标小窗原本的两个 window-type atom）。停止监听
本身不会清除已经修改的 X11 属性。不要修改全局 focus-follows-mouse 或重启合成器。

源码依据：
<https://github.com/Supreeeme/xwayland-satellite/blob/v0.8.3/src/xstate/mod.rs#L1156-L1222>
