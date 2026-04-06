import atexit
import os
import select
import sys
import termios
import tty


_fd = None
_settings = None
_INSTRUCTIONS = """keyboard_input controls:
w: up
a: left
s: stop
d: right
q: up_left
e: up_right
x: down
z: down_left
c: down_right
up arrow: increase speed
down arrow: decrease speed
left arrow: increase turn rate
right arrow: decrease turn rate
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
            return "none"

        key = os.read(_fd, 1).decode("utf-8", errors="ignore").lower()

        if key == "w":
            return "up"
        if key == "a":
            return "left"
        if key == "s":
            return "stop"
        if key == "d":
            return "right"
        if key == "x":
            return "down"
        if key == "q":
            return "up_left"
        if key == "e":
            return "up_right"
        if key == "z":
            return "down_left"
        if key == "c":
            return "down_right"
        if key == "?" or key == "/":
            print_instructions()
            continue

        if key == "\x1b":
            readable, _, _ = select.select([_fd], [], [], 0.01)
            if not readable:
                return "quit"

            rest = os.read(_fd, 2).decode("utf-8", errors="ignore")
            if rest == "[A":
                return "speed_up"
            if rest == "[B":
                return "speed_down"
            if rest == "[D":
                return "turn_up"
            if rest == "[C":
                return "turn_down"


def read_command(timeout=0.0):
    key = read_key(timeout)
    if key is None:
        return "stop"
    return key


def cleanup():
    global _fd, _settings

    if _fd is None or _settings is None:
        return

    termios.tcsetattr(_fd, termios.TCSADRAIN, _settings)
    _fd = None
    _settings = None


atexit.register(cleanup)
