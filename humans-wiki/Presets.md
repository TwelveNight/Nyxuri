Some apps ship flavor variants — presets layer between defaults and your `__custom__` files, so switching never touches your own tweaks.

Built-in official presets:
- **`kitty`**:
  - `default`: standard 90% opacity
  - `transparent`: 75% higher translucency flavor
- **`niri`**:
  - `default`: minimalist frameless layout (default)

---

## Modular Parts slots (Niri)

Beyond full preset bundles, the preset architecture supports modular **Parts slots**, allowing granular hot-swapping of individual visual components:

- **`glow`** (window focus outline & diffused glow):
  - `default`: frameless minimal look without outline or glow
  - `glow`: 2px outline and 28px soft diffused ambient glow for distinct tiling window focus
  - `glow-material-you`: focus glow follows Noctalia's active Material You wallpaper palette (dynamically re-rendered in real time)
- **`effects`** (compositor shader & blur pipeline):
  - `default`: standard window rendering
  - `xray-blur`: backdrop blur and window transparency

Switch parts with `nyxuri preset niri part <slot> <name>`.

---

## Preset commands

| Command | Description |
| :--- | :--- |
| `nyxuri preset <app> list` | List full presets (`*` marks the active one) |
| `nyxuri preset <app> apply <name>` | Switch preset (`apply default` resets) |
| `nyxuri preset <app> parts` | Inspect available Parts slots and variants |
| `nyxuri preset <app> part <slot> <name>` | Hot-swap a single component part (e.g. glow, effects) |
| `nyxuri preset <app> save <name>` | Save the current config as a private preset |
| `nyxuri preset <app> edit <name>` | Edit a private preset in `$EDITOR` |
| `nyxuri preset <app> delete <name>` | Delete a private preset (official ones are read-only) |

Official presets update with `nyxuri update`; private ones live in `~/.config/nyxuri/presets/`.
