"""The alarm that walks across the screen, then asks what to do."""

import time
import traceback
import tkinter as tk

from nudge.logic import TRAVEL_SECONDS, alarm_title, duration_phrase, format_remaining, format_span, travel_position
from nudge.models import DEFAULT_SNOOZE, MEETING_FROM_ALARM, PROMPT_TIMEOUT, SNOOZE_MINUTES
from nudge.sprites import draw_check, draw_sprite
from nudge.theme import (
    MEETING_BG,
    MEETING_FG,
    MEETING_HOVER,
    OVERLAY_BG,
    OVERLAY_BUTTON,
    OVERLAY_BUTTON_HOVER,
    OVERLAY_FG,
    OVERLAY_MUTED,
    mix,
)
from nudge.widgets import FlatButton

TRAVEL_W = 270
PROMPT_W = 380
CANVAS_H = 176


class AlarmOverlay(object):
    def __init__(self, master, reminder, family, mono, player, on_snooze, on_meeting, on_closed, preview=False):
        self.reminder = reminder
        self.family = family
        self.mono = mono
        self.player = player
        self.on_snooze = on_snooze
        self.on_meeting = on_meeting
        self.on_closed = on_closed
        self.preview = preview
        self.phase = "travel"
        self.alive = True
        self.elapsed = 0.0
        self.prompt_started = None
        self.done_mark = None
        self.deadline = None
        self.time_label = None
        self._last = time.perf_counter()
        self._frames = 0
        self._placed = None

        self.window = tk.Toplevel(master)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(bg=reminder.color)
        try:
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass

        shell = tk.Frame(self.window, bg=reminder.color)
        shell.pack(fill="both", expand=True)
        self.inner = tk.Frame(shell, bg=OVERLAY_BG)
        self.inner.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas = tk.Canvas(
            self.inner,
            width=TRAVEL_W - 8,
            height=CANVAS_H,
            bg=OVERLAY_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.controls = tk.Frame(self.inner, bg=OVERLAY_BG)
        self.window.bind("<Escape>", self._on_escape)
        self.window.bind("<Return>", self._on_return)

        self.window.update_idletasks()
        measured = self.window.winfo_reqheight()
        self.travel_height = measured if measured > 80 else CANVAS_H + 8
        self._advance()
        self._redraw()
        self.window.deiconify()
        self.window.lift()
        try:
            # Set again now that the window is showing; some systems reset it on show.
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._play_once()
        self.window.after(33, self._animate)

    @property
    def reminder_id(self):
        return self.reminder.id

    def _animate(self):
        if not self.alive:
            return
        now = time.perf_counter()
        self.elapsed += min(0.05, now - self._last)
        self._last = now
        self._frames += 1
        try:
            self._advance()
            if not self.alive:
                return
            self._redraw()
            if self._frames % 15 == 0:
                self.window.lift()
                try:
                    self.window.attributes("-topmost", True)
                except tk.TclError:
                    pass
        except tk.TclError:
            self.alive = False
            return
        if self.alive:
            try:
                self.window.after(33, self._animate)
            except tk.TclError:
                self.alive = False

    def _advance(self):
        if not self.alive:
            return
        if self.phase == "travel":
            screen_w = self.window.winfo_screenwidth()
            screen_h = self.window.winfo_screenheight()
            x, y, arrived = travel_position(
                self.elapsed,
                screen_w,
                screen_h,
                TRAVEL_W,
                self.travel_height,
                TRAVEL_SECONDS,
            )
            self._move(x, y, TRAVEL_W, self.travel_height)
            if arrived:
                self._enter_prompt()
            return
        if self.phase == "prompt":
            if self.prompt_started is not None and time.time() - self.prompt_started >= PROMPT_TIMEOUT:
                self._snooze(DEFAULT_SNOOZE)
            return
        if self.phase == "active":
            left = self.deadline - time.time()
            if left <= 0:
                self._enter_done()
            elif self.time_label is not None:
                self.time_label.configure(text=format_remaining(left))
            return
        if self.phase == "done" and self.done_mark is not None and self.elapsed - self.done_mark > 1.3:
            self._shutdown(lambda: None)

    def _redraw(self):
        width = int(float(self.canvas.cget("width")))
        height = int(float(self.canvas.cget("height")))
        self.canvas.delete("sprite")
        self.canvas.delete("caption")
        color = self.reminder.color
        if self.phase == "done":
            draw_check(
                self.canvas,
                width / 2.0,
                height / 2.0 - 6,
                self.elapsed - (self.done_mark or self.elapsed),
                color,
                scale=1.3,
                tag="sprite",
            )
            caption = "Nice."
        else:
            draw_sprite(
                self.canvas,
                self.reminder.kind,
                width / 2.0,
                height / 2.0 - 10,
                self.elapsed,
                color,
                scale=1.15,
                tag="sprite",
                ground="#2a2622",
                hole=OVERLAY_BG,
            )
            caption = self.reminder.name if self.phase == "travel" else ""
        if caption:
            self.canvas.create_text(
                width / 2.0,
                height - 16,
                text=caption,
                fill=OVERLAY_FG,
                font=(self.family, 14, "bold"),
                width=max(40, width - 24),
                justify="center",
                tags="caption",
            )

    def _enter_prompt(self):
        if not self.alive or self.phase != "travel":
            return
        self.phase = "prompt"
        self.prompt_started = time.time()
        self._build_prompt()
        self._fit(PROMPT_W)
        try:
            self.window.focus_force()
        except tk.TclError:
            pass

    def _begin(self):
        if not self.alive or self.phase != "prompt":
            return
        self.phase = "active"
        self.deadline = time.time() + self.reminder.duration_minutes * 60
        self._clear_controls()
        self.time_label = tk.Label(
            self.controls,
            text=format_remaining(self.reminder.duration_minutes * 60),
            bg=OVERLAY_BG,
            fg=OVERLAY_FG,
            font=(self.mono, 36, "bold"),
        )
        self.time_label.pack(fill="x", pady=(2, 0))
        tk.Label(
            self.controls,
            text=self.reminder.name,
            bg=OVERLAY_BG,
            fg=OVERLAY_MUTED,
            font=(self.family, 13),
            wraplength=PROMPT_W - 48,
            justify="center",
        ).pack(fill="x", pady=(0, 10))
        self._primary("Done", self._enter_done).pack(fill="x", pady=(0, 8))
        self._meeting_button().pack(fill="x")
        self._fit(PROMPT_W)

    def _enter_done(self):
        if not self.alive or self.phase == "done":
            return
        self.phase = "done"
        self.done_mark = self.elapsed
        self.time_label = None
        for child in list(self.controls.winfo_children()):
            child.destroy()
        self.controls.pack_forget()
        self.canvas.configure(width=TRAVEL_W - 8)
        self._center(TRAVEL_W, self.travel_height)

    def _build_prompt(self):
        self._clear_controls()
        self.time_label = None
        tk.Label(
            self.controls,
            text=alarm_title(self.reminder.name),
            bg=OVERLAY_BG,
            fg=OVERLAY_FG,
            font=(self.family, 18, "bold"),
            wraplength=PROMPT_W - 48,
            justify="center",
        ).pack(fill="x")
        tk.Label(
            self.controls,
            text="The timer runs for %s." % duration_phrase(self.reminder.duration_minutes),
            bg=OVERLAY_BG,
            fg=OVERLAY_MUTED,
            font=(self.family, 11),
            wraplength=PROMPT_W - 48,
            justify="center",
        ).pack(fill="x", pady=(4, 10))
        self._primary("Start", self._begin).pack(fill="x", pady=(0, 10))
        tk.Label(
            self.controls,
            text="Snooze this one",
            bg=OVERLAY_BG,
            fg=OVERLAY_MUTED,
            font=(self.family, 11),
        ).pack(anchor="w")
        row = tk.Frame(self.controls, bg=OVERLAY_BG)
        row.pack(fill="x", pady=(4, 10))
        for minutes in SNOOZE_MINUTES:
            FlatButton(
                row,
                format_span(minutes),
                lambda m=minutes: self._snooze(m),
                bg=OVERLAY_BUTTON,
                fg=OVERLAY_FG,
                hover=OVERLAY_BUTTON_HOVER,
                font=(self.family, 12),
                pady=6,
            ).pack(side="left", expand=True, fill="x", padx=2)
        self._meeting_button().pack(fill="x")

    def _primary(self, text, command):
        return FlatButton(
            self.controls,
            text,
            command,
            bg=self.reminder.color,
            fg="#ffffff",
            hover=mix(self.reminder.color, "#000000", 0.18),
            font=(self.family, 14, "bold"),
            pady=8,
        )

    def _meeting_button(self):
        return FlatButton(
            self.controls,
            "I'm in a meeting · %s" % format_span(MEETING_FROM_ALARM),
            self._meeting,
            bg=MEETING_BG,
            fg=MEETING_FG,
            hover=MEETING_HOVER,
            font=(self.family, 12, "bold"),
            pady=8,
        )

    def _clear_controls(self):
        for child in list(self.controls.winfo_children()):
            child.destroy()
        if not self.controls.winfo_ismapped():
            self.controls.pack(fill="x", padx=16, pady=(0, 14))

    def _fit(self, width):
        self.canvas.configure(width=max(40, int(width) - 8))
        self.window.update_idletasks()
        height = self.window.winfo_reqheight()
        if height < CANVAS_H:
            height = CANVAS_H + 8
        self._center(width, height)

    def _center(self, width, height):
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = max(16, (screen_w - width) / 2.0)
        y = max(16, min(screen_h * 0.12, screen_h - height - 16))
        self._move(x, y, width, height)

    def _move(self, x, y, width, height):
        width = int(width)
        height = int(height)
        # macOS ignores a size change on a borderless window that is already
        # visible. Hide it, resize, then show it again. Position-only moves
        # during the walk stay on screen.
        size = (width, height)
        resize = self._placed != size and bool(self.window.winfo_ismapped())
        self._placed = size
        if resize:
            self.window.withdraw()
            self.window.overrideredirect(True)
        self.window.geometry("%dx%d+%d+%d" % (width, height, int(x), int(y)))
        if resize:
            self.window.update_idletasks()
            self.window.deiconify()
            try:
                self.window.attributes("-topmost", True)
            except tk.TclError:
                pass
            self.window.lift()

    def _on_canvas_click(self, _event):
        if self.phase == "travel":
            self._enter_prompt()
        elif self.phase == "done":
            self._shutdown(lambda: None)

    def _on_escape(self, _event):
        if not self.alive:
            return
        if self.phase == "active":
            self._enter_done()
        elif self.phase == "done":
            self._shutdown(lambda: None)
        else:
            self._snooze(DEFAULT_SNOOZE)

    def _on_return(self, _event):
        if self.phase == "prompt":
            self._begin()
        elif self.phase == "travel":
            self._enter_prompt()

    def _snooze(self, minutes):
        self._shutdown(lambda: self.on_snooze(minutes))

    def _meeting(self):
        self._shutdown(lambda: self.on_meeting(MEETING_FROM_ALARM))

    def dismiss_quietly(self):
        self._shutdown(lambda: None)

    def _shutdown(self, action):
        if not self.alive:
            return
        self.alive = False
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        try:
            action()
        except Exception:
            traceback.print_exc()
        try:
            self.on_closed()
        except Exception:
            traceback.print_exc()

    def _play_once(self):
        try:
            self.player(self.reminder.kind, self.reminder.sound)
        except Exception:
            traceback.print_exc()
