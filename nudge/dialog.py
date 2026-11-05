"""Add and edit a reminder."""

import tkinter as tk
from tkinter import filedialog

from nudge.models import (
    KIND_ORDER,
    KINDS,
    MAX_DURATION,
    MAX_FREQUENCY,
    MIN_DURATION,
    MIN_FREQUENCY,
    PALETTE,
    SOUND_AUTO,
)
from nudge.sound import (
    SOUND_ADD,
    SoundImportError,
    add_custom_sound,
    sound_choices,
    supported_extensions,
)
from nudge.sprites import draw_sprite, still_time
from nudge.theme import BG, CARD, CHIP, CHIP_HOVER, DANGER, INK, LINE, MUTED
from nudge.widgets import FlatButton


class ReminderDialog(tk.Toplevel):
    def __init__(self, master, family, mono, reminder, suggested_color, on_save, player=None):
        super().__init__(master)
        self.player = player
        self.family = family
        self.mono = mono
        self.on_save = on_save
        self.reminder = reminder
        self.kind = reminder.kind if reminder is not None else "water"
        self.color = reminder.color if reminder is not None else suggested_color
        self.color_touched = reminder is not None
        self.sound = reminder.sound if reminder is not None else SOUND_AUTO
        self._saved = False
        self.kind_widgets = {}
        self.swatches = {}
        self.title("Edit reminder" if reminder is not None else "Add a reminder")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), 460)
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.name_entry.focus_set()

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(outer, text="Name", bg=BG, fg=INK, font=(self.family, 12, "bold"), anchor="w").pack(fill="x")
        self.name_entry = tk.Entry(
            outer,
            bg=CARD,
            fg=INK,
            insertbackground=INK,
            relief="flat",
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=INK,
            font=(self.family, 13),
        )
        self.name_entry.pack(fill="x", ipady=6, pady=(4, 12))
        if self.reminder is not None:
            self.name_entry.insert(0, self.reminder.name)

        tk.Label(outer, text="Animation", bg=BG, fg=INK, font=(self.family, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            outer,
            text="This is what walks across the screen.",
            bg=BG,
            fg=MUTED,
            font=(self.family, 11),
            anchor="w",
        ).pack(fill="x", pady=(2, 6))
        kinds = tk.Frame(outer, bg=BG)
        kinds.pack(fill="x", pady=(0, 12))
        for kind in KIND_ORDER:
            self.kind_widgets[kind] = self._kind_cell(kinds, kind)

        tk.Label(outer, text="Color", bg=BG, fg=INK, font=(self.family, 12, "bold"), anchor="w").pack(fill="x")
        colors = tk.Frame(outer, bg=BG)
        colors.pack(fill="x", pady=(6, 12))
        for color in PALETTE:
            swatch = tk.Frame(colors, bg=color, width=26, height=26, highlightthickness=2, cursor="hand2")
            swatch.pack(side="left", padx=(0, 6))
            swatch.pack_propagate(False)
            swatch.bind("<Button-1>", lambda _event, chosen=color: self._select_color(chosen))
            self.swatches[color] = swatch

        self._build_sound(outer)

        self._number_field(
            outer,
            "Frequency",
            "How often this reminder appears.",
            "freq",
            self.reminder.frequency_minutes if self.reminder else 30,
        )
        self._number_field(
            outer,
            "Timer",
            "How long the activity lasts after you start it.",
            "dur",
            self.reminder.duration_minutes if self.reminder else 2,
        )

        self.error = tk.Label(
            outer,
            text="",
            bg=BG,
            fg=DANGER,
            font=(self.family, 11),
            anchor="w",
            wraplength=400,
            justify="left",
        )
        self.error.pack(fill="x", pady=(4, 8))

        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x")
        FlatButton(
            actions,
            "Save",
            self._save,
            bg=INK,
            fg="#fffdf9",
            hover="#3a342c",
            font=(self.family, 13, "bold"),
            padx=12,
            pady=8,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        FlatButton(
            actions,
            "Cancel",
            self.destroy,
            bg=CHIP,
            fg=INK,
            hover=CHIP_HOVER,
            font=(self.family, 13),
            padx=12,
            pady=8,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))
        self._paint()

    def _build_sound(self, outer):
        tk.Label(outer, text="Sound", bg=BG, fg=INK, font=(self.family, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(outer, text="What plays when this reminder appears.", bg=BG, fg=MUTED,
                 font=(self.family, 11), anchor="w").pack(fill="x", pady=(2, 4))
        self.sound_var = tk.StringVar()
        row = tk.Frame(outer, bg=BG)
        row.pack(fill="x", pady=(0, 12))
        self.sound_menu = tk.OptionMenu(row, self.sound_var, "")
        self.sound_menu.configure(bg=CARD, fg=INK, activebackground=CHIP_HOVER, activeforeground=INK,
                                  highlightthickness=1, highlightbackground=LINE, relief="flat",
                                  font=(self.family, 12), anchor="w", width=22)
        self.sound_menu.pack(side="left")
        self.sound_play = FlatButton(
            row, "Play", self._play_sound, bg=CHIP, fg=INK, hover=CHIP_HOVER,
            font=(self.family, 12), padx=14, pady=5,
        )
        self.sound_play.pack(side="left", padx=(8, 0))
        self._fill_sound_menu(self.sound)

    def _fill_sound_menu(self, selected):
        """List every sound and show `selected` as the current one."""
        self.sound_options = sound_choices(selected)
        menu = self.sound_menu["menu"]
        menu.configure(font=(self.family, 12))
        menu.delete(0, "end")
        for value, label in self.sound_options:
            menu.add_command(label=label, command=lambda chosen=value: self._pick_sound(chosen))
        self.sound = selected
        self.sound_var.set(dict(self.sound_options)[selected])

    def _pick_sound(self, value):
        if value == SOUND_ADD:
            self._add_sound()
            return
        self.sound = value
        self.sound_var.set(dict(self.sound_options)[value])

    def _ask_sound_file(self):
        patterns = " ".join(f"*.{extension}" for extension in supported_extensions())
        return filedialog.askopenfilename(
            parent=self,
            title="Choose a sound",
            filetypes=[("Sounds", patterns), ("All files", "*.*")],
        )

    def _add_sound(self):
        """Let the person pick a sound file; keep their previous choice if it does not work out."""
        keep = self.sound
        path = self._ask_sound_file()
        if not path:
            self.sound_var.set(dict(self.sound_options)[keep])
            return
        try:
            value = add_custom_sound(path)
        except SoundImportError as problem:
            self.error.configure(text=str(problem))
            self.sound_var.set(dict(self.sound_options)[keep])
            return
        self.error.configure(text="")
        self._fill_sound_menu(value)
        self._play_sound()

    def _chosen_sound(self):
        label = self.sound_var.get()
        for value, text in self.sound_options:
            if text == label and value != SOUND_ADD:
                self.sound = value
                break
        return self.sound

    def _play_sound(self):
        if self.player is not None:
            self.player(self.kind, self._chosen_sound())

    def _number_field(self, parent, title, help_text, attr, value):
        tk.Label(parent, text=title, bg=BG, fg=INK, font=(self.family, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(parent, text=help_text, bg=BG, fg=MUTED, font=(self.family, 11),
                 anchor="w").pack(fill="x", pady=(2, 4))
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 10))
        entry = tk.Entry(
            row,
            bg=CARD,
            fg=INK,
            insertbackground=INK,
            relief="flat",
            width=6,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=INK,
            font=(self.mono, 13),
            justify="center",
        )
        entry.pack(side="left", ipady=4)
        entry.insert(0, str(value))
        tk.Label(row, text="minutes", bg=BG, fg=MUTED, font=(self.family, 11)).pack(side="left", padx=(8, 0))
        setattr(self, attr + "_entry", entry)

    def _kind_cell(self, parent, kind):
        frame = tk.Frame(parent, bg=BG, cursor="hand2", highlightthickness=2, bd=0)
        frame.pack(side="left", padx=(0, 6))
        canvas = tk.Canvas(frame, width=68, height=58, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        canvas.pack()
        label = tk.Label(frame, text=KINDS[kind]["label"], bg=BG, fg=MUTED, font=(self.family, 10), cursor="hand2")
        label.pack(pady=(0, 4))
        for widget in (frame, canvas, label):
            widget.bind("<Button-1>", lambda _event, chosen=kind: self._select_kind(chosen))
        return {"frame": frame, "canvas": canvas, "label": label}

    def _select_kind(self, kind):
        self.kind = kind
        if not self.color_touched:
            self.color = KINDS[kind]["color"]
        self._paint()

    def _select_color(self, color):
        self.color = color
        self.color_touched = True
        self._paint()

    def _paint(self):
        for kind, widgets in self.kind_widgets.items():
            selected = kind == self.kind
            bg = CARD if selected else BG
            widgets["frame"].configure(
                bg=bg,
                highlightbackground=self.color if selected else BG,
                highlightcolor=self.color if selected else BG,
            )
            widgets["canvas"].configure(bg=bg)
            widgets["label"].configure(bg=bg, fg=INK if selected else MUTED)
            color = self.color if selected else KINDS[kind]["color"]
            canvas = widgets["canvas"]
            canvas.delete("all")
            draw_sprite(
                canvas,
                kind,
                34,
                30,
                still_time(kind),
                color,
                scale=0.42,
                tag="sprite",
                ground=bg,
                hole=bg,
            )
        for color, swatch in self.swatches.items():
            selected = color.lower() == self.color.lower()
            swatch.configure(highlightbackground=INK if selected else BG, highlightcolor=INK if selected else BG)

    def _save(self):
        if self._saved:
            return
        name = " ".join(self.name_entry.get().split())
        if not name:
            self.error.configure(text="Give this reminder a name.")
            return
        if len(name) > 40:
            self.error.configure(text="Use 40 characters or fewer.")
            return
        try:
            frequency = int(self.freq_entry.get().strip())
            duration = int(self.dur_entry.get().strip())
        except ValueError:
            self.error.configure(text="Frequency and timer need whole minutes.")
            return
        if frequency < MIN_FREQUENCY or frequency > MAX_FREQUENCY:
            self.error.configure(
                text=f"Frequency should be {MIN_FREQUENCY}–{MAX_FREQUENCY} minutes."
            )
            return
        if duration < MIN_DURATION or duration > MAX_DURATION:
            self.error.configure(text=f"Timer should be {MIN_DURATION}–{MAX_DURATION} minutes.")
            return
        self._saved = True
        self.on_save(
            {
                "name": name,
                "kind": self.kind,
                "color": self.color,
                "sound": self._chosen_sound(),
                "frequency": frequency,
                "duration": duration,
            }
        )
        self.destroy()
