"""The alarm: firing, the walk across the screen, the prompt, snooze, and the timer."""

import time
import tkinter as tk
import unittest
from unittest import mock

from helpers import GuiCase, needs_tk

from nudge.logic import TRAVEL_SECONDS, travel_position
from nudge.models import DEFAULT_SNOOZE, KIND_ORDER, MEETING_FROM_ALARM, PROMPT_TIMEOUT, Reminder
from nudge.overlay import AlarmOverlay


@needs_tk
class FiringTests(GuiCase):
    def test_a_due_reminder_rings_once_and_is_rescheduled(self):
        app = self.launch()
        water = self.reminder("Drink water")
        self.assertIsNone(app.overlay)
        self.tick_at(water.next_due - 1)
        self.assertIsNone(app.overlay, "one second early: nothing yet")
        self.tick_at(water.next_due)
        self.assertIsNotNone(app.overlay)
        self.assertEqual(app.overlay.phase, "travel")
        self.assertFalse(app.overlay.preview)
        self.assertEqual(app.overlay.reminder_id, water.id)
        self.assertEqual(self.played, ["water"])
        self.assertAlmostEqual(water.next_due, self.clock() + 40 * 60)
        app.tick()
        app.tick()
        self.assertEqual(self.played, ["water"], "ticking again must not ring again")

    def test_alarms_use_the_sound_of_their_own_animation(self):
        app = self.launch()
        for name, kind in (
            ("Drink water", "water"),
            ("Take a small rest", "rest"),
            ("Walk a bit", "walk"),
            ("Stretch", "stretch"),
        ):
            with self.subTest(name=name):
                target = self.reminder(name)
                for item in app.state.reminders:
                    item.enabled = item is target
                self.played.clear()
                self.fire(target)
                self.assertEqual(self.played, [kind])
                app.overlay.dismiss_quietly()
                self.assertIsNone(app.overlay)

    def test_muted_means_no_sound_but_still_an_alarm(self):
        app = self.launch()
        app._toggle_sound()
        self.assertFalse(app.state.sound_enabled)
        self.assertEqual(app.sound_button.cget("text"), "Muted")
        self.assertFalse(self.saved().sound_enabled)
        self.fire(self.reminder("Drink water"))
        self.assertIsNotNone(app.overlay)
        self.assertEqual(self.played, [])
        app.overlay.dismiss_quietly()
        app._toggle_sound()
        self.assertEqual(app.sound_button.cget("text"), "Sound on")

    def test_a_failing_sound_player_does_not_stop_the_alarm(self):
        app = self.launch()
        app.player = mock.Mock(side_effect=RuntimeError("no audio device"))
        with mock.patch("traceback.print_exc") as report:
            self.fire(self.reminder("Drink water"))
        self.assertIsNotNone(app.overlay)
        self.assertEqual(app.player.call_count, 1)
        self.assertTrue(report.called, "the problem is reported, not swallowed silently")

    def test_a_window_that_cannot_open_does_not_crash_the_app(self):
        app = self.launch()
        with mock.patch("nudge.app.AlarmOverlay", side_effect=RuntimeError("boom")), \
                mock.patch("traceback.print_exc") as report:
            self.fire(self.reminder("Drink water"))
        self.assertIsNone(app.overlay)
        self.assertTrue(report.called)
        app.tick()

    def test_reminders_due_together_ring_one_after_another_in_list_order(self):
        app = self.launch()
        self.tick_at(self.clock() + 3 * 3600)
        order = []
        while app.overlay is not None:
            order.append(app.overlay.reminder.name)
            self.assertEqual(len([w for w in self.root.winfo_children() if w.winfo_class() == "Toplevel"]), 1)
            app.overlay.dismiss_quietly()
        self.assertEqual(order, ["Drink water", "Take a small rest", "Walk a bit", "Stretch"])
        self.assertEqual(self.played, ["water", "rest", "walk", "stretch"])
        for item in app.state.reminders:
            self.assertGreater(item.next_due, self.clock())

    def test_a_reminder_switched_off_while_waiting_is_skipped(self):
        app = self.launch()
        self.tick_at(self.clock() + 3 * 3600)
        first = app.overlay.reminder.name
        self.assertEqual(first, "Drink water")
        app._toggle(self.reminder("Take a small rest"))
        app.overlay.dismiss_quietly()
        self.assertEqual(app.overlay.reminder.name, "Walk a bit")

    def test_an_alarm_on_screen_blocks_a_second_window_but_not_the_clock(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        first = app.overlay
        self.tick_at(self.clock() + 10)
        self.assertIs(app.overlay, first)


@needs_tk
class WalkAcrossTheScreenTests(GuiCase):
    def test_the_window_is_borderless_and_on_top(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        window = app.overlay.window
        self.assertTrue(window.overrideredirect())
        self.assertEqual(int(window.attributes("-topmost")), 1)

    def test_it_enters_from_the_right_edge_and_settles_in_the_middle(self):
        app = self.launch()
        self.fire(self.only("Stretch"))
        overlay = app.overlay
        self.assertEqual(overlay.reminder.name, "Stretch")
        screen_w = overlay.window.winfo_screenwidth()
        screen_h = overlay.window.winfo_screenheight()
        xs = []
        for moment in (0.0, 1.0, 2.0, 3.0, 4.0, 4.9):
            overlay.elapsed = moment
            overlay._advance()
            geometry = overlay.window.winfo_geometry()
            xs.append(int(geometry.split("+")[1]))
        self.assertGreater(xs[0], screen_w, "starts just off the right edge")
        self.assertEqual(xs, sorted(xs, reverse=True), "moves steadily leftward")
        overlay.elapsed = TRAVEL_SECONDS + 1
        overlay._advance()
        self.assertEqual(overlay.phase, "prompt")
        width, _, rest = overlay.window.winfo_geometry().partition("x")
        left = int(rest.split("+")[1])
        self.assertAlmostEqual(left, (screen_w - int(width)) / 2.0, delta=2)
        top = int(rest.split("+")[2])
        self.assertGreaterEqual(top, 16)
        self.assertLess(top, screen_h)

    def test_the_whole_prompt_fits_on_screen(self):
        self.launch()
        self.fire(self.only("Walk a bit"))
        overlay = self.to_prompt()
        overlay.window.update_idletasks()
        size = overlay.window.winfo_geometry().split("+")[0]
        width, height = [int(part) for part in size.split("x")]
        self.assertGreater(height, 300)
        self.assertLess(height, overlay.window.winfo_screenheight() - 32)
        self.assertLessEqual(overlay.window.winfo_reqheight(), height)
        self.assertLessEqual(overlay.controls.winfo_reqwidth(), width)

    def test_path_is_a_smooth_arc(self):
        points = [travel_position(t / 10.0, 1728, 1117, 270, 184) for t in range(0, 51)]
        ys = [p[1] for p in points]
        self.assertEqual(points[0][2], False)
        self.assertEqual(points[-1][2], True)
        self.assertGreater(max(ys), ys[0])
        for left, right in zip(points, points[1:]):
            self.assertLessEqual(abs(right[1] - left[1]), 30)

    def test_clicking_the_walking_figure_skips_to_the_prompt(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        app.overlay._on_canvas_click(None)
        self.assertEqual(app.overlay.phase, "prompt")

    def test_every_animation_runs_through_every_phase(self):
        app = self.launch()
        for kind in KIND_ORDER:
            with self.subTest(kind=kind):
                reminder = Reminder.create("Test " + kind, kind, 30, 1, "#2f80ed", self.clock())
                app.state.reminders.append(reminder)
                app.preview(reminder)
                overlay = app.overlay
                for step in range(0, 30):
                    overlay.elapsed = step * 0.2
                    overlay._advance()
                    overlay._redraw()
                    if overlay.phase != "travel":
                        break
                self.assertEqual(overlay.phase, "prompt")
                overlay._redraw()
                overlay._begin()
                overlay._redraw()
                overlay._enter_done()
                overlay._redraw()
                self.assertTrue(overlay.canvas.find_withtag("sprite"), "the done mark is drawn")
                overlay.dismiss_quietly()
                self.assertIsNone(app.overlay)


@needs_tk
class PromptAndTimerTests(GuiCase):
    def test_start_runs_the_timer_and_it_counts_down(self):
        self.launch()
        self.fire(self.only("Stretch"))
        overlay = self.to_prompt()
        overlay._begin()
        self.assertEqual(overlay.phase, "active")
        self.assertEqual(overlay.time_label.cget("text"), "02:00")
        self.assertAlmostEqual(overlay.deadline - time.time(), 2 * 60, delta=2)
        overlay.deadline = time.time() + 61.2
        overlay._advance()
        self.assertEqual(overlay.time_label.cget("text"), "01:01")

    def test_timer_ends_by_itself_and_the_window_goes_away(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        overlay = self.to_prompt()
        overlay._begin()
        overlay.deadline = time.time() - 1
        overlay._advance()
        self.assertEqual(overlay.phase, "done")
        overlay.done_mark = overlay.elapsed - 0.5
        overlay._advance()
        self.assertIs(app.overlay, overlay, "stays up briefly so you see it finished")
        overlay.done_mark = overlay.elapsed - 2
        overlay._advance()
        self.assertIsNone(app.overlay)

    def test_done_button_finishes_early(self):
        self.launch()
        self.fire(self.reminder("Drink water"))
        overlay = self.to_prompt()
        overlay._begin()
        overlay._enter_done()
        self.assertEqual(overlay.phase, "done")
        overlay._enter_done()
        self.assertEqual(overlay.phase, "done")

    def test_starting_does_not_change_when_the_next_alarm_is_due(self):
        self.launch()
        water = self.reminder("Drink water")
        self.fire(water)
        due = water.next_due
        overlay = self.to_prompt()
        overlay._begin()
        overlay._enter_done()
        overlay.dismiss_quietly()
        self.assertEqual(water.next_due, due)

    def test_snooze_choices_delay_only_that_reminder(self):
        for minutes in (5, 10, 15):
            with self.subTest(minutes=minutes):
                self.reset()
                app = self.launch()
                water = self.reminder("Drink water")
                walk = self.reminder("Walk a bit")
                walk_due = walk.next_due
                self.fire(water)
                self.to_prompt()._snooze(minutes)
                self.assertIsNone(app.overlay)
                snoozed_at = self.clock()
                self.assertAlmostEqual(water.next_due, snoozed_at + minutes * 60)
                self.assertEqual(walk.next_due, walk_due)
                self.only("Drink water")  # so Stretch does not ring during the wait
                self.assertAlmostEqual(self.saved().reminders[0].next_due, snoozed_at + minutes * 60)
                self.tick_at(snoozed_at + minutes * 60 - 1)
                self.assertIsNone(app.overlay)
                self.tick_at(snoozed_at + minutes * 60 + 1)
                self.assertIsNotNone(app.overlay, "rings again once the snooze is over")
                self.assertEqual(app.overlay.reminder_id, water.id)

    def test_ignoring_the_prompt_snoozes_it(self):
        app = self.launch()
        water = self.reminder("Drink water")
        self.fire(water)
        overlay = self.to_prompt()
        overlay.prompt_started = time.time() - PROMPT_TIMEOUT + 5
        overlay._advance()
        self.assertIs(app.overlay, overlay)
        overlay.prompt_started = time.time() - PROMPT_TIMEOUT - 1
        overlay._advance()
        self.assertIsNone(app.overlay)
        self.assertAlmostEqual(water.next_due, self.clock() + DEFAULT_SNOOZE * 60)

    def test_keyboard_shortcuts(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        overlay = app.overlay
        self.assertTrue(overlay.window.bind("<Escape>"))
        self.assertTrue(overlay.window.bind("<Return>"))
        overlay._on_return(None)
        self.assertEqual(overlay.phase, "prompt")
        overlay._on_return(None)
        self.assertEqual(overlay.phase, "active")
        overlay._on_escape(None)
        self.assertEqual(overlay.phase, "done")
        overlay._on_escape(None)
        self.assertIsNone(app.overlay)

    def test_escape_on_the_prompt_snoozes_ten_minutes(self):
        app = self.launch()
        water = self.reminder("Drink water")
        self.fire(water)
        self.to_prompt()._on_escape(None)
        self.assertIsNone(app.overlay)
        self.assertAlmostEqual(water.next_due, self.clock() + 10 * 60)

    def test_escape_while_walking_also_snoozes(self):
        app = self.launch()
        water = self.reminder("Drink water")
        self.fire(water)
        app.overlay._on_escape(None)
        self.assertIsNone(app.overlay)
        self.assertAlmostEqual(water.next_due, self.clock() + 10 * 60)

    def test_in_a_meeting_from_the_alarm_snoozes_everything(self):
        app = self.launch()
        self.tick_at(self.clock() + 3 * 3600)
        self.assertGreaterEqual(len(app.queue), 1)
        start = self.clock()
        self.to_prompt()._meeting()
        self.assertIsNone(app.overlay, "no further alarms from the queue")
        self.assertEqual(app.queue, [])
        self.assertAlmostEqual(app.state.snooze_until, start + MEETING_FROM_ALARM * 60)
        self.assertIsNotNone(app.state.hold_started_at)
        self.assertAlmostEqual(self.saved().snooze_until, start + MEETING_FROM_ALARM * 60)
        self.tick_at(start + 10 * 60)
        self.assertIsNone(app.overlay)

    def test_closing_the_app_closes_the_alarm_and_saves(self):
        app = self.launch()
        self.fire(self.reminder("Drink water"))
        window = app.overlay.window
        app.close()
        self.assertIsNone(app.overlay)
        self.assertFalse(app._alive)
        with self.assertRaises(tk.TclError):
            window.winfo_exists()
        self.assertTrue(self.path.exists())


@needs_tk
class PreviewTests(GuiCase):
    def test_preview_plays_the_animation_without_touching_the_schedule(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        due = stretch.next_due
        app.preview(stretch)
        self.assertTrue(app.overlay.preview)
        self.assertEqual(self.played, ["stretch"])
        self.to_prompt()._snooze(15)
        self.assertEqual(stretch.next_due, due)
        self.assertIsNone(app.overlay)

    def test_preview_while_another_is_showing_is_declined(self):
        app = self.launch()
        app.preview(self.reminder("Stretch"))
        first = app.overlay
        app.preview(self.reminder("Walk a bit"))
        self.assertIs(app.overlay, first)
        self.assertIn("already", app.note)

    def test_preview_of_a_switched_off_reminder_still_plays(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        app._toggle(stretch)
        app.preview(stretch)
        self.assertIsNotNone(app.overlay)

    def test_preview_is_silent_when_muted(self):
        app = self.launch()
        app._toggle_sound()
        app.preview(self.reminder("Walk a bit"))
        self.assertEqual(self.played, [])

    def test_a_real_alarm_waits_for_a_preview_to_finish(self):
        app = self.launch()
        app.preview(self.reminder("Stretch"))
        self.fire(self.reminder("Drink water"))
        self.assertTrue(app.overlay.preview)
        app.overlay.dismiss_quietly()
        self.assertFalse(app.overlay.preview)
        self.assertEqual(app.overlay.reminder.name, "Drink water")


@needs_tk
class OverlayUnitTests(GuiCase):
    def test_overlay_can_be_closed_twice_safely(self):
        self.launch()
        closed = []
        reminder = self.reminder("Drink water")
        overlay = AlarmOverlay(
            self.root, reminder, "Helvetica", "Courier", lambda kind, sound="auto": None,
            on_snooze=lambda minutes: closed.append(("snooze", minutes)),
            on_meeting=lambda minutes: closed.append(("meeting", minutes)),
            on_closed=lambda: closed.append("closed"),
        )
        overlay._snooze(5)
        overlay._snooze(5)
        overlay._meeting()
        overlay.dismiss_quietly()
        self.assertEqual(closed, [("snooze", 5), "closed"])

    def test_errors_in_callbacks_do_not_leave_the_window_open(self):
        self.launch()
        reminder = self.reminder("Drink water")

        def explode(_minutes):
            raise RuntimeError("callback failed")

        overlay = AlarmOverlay(
            self.root, reminder, "Helvetica", "Courier", lambda kind, sound="auto": None,
            on_snooze=explode, on_meeting=explode, on_closed=lambda: None,
        )
        with mock.patch("traceback.print_exc"):
            overlay._snooze(5)
        self.assertFalse(overlay.alive)

    def test_title_reads_naturally_for_custom_names(self):
        self.launch()
        reminder = Reminder.create("Look away from the screen", "bounce", 20, 1, "#d6456a", self.clock())
        overlay = AlarmOverlay(
            self.root, reminder, "Helvetica", "Courier", lambda kind, sound="auto": None,
            on_snooze=lambda m: None, on_meeting=lambda m: None, on_closed=lambda: None,
        )
        overlay.elapsed = 6
        overlay._advance()
        texts = [w.cget("text") for w in overlay.controls.winfo_children() if w.winfo_class() == "Label"]
        self.assertIn("Time to look away from the screen", texts)
        overlay.dismiss_quietly()


@needs_tk
class AlarmSoundTests(GuiCase):
    def test_an_alarm_plays_the_sound_chosen_for_its_reminder(self):
        def choose(state):
            state.reminders[0].sound = "none"
            state.reminders[3].sound = "Hero"

        app = self.launch(mutate=choose)
        self.fire(self.only("Drink water"))
        self.assertEqual((self.played, self.played_sounds), (["water"], ["none"]))
        app.overlay.dismiss_quietly()
        self.played.clear()
        self.played_sounds.clear()
        self.fire(self.only("Stretch"))
        self.assertEqual((self.played, self.played_sounds), (["stretch"], ["Hero"]))

    def test_a_reminder_left_on_auto_asks_for_its_animation_sound(self):
        self.launch()
        self.fire(self.only("Walk a bit"))
        self.assertEqual((self.played, self.played_sounds), (["walk"], ["auto"]))

    def test_the_card_preview_uses_the_reminders_sound_too(self):
        app = self.launch(mutate=lambda state: setattr(state.reminders[3], "sound", "Hero"))
        app.preview(self.reminder("Stretch"))
        self.assertEqual(self.played_sounds, ["Hero"])

    def test_the_global_mute_still_silences_every_chosen_sound(self):
        app = self.launch(mutate=lambda state: setattr(state.reminders[0], "sound", "Hero"))
        app._toggle_sound()
        self.fire(self.only("Drink water"))
        self.assertEqual((self.played, self.played_sounds), ([], []))


if __name__ == "__main__":
    unittest.main()
