"""The alarm chime must never raise, whatever the platform."""

import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import helpers

from nudge import models, sound
from nudge import sound as sound_module
from nudge.models import KIND_ORDER

assert helpers.START  # importing helpers puts the project on sys.path


class SoundsFolderCase(unittest.TestCase):
    """Gives each test its own empty sounds folder, so nothing touches the real one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "sounds"
        patcher = mock.patch.dict(os.environ, {"NUDGE_SOUNDS_DIR": str(self.folder)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(sound_module.stop)

    def make_file(self, name="ding.wav", data=b"RIFF....WAVEfmt ", where=None):
        folder = Path(where or self._tmp.name)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(data)
        return path


class ChimeTests(SoundsFolderCase):
    def test_every_animation_has_its_own_mac_sound(self):
        self.assertEqual(set(sound._MAC_SOUNDS), set(KIND_ORDER))
        self.assertEqual(len(set(sound._MAC_SOUNDS.values())), len(KIND_ORDER))

    def test_mac_plays_the_matching_file_quietly(self):
        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("os.path.exists", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            sound.play_chime("walk")
        command = popen.call_args[0][0]
        self.assertEqual(command[0], "afplay")
        self.assertIn("-v", command)
        self.assertEqual(command[-1], sound._MAC_SOUNDS["walk"])

    def test_unknown_animation_falls_back_to_the_generic_sound(self):
        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("os.path.exists", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            sound.play_chime("unicorn")
        self.assertEqual(popen.call_args[0][0][-1], sound._MAC_SOUNDS["bounce"])

    def test_mac_without_the_sound_file_uses_the_system_beep(self):
        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("os.path.exists", return_value=False), \
                mock.patch("subprocess.Popen") as popen:
            sound.play_chime("water")
        self.assertEqual(popen.call_args[0][0][0], "osascript")

    def test_windows_uses_the_system_chime(self):
        fake = types.SimpleNamespace(MessageBeep=mock.Mock(), MB_ICONASTERISK=64)
        with mock.patch("platform.system", return_value="Windows"), \
                mock.patch.dict(sys.modules, {"winsound": fake}):
            sound.play_chime("water")
        fake.MessageBeep.assert_called_once_with(64)

    def test_linux_tries_the_desktop_bell(self):
        with mock.patch("platform.system", return_value="Linux"), \
                mock.patch("subprocess.Popen") as popen:
            sound.play_chime("water")
        self.assertEqual(popen.call_args[0][0][0], "paplay")

    def test_a_missing_player_never_raises_and_falls_back_to_the_terminal_bell(self):
        for system in ("Darwin", "Linux", "Windows"):
            with self.subTest(system=system):
                out = io.StringIO()
                with mock.patch("platform.system", return_value=system), \
                        mock.patch("subprocess.Popen", side_effect=FileNotFoundError("no player")), \
                        mock.patch.dict(sys.modules, {"winsound": None}), \
                        mock.patch("sys.stdout", out):
                    sound.play_chime("water")
                self.assertIn("\a", out.getvalue())

    def test_a_broken_terminal_is_also_survived(self):
        broken = mock.Mock()
        broken.write.side_effect = OSError("closed")
        with mock.patch("platform.system", return_value="Linux"), \
                mock.patch("subprocess.Popen", side_effect=OSError("nope")), \
                mock.patch("sys.stdout", broken):
            sound.play_chime("water")


class ChosenSoundTests(SoundsFolderCase):
    def play(self, sound, kind="water", system="Darwin", exists=True):
        with mock.patch("platform.system", return_value=system), \
                mock.patch("os.path.exists", return_value=exists), \
                mock.patch("subprocess.Popen") as popen:
            sound_module.play_chime(kind, sound)
        return popen

    def test_a_chosen_system_sound_replaces_the_animation_sound(self):
        popen = self.play("Hero", kind="water")
        self.assertEqual(popen.call_args[0][0][-1], "/System/Library/Sounds/Hero.aiff")
        self.assertEqual(popen.call_args[0][0][0], "afplay")

    def test_every_listed_system_sound_plays_its_own_file(self):
        for name in models.MAC_SOUND_NAMES:
            with self.subTest(name=name):
                self.assertEqual(self.play(name).call_args[0][0][-1], f"/System/Library/Sounds/{name}.aiff")

    def test_silent_plays_nothing_on_any_system(self):
        for system in ("Darwin", "Linux", "Windows"):
            with self.subTest(system=system):
                self.assertFalse(self.play("none", system=system).called)

    def test_silent_does_not_even_fall_back_to_the_terminal_bell(self):
        out = io.StringIO()
        with mock.patch("platform.system", return_value="Linux"), \
                mock.patch("subprocess.Popen", side_effect=OSError("nope")), \
                mock.patch("sys.stdout", out):
            sound_module.play_chime("water", "none")
        self.assertEqual(out.getvalue(), "")

    def test_auto_keeps_the_per_animation_sound(self):
        for kind in KIND_ORDER:
            with self.subTest(kind=kind):
                self.assertEqual(self.play("auto", kind=kind).call_args[0][0][-1], sound_module._MAC_SOUNDS[kind])

    def test_an_unknown_or_hostile_name_is_never_used_as_a_path(self):
        for bad in ("NoSuchSound", "../../etc/passwd", "/etc/passwd", "", None, 5, "glass"):
            with self.subTest(bad=bad):
                popen = self.play(bad, kind="walk")
                self.assertEqual(popen.call_args[0][0][-1], sound_module._MAC_SOUNDS["walk"])

    def test_a_chosen_sound_whose_file_is_missing_falls_back_to_the_animation_sound(self):
        def only_default(path):
            return path == sound_module._MAC_SOUNDS["stretch"]

        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("os.path.exists", side_effect=only_default), \
                mock.patch("subprocess.Popen") as popen:
            sound_module.play_chime("stretch", "Hero")
        self.assertEqual(popen.call_args[0][0][-1], sound_module._MAC_SOUNDS["stretch"])

    def test_other_systems_ignore_the_mac_names_but_still_make_a_sound(self):
        self.assertEqual(self.play("Hero", system="Linux").call_args[0][0][0], "paplay")
        fake = types.SimpleNamespace(MessageBeep=mock.Mock(), MB_ICONASTERISK=64)
        with mock.patch("platform.system", return_value="Windows"), \
                mock.patch.dict(sys.modules, {"winsound": fake}):
            sound_module.play_chime("water", "Hero")
        fake.MessageBeep.assert_called_once_with(64)


class ChoiceListTests(SoundsFolderCase):
    def values(self, system, current="auto", exists=True):
        with mock.patch("platform.system", return_value=system), \
                mock.patch("os.path.exists", return_value=exists):
            return sound_module.sound_choices(current)

    def test_mac_offers_auto_silent_and_every_system_sound(self):
        choices = self.values("Darwin")
        self.assertEqual([v for v, _ in choices][:2], ["auto", "none"])
        self.assertEqual([v for v, _ in choices][2:-1], list(models.MAC_SOUND_NAMES))
        self.assertEqual(choices[-1], (sound_module.SOUND_ADD, sound_module.ADD_LABEL))
        self.assertEqual(len({label for _, label in choices}), len(choices), "labels must be unique")

    def test_mac_skips_sounds_that_are_not_installed(self):
        self.assertEqual([v for v, _ in self.values("Darwin", exists=False)], ["auto", "none", "__add__"])

    def test_other_systems_only_offer_auto_and_silent(self):
        for system in ("Linux", "Windows"):
            self.assertEqual([v for v, _ in self.values(system)], ["auto", "none", "__add__"])

    def test_a_saved_choice_this_computer_cannot_play_is_still_listed(self):
        choices = dict(self.values("Linux", current="Hero"))
        self.assertIn("Hero", choices)
        self.assertIn("not available", choices["Hero"])

    def test_every_choice_the_picker_can_save_is_accepted_by_storage(self):
        for value, _label in self.values("Darwin"):
            if value != sound_module.SOUND_ADD:
                self.assertTrue(models.is_valid_sound(value), value)


class AddingSoundsTests(SoundsFolderCase):
    def test_adding_copies_the_file_and_returns_its_value(self):
        source = self.make_file("Door Bell.wav", b"abc")
        value = sound_module.add_custom_sound(source)
        self.assertEqual(value, "custom:Door Bell.wav")
        self.assertEqual((self.folder / "Door Bell.wav").read_bytes(), b"abc")
        self.assertTrue(models.is_valid_sound(value))

    def test_the_copy_keeps_working_after_the_original_is_gone(self):
        source = self.make_file("ding.wav")
        value = sound_module.add_custom_sound(source)
        source.unlink()
        self.assertIn(value, sound_module.custom_sounds())
        self.assertIsNotNone(sound_module._custom_path(value))

    def test_adding_the_same_file_twice_does_not_make_a_duplicate(self):
        source = self.make_file("ding.wav", b"same")
        first = sound_module.add_custom_sound(source)
        second = sound_module.add_custom_sound(source)
        self.assertEqual(first, second)
        self.assertEqual(len(os.listdir(self.folder)), 1)

    def test_a_different_file_with_the_same_name_gets_a_new_name(self):
        first = sound_module.add_custom_sound(self.make_file("ding.wav", b"one"))
        second = sound_module.add_custom_sound(self.make_file("ding.wav", b"two", where=Path(self._tmp.name) / "other"))
        self.assertNotEqual(first, second)
        self.assertEqual(second, "custom:ding 2.wav")
        self.assertEqual((self.folder / "ding.wav").read_bytes(), b"one", "the first sound is never overwritten")

    def test_awkward_file_names_are_made_safe(self):
        for raw in ("sound<>:*?.wav", "  ..spaced..  .wav", "ünï côdé.wav", "a" * 200 + ".wav", "...wav"):
            with self.subTest(raw=raw):
                value = sound_module.add_custom_sound(self.make_file(raw))
                self.assertTrue(models.is_valid_sound(value), value)
                self.assertTrue((self.folder / value[len("custom:"):]).is_file())
                self.assertEqual(Path(value[len("custom:"):]).name, value[len("custom:"):])

    def test_upper_case_extensions_are_fine(self):
        with mock.patch("platform.system", return_value="Darwin"):
            value = sound_module.add_custom_sound(self.make_file("LOUD.MP3"))
        self.assertEqual(value, "custom:LOUD.mp3")

    def test_unsupported_files_are_refused_with_a_plain_message(self):
        with mock.patch("platform.system", return_value="Darwin"):
            with self.assertRaises(sound_module.SoundImportError) as caught:
                sound_module.add_custom_sound(self.make_file("song.exe"))
        self.assertIn("WAV", str(caught.exception))
        self.assertIn("MP3", str(caught.exception))
        self.assertFalse(self.folder.exists() and os.listdir(self.folder))

    def test_each_system_lists_only_formats_it_can_play(self):
        for system, expected, refused in (("Windows", "wav", "mp3"), ("Linux", "ogg", "mp3"), ("Darwin", "m4a", "ogg")):
            with self.subTest(system=system), mock.patch("platform.system", return_value=system):
                self.assertIn(expected, sound_module.supported_extensions())
                self.assertNotIn(refused, sound_module.supported_extensions())
                with self.assertRaises(sound_module.SoundImportError):
                    sound_module.add_custom_sound(self.make_file("x." + refused))

    def test_missing_empty_and_huge_files_are_refused(self):
        with self.assertRaises(sound_module.SoundImportError):
            sound_module.add_custom_sound(Path(self._tmp.name) / "nope.wav")
        with self.assertRaises(sound_module.SoundImportError):
            sound_module.add_custom_sound(self.make_file("empty.wav", b""))
        with self.assertRaises(sound_module.SoundImportError) as caught:
            sound_module.add_custom_sound(self.make_file("long.wav", b"x" * (sound_module.MAX_SOUND_BYTES + 1)))
        self.assertIn("too long", str(caught.exception))
        with self.assertRaises(sound_module.SoundImportError):
            sound_module.add_custom_sound(self._tmp.name)

    def test_a_folder_that_cannot_be_written_gives_a_friendly_error(self):
        source = self.make_file("ding.wav")
        with mock.patch("pathlib.Path.mkdir", side_effect=OSError("read-only")):
            with self.assertRaises(sound_module.SoundImportError):
                sound_module.add_custom_sound(source)

    def test_added_sounds_appear_in_the_picker_by_a_friendly_name(self):
        sound_module.add_custom_sound(self.make_file("Door Bell.wav"))
        with mock.patch("platform.system", return_value="Linux"):
            choices = sound_module.sound_choices("auto")
        self.assertIn(("custom:Door Bell.wav", "Door Bell (yours)"), choices)
        self.assertEqual(choices[-1][0], "__add__")

    def test_sounds_this_computer_cannot_play_are_not_offered(self):
        (self.folder).mkdir(parents=True)
        for name in ("a.wav", "b.mp3", "notes.txt"):
            (self.folder / name).write_bytes(b"x")
        with mock.patch("platform.system", return_value="Windows"):
            self.assertEqual(sound_module.custom_sounds(), ["custom:a.wav"])

    def test_a_missing_folder_just_means_no_added_sounds(self):
        self.assertEqual(sound_module.custom_sounds(), [])

    def test_removing_a_sound_deletes_only_that_file(self):
        keep = sound_module.add_custom_sound(self.make_file("keep.wav", b"1"))
        drop = sound_module.add_custom_sound(self.make_file("drop.wav", b"2"))
        self.assertTrue(sound_module.remove_custom_sound(drop))
        self.assertEqual(sound_module.custom_sounds(), [keep])
        self.assertFalse(sound_module.remove_custom_sound(drop))
        self.assertFalse(sound_module.remove_custom_sound("custom:../../outside.wav"))
        self.assertFalse(sound_module.remove_custom_sound("Hero"))

    def test_a_saved_sound_that_was_deleted_is_still_listed_and_still_safe_to_play(self):
        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("os.path.exists", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            sound_module.play_chime("walk", "custom:gone.wav")
        self.assertEqual(popen.call_args[0][0][-1], sound_module._MAC_SOUNDS["walk"])
        with mock.patch("platform.system", return_value="Linux"):
            labels = dict(sound_module.sound_choices("custom:gone.wav"))
        self.assertIn("not available", labels["custom:gone.wav"])


class PlayingAddedSoundsTests(SoundsFolderCase):
    def added(self, name="ding.wav"):
        return sound_module.add_custom_sound(self.make_file(name))

    def test_mac_plays_the_added_file_and_caps_its_length(self):
        value = self.added()
        with mock.patch("platform.system", return_value="Darwin"), \
                mock.patch("subprocess.Popen") as popen:
            sound_module.play_chime("water", value)
        command = popen.call_args[0][0]
        self.assertEqual(command[0], "afplay")
        self.assertEqual(command[-1], str(self.folder / "ding.wav"))
        self.assertIn("-t", command)

    def test_windows_plays_added_wav_files_without_blocking(self):
        value = self.added()
        fake = types.SimpleNamespace(PlaySound=mock.Mock(), MessageBeep=mock.Mock(), MB_ICONASTERISK=64,
                                     SND_FILENAME=2, SND_ASYNC=1)
        with mock.patch("platform.system", return_value="Windows"), \
                mock.patch.dict(sys.modules, {"winsound": fake}):
            sound_module.play_chime("water", value)
        fake.PlaySound.assert_called_once_with(str(self.folder / "ding.wav"), 3)
        self.assertFalse(fake.MessageBeep.called)

    def test_windows_falls_back_to_the_system_chime_for_other_formats(self):
        self.folder.mkdir(parents=True)
        (self.folder / "song.mp3").write_bytes(b"x")
        fake = types.SimpleNamespace(PlaySound=mock.Mock(), MessageBeep=mock.Mock(), MB_ICONASTERISK=64,
                                     SND_FILENAME=2, SND_ASYNC=1)
        with mock.patch("platform.system", return_value="Windows"), \
                mock.patch.dict(sys.modules, {"winsound": fake}):
            sound_module.play_chime("water", "custom:song.mp3")
        self.assertFalse(fake.PlaySound.called)
        fake.MessageBeep.assert_called_once_with(64)

    def test_linux_plays_the_added_file(self):
        value = self.added()
        with mock.patch("platform.system", return_value="Linux"), mock.patch("subprocess.Popen") as popen:
            sound_module.play_chime("water", value)
        self.assertEqual(popen.call_args[0][0], ["paplay", str(self.folder / "ding.wav")])

    def test_a_new_sound_replaces_the_one_still_playing(self):
        value = self.added()
        first, second = mock.Mock(), mock.Mock()
        with mock.patch("platform.system", return_value="Linux"), \
                mock.patch("subprocess.Popen", side_effect=[first, second]):
            sound_module.play_chime("water", value)
            sound_module.play_chime("water", value)
        first.terminate.assert_called_once()
        self.assertFalse(second.terminate.called)
        sound_module.stop()
        second.terminate.assert_called_once()

    def test_stopping_when_nothing_plays_is_harmless(self):
        sound_module.stop()
        sound_module.stop()

    def test_a_player_that_already_finished_does_not_break_the_next_sound(self):
        value = self.added()
        finished = mock.Mock()
        finished.terminate.side_effect = ProcessLookupError("gone")
        with mock.patch("platform.system", return_value="Linux"), \
                mock.patch("subprocess.Popen", side_effect=[finished, mock.Mock()]) as popen:
            sound_module.play_chime("water", value)
            sound_module.play_chime("water", value)
        self.assertEqual(popen.call_count, 2)

    def test_a_hostile_value_never_reaches_the_file_system(self):
        outside = self.make_file("secret.wav", b"x", where=Path(self._tmp.name) / "outside")
        for bad in ("custom:../outside/secret.wav", "custom:" + str(outside), "custom:..\\outside\\secret.wav"):
            with self.subTest(bad=bad):
                self.assertIsNone(sound_module._custom_path(bad))


if __name__ == "__main__":
    unittest.main()
