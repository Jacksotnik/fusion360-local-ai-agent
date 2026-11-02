"""Terminal helpers: colors, status symbols, OS name. Everything degrades to plain text."""
import os
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def os_name():
    if IS_WINDOWS:
        return "windows"
    if IS_MAC:
        return "macos"
    return "linux"


def _enable_windows_vt():
    """Turn on ANSI escape handling in the Windows console; False when it is not possible."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_virtual_terminal_processing = 0x0004
        if mode.value & enable_virtual_terminal_processing:
            return True
        return bool(kernel32.SetConsoleMode(handle, mode.value | enable_virtual_terminal_processing))
    except (AttributeError, OSError):
        return False


def _detect_color():
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if IS_WINDOWS:
        return _enable_windows_vt()
    return os.environ.get("TERM") != "dumb"


def _detect_unicode_symbols():
    """The classic Windows console font has no glyphs for check marks and braille spinners."""
    if not IS_WINDOWS:
        return True
    return bool(os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") or os.environ.get("ConEmuANSI"))


HAS_COLOR = _detect_color()
HAS_UNICODE_SYMBOLS = _detect_unicode_symbols()

GREY = "90"
RED = "31"
GREEN = "32"
YELLOW = "33"
CYAN = "36"
BOLD = "1"

if HAS_UNICODE_SYMBOLS:
    SYMBOLS = {"ok": "✔", "warn": "!", "fail": "✖", "skip": "○", "bullet": "•", "prompt": "›"}
    SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
else:
    SYMBOLS = {"ok": "+", "warn": "!", "fail": "x", "skip": "-", "bullet": "*", "prompt": ">"}
    SPINNER_FRAMES = "|/-\\"

STATUS_COLORS = {"ok": GREEN, "warn": YELLOW, "fail": RED, "skip": GREY}


def paint(text, color):
    if not HAS_COLOR or not color:
        return text
    return "\x1b[%sm%s\x1b[0m" % (color, text)


def status_mark(status):
    return paint(SYMBOLS.get(status, "?"), STATUS_COLORS.get(status))
