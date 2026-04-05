from smbus2 import SMBus


_devices = {}

_DEFAULT_BUS = 1
_DEFAULT_ADDRESS = 0x53

_REG_DEVID = 0x00
_REG_BW_RATE = 0x2C
_REG_POWER_CTL = 0x2D
_REG_DATA_FORMAT = 0x31
_REG_DATAX0 = 0x32

_EXPECTED_DEVICE_ID = 0xE5
_MEASURE_BIT = 0x08
_FULL_RES_BIT = 0x08
_G_PER_LSB = 0.00390625
_STANDARD_GRAVITY = 9.80665

_RANGE_BITS = {
    2: 0x00,
    4: 0x01,
    8: 0x02,
    16: 0x03,
}

_DATA_RATE_BITS = {
    12.5: 0x07,
    25.0: 0x08,
    50.0: 0x09,
    100.0: 0x0A,
    200.0: 0x0B,
    400.0: 0x0C,
}


def _device_key(bus_number, address):
    return f"{bus_number}:{address}"


def _normalize_address(address):
    if isinstance(address, str):
        return int(address, 0)
    return int(address)


def _open_device(bus_number, address):
    key = _device_key(bus_number, address)
    if key not in _devices:
        bus = SMBus(bus_number)
        _devices[key] = {
            "bus": bus,
            "bus_number": bus_number,
            "address": address,
        }
    return _devices[key]


def _require_device(bus_number, address):
    key = _device_key(bus_number, address)
    if key not in _devices:
        raise RuntimeError(
            f"ADXL345 at bus {bus_number}, address {hex(address)} is not initialized. "
            "Call init_imu() first."
        )
    return _devices[key]


def _write_register(device, register, value):
    device["bus"].write_byte_data(device["address"], register, value)


def _read_register(device, register):
    return device["bus"].read_byte_data(device["address"], register)


def _read_axes_raw(device):
    data = device["bus"].read_i2c_block_data(device["address"], _REG_DATAX0, 6)
    axes = []
    for index in range(0, 6, 2):
        value = data[index] | (data[index + 1] << 8)
        if value >= 0x8000:
            value -= 0x10000
        axes.append(value)
    return axes


def _configure_device(device, range_g, rate_hz):
    if range_g not in _RANGE_BITS:
        raise ValueError("range_g must be one of: 2, 4, 8, 16")
    if rate_hz not in _DATA_RATE_BITS:
        raise ValueError("rate_hz must be one of: 12.5, 25, 50, 100, 200, 400")

    _write_register(device, _REG_POWER_CTL, 0x00)
    _write_register(device, _REG_DATA_FORMAT, _FULL_RES_BIT | _RANGE_BITS[range_g])
    _write_register(device, _REG_BW_RATE, _DATA_RATE_BITS[rate_hz])
    _write_register(device, _REG_POWER_CTL, _MEASURE_BIT)

    device["range_g"] = range_g
    device["rate_hz"] = rate_hz


def init_imu(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS, range_g=2, rate_hz=100.0):
    bus_number = int(bus_number)
    address = _normalize_address(address)
    device = _open_device(bus_number, address)

    device_id = _read_register(device, _REG_DEVID)
    if device_id != _EXPECTED_DEVICE_ID:
        raise RuntimeError(
            f"Unexpected ADXL345 device id 0x{device_id:02x} at bus {bus_number}, "
            f"address {hex(address)}."
        )

    _configure_device(device, int(range_g), float(rate_hz))


def read_raw(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    bus_number = int(bus_number)
    address = _normalize_address(address)
    device = _require_device(bus_number, address)
    return _read_axes_raw(device)


def read_acceleration_g(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    raw_x, raw_y, raw_z = read_raw(bus_number, address)
    return [
        raw_x * _G_PER_LSB,
        raw_y * _G_PER_LSB,
        raw_z * _G_PER_LSB,
    ]


def read_acceleration_ms2(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    x_g, y_g, z_g = read_acceleration_g(bus_number, address)
    return [
        x_g * _STANDARD_GRAVITY,
        y_g * _STANDARD_GRAVITY,
        z_g * _STANDARD_GRAVITY,
    ]


def read_x_g(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    return read_acceleration_g(bus_number, address)[0]


def read_y_g(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    return read_acceleration_g(bus_number, address)[1]


def read_z_g(bus_number=_DEFAULT_BUS, address=_DEFAULT_ADDRESS):
    return read_acceleration_g(bus_number, address)[2]


def cleanup():
    for device in _devices.values():
        try:
            device["bus"].close()
        except Exception:
            pass

    _devices.clear()
