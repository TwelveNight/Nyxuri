Nyxuri is a Material You desktop suite and management engine for Arch Linux / CachyOS.
The root README serves as a minimal storefront and bootstrap entrypoint. This Wiki houses the full configuration layout, preset details, complete keybindings, CLI tooling matrix, and troubleshooting guides.

### Install from the AUR (Arch / CachyOS, recommended)

```bash
paru -S nyxuri-git        # management engine + config units + Nyxuri Shell, one package
nyxuri install full       # or assemble the desktop per unit: nyxuri on <unit>
```
> Installing enters system-package mode: updates are handled by pacman. Desktop apps are not bundled — enabling a unit installs only what that unit needs.

---

## Documentation Index

| Topic | Summary | Reference |
| :--- | :--- | :--- |
| Units, Configs & Customization | Directory tree, Dunder protocol preservation, hooks architecture | [Read guide](Configuration) |
| Presets & Modular Parts | Official Kitty/Niri presets, Parts slots, custom presets | [Read guide](Presets) |
| Complete Keybindings | Window & column navigation, shell action gateway, nyxhelp | [Read guide](Keybindings) |
| CLI Reference Manual | Units, install, update, snapshot rollback, doctor, uninstall matrix | [Read guide](CLI-Reference) |
| Troubleshooting Guide | DDC bus conflict, hybrid GPU video artifacts, CSS cleanups | [Read guide](Troubleshooting) |
