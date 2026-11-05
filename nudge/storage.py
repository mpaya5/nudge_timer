"""Load and save Nudge state, plus a single-instance lock."""

import json
import math
import os
import re
from pathlib import Path

from nudge.models import (
    KINDS,
    MAX_DURATION,
    MAX_FREQUENCY,
    MIN_DURATION,
    MIN_FREQUENCY,
    SOUND_AUTO,
    is_valid_sound,
    AppState,
    Reminder,
    default_state,
    new_id,
)


def default_state_path():
    return Path(__file__).resolve().parent.parent / "data" / "state.json"


def _as_int(value, default, lo, hi):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(lo, min(hi, number))


def _as_bool(value, default):
    if isinstance(value, bool):
        return value
    return default


def _as_optional_float(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _color(value, fallback):
    if isinstance(value, str) and _COLOR.fullmatch(value):
        return value.lower()
    return fallback


def _sound(value):
    if is_valid_sound(value):
        return value
    return SOUND_AUTO


def reminder_from_dict(raw, now):
    if not isinstance(raw, dict):
        raise ValueError("reminder must be an object")
    kind = raw.get("kind", "bounce")
    if not isinstance(kind, str) or kind not in KINDS:
        kind = "bounce"
    frequency = _as_int(raw.get("frequency_minutes", 30), 30, MIN_FREQUENCY, MAX_FREQUENCY)
    duration = _as_int(raw.get("duration_minutes", 2), 2, MIN_DURATION, MAX_DURATION)
    name = raw.get("name", "Reminder")
    if not isinstance(name, str) or not name.strip():
        name = "Reminder"
    name = " ".join(name.split())[:40]
    due = _as_optional_float(raw.get("next_due"))
    if due is None:
        due = now + frequency * 60
    reminder_id = raw.get("id")
    if not isinstance(reminder_id, str) or not reminder_id.strip():
        reminder_id = new_id()
    return Reminder(
        id=reminder_id,
        name=name,
        kind=kind,
        frequency_minutes=frequency,
        duration_minutes=duration,
        enabled=_as_bool(raw.get("enabled", True), True),
        next_due=due,
        color=_color(raw.get("color"), KINDS[kind]["color"]),
        sound=_sound(raw.get("sound")),
    )


def state_from_dict(raw, now):
    if not isinstance(raw, dict) or "reminders" not in raw:
        raise ValueError("incomplete state")
    reminder_raw = raw["reminders"]
    if not isinstance(reminder_raw, list):
        raise ValueError("reminders must be a list")
    reminders = []
    seen = set()
    for item in reminder_raw:
        reminder = reminder_from_dict(item, now)
        if reminder.id in seen:
            reminder.id = new_id()
        seen.add(reminder.id)
        reminders.append(reminder)
    return AppState(
        reminders=reminders,
        snooze_until=_as_optional_float(raw.get("snooze_until")),
        hold_started_at=_as_optional_float(raw.get("hold_started_at")),
        sound_enabled=_as_bool(raw.get("sound_enabled", True), True),
        running=_as_bool(raw.get("running", True), True),
        hint_dismissed=_as_bool(raw.get("hint_dismissed", False), False),
    )


def load_state(path, now):
    """Return (state, created). `created` is True when there was no usable file."""
    path = Path(path)
    if not path.exists():
        return default_state(now), True
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return state_from_dict(raw, now), False
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        broken = path.with_name(path.name + ".broken")
        try:
            path.replace(broken)
        except OSError:
            pass
        return default_state(now), True


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _windows_pid_is_running(pid):
    """Windows cannot use os.kill(pid, 0): there it would end the process instead of checking it."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return kernel32.GetLastError() == 5  # access denied: it exists, we just may not look
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_is_running(pid):
    """True when a process with this id exists. Never disturbs the process."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            return _windows_pid_is_running(pid)
        except (OSError, AttributeError, ImportError):
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class ProcessLock(object):
    """A lock file so two Nudge windows don't write the same state."""

    def __init__(self, path):
        self.path = Path(path)
        self.fd = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._owner_alive():
                    return False
                try:
                    self.path.unlink()
                except OSError:
                    return False
                continue
            os.write(self.fd, str(os.getpid()).encode("ascii"))
            return True
        return False

    def release(self):
        fd = self.fd
        self.fd = None
        if fd is None:
            return
        os.close(fd)
        try:
            current = int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        if current != os.getpid():
            return
        try:
            self.path.unlink()
        except OSError:
            pass

    def _owner_alive(self):
        try:
            pid = int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return False
        return pid_is_running(pid)
