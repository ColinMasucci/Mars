import atexit
import os
import sys
import termios
import tty


_fd = None
_settings = None


def _start_keyboard():
    global _fd, _settings

    if _fd is not None:
        return

    if not sys.stdin.isatty():
        raise RuntimeError("Keyboard input requires a terminal.")

    _fd = sys.stdin.fileno()
    _settings = termios.tcgetattr(_fd)
    tty.setcbreak(_fd)


def _ensure_started():
    if _fd is None:
        _start_keyboard()


def read_key():
    _ensure_started()

    while True:
        key = os.read(_fd, 1).decode("utf-8", errors="ignore")

        if key == "w":
            return "up"
        if key == "a":
            return "left"
        if key == "s":
            return "down"
        if key == "d":
            return "right"
        if key == "q":
            return "quit"

        if key == "\x1b":
            rest = os.read(_fd, 2).decode("utf-8", errors="ignore")
            if rest == "[A":
                return "up"
            if rest == "[D":
                return "left"
            if rest == "[B":
                return "down"
            if rest == "[C":
                return "right"


def cleanup():
    global _fd, _settings

    if _fd is None or _settings is None:
        return

    termios.tcsetattr(_fd, termios.TCSADRAIN, _settings)
    _fd = None
    _settings = None


atexit.register(cleanup)
