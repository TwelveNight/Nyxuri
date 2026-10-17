# Bongo Cat 键盘输入

> 本页是个人 Noctalia Bongo Cat 输入选择的契约，以 `personal/bongocat_input.py`、`personal/install.py` 和 `tests/test_personal_bongocat.py` 为准。

## 输入边界

Bongo Cat 是可选的官方 Noctalia 插件。插件和 `evtest` 由用户安装；个人部署不自动安装、启用插件，也不修改输入设备权限、keyd 配置或键盘映射。

不能把 `/dev/input/eventN` 当作键盘身份：设备编号会变化，同一编号可能变成音频插孔或其他设备。解析器每次启动按 sysfs 的设备名精确查找 `keyd virtual keyboard`，只选择存在且可读的节点；多个候选直接报错。不直接读取输入事件。

keyd 不存在时，仅回退到配置指定的内置键盘稳定路径 `/dev/input/by-path/platform-i8042-serio-0-event-kbd`。找不到可读节点就失败，不扩展到所有输入设备。

选择完成后用 `execv` 替换为 `/usr/bin/evtest`，参数是 `['evtest', '<selected-device>']`。沿用官方插件已有输入流，不增加常驻守护进程、轮询、设备抓取或按键日志。

## 部署

- `personal/bongocat_input.py` 复制到私有 `niri/scripts/bongocat_input.py`，保留可执行权限。
- `personal/noctalia-bongocat.toml` 复制到私有 Noctalia 的 `zz-personal-bongocat.toml`，渲染目标 HOME。
- 仅设置 `cat`、`atelier-cat`、`atelier-split-cat` 的 `input_devices` 和 `executable_path`，不改变尺寸、颜色、音频反应或暂停设置。
- 新配置是普通受仓库管理的文件，随个人部署更新；现有 `__custom__` 保留语义不变。GUI 状态优先级高于声明式配置，迁移旧实例时还需核对其 `input_devices` 是否覆盖了新选择器。

设备在输入流启动后被重新创建时，需要重载 Noctalia 配置；不为此默认增加热插拔 watcher。

## 验收

```bash
python3 -m unittest tests.test_personal_bongocat -q
python3 personal/bongocat_input.py --resolve /dev/input/by-path/platform-i8042-serio-0-event-kbd
```

第一条使用 `TempEnv` 隔离 HOME，覆盖编号变化、错误 selector、歧义、稳定回退、准确 exec 参数、实际沙箱部署和目标 HOME 渲染。第二条只输出选择的设备路径，不读取按键。

实机检查要核对有效配置与 evtest 进程参数，确认没有继续监听旧设备。必要时使用官方 `resume` IPC 解除暂停；最终由用户打字确认拍爪，不能仅用“进程运行中”作为动画恢复证明。
