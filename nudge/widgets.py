"""Shared Tk widgets. Labels stand in for buttons so colors work on older Tk."""

import tkinter as tk

from nudge.sprites import draw_sprite, still_time
from nudge.theme import CARD, INK, MUTED, TRACK


class FlatButton(tk.Label):
    def __init__(self, master, text, command, bg, fg, hover, font, padx=12, pady=6):
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            padx=padx,
            pady=pady,
            cursor="hand2",
            takefocus=0,
            anchor="center",
        )
        self.command = command
        self._bg = bg
        self._hover = hover
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event):
        self.configure(bg=self._hover)

    def _on_leave(self, _event):
        self.configure(bg=self._bg)

    def _on_click(self, _event):
        if self.command is not None:
            self.command()

    def set_text(self, text):
        self.configure(text=text)

    def set_colors(self, bg, fg, hover):
        self._bg = bg
        self._hover = hover
        self.configure(bg=bg, fg=fg)


class ScrolledFrame(tk.Frame):
    def __init__(self, master, bg):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas_width = None
        self._scrollregion = None
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", self._wheel_up)
        self.bind_all("<Button-5>", self._wheel_down)

    def _on_inner(self, _event):
        region = self.canvas.bbox("all")
        if region != self._scrollregion:
            self._scrollregion = region
            self.canvas.configure(scrollregion=region)

    def _on_canvas(self, event):
        if event.width == self._canvas_width:
            return
        self._canvas_width = event.width
        self.canvas.itemconfigure(self._window, width=event.width)

    def _pointer_inside(self):
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        while widget is not None:
            if widget == self:
                return True
            widget = widget.master
        return False

    def _wheel(self, event):
        if not self._pointer_inside():
            return
        delta = getattr(event, "delta", 0)
        if not delta:
            return
        if abs(delta) >= 120:
            steps = int(-delta / 120) or (-1 if delta > 0 else 1)
        else:
            steps = -1 if delta > 0 else 1
        self.canvas.yview_scroll(steps, "units")

    def _wheel_up(self, _event):
        if self._pointer_inside():
            self.canvas.yview_scroll(-1, "units")

    def _wheel_down(self, _event):
        if self._pointer_inside():
            self.canvas.yview_scroll(1, "units")


class Ring(tk.Canvas):
    def __init__(self, master, size, family, mono):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=CARD,
            highlightthickness=0,
            bd=0,
        )
        self.size = size
        self.family = family
        self.mono = mono

    def render(self, fraction, color, kind, time_text):
        self.delete("all")
        size = self.size
        pad = 12
        self.create_oval(pad, pad, size - pad, size - pad, fill=CARD, outline=TRACK, width=10)
        if fraction > 0.001:
            extent = max(-359.5, -360.0 * min(1.0, fraction))
            self.create_arc(
                pad,
                pad,
                size - pad,
                size - pad,
                start=90,
                extent=extent,
                style="arc",
                outline=color,
                width=10,
            )
        center = size / 2.0
        if kind:
            draw_sprite(
                self,
                kind,
                center,
                center - 14,
                still_time(kind),
                color,
                scale=0.42,
                tag="sprite",
                ground=CARD,
                hole=CARD,
            )
            self.create_text(
                center,
                center + 32,
                text=time_text,
                fill=INK,
                font=(self.mono, 15, "bold"),
            )
        else:
            self.create_text(
                center,
                center + 2,
                text=time_text,
                fill=MUTED,
                font=(self.family, 22, "bold"),
            )


def paint_bar(canvas, fraction, color, width):
    canvas.delete("all")
    canvas.create_rectangle(0, 1, max(width, 1), 5, fill=TRACK, outline="")
    filled = int(max(0, width) * max(0.0, min(1.0, fraction)))
    if filled > 0:
        canvas.create_rectangle(0, 1, filled, 5, fill=color, outline="")
