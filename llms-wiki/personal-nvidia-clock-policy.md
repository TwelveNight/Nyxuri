# 个人 NVIDIA 插电时钟策略

> 本页是本机 NVIDIA 时钟策略的契约，以 `personal/nvidia_clock_policy.py` 和 `tests/test_personal_nvidia_clock_policy.py` 为准。

## 范围与原因

这是个人 RTX 3060 Laptop、PCI `0000:01:00.0`、HDMI-A-1 的适配。
Nyxuri、iNiR 和 Hyprland + II 共用一个系统服务，不各自启动锁频任务。
不修改上游默认配置，不随普通 install/update 自动安装或更新系统级文件。
系统平台模式与 NVIDIA 自动调频分别管理；本策略不切换平台模式、CPU governor 或功率限制。

本机在插电、外屏 144 Hz 条件下，空闲后的首次切换测到 55–69 ms 长帧。
核心最低 1200 MHz、显存最低 6001 MHz 时，四轮测量为 7–14 ms。
最高值 2100/7001 MHz 沿用本机支持频率，没有超频。
显卡空闲功耗约从 14 W 增到 21–23 W；其他桌面的鼠标跟手感仍需用户对照验收。
这些数值来自本机诊断，不作为其他硬件的推荐值。

## 运行契约

仅在三个条件同时成立时提高时钟下限：

- AC 电源 online=1。
- NVIDIA HDMI-A-1 connected、enabled，且 DPMS On。
- 指定普通用户正在运行 Nyxuri、iNiR 或 Hyprland + II 的 compositor。

Nyxuri 匹配 `niri --session --config ~/.config/nyxuri-desktop/niri/config.kdl`。
iNiR 匹配本机用户服务的 `niri --session` 默认入口，或显式指定 `~/.config/niri/config.kdl`。
Hyprland 匹配本机默认 `Hyprland` 入口，或显式指定 `~/.config/hypr/hyprland.lua`／`hyprland.conf`。
显式配置参数支持 `--config PATH`、`--config=PATH` 和 `-c PATH`；未知路径、缺参数、
重复指定、其他用户／compositor 与 CLI 查询／校验入口均不匹配。

每两秒检查一次。拔电、关闭／断开外屏、熄屏或退出这三套桌面后恢复自动调频。
无法读取条件时按不满足处理。按 PCI 查找 DRM card，不依赖易变的 card 编号。
缓存的 compositor PID 每轮重新验证归属与参数，不能沿用离开的会话。
检测到恢复运行的时间间隔后重新施加策略；活跃状态每 60 秒重新施加，防止驱动重置后失效。

两个时钟下限任一失败时，尝试重置两个域并记录错误；失败后 15 秒再试。
启动时不满足条件也会清理残留锁频。正常停止有 finally 重置，异常退出有
systemd `ExecStopPost` 重置；驱动不可用时重置可能失败，日志必须说明。
服务拥有这块显卡的时钟锁定策略，不应与其他锁频工具同时使用。

## 安装与恢复

使用已有 Python、nvidia-smi、systemd；不安装新依赖。
系统服务必须运行由 root 拥有的独立副本，不能从可被普通用户修改的仓库或 HOME
执行特权代码。service 模板中的 `@USER@` 在安装前替换为已核实的用户名。
部署只写下面两个系统文件，并 enable/start 服务：

- `/usr/local/libexec/nyxuri-nvidia-clock-policy.py`：root:root，0644。
- `/etc/systemd/system/nyxuri-nvidia-clock-policy.service`：root:root，0644。

更新代码后需显式重新复制上述文件、daemon-reload 并 restart 服务。
普通 Nyxuri 配置更新不会覆盖这个特权副本，当前个人策略也不会进入公共配置。
服务保留原名 `nyxuri-nvidia-clock-policy.service`，支持范围以代码为准；
iNiR／II 无需新增服务或修改 compositor 配置。

查看运行状态和日志：

```bash
systemctl status nyxuri-nvidia-clock-policy.service
journalctl -b -u nyxuri-nvidia-clock-policy.service
nvidia-smi --query-gpu=pstate,clocks.current.graphics,clocks.current.memory,power.draw --format=csv
```

恢复默认并停止后续自动启用：

```bash
sudo systemctl disable --now nyxuri-nvidia-clock-policy.service
```

`ExecStopPost` 会恢复两个时钟域。该操作保留代码和 unit，便于重新启用。
需要彻底移除时，先停止，再删除上述两个系统文件并 daemon-reload。

## 验收

`python3 -m unittest tests.test_personal_nvidia_clock_policy` 在 TempEnv 中覆盖
AC、DPMS、输出、三套桌面入口、用户／会话身份、部分失败回滚、恢复运行重施加和命令参数。
实机检查 root 文件归属、服务 active、空闲频率下限和停服后的自动降频。
拔插电、熄屏／亮屏、注销／登录的物理路径和鼠标手感分别报告，模拟不能替代实际验收。
