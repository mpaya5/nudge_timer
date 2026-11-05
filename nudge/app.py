"""The Nudge window: a clock, one card per break, and meeting snooze."""

import time
import traceback
import tkinter as tk
from tkinter import messagebox

from nudge.cards import ReminderCard
from nudge.dialog import ReminderDialog
from nudge.logic import (
    bump_minutes,
    clock_basis,
    elapsed_fraction,
    format_clock,
    looks_like_wake,
    format_remaining,
    format_span,
    is_suppressed,
    meeting_is_active,
    pause,
    reconcile_hold_on_startup,
    resume,
    retarget_frequency,
    soonest,
    soften_startup_overdue,
    start_meeting,
    take_due,
    tick_expired_snooze,
    end_meeting,
)
from nudge.models import (
    DURATION_STEP,
    FREQUENCY_STEP,
    MAX_DURATION,
    MAX_FREQUENCY,
    MEETING_MINUTES,
    MIN_DURATION,
    MIN_FREQUENCY,
    PALETTE,
    SOUND_AUTO,
    Reminder,
)
from nudge.overlay import AlarmOverlay
from nudge.sound import play_chime
from nudge.storage import default_state_path, load_state, save_state
from nudge.theme import (
    BG,
    CARD,
    CHIP,
    CHIP_HOVER,
    INK,
    LINE,
    MUTED,
    OK,
    OK_HOVER,
    TAGLINE,
    WARN,
    pick_family,
    pick_mono,
)
from nudge.widgets import FlatButton, Ring, ScrolledFrame


class NudgeApp(object):
    def __init__(self, root, state_path, now=None, player=None):
        self.root = root
        self.path = state_path
        self.now = now or time.time
        self.player = player or play_chime
        self.overlay = None
        self.queue = []
        self.dialog = None
        self.cards = {}
        self.note = ""
        self.note_until = 0
        self._alive = True

        moment = self.now()
        self._last_tick = moment
        self.state, created = load_state(self.path, moment)
        changed = reconcile_hold_on_startup(self.state, moment)
        if not is_suppressed(self.state, moment):
            if soften_startup_overdue(self.state.reminders, moment):
                changed = True
        if created or changed:
            self._save()

        self.family = pick_family(root)
        self.mono = pick_mono(root)
        self.root.title("Nudge")
        self.root.configure(bg=BG)
        self._place_window()
        self._build()
        self._rebuild_cards()
        self._refresh_all()
        self._install_quit()
        self._schedule()

    def _place_window(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(560, screen_w - 40)
        height = min(1080, screen_h - 48)
        width = max(320, width)
        height = max(480, height)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 6)
        self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.root.minsize(min(540, screen_w - 20), min(640, max(480, screen_h - 80)))

    def _build(self):
        self.outer = tk.Frame(self.root, bg=BG)
        self.outer.pack(fill="both", expand=True, padx=18, pady=14)
        self._build_top()
        self._build_hero()
        self._build_hint()
        tk.Label(
            self.outer,
            text="Reminders",
            bg=BG,
            fg=INK,
            font=(self.family, 13, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))
        self._build_footer()
        self._build_add()
        self.scroller = ScrolledFrame(self.outer, BG)
        self.scroller.pack(fill="both", expand=True)

    def _build_top(self):
        top = tk.Frame(self.outer, bg=BG)
        top.pack(fill="x")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="Nudge", bg=BG, fg=INK, font=(self.family, 26, "bold")).pack(side="left")
        self.clock = tk.Label(row, text="", bg=BG, fg=MUTED, font=(self.mono, 14))
        self.clock.pack(side="right", pady=(8, 0))
        tk.Label(
            top,
            text=TAGLINE,
            bg=BG,
            fg=MUTED,
            font=(self.family, 12),
            anchor="w",
        ).pack(fill="x", pady=(2, 8))
        buttons = tk.Frame(top, bg=BG)
        buttons.pack(fill="x", pady=(0, 10))
        self.sound_button = FlatButton(
            buttons,
            "Sound on",
            self._toggle_sound,
            bg=CHIP,
            fg=INK,
            hover=CHIP_HOVER,
            font=(self.family, 11),
            padx=10,
            pady=4,
        )
        self.sound_button.pack(side="right", padx=(6, 0))
        self.pause_button = FlatButton(
            buttons,
            "Pause",
            self._toggle_pause,
            bg=CHIP,
            fg=INK,
            hover=CHIP_HOVER,
            font=(self.family, 11, "bold"),
            padx=10,
            pady=4,
        )
        self.pause_button.pack(side="right")

    def _build_hero(self):
        self.hero = tk.Frame(self.outer, bg=CARD, highlightthickness=1, highlightbackground=LINE, bd=0)
        self.hero.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(self.hero, bg=CARD)
        inner.pack(fill="x", padx=8, pady=8)
        self.ring = Ring(inner, 140, self.family, self.mono)
        self.ring.pack(side="left")
        copy = tk.Frame(inner, bg=CARD)
        copy.pack(side="left", fill="both", expand=True, padx=(8, 8))
        self.status = tk.Label(
            copy,
            text="",
            bg=CARD,
            fg=MUTED,
            font=(self.family, 11),
            anchor="w",
            wraplength=250,
            justify="left",
        )
        self.status.pack(anchor="w", pady=(16, 2))
        self.next_name = tk.Label(
            copy,
            text="",
            bg=CARD,
            fg=INK,
            font=(self.family, 20, "bold"),
            anchor="w",
            wraplength=250,
            justify="left",
        )
        self.next_name.pack(anchor="w")
        self.next_meta = tk.Label(
            copy,
            text="",
            bg=CARD,
            fg=MUTED,
            font=(self.family, 12),
            anchor="w",
            wraplength=250,
            justify="left",
        )
        self.next_meta.pack(anchor="w", pady=(4, 0))

    def _build_hint(self):
        self.hint = tk.Frame(self.outer, bg="#fff4e5", highlightthickness=1, highlightbackground="#f0e0c8")
        tk.Label(
            self.hint,
            text="Preview on a card plays the animation now, without changing that reminder.",
            bg="#fff4e5",
            fg=WARN,
            font=(self.family, 11),
            wraplength=390,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        FlatButton(
            self.hint,
            "Dismiss",
            self._dismiss_hint,
            bg="#fff4e5",
            fg=WARN,
            hover="#ffe6c2",
            font=(self.family, 11, "bold"),
            padx=8,
            pady=2,
        ).pack(side="right", padx=(0, 8))
        if not self.state.hint_dismissed:
            self.hint.pack(fill="x", pady=(0, 10))

    def _build_footer(self):
        self.footer = tk.Frame(self.outer, bg=BG)
        self.footer.pack(side="bottom", fill="x", pady=(12, 0))
        tk.Frame(self.footer, bg=LINE, height=1).pack(fill="x", pady=(0, 10))

        self.meeting_idle = tk.Frame(self.footer, bg=BG)
        tk.Label(
            self.meeting_idle,
            text="In a meeting?",
            bg=BG,
            fg=INK,
            font=(self.family, 13, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            self.meeting_idle,
            text="Snooze every reminder, then pick back up when you're free.",
            bg=BG,
            fg=MUTED,
            font=(self.family, 11),
            anchor="w",
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))
        row = tk.Frame(self.meeting_idle, bg=BG)
        row.pack(fill="x")
        for minutes in MEETING_MINUTES:
            FlatButton(
                row,
                format_span(minutes),
                lambda m=minutes: self._meeting_from_main(m),
                bg="#fff4e5",
                fg=WARN,
                hover="#ffe6c2",
                font=(self.family, 12, "bold"),
                padx=8,
                pady=6,
            ).pack(side="left", expand=True, fill="x", padx=3)

        self.meeting_active = tk.Frame(
            self.footer,
            bg="#fff4e5",
            highlightthickness=1,
            highlightbackground="#f0e0c8",
        )
        self.meeting_until = tk.Label(
            self.meeting_active,
            text="",
            bg="#fff4e5",
            fg=INK,
            font=(self.family, 13, "bold"),
            anchor="w",
        )
        self.meeting_until.pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            self.meeting_active,
            text="Reminders are frozen and will resume on their own.",
            bg="#fff4e5",
            fg=WARN,
            font=(self.family, 11),
            anchor="w",
        ).pack(anchor="w", padx=12)
        FlatButton(
            self.meeting_active,
            "Resume now",
            self._resume_now,
            bg=INK,
            fg="#fffdf9",
            hover="#3a342c",
            font=(self.family, 12, "bold"),
            padx=10,
            pady=4,
        ).pack(anchor="w", padx=12, pady=(8, 10))

    def _build_add(self):
        self.add_button = FlatButton(
            self.outer,
            "Add a reminder",
            self._add,
            bg=INK,
            fg="#fffdf9",
            hover="#3a342c",
            font=(self.family, 13, "bold"),
            pady=8,
        )
        self.add_button.pack(side="bottom", fill="x", pady=(10, 0))

    def _rebuild_cards(self):
        for child in list(self.scroller.inner.winfo_children()):
            child.destroy()
        self.cards = {}
        if not self.state.reminders:
            tk.Label(
                self.scroller.inner,
                text="No reminders yet. Add one below.",
                bg=BG,
                fg=MUTED,
                font=(self.family, 12),
                anchor="w",
            ).pack(anchor="w", pady=8)
            return
        for reminder in self.state.reminders:
            card = ReminderCard(
                self.scroller.inner,
                reminder,
                self.family,
                self.mono,
                on_toggle=self._toggle,
                on_frequency=self._change_frequency,
                on_duration=self._change_duration,
                on_preview=self.preview,
                on_edit=self._edit,
                on_delete=self._delete,
            )
            card.pack(fill="x", padx=2, pady=(0, 8))
            self.cards[reminder.id] = card

    def _refresh_all(self):
        if not self._alive:
            return
        now = self.now()
        self._refresh_top(now)
        self._refresh_hero(now)
        self._refresh_cards(now)
        self._refresh_meeting(now)

    def _refresh_top(self, now):
        self.clock.configure(text=time.strftime("%H:%M", time.localtime(now)))
        paused = not self.state.running
        self.pause_button.set_text("Resume" if paused else "Pause")
        if paused:
            self.pause_button.set_colors(OK, "#ffffff", OK_HOVER)
        else:
            self.pause_button.set_colors(CHIP, INK, CHIP_HOVER)
        if self.state.sound_enabled:
            self.sound_button.set_text("Sound on")
            self.sound_button.set_colors(CHIP, INK, CHIP_HOVER)
        else:
            self.sound_button.set_text("Muted")
            self.sound_button.set_colors(CHIP, WARN, CHIP_HOVER)

    def _refresh_hero(self, now):
        basis = clock_basis(self.state, now)
        nxt = soonest(self.state.reminders)
        if self.note and now < self.note_until:
            status = self.note
        elif meeting_is_active(self.state, now):
            status = "In a meeting until " + format_clock(self.state.snooze_until)
        elif not self.state.running:
            status = "Paused. Reminders are frozen."
        elif nxt is None:
            status = "Nothing is scheduled."
        else:
            status = "Next up"
        self.status.configure(text=status)
        if nxt is None:
            self.ring.render(0, LINE, None, "—")
            self.next_name.configure(text="No reminder")
            self.next_meta.configure(text="Turn one on, or add your own.")
            return
        remaining = nxt.next_due - basis
        fraction = elapsed_fraction(nxt.next_due, basis, nxt.frequency_minutes)
        self.ring.render(fraction, nxt.color, nxt.kind, format_remaining(remaining))
        self.next_name.configure(text=nxt.name)
        self.next_meta.configure(
            text="Every %d min   ·   %d min timer" % (nxt.frequency_minutes, nxt.duration_minutes)
        )

    def _refresh_cards(self, now):
        basis = clock_basis(self.state, now)
        for reminder in self.state.reminders:
            card = self.cards.get(reminder.id)
            if card is not None:
                card.render(reminder, basis)

    def _refresh_meeting(self, now):
        if meeting_is_active(self.state, now):
            self.meeting_idle.pack_forget()
            if not self.meeting_active.winfo_ismapped():
                self.meeting_active.pack(fill="x")
            self.meeting_until.configure(text="Snoozed until " + format_clock(self.state.snooze_until))
        else:
            self.meeting_active.pack_forget()
            if not self.meeting_idle.winfo_ismapped():
                self.meeting_idle.pack(fill="x")

    def _flash(self, text):
        self.note = text
        self.note_until = self.now() + 3
        self._refresh_hero(self.now())

    def _basis(self, now=None):
        if now is None:
            now = self.now()
        return clock_basis(self.state, now)

    def _find(self, reminder_id):
        for reminder in self.state.reminders:
            if reminder.id == reminder_id:
                return reminder
        return None

    def _save(self):
        save_state(self.path, self.state)

    def _change_frequency(self, reminder, direction):
        new = bump_minutes(
            reminder.frequency_minutes,
            direction,
            FREQUENCY_STEP,
            MIN_FREQUENCY,
            MAX_FREQUENCY,
        )
        if new == reminder.frequency_minutes:
            return
        reminder.frequency_minutes = new
        reminder.next_due = retarget_frequency(reminder.next_due, self._basis(), new)
        self._save()
        self._refresh_all()

    def _change_duration(self, reminder, direction):
        new = bump_minutes(
            reminder.duration_minutes,
            direction,
            DURATION_STEP,
            MIN_DURATION,
            MAX_DURATION,
        )
        if new == reminder.duration_minutes:
            return
        reminder.duration_minutes = new
        self._save()
        self._refresh_all()

    def _toggle(self, reminder):
        reminder.enabled = not reminder.enabled
        if reminder.enabled and reminder.next_due <= self._basis():
            reminder.next_due = self._basis() + reminder.frequency_minutes * 60
        self._save()
        self._refresh_all()

    def _delete(self, reminder):
        if not messagebox.askyesno(
            "Delete reminder",
            'Delete "%s"?' % reminder.name,
            parent=self.root,
        ):
            return
        self.state.reminders = [item for item in self.state.reminders if item.id != reminder.id]
        self.queue = [item for item in self.queue if item != reminder.id]
        self._save()
        self._rebuild_cards()
        self._refresh_all()

    def _next_color(self):
        used = set(reminder.color.lower() for reminder in self.state.reminders)
        for color in PALETTE:
            if color.lower() not in used:
                return color
        return PALETTE[len(self.state.reminders) % len(PALETTE)]

    def _add(self):
        self._open_editor(None, self._commit_new, self._next_color())

    def _edit(self, reminder):
        self._open_editor(reminder, lambda data, current=reminder: self._commit_edit(current, data), reminder.color)

    def _open_editor(self, reminder, on_save, color):
        if self.dialog is not None:
            try:
                if self.dialog.winfo_exists():
                    self._flash("Finish the reminder you're editing first.")
                    self.dialog.lift()
                    return
            except tk.TclError:
                self.dialog = None

        def wrapped(data, save=on_save):
            save(data)

        self.dialog = ReminderDialog(
            self.root, self.family, self.mono, reminder, color, wrapped, player=self._preview_sound
        )
        self.dialog.bind("<Destroy>", self._clear_dialog, add="+")

    def _clear_dialog(self, event):
        if self.dialog is not None and event.widget == self.dialog:
            self.dialog = None

    def _commit_new(self, data):
        reminder = Reminder.create(
            data["name"],
            data["kind"],
            data["frequency"],
            data["duration"],
            data["color"],
            self._basis(),
            sound=data.get("sound", SOUND_AUTO),
        )
        self.state.reminders.append(reminder)
        self._save()
        self._rebuild_cards()
        self._refresh_all()

    def _commit_edit(self, reminder, data):
        if self._find(reminder.id) is None:
            self._flash("That reminder was deleted, so nothing was saved.")
            return
        reminder.name = data["name"]
        reminder.kind = data["kind"]
        reminder.color = data["color"]
        reminder.sound = data.get("sound", reminder.sound)
        reminder.duration_minutes = data["duration"]
        if data["frequency"] != reminder.frequency_minutes:
            reminder.frequency_minutes = data["frequency"]
            reminder.next_due = retarget_frequency(reminder.next_due, self._basis(), data["frequency"])
        self._save()
        self._refresh_all()

    def _preview_sound(self, kind, sound):
        """Play a sound from the editor. Works even while muted, since the user asked to hear it."""
        try:
            self.player(kind, sound)
        except Exception:
            traceback.print_exc()

    def _toggle_sound(self):
        self.state.sound_enabled = not self.state.sound_enabled
        self._save()
        self._refresh_all()

    def _toggle_pause(self):
        now = self.now()
        if self.state.running:
            self.queue.clear()
            pause(self.state, now)
            self._save()
            self._refresh_all()
            if self.overlay is not None:
                self.overlay.dismiss_quietly()
            return
        resume(self.state, now)
        self._save()
        self._collect_due(now)
        self._refresh_all()

    def _apply_meeting(self, minutes):
        self.queue.clear()
        start_meeting(self.state, self.now(), minutes)
        self._save()
        self._refresh_all()

    def _meeting_from_main(self, minutes):
        self._apply_meeting(minutes)
        if self.overlay is not None:
            self.overlay.dismiss_quietly()

    def _resume_now(self):
        end_meeting(self.state, self.now())
        self._save()
        self._collect_due(self.now())
        self._refresh_all()

    def _dismiss_hint(self):
        self.state.hint_dismissed = True
        self.hint.pack_forget()
        self._save()

    def preview(self, reminder):
        if self.overlay is not None:
            self._flash("An alarm is already on screen.")
            return
        self._open_overlay(reminder, preview=True)

    def _open_overlay(self, reminder, preview):
        def snooze(minutes, current=reminder, is_preview=preview):
            if not is_preview:
                current.next_due = self.now() + minutes * 60
                self._save()

        try:
            self.overlay = AlarmOverlay(
                self.root,
                reminder,
                family=self.family,
                mono=self.mono,
                player=self._play,
                on_snooze=snooze,
                on_meeting=self._apply_meeting,
                on_closed=self._on_overlay_closed,
                preview=preview,
            )
        except Exception:
            traceback.print_exc()
            self.overlay = None

    def _on_overlay_closed(self):
        self.overlay = None
        if not self._alive:
            return
        self._refresh_all()
        self._pump_queue()

    def _play(self, kind, sound=SOUND_AUTO):
        if not self.state.sound_enabled:
            return
        try:
            self.player(kind, sound)
        except Exception:
            traceback.print_exc()

    def _collect_due(self, now):
        if not self._alive or is_suppressed(self.state, now):
            return
        taken = take_due(self.state.reminders, now)
        added = False
        for reminder_id in taken:
            if reminder_id not in self.queue:
                self.queue.append(reminder_id)
                added = True
        if added:
            self._save()
        self._pump_queue()

    def _pump_queue(self):
        if not self._alive or self.overlay is not None:
            return
        if is_suppressed(self.state, self.now()):
            return
        while self.queue:
            reminder_id = self.queue.pop(0)
            reminder = self._find(reminder_id)
            if reminder is not None and reminder.enabled:
                self._open_overlay(reminder, preview=False)
                return

    def tick(self):
        if not self._alive:
            return
        now = self.now()
        woke = looks_like_wake(self._last_tick, now)
        self._last_tick = now
        if tick_expired_snooze(self.state, now):
            self._save()
        if woke and not is_suppressed(self.state, now):
            # The computer was asleep: don't fire every missed reminder at once.
            if soften_startup_overdue(self.state.reminders, now):
                self._save()
        self._collect_due(now)
        self._refresh_all()

    def _scheduled_tick(self):
        if not self._alive:
            return
        try:
            self.tick()
        except tk.TclError:
            return
        except Exception:
            traceback.print_exc()
        self._schedule()

    def _schedule(self):
        if not self._alive:
            return
        try:
            self.root.after(1000, self._scheduled_tick)
        except tk.TclError:
            self._alive = False

    def _install_quit(self):
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.root.createcommand("tk::mac::Quit", self.close)
        except tk.TclError:
            pass

    def close(self):
        if not self._alive:
            return
        self._alive = False
        try:
            self._save()
        except OSError:
            traceback.print_exc()
        overlay = self.overlay
        self.overlay = None
        if overlay is not None:
            overlay.dismiss_quietly()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def bring_to_front(root):
    """Python started from a terminal opens behind other apps on macOS."""
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after(400, lambda: _safe_attr(root, "-topmost", False))
        root.focus_force()
    except tk.TclError:
        pass


def set_window_icon(root):
    """Use the Nudge picture in the Dock, taskbar and window corner. Optional, so never fatal."""
    from pathlib import Path

    path = Path(__file__).resolve().parent / "assets" / "icon-256.png"
    try:
        image = tk.PhotoImage(master=root, file=str(path))
        root.iconphoto(True, image)
        root._nudge_icon = image  # Tk forgets the picture if Python lets go of it
    except (tk.TclError, OSError):
        pass


def _safe_attr(root, name, value):
    try:
        root.attributes(name, value)
    except tk.TclError:
        pass


def run(state_path=None, now=None, player=None, use_lock=True, preview_on_start=False, demo=False):
    import tempfile
    from pathlib import Path

    if demo:
        path = Path(tempfile.mkdtemp(prefix="nudge-demo-")) / "state.json"
        use_lock = False
    else:
        path = state_path or default_state_path()
    root = tk.Tk()
    root.withdraw()
    root.configure(bg=BG)
    set_window_icon(root)
    lock = None
    if use_lock:
        from nudge.storage import ProcessLock

        lock = ProcessLock(path.with_name("nudge.lock"))
        if not lock.acquire():
            root.deiconify()
            messagebox.showinfo("Nudge", "Nudge is already running.", parent=root)
            root.destroy()
            return
    try:
        app = NudgeApp(root, path, now=now, player=player)
        if demo:
            moment = app.now()
            for index, reminder in enumerate(app.state.reminders):
                reminder.next_due = moment + 8 + index * 20
            app._save()
        if preview_on_start and app.state.reminders:
            root.after(500, lambda: app.preview(app.state.reminders[0]))
        try:
            root.createcommand("tk::mac::ReopenApplication", lambda: bring_to_front(root))
        except tk.TclError:
            pass
        bring_to_front(root)
        root.mainloop()
    finally:
        if lock is not None:
            lock.release()
