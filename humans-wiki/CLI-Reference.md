`nyxuri` manages installation, snapshots and diagnostics. Interactive deployments create a snapshot in `~/.config/nyxuri/backups/` by default.

> Legacy Bash users must run the bootstrap entrypoint before using these commands. The old `nyxniri update` cannot perform the directory migration.

---

## Units (the market verbs)

| Command | Description |
| :--- | :--- |
| `nyxuri list [unit]` | Every unit with its switch state and active preset, or one unit in detail |
| `nyxuri on <unit> [--preset <name>]` | Enable a unit (dependencies and missing packages disclosed first); same as `enable` |
| `nyxuri off <unit> [--cascade]` | Disable a unit — custom files go to the vault, managed files wiped; same as `disable` |
| `nyxuri doctor [unit]` | Three-state reconciliation (`Synced` / `Drifted` / `Ghost`) plus a system checkup |

Everything on the desktop is a unit — including wallpapers: `nyxuri on wallpapers`
deploys the built-in fallback into `~/Pictures/Wallpapers`; the full video pack is
user-domain content installed via `units/wallpapers/hooks/install-pack`.

---

## Deployment & themes

| Command | Description |
| :--- | :--- |
| `nyxuri install [full\|config]` | Legacy full pipeline (configs + wallpapers unit + hook replay), or configs only |
| `nyxuri update [--force\|--no-deploy] [--to <tag\|commit>]` | Update source; force config deployment or skip it; pin a version |
| `nyxuri preset <app> [list\|apply <name>\|save <name>\|edit <name>\|delete <name>]` | Switch / manage presets |
| `nyxuri preset <app> [parts\|part <slot> <name>]` | Inspect / hot-swap component parts (effects, glow, …) |
| `nyxuri theme [toggle\|dark\|light\|sync\|status]` | Switch or sync the dark/light axis |
| `nyxuri shell [get\|set <noctalia\|nyxuri-shell> [bin_path]\|switch [<target> [bin_path]]\|status]` | Inspect or hot-switch the desktop shell slot (experimental) |

---

## Supply

| Command | Description |
| :--- | :--- |
| `nyxuri deps [core\|apps]` | Core dependency checklist, or the recommended-software menu (catalog + optional units) |
| `nyxuri pkg <install\|upgrade\|remove\|search\|info\|installed>` | Direct package management; search accepts `aur` / `pac` prefixes |
| `nyxuri clean [-n] [--only <tasks>]` | Cache sweeper; `-n` previews only |

---

## Snapshots

| Command | Description |
| :--- | :--- |
| `nyxuri snapshot [note]` | Save current config state |
| `nyxuri snapshot list` | List snapshots |
| `nyxuri snapshot delete [index]` | Delete snapshots (multi-select if no index) |
| `nyxuri rollback [index]` | Restore a snapshot |

---

## System

| Command | Description |
| :--- | :--- |
| `nyxuri doctor [unit]` | Unit reconciliation + dependency and system health check |
| `nyxuri bug` | Export a diagnostic report |
| `nyxuri test` | Developer sandbox deploy (no backup, keeps monitor.kdl) |
| `nyxuri uninstall [--all\|standard\|restore\|purge]` | Checkbox uninstall — pick what gets cleaned (or run standard, restore, purge, --all directly) |
| `nyxuri help` | Show CLI help and usage |

---

## Retired names (KM3.5)

`deploy` `backup` `restore` `remove` `purge` `recommended` `apps` `wp` `wallpapers`
`report` and the module verbs `greeter` `fcitx` `gtk` `fisher` are gone — they are
plain unknown commands now. Use the unit verbs (`on` / `off`) and the state verbs
(`snapshot` / `rollback` / `uninstall`) instead.

---

## Quick reference: nyxhelp

`nyxhelp` is an `fzf`-based cheat sheet covering the CLI, shell helpers and core keybindings:

| Command | Description |
| :--- | :--- |
| `nyxhelp` | Two-pane interactive cheat menu |
| `nyxhelp keys` | Niri keybindings |
| `nyxhelp proxy` | Proxy control (`proxy_on [port]`, `proxy_off`, `proxy_status`) |
| `nyxhelp pkg` | Package shortcuts (`up`, `in`, `se`, `un`, `clean`) |
| `nyxhelp all` | Full cheat sheet |
