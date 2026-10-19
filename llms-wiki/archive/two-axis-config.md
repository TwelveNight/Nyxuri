# Two-Axis Config — 可选 / 有配置 解耦

> 一个单元有两个**独立**属性："有没有配置" 和 "是不是可选软件"。两轴正交，不绑一起。
> 源码：`nyxuri/deploy/manifest.py`。

## 为什么解耦

二元模型：有配置 = 必装，无配置 = 可选。问题：给一个可选软件加配置会"毕业"成必装
（不想）。用户可能兴致大发给 nautilus 挂个配置，但 nautilus 该**一直保持可选**（不是所有人
用 GNOME 文件管理器）。

解耦后两轴独立：
- **有配置（axis A）**：`configs/<unit>/` 目录里 ship 了真实配置 → 部署进 `~/.config`
- **可选（axis B）**：manifest 声明 `optional = true` → 进应用菜单、PKGBUILD `optdepends`

一个单元可以是：可选+无配置（nautilus 现状——目录里只有 manifest）、必装+有配置
（niri/kitty）、**可选+有配置**（zed / mango 现状——既有配置又登进可选菜单）、或都
不沾（不存在——纯空目录无意义）。

## 两个 discover 函数（独立查询）

| 函数 | 看什么 | 干啥 | 返回 |
|---|---|---|---|
| `discover_deployable_apps()` | 目录里除 manifest 外有无真实文件 | 部署进 `~/.config` | ship 配置的单元 |
| `discover_optional_apps()` | manifest 的 `optional` 声明 | 应用菜单 + optdepends | `optional = true` 的单元 |

`discover_manifest_apps()` 纯目录扫描，返回 `(name, ModuleManifest)` 列表——每单元一条，
两轴事实都在同一条记录上（`is_deployable` 与 `is_optional` 各自独立为真）。

## gen-deps 的判别（axis B 优先）

```python
for _name, m in discover_manifest_apps():
    if m.is_optional:           # axis B → optdepends（即使也有配置目录）
        optdepends += packages
    elif m.is_deployable:      # axis A only → depends（必装）
        depends += packages
```

is_optional 先判——可选+配置的单元进 optdepends（保持可选），不进 depends。

## "加配置不毕业"的场景（用户要的）

nautilus 现在可选、无配置（目录里只有 manifest.toml）。将来兴致大发加配置：

```bash
mkdir -p configs/nautilus && 放配置文件
```

立刻：`discover_deployable_apps()` 认出它 → 部署它的配置。
但 manifest 仍声明 `optional = true` → 仍在应用菜单、仍是 optdepends。
**两条轴互不干扰**，加配置不会误伤可选性。毕业（从可选变必装）= 主动删掉 manifest 里的
`optional = true`，不是被动触发。

## 单元目录即登记载体

可选软件住 `configs/<unit>/`（哪怕只有 manifest），只为让应用菜单和 PKGBUILD optdepends
知道"有这么个可选单元、包名叫啥"——单一扫描路径，不加第二处。
`.optional-apps.toml` 中心登记簿已随 KM1 ② 物理删除：登记分散进各单元自己的
manifest，**加可选软件 = 加一个目录 + 几行例外**，不碰代码、不加中心文件。
字段详见 [manifest-schema](manifest-schema.md)。

## 替代了什么

旧 `deps.py` 的 `_OPT_APP_PKG_MAP` 硬编码 dict（"nautilus"→["nautilus"]…）被这套数据化
取代；旧 `.optional-apps.toml` 中心登记簿又被单元自描述取代——两层替代，同一个方向：
数据住进单元自己身上。
