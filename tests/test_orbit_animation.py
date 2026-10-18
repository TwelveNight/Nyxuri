"""Exercise the actual frame callback without requiring GTK or a display."""

import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests.utils import TempEnv


ORBIT = Path(__file__).resolve().parent.parent / "configs/noctalia/tools/orbit"


class TestOrbitAnimation(unittest.TestCase):
    def setUp(self):
        ctx = TempEnv()
        ctx.__enter__()
        self.addCleanup(ctx.__exit__)
        spec = importlib.util.spec_from_file_location("orbit_physics", ORBIT / "physics.py")
        physics = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(physics)
        self.Spring = physics.Spring
        # Compile the production callback alone so its real control flow runs
        # with a small window fixture, independent of GI availability.
        tree = ast.parse((ORBIT / "window.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "OrbitLauncher")
        callback = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "on_frame_tick")
        namespace = {"math": math, "GLib": SimpleNamespace(SOURCE_REMOVE=False, SOURCE_CONTINUE=True)}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), str(ORBIT / "window.py"), "exec"), namespace)
        self.tick = namespace["on_frame_tick"]

    def make_window(self, angle):
        spring = self.Spring
        return SimpleNamespace(
            last_frame_time=0, cursor_time=0, tick_callback_id=1,
            entry_spring=spring(1), trans_spring=spring(1),
            search_spring=spring(0), engine_switch_spring=spring(1),
            core_spring_x=spring(0, omega=18, zeta=1),
            core_spring_y=spring(0, omega=18, zeta=1),
            node_springs=[spring(0)], apps=[{"center_angle": angle}],
            num_items=1, keyboard_selected=None, hovered_index=0,
            is_dismissing=False, menu_stack=[], queue_draw=lambda: None,
        )

    def test_diagonal_hover_moves_both_axes_on_first_frame(self):
        for angle in (45, 135, 225, 315):
            with self.subTest(angle=angle):
                window = self.make_window(angle)
                self.assertTrue(self.tick(window, None, SimpleNamespace(get_frame_time=lambda: 10000)))
                self.assertNotEqual(window.core_spring_x.current, 0)
                self.assertNotEqual(window.core_spring_y.current, 0)
                self.assertAlmostEqual(abs(window.core_spring_x.current), abs(window.core_spring_y.current))

    def test_hover_settles_and_stops_redrawing(self):
        for hz in (60, 144, 165):
            with self.subTest(hz=hz):
                window = self.make_window(45)
                for frame in range(1, hz * 3):
                    clock = SimpleNamespace(get_frame_time=lambda: round(frame * 1000000 / hz))
                    moving = self.tick(window, None, clock)
                    self.assertAlmostEqual(window.core_spring_x.current, window.core_spring_y.current)
                    if not moving:
                        break
                self.assertFalse(moving)
                self.assertIsNone(window.tick_callback_id)
                self.assertAlmostEqual(window.core_spring_x.current, 10 / math.sqrt(2))
