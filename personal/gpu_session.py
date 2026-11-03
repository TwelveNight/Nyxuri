#!/usr/bin/env python3
"""Select this private Niri login's renderer, without changing its config argv."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

PRIME = {'__NV_PRIME_RENDER_OFFLOAD': '1', '__GLX_VENDOR_LIBRARY_NAME': 'nvidia',
         '__VK_LAYER_NV_optimus': 'NVIDIA_only'}
GPU_ENV = tuple(PRIME) + (
    'AQ_DRM_DEVICES', 'WLR_NO_HARDWARE_CURSORS', 'WLR_DRM_NO_ATOMIC',
    'LIBVA_DRIVER_NAME', '__GL_VRR_ALLOWED', 'DRI_PRIME',
    '__EGL_VENDOR_LIBRARY_FILENAMES', 'VK_LOADER_DRIVERS_DISABLE',
    'VK_ICD_FILENAMES', 'VK_DRIVER_FILES', 'MESA_VK_DEVICE_SELECT',
    'MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE', 'VDPAU_DRIVER',
    'QT_FFMPEG_DECODING_HW_DEVICE_TYPES', 'INIR_SHELL_GPU_PREFERENCE')


def selection_path(config, runtime):
    key = hashlib.sha256(str(Path(config).resolve()).encode()).hexdigest()
    return Path(runtime) / 'nyxuri-gpu' / key


def prepare_login(config, *, runtime, drm=Path('/sys/class/drm'), dri=Path('/dev/dri')):
    # POSIX process locks survive exec but are NOT inherited by forked apps.
    # Thus a lingering terminal cannot keep a dead compositor's login locked.
    # Another login must fail before touching the watched renderer fragment.
    state = selection_path(config, runtime)
    state.parent.mkdir(mode=0o700, exist_ok=True)
    lock_fd = os.open(state.with_suffix('.lock'), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Nyxuri GPU selection is already running') from None
        connectors = sorted(path.parent.name for path in drm.glob('card*-*/status')
                            if not path.parent.name.split('-', 1)[1].startswith(('eDP-', 'LVDS-', 'DSI-'))
                            and path.read_text().strip() == 'connected')
        renderer, pci = ('nvidia', '0000:01:00.0') if connectors else ('amd', '0000:06:00.0')
        render = dri / 'by-path' / f'pci-{pci}-render'
        card = dri / 'by-path' / f'pci-{pci}-card'
        device = drm / card.resolve().name / 'device'
        if (not render.exists() or not card.exists() or not device.exists()
                or device.resolve().name != pci
                or (device / 'vendor').read_text().strip() != ('0x10de' if connectors else '0x1002')):
            raise ValueError(f'selected GPU {pci} is missing or mismatched')
        fragment = Path(config).resolve().parent / 'personal-gpu-session__custom__.kdl'
        fragment.write_text('debug {\n    render-drm-device ' + json.dumps(str(render)) + '\n}\n'
                            'environment {\n' + ''.join(f'    {name} {json.dumps(value) if connectors else "null"}\n'
                                                        for name, value in PRIME.items()) + '}\n')
        result = dict(config=str(Path(config).resolve()), renderer=renderer, pci=pci, connectors=connectors)
        state.with_suffix('.json').write_text(json.dumps(result) + '\n')
        os.set_inheritable(lock_fd, True)
        return dict(result, lock_fd=lock_fd)
    except BaseException:
        os.close(lock_fd)
        raise


def main(argv=None, *, runtime=None, drm=Path('/sys/class/drm'), dri=Path('/dev/dri')):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('niri', 'shell'))
    parser.add_argument('--config', required=True)
    args = parser.parse_args(argv)
    runtime = Path(runtime) if runtime is not None else Path(os.environ['XDG_RUNTIME_DIR'])
    env = {name: value for name, value in os.environ.items() if name not in GPU_ENV}
    if args.mode == 'niri':
        selection = prepare_login(args.config, runtime=runtime, drm=drm, dri=dri)
        print(f"nyxuri-gpu: pci={selection['pci']} renderer={selection['renderer']} connectors={','.join(selection['connectors']) or 'none'}",
              file=sys.stderr, flush=True)
        # Keep the literal canonical argv: the existing clock controller uses
        # this exact config identity to recognize an authorized Niri session.
        os.execve('/usr/bin/niri', ['/usr/bin/niri', '--session', '--config', args.config], env)
        return selection  # Only reachable when the compositor boundary is mocked.
    state = selection_path(args.config, runtime)
    with state.with_suffix('.lock').open('r+b') as lock:
        try:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise RuntimeError('Nyxuri GPU login is not running')
    selection = json.loads(state.with_suffix('.json').read_text())
    if selection['config'] != str(Path(args.config).resolve()) or selection['renderer'] not in ('amd', 'nvidia'):
        raise ValueError('Invalid Nyxuri login GPU selection')
    if selection['renderer'] == 'nvidia':
        env.update(PRIME)
    script = str(Path(__file__).with_name('runtime.py'))
    os.execve(sys.executable, [sys.executable, script], env)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(f'nyxuri-gpu: {error}') from None
