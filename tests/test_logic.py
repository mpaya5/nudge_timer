"""Timing, storage, and the single-instance lock. No window required."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from nudge.logic import (
    alarm_title,
    bump_minutes,
    clock_basis,
    elapsed_fraction,
    end_meeting,
    format_clock,
    format_remaining,
    format_span,
    is_suppressed,
    meeting_is_active,
    pause,
    reconcile_hold_on_startup,
    resume,
    retarget_frequency,
    soften_startup_overdue,
    soonest,
    start_meeting,
    take_due,
    tick_expired_snooze,
    travel_position,
)
from nudge.models import AppState, Reminder, default_state
from nudge.storage import ProcessLock, load_state, save_state


def reminder(name, due, frequency=40, enabled=True):
    item = Reminder.create(name, "water", frequency, 1, "#2f80ed", 0)
    item.next_due = due
    item.enabled = enabled
    return item


def make_state(items, running=True, snooze=None, hold=None):
    return AppState(list(items), snooze, hold, True, running, False)


class FormatTests(unittest.TestCase):
    def test_remaining_clock(self):
        self.assertEqual(format_remaining(0), "00:00")
        self.assertEqual(format_remaining(59), "00:59")
        self.assertEqual(format_remaining(60), "01:00")
        self.assertEqual(format_remaining(3599), "59:59")
        self.assertEqual(format_remaining(3600), "1:00:00")
        self.assertEqual(format_remaining(-4), "00:00")

    def test_clock_uses_local_time(self):
        moment = 1_700_000_000
        self.assertEqual(format_clock(moment), time.strftime("%H:%M", time.localtime(moment)))

    def test_span_and_title(self):
        self.assertEqual(format_span(15), "15 min")
        self.assertEqual(format_span(60), "1 hour")
        self.assertEqual(format_span(120), "2 hours")
        self.assertEqual(alarm_title("Drink water"), "Time to drink water")
        self.assertEqual(alarm_title("  "), "Time for a break")


class StepperTests(unittest.TestCase):
    def test_bump_snaps_to_the_step(self):
        self.assertEqual(bump_minutes(45, 1, 5, 1, 240), 50)
        self.assertEqual(bump_minutes(45, -1, 5, 1, 240), 40)
        self.assertEqual(bump_minutes(25, 1, 5, 1, 240), 30)
        self.assertEqual(bump_minutes(7, -1, 5, 1, 240), 5)
        self.assertEqual(bump_minutes(1, -1, 5, 1, 240), 1)
        self.assertEqual(bump_minutes(240, 1, 5, 1, 240), 240)


class ScheduleTests(unittest.TestCase):
    def test_fraction_and_retarget(self):
        self.assertAlmostEqual(elapsed_fraction(30, 0, 1), 0.5)
        self.assertEqual(elapsed_fraction(100, 0, 1), 0.0)
        self.assertAlmostEqual(retarget_frequency(200, 100, 1), 160)
        self.assertAlmostEqual(retarget_frequency(50, 100, 2), 220)

    def test_soonest_skips_disabled(self):
        items = [
            reminder("Later", 500),
            reminder("Off", 100, enabled=False),
            reminder("Soon", 200),
        ]
        self.assertEqual(soonest(items).name, "Soon")
        items[2].enabled = False
        self.assertEqual(soonest(items).name, "Later")
        self.assertIsNone(soonest([reminder("Off", 100, enabled=False)]))

    def test_take_due_reschedules_only_what_is_due(self):
        now = 1_000.0
        water = reminder("Water", 900, frequency=40)
        stretch = reminder("Stretch", 2_000, frequency=45)
        taken = take_due([water, stretch], now)
        self.assertEqual(taken, [water.id])
        self.assertAlmostEqual(water.next_due, now + 40 * 60)
        self.assertEqual(stretch.next_due, 2_000)
        self.assertEqual(take_due([water, stretch], now), [])

    def test_soften_spaces_missed_reminders(self):
        now = 10_000.0
        first = reminder("A", 1_000)
        second = reminder("B", 2_000)
        later = reminder("C", 50_000)
        self.assertTrue(soften_startup_overdue([second, first, later], now, first_delay=2, gap=45))
        self.assertAlmostEqual(first.next_due, now + 2)
        self.assertAlmostEqual(second.next_due, now + 47)
        self.assertEqual(later.next_due, 50_000)
        self.assertFalse(soften_startup_overdue([later], now))


class HoldTests(unittest.TestCase):
    def test_meeting_preserves_remaining_time(self):
        now = 1_000.0
        item = reminder("Water", 1_300)
        state = make_state([item])
        start_meeting(state, now, 30)
        self.assertTrue(is_suppressed(state, now))
        self.assertAlmostEqual(clock_basis(state, now + 100), now)
        self.assertAlmostEqual(item.next_due - clock_basis(state, now + 100), 300)
        self.assertFalse(tick_expired_snooze(state, now + 1_000))
        self.assertTrue(tick_expired_snooze(state, now + 1_800))
        self.assertFalse(is_suppressed(state, now + 1_800))
        self.assertAlmostEqual(item.next_due - (now + 1_800), 300)

    def test_early_resume_also_preserves_remaining(self):
        now = 1_000.0
        item = reminder("Water", 1_600)
        state = make_state([item])
        start_meeting(state, now, 30)
        end_meeting(state, now + 600)
        self.assertAlmostEqual(item.next_due - (now + 600), 600)
        self.assertIsNone(state.snooze_until)
        self.assertIsNone(state.hold_started_at)

    def test_pause_cancels_the_meeting_timer(self):
        now = 1_000.0
        item = reminder("Water", 1_400)
        state = make_state([item])
        start_meeting(state, now, 15)
        pause(state, now + 100)
        self.assertIsNone(state.snooze_until)
        self.assertFalse(state.running)
        self.assertAlmostEqual(state.hold_started_at, now)
        self.assertFalse(meeting_is_active(state, now + 100))
        resume(state, now + 500)
        self.assertTrue(state.running)
        self.assertAlmostEqual(item.next_due - (now + 500), 400)

    def test_meeting_after_a_pause_keeps_the_whole_freeze(self):
        now = 1_000.0
        item = reminder("Water", 1_600)
        state = make_state([item])
        pause(state, now)
        start_meeting(state, now + 300, 15)
        self.assertTrue(state.running)
        self.assertAlmostEqual(state.hold_started_at, now)
        self.assertTrue(tick_expired_snooze(state, now + 300 + 15 * 60))
        resumed_at = now + 300 + 15 * 60
        self.assertAlmostEqual(item.next_due - resumed_at, 600)

    def test_overdue_reminder_fires_when_the_freeze_ends(self):
        now = 1_000.0
        item = reminder("Water", 900)
        state = make_state([item])
        pause(state, now)
        resume(state, now + 300)
        self.assertAlmostEqual(item.next_due, now + 300)

    def test_startup_after_an_expired_meeting_counts_the_time_after_it(self):
        hold = 1_000.0
        item = reminder("Water", 1_300)
        state = make_state([item], snooze=2_800, hold=hold)
        self.assertTrue(reconcile_hold_on_startup(state, 3_000))
        self.assertIsNone(state.hold_started_at)
        self.assertIsNone(state.snooze_until)
        self.assertAlmostEqual(item.next_due, 3_100)

    def test_startup_during_a_meeting_stays_frozen(self):
        item = reminder("Water", 1_300)
        state = make_state([item], snooze=2_800, hold=1_000)
        self.assertFalse(reconcile_hold_on_startup(state, 2_000))
        self.assertAlmostEqual(state.hold_started_at, 1_000)
        self.assertAlmostEqual(item.next_due, 1_300)
        self.assertTrue(is_suppressed(state, 2_000))

    def test_startup_while_paused_does_not_advance(self):
        item = reminder("Water", 1_300)
        state = make_state([item], running=False, hold=1_000)
        self.assertFalse(reconcile_hold_on_startup(state, 5_000))
        self.assertAlmostEqual(state.hold_started_at, 1_000)
        self.assertAlmostEqual(item.next_due, 1_300)

    def test_leftover_hold_while_running_is_dropped(self):
        item = reminder("Water", 1_300)
        state = make_state([item], hold=1_000)
        self.assertTrue(reconcile_hold_on_startup(state, 2_000))
        self.assertIsNone(state.hold_started_at)
        self.assertAlmostEqual(item.next_due, 1_300)


class TravelTests(unittest.TestCase):
    def test_crosses_the_screen_and_settles_in_the_center(self):
        start_x, start_y, done = travel_position(0, 1728, 1117, 240, 180)
        mid_x, mid_y, mid_done = travel_position(2.5, 1728, 1117, 240, 180)
        end_x, end_y, arrived = travel_position(5, 1728, 1117, 240, 180)
        self.assertFalse(done)
        self.assertFalse(mid_done)
        self.assertTrue(arrived)
        self.assertGreater(start_x, 1728)
        self.assertGreater(start_x, mid_x)
        self.assertGreater(mid_x, end_x)
        self.assertGreater(mid_y, start_y)
        self.assertGreater(mid_y, end_y)
        self.assertAlmostEqual(end_x, (1728 - 240) / 2.0)

    def test_stays_on_a_short_screen(self):
        _x, y, _done = travel_position(2.5, 800, 600, 240, 500)
        self.assertGreaterEqual(y, 16)
        self.assertLessEqual(y, 600 - 500 - 16)


class StorageTests(unittest.TestCase):
    def test_roundtrip_and_defaults(self):
        now = 1_700_000_000.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state, created = load_state(path, now)
            self.assertTrue(created)
            self.assertEqual(
                [item.name for item in state.reminders],
                ["Drink water", "Take a small rest", "Walk a bit", "Stretch"],
            )
            state.reminders[0].name = "Sip"
            state.sound_enabled = False
            state.hold_started_at = now
            save_state(path, state)
            loaded, created = load_state(path, now + 10)
            self.assertFalse(created)
            self.assertEqual(loaded.reminders[0].name, "Sip")
            self.assertFalse(loaded.sound_enabled)
            self.assertAlmostEqual(loaded.hold_started_at, now)

    def test_corrupt_file_falls_back_and_is_kept(self):
        now = 1_700_000_000.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            state, created = load_state(path, now)
            self.assertTrue(created)
            self.assertEqual(len(state.reminders), 4)
            self.assertTrue((Path(directory) / "state.json.broken").exists())

    def test_values_are_clamped_and_duplicate_ids_split(self):
        now = 50.0
        raw = {
            "reminders": [
                {
                    "id": "same",
                    "name": "  Walk   a bit  ",
                    "kind": "nope",
                    "frequency_minutes": 999,
                    "duration_minutes": 0,
                    "enabled": True,
                    "next_due": 80,
                    "color": "blue",
                },
                {"id": "same", "name": "Stretch", "kind": "stretch", "frequency_minutes": 10, "duration_minutes": 2},
            ]
        }
        from nudge.storage import state_from_dict

        state = state_from_dict(raw, now)
        self.assertEqual(state.reminders[0].name, "Walk a bit")
        self.assertEqual(state.reminders[0].kind, "bounce")
        self.assertEqual(state.reminders[0].frequency_minutes, 240)
        self.assertEqual(state.reminders[0].duration_minutes, 1)
        self.assertEqual(state.reminders[0].color, "#d6456a")
        self.assertNotEqual(state.reminders[0].id, state.reminders[1].id)

    def test_lock_blocks_a_second_holder_and_clears_a_dead_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nudge.lock"
            first = ProcessLock(path)
            self.assertTrue(first.acquire())
            second = ProcessLock(path)
            self.assertFalse(second.acquire())
            first.release()
            self.assertFalse(path.exists())
            self.assertTrue(second.acquire())
            second.release()

            dead = 99_999_999
            try:
                os.kill(dead, 0)
            except OSError:
                path.write_text(str(dead), encoding="utf-8")
                revived = ProcessLock(path)
                self.assertTrue(revived.acquire())
                revived.release()
            else:
                self.skipTest("unexpected live pid")


class DefaultStateTests(unittest.TestCase):
    def test_defaults_are_armed_in_the_future(self):
        now = 10_000.0
        state = default_state(now)
        self.assertTrue(state.running)
        self.assertTrue(state.sound_enabled)
        for item in state.reminders:
            self.assertGreater(item.next_due, now)
            self.assertTrue(item.enabled)


if __name__ == "__main__":
    unittest.main()
