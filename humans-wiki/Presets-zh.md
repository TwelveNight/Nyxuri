有些应用自带多套风味——预设叠在默认配置和你的 `__custom__` 之间，切换不会碰你的自定义改动。

内置官方预设：
- **`kitty`**：
  - `default`：标准 90% 不透明度
  - `transparent`：75% 半透明高透风味
- **`niri`**：
  - `default`：极简无边框（默认）

---

## 独立零件插槽 Parts slots (Niri)

除整套预设外，预设体系支持细粒度热插拔的**零件插槽 (Parts)**：

- **`glow`**（窗口焦点轮廓与弥散光晕）：
  - `default`：无轮廓、无光晕极简风
  - `glow`：启用 2px 轮廓与 28px 柔和弥散光晕，增强平铺窗口下的焦点识别
  - `glow-material-you`：聚焦光晕实时跟随 Noctalia 当前壁纸提取的 Material You 配色（动态重绘）
- **`effects`**（合成器着色器与模糊）：
  - `default`：标准窗口渲染
  - `xray-blur`：窗口透光与背景毛玻璃模糊

切换零件指令：`nyxuri preset niri part <slot> <name>`。

---

## 预设管理指令

| 指令 | 作用 |
| :--- | :--- |
| `nyxuri preset <app> list` | 列出应用级完整预设（`*` 标当前活动） |
| `nyxuri preset <app> apply <name>` | 切换预设（`apply default` 回默认） |
| `nyxuri preset <app> parts` | 查看当前应用的零件插槽与可选变体 |
| `nyxuri preset <app> part <slot> <name>` | 切换单个零件部件（如 glow、effects 等） |
| `nyxuri preset <app> save <name>` | 把当前配置存为私有预设 |
| `nyxuri preset <app> edit <name>` | 在 `$EDITOR` 里改私有预设 |
| `nyxuri preset <app> delete <name>` | 删除私有预设（官方预设只读） |

官方预设随 `nyxuri update` 更新；私有预设存在 `~/.config/nyxuri/presets/`。
