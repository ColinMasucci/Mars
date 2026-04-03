from gpiozero import OutputDevice, PWMOutputDevice


_devices = {}
_MAX_MOTOR_OUTPUT = 0.8


def _device_key(kind, pin):
    return f"{kind}:{pin}"


def _get_sleep_device(pin):
    key = _device_key("sleep", pin)
    if key not in _devices:
        _devices[key] = OutputDevice(pin, initial_value=True)
    else:
        _devices[key].on()
    return _devices[key]


def _get_pwm_device(pin):
    key = _device_key("pwm", pin)
    if key not in _devices:
        _devices[key] = PWMOutputDevice(pin, frequency=1000)
    return _devices[key]


def _require_device(kind, pin):
    key = _device_key(kind, pin)
    if key not in _devices:
        raise RuntimeError(
            f"Motor pin {pin} is not initialized. Call init_motor() first."
        )
    return _devices[key]


def init_motor(forward_pin, backward_pin, sleep_pin):
    _get_sleep_device(sleep_pin).on()
    _get_pwm_device(forward_pin)
    _get_pwm_device(backward_pin)


def drive_motor(forward_pin, backward_pin, sleep_pin, speed):
    _require_device("sleep", sleep_pin).on()
    forward = _require_device("pwm", forward_pin)
    backward = _require_device("pwm", backward_pin)
    speed = max(-1.0, min(1.0, speed)) * _MAX_MOTOR_OUTPUT

    if speed > 0:
        forward.value = speed
        backward.value = 0
    elif speed < 0:
        forward.value = 0
        backward.value = -speed
    else:
        forward.value = 0
        backward.value = 0


def stop_motor(forward_pin, backward_pin, sleep_pin):
    drive_motor(forward_pin, backward_pin, sleep_pin, 0)


def cleanup():
    for device in _devices.values():
        try:
            device.close()
        except Exception:
            pass

    _devices.clear()
