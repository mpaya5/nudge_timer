"""Reminder data and the built-in break options."""

import re
import uuid
from dataclasses import dataclass, asdict
from typing import List, Optional


MIN_FREQUENCY = 1
MAX_FREQUENCY = 240
MIN_DURATION = 1
MAX_DURATION = 60
FREQUENCY_STEP = 5
DURATION_STEP = 1

SNOOZE_MINUTES = (5, 10, 15)
DEFAULT_SNOOZE = 10
MEETING_MINUTES = (15, 30, 60, 120)
MEETING_FROM_ALARM = 30
PROMPT_TIMEOUT = 300

KINDS = {
    "water": {"label": "Water", "color": "#2f80ed"},
    "rest": {"label": "Rest", "color": "#7c5cbf"},
    "walk": {"label": "Walk", "color": "#1f9d62"},
    "stretch": {"label": "Stretch", "color": "#e07a3d"},
    "bounce": {"label": "Bounce", "color": "#d6456a"},
}
KIND_ORDER = ["water", "rest", "walk", "stretch", "bounce"]

# Alarm sounds. "auto" follows the animation, "none" is silent for that reminder,
# and the rest are the standard macOS system sounds.
SOUND_AUTO = "auto"
SOUND_NONE = "none"
MAC_SOUND_NAMES = (
    "Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero",
    "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink",
)
VALID_SOUNDS = (SOUND_AUTO, SOUND_NONE) + MAC_SOUND_NAMES

# Sounds the person added themselves are stored as "custom:<file name>" and live in
# the app's own sounds folder. Only plain file names are accepted, never paths.
CUSTOM_PREFIX = "custom:"
SOUND_EXTENSIONS = ("wav", "mp3", "aiff", "aif", "m4a", "ogg", "oga", "flac")
_CUSTOM = re.compile(
    r"custom:(?![.])[\w .()'\-]{1,80}\.(?:" + "|".join(SOUND_EXTENSIONS) + ")",
    re.IGNORECASE,
)


def is_valid_sound(value):
    if not isinstance(value, str):
        return False
    if value in VALID_SOUNDS:
        return True
    return bool(_CUSTOM.fullmatch(value)) and ".." not in value


PALETTE = [
    "#2f80ed",
    "#7c5cbf",
    "#1f9d62",
    "#e07a3d",
    "#d6456a",
    "#0f8a8a",
    "#c9842a",
    "#3d6b4f",
]


def new_id():
    return uuid.uuid4().hex[:12]


@dataclass
class Reminder:
    id: str
    name: str
    kind: str
    frequency_minutes: int
    duration_minutes: int
    enabled: bool
    next_due: float
    color: str
    sound: str = SOUND_AUTO

    def to_dict(self):
        return asdict(self)

    @classmethod
    def create(cls, name, kind, frequency_minutes, duration_minutes, color, now, enabled=True,
               sound=SOUND_AUTO):
        return cls(
            id=new_id(),
            name=name,
            kind=kind,
            frequency_minutes=int(frequency_minutes),
            duration_minutes=int(duration_minutes),
            enabled=enabled,
            next_due=float(now) + int(frequency_minutes) * 60,
            color=color,
            sound=sound,
        )


@dataclass
class AppState:
    reminders: List[Reminder]
    snooze_until: Optional[float]
    hold_started_at: Optional[float]
    sound_enabled: bool
    running: bool
    hint_dismissed: bool

    def to_dict(self):
        return {
            "version": 1,
            "snooze_until": self.snooze_until,
            "hold_started_at": self.hold_started_at,
            "sound_enabled": self.sound_enabled,
            "running": self.running,
            "hint_dismissed": self.hint_dismissed,
            "reminders": [reminder.to_dict() for reminder in self.reminders],
        }


def default_state(now):
    specs = (
        ("Drink water", "water", 40, 1),
        ("Take a small rest", "rest", 90, 5),
        ("Walk a bit", "walk", 60, 5),
        ("Stretch", "stretch", 45, 2),
    )
    reminders = [
        Reminder.create(name, kind, frequency, duration, KINDS[kind]["color"], now)
        for name, kind, frequency, duration in specs
    ]
    return AppState(
        reminders=reminders,
        snooze_until=None,
        hold_started_at=None,
        sound_enabled=True,
        running=True,
        hint_dismissed=False,
    )
