"""Saved settings: loading bad files, clamping, atomic saves, and the instance lock."""

import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import START

from nudge.models import MAX_DURATION, MAX_FREQUENCY, MIN_DURATION, MIN_FREQUENCY, Reminder
from nudge.storage import (
    ProcessLock,
    default_state_path,
    load_state,
    reminder_from_dict,
    save_state,
    state_from_dict,
)


class LoadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "state.json"

    def write(self, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        self.path.write_text(text, encoding="utf-8")

    def assert_fell_back_to_defaults(self):
        state, created = load_state(self.path, START)
        self.assertTrue(created)
        self.assertEqual(len(state.reminders), 4)
        return state

    def test_missing_file_gives_the_defaults(self):
        self.assert_fell_back_to_defaults()

    def test_unreadable_files_are_set_aside_not_deleted(self):
        for content in (
            "", "{not json", "[]", "null", '"text"', "42", "{}", '{"reminders": 5}', '{"reminders": [1]}',
        ):
            with self.subTest(content=content):
                if self.path.exists():
                    self.path.unlink()
                self.write(content)
                self.assert_fell_back_to_defaults()
                broken = self.path.with_name("state.json.broken")
                self.assertTrue(broken.exists())
                self.assertEqual(broken.read_text(encoding="utf-8"), content)
                broken.unlink()

    def test_non_utf8_file_is_handled(self):
        self.path.write_bytes(b"\xff\xfe\x00bad")
        self.assert_fell_back_to_defaults()

    def test_an_empty_list_is_a_real_choice_and_is_kept(self):
        self.write({"reminders": []})
        state, created = load_state(self.path, START)
        self.assertFalse(created)
        self.assertEqual(state.reminders, [])

    def test_unknown_extra_keys_are_ignored(self):
        self.write({"reminders": [], "future_feature": {"a": 1}, "version": 99})
        state, created = load_state(self.path, START)
        self.assertFalse(created)

    def test_bad_values_are_repaired_not_fatal(self):
        raw = {
            "reminders": [
                {
                    "id": "",
                    "name": 123,
                    "kind": ["x"],
                    "frequency_minutes": "soon",
                    "duration_minutes": None,
                    "enabled": "yes",
                    "next_due": "later",
                    "color": 7,
                }
            ],
            "snooze_until": "never",
            "hold_started_at": float("nan"),
            "sound_enabled": "loud",
            "running": 0,
            "hint_dismissed": "true",
        }
        state = state_from_dict(raw, START)
        item = state.reminders[0]
        self.assertTrue(item.id)
        self.assertEqual(item.name, "Reminder")
        self.assertEqual(item.kind, "bounce")
        self.assertEqual(item.frequency_minutes, 30)
        self.assertEqual(item.duration_minutes, 2)
        self.assertTrue(item.enabled)
        self.assertAlmostEqual(item.next_due, START + 30 * 60)
        self.assertRegex(item.color, r"^#[0-9a-f]{6}$")
        self.assertIsNone(state.snooze_until)
        self.assertIsNone(state.hold_started_at)
        self.assertTrue(state.sound_enabled)
        self.assertTrue(state.running)
        self.assertFalse(state.hint_dismissed)

    def test_numbers_are_clamped_to_the_allowed_range(self):
        for freq, dur, want_freq, want_dur in (
            (0, 0, MIN_FREQUENCY, MIN_DURATION),
            (-50, -1, MIN_FREQUENCY, MIN_DURATION),
            (10**9, 10**9, MAX_FREQUENCY, MAX_DURATION),
            ("15", "3", 15, 3),
            (12.9, 4.2, 12, 4),
        ):
            with self.subTest(freq=freq, dur=dur):
                item = reminder_from_dict(
                    {"name": "x", "frequency_minutes": freq, "duration_minutes": dur}, START
                )
                self.assertEqual((item.frequency_minutes, item.duration_minutes), (want_freq, want_dur))

    def test_infinite_and_nan_times_are_discarded(self):
        for bad in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(bad=bad):
                item = reminder_from_dict({"name": "x", "frequency_minutes": 10, "next_due": bad}, START)
                self.assertTrue(math.isfinite(item.next_due))
                self.assertAlmostEqual(item.next_due, START + 600)

    def test_names_are_collapsed_and_cut_to_forty_characters(self):
        item = reminder_from_dict({"name": "  a   b\n c  " + "z" * 80}, START)
        self.assertEqual(item.name, ("a b c " + "z" * 80)[:40])
        self.assertLessEqual(len(item.name), 40)

    def test_colors_must_be_a_hash_and_six_hex_digits(self):
        for given, expected in (
            ("#ABCDEF", "#abcdef"),
            ("#12345", None),
            ("123456", None),
            ("#12345g", None),
            ("#1234567", None),
            ("#+12345", None),
            ("#-12345", None),
            ("# 12345", None),
            ("#12345\n", None),
            (None, None),
        ):
            with self.subTest(given=given):
                item = reminder_from_dict({"name": "x", "kind": "walk", "color": given}, START)
                self.assertEqual(item.color, expected or "#1f9d62")

    def test_duplicate_ids_are_made_unique(self):
        raw = {"reminders": [{"id": "a", "name": "1"}, {"id": "a", "name": "2"}, {"id": "a", "name": "3"}]}
        state = state_from_dict(raw, START)
        self.assertEqual(len({item.id for item in state.reminders}), 3)

    def test_unknown_kind_becomes_the_generic_animation(self):
        item = reminder_from_dict({"name": "x", "kind": "dance"}, START)
        self.assertEqual(item.kind, "bounce")


class SaveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "nested" / "dir" / "state.json"

    def test_save_creates_folders_and_leaves_no_temporary_file(self):
        state, _ = load_state(self.path, START)
        save_state(self.path, state)
        self.assertTrue(self.path.exists())
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["state.json"])

    def test_saved_file_is_valid_json_with_every_reminder(self):
        state, _ = load_state(self.path, START)
        save_state(self.path, state)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["reminders"]), 4)
        for key in ("id", "name", "kind", "frequency_minutes", "duration_minutes", "enabled", "next_due", "color", "sound"):
            self.assertIn(key, data["reminders"][0])

    def test_roundtrip_keeps_every_field(self):
        state, _ = load_state(self.path, START)
        state.reminders.append(Reminder.create("Café ☕ break", "rest", 33, 7, "#0f8a8a", START, enabled=False))
        state.snooze_until = START + 100
        state.hold_started_at = START + 5
        state.sound_enabled = False
        state.running = False
        state.hint_dismissed = True
        save_state(self.path, state)
        loaded, created = load_state(self.path, START + 999)
        self.assertFalse(created)
        self.assertEqual(loaded.to_dict(), state.to_dict())

    def test_a_chosen_sound_survives_saving_and_loading(self):
        state, _ = load_state(self.path, START)
        state.reminders[0].sound = "Hero"
        state.reminders[1].sound = "none"
        save_state(self.path, state)
        loaded, _ = load_state(self.path, START)
        self.assertEqual([r.sound for r in loaded.reminders], ["Hero", "none", "auto", "auto"])

    def test_an_added_sound_survives_saving_and_loading(self):
        state, _ = load_state(self.path, START)
        state.reminders[0].sound = "custom:Door Bell (2).wav"
        save_state(self.path, state)
        loaded, _ = load_state(self.path, START)
        self.assertEqual(loaded.reminders[0].sound, "custom:Door Bell (2).wav")

    def test_files_saved_before_sounds_existed_still_load(self):
        state, _ = load_state(self.path, START)
        data = state.to_dict()
        for item in data["reminders"]:
            del item["sound"]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
        loaded, created = load_state(self.path, START)
        self.assertFalse(created)
        self.assertEqual({r.sound for r in loaded.reminders}, {"auto"})

    def test_a_damaged_sound_value_falls_back_to_auto_without_losing_the_reminder(self):
        state, _ = load_state(self.path, START)
        data = state.to_dict()
        bad = [None, 7, ["Glass"], "", "glass", "NoSuchSound", "../../etc/passwd", "/System/Library/Sounds/Glass.aiff",
               "custom:../x.wav", "custom:a/b.wav", "custom:a\\b.wav", "custom:", "custom:.wav",
               "custom:x.exe", "custom:" + "a" * 90 + ".wav"]
        data["reminders"] = [dict(data["reminders"][0], id=f"r{i}", sound=value) for i, value in enumerate(bad)]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
        loaded, created = load_state(self.path, START)
        self.assertFalse(created)
        self.assertEqual(len(loaded.reminders), len(bad))
        self.assertEqual({r.sound for r in loaded.reminders}, {"auto"})

    def test_the_default_location_is_inside_the_project(self):
        path = default_state_path()
        self.assertEqual(path.name, "state.json")
        self.assertEqual(path.parent.name, "data")
        self.assertTrue((path.parent.parent / "main.py").exists())


class LockTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "nudge.lock"

    def test_second_holder_is_refused_until_the_first_lets_go(self):
        first, second = ProcessLock(self.path), ProcessLock(self.path)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        first.release()
        self.assertFalse(self.path.exists())
        self.assertTrue(second.acquire())
        second.release()

    def test_lock_records_the_owning_process(self):
        lock = ProcessLock(self.path)
        lock.acquire()
        self.assertEqual(int(self.path.read_text()), os.getpid())
        lock.release()

    def test_a_lock_left_by_a_dead_process_is_taken_over(self):
        dead = 99_999_999
        try:
            os.kill(dead, 0)
        except OSError:
            pass
        else:
            self.skipTest("unexpectedly live pid")
        self.path.write_text(str(dead))
        lock = ProcessLock(self.path)
        self.assertTrue(lock.acquire())
        lock.release()

    def test_garbage_in_the_lock_file_counts_as_stale(self):
        for content in ("", "abc", "-4", "0", "1.5"):
            with self.subTest(content=content):
                self.path.write_text(content)
                lock = ProcessLock(self.path)
                self.assertTrue(lock.acquire())
                lock.release()

    def test_release_does_not_remove_someone_elses_lock(self):
        lock = ProcessLock(self.path)
        self.assertTrue(lock.acquire())
        self.path.write_text(str(os.getpid() + 1))
        lock.release()
        self.assertTrue(self.path.exists())

    def test_release_without_acquire_is_harmless(self):
        ProcessLock(self.path).release()
        self.assertFalse(self.path.exists())

    def test_release_twice_is_harmless(self):
        lock = ProcessLock(self.path)
        lock.acquire()
        lock.release()
        lock.release()


class PidCheckTests(unittest.TestCase):
    def test_this_process_is_running_and_nonsense_ids_are_not(self):
        from nudge.storage import pid_is_running
        self.assertTrue(pid_is_running(os.getpid()))
        for bad in (0, -1, -12345):
            self.assertFalse(pid_is_running(bad))

    def test_a_process_we_may_not_signal_still_counts_as_running(self):
        from nudge.storage import pid_is_running
        with mock.patch("os.name", "posix"), mock.patch("os.kill", side_effect=PermissionError()):
            self.assertTrue(pid_is_running(4242))

    def test_a_missing_process_is_not_running(self):
        from nudge.storage import pid_is_running
        for error in (ProcessLookupError(), OSError("odd")):
            with mock.patch("os.name", "posix"), mock.patch("os.kill", side_effect=error):
                self.assertFalse(pid_is_running(4242))

    def test_windows_never_calls_kill_because_there_it_ends_the_process(self):
        from nudge import storage
        with mock.patch("os.name", "nt"), \
                mock.patch("os.kill") as kill, \
                mock.patch.object(storage, "_windows_pid_is_running", return_value=True) as check:
            self.assertTrue(storage.pid_is_running(4242))
        self.assertFalse(kill.called, "os.kill(pid, 0) would terminate the other Nudge on Windows")
        check.assert_called_once_with(4242)

    def test_windows_answers_false_when_the_system_call_is_unavailable(self):
        from nudge import storage
        with mock.patch("os.name", "nt"), \
                mock.patch("os.kill") as kill, \
                mock.patch.object(storage, "_windows_pid_is_running", side_effect=AttributeError("no windll")):
            self.assertFalse(storage.pid_is_running(4242))
        self.assertFalse(kill.called)

    def test_the_lock_uses_the_safe_check(self):
        from nudge import storage
        with tempfile.TemporaryDirectory() as folder:
            lock_path = Path(folder) / "nudge.lock"
            lock_path.write_text("4242", encoding="utf-8")
            with mock.patch.object(storage, "pid_is_running", return_value=True) as check:
                self.assertFalse(storage.ProcessLock(lock_path).acquire())
            check.assert_called_once_with(4242)


if __name__ == "__main__":
    unittest.main()
