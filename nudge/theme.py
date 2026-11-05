"""Colors and fonts for the Nudge window."""

BG = "#f6f3ee"
INK = "#1f1d1a"
MUTED = "#6f6a62"
CARD = "#fffdf9"
LINE = "#e6dfd4"
CHIP = "#f1ebe3"
CHIP_HOVER = "#e5ddd2"
WARN = "#9a5b12"
DANGER = "#9c3b32"
OK = "#1f7a4d"
OK_HOVER = "#176240"
TRACK = "#ece6dc"

OVERLAY_BG = "#1c1917"
OVERLAY_FG = "#f6f1e8"
OVERLAY_MUTED = "#b7b0a4"
OVERLAY_BUTTON = "#2c2824"
OVERLAY_BUTTON_HOVER = "#3c3833"
MEETING_BG = "#3f3226"
MEETING_FG = "#f3ddc4"
MEETING_HOVER = "#554433"

TAGLINE = "Timers for the breaks you mean to take."


def mix(color, other, amount):
    """Blend `color` toward `other`. amount=1 returns `other`."""
    try:
        def parts(value):
            value = value.lstrip("#")
            return (
                int(value[0:2], 16),
                int(value[2:4], 16),
                int(value[4:6], 16),
            )

        red, green, blue = parts(color)
        target_red, target_green, target_blue = parts(other)
        red = int(red + (target_red - red) * amount)
        green = int(green + (target_green - green) * amount)
        blue = int(blue + (target_blue - blue) * amount)
        return f"#{red:02x}{green:02x}{blue:02x}"
    except (ValueError, IndexError, AttributeError):
        return other


def pick_family(root):
    import tkinter.font as tkfont

    families = set(tkfont.families(root))
    for name in (
        "Avenir Next", "Avenir", "Helvetica Neue", "Segoe UI", "Cantarell", "Ubuntu", "Noto Sans",
        "DejaVu Sans", "Helvetica",
    ):
        if name in families:
            return name
    return "Helvetica"


def pick_mono(root):
    import tkinter.font as tkfont

    families = set(tkfont.families(root))
    for name in ("Menlo", "Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New", "Courier"):
        if name in families:
            return name
    return "Courier"
