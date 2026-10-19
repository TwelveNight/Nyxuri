#!/usr/bin/env python3
"""Local RTX 3060 clock floors for AC-powered Nyxuri, iNiR and Hyprland."""
import argparse
import os
from pathlib import Path
import pwd
import signal
import subprocess
import threading
import time

PCI = "0000:01:00.0"
GPU = "00000000:01:00.0"
CORE = "1200,2100"
MEMORY = "6001,7001"
POLL_SECONDS = 2
RETRY_SECONDS = 15
REASSERT_SECONDS = 60


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


class Conditions:
    def __init__(self, uid, config, sys_root=Path("/sys"), proc_root=Path("/proc")):
        self.uid = uid
        self.config = str(config)
        config_root = next((parent for parent in Path(config).parents if parent.name == ".config"), Path(config).parent.parent)
        self.configs = {
            "niri": {self.config, str(config_root / "niri/config.kdl")},
            "Hyprland": {str(config_root / "hypr/hyprland.lua"),
                         str(config_root / "hypr/hyprland.conf")},
        }
        self.sys = sys_root
        self.proc = proc_root
        self.pid = None

    def on_ac(self):
        return any(read(p / "type") == "Mains" and read(p / "online") == "1"
                   for p in (self.sys / "class/power_supply").glob("*"))

    def display_on(self):
        # The internal panel belongs to AMD while Niri can render on NVIDIA.
        # Scan both GPUs; require at least one enabled, awake connector.
        for output in (self.sys / "class/drm").glob("card[0-9]*-*"):
            if (read(output / "status") == "connected"
                    and read(output / "enabled") == "enabled"
                    and read(output / "dpms") == "On"):
                return True
        return False

    def matches_session(self, p):
        try:
            compositor = read(p / "comm")
            if p.stat().st_uid != self.uid or compositor not in self.configs:
                return False
            args = (p / "cmdline").read_bytes().split(b"\0")
            args = [os.fsdecode(arg) for arg in args if arg]
            if not args or Path(args[0]).name != compositor:
                return False
            # iNiR's real user unit starts `niri --session` with default config.
            # Requiring --session excludes transient niri msg/validate clients.
            if compositor == "niri" and "--session" not in args:
                return False
            if any(arg in args for arg in ("--help", "-h", "--version", "--verify-config")):
                return False
            configs = []
            for index, arg in enumerate(args[1:], 1):
                if arg in ("--config", "-c"):
                    value = args[index + 1]
                    if value.startswith("-"):
                        return False
                    configs.append(value)
                elif arg.startswith("--config="):
                    configs.append(arg.split("=", 1)[1])
            # Default launches are the locally verified iNiR / Hyprland entries;
            # explicit paths must stay inside one of these three desktop roots.
            return not configs or (len(configs) == 1 and configs[0] in self.configs[compositor])
        except (OSError, IndexError):
            return False

    def session_active(self):
        if self.pid is not None and self.matches_session(self.proc / self.pid):
            return True
        self.pid = None
        for p in self.proc.glob("[0-9]*"):
            if self.matches_session(p):
                self.pid = p.name
                return True
        return False

    def wanted(self):
        if not self.on_ac():
            return False, "battery or AC unavailable"
        if not self.display_on():
            return False, "all displays disabled, disconnected or asleep"
        if not self.session_active():
            return False, "Nyxuri, iNiR or Hyprland session absent"
        return True, "AC + awake display + supported desktop session"


def smi(option, value=None):
    args = ["/usr/bin/nvidia-smi", "-i", GPU, option]
    if value is not None:
        args.append(value)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5,
                                check=False, env={"PATH": "/usr/bin", "LC_ALL": "C"})
        if result.returncode:
            print(f"{option} failed: {(result.stderr or result.stdout).strip()}", flush=True)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{option} failed: {error}", flush=True)
        return False


def reset():
    # Always attempt both resets, including after partial startup or driver loss.
    memory_ok = smi("-rmc")
    core_ok = smi("-rgc")
    return memory_ok and core_ok


class Policy:
    def __init__(self):
        self.applied = None
        self.dirty = False
        self.last_apply = 0
        self.last_check = None
        self.retry_at = 0

    def step(self, wanted, reason, now):
        resumed = self.last_check is not None and now - self.last_check > POLL_SECONDS * 3
        self.last_check = now
        if now < self.retry_at:
            return
        if wanted:
            if self.applied is True and not resumed and now - self.last_apply < REASSERT_SECONDS:
                return
            self.dirty = True
            if smi("-lgc", CORE) and smi("-lmc", MEMORY):
                if self.applied is not True:
                    print(f"Clock floors enabled: core {CORE}, memory {MEMORY}; {reason}", flush=True)
                self.applied = True
                self.last_apply = now
                return
            self.dirty = not reset()
            self.applied = None
        elif self.applied is not False or self.dirty:
            if reset():
                self.dirty = False
                self.applied = False
                print(f"Automatic clocks restored: {reason}", flush=True)
                return
            self.dirty = True
        else:
            return
        self.retry_at = now + RETRY_SECONDS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "reset"))
    parser.add_argument("--user")
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error("The installed system service must run as root to set NVIDIA clocks.")
    if args.action == "reset":
        return 0 if reset() else 1
    if not args.user:
        parser.error("run requires --user")
    account = pwd.getpwnam(args.user)
    if account.pw_uid == 0:
        parser.error("--user must be a desktop user")
    conditions = Conditions(account.pw_uid, Path(account.pw_dir) / ".config/niri/config.kdl")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    policy = Policy()
    try:
        while not stop.is_set():
            wanted, reason = conditions.wanted()
            # BOOTTIME includes suspend, so resume promptly reasserts the floors.
            policy.step(wanted, reason, time.clock_gettime(time.CLOCK_BOOTTIME))
            stop.wait(POLL_SECONDS)
    finally:
        reset()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
