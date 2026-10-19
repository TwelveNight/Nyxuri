"""AC/session/display gating and clock rollback without touching a real GPU."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import call, patch

from tests.utils import TempEnv

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("nvidia_clock_policy", ROOT / "personal/nvidia_clock_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class TestPersonalNvidiaClockPolicy(unittest.TestCase):
    def setUp(self):
        self.ctx = TempEnv().__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)

    def conditions(self):
        sys = self.ctx.home / "sys"
        proc = self.ctx.home / "proc"
        config = self.ctx.home / ".config/niri/config.kdl"
        ac = sys / "class/power_supply/ADP0"
        output = sys / "class/drm/card7-HDMI-A-1"
        session = proc / "1234"
        for directory in (ac, output, session):
            directory.mkdir(parents=True)
        for path, value in ((ac / "type", "Mains"), (ac / "online", "1"),
                            (output / "status", "connected"), (output / "enabled", "enabled"),
                            (output / "dpms", "On"), (session / "comm", "niri")):
            path.write_text(value)
        (session / "cmdline").write_bytes(b"/usr/bin/niri\0--session\0--config\0" + os.fsencode(config) + b"\0")
        return policy.Conditions(os.getuid(), config, sys, proc), ac, output, session

    def test_internal_only_and_mixed_displays_require_one_awake_connector(self):
        conditions, ac, external, session = self.conditions()
        external.joinpath('status').write_text('disconnected')
        external.joinpath('enabled').write_text('disabled')
        internal = conditions.sys / 'class/drm/card1-eDP-2'
        internal.mkdir(parents=True)
        for name, value in [('status', 'connected'), ('enabled', 'enabled'), ('dpms', 'On')]:
            (internal / name).write_text(value)
        self.assertTrue(conditions.wanted()[0])
        (ac / 'online').write_text('0')
        self.assertFalse(conditions.wanted()[0])
        (ac / 'online').write_text('1')
        (internal / 'dpms').write_text('Off')
        self.assertFalse(conditions.wanted()[0])
        (external / 'status').write_text('connected')
        (external / 'enabled').write_text('enabled')
        self.assertTrue(conditions.wanted()[0])
        (external / 'dpms').unlink()
        self.assertFalse(conditions.wanted()[0])

    def test_conditions_fail_closed_on_battery_sleep_disconnect_or_other_session(self):
        conditions, ac, output, session = self.conditions()
        self.assertTrue(conditions.wanted()[0])
        for path, disabled, enabled in ((ac / "online", "0", "1"),
                                        (output / "dpms", "Off", "On"),
                                        (output / "enabled", "disabled", "enabled"),
                                        (output / "status", "disconnected", "connected")):
            path.write_text(disabled)
            self.assertFalse(conditions.wanted()[0], str(path))
            path.write_text(enabled)
        (session / "cmdline").write_bytes(b"/usr/bin/niri\0--config\0/home/other/.config/niri/config.kdl\0")
        self.assertFalse(conditions.wanted()[0])
        (session / "cmdline").write_bytes(b"/usr/bin/niri\0--config\0")
        self.assertFalse(conditions.wanted()[0])
        (ac / "online").unlink()
        self.assertFalse(conditions.wanted()[0])

    def test_cached_session_is_revalidated_and_user_is_checked(self):
        conditions, _, _, session = self.conditions()
        self.assertTrue(conditions.session_active())
        self.assertEqual(conditions.pid, session.name)
        conditions.uid += 1
        self.assertFalse(conditions.session_active())
        conditions.uid -= 1
        (session / "comm").write_text("weston")
        self.assertFalse(conditions.session_active())

    def test_three_desktop_launches_and_explicit_config_forms(self):
        conditions, _, _, session = self.conditions()
        root = self.ctx.home / ".config"
        for comm, args in (
                ("niri", ["/usr/bin/niri", "--session", "--config", conditions.config]),
                ("niri", ["/usr/bin/niri", "--session"]),
                ("niri", ["/usr/bin/niri", "--session", "-c", str(root / "niri/config.kdl")]),
                ("niri", ["/usr/bin/niri", "--session", "--config=" + str(root / "niri/config.kdl")]),
                ("Hyprland", ["/usr/bin/Hyprland"]),
                ("Hyprland", ["/usr/bin/Hyprland", "--config", str(root / "hypr/hyprland.lua")]),
                ("Hyprland", ["/usr/bin/Hyprland", "-c", str(root / "hypr/hyprland.conf")])):
            with self.subTest(args=args):
                (session / "comm").write_text(comm)
                (session / "cmdline").write_bytes(b"\0".join(os.fsencode(arg) for arg in args) + b"\0")
                self.assertTrue(conditions.wanted()[0])
        # The cached PID now belongs to an unrelated compositor: stop matching it.
        (session / "comm").write_text("weston")
        self.assertFalse(conditions.wanted()[0])

    def test_reject_cli_clients_unknown_configs_and_malformed_options(self):
        conditions, _, _, session = self.conditions()
        for comm, args in (
                ("niri", ["/usr/bin/niri", "msg", "outputs"]),
                ("niri", ["/usr/bin/niri", "validate", "-c", conditions.config]),
                ("niri", ["/usr/bin/niri", "--session", "--config"]),
                ("niri", ["/usr/bin/niri", "--session", "--config", "--session"]),
                ("niri", ["/usr/bin/niri", "--session", "--config=/tmp/test.kdl"]),
                ("niri", ["/usr/bin/niri", "--session", "--config", conditions.config, "-c", conditions.config]),
                ("Hyprland", ["/usr/bin/Hyprland", "--config", "/tmp/test.lua"]),
                ("Hyprland", ["/usr/bin/Hyprland", "--config="]),
                ("Hyprland", ["/usr/bin/Hyprland", "--help"]),
                ("Hyprland", ["/usr/bin/Hyprland", "--verify-config"]),
                ("Hyprland", ["/usr/bin/other"])):
            with self.subTest(args=args):
                (session / "comm").write_text(comm)
                (session / "cmdline").write_bytes(b"\0".join(os.fsencode(arg) for arg in args) + b"\0")
                self.assertFalse(conditions.wanted()[0])

    def test_enable_avoid_repeated_commands_restore_and_reenable(self):
        controller = policy.Policy()
        with patch.object(policy, "smi", return_value=True) as smi:
            controller.step(True, "active", 1)
            controller.step(True, "active", 3)
            self.assertEqual(smi.call_args_list, [call("-lgc", policy.CORE), call("-lmc", policy.MEMORY)])
            controller.step(False, "battery", 5)
            controller.step(False, "battery", 7)
            self.assertEqual(smi.call_args_list[-2:], [call("-rmc"), call("-rgc")])
            self.assertEqual(smi.call_count, 4)
            controller.step(True, "active", 9)
            self.assertTrue(controller.applied)
            self.assertEqual(smi.call_count, 6)

    def test_partial_lock_failure_resets_both_and_backs_off(self):
        controller = policy.Policy()
        with patch.object(policy, "smi", side_effect=[True, False, True, True, True, True]) as smi:
            controller.step(True, "active", 1)
            self.assertEqual(smi.call_args_list, [call("-lgc", policy.CORE), call("-lmc", policy.MEMORY),
                                                 call("-rmc"), call("-rgc")])
            self.assertIsNone(controller.applied)
            controller.step(True, "active", 3)
            self.assertEqual(smi.call_count, 4)
            controller.step(True, "active", 17)
            self.assertTrue(controller.applied)

    def test_resume_and_periodic_reassert_after_external_reset(self):
        controller = policy.Policy()
        with patch.object(policy, "smi", return_value=True) as smi:
            controller.step(True, "active", 1)
            controller.step(True, "active", 11)
            self.assertEqual(smi.call_count, 4)
            for now in range(13, 73, 2):
                controller.step(True, "active", now)
            self.assertEqual(smi.call_count, 6)

    def test_failed_reset_is_retried_and_both_domains_are_attempted(self):
        controller = policy.Policy()
        with patch.object(policy, "smi", side_effect=[False, True, True, True]) as smi:
            controller.step(False, "battery", 1)
            self.assertTrue(controller.dirty)
            controller.step(False, "battery", 17)
            self.assertFalse(controller.dirty)
            self.assertFalse(controller.applied)
            self.assertEqual(smi.call_args_list, [call("-rmc"), call("-rgc"), call("-rmc"), call("-rgc")])

    def test_external_command_shape_timeout_and_isolated_environment(self):
        with patch.object(policy.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(policy.smi("-lgc", policy.CORE))
            run.assert_called_once_with(["/usr/bin/nvidia-smi", "-i", policy.GPU, "-lgc", "1200,2100"],
                                        capture_output=True, text=True, timeout=5, check=False,
                                        env={"PATH": "/usr/bin", "LC_ALL": "C"})
        with patch.object(policy.subprocess, "run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 5)):
            self.assertFalse(policy.smi("-rmc"))

    def test_service_uses_root_owned_copy_and_resets_after_any_exit(self):
        unit = (ROOT / "personal/nyxuri-nvidia-clock-policy.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 -I /usr/local/libexec/nyxuri-nvidia-clock-policy.py run --user @USER@", unit)
        self.assertIn("ExecStopPost=/usr/bin/python3 -I /usr/local/libexec/nyxuri-nvidia-clock-policy.py reset", unit)
        self.assertIn("ProtectHome=yes", unit)
        self.assertNotIn("PrivateDevices=yes", unit)
        self.assertNotIn("nvidia-clock", (ROOT / "personal/install.py").read_text())
