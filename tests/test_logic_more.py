"""Edge cases for the timing rules, plus a randomised check that frozen time is never lost."""

import random
import unittest

from helpers import START

from nudge.logic import (
    WAKE_GAP_SECONDS,
    alarm_title,
    bump_minutes,
    clock_basis,
    duration_phrase,
    elapsed_fraction,
    end_meeting,
    format_remaining,
    format_span,
    is_suppressed,
    looks_like_wake,
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
from nudge.models import AppState, Reminder


def reminder(name, due, frequency=40, enabled=True):
    item = Reminder.create(name, "water", frequency, 1, "#2f80ed", 0)
    item.next_due = due
    item.enabled = enabled
    return item


def make_state(items, running=True, snooze=None, hold=None):
    return AppState(list(items), snooze, hold, True, running, False)


class WakeDetectionTests(unittest.TestCase):
    def test_threshold(self):
        self.assertFalse(looks_like_wake(None, 1000))
        self.assertFalse(looks_like_wake(1000, 1001))
        self.assertFalse(looks_like_wake(1000, 1000 + WAKE_GAP_SECONDS))
        self.assertTrue(looks_like_wake(1000, 1000 + WAKE_GAP_SECONDS + 0.1))
        self.assertTrue(looks_like_wake(1000, 1000 + 8 * 3600))

    def test_a_clock_moved_backwards_is_not_a_wake(self):
        self.assertFalse(looks_like_wake(1000, 500))


class WordingTests(unittest.TestCase):
    def test_spans(self):
        self.assertEqual(format_span(1), "1 min")
        self.assertEqual(format_span(90), "90 min")
        self.assertEqual(format_span(60), "1 hour")
        self.assertEqual(format_span(180), "3 hours")

    def test_durations(self):
        self.assertEqual(duration_phrase(1), "1 minute")
        self.assertEqual(duration_phrase(2), "2 minutes")
        self.assertEqual(duration_phrase(60), "60 minutes")

    def test_titles(self):
        self.assertEqual(alarm_title("Stretch"), "Time to stretch")
        self.assertEqual(alarm_title("drink water"), "Time to drink water")
        self.assertEqual(alarm_title("  Drink   water  "), "Time to drink water")
        self.assertEqual(alarm_title("Étirer"), "Time to étirer")
        self.assertEqual(alarm_title(""), "Time for a break")

    def test_remaining_rounds_to_the_nearest_second(self):
        self.assertEqual(format_remaining(59.4), "00:59")
        self.assertEqual(format_remaining(59.6), "01:00")
        self.assertEqual(format_remaining(3661), "1:01:01")
        self.assertEqual(format_remaining(0.2), "00:00")
        self.assertEqual(format_remaining(10 * 3600), "10:00:00")


class StepperEdgeTests(unittest.TestCase):
    def test_up_then_down_from_multiples_is_symmetrical(self):
        for value in range(5, 236, 5):
            up = bump_minutes(value, 1, 5, 1, 240)
            self.assertEqual(up, value + 5)
            self.assertEqual(bump_minutes(up, -1, 5, 1, 240), value)

    def test_off_step_values_snap_in_both_directions(self):
        self.assertEqual(bump_minutes(41, 1, 5, 1, 240), 45)
        self.assertEqual(bump_minutes(41, -1, 5, 1, 240), 40)
        self.assertEqual(bump_minutes(44, 1, 5, 1, 240), 45)
        self.assertEqual(bump_minutes(46, -1, 5, 1, 240), 45)
        self.assertEqual(bump_minutes(1, 1, 5, 1, 240), 5)

    def test_always_stays_inside_the_range(self):
        for value in range(1, 241):
            for direction in (-1, 1):
                result = bump_minutes(value, direction, 5, 1, 240)
                self.assertTrue(1 <= result <= 240, (value, direction, result))
        for value in range(1, 61):
            for direction in (-1, 1):
                result = bump_minutes(value, direction, 1, 1, 60)
                self.assertEqual(result, max(1, min(60, value + direction)))


class ScheduleEdgeTests(unittest.TestCase):
    def test_take_due_includes_the_exact_moment(self):
        item = reminder("Water", 1000)
        self.assertEqual(take_due([item], 999.9), [])
        self.assertEqual(take_due([item], 1000), [item.id])

    def test_take_due_ignores_switched_off_reminders(self):
        off = reminder("Off", 100, enabled=False)
        self.assertEqual(take_due([off], 10_000), [])
        self.assertEqual(off.next_due, 100)

    def test_soonest_breaks_ties_by_name(self):
        a, b = reminder("Bravo", 100), reminder("Alpha", 100)
        self.assertEqual(soonest([a, b]).name, "Alpha")
        self.assertIsNone(soonest([]))

    def test_fraction_is_clamped(self):
        self.assertEqual(elapsed_fraction(-50, 0, 1), 1.0)
        self.assertEqual(elapsed_fraction(10_000, 0, 1), 0.0)
        self.assertEqual(elapsed_fraction(30, 0, 0), 0.0)
        self.assertAlmostEqual(elapsed_fraction(45, 0, 1), 0.25)

    def test_retarget_edges(self):
        self.assertEqual(retarget_frequency(100, 100, 2), 220)
        self.assertEqual(retarget_frequency(90, 100, 2), 220)
        self.assertEqual(retarget_frequency(160, 100, 1), 160)
        self.assertEqual(retarget_frequency(10_000, 100, 1), 160)

    def test_soften_ignores_switched_off_and_future_reminders(self):
        now = 1000.0
        items = [reminder("Off", 1, enabled=False), reminder("Later", 5000), reminder("Late", 10)]
        self.assertTrue(soften_startup_overdue(items, now))
        self.assertEqual(items[0].next_due, 1)
        self.assertEqual(items[1].next_due, 5000)
        self.assertAlmostEqual(items[2].next_due, now + 2)

    def test_soften_keeps_the_original_order(self):
        now = 1000.0
        items = [reminder("C", 30), reminder("A", 10), reminder("B", 20)]
        soften_startup_overdue(items, now, first_delay=1, gap=10)
        self.assertEqual({i.name: i.next_due for i in items}, {"A": 1001, "B": 1011, "C": 1021})


class HoldEdgeTests(unittest.TestCase):
    def test_a_meeting_must_have_a_positive_length(self):
        state = make_state([reminder("W", 500)])
        for minutes in (0, -5):
            with self.assertRaises(ValueError):
                start_meeting(state, 100, minutes)
        self.assertIsNone(state.snooze_until)
        self.assertTrue(state.running)

    def test_the_meeting_is_over_at_the_exact_end_moment(self):
        state = make_state([reminder("W", 5000)])
        start_meeting(state, 1000, 15)
        end = 1000 + 900
        self.assertTrue(meeting_is_active(state, end - 0.001))
        self.assertFalse(meeting_is_active(state, end))
        self.assertTrue(is_suppressed(state, end - 0.001))
        self.assertFalse(is_suppressed(state, end))

    def test_normal_running_is_not_suppressed(self):
        state = make_state([reminder("W", 5000)])
        self.assertFalse(is_suppressed(state, 100))
        self.assertEqual(clock_basis(state, 100), 100)

    def test_expiry_is_ignored_when_nothing_is_frozen_or_paused(self):
        state = make_state([reminder("W", 5000)])
        self.assertFalse(tick_expired_snooze(state, 10_000))
        paused = make_state([reminder("W", 5000)], running=False, hold=50)
        self.assertFalse(tick_expired_snooze(paused, 10_000))

    def test_resume_during_a_meeting_does_not_end_it(self):
        item = reminder("W", 1600)
        state = make_state([item])
        start_meeting(state, 1000, 30)
        resume(state, 1200)
        self.assertTrue(is_suppressed(state, 1300))
        self.assertEqual(item.next_due, 1600)

    def test_resume_after_the_meeting_ran_out_releases_the_hold(self):
        item = reminder("W", 1600)
        state = make_state([item])
        start_meeting(state, 1000, 10)
        resume(state, 1000 + 700)
        self.assertIsNone(state.snooze_until)
        self.assertIsNone(state.hold_started_at)
        self.assertAlmostEqual(item.next_due, 1600 + 700)

    def test_end_meeting_also_ends_a_manual_pause(self):
        item = reminder("W", 1600)
        state = make_state([item])
        pause(state, 1000)
        end_meeting(state, 1500)
        self.assertTrue(state.running)
        self.assertAlmostEqual(item.next_due, 2100)

    def test_pause_twice_keeps_the_first_moment(self):
        state = make_state([reminder("W", 1600)])
        pause(state, 1000)
        pause(state, 1400)
        self.assertEqual(state.hold_started_at, 1000)

    def test_startup_bookkeeping_for_odd_saved_states(self):
        item = reminder("W", 1600)
        paused_with_old_meeting = make_state([item], running=False, snooze=500, hold=400)
        self.assertTrue(reconcile_hold_on_startup(paused_with_old_meeting, 1000))
        self.assertIsNone(paused_with_old_meeting.snooze_until)
        self.assertEqual(paused_with_old_meeting.hold_started_at, 400)
        meeting_without_hold = make_state([item], snooze=5000, hold=None)
        self.assertTrue(reconcile_hold_on_startup(meeting_without_hold, 1000))
        self.assertEqual(meeting_without_hold.hold_started_at, 1000)
        healthy = make_state([item])
        self.assertFalse(reconcile_hold_on_startup(healthy, 1000))


class TravelEdgeTests(unittest.TestCase):
    def test_zero_duration_arrives_immediately(self):
        x, y, done = travel_position(0, 1000, 800, 200, 100, duration=0)
        self.assertTrue(done)
        self.assertAlmostEqual(x, 400)

    def test_time_outside_the_trip_is_clamped(self):
        before = travel_position(-3, 1000, 800, 200, 100)
        start = travel_position(0, 1000, 800, 200, 100)
        after = travel_position(99, 1000, 800, 200, 100)
        end = travel_position(5, 1000, 800, 200, 100)
        self.assertEqual(before, start)
        self.assertEqual(after, end)

    def test_never_leaves_the_vertical_screen_area(self):
        for screen_w, screen_h, win_h in ((1728, 1117, 184), (1366, 768, 416), (800, 600, 500), (320, 240, 300)):
            for step in range(0, 51):
                _, y, _ = travel_position(step / 10.0, screen_w, screen_h, 270, win_h)
                self.assertGreaterEqual(y, 16)
                if screen_h - win_h - 16 >= 16:
                    self.assertLessEqual(y, screen_h - win_h - 16)


class FrozenTimeNeverLeaksTests(unittest.TestCase):
    """Random pauses, meetings and resumes must never gain or lose countdown time."""

    def run_sequence(self, seed):
        rng = random.Random(seed)
        far = 10**7
        item = reminder("Far", START + far)
        state = make_state([item])
        t = START
        unsuppressed = 0.0
        history = []
        for _ in range(150):
            previous = t
            dt = rng.choice([1, 5, 30, 90, 300, 900, 3600])
            t += dt
            if is_suppressed(state, previous):
                if meeting_is_active(state, previous) and state.snooze_until < t and state.running:
                    unsuppressed += t - state.snooze_until
            else:
                unsuppressed += dt
            tick_expired_snooze(state, t)
            op = rng.choice(["none", "none", "pause", "resume", "meeting", "end"])
            if op == "pause":
                pause(state, t)
            elif op == "resume":
                resume(state, t)
            elif op == "meeting":
                start_meeting(state, t, rng.choice([15, 30, 60, 120]))
            elif op == "end":
                end_meeting(state, t)
            history.append((round(t - START), op))
            remaining = item.next_due - clock_basis(state, t)
            expected = far - unsuppressed
            self.assertAlmostEqual(remaining, expected, places=3, msg="seed %s after %s" % (seed, history[-6:]))
            self.assertEqual(
                state.hold_started_at is None,
                not is_suppressed(state, t),
                "seed %s: hold and suppression disagree after %s" % (seed, history[-6:]),
            )

    def test_many_random_histories(self):
        for seed in range(300):
            self.run_sequence(seed)


if __name__ == "__main__":
    unittest.main()
