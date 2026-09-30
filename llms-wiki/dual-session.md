# Personal dual session

此页面描述 `night/personal-overlay` 的双会话特例。实机安装步骤见
[`personal/README.md`](../personal/README.md)。

## 部署边界

`personal/install.py` 是该分支的配置部署入口。它通过
`_phase_atomic_deployment` 只部署 `niri`、`noctalia` 和 `kitty-nyxuri`，
再用 `atomic_replace_item` 安装 niri 专属 Portal 路由，
并向壁纸目录补齐离线基础图片。入口不运行默认安装后的
主题同步、GTK 渲染、Fisher、Fcitx 皮肤或 Greeter 安装。
成功后写入 `~/.config/nyxuri/personal-mode`；普通 CLI 的无参数、
`install`、`deploy`、`update` 路径会拒绝执行，避免随后覆写已有应用配置。

## 运行时

Hyprland 保持当前 Kitty 配置及 ii 生成的颜色；niri 设置
`KITTY_CONFIG_DIRECTORY` 指向 `kitty-nyxuri`，加载现有 Kitty 设置后
用 Noctalia 单独生成的颜色覆盖。Kitty 字体、键位和 Shell 仍取现有配置。
Noctalia 的 GTK、Qt、Starship、Fcitx 输出关闭，niri 使用 KDE Qt 平台主题。

个人部署不改 ii/skwd 的用户服务和自启动链接。Noctalia 的壁纸及其配色
由自身状态管理。壁纸资源目录可共用，壁纸选择状态分开；同一用户的
systemd 服务可跨会话存活，需要登录后检查渲染进程是否重叠。

## 范围

此分支只准备文件。GDM 的 `personal/nyxuri.desktop` 需在 niri 安装后
部署到系统会话目录，往返登录实测才可确认两边视觉无串色。
