"""Login-only GPU selection uses real sysfs/by-path fixtures in a private HOME."""
import importlib.util
import os
from pathlib import Path
import unittest
import subprocess
import sys
import time
import json
from unittest.mock import patch

from tests.utils import TempEnv

ROOT = Path(__file__).resolve().parents[1]


class TestPersonalGpuSession(unittest.TestCase):
    def load_policy(self):
        source = ROOT / "personal/gpu_session.py"
        self.assertTrue(source.is_file(), "missing login-only GPU wrapper")
        spec = importlib.util.spec_from_file_location("personal_gpu_session_test", source)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, home):
        drm = home / "sys/class/drm"
        dri = home / "dev/dri"
        (dri / "by-path").mkdir(parents=True)
        drm.mkdir(parents=True)
        for pci, card, vendor in (("0000:06:00.0", "card8", "0x1002"),
                                  ("0000:01:00.0", "card3", "0x10de")):
            device = home / "sys/devices" / pci
            device.mkdir(parents=True)
            (device / "vendor").write_text(vendor + "\n")
            (drm / card).mkdir()
            (drm / card / "device").symlink_to(device)
            for suffix, node in (("card", card), ("render", "renderD" + card[4:])):
                (dri / node).touch()
                (dri / "by-path" / f"pci-{pci}-{suffix}").symlink_to("../" + node)
        self.connector(drm, "card8-eDP-2", "connected")
        self.connector(drm, "card3-eDP-1", "disconnected")
        config = home / "profile/niri/config.kdl"
        config.parent.mkdir(parents=True)
        config.write_text('include "monitor.kdl"\ninclude "personal-gpu.kdl"\ninclude optional=true "__custom__.kdl"\n')
        (config.parent / "monitor.kdl").write_text('output "eDP-2" {}\n')
        (config.parent / "personal-gpu.kdl").write_text('// installed sentinel; never rewrite\n')
        runtime = home / "runtime"
        runtime.mkdir(mode=0o700)
        return config, runtime, drm, dri

    def connector(self, drm, name, status):
        connector = drm / name
        connector.mkdir(exist_ok=True)
        (connector / "status").write_text(status + "\n")

    def test_only_internal_panel_selects_amd(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            policy = self.load_policy()
            result = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            self.assertEqual(result["renderer"], "amd")
            self.assertEqual(result["pci"], "0000:06:00.0")
            gpu = (config.parent / "personal-gpu-session__custom__.kdl").read_text()
            self.assertIn(str(dri / "by-path/pci-0000:06:00.0-render"), gpu)
            self.assertIn('__NV_PRIME_RENDER_OFFLOAD null', gpu)
            self.assertNotIn('NVIDIA_only', gpu)


    def test_connected_external_selects_nvidia(self):
        for connector in ("card3-HDMI-A-1", "card3-DP-2", "card8-DP-4"):
            with self.subTest(connector=connector), TempEnv() as ctx:
                config, runtime, drm, dri = self.fixture(ctx.home)
                self.connector(drm, connector, "connected")
                result = self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)
                self.assertEqual(result["renderer"], "nvidia")
                self.assertEqual(result["pci"], "0000:01:00.0")
                self.assertEqual(result["connectors"], [connector])
                gpu = (config.parent / "personal-gpu-session__custom__.kdl").read_text()
                self.assertIn(str(dri / "by-path/pci-0000:01:00.0-render"), gpu)
                self.assertIn('__NV_PRIME_RENDER_OFFLOAD "1"', gpu)
                self.assertIn('__GLX_VENDOR_LIBRARY_NAME "nvidia"', gpu)
                self.assertIn('__VK_LAYER_NV_optimus "NVIDIA_only"', gpu)


    def test_missing_selected_device_refuses_before_writing(self):
        for external, suffix in ((False, "render"), (False, "card"), (True, "render"), (True, "card")):
            with self.subTest(external=external, suffix=suffix), TempEnv() as ctx:
                config, runtime, drm, dri = self.fixture(ctx.home)
                if external:
                    self.connector(drm, "card3-HDMI-A-1", "connected")
                pci = "0000:01:00.0" if external else "0000:06:00.0"
                (dri / "by-path" / f"pci-{pci}-{suffix}").unlink()
                before = {p: p.read_bytes() for p in config.parent.iterdir()}
                with self.assertRaisesRegex(ValueError, "selected GPU"):
                    self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)
                self.assertEqual(before, {p: p.read_bytes() for p in config.parent.iterdir()})

    def test_wrong_pci_or_vendor_refuses_selection(self):
        for wrong in ("pci", "vendor"):
            with self.subTest(wrong=wrong), TempEnv() as ctx:
                config, runtime, drm, dri = self.fixture(ctx.home)
                if wrong == "pci":
                    alias = dri / "by-path/pci-0000:06:00.0-card"
                    alias.unlink()
                    alias.symlink_to("../card3")
                else:
                    (drm / "card8/device/vendor").write_text("0x10de\n")
                with self.assertRaisesRegex(ValueError, "selected GPU"):
                    self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)


    def test_second_login_cannot_rewrite_a_running_selection(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            policy = self.load_policy()
            first = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            fragment = config.parent / "personal-gpu-session__custom__.kdl"
            before = fragment.read_bytes()
            self.connector(drm, "card3-HDMI-A-1", "connected")
            code = ('from pathlib import Path; from personal.gpu_session import prepare_login; '
                    f'prepare_login(Path({str(config)!r}),runtime=Path({str(runtime)!r}),'
                    f'drm=Path({str(drm)!r}),dri=Path({str(dri)!r}))')
            attempt = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(attempt.returncode, 0)
            self.assertIn('already running', attempt.stderr)
            self.assertEqual(before, fragment.read_bytes())
            self.assertTrue(os.get_inheritable(first["lock_fd"]))
            os.close(first["lock_fd"])
            second = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            self.addCleanup(os.close, second["lock_fd"])
            self.assertEqual(second["renderer"], "nvidia")


    def test_private_service_launch_keeps_clock_controller_argv(self):
        from personal import install
        with TempEnv() as ctx:
            staged = ctx.home / "staged"
            staged.mkdir()
            install.prepare_sources(staged)
            self.assertTrue((staged / "niri/scripts/gpu_session.py").is_file())
            selector = (staged / "niri/personal-gpu.kdl").read_text()
            self.assertIn('include optional=true "personal-gpu-session__custom__.kdl"', selector)
            self.assertNotIn('render-drm-device', selector)
            niri_unit = (ROOT / "personal/nyxuri-niri.service").read_text()
            self.assertIn('/usr/bin/python3 %h/.config/niri/scripts/gpu_session.py niri --config %h/.config/niri/config.kdl', niri_unit)
            shell_unit = (ROOT / "personal/nyxuri-shell.service").read_text()
            self.assertIn('/usr/bin/python3 %h/.config/niri/scripts/gpu_session.py shell --config %h/.config/niri/config.kdl', shell_unit)
            self.assertNotIn('Environment=__NV_PRIME_RENDER_OFFLOAD=1', shell_unit)

    def test_exec_keeps_original_config_and_shell_uses_same_login_selection(self):
        for external in (False, True):
            with self.subTest(external=external), TempEnv() as ctx:
                config, runtime, drm, dri = self.fixture(ctx.home)
                alias = ctx.home / ".config/niri"
                alias.symlink_to(config.parent)
                original = str(alias / "config.kdl")
                if external:
                    self.connector(drm, "card3-DP-1", "connected")
                policy = self.load_policy()
                self.assertTrue(callable(getattr(policy, "main", None)), "missing GPU-aware exec wiring")
                installed_before = {p: p.read_bytes() for p in config.parent.iterdir()}
                inherited = {"__NV_PRIME_RENDER_OFFLOAD": "stale", "__GLX_VENDOR_LIBRARY_NAME": "stale",
                             "__VK_LAYER_NV_optimus": "stale", "DRI_PRIME": "1", "VK_DRIVER_FILES": "/old/icd.json"}
                with patch.dict(os.environ, inherited), patch.object(policy.os, "execve") as execute:
                    selection = policy.main(["niri", "--config", original], runtime=runtime, drm=drm, dri=dri)
                self.addCleanup(os.close, selection["lock_fd"])
                binary, arguments, env = execute.call_args.args
                self.assertEqual(binary, "/usr/bin/niri")
                self.assertEqual(arguments, ["/usr/bin/niri", "--session", "--config", original])
                from personal.nvidia_clock_policy import Conditions
                proc = ctx.home / "proc/123"
                proc.mkdir(parents=True)
                (proc / "comm").write_text("niri\n")
                (proc / "cmdline").write_bytes(b"\0".join(os.fsencode(arg) for arg in arguments) + b"\0")
                self.assertTrue(Conditions(os.getuid(), original).matches_session(proc))
                for name in inherited:
                    self.assertNotIn(name, env)
                for path, content in installed_before.items():
                    self.assertEqual(path.read_bytes(), content)
                # A hotplug after admission must NOT recalculate the shell policy.
                self.connector(drm, "card3-DP-1", "disconnected" if external else "connected")
                code = ('import json; from pathlib import Path; from personal import gpu_session as p; '
                        f'keys={tuple(inherited)!r}; '
                        'p.os.execve=lambda exe,args,env: print(json.dumps([exe,args,{key:env[key] for key in keys if key in env}])); '
                        f'p.main(["shell","--config",{original!r}],runtime=Path({str(runtime)!r}))')
                with patch.dict(os.environ, inherited):
                    captured = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=5)
                self.assertEqual(captured.returncode, 0, captured.stderr)
                binary, arguments, env = json.loads(captured.stdout)
                self.assertEqual(binary, __import__('sys').executable)
                self.assertEqual(arguments, [binary, str(ROOT / "personal/runtime.py")])
                self.assertNotIn("DRI_PRIME", env)
                self.assertNotIn("VK_DRIVER_FILES", env)
                if external:
                    self.assertEqual(env["__NV_PRIME_RENDER_OFFLOAD"], "1")
                    self.assertEqual(env["__GLX_VENDOR_LIBRARY_NAME"], "nvidia")
                    self.assertEqual(env["__VK_LAYER_NV_optimus"], "NVIDIA_only")
                else:
                    for name in inherited:
                        self.assertNotIn(name, env)


    def test_shell_refuses_stale_login_record(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            policy = self.load_policy()
            admitted = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            os.close(admitted["lock_fd"])
            with patch.object(policy.os, "execve") as execute:
                with self.assertRaisesRegex(RuntimeError, "not running"):
                    policy.main(["shell", "--config", str(config)], runtime=runtime)
            execute.assert_not_called()

    def test_disconnected_outputs_and_internal_connector_families_do_not_trigger_nvidia(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            for name, status in (("card3-eDP-1", "connected"), ("card3-LVDS-1", "connected"),
                                 ("card8-DSI-1", "connected"), ("card3-HDMI-A-1", "disconnected"),
                                 ("card3-DP-1", "unknown")):
                self.connector(drm, name, status)
            result = self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            self.addCleanup(os.close, result["lock_fd"])
            self.assertEqual(result["renderer"], "amd")
            self.assertEqual(result["connectors"], [])


    def test_login_lock_survives_real_exec_boundary(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            ready = ctx.home / "exec-ready"
            fake = ctx.home / "fake-niri"
            fake.write_text('#!/usr/bin/python3\nimport pathlib,time\n'
                            + f'pathlib.Path({str(ready)!r}).write_text("ready")\n'
                            + 'time.sleep(30)\n')
            fake.chmod(0o700)
            code = ('import importlib.util,os; from pathlib import Path; '
                    f's=importlib.util.spec_from_file_location("gpu",{str(ROOT / "personal/gpu_session.py")!r}); '
                    'p=importlib.util.module_from_spec(s); s.loader.exec_module(p); real=os.execve; '
                    f'p.os.execve=lambda exe,args,env: real({str(fake)!r},args,env); '
                    f'p.main(["niri","--config",{str(config)!r}],runtime=Path({str(runtime)!r}),'
                    f'drm=Path({str(drm)!r}),dri=Path({str(dri)!r}))')
            child = subprocess.Popen([sys.executable, '-B', '-c', code], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "exec fixture failed to start")
                before = (config.parent / "personal-gpu-session__custom__.kdl").read_bytes()
                self.connector(drm, "card3-DP-1", "connected")
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)
                self.assertEqual(before, (config.parent / "personal-gpu-session__custom__.kdl").read_bytes())
            finally:
                child.terminate()
                _, errors = child.communicate(timeout=5)
            self.assertIn('pci=0000:06:00.0 renderer=amd connectors=none', errors)
            selection = self.load_policy().prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            self.addCleanup(os.close, selection["lock_fd"])
            self.assertEqual(selection["renderer"], "nvidia")


    def test_lingering_app_descriptor_does_not_block_next_login(self):
        with TempEnv() as ctx:
            config, runtime, drm, dri = self.fixture(ctx.home)
            policy = self.load_policy()
            first = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(write_fd)
                os.read(read_fd, 1)
                os._exit(0)
            os.close(read_fd)
            os.close(first["lock_fd"])
            try:
                second = policy.prepare_login(config, runtime=runtime, drm=drm, dri=dri)
                self.addCleanup(os.close, second["lock_fd"])
            finally:
                os.close(write_fd)
                os.waitpid(pid, 0)


if __name__ == "__main__":
    unittest.main()
