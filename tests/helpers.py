"""Shared test tools: a fake clock and a base class that opens the real window.

Run the suite from the project root:

    python3 -m unittest discover -s tests

Window tests need a display and a Python with Tk. They are skipped when Tk
cannot start.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk  # noqa: E402

from nudge.app import NudgeApp  # noqa: E402
from nudge.models import default_state  # noqa: E402
from nudge.storage import load_state, save_state  # noqa: E402

START = 1_700_000_000.0


def _tk_works():
    """Ask a separate process, so a failure there cannot take the tests down.

    (On macOS, Tk 9 can crash a process that destroys a window it never drew,
    so this probe must not create a throwaway window in the test process.)
    """
    probe = "import tkinter; r = tkinter.Tk(); r.withdraw(); r.update_idletasks(); r.destroy()"
    flags = ["-ApplePersistenceIgnoreState", "YES"] if sys.platform == "darwin" else []
    try:
        result = subprocess.run(
            [sys.executable, "-c", probe] + flags,
            capture_output=True,
            timeout=30,
            env=dict(os.environ, TK_SILENCE_DEPRECATION="1"),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


HAS_TK = _tk_works()
needs_tk = unittest.skipUnless(HAS_TK, "Tk is not available here")


class FakeClock(object):
    def __init__(self, start=START):
        self.t = float(start)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def write_state(path, mutate=None, now=START):
    state = default_state(now)
    if mutate is not None:
        mutate(state)
    save_state(path, state)
    return state


def read_state(path, now=START):
    state, created = load_state(path, now)
    assert not created, "expected a saved state file"
    return state


@needs_tk
class GuiCase(unittest.TestCase):
    """Opens the real app window with a fake clock and a recording sound player."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "state.json"
        # Sounds added during a test go into the temporary folder, never into the real app.
        self.sounds_dir = Path(self._tmp.name) / "sounds"
        patcher = mock.patch.dict(os.environ, {"NUDGE_SOUNDS_DIR": str(self.sounds_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.clock = FakeClock()
        self.played, self.played_sounds = [], []
        self.root = None
        self.app = None
        self.addCleanup(self._teardown)

    def _record_sound(self, kind, sound="auto"):
        """Stands in for the speaker: `played` lists animations, `played_sounds` the chosen sounds."""
        self.played.append(kind)
        self.played_sounds.append(sound)

    def _teardown(self):
        app = self.app
        if app is not None:
            app._alive = False
            if app.overlay is not None:
                app.overlay.alive = False
        if self.root is not None:
            try:
                self.root.update_idletasks()
                self.root.destroy()
            except tk.TclError:
                pass

    def new_root(self):
        """A hidden window that has been drawn once.

        (Tk 9 on macOS can crash the next window if one is destroyed before it
        was ever drawn, so every test window gets an idle pass first.)
        """
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.update_idletasks()
        return self.root

    def launch(self, mutate=None, saved=None):
        """Start the app. `mutate` edits a fresh default state first."""
        if mutate is not None or saved is not None:
            write_state(self.path, mutate)
        self.new_root()
        self.app = NudgeApp(
            self.root,
            self.path,
            now=self.clock,
            player=self._record_sound,
        )
        self.root.update_idletasks()
        return self.app

    def relaunch(self):
        """Quit and start again from the saved file, like closing and reopening."""
        self.app.close()
        self.played, self.played_sounds = [], []
        return self.launch()

    def reminder(self, name):
        for item in self.app.state.reminders:
            if item.name == name:
                return item
        raise AssertionError("no reminder named %r" % name)

    def saved(self):
        return read_state(self.path)

    def only(self, name):
        """Switch every reminder off except one, so nothing else interrupts the test."""
        target = self.reminder(name)
        for item in self.app.state.reminders:
            item.enabled = item is target
        return target

    def tick_at(self, moment):
        """Jump the clock and tick once, as if the app had been ticking all along.

        The app ticks every second for real, so a long jump here must not look
        like the computer waking from sleep. Use `wake_at` to test that.
        """
        self.clock.t = float(moment)
        self.app._last_tick = self.clock.t - 1
        self.app.tick()
        self.root.update_idletasks()

    def wake_at(self, moment):
        """Jump the clock and tick once, as after the computer slept."""
        self.clock.t = float(moment)
        self.app.tick()
        self.root.update_idletasks()

    def fire(self, reminder):
        """Move the clock just past a reminder's due time and let the app tick."""
        self.tick_at(max(self.clock.t, reminder.next_due + 1))

    def reset(self):
        """Throw the current app away and start over with a fresh file and clock."""
        self._teardown()
        if self.path.exists():
            self.path.unlink()
        self.clock = type(self.clock)()
        self.played, self.played_sounds = [], []
        self.root = None
        self.app = None

    def to_prompt(self):
        overlay = self.app.overlay
        assert overlay is not None, "no alarm is on screen"
        overlay.elapsed = 6.0
        overlay._advance()
        assert overlay.phase == "prompt", overlay.phase
        return overlay

    def fill(self, dialog, name=None, freq=None, dur=None):
        for entry, value in (
            (dialog.name_entry, name),
            (dialog.freq_entry, freq),
            (dialog.dur_entry, dur),
        ):
            if value is not None:
                entry.delete(0, "end")
                entry.insert(0, str(value))
