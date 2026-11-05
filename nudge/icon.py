"""The Nudge app icon, drawn from scratch so no image libraries are needed.

A dark rounded square with a timer ring. Four dots on the ring use the colors of
the four built-in reminders. `render_png(size)` returns PNG bytes; the other
functions pack those into the icon formats macOS (.icns) and Windows (.ico) use.
"""

import math
import struct
import zlib

from nudge.models import KINDS
from nudge.theme import CARD, INK


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _segment(px, py, ax, ay, bx, by):
    """Distance from a point to a line segment."""
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rounded_square(px, py, half, radius):
    qx, qy = abs(px - 0.5) - half + radius, abs(py - 0.5) - half + radius
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - radius


def _shapes():
    """(color, distance function) from bottom to top. Negative distance means inside."""
    ink, cream = _rgb(INK), _rgb(CARD)
    shapes = [(ink, lambda x, y: _rounded_square(x, y, 0.46, 0.21))]
    shapes.append((cream, lambda x, y: abs(math.hypot(x - 0.5, y - 0.5) - 0.285) - 0.028))
    shapes.append((cream, lambda x, y: _segment(x, y, 0.5, 0.5, 0.5, 0.33) - 0.026))
    shapes.append((cream, lambda x, y: _segment(x, y, 0.5, 0.5, 0.61, 0.5) - 0.026))
    shapes.append((cream, lambda x, y: math.hypot(x - 0.5, y - 0.5) - 0.045))
    for kind, angle in zip(("water", "walk", "rest", "stretch"), (0, 90, 180, 270)):
        cx = 0.5 + 0.285 * math.sin(math.radians(angle))
        cy = 0.5 - 0.285 * math.cos(math.radians(angle))
        shapes.append((_rgb(KINDS[kind]["color"]),
                       lambda x, y, cx=cx, cy=cy: math.hypot(x - cx, y - cy) - 0.062))
    return shapes


def _pixels(size):
    shapes = _shapes()
    pixel = 1.0 / size
    rows = bytearray()
    for row in range(size):
        rows.append(0)  # PNG filter: none
        y = (row + 0.5) * pixel
        for column in range(size):
            x = (column + 0.5) * pixel
            red = green = blue = alpha = 0.0
            for color, distance in shapes:
                cover = 0.5 - distance(x, y) / pixel
                if cover <= 0.0:
                    continue
                cover = min(cover, 1.0)
                out = cover + alpha * (1.0 - cover)
                red = (color[0] * cover + red * alpha * (1.0 - cover)) / out
                green = (color[1] * cover + green * alpha * (1.0 - cover)) / out
                blue = (color[2] * cover + blue * alpha * (1.0 - cover)) / out
                alpha = out
            rows += bytes((int(red + 0.5), int(green + 0.5), int(blue + 0.5), int(alpha * 255 + 0.5)))
    return bytes(rows)


def render_png(size):
    """The icon as a square RGBA PNG, `size` pixels wide."""
    if size < 8:
        raise ValueError("icons smaller than 8 pixels are not supported")

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(_pixels(size), 9))
        + chunk(b"IEND", b"")
    )


def png_size(data):
    """(width, height) of PNG bytes. Used to check what was written."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


# macOS .icns: a list of (type code, pixel size). Each holds a PNG.
ICNS_PARTS = (
    (b"ic11", 32), (b"ic12", 64), (b"ic07", 128), (b"ic13", 256),
    (b"ic08", 256), (b"ic14", 512), (b"ic09", 512),
)
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def build_icns(png_for):
    """Pack PNGs into a macOS icon. `png_for(size)` returns the PNG for that size."""
    parts = b"".join(
        code + struct.pack(">I", len(data) + 8) + data
        for code, data in ((code, png_for(size)) for code, size in ICNS_PARTS)
    )
    return b"icns" + struct.pack(">I", len(parts) + 8) + parts


def build_ico(png_for):
    """Pack PNGs into a Windows icon. `png_for(size)` returns the PNG for that size."""
    images = [(size, png_for(size)) for size in ICO_SIZES]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in images:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return out + b"".join(data for _size, data in images)


if __name__ == "__main__":
    # Regenerates the picture the window shows in the Dock / taskbar.
    import pathlib

    target = pathlib.Path(__file__).resolve().parent / "assets" / "icon-256.png"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(render_png(256))
    print("wrote", target)
