#!/usr/bin/python3
"""Correct WPS mini-toolbar X11 types before xwayland-satellite maps them.

Satellite 0.8.3 treats WPS's KDE_OVERRIDE + NORMAL as a centered toplevel.
A POPUP_MENU retains the app-requested position and normal popup lifetime.
Never unmap/remap client windows or alter document focus/content here.
"""
import fcntl
import os
from pathlib import Path
import time


APPS = {'wps', 'et', 'wpp', 'pdf'}


def is_toolbar(*, app, title, size, minimum, maximum, decorations, transient, types):
    return (app in APPS and title == app and not transient and decorations == 0
            and minimum == maximum == size and 80 <= size[0] <= 600
            and 16 <= size[1] <= 120
            and '_KDE_NET_WM_WINDOW_TYPE_OVERRIDE' in types
            and '_NET_WM_WINDOW_TYPE_NORMAL' in types)


def main():
    from Xlib import X, Xatom, error
    from Xlib.display import Display

    # One helper per X display, including after repeated manual launches.
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    display_name = os.environ.get('DISPLAY', '').replace('/', '_')
    lock = (runtime / ('nyxuri-wps-toolbar-' + display_name + '.lock')).open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    for attempt in range(30):
        try:
            display = Display()
            break
        except error.DisplayConnectionError:
            if attempt == 29:
                raise
            time.sleep(1)
    else:
        raise RuntimeError('X display unavailable')
    root = display.screen().root
    atoms = {name: display.intern_atom(name) for name in (
        '_NET_WM_NAME', 'UTF8_STRING', '_NET_WM_WINDOW_TYPE',
        '_NET_WM_WINDOW_TYPE_POPUP_MENU', '_MOTIF_WM_HINTS')}
    display.set_error_handler(lambda *_: None)  # Clients may disappear at any time.

    def correct(window):
        try:
            wm_class = window.get_wm_class()
            if not wm_class or wm_class[-1] not in APPS:
                return
            name = window.get_full_property(atoms['_NET_WM_NAME'], atoms['UTF8_STRING'])
            title = (bytes(name.value).decode('utf-8', errors='replace') if name
                     else window.get_wm_name())
            geometry = window.get_geometry()
            normal = window.get_wm_normal_hints()
            hints = normal._data if normal else {}
            motif = window.get_full_property(atoms['_MOTIF_WM_HINTS'], X.AnyPropertyType)
            values = list(motif.value) if motif else []
            decorations = values[2] if len(values) >= 3 and values[0] & 2 else None
            types = window.get_full_property(atoms['_NET_WM_WINDOW_TYPE'], Xatom.ATOM)
            type_names = tuple(display.get_atom_name(a) for a in types.value) if types else ()
            def dimensions(prefix):
                w, h = hints.get(prefix + '_width'), hints.get(prefix + '_height')
                return (w, h) if w is not None and h is not None else None
            if is_toolbar(app=wm_class[-1], title=title,
                          size=(geometry.width, geometry.height),
                          minimum=dimensions('min'), maximum=dimensions('max'),
                          decorations=decorations, transient=bool(window.get_wm_transient_for()),
                          types=type_names):
                window.change_property(atoms['_NET_WM_WINDOW_TYPE'], Xatom.ATOM, 32,
                                       [atoms['_NET_WM_WINDOW_TYPE_POPUP_MENU']])
                display.flush()
                print(f'WPS mini-toolbar 0x{window.id:x}: use popup type', flush=True)
        except (error.XError, AttributeError, TypeError, ValueError):
            pass  # Incomplete properties will be retried on PropertyNotify.

    def watch(window):
        window.change_attributes(event_mask=X.PropertyChangeMask)
        correct(window)

    # Subscribe before enumerating to avoid missing newly created client windows.
    root.change_attributes(event_mask=X.SubstructureNotifyMask)
    for window in root.query_tree().children:
        watch(window)
    display.flush()
    print('WPS mini-toolbar watcher ready', flush=True)
    while True:
        event = display.next_event()
        if event.type == X.CreateNotify:
            watch(event.window)
            display.flush()
        elif event.type in (X.PropertyNotify, X.MapNotify):
            correct(event.window)


if __name__ == '__main__':
    main()
