"""Ctrl+C as a key on Windows.

The Windows launcher is a .cmd file, so cmd.exe waits while the app runs. If Ctrl+C reaches the console
as a signal, cmd.exe remembers it and asks "Terminate batch job (Y/N)?" when the app ends, eating the
next line typed. The app therefore turns the console's Ctrl+C signal off for as long as it runs
(ENABLE_PROCESSED_INPUT): at the prompt prompt_toolkit reads Ctrl+C as a key anyway, and during an
answer ctrl_c_pressed() reads it from the keyboard. On macOS and Linux nothing changes: Ctrl+C is SIGINT.
"""
import atexit
import sys

from fusion_agent import term

ENABLE_PROCESSED_INPUT = 0x0001
_saved_mode = None


def _stdin_handle():
    import ctypes
    return ctypes.windll.kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE


def _console_mode():
    import ctypes
    mode = ctypes.c_uint32()
    if not ctypes.windll.kernel32.GetConsoleMode(_stdin_handle(), ctypes.byref(mode)):
        return None
    return mode.value


def _set_console_mode(value):
    import ctypes
    return bool(ctypes.windll.kernel32.SetConsoleMode(_stdin_handle(), value))


def take_ctrl_c_as_key():
    """Windows console only: Ctrl+C stops being a signal until the app exits. Returns True when done."""
    global _saved_mode
    if not term.IS_WINDOWS or not sys.stdin.isatty():
        return False
    try:
        mode = _console_mode()
        if mode is None:
            return False
        if not _set_console_mode(mode & ~ENABLE_PROCESSED_INPUT):
            return False
    except (AttributeError, OSError):
        return False
    _saved_mode = mode
    atexit.register(restore)
    return True


def keep_ctrl_c_as_key():
    """prompt_toolkit restores the mode it found when a prompt ends; call this after each prompt."""
    if _saved_mode is None:
        return
    try:
        mode = _console_mode()
        if mode is not None and mode & ENABLE_PROCESSED_INPUT:
            _set_console_mode(mode & ~ENABLE_PROCESSED_INPUT)
    except (AttributeError, OSError):
        pass


def restore():
    global _saved_mode
    if _saved_mode is None:
        return
    try:
        _set_console_mode(_saved_mode)
    except (AttributeError, OSError):
        pass
    _saved_mode = None


def ctrl_c_pressed():
    """True when Ctrl+C was typed since the last call (Windows, while the signal is off). Other keys
    typed during an answer are dropped: the next request is typed at the prompt."""
    if _saved_mode is None:
        return False
    import msvcrt
    is_pressed = False
    while msvcrt.kbhit():
        if msvcrt.getwch() == "\x03":
            is_pressed = True
    return is_pressed
