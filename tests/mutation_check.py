"""Plant deliberate bugs in a scratch copy and check the suite notices each one.

    python3 tests/mutation_check.py

The real project files are never touched; every bug is planted in a temporary copy.
Takes a few minutes because each bug triggers a full test run.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

MUTATIONS = [
    ("logic: freeze no longer shifts deadlines", "nudge/logic.py",
     "            reminder.next_due += delta", "            reminder.next_due += 0"),
    ("logic: already-due reminders not released at hold end", "nudge/logic.py",
     "            reminder.next_due = end\n        else:", "            reminder.next_due += delta\n        else:"),
    ("logic: disabled reminders still fire", "nudge/logic.py",
     "if not reminder.enabled or reminder.next_due > now:", "if reminder.next_due > now:"),
    ("logic: fired reminder not rescheduled", "nudge/logic.py",
     "        reminder.next_due = now + reminder.frequency_minutes * 60\n        taken",
     "        taken"),
    ("logic: pause no longer suppresses alarms", "nudge/logic.py",
     "    if not state.running:\n        return True\n    return meeting_is_active",
     "    return meeting_is_active"),
    ("logic: wake detection off", "nudge/logic.py",
     "return (now - last_tick) > gap", "return False"),
    ("logic: meeting accepts zero minutes", "nudge/logic.py",
     "    if minutes <= 0:\n        raise ValueError", "    if minutes < 0:\n        raise ValueError"),
    ("storage: accepts malformed colors", "nudge/storage.py",
     "_COLOR.fullmatch(value)", "value"),
    ("storage: non-string kind crashes loading", "nudge/storage.py",
     'if not isinstance(kind, str) or kind not in KINDS:', 'if kind not in KINDS:'),
    ("app: editing a deleted reminder not guarded", "nudge/app.py",
     "        if self._find(reminder.id) is None:\n"
     "            self._flash(\"That reminder was deleted, so nothing was saved.\")\n            return\n",
     ""),
    ("app: tick ignores wake-from-sleep", "nudge/app.py",
     "if woke and not is_suppressed(self.state, now):", "if False:"),
    ("app: tick never expires meeting snooze", "nudge/app.py",
     "if tick_expired_snooze(self.state, now):", "if False:"),
    ("sound: a silent reminder still plays", "nudge/sound.py",
     "    if sound == SOUND_NONE:\n        return\n    try:", "    try:"),
    ("sound: added-sound names are not checked (path escape)", "nudge/sound.py",
     " or not value.startswith(CUSTOM_PREFIX) or not is_valid_sound(value):",
     " or not value.startswith(CUSTOM_PREFIX):"),
    ("sound: files of any type can be added", "nudge/sound.py",
     "    if extension not in supported_extensions():", "    if False:"),
    ("storage: a damaged sound value is kept", "nudge/storage.py",
     "    if is_valid_sound(value):\n        return value", "    if isinstance(value, str):\n        return value"),
    ("storage: Windows process check uses os.kill (ends the other Nudge)", "nudge/storage.py",
     '    if os.name == "nt":\n        try:', '    if False:\n        try:'),
    ("app: editing a reminder does not save its sound", "nudge/app.py",
     '        reminder.sound = data.get("sound", reminder.sound)\n', ""),
    ("overlay: alarm ignores the reminder's sound", "nudge/overlay.py",
     "self.player(self.reminder.kind, self.reminder.sound)", "self.player(self.reminder.kind)"),
    ("dialog: the 'Add your own sound' entry can be saved as a sound", "nudge/dialog.py",
     "if text == label and value != SOUND_ADD:", "if text == label:"),
    ("installer: an update overwrites the person's reminders", "nudge/installer.py",
     "    if old.is_dir() and not new.exists():", "    if old.is_dir():"),
    ("installer: uninstall always deletes the reminders", "nudge/installer.py",
     "        if remove_data:\n            shutil.rmtree(plan.app_dir",
     "        if True:\n            shutil.rmtree(plan.app_dir"),
    ("installer: Windows fallback launcher loses its Windows line endings", "nudge/installer.py",
     '            "@echo off\\r\\n"', '            "@echo off\\n"'),
]


def run(tests):
    env = dict(os.environ, NUDGE_NO_REEXEC="1")
    try:
        r = subprocess.run([PY, "tests/run_all.py"] + tests, cwd=work, env=env,
                           capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return 99
    return r.returncode


survived = []
for label, path, old, new in MUTATIONS:
    work = tempfile.mkdtemp(prefix="mut-")
    shutil.rmtree(work)
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns("data", "__pycache__", ".git"))
    target = os.path.join(work, path)
    text = open(target).read()
    if old not in text:
        print("SKIPPED (pattern not found):", label)
        survived.append(label)
        continue
    open(target, "w").write(text.replace(old, new, 1))
    code = run([])
    verdict = "caught" if code != 0 else "SURVIVED"
    print(f"{verdict:9} {label}", flush=True)
    if code == 0:
        survived.append(label)
    shutil.rmtree(work, ignore_errors=True)

print()
print(f"{len(MUTATIONS) - len(survived)}/{len(MUTATIONS)} planted bugs caught")
for s in survived:
    print("  not caught:", s)
sys.exit(1 if survived else 0)
