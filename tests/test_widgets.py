"""Buttons, the countdown ring, the scrolling list and every drawing."""

import tkinter as tk
import tkinter.font as tkfont
import types
import unittest
from unittest import mock

from helpers import GuiCase, needs_tk

from nudge.models import KIND_ORDER
from nudge.sprites import draw_check, draw_sprite, still_time
from nudge.theme import pick_family, pick_mono
from nudge.widgets import FlatButton, Ring, ScrolledFrame, paint_bar


@needs_tk
class FlatButtonTests(GuiCase):
    def make(self, command=None):
        self.new_root()
        return FlatButton(self.root, "Go", command, bg="#111111", fg="#ffffff", hover="#222222", font=("Helvetica", 12))

    def test_click_runs_the_command(self):
        calls = []
        button = self.make(lambda: calls.append(1))
        self.assertTrue(button.bind("<Button-1>"))
        button._on_click(None)
        button._on_click(None)
        self.assertEqual(calls, [1, 1])

    def test_a_button_without_a_command_is_harmless(self):
        self.make(None)._on_click(None)

    def test_hover_changes_colour_and_leaving_restores_it(self):
        button = self.make()
        button._on_enter(None)
        self.assertEqual(button.cget("bg"), "#222222")
        button._on_leave(None)
        self.assertEqual(button.cget("bg"), "#111111")

    def test_text_and_colours_can_change(self):
        button = self.make()
        button.set_text("Stop")
        self.assertEqual(button.cget("text"), "Stop")
        button.set_colors("#333333", "#eeeeee", "#444444")
        self.assertEqual(button.cget("bg"), "#333333")
        button._on_enter(None)
        self.assertEqual(button.cget("bg"), "#444444")
        button._on_leave(None)
        self.assertEqual(button.cget("bg"), "#333333")


@needs_tk
class RingAndBarTests(GuiCase):
    def make_ring(self):
        self.new_root()
        return Ring(self.root, 140, "Helvetica", "Courier")

    def arcs(self, ring):
        return [i for i in ring.find_all() if ring.type(i) == "arc"]

    def test_empty_ring_draws_no_progress_arc(self):
        ring = self.make_ring()
        ring.render(0.0, "#2f80ed", "water", "40:00")
        self.assertEqual(self.arcs(ring), [])

    def test_progress_arc_matches_the_fraction(self):
        ring = self.make_ring()
        ring.render(0.25, "#2f80ed", "water", "30:00")
        arcs = self.arcs(ring)
        self.assertEqual(len(arcs), 1)
        self.assertAlmostEqual(float(ring.itemcget(arcs[0], "extent")), -90.0)

    def test_full_and_overfull_rings_never_close_the_circle_completely(self):
        ring = self.make_ring()
        for fraction in (1.0, 1.7):
            ring.render(fraction, "#2f80ed", "water", "00:00")
            self.assertAlmostEqual(float(ring.itemcget(self.arcs(ring)[0], "extent")), -359.5)

    def test_empty_state_shows_only_text(self):
        ring = self.make_ring()
        ring.render(0, "#e6dfd4", None, "—")
        texts = [ring.itemcget(i, "text") for i in ring.find_all() if ring.type(i) == "text"]
        self.assertEqual(texts, ["—"])

    def test_the_time_is_drawn_for_every_animation(self):
        ring = self.make_ring()
        for kind in KIND_ORDER:
            ring.render(0.5, "#2f80ed", kind, "12:34")
            texts = [ring.itemcget(i, "text") for i in ring.find_all() if ring.type(i) == "text"]
            self.assertEqual(texts, ["12:34"], kind)

    def test_render_replaces_the_previous_drawing(self):
        ring = self.make_ring()
        ring.render(0.5, "#2f80ed", "water", "1")
        first = len(ring.find_all())
        ring.render(0.5, "#2f80ed", "water", "2")
        self.assertEqual(len(ring.find_all()), first)

    def test_progress_bar_width_follows_the_fraction(self):
        self.new_root()
        bar = tk.Canvas(self.root, height=6)
        paint_bar(bar, 0.0, "#2f80ed", 200)
        self.assertEqual(len(bar.find_all()), 1)
        paint_bar(bar, 0.5, "#2f80ed", 200)
        items = bar.find_all()
        self.assertEqual(len(items), 2)
        self.assertEqual(int(bar.coords(items[1])[2]), 100)
        paint_bar(bar, 3.0, "#2f80ed", 200)
        self.assertEqual(int(bar.coords(bar.find_all()[1])[2]), 200)
        paint_bar(bar, -1.0, "#2f80ed", 200)
        self.assertEqual(len(bar.find_all()), 1)
        paint_bar(bar, 0.5, "#2f80ed", 0)


@needs_tk
class ScrolledFrameTests(GuiCase):
    def make(self):
        self.new_root()
        frame = ScrolledFrame(self.root, "#ffffff")
        frame.canvas.yview_scroll = mock.Mock()
        return frame

    def wheel(self, frame, delta):
        frame._wheel(types.SimpleNamespace(delta=delta))

    def test_scrolls_only_when_the_pointer_is_over_the_list(self):
        frame = self.make()
        with mock.patch.object(frame, "_pointer_inside", return_value=False):
            self.wheel(frame, 120)
            frame._wheel_up(None)
            frame._wheel_down(None)
        frame.canvas.yview_scroll.assert_not_called()

    def test_wheel_directions_and_speeds(self):
        frame = self.make()
        with mock.patch.object(frame, "_pointer_inside", return_value=True):
            for delta, units in ((120, -1), (-120, 1), (240, -2), (1, -1), (-1, 1), (5, -1), (-3, 1)):
                frame.canvas.yview_scroll.reset_mock()
                self.wheel(frame, delta)
                frame.canvas.yview_scroll.assert_called_once_with(units, "units")
            frame.canvas.yview_scroll.reset_mock()
            self.wheel(frame, 0)
            frame.canvas.yview_scroll.assert_not_called()
            frame._wheel_up(None)
            frame.canvas.yview_scroll.assert_called_with(-1, "units")
            frame._wheel_down(None)
            frame.canvas.yview_scroll.assert_called_with(1, "units")

    def test_pointer_detection_walks_up_to_the_frame(self):
        frame = self.make()
        with mock.patch.object(frame, "winfo_containing", return_value=frame.inner):
            self.assertTrue(frame._pointer_inside())
        with mock.patch.object(frame, "winfo_containing", return_value=self.root):
            self.assertFalse(frame._pointer_inside())
        with mock.patch.object(frame, "winfo_containing", return_value=None):
            self.assertFalse(frame._pointer_inside())

    def test_inner_content_width_follows_the_canvas_and_scrollregion_follows_content(self):
        frame = self.make()
        frame._on_canvas(types.SimpleNamespace(width=321))
        self.assertEqual(int(frame.canvas.itemcget(frame._window, "width")), 321)
        frame._on_canvas(types.SimpleNamespace(width=321))
        tk.Label(frame.inner, text="x" * 10).pack()
        frame.update_idletasks()
        frame._on_inner(None)
        region = [int(float(v)) for v in frame.canvas.cget("scrollregion").split()]
        self.assertEqual(len(region), 4)
        self.assertGreater(region[3], 0)


@needs_tk
class DrawingTests(GuiCase):
    def canvas(self):
        self.new_root()
        return tk.Canvas(self.root, width=200, height=200)

    def test_every_animation_draws_at_many_moments_and_sizes(self):
        canvas = self.canvas()
        for kind in KIND_ORDER:
            for scale in (0.3, 0.42, 1.0, 1.15, 2.0):
                for moment in (0.0, 0.1, 0.5, 1.7, 3.14, 10.0, 123.456):
                    canvas.delete("all")
                    draw_sprite(canvas, kind, 100, 100, moment, "#2f80ed", scale=scale, tag="sprite")
                    self.assertGreaterEqual(len(canvas.find_withtag("sprite")), 2, (kind, scale, moment))

    def test_an_unknown_animation_still_draws_the_generic_one(self):
        canvas = self.canvas()
        draw_sprite(canvas, "unicorn", 100, 100, 0.5, "#2f80ed")
        self.assertTrue(canvas.find_withtag("sprite"))

    def test_the_figure_actually_moves(self):
        canvas = self.canvas()
        for kind in ("water", "walk", "stretch", "bounce", "rest"):
            frames = []
            for moment in (0.0, 0.4, 0.9):
                canvas.delete("all")
                draw_sprite(canvas, kind, 100, 100, moment, "#2f80ed", scale=1.0, tag="sprite")
                frames.append(tuple(round(c) for i in canvas.find_all() for c in canvas.coords(i)))
            self.assertGreater(len(set(frames)), 1, "%s animation is static" % kind)

    def test_still_poses_exist_for_known_and_unknown_kinds(self):
        for kind in KIND_ORDER:
            self.assertIsInstance(still_time(kind), float)
        self.assertEqual(still_time("unicorn"), 0.4)

    def test_check_mark_grows_in_then_holds(self):
        canvas = self.canvas()
        sizes = []
        for moment in (0.0, 0.1, 0.35, 1.0):
            canvas.delete("all")
            draw_check(canvas, 100, 100, moment, "#2f80ed", scale=1.3)
            coords = canvas.coords(canvas.find_withtag("sprite")[0])
            sizes.append(max(coords[0::2]) - min(coords[0::2]))
        self.assertEqual(sizes, sorted(sizes))
        self.assertAlmostEqual(sizes[-2], sizes[-1])
        self.assertEqual(sizes[0], 0)

    def test_fonts_resolve_to_installed_families(self):
        self.new_root()
        families = set(tkfont.families(self.root))
        self.assertIn(pick_family(self.root), families | {"Helvetica"})
        self.assertIn(pick_mono(self.root), families | {"Courier"})


if __name__ == "__main__":
    unittest.main()
