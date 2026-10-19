pragma Singleton

import QtQuick
import Quickshell

// UnitCatalog — the host-side declaration of the twelve Shell units
// (unit-model.md §6). One row per shell/units/<domain>/ blueprint.
//
// The six-slot taxonomy is Shell-side knowledge (kernel §6 keeps only the
// ledger, the event channel and dotted ids), so slot and component source
// live here. `order` is stacking order (bottom → top) and preserves the
// exact window layering of the pre-KM4 AppShell.
//
// Unit switches toggle the domain's EXISTENCE — its surfaces, windows and
// unit-owned IPC handlers. Domain services that other domains read
// (NotificationService feeds, wallpaper state for the theme pipeline) stay
// app-level by design; e.g. `wallpaper` off unloads the wallpaper visual,
// while the compositor's own desktop background shows through.
//
// Kept in sync with shell/units/ by shell/tests/test_unit_catalog.py.
Singleton {
    id: root

    readonly property var units: [
        {
            "id": "wallpaper",
            "label": "Wallpaper",
            "slot": "surface:desktop",
            "source": "../units/wallpaper/WallpaperBackground.qml"
        },
        {
            "id": "desktopcards",
            "label": "Desktop Cards",
            "slot": "surface:desktop",
            "source": "../units/desktopcards/DesktopCardHost.qml"
        },
        {
            "id": "bar",
            "label": "Status Bar",
            "slot": "edge",
            "source": "../units/bar/Bar.qml"
        },
        {
            "id": "dock",
            "label": "Dock",
            "slot": "edge",
            "source": "../units/dock/DockHost.qml"
        },
        {
            "id": "keystone",
            "label": "Keystone Island",
            "slot": "island",
            "source": "../units/keystone/Keystone.qml"
        },
        {
            "id": "notifications",
            "label": "Notifications",
            "slot": "popup:notification",
            "source": "../units/notifications/NotificationPopupHost.qml"
        },
        {
            "id": "regionselector",
            "label": "Region Selector",
            "slot": "overlay",
            "source": "../units/regionselector/RegionSelector.qml"
        },
        {
            "id": "sidebars",
            "label": "Sidebars",
            "slot": "drawer",
            "source": "../units/sidebars/SidebarHostWindow.qml"
        },
        {
            "id": "lock",
            "label": "Lock Screen",
            "slot": "overlay",
            "source": "../units/lock/Lock.qml"
        },
        {
            "id": "session",
            "label": "Session",
            "slot": "overlay",
            "source": "../units/session/SessionHost.qml"
        },
        {
            "id": "settings",
            "label": "Settings",
            "slot": "overlay",
            "source": "../units/settings/SettingsHost.qml"
        },
        {
            "id": "launcher",
            "label": "Launcher",
            "slot": "overlay",
            "source": "../units/launcher/LauncherHost.qml"
        }
    ]
}
