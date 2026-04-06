from smbus2 import SMBus


_devices = {}

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
    data = device["bus"].read_i2c_block_data(device["address"], device["reg_data_x0"], 6)
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

    _write_register(device, device["reg_power_control"], 0x00)
    _write_register(
        device,
        device["reg_data_format"],
        device["full_resolution_bit"] | _RANGE_BITS[range_g],
    )
    _write_register(device, device["reg_bandwidth_rate"], _DATA_RATE_BITS[rate_hz])
    _write_register(device, device["reg_power_control"], device["measure_bit"])

    device["range_g"] = range_g
    device["rate_hz"] = rate_hz


def init_imu(
    bus_number,
    address,
    reg_device_id,
    reg_bandwidth_rate,
    reg_power_control,
    reg_data_format,
    reg_data_x0,
    expected_device_id,
    measure_bit,
    full_resolution_bit,
    range_g,
    rate_hz,
    grams_per_lsb,
    standard_gravity,
):
    bus_number = int(bus_number)
    address = int(address)
    device = _open_device(bus_number, address)
    device["reg_device_id"] = int(reg_device_id)
    device["reg_bandwidth_rate"] = int(reg_bandwidth_rate)
    device["reg_power_control"] = int(reg_power_control)
    device["reg_data_format"] = int(reg_data_format)
    device["reg_data_x0"] = int(reg_data_x0)
    device["expected_device_id"] = int(expected_device_id)
    device["measure_bit"] = int(measure_bit)
    device["full_resolution_bit"] = int(full_resolution_bit)
    device["grams_per_lsb"] = float(grams_per_lsb)
    device["standard_gravity"] = float(standard_gravity)

    device_id = _read_register(device, device["reg_device_id"])
    if device_id != device["expected_device_id"]:
        raise RuntimeError(
            f"Unexpected ADXL345 device id 0x{device_id:02x} at bus {bus_number}, "
            f"address {hex(address)}."
        )

    _configure_device(device, int(range_g), float(rate_hz))


def read_raw(bus_number, address):
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)
    return _read_axes_raw(device)


def read_acceleration_g(bus_number, address):
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)
    raw_x, raw_y, raw_z = _read_axes_raw(device)
    return [
        raw_x * device["grams_per_lsb"],
        raw_y * device["grams_per_lsb"],
        raw_z * device["grams_per_lsb"],
    ]


def read_acceleration_ms2(bus_number, address):
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)
    x_g, y_g, z_g = read_acceleration_g(bus_number, address)
    return [
        x_g * device["standard_gravity"],
        y_g * device["standard_gravity"],
        z_g * device["standard_gravity"],
    ]


def read_x_g(bus_number, address):
    return read_acceleration_g(bus_number, address)[0]


def read_y_g(bus_number, address):
    return read_acceleration_g(bus_number, address)[1]


def read_z_g(bus_number, address):
    return read_acceleration_g(bus_number, address)[2]


def cleanup():
    for device in _devices.values():
        try:
            device["bus"].close()
        except Exception:
            pass

    _devices.clear()
