# 个人共享剪贴板

`personal/clipboard.py` 使用 cliphist 原生配置和数据库，与 iNiR 的 wrapper 及 ii
的直接调用一致。默认历史库是 `~/.cache/cliphist/db`，不设置私有 -db-path、
-config-path 或缓存根，不迁移、清空已有条目。

## 部署和入口

`personal/install.py:prepare_sources` 将 clipboard.py 复制到私有 Niri scripts，并将
`personal/clipboard-panel/` 与同源 backend.py 复制到私有 Noctalia 的
`personal-plugins/shared-clipboard/`。文件通过 atomic_replace_item 随个人安装／更新部署。
部署后的 shell-action.sh 的 clipboard 动作为 Python pick；Mod+V 禁用按住重复触发。
上游配置源码不变。`zz-personal.toml` 关闭内置独立历史面板，旧缓存保留。
安装预检要求 cliphist、wl-paste、wl-copy、wl-clip-persist，不依赖 Fuzzel。

pick 直接调用 `noctalia msg panel-toggle night/shared-clipboard:history`；没有选择器进程锁。
插件未注册时，添加名为 nyxuri-personal 的私有 path 源并启用 night/shared-clipboard，
等待异步启用完成后再 toggle。使用 Noctalia 原生插件管理接口，保留其他源和启用插件，
不创建公共数据目录中的插件。注册只写本会话的私有 GUI 状态；首次使用后持久保留。

## 记录服务

`nyxuri-niri.service` Wants 私有 `nyxuri-clipboard.service`，后者 After 私有 Niri 和
Shell，Requisite Shell，并 BindsTo／PartOf 私有 Niri。没有 Install 段，不启用到
default.target 或 graphical-session.target。Shell 完成显示交接后开始记录。
服务停止时 KillMode=control-group 清理所有子进程；工作进程异常退出则服务重启。
安装只写服务并 daemon-reload，不启动它；下一次登录自动启动。

watch 启动两个 wl-paste --watch（text／image）以及 wl-clip-persist --clipboard both。
文字监听使用 --no-newline，store-text 仅过滤 iNiR 同款浏览器 HTML；普通文字、
原始换行与图片字节不变。CLIPBOARD_STATE 为 nil、clear、sensitive 的事件跳过。
每个子进程独立进程组，终止只针对这些组，不 killall 其他桌面的监听。
watch 的运行锁在 XDG_RUNTIME_DIR，不删除锁 inode。

## 原生共享历史面板

个人 plugin_api=24 插件使用 Noctalia ui.* 原生组件，主框、输入框、字体、圆角、透明度
及颜色角色均由当前 shell 绘制；不声称替换了内置面板的存储后端。
Super+V 再按一次关闭，Esc 或点击外部也关闭；Down／Up 和 Ctrl+J／K 选择，Enter／
点击条目／复制按钮执行 cliphist decode ID → wl-copy，失败时保留当前内容。
选择后用 Ctrl+V 粘贴，不自动模拟按键。私有 backend 的 list 只经进程管道传 JSON，
不将历史列表或文字内容写入文件／日志。

列表以五条为一页，搜索覆盖全部历史，键盘选择会自动翻页，防止超过原生 UI 单层
256 子节点上限。右侧显示选中的完整文字（最多 16,000 字符）或图片预览。
只解码选中的条目，图片放在 `$XDG_RUNTIME_DIR/nyxuri-clipboard-previews/<打开标识>/`，
目录权限 0700、文件 0600，关闭面板清理；旧异步回调只清理自身打开标识，不影响新面板。
关闭后也释放 Luau 历史列表与预览。PNG／JPEG／GIF／WebP 复制保持二进制，
旧浏览器 HTML 文字条目仍按 iNiR 规则清理。

共享资源是历史数据库，监听、面板和预览属于 Nyxuri；顺序注销登录时三套桌面
读取相同历史，不支持同一用户同时运行多个 compositor。

## 验证

`tests/test_personal_clipboard.py` 使用 TempEnv 检查参数数组、文字／图片字节、
原生 cliphist 临时库往返、HTML 清理、非法 ID／失败、原生 toggle、注册源形状、
私有预览权限与清理、私有进程清理及重复部署保留历史和原桌面文件。
插件 lint 与合成数据实机截图核验原生主题、图片预览、开关、方向键／Enter 和 Esc；
实际跨桌面往返登录仍需用户验收。
