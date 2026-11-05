"""Alarm sounds: the built-in ones, the ones people add, and playing them. Never raises."""

import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from nudge.models import (
    CUSTOM_PREFIX,
    MAC_SOUND_NAMES,
    SOUND_AUTO,
    SOUND_NONE,
    is_valid_sound,
)

MAC_SOUND_DIR = "/System/Library/Sounds"

# What each animation plays when its reminder is set to "Matches the animation".
_MAC_SOUNDS = {
    "water": MAC_SOUND_DIR + "/Submarine.aiff",
    "rest": MAC_SOUND_DIR + "/Blow.aiff",
    "walk": MAC_SOUND_DIR + "/Tink.aiff",
    "stretch": MAC_SOUND_DIR + "/Glass.aiff",
    "bounce": MAC_SOUND_DIR + "/Pop.aiff",
}

# Not a real sound: the last entry in the picker, which opens the file chooser.
SOUND_ADD = "__add__"
ADD_LABEL = "Add your own sound…"

MAX_SOUND_BYTES = 5 * 1024 * 1024
MAC_MAX_SECONDS = 10

# What each system can play without installing anything extra.
_EXTENSIONS = {
    "Darwin": ("wav", "mp3", "aiff", "aif", "m4a"),
    "Windows": ("wav",),
    "Linux": ("wav", "ogg", "oga", "flac"),
}

_playing = None


class SoundImportError(Exception):
    """The chosen file cannot be used. The message is written for the person who picked it."""


def sounds_folder():
    """Where added sounds are kept: next to the reminders, so they travel together."""
    override = os.environ.get("NUDGE_SOUNDS_DIR")
    if override:
        return Path(override)
    from nudge.storage import default_state_path

    return default_state_path().parent / "sounds"


def supported_extensions(system=None):
    return _EXTENSIONS.get(system or platform.system(), _EXTENSIONS["Linux"])


def _readable_formats(system=None):
    return ", ".join(e.upper() for e in supported_extensions(system))


def _label_for(value):
    return Path(value[len(CUSTOM_PREFIX):]).stem


def custom_sounds():
    """Values of every sound the person has added that this computer can play."""
    folder = sounds_folder()
    allowed = supported_extensions()
    try:
        names = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return []
    found = []
    for name in names:
        value = CUSTOM_PREFIX + name
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension in allowed and is_valid_sound(value) and (folder / name).is_file():
            found.append(value)
    return found


def _custom_path(value):
    """The file behind a "custom:" value, or None. Never follows anything outside the folder."""
    if not isinstance(value, str) or not value.startswith(CUSTOM_PREFIX) or not is_valid_sound(value):
        return None
    path = sounds_folder() / value[len(CUSTOM_PREFIX):]
    return path if path.is_file() else None


def _clean_stem(stem):
    stem = re.sub(r"[^\w .()'\-]", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return (stem or "My sound")[:60]


def add_custom_sound(source):
    """Copy a sound file into the app and return its value. Raises SoundImportError."""
    source = Path(str(source))
    if not source.is_file():
        raise SoundImportError("That file could not be found.")
    extension = source.suffix.lower().lstrip(".")
    if extension not in supported_extensions():
        raise SoundImportError(
            f"Nudge can play {_readable_formats()} files on this computer. "
            "Please choose one of those."
        )
    try:
        size = source.stat().st_size
    except OSError:
        raise SoundImportError("That file could not be read.")
    if size == 0:
        raise SoundImportError("That file is empty.")
    if size > MAX_SOUND_BYTES:
        raise SoundImportError("That sound is too long. Please choose one that lasts a few seconds.")
    folder = sounds_folder()
    stem = _clean_stem(source.stem)
    name = f"{stem}.{extension}"
    number = 1
    try:
        data = source.read_bytes()
        folder.mkdir(parents=True, exist_ok=True)
        while (folder / name).exists() and (folder / name).read_bytes() != data:
            number += 1
            name = f"{stem} {number}.{extension}"
        (folder / name).write_bytes(data)
    except OSError:
        raise SoundImportError("Nudge could not save that sound. Please try another file.")
    return CUSTOM_PREFIX + name


def remove_custom_sound(value):
    """Delete an added sound. Returns True when a file was removed."""
    path = _custom_path(value)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _mac_path(name):
    """The file for a system sound name. Only known names are accepted, never a raw path."""
    if name in MAC_SOUND_NAMES:
        return f"{MAC_SOUND_DIR}/{name}.aiff"
    return None


def sound_choices(current=SOUND_AUTO):
    """(value, label) pairs for the sound picker, in display order.

    System sounds are only offered where they exist. A saved choice that this
    computer cannot play is still listed, so editing a reminder never loses it.
    The last entry always opens the file chooser.
    """
    choices = [(SOUND_AUTO, "Matches the animation"), (SOUND_NONE, "Silent")]
    if platform.system() == "Darwin":
        for name in MAC_SOUND_NAMES:
            if os.path.exists(_mac_path(name)):
                choices.append((name, name))
    for value in custom_sounds():
        choices.append((value, f"{_label_for(value)} (yours)"))
    if current not in [value for value, _label in choices]:
        label = _label_for(current) if str(current).startswith(CUSTOM_PREFIX) else current
        choices.append((current, f"{label} (not available here)"))
    choices.append((SOUND_ADD, ADD_LABEL))
    return choices


def stop():
    """Stop the sound that is playing, if any."""
    global _playing
    process, _playing = _playing, None
    if process is not None:
        try:
            process.terminate()
        except (OSError, AttributeError):
            pass


def _launch(command):
    global _playing
    _playing = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def play_chime(kind, sound=SOUND_AUTO):
    """Play the sound chosen for a reminder; `kind` decides when the choice is "auto"."""
    if sound == SOUND_NONE:
        return
    try:
        stop()
        system = platform.system()
        custom = _custom_path(sound)
        if system == "Darwin":
            fallback = _MAC_SOUNDS.get(kind) or _MAC_SOUNDS["bounce"]
            path = str(custom) if custom else (_mac_path(sound) or fallback)
            if not os.path.exists(path):
                path = fallback
            if os.path.exists(path):
                _launch(["afplay", "-v", "0.55", "-t", str(MAC_MAX_SECONDS), path])
                return
            _launch(["osascript", "-e", "beep"])
            return
        if system == "Windows":
            import winsound

            if custom is not None and custom.suffix.lower() == ".wav":
                winsound.PlaySound(str(custom), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            return
        if custom is not None:
            _launch(["paplay", str(custom)])
            return
        _launch(["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"])
    except (OSError, ImportError):
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except OSError:
            pass
