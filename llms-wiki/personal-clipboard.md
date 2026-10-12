# 个人共享剪贴板

`personal/clipboard.py` 使用 cliphist 原生配置和数据库，与 iNiR 的 cliphist wrapper
及 ii 的直接 cliphist 调用一致。默认历史库是 `~/.cache/cliphist/db`，不设置私有
`-db-path`、`-config-path` 或缓存根，不迁移、清空已有条目。

## 部署和入口

`personal/install.py:prepare_sources` 将 clipboard.py、clipboard-fuzzel.ini 复制到
私有 Niri scripts，部署后的 shell-action.sh 的 clipboard 动作改为 Python pick。
上游 binds.kdl 的 Mod+V 仍调用该动作；上游配置源码保持原样。
私有 `zz-personal.toml` 设置 `[shell] clipboard_enabled=false`，停止 Noctalia 独立历史面板，
其旧缓存保留。个人安装预检要求 cliphist、wl-paste、wl-copy、wl-clip-persist、fuzzel。
官方安装引导后的个人安装／更新路径通过 atomic_replace_item 部署配置及服务。

## 记录服务

`nyxuri-niri.service` Wants 私有 `nyxuri-clipboard.service`，后者 After 私有 Niri 和
Shell，Requisite Shell，并 BindsTo／PartOf 私有 Niri。没有 Install 段，不启用到
default.target 或 graphical-session.target。Shell 完成显示交接后才能开始记录。
服务停止时 KillMode=control-group 清理所有子进程；工作进程异常退出则服务重启。
安装只写服务并 daemon-reload，不启动它。当前会话首次应用需显式 start，下一次登录自动启动。

watch 启动两个 wl-paste --watch（text／image）以及 wl-clip-persist --clipboard both。
文字监听使用 --no-newline，store-text 仅过滤 iNiR 同款浏览器 HTML；普通文字、
原始换行与图片字节不变。CLIPBOARD_STATE 为 nil、clear、sensitive 的事件跳过。
每个子进程独立进程组，终止只针对这些组，不 killall 其他桌面的监听。
运行锁在 XDG_RUNTIME_DIR，watch／pick 分别持锁，不删除锁 inode。

## 选择历史

pick 将 cliphist list 输出交给 Fuzzel --dmenu --index --only-match，用返回索引选原条目，
再通过 cliphist decode 恢复字节并送给 wl-copy。解码失败或取消时不改当前剪贴板。
旧浏览器 HTML 文字条目同样按 iNiR 规则清理；图片保持二进制数据。Fuzzel 使用携带的
私有配置，不加载公共 Fuzzel 主题；图片条目显示格式和尺寸，不提供缩略图。
选择后按 Ctrl+V 粘贴，不自动模拟按键。不记录历史内容到 stdout／journal。

共享资源是历史数据库，监听、界面和运行锁属于 Nyxuri。顺序注销登录时三套桌面
读取相同历史；不支持同一用户同时运行多个 compositor。Noctalia 原生面板不能替换
存储后端，故不声称它的原生面板与 cliphist 同步。

## 验证

`tests/test_personal_clipboard.py` 使用 TempEnv 检查参数数组、文字和图片字节、
原生 cliphist 临时库往返、HTML 清理、取消／失败、重复选择器、私有进程清理、
重复部署保留历史和原桌面文件。实际跨桌面往返登录仍需用户验收。
