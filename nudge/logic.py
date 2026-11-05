"""Timing rules for Nudge.

Each reminder stores an absolute `next_due` timestamp. While the app is
running, wall-clock time counts toward that deadline. Pause and meeting
snooze freeze every reminder: the start of the freeze is remembered and,
when it ends, each deadline is pushed forward by the frozen duration.

Time the app spends closed still counts, unless a freeze was active when
it quit. A meeting that expires while the app is closed only freezes the
meeting itself — time after that counts again.
"""

import math
import time

TRAVEL_SECONDS = 5.0


def format_remaining(seconds):
    total = int(max(0, round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_clock(epoch):
    return time.strftime("%H:%M", time.localtime(epoch))


def format_span(minutes):
    minutes = int(minutes)
    if minutes > 0 and minutes % 60 == 0:
        hours = minutes // 60
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit}"
    return f"{minutes} min"


def duration_phrase(minutes):
    minutes = int(minutes)
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


def alarm_title(name):
    text = " ".join(str(name).split())
    if not text:
        return "Time for a break"
    return "Time to " + text[0].lower() + text[1:]


def bump_minutes(value, direction, step, minimum, maximum):
    value = int(value)
    step = max(1, int(step))
    if direction > 0:
        nxt = (value // step) * step + step
        if nxt <= value:
            nxt = value + step
    else:
        nxt = ((value - 1) // step) * step
        if nxt >= value:
            nxt = value - step
    return max(int(minimum), min(int(maximum), int(nxt)))


def meeting_is_active(state, now):
    return state.snooze_until is not None and now < state.snooze_until


def is_suppressed(state, now):
    if not state.running:
        return True
    return meeting_is_active(state, now)


def clock_basis(state, now):
    """The 'now' reminders should be measured against.

    During a freeze, deadlines stay put, so remaining time is computed as of
    the moment the freeze began.
    """
    if state.hold_started_at is not None and is_suppressed(state, now):
        return state.hold_started_at
    return now


def elapsed_fraction(next_due, basis, frequency_minutes):
    span = frequency_minutes * 60
    if span <= 0:
        return 0.0
    remaining = next_due - basis
    elapsed = span - remaining
    return min(1.0, max(0.0, elapsed / float(span)))


def retarget_frequency(next_due, basis, new_frequency):
    remaining = next_due - basis
    span = new_frequency * 60
    if remaining <= 0:
        return basis + span
    return basis + min(remaining, span)


def soonest(reminders):
    enabled = [reminder for reminder in reminders if reminder.enabled]
    if not enabled:
        return None
    return min(enabled, key=lambda reminder: (reminder.next_due, reminder.name))


def take_due(reminders, now):
    """Mark every due reminder as fired and return their ids in list order."""
    taken = []
    for reminder in reminders:
        if not reminder.enabled or reminder.next_due > now:
            continue
        reminder.next_due = now + reminder.frequency_minutes * 60
        taken.append(reminder.id)
    return taken


def ensure_hold(state, now):
    if state.hold_started_at is None:
        state.hold_started_at = now


def shift_hold(state, end):
    """Push deadlines forward by the freeze, then clear it.

    A reminder that was already due when the freeze began becomes due at
    `end`, so it can alert as soon as reminders resume.
    """
    if state.hold_started_at is None:
        return
    delta = max(0.0, end - state.hold_started_at)
    for reminder in state.reminders:
        if reminder.next_due <= state.hold_started_at:
            reminder.next_due = end
        else:
            reminder.next_due += delta
    state.hold_started_at = None


def start_meeting(state, now, minutes):
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    state.running = True
    state.snooze_until = now + minutes * 60
    ensure_hold(state, now)


def end_meeting(state, now):
    """Resume immediately, ending a meeting snooze or a manual pause."""
    state.running = True
    if state.hold_started_at is not None:
        shift_hold(state, now)
    state.snooze_until = None


def pause(state, now):
    """Freeze reminders until the user resumes. Cancels a timed meeting."""
    state.running = False
    state.snooze_until = None
    ensure_hold(state, now)


def resume(state, now):
    state.running = True
    if state.snooze_until is not None and now < state.snooze_until:
        return
    if state.hold_started_at is not None:
        shift_hold(state, now)
    if state.snooze_until is not None and now >= state.snooze_until:
        state.snooze_until = None


def tick_expired_snooze(state, now):
    """Release a meeting snooze that has reached its end. Returns True if it did."""
    if state.hold_started_at is None or not state.running:
        return False
    if state.snooze_until is None or now < state.snooze_until:
        return False
    shift_hold(state, state.snooze_until)
    state.snooze_until = None
    return True


def reconcile_hold_on_startup(state, now):
    """Apply a freeze that ended (or is still running) while the app was closed."""
    changed = False
    if not state.running:
        if state.snooze_until is not None and state.snooze_until <= now:
            state.snooze_until = None
            changed = True
        return changed
    if state.snooze_until is not None and now < state.snooze_until:
        if state.hold_started_at is None:
            state.hold_started_at = now
            changed = True
        return changed
    if state.snooze_until is not None and now >= state.snooze_until:
        if state.hold_started_at is not None:
            shift_hold(state, state.snooze_until)
            changed = True
        state.snooze_until = None
        changed = True
        return changed
    if state.hold_started_at is not None:
        state.hold_started_at = None
        changed = True
    return changed


WAKE_GAP_SECONDS = 90


def looks_like_wake(last_tick, now, gap=WAKE_GAP_SECONDS):
    """True when far more time passed between two ticks than a tick takes.

    The app ticks once a second, so a long gap means the computer was asleep
    (or the process was suspended).
    """
    if last_tick is None:
        return False
    return (now - last_tick) > gap


def soften_startup_overdue(reminders, now, first_delay=2, gap=45):
    """Space out reminders missed while the app was closed so they don't stack."""
    overdue = sorted(
        (reminder for reminder in reminders if reminder.enabled and reminder.next_due <= now),
        key=lambda reminder: reminder.next_due,
    )
    if not overdue:
        return False
    for index, reminder in enumerate(overdue):
        reminder.next_due = now + first_delay + index * gap
    return True


def travel_position(elapsed, screen_w, screen_h, win_w, win_h, duration=TRAVEL_SECONDS):
    """Move a window from off the right edge to the horizontal center.

    The path bows downward through the upper part of the screen, then settles.
    Returns x, y, and whether the trip is finished.
    """
    if duration <= 0:
        progress = 1.0
    else:
        progress = min(1.0, max(0.0, float(elapsed) / float(duration)))
    start_x = float(screen_w) + 8.0
    end_x = (float(screen_w) - float(win_w)) / 2.0
    x = start_x + (end_x - start_x) * progress
    base_y = max(24.0, float(screen_h) * 0.12)
    room = float(screen_h) - float(win_h) - base_y - 16.0
    arc = min(float(screen_h) * 0.22, max(0.0, room))
    y = base_y + math.sin(progress * math.pi) * arc
    y = min(y, float(screen_h) - float(win_h) - 16.0)
    y = max(16.0, y)
    return x, y, progress >= 1.0
