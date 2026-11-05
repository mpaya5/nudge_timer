"""Constants, defaults and colour helpers. No window needed."""

import re
import unittest
from unittest import mock

from helpers import START

from nudge import models
from nudge.models import AppState, Reminder, default_state
from nudge.theme import mix


class ConstantsTests(unittest.TestCase):
    def test_ranges_and_steps_make_sense(self):
        self.assertLess(models.MIN_FREQUENCY, models.MAX_FREQUENCY)
        self.assertLess(models.MIN_DURATION, models.MAX_DURATION)
        self.assertGreater(models.FREQUENCY_STEP, 0)
        self.assertGreater(models.DURATION_STEP, 0)
        self.assertGreaterEqual(models.MIN_FREQUENCY, 1)

    def test_snooze_and_meeting_choices(self):
        self.assertIn(models.DEFAULT_SNOOZE, models.SNOOZE_MINUTES)
        self.assertEqual(list(models.SNOOZE_MINUTES), sorted(set(models.SNOOZE_MINUTES)))
        self.assertEqual(models.MEETING_MINUTES, (15, 30, 60, 120))
        self.assertGreater(models.MEETING_FROM_ALARM, 0)
        self.assertGreater(models.PROMPT_TIMEOUT, models.DEFAULT_SNOOZE)

    def test_kinds_and_palette(self):
        self.assertEqual(set(models.KIND_ORDER), set(models.KINDS))
        for kind, info in models.KINDS.items():
            self.assertRegex(info["color"], r"^#[0-9a-f]{6}$", kind)
            self.assertTrue(info["label"])
        for color in models.PALETTE:
            self.assertRegex(color, r"^#[0-9a-f]{6}$")
        self.assertEqual(len(set(models.PALETTE)), len(models.PALETTE))


class DefaultsTests(unittest.TestCase):
    def test_the_four_options_from_the_brief(self):
        state = default_state(START)
        by_name = {item.name: item for item in state.reminders}
        self.assertEqual(set(by_name), {"Drink water", "Take a small rest", "Walk a bit", "Stretch"})
        self.assertEqual(by_name["Drink water"].kind, "water")
        self.assertEqual(by_name["Take a small rest"].kind, "rest")
        self.assertEqual(by_name["Walk a bit"].kind, "walk")
        self.assertEqual(by_name["Stretch"].kind, "stretch")

    def test_defaults_are_valid(self):
        state = default_state(START)
        self.assertTrue(state.running)
        self.assertTrue(state.sound_enabled)
        self.assertFalse(state.hint_dismissed)
        self.assertIsNone(state.snooze_until)
        self.assertIsNone(state.hold_started_at)
        ids = set()
        for item in state.reminders:
            self.assertTrue(item.enabled)
            self.assertTrue(models.MIN_FREQUENCY <= item.frequency_minutes <= models.MAX_FREQUENCY)
            self.assertTrue(models.MIN_DURATION <= item.duration_minutes <= models.MAX_DURATION)
            self.assertAlmostEqual(item.next_due, START + item.frequency_minutes * 60)
            self.assertEqual(item.color, models.KINDS[item.kind]["color"])
            ids.add(item.id)
        self.assertEqual(len(ids), 4)

    def test_each_call_gets_fresh_ids_and_independent_objects(self):
        first, second = default_state(START), default_state(START)
        self.assertNotEqual([r.id for r in first.reminders], [r.id for r in second.reminders])
        first.reminders[0].name = "changed"
        self.assertEqual(second.reminders[0].name, "Drink water")

    def test_create_coerces_numbers_and_arms_the_timer(self):
        item = Reminder.create("x", "walk", "25", "3", "#1f9d62", START)
        self.assertEqual((item.frequency_minutes, item.duration_minutes), (25, 3))
        self.assertAlmostEqual(item.next_due, START + 25 * 60)
        self.assertTrue(item.enabled)
        disabled = Reminder.create("x", "walk", 25, 3, "#1f9d62", START, enabled=False)
        self.assertFalse(disabled.enabled)

    def test_reminders_follow_their_animation_sound_unless_told_otherwise(self):
        self.assertEqual(Reminder.create("x", "walk", 25, 3, "#1f9d62", START).sound, "auto")
        self.assertEqual(Reminder.create("x", "walk", 25, 3, "#1f9d62", START, sound="Glass").sound, "Glass")
        self.assertTrue(all(item.sound == "auto" for item in default_state(START).reminders))
        self.assertEqual(Reminder.create("x", "walk", 25, 3, "#1f9d62", START, sound="none").to_dict()["sound"], "none")

    def test_the_sound_choices_are_unique_and_include_auto_and_silent(self):
        self.assertEqual(len(set(models.VALID_SOUNDS)), len(models.VALID_SOUNDS))
        self.assertIn(models.SOUND_AUTO, models.VALID_SOUNDS)
        self.assertIn(models.SOUND_NONE, models.VALID_SOUNDS)
        for name in models.MAC_SOUND_NAMES:
            self.assertRegex(name, r"^[A-Za-z]+$")

    def test_serialisation_has_a_version_and_every_flag(self):
        data = default_state(START).to_dict()
        self.assertEqual(data["version"], 1)
        for key in ("snooze_until", "hold_started_at", "sound_enabled", "running", "hint_dismissed", "reminders"):
            self.assertIn(key, data)
        self.assertIsInstance(AppState([], None, None, True, True, False).to_dict()["reminders"], list)


class MixTests(unittest.TestCase):
    def test_blends(self):
        self.assertEqual(mix("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(mix("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(mix("#000000", "#ffffff", 0.5), "#7f7f7f")
        self.assertEqual(mix("#ff0000", "#0000ff", 0.5), "#7f007f")

    def test_always_returns_a_valid_colour(self):
        for color in ("#2f80ed", "#e07a3d", "#1c1917"):
            for amount in (0, 0.18, 0.55, 0.72, 0.86, 1):
                self.assertTrue(re.fullmatch(r"#[0-9a-f]{6}", mix(color, "#ffffff", amount)))

    def test_bad_input_falls_back_to_the_target(self):
        self.assertEqual(mix("blue", "#ffffff", 0.5), "#ffffff")
        self.assertEqual(mix("#12", "#ffffff", 0.5), "#ffffff")
        self.assertEqual(mix(None, "#ffffff", 0.5), "#ffffff")


class FontChoiceTests(unittest.TestCase):
    def pick(self, function, installed):
        with mock.patch("tkinter.font.families", return_value=tuple(installed)):
            return function(None)

    def test_each_system_gets_a_font_it_actually_has(self):
        from nudge.theme import pick_family, pick_mono
        cases = (
            (["Segoe UI", "Arial", "Consolas"], "Segoe UI", "Consolas"),
            (["Cantarell", "DejaVu Sans", "DejaVu Sans Mono"], "Cantarell", "DejaVu Sans Mono"),
            (["Ubuntu", "Liberation Mono"], "Ubuntu", "Liberation Mono"),
            (["Avenir Next", "Helvetica", "Menlo"], "Avenir Next", "Menlo"),
        )
        for installed, family, mono in cases:
            with self.subTest(installed=installed):
                self.assertEqual(self.pick(pick_family, installed), family)
                self.assertEqual(self.pick(pick_mono, installed), mono)

    def test_an_unknown_system_still_gets_a_usable_name(self):
        from nudge.theme import pick_family, pick_mono
        self.assertEqual(self.pick(pick_family, ["Zapf"]), "Helvetica")
        self.assertEqual(self.pick(pick_mono, ["Zapf"]), "Courier")


if __name__ == "__main__":
    unittest.main()
