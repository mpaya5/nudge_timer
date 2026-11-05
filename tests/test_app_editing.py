"""Adding, editing, deleting and adjusting reminders through the real window."""

import unittest
from unittest import mock

from helpers import GuiCase, needs_tk

from nudge.models import KINDS, MAX_DURATION, MAX_FREQUENCY, PALETTE


@needs_tk
class StartupTests(GuiCase):
    def test_first_launch_shows_the_four_default_options(self):
        app = self.launch()
        self.assertEqual(
            [r.name for r in app.state.reminders],
            ["Drink water", "Take a small rest", "Walk a bit", "Stretch"],
        )
        self.assertEqual(len(app.cards), 4)
        self.assertTrue(self.path.exists(), "first launch should save the defaults")
        self.assertEqual(
            [(r.frequency_minutes, r.duration_minutes) for r in app.state.reminders],
            [(40, 1), (90, 5), (60, 5), (45, 2)],
        )

    def test_cards_and_hero_show_the_countdown(self):
        app = self.launch()
        water = self.reminder("Drink water")
        card = app.cards[water.id]
        self.assertEqual(card.countdown.cget("text"), "Next in 40:00")
        self.assertEqual(card.freq_value.cget("text"), "40")
        self.assertEqual(card.dur_value.cget("text"), "1")
        self.assertEqual(app.next_name.cget("text"), "Drink water")
        self.assertEqual(app.status.cget("text"), "Next up")
        self.assertIn("Every 40 min", app.next_meta.cget("text"))

    def test_countdown_moves_with_the_clock(self):
        app = self.launch()
        self.clock.advance(65)
        app.tick()
        card = app.cards[self.reminder("Drink water").id]
        self.assertEqual(card.countdown.cget("text"), "Next in 38:55")

    def test_settings_survive_closing_and_reopening(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._change_frequency(water, 1)
        app._change_duration(water, 1)
        app._toggle(self.reminder("Stretch"))
        app._commit_new(
            {"name": "Look away", "kind": "bounce", "color": "#0f8a8a", "frequency": 20, "duration": 1}
        )
        self.clock.advance(120)
        app = self.relaunch()
        self.assertEqual(len(app.cards), 5)
        water = self.reminder("Drink water")
        self.assertEqual((water.frequency_minutes, water.duration_minutes), (45, 2))
        self.assertFalse(self.reminder("Stretch").enabled)
        look = self.reminder("Look away")
        self.assertEqual((look.kind, look.color, look.frequency_minutes), ("bounce", "#0f8a8a", 20))

    def test_the_clock_label_uses_the_current_time(self):
        import time

        app = self.launch()
        expected = time.strftime("%H:%M", time.localtime(self.clock()))
        self.assertEqual(app.clock.cget("text"), expected)

    def test_hint_is_shown_once_then_stays_dismissed(self):
        app = self.launch()
        self.assertEqual(app.hint.winfo_manager(), "pack")
        app._dismiss_hint()
        self.assertEqual(app.hint.winfo_manager(), "")
        app = self.relaunch()
        self.assertEqual(app.hint.winfo_manager(), "")
        self.assertTrue(app.state.hint_dismissed)

    def test_reminders_missed_while_closed_come_back_one_by_one(self):
        def overdue(state):
            for index, reminder in enumerate(state.reminders):
                reminder.next_due = self.clock() - 1000 + index

        self.launch(overdue)
        due = sorted(r.next_due for r in self.app.state.reminders)
        base = self.clock()
        self.assertEqual([round(d - base) for d in due], [2, 47, 92, 137])
        self.assertIsNone(self.app.overlay, "nothing should pop up at the instant of launch")

    def test_empty_list_stays_empty_after_restart(self):
        def nothing(state):
            state.reminders = []

        app = self.launch(nothing)
        self.assertEqual(app.cards, {})
        self.assertEqual(app.next_name.cget("text"), "No reminder")
        app = self.relaunch()
        self.assertEqual(app.state.reminders, [])


@needs_tk
class AddEditDialogTests(GuiCase):
    def open_add(self):
        self.app._add()
        self.assertIsNotNone(self.app.dialog)
        return self.app.dialog

    def test_add_a_reminder(self):
        app = self.launch()
        dialog = self.open_add()
        self.fill(dialog, name="Look away from the screen", freq=20, dur=1)
        dialog._select_kind("bounce")
        dialog._save()
        self.assertEqual(len(app.state.reminders), 5)
        added = self.reminder("Look away from the screen")
        self.assertEqual(added.kind, "bounce")
        self.assertEqual(added.frequency_minutes, 20)
        self.assertEqual(added.duration_minutes, 1)
        self.assertTrue(added.enabled)
        self.assertAlmostEqual(added.next_due, self.clock() + 20 * 60)
        self.assertIn(added.id, app.cards)
        self.assertIsNone(app.dialog, "the dialog closes after saving")
        self.assertEqual(self.saved().reminders[-1].name, "Look away from the screen")

    def test_a_new_reminder_gets_an_unused_color_and_follows_its_animation(self):
        self.launch()
        dialog = self.open_add()
        used = {r.color for r in self.app.state.reminders}
        self.assertNotIn(dialog.color, used)
        self.assertIn(dialog.color, PALETTE)
        dialog._select_kind("walk")
        self.assertEqual(dialog.color, KINDS["walk"]["color"])
        dialog._select_color(PALETTE[5])
        dialog._select_kind("rest")
        self.assertEqual(dialog.color, PALETTE[5], "a color you picked is kept")

    def test_name_is_tidied(self):
        app = self.launch()
        dialog = self.open_add()
        self.fill(dialog, name="   Look    far   away  ", freq=10, dur=1)
        dialog._save()
        self.assertEqual(app.state.reminders[-1].name, "Look far away")

    def test_limits_are_accepted(self):
        app = self.launch()
        for name, freq, dur in (
            ("a" * 40, 1, 1),
            ("Longest", MAX_FREQUENCY, MAX_DURATION),
        ):
            dialog = self.open_add()
            self.fill(dialog, name=name, freq=freq, dur=dur)
            dialog._save()
        self.assertEqual(len(app.state.reminders), 6)
        self.assertEqual(app.state.reminders[-1].frequency_minutes, 240)
        self.assertEqual(app.state.reminders[-1].duration_minutes, 60)

    def test_invalid_input_is_refused_with_a_message(self):
        app = self.launch()
        cases = [
            (dict(name="", freq=10, dur=1), "name"),
            (dict(name="   ", freq=10, dur=1), "name"),
            (dict(name="x" * 41, freq=10, dur=1), "40 characters"),
            (dict(name="Ok", freq="abc", dur=1), "whole minutes"),
            (dict(name="Ok", freq="", dur=1), "whole minutes"),
            (dict(name="Ok", freq="1.5", dur=1), "whole minutes"),
            (dict(name="Ok", freq=10, dur="soon"), "whole minutes"),
            (dict(name="Ok", freq=0, dur=1), "Frequency should be"),
            (dict(name="Ok", freq=-5, dur=1), "Frequency should be"),
            (dict(name="Ok", freq=MAX_FREQUENCY + 1, dur=1), "Frequency should be"),
            (dict(name="Ok", freq=10, dur=0), "Timer should be"),
            (dict(name="Ok", freq=10, dur=MAX_DURATION + 1), "Timer should be"),
        ]
        dialog = self.open_add()
        for values, expected in cases:
            with self.subTest(values=values):
                self.fill(dialog, **values)
                dialog._save()
                self.assertEqual(len(app.state.reminders), 4)
                self.assertIs(app.dialog, dialog, "the dialog stays open so you can fix it")
                self.assertIn(expected, dialog.error.cget("text"))
        self.fill(dialog, name="Fixed", freq=10, dur=1)
        dialog._save()
        self.assertEqual(len(app.state.reminders), 5)

    def test_saving_twice_adds_only_one(self):
        app = self.launch()
        dialog = self.open_add()
        self.fill(dialog, name="Once", freq=10, dur=1)
        dialog._save()
        dialog._save()
        self.assertEqual(len([r for r in app.state.reminders if r.name == "Once"]), 1)

    def test_cancel_adds_nothing(self):
        app = self.launch()
        dialog = self.open_add()
        self.fill(dialog, name="Never saved", freq=10, dur=1)
        dialog.destroy()
        self.assertEqual(len(app.state.reminders), 4)
        self.assertIsNone(app.dialog)

    def test_only_one_dialog_at_a_time(self):
        app = self.launch()
        first = self.open_add()
        app._add()
        app._edit(self.reminder("Stretch"))
        self.assertIs(app.dialog, first)
        self.assertIn("Finish", app.note)

    def test_dialog_keyboard_shortcuts_are_bound(self):
        self.launch()
        dialog = self.open_add()
        self.assertTrue(dialog.bind("<Return>"))
        self.assertTrue(dialog.bind("<Escape>"))

    def test_edit_dialog_shows_the_current_values(self):
        self.launch()
        walk = self.reminder("Walk a bit")
        self.app._edit(walk)
        dialog = self.app.dialog
        self.assertEqual(dialog.name_entry.get(), "Walk a bit")
        self.assertEqual(dialog.freq_entry.get(), "60")
        self.assertEqual(dialog.dur_entry.get(), "5")
        self.assertEqual(dialog.kind, "walk")
        self.assertEqual(dialog.color, walk.color)

    def test_edit_everything(self):
        app = self.launch()
        walk = self.reminder("Walk a bit")
        app._edit(walk)
        dialog = app.dialog
        self.fill(dialog, name="Walk to the window", freq=30, dur=3)
        dialog._select_kind("stretch")
        dialog._select_color(PALETTE[6])
        dialog._save()
        saved = self.saved().reminders[2]
        self.assertEqual(saved.id, walk.id)
        self.assertEqual(
            (saved.name, saved.kind, saved.color, saved.frequency_minutes, saved.duration_minutes),
            ("Walk to the window", "stretch", PALETTE[6], 30, 3),
        )
        self.assertEqual(app.cards[walk.id].name.cget("text"), "Walk to the window")

    def test_lowering_the_frequency_pulls_the_next_alarm_in(self):
        app = self.launch()
        walk = self.reminder("Walk a bit")
        self.assertAlmostEqual(walk.next_due - self.clock(), 60 * 60)
        app._edit(walk)
        self.fill(app.dialog, freq=10)
        app.dialog._save()
        self.assertAlmostEqual(walk.next_due - self.clock(), 10 * 60)

    def test_raising_the_frequency_keeps_the_time_already_counted(self):
        app = self.launch()
        walk = self.reminder("Walk a bit")
        self.clock.advance(30 * 60)
        app._edit(walk)
        self.fill(app.dialog, freq=120)
        app.dialog._save()
        self.assertAlmostEqual(walk.next_due - self.clock(), 30 * 60)

    def test_editing_the_timer_alone_does_not_move_the_schedule(self):
        app = self.launch()
        walk = self.reminder("Walk a bit")
        before = walk.next_due
        app._edit(walk)
        self.fill(app.dialog, dur=9)
        app.dialog._save()
        self.assertEqual(walk.next_due, before)
        self.assertEqual(walk.duration_minutes, 9)

    def test_saving_an_edit_for_a_reminder_deleted_meanwhile_is_refused(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        app._edit(stretch)
        dialog = app.dialog
        with mock.patch("nudge.app.messagebox.askyesno", return_value=True):
            app._delete(stretch)
        self.fill(dialog, name="Ghost")
        dialog._save()
        self.assertEqual(len(app.state.reminders), 3)
        self.assertNotIn("Ghost", [r.name for r in self.saved().reminders])
        self.assertIn("deleted", app.note)


@needs_tk
class AdjustAndDeleteTests(GuiCase):
    def test_frequency_steps_by_five_and_stays_in_range(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._change_frequency(water, 1)
        self.assertEqual(water.frequency_minutes, 45)
        app._change_frequency(water, -1)
        app._change_frequency(water, -1)
        self.assertEqual(water.frequency_minutes, 35)
        water.frequency_minutes = 3
        app._change_frequency(water, -1)
        self.assertEqual(water.frequency_minutes, 1)
        app._change_frequency(water, -1)
        self.assertEqual(water.frequency_minutes, 1)
        water.frequency_minutes = MAX_FREQUENCY
        app._change_frequency(water, 1)
        self.assertEqual(water.frequency_minutes, MAX_FREQUENCY)

    def test_timer_steps_by_one_and_stays_in_range(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._change_duration(water, 1)
        self.assertEqual(water.duration_minutes, 2)
        app._change_duration(water, -1)
        app._change_duration(water, -1)
        self.assertEqual(water.duration_minutes, 1)
        water.duration_minutes = MAX_DURATION
        app._change_duration(water, 1)
        self.assertEqual(water.duration_minutes, MAX_DURATION)
        self.assertEqual(self.saved().reminders[0].duration_minutes, 1, "unchanged edge is not rewritten")

    def test_changing_frequency_with_the_buttons_is_saved_and_shown(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._change_frequency(water, -1)
        self.assertEqual(self.saved().reminders[0].frequency_minutes, 35)
        self.assertEqual(app.cards[water.id].freq_value.cget("text"), "35")

    def test_shortening_frequency_never_leaves_more_time_than_the_new_frequency(self):
        app = self.launch()
        water = self.reminder("Drink water")
        water.frequency_minutes = 10
        water.next_due = self.clock() + 10 * 60
        app._change_frequency(water, -1)
        self.assertEqual(water.frequency_minutes, 5)
        self.assertAlmostEqual(water.next_due - self.clock(), 5 * 60)

    def test_switch_off_stops_alarms_and_switch_on_restarts_a_late_one(self):
        app = self.launch()
        water = self.reminder("Drink water")
        app._toggle(water)
        self.assertFalse(water.enabled)
        self.assertEqual(app.cards[water.id].countdown.cget("text"), "Off")
        self.tick_at(self.clock() + 3 * 3600)
        self.assertNotIn("water", self.played)
        app._toggle(water)
        self.assertTrue(water.enabled)
        self.assertAlmostEqual(water.next_due - self.clock(), 40 * 60)

    def test_switching_on_keeps_a_deadline_that_has_not_passed(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        due = stretch.next_due
        app._toggle(stretch)
        app._toggle(stretch)
        self.assertEqual(stretch.next_due, due)

    def test_hero_skips_switched_off_reminders(self):
        app = self.launch()
        app._toggle(self.reminder("Drink water"))
        self.assertEqual(app.next_name.cget("text"), "Stretch")
        for item in app.state.reminders:
            if item.enabled:
                app._toggle(item)
        self.assertEqual(app.next_name.cget("text"), "No reminder")

    def test_delete_asks_first(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        with mock.patch("nudge.app.messagebox.askyesno", return_value=False) as ask:
            app._delete(stretch)
        self.assertTrue(ask.called)
        self.assertEqual(len(app.state.reminders), 4)
        with mock.patch("nudge.app.messagebox.askyesno", return_value=True):
            app._delete(stretch)
        self.assertEqual(len(app.state.reminders), 3)
        self.assertNotIn(stretch.id, app.cards)
        self.assertEqual(len(self.saved().reminders), 3)

    def test_deleting_the_last_one_shows_the_empty_state(self):
        app = self.launch()
        with mock.patch("nudge.app.messagebox.askyesno", return_value=True):
            for item in list(app.state.reminders):
                app._delete(item)
        self.assertEqual(app.cards, {})
        self.assertEqual(app.next_name.cget("text"), "No reminder")
        app.tick()
        self.assertIsNone(app.overlay)

    def test_a_deleted_reminder_waiting_in_the_queue_never_rings(self):
        app = self.launch()
        water = self.reminder("Drink water")
        rest = self.reminder("Take a small rest")
        self.tick_at(rest.next_due + 1)
        self.assertEqual(app.overlay.reminder_id, water.id)
        self.assertIn(rest.id, app.queue)
        with mock.patch("nudge.app.messagebox.askyesno", return_value=True):
            app._delete(rest)
        self.assertNotIn(rest.id, app.queue)
        app.overlay.dismiss_quietly()
        names = []
        while app.overlay is not None:
            names.append(app.overlay.reminder.name)
            app.overlay.dismiss_quietly()
        self.assertNotIn("Take a small rest", names)


@needs_tk
class SoundChoiceTests(GuiCase):
    def pick(self, dialog, value):
        labels = dict(dialog.sound_options)
        dialog.sound_var.set(labels[value])

    def a_named_sound(self, dialog):
        named = [v for v, _ in dialog.sound_options if v not in ("auto", "none")]
        if not named:
            self.skipTest("this computer has no system sounds to choose from")
        return named[0]

    def test_the_editor_starts_on_the_current_sound(self):
        self.launch(mutate=lambda state: setattr(state.reminders[1], "sound", "none"))
        self.app._edit(self.reminder("Walk a bit"))
        self.assertEqual(self.app.dialog._chosen_sound(), "auto")
        self.app.dialog.destroy()
        self.app._edit(self.reminder("Take a small rest"))
        self.assertEqual(self.app.dialog._chosen_sound(), "none")
        self.assertEqual(self.app.dialog.sound_var.get(), "Silent")

    def test_a_new_reminder_defaults_to_the_animation_sound(self):
        app = self.launch()
        app._add()
        self.assertEqual(app.dialog._chosen_sound(), "auto")
        self.fill(app.dialog, name="Look away", freq=20, dur=1)
        app.dialog._save()
        self.assertEqual(self.reminder("Look away").sound, "auto")

    def test_choose_a_sound_for_a_new_reminder(self):
        app = self.launch()
        app._add()
        dialog = app.dialog
        self.fill(dialog, name="Look away", freq=20, dur=1)
        self.pick(dialog, "none")
        dialog._save()
        self.assertEqual(self.reminder("Look away").sound, "none")
        self.assertEqual(self.saved().reminders[-1].sound, "none")

    def test_changing_the_sound_of_an_existing_reminder_keeps_everything_else(self):
        app = self.launch()
        walk = self.reminder("Walk a bit")
        due = walk.next_due
        app._edit(walk)
        self.pick(app.dialog, self.a_named_sound(app.dialog))
        chosen = app.dialog._chosen_sound()
        app.dialog._save()
        self.assertEqual(walk.sound, chosen)
        self.assertEqual((walk.name, walk.kind, walk.frequency_minutes, walk.duration_minutes),
                         ("Walk a bit", "walk", 60, 5))
        self.assertEqual(walk.next_due, due)
        self.assertEqual(self.saved().reminders[2].sound, chosen)

    def test_each_reminder_keeps_its_own_sound(self):
        app = self.launch()
        for name, value in (("Drink water", "none"), ("Stretch", None)):
            app._edit(self.reminder(name))
            self.pick(app.dialog, value or self.a_named_sound(app.dialog))
            app.dialog._save()
        self.assertEqual([r.sound for r in app.state.reminders][0], "none")
        self.assertNotIn(app.state.reminders[3].sound, ("auto", "none"))
        self.assertEqual([r.sound for r in app.state.reminders][1:3], ["auto", "auto"])

    def test_the_choice_survives_closing_and_reopening_the_app(self):
        app = self.launch()
        app._edit(self.reminder("Stretch"))
        self.pick(app.dialog, "none")
        app.dialog._save()
        self.relaunch()
        self.assertEqual(self.reminder("Stretch").sound, "none")

    def test_cancelling_the_editor_keeps_the_old_sound(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        app._edit(stretch)
        self.pick(app.dialog, "none")
        app.dialog.destroy()
        self.assertEqual(stretch.sound, "auto")

    def test_play_previews_the_chosen_sound_with_the_chosen_animation(self):
        app = self.launch()
        app._add()
        app.dialog._select_kind("rest")
        self.pick(app.dialog, "none")
        app.dialog._play_sound()
        self.assertEqual(self.played, ["rest"])
        self.assertEqual(self.played_sounds, ["none"])
        named = self.a_named_sound(app.dialog)
        self.pick(app.dialog, named)
        app.dialog._play_sound()
        self.assertEqual(self.played_sounds, ["none", named])

    def test_play_works_even_while_everything_is_muted(self):
        app = self.launch()
        app._toggle_sound()
        self.assertFalse(app.state.sound_enabled)
        app._add()
        app.dialog._play_sound()
        self.assertEqual(self.played_sounds, ["auto"])

    def test_playing_never_changes_the_saved_reminder(self):
        app = self.launch()
        before = [r.to_dict() for r in app.state.reminders]
        app._edit(self.reminder("Stretch"))
        self.pick(app.dialog, "none")
        app.dialog._play_sound()
        self.assertEqual([r.to_dict() for r in app.state.reminders], before)

    def test_a_failing_speaker_does_not_break_the_editor(self):
        app = self.launch()
        app.player = mock.Mock(side_effect=RuntimeError("no audio device"))
        app._add()
        with mock.patch("traceback.print_exc") as report:
            app.dialog._play_sound()
        self.assertTrue(report.called)
        self.assertTrue(app.dialog.winfo_exists())

    def test_a_saved_sound_this_computer_lacks_is_kept_when_editing(self):
        app = self.launch()
        stretch = self.reminder("Stretch")
        stretch.sound = "Hero"
        with mock.patch("platform.system", return_value="Linux"):
            app._edit(stretch)
        dialog = app.dialog
        self.assertEqual(dialog._chosen_sound(), "Hero")
        self.fill(dialog, name="Stretch more")
        dialog._save()
        self.assertEqual(stretch.sound, "Hero", "renaming must not silently change the sound")


@needs_tk
class AddYourOwnSoundTests(GuiCase):
    def wav(self, name="Door Bell.wav", data=b"RIFF....WAVE"):
        path = self.sounds_dir.parent / "downloads" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def open_editor(self, name="Stretch"):
        app = self.launch()
        app._edit(self.reminder(name))
        return app, app.dialog

    def menu_labels(self, dialog):
        menu = dialog.sound_menu["menu"]
        return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]

    def test_the_last_menu_entry_invites_people_to_add_a_sound(self):
        _app, dialog = self.open_editor()
        self.assertEqual(self.menu_labels(dialog)[-1], "Add your own sound…")
        self.assertEqual(self.menu_labels(dialog), [label for _v, label in dialog.sound_options])

    def test_clicking_the_menu_entry_opens_the_file_chooser(self):
        _app, dialog = self.open_editor()
        path = self.wav()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(path)) as ask:
            menu = dialog.sound_menu["menu"]
            menu.invoke(menu.index("end"))
        self.assertTrue(ask.called)
        self.assertEqual(dialog._chosen_sound(), "custom:Door Bell.wav")
        self.assertEqual(dialog.sound_var.get(), "Door Bell (yours)")

    def test_an_added_sound_is_selected_played_and_saved_with_the_reminder(self):
        app, dialog = self.open_editor()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav())):
            dialog._pick_sound("__add__")
        self.assertEqual(self.played_sounds, ["custom:Door Bell.wav"], "the new sound plays so you can hear it")
        self.assertEqual(dialog.error.cget("text"), "")
        dialog._save()
        stretch = self.reminder("Stretch")
        self.assertEqual(stretch.sound, "custom:Door Bell.wav")
        self.assertEqual(self.saved().reminders[3].sound, "custom:Door Bell.wav")
        self.assertTrue((self.sounds_dir / "Door Bell.wav").is_file())
        self.assertTrue(app.state.reminders[3] is stretch)

    def test_the_added_sound_can_be_used_by_other_reminders_too(self):
        app, dialog = self.open_editor()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav())):
            dialog._pick_sound("__add__")
        dialog._save()
        app._edit(self.reminder("Walk a bit"))
        values = [v for v, _l in app.dialog.sound_options]
        self.assertIn("custom:Door Bell.wav", values)
        self.assertEqual(values[-1], "__add__")
        app.dialog._pick_sound("custom:Door Bell.wav")
        app.dialog._save()
        self.assertEqual(self.reminder("Walk a bit").sound, "custom:Door Bell.wav")

    def test_an_alarm_rings_with_the_added_sound_after_restarting_the_app(self):
        app, dialog = self.open_editor()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav())):
            dialog._pick_sound("__add__")
        dialog._save()
        self.relaunch()
        self.fire(self.only("Stretch"))
        self.assertEqual(self.played_sounds, ["custom:Door Bell.wav"])

    def test_closing_the_file_chooser_changes_nothing(self):
        _app, dialog = self.open_editor()
        dialog._pick_sound("none")
        with mock.patch.object(dialog, "_ask_sound_file", return_value=""):
            dialog._pick_sound("__add__")
        self.assertEqual(dialog._chosen_sound(), "none")
        self.assertEqual(dialog.sound_var.get(), "Silent")
        self.assertEqual(self.played_sounds, [])
        self.assertFalse(self.sounds_dir.exists())

    def test_an_unusable_file_explains_the_problem_and_keeps_the_old_choice(self):
        _app, dialog = self.open_editor()
        dialog._pick_sound("none")
        bad = self.wav("notes.txt")
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(bad)):
            dialog._pick_sound("__add__")
        self.assertIn("Nudge can play", dialog.error.cget("text"))
        self.assertEqual(dialog._chosen_sound(), "none")
        self.assertEqual(dialog.sound_var.get(), "Silent")
        self.assertTrue(dialog.winfo_exists())

    def test_the_error_goes_away_after_a_good_file(self):
        _app, dialog = self.open_editor()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav("notes.txt"))):
            dialog._pick_sound("__add__")
        self.assertNotEqual(dialog.error.cget("text"), "")
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav())):
            dialog._pick_sound("__add__")
        self.assertEqual(dialog.error.cget("text"), "")

    def test_the_add_entry_is_never_saved_as_a_sound(self):
        _app, dialog = self.open_editor()
        dialog.sound_var.set("Add your own sound…")
        self.assertEqual(dialog._chosen_sound(), "auto")
        dialog._save()
        self.assertEqual(self.reminder("Stretch").sound, "auto")

    def test_the_file_chooser_only_suggests_sounds_this_computer_can_play(self):
        _app, dialog = self.open_editor()
        with mock.patch("nudge.dialog.filedialog.askopenfilename", return_value="") as ask, \
                mock.patch("platform.system", return_value="Windows"):
            self.assertEqual(dialog._ask_sound_file(), "")
        kwargs = ask.call_args[1]
        self.assertEqual(kwargs["filetypes"][0], ("Sounds", "*.wav"))
        self.assertIs(kwargs["parent"], dialog)

    def test_adding_a_sound_while_muted_still_lets_you_hear_it(self):
        app, dialog = self.open_editor()
        app._toggle_sound()
        with mock.patch.object(dialog, "_ask_sound_file", return_value=str(self.wav())):
            dialog._pick_sound("__add__")
        self.assertEqual(self.played_sounds, ["custom:Door Bell.wav"])


if __name__ == "__main__":
    unittest.main()
