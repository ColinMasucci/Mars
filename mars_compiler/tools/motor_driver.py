from gpiozero import OutputDevice, PWMOutputDevice
from time import sleep

# Internal storage for devices
_devices = {}


# ----------------------------
# Initialize motor pins
# ----------------------------
def init(in1, in2, ena):
    global _devices

    if in1 not in _devices:
        _devices[in1] = OutputDevice(in1)
    if in2 not in _devices:
        _devices[in2] = OutputDevice(in2)
    if ena not in _devices:
        _devices[ena] = PWMOutputDevice(ena)


# ----------------------------
# Drive motor
# speed: -1.0 to 1.0
# ----------------------------
def drive(in1, in2, ena, speed):
    global _devices

    if speed > 0:
        _devices[in1].on()
        _devices[in2].off()
        _devices[ena].value = speed

    elif speed < 0:
        _devices[in1].off()
        _devices[in2].on()
        _devices[ena].value = -speed

    else:
        _devices[in1].off()
        _devices[in2].off()
        _devices[ena].value = 0


def wait(time):
    sleep(time)    


# ----------------------------
# Stop motor
# ----------------------------
def stop(in1, in2, ena):
    global _devices

    _devices[in1].off()
    _devices[in2].off()
    _devices[ena].value = 0


# ----------------------------
# Optional cleanup (good practice)
# ----------------------------
def cleanup():
    global _devices

    for device in _devices.values():
        try:
            device.close()
        except:
            pass

    _devices.clear()