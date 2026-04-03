from gpiozero import OutputDevice, PWMOutputDevice
from time import sleep


HAT_MOTOR_PINS = {
    1: {"forward": 17, "backward": 27, "sleep": 12},
    2: {"forward": 22, "backward": 23, "sleep": 12},
    3: {"forward": 24, "backward": 25, "sleep": 13},
    4: {"forward": 26, "backward": 16, "sleep": 13},
}

_devices = {}


def _clamp_speed(speed):
    return max(-1.0, min(1.0, float(speed)))


def _motor_key(port, direction):
    return f"motor:{port}:{direction}"


def _sleep_key(pin):
    return f"sleep:{pin}"


def init_motor(port):
    if port not in HAT_MOTOR_PINS:
        raise ValueError(f"Unknown motor port: {port}")

    pins = HAT_MOTOR_PINS[port]
    forward_key = _motor_key(port, "forward")
    backward_key = _motor_key(port, "backward")
    sleep_key = _sleep_key(pins["sleep"])

    if sleep_key not in _devices:
        _devices[sleep_key] = OutputDevice(pins["sleep"], initial_value=True)
    else:
        _devices[sleep_key].on()

    if forward_key not in _devices:
        _devices[forward_key] = PWMOutputDevice(pins["forward"], frequency=1000)
    if backward_key not in _devices:
        _devices[backward_key] = PWMOutputDevice(pins["backward"], frequency=1000)


def set_motor(port, speed):
    init_motor(port)
    speed = _clamp_speed(speed)

    forward = _devices[_motor_key(port, "forward")]
    backward = _devices[_motor_key(port, "backward")]

    if speed > 0:
        forward.value = speed
        backward.value = 0
    elif speed < 0:
        forward.value = 0
        backward.value = -speed
    else:
        forward.value = 0
        backward.value = 0


def stop_motor(port):
    set_motor(port, 0)


def spin_motor(port, speed, duration):
    set_motor(port, speed)
    sleep(duration)
    stop_motor(port)


def stop_all():
    for port in HAT_MOTOR_PINS:
        stop_motor(port)


def cleanup():
    stop_all()

    for device in _devices.values():
        try:
            device.close()
        except Exception:
            pass

    _devices.clear()
