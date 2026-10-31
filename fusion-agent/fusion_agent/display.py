"""Inline pictures in the terminal, best effort: iTerm2 / WezTerm, Kitty / Ghostty, Sixel (Windows
Terminal 1.22+). Anywhere else, and on any error, show_image() returns False and the caller prints
the path. Set FUSION_AGENT_INLINE_IMAGES=off to turn it off, or to iterm|kitty|sixel to force one."""
import base64
import os
import shutil
import sys

DISPLAY_COLUMNS = 60
SIXEL_WIDTH_PX = 520
SIXEL_COLORS = 128


def detect_protocol(environ=None):
    environ = os.environ if environ is None else environ
    forced = environ.get("FUSION_AGENT_INLINE_IMAGES", "").strip().lower()
    if forced in ("off", "none", "0", "no"):
        return None
    if forced in ("iterm", "kitty", "sixel"):
        return forced
    if environ.get("TMUX") or environ.get("STY"):
        return None
    term_program = environ.get("TERM_PROGRAM", "")
    if term_program in ("iTerm.app", "WezTerm") or environ.get("LC_TERMINAL") == "iTerm2":
        return "iterm"
    if environ.get("KITTY_WINDOW_ID") or environ.get("TERM") == "xterm-kitty" or term_program == "ghostty":
        return "kitty"
    if environ.get("WT_SESSION"):
        return "sixel"
    return None


def show_image(path):
    """Draw the PNG at path below the cursor. True when it was drawn."""
    if not sys.stdout.isatty():
        return False
    protocol = detect_protocol()
    if protocol is None:
        return False
    try:
        with open(path, "rb") as file:
            png_bytes = file.read()
        columns = min(DISPLAY_COLUMNS, max(20, shutil.get_terminal_size((100, 24)).columns - 4))
        if protocol == "iterm":
            data = iterm_sequence(png_bytes, columns)
        elif protocol == "kitty":
            data = kitty_sequence(png_bytes, columns)
        else:
            data = sixel_sequence_from_png(png_bytes)
        sys.stdout.write(data + "\n")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def iterm_sequence(png_bytes, columns):
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return "\x1b]1337;File=inline=1;size=%d;width=%d;preserveAspectRatio=1:%s\x07" % (
        len(png_bytes), columns, encoded)


def kitty_sequence(png_bytes, columns):
    """Kitty graphics protocol: transmit and display a PNG in 4096-byte chunks."""
    encoded = base64.b64encode(png_bytes).decode("ascii")
    chunks = [encoded[index:index + 4096] for index in range(0, len(encoded), 4096)]
    parts = []
    for index, chunk in enumerate(chunks):
        has_more = 1 if index < len(chunks) - 1 else 0
        if index == 0:
            parts.append("\x1b_Ga=T,f=100,c=%d,m=%d;%s\x1b\\" % (columns, has_more, chunk))
        else:
            parts.append("\x1b_Gm=%d;%s\x1b\\" % (has_more, chunk))
    return "".join(parts)


def sixel_sequence_from_png(png_bytes):
    import io
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as image:
        rgb = image.convert("RGB")
    if rgb.width > SIXEL_WIDTH_PX:
        height = max(1, round(rgb.height * SIXEL_WIDTH_PX / rgb.width))
        rgb = rgb.resize((SIXEL_WIDTH_PX, height), Image.LANCZOS)
    paletted = rgb.quantize(colors=SIXEL_COLORS, dither=Image.Dither.NONE)
    return sixel_sequence(paletted)


def _sixel_run(char, count):
    if count >= 4:
        return "!%d%s" % (count, char)
    return char * count


def sixel_sequence(paletted):
    """Encode a palette ("P" mode) Pillow image as a Sixel string."""
    width, height = paletted.size
    palette = paletted.getpalette() or []
    pixels = paletted.load()
    used_colors = sorted(index for _, index in paletted.getcolors(256))
    parts = ["\x1bP0;1;0q", '"1;1;%d;%d' % (width, height)]
    for color in used_colors:
        red, green, blue = palette[color * 3:color * 3 + 3] if len(palette) >= color * 3 + 3 else (0, 0, 0)
        parts.append("#%d;2;%d;%d;%d" % (color, red * 100 // 255, green * 100 // 255, blue * 100 // 255))
    for band_top in range(0, height, 6):
        # bits[color][x]: which of the six rows of this band have that color at column x.
        bits = {}
        for row in range(6):
            y = band_top + row
            if y >= height:
                break
            for x in range(width):
                color = pixels[x, y]
                column_bits = bits.get(color)
                if column_bits is None:
                    column_bits = [0] * width
                    bits[color] = column_bits
                column_bits[x] |= 1 << row
        band_parts = []
        for color, column_bits in bits.items():
            line = ["#%d" % color]
            run_char = None
            run_count = 0
            for value in column_bits:
                char = chr(63 + value)
                if char == run_char:
                    run_count += 1
                    continue
                if run_char is not None:
                    line.append(_sixel_run(run_char, run_count))
                run_char = char
                run_count = 1
            # Trailing empty columns ("?") need not be sent.
            if run_char is not None and run_char != "?":
                line.append(_sixel_run(run_char, run_count))
            band_parts.append("".join(line))
        parts.append("$".join(band_parts) + "-")
    parts.append("\x1b\\")
    return "".join(parts)
