"""Meeting snooze, pause, restarts while frozen, and waking from sleep."""

import unittest

from helpers import GuiCase, needs_tk

from nudge.logic import WAKE_GAP_SECONDS, is_suppressed
from nudge.models import MEETING_MINUTES


@needs_tk
class MeetingTests(GuiCase):
    def test_every_snooze_length_freezes_until_the_right_time(self):
        for minutes in MEETING_MINUTES:
            with self.subTest(minutes=minutes):
                self.reset()
                app = self.launch()
                start = self.clock()
                app._meeting_from_main(minutes)
                self.assertAlmostEqual(app.state.snooze_until, start + minutes * 60)
                self.assertTrue(is_suppressed(app.state, start))
                self.assertAlmostEqual(self.saved().snooze_until, start + minutes * 60)
                self.assertEqual(app.meeting_active.winfo_manager(), "pack")
                self.assertEqual(app.meeting_idle.winfo_manager(), "")
                self.assertIn("Snoozed until", app.meeting_until.cget("text"))
                self.assertIn("In a meeting until", app.status.cget("text"))

    def test_meeting_buttons_offer_the_documented_lengths(self):
        app = self.launch()
        labels = [w.cget("text") for w in app.meeting_idle.winfo_children()[-1].winfo_children()]
        self.assertEqual(labels, ["15 min", "30 min", "1 hour", "2 hours"])

    def test_nothing_rings_during_a_meeting(self):
        app = self.launch()
        start = self.clock()
        app._meeting_from_main(60)
        self.tick_at(start + 59 * 60)
        self.assertIsNone(app.overlay)
        self.assertEqual(self.played, [])
        self.assertEqual(app.queue, [])

    def test_countdowns_stand_still_during_a_meeting(self):
        app = self.launch()
        self.clock.advance(10 * 60)
        water = self.reminder("Drink water")
        card = app.cards[water.id]
        app.tick()
        self.assertEqual(card.countdown.cget("text"), "Next in 30:00")
        start = self.clock()
        app._meeting_from_main(60)
        self.tick_at(start + 20 * 60)
        self.assertEqual(card.countdown.cget("text"), "Next in 30:00")
        self.assertEqual(app.next_name.cget("text"), "Drink water")

    def test_time_that_was_left_is_still_left_after_the_meeting(self):
        app = self.launch()
        self.clock.advance(10 * 60)
        water = self.reminder("Drink water")
        start = self.clock()
        app._meeting_from_main(30)
        end = start + 30 * 60
        self.tick_at(end + 1)
        self.assertFalse(is_suppressed(app.state, self.clock()))
        self.assertIsNone(app.state.snooze_until)
        self.assertIsNone(app.state.hold_started_at)
        self.assertAlmostEqual(water.next_due, end + 30 * 60)
        self.assertIsNone(app.overlay)
        self.assertEqual(app.meeting_idle.winfo_manager(), "pack")
        self.tick_at(water.next_due + 1)
        self.assertEqual(app.overlay.reminder_id, water.id)

    def test_resume_now_ends_the_meeting_early_and_keeps_the_time_left(self):
        app = self.launch()
        start = self.clock()
        app._meeting_from_main(120)
        self.tick_at(start + 5 * 60)
        water = self.reminder("Drink water")
        app._resume_now()
        self.assertFalse(is_suppressed(app.state, self.clock()))
        self.assertAlmostEqual(water.next_due - self.clock(), 40 * 60)
        self.assertIsNone(self.saved().snooze_until)
        self.assertEqual(app.meeting_idle.winfo_manager(), "pack")

    def test_a_second_meeting_extends_the_first_without_losing_time(self):
        app = self.launch()
        water = self.reminder("Drink water")
        start = self.clock()
        app._meeting_from_main(15)
        self.tick_at(start + 5 * 60)
        app._meeting_from_main(30)
        end = start + 5 * 60 + 30 * 60
        self.assertAlmostEqual(app.state.snooze_until, end)
        self.tick_at(end + 1)
        self.assertAlmostEqual(water.next_due, end + 40 * 60)

    def test_meeting_from_the_window_closes_an_alarm_and_clears_the_queue(self):
        app = self.launch()
        self.tick_at(self.clock() + 3 * 3600)
        self.assertIsNotNone(app.overlay)
        self.assertTrue(app.queue)
        app._meeting_from_main(30)
        self.assertIsNone(app.overlay)
        self.assertEqual(app.queue, [])

    def test_a_meeting_still_running_when_the_app_reopens_stays_frozen(self):
        app = self.launch()
        start = self.clock()
        water = self.reminder("Drink water")
        due = water.next_due
        app._meeting_from_main(60)
        self.clock.advance(10 * 60)
        app = self.relaunch()
        water = self.reminder("Drink water")
        self.assertEqual(water.next_due, due)
        self.assertAlmostEqual(app.state.snooze_until, start + 3600)
        self.assertEqual(app.meeting_active.winfo_manager(), "pack")
        self.tick_at(start + 50 * 60)
        self.assertIsNone(app.overlay)
        self.tick_at(start + 3600 + 1)
        self.assertFalse(is_suppressed(app.state, self.clock()))
        self.assertAlmostEqual(self.reminder("Drink water").next_due, due + 3600)

    def test_a_meeting_that_ended_while_closed_only_counts_time_after_it(self):
        app = self.launch()
        start = self.clock()
        app._meeting_from_main(30)
        self.clock.advance(45 * 60)
        app = self.relaunch()
        water = self.reminder("Drink water")
        self.assertFalse(is_suppressed(app.state, self.clock()))
        self.assertAlmostEqual(water.next_due, start + 30 * 60 + 40 * 60)
        self.assertEqual(app.cards[water.id].countdown.cget("text"), "Next in 25:00")


@needs_tk
class PauseTests(GuiCase):
    def test_pause_and_resume_buttons(self):
        app = self.launch()
        self.assertEqual(app.pause_button.cget("text"), "Pause")
        app._toggle_pause()
        self.assertFalse(app.state.running)
        self.assertEqual(app.pause_button.cget("text"), "Resume")
        self.assertIn("Paused", app.status.cget("text"))
        self.assertFalse(self.saved().running)
        app._toggle_pause()
        self.assertTrue(app.state.running)
        self.assertEqual(app.pause_button.cget("text"), "Pause")

    def test_nothing_rings_while_paused_and_time_left_is_kept(self):
        app = self.launch()
        water = self.reminder("Drink water")
        start = self.clock()
        self.tick_at(start + 5 * 60)
        pause_time = self.clock()
        remaining = water.next_due - pause_time
        app._toggle_pause()
        card = app.cards[water.id]
        shown = card.countdown.cget("text")
        self.tick_at(pause_time + 5 * 3600)
        self.assertIsNone(app.overlay)
        self.assertEqual(self.played, [])
        self.assertEqual(card.countdown.cget("text"), shown)
        resumed = self.clock()
        app._toggle_pause()
        self.assertAlmostEqual(water.next_due - resumed, remaining)
        self.assertIsNone(app.overlay)

    def test_pausing_closes_an_alarm_and_clears_the_queue(self):
        app = self.launch()
        self.tick_at(self.clock() + 3 * 3600)
        self.assertIsNotNone(app.overlay)
        app._toggle_pause()
        self.assertIsNone(app.overlay)
        self.assertEqual(app.queue, [])
        app.tick()
        self.assertIsNone(app.overlay)

    def test_pausing_cancels_a_meeting_and_resume_picks_up_where_it_was(self):
        app = self.launch()
        water = self.reminder("Drink water")
        start = self.clock()
        app._meeting_from_main(30)
        self.tick_at(start + 10 * 60)
        app._toggle_pause()
        self.assertIsNone(app.state.snooze_until)
        self.assertEqual(app.meeting_idle.winfo_manager(), "pack")
        self.tick_at(start + 20 * 60)
        app._toggle_pause()
        self.assertAlmostEqual(water.next_due - self.clock(), 40 * 60)

    def test_a_meeting_can_start_while_paused(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._toggle_pause()
        app._meeting_from_main(15)
        self.assertTrue(app.state.running)
        self.assertEqual(app.pause_button.cget("text"), "Pause")
        self.assertTrue(is_suppressed(app.state, self.clock()))
        self.assertEqual(water.next_due - app.state.hold_started_at, 40 * 60)

    def test_paused_stays_paused_after_reopening(self):
        app = self.launch()
        water = self.reminder("Drink water")
        due = water.next_due
        app._toggle_pause()
        self.clock.advance(8 * 3600)
        app = self.relaunch()
        self.assertFalse(app.state.running)
        self.assertEqual(self.reminder("Drink water").next_due, due)
        self.assertEqual(app.pause_button.cget("text"), "Resume")
        app.tick()
        self.assertIsNone(app.overlay)


@needs_tk
class SleepAndWakeTests(GuiCase):
    def test_waking_up_spaces_out_the_missed_alarms(self):
        app = self.launch()
        woke = self.clock() + 8 * 3600
        self.wake_at(woke)
        self.assertIsNone(app.overlay, "nothing fires at the instant of waking")
        due = {r.name: round(r.next_due - woke) for r in app.state.reminders}
        self.assertEqual(
            due,
            {"Drink water": 2, "Stretch": 47, "Walk a bit": 92, "Take a small rest": 137},
        )
        order = []
        for offset in (3, 48, 93, 138):
            self.tick_at(woke + offset)
            self.assertIsNotNone(app.overlay)
            order.append(app.overlay.reminder.name)
            app.overlay.dismiss_quietly()
        self.assertEqual(order, ["Drink water", "Stretch", "Walk a bit", "Take a small rest"])
        self.assertEqual(self.played, ["water", "stretch", "walk", "rest"])

    def test_a_short_gap_is_not_mistaken_for_sleep(self):
        app = self.launch()
        water = self.reminder("Drink water")
        water.next_due = self.clock() + 10
        self.wake_at(self.clock() + WAKE_GAP_SECONDS - 5)
        self.assertIsNotNone(app.overlay)
        self.assertEqual(app.overlay.reminder_id, water.id)

    def test_a_long_gap_with_nothing_missed_changes_nothing(self):
        app = self.launch()
        before = {r.id: r.next_due for r in app.state.reminders}
        self.wake_at(self.clock() + WAKE_GAP_SECONDS + 10)
        self.assertEqual({r.id: r.next_due for r in app.state.reminders}, before)

    def test_sleeping_through_a_meeting_does_not_disturb_the_frozen_times(self):
        app = self.launch()
        water = self.reminder("Drink water")
        due = water.next_due
        start = self.clock()
        app._meeting_from_main(120)
        self.wake_at(start + 60 * 60)
        self.assertEqual(water.next_due, due)
        self.assertIsNone(app.overlay)

    def test_every_tick_remembers_when_it_last_ran(self):
        app = self.launch()
        self.clock.advance(5)
        app.tick()
        self.assertEqual(app._last_tick, self.clock())


if __name__ == "__main__":
    unittest.main()
