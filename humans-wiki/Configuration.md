```text
Nyxuri
├── install.sh                  # lightweight bootstrap entrypoint
├── catalog.toml                # package catalogue (17 standalone apps without dotfiles)
├── nyxuri/                     # Python core engine (zero pip dependencies)
├── shell/                      # Nyxuri Shell (QML/Qt6 desktop shell, experimental)
└── units/                      # 12 modular desktop capability units
    ├── fastfetch/              # system information
    ├── fcitx5-rime/            # dynamic Material You input skin & Rime config
    ├── fish/                   # shell aliases & functions
    ├── greeter/                # Noctalia Greeter login integration
    ├── kitty/                  # terminal emulator & opacity presets
    ├── mango/                  # MangoWM window manager & session scripts
    ├── niri/                   # window manager & session scripts
    ├── noctalia/               # desktop shell, theme sync, Orbit & wallpaper picker
    ├── starship/               # prompt styling
    ├── wallpapers/             # companion wallpapers & video pack hooks
    ├── xdg-desktop-portal/     # portal routing (theme sync, screencast)
    └── zed/                    # editor configuration
```

Configs deploy atomically. Personal tweaks survive updates via the Dunder protocol:
- Any file (e.g. `__custom__.kdl`, `__custom__.conf`) or folder containing `__custom__` is preserved.
- `~/.config/niri/monitor.kdl` is kept across deployments.

---

## How to customize (Dunder Protocol)

Any file or folder containing `__custom__` survives updates and preset switches:

- **Loaded per-app**: each app uses its native include mechanism — Niri includes `__custom__.kdl`, Kitty includes `__custom__.conf`, while Fish autoloads files under `conf.d/`.
- **Modular & composable**: to split tweaks across multiple files, simply include them from your main custom file (e.g. put `include "my_rules__custom__.kdl"` inside `__custom__.kdl` — all files containing `__custom__` remain preserved).
- **Dedicated files**: files referenced by name like `~/.config/niri/monitor.kdl` are preserved automatically; edit them directly.

---

## Hooks Architecture

Nyxuri separates finishing automation into two isolated layers:

### 1. User Post-Deploy Hooks (`~/.config/nyxuri/hooks/`)
Put personal finishing scripts in `~/.config/nyxuri/hooks/`. Any script ending in `.sh` runs in alphanumeric filename order after normal config deployments (`nyxuri install` or updates) with a 30-second timeout. A failed or timed-out script prints a diagnostic warning without interrupting the rest. `nyxuri test` skips user hooks, and uninstallation preserves them.

### 2. Unit Lifecycle Hooks (`units/<unit>/hooks/`)
Units declare their own lifecycle side effects in `units/<unit>/manifest.toml` (e.g. `post_install = "setup-rime"`, `install-pack` for wallpaper downloads). These scripts are unit-owned and run strictly through the transaction engine during unit activation (`nyxuri on`), deactivation (`nyxuri off`), or hook replay after updates (`transaction.replay_enabled_hooks()`). Users do not manually place scripts here.
