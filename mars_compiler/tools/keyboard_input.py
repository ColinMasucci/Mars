import atexit
import os
import select
import sys
import termios
import tty


_fd = None
_settings = None
_INSTRUCTIONS = """keyboard_input controls:
w or up arrow: up
a or left arrow: left
s or down arrow: down
d or right arrow: right
q: up_left
e: up_right
z: down_left
c: down_right
?: print instructions
esc: quit
"""


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


def print_instructions():
    print(_INSTRUCTIONS)


def read_key(timeout=0.0):
    _ensure_started()

    while True:
        readable, _, _ = select.select([_fd], [], [], timeout)
        if not readable:
            return None

        key = os.read(_fd, 1).decode("utf-8", errors="ignore").lower()

        if key == "w":
            return "up"
        if key == "a":
            return "left"
        if key == "s":
            return "down"
        if key == "d":
            return "right"
        if key == "q":
            return "up_left"
        if key == "e":
            return "up_right"
        if key == "z":
            return "down_left"
        if key == "c":
            return "down_right"
        if key == "?":
            print_instructions()
            continue

        if key == "\x1b":
            readable, _, _ = select.select([_fd], [], [], 0.01)
            if not readable:
                return "quit"

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
