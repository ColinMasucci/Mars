import math
import time

from smbus2 import SMBus


_devices = {}

_MPU6050_ACCEL_CONFIG_BITS = {
    2: 0x00,
    4: 0x08,
    8: 0x10,
    16: 0x18,
}

_MPU6050_GYRO_CONFIG_BITS = {
    250: 0x00,
    500: 0x08,
    1000: 0x10,
    2000: 0x18,
}


def _device_key(bus_number, address):
    return f"{bus_number}:{address}"


def _open_device(bus_number, address):
    key = _device_key(bus_number, address)
    if key not in _devices:
        _devices[key] = {
            "bus": SMBus(bus_number),
            "bus_number": bus_number,
            "address": address,
        }
    return _devices[key]


def _require_device(bus_number, address):
    key = _device_key(bus_number, address)
    if key not in _devices:
        raise RuntimeError(
            f"MPU6050 at bus {bus_number}, address {hex(address)} is not initialized. "
            "Call init_mpu6050() first."
        )
    return _devices[key]


def _write_register(device, register, value):
    device["bus"].write_byte_data(device["address"], register, value)


def _read_register(device, register):
    return device["bus"].read_byte_data(device["address"], register)


def _read_axes_raw(device, start_register):
    data = device["bus"].read_i2c_block_data(device["address"], start_register, 6)
    axes = []
    for index in range(0, 6, 2):
        value = (data[index] << 8) | data[index + 1]
        if value >= 0x8000:
            value -= 0x10000
        axes.append(value)
    return axes


def _configure_mpu6050(device, accel_range_g, gyro_range_dps, dlpf_config, sample_rate_div):
    if accel_range_g not in _MPU6050_ACCEL_CONFIG_BITS:
        raise ValueError("accel_range_g must be one of: 2, 4, 8, 16")
    if gyro_range_dps not in _MPU6050_GYRO_CONFIG_BITS:
        raise ValueError("gyro_range_dps must be one of: 250, 500, 1000, 2000")
    if not 0 <= int(dlpf_config) <= 6:
        raise ValueError("dlpf_config must be between 0 and 6")
    if not 0 <= int(sample_rate_div) <= 255:
        raise ValueError("sample_rate_div must be between 0 and 255")

    # A device reset takes a short time; if we program registers immediately
    # afterward the MPU6050 can remain asleep and return all-zero samples.
    _write_register(device, device["reg_power_mgmt_1"], 0x80)
    time.sleep(0.1)
    _write_register(device, device["reg_power_mgmt_1"], 0x00)
    time.sleep(0.01)
    _write_register(device, device["reg_power_mgmt_1"], device["clock_source_bits"])
    time.sleep(0.01)
    _write_register(device, device["reg_config"], int(dlpf_config))
    _write_register(device, device["reg_sample_rate_div"], int(sample_rate_div))
    _write_register(device, device["reg_gyro_config"], _MPU6050_GYRO_CONFIG_BITS[gyro_range_dps])
    _write_register(device, device["reg_accel_config"], _MPU6050_ACCEL_CONFIG_BITS[accel_range_g])

    device["accel_g_per_lsb"] = float(accel_range_g) / 32768.0
    device["gyro_dps_per_lsb"] = float(gyro_range_dps) / 32768.0
    device["standard_gravity"] = float(device["standard_gravity"])


def init_mpu6050(
    bus_number,
    address,
    reg_device_id,
    reg_power_mgmt_1,
    reg_sample_rate_div,
    reg_config,
    reg_gyro_config,
    reg_accel_config,
    reg_accel_xout_h,
    reg_gyro_xout_h,
    expected_device_id,
    clock_source_bits,
    accel_range_g,
    gyro_range_dps,
    dlpf_config,
    sample_rate_div,
    standard_gravity,
):
    bus_number = int(bus_number)
    address = int(address)
    device = _open_device(bus_number, address)
    device["reg_device_id"] = int(reg_device_id)
    device["reg_power_mgmt_1"] = int(reg_power_mgmt_1)
    device["reg_sample_rate_div"] = int(reg_sample_rate_div)
    device["reg_config"] = int(reg_config)
    device["reg_gyro_config"] = int(reg_gyro_config)
    device["reg_accel_config"] = int(reg_accel_config)
    device["reg_accel_xout_h"] = int(reg_accel_xout_h)
    device["reg_gyro_xout_h"] = int(reg_gyro_xout_h)
    device["expected_device_id"] = int(expected_device_id)
    device["clock_source_bits"] = int(clock_source_bits)
    device["standard_gravity"] = float(standard_gravity)

    device_id = _read_register(device, device["reg_device_id"])
    if device_id != device["expected_device_id"]:
        raise RuntimeError(
            f"Unexpected MPU6050 device id 0x{device_id:02x} at bus {bus_number}, "
            f"address {hex(address)}."
        )

    _configure_mpu6050(
        device,
        int(accel_range_g),
        int(gyro_range_dps),
        int(dlpf_config),
        int(sample_rate_div),
    )


def read_acceleration_g(bus_number, address):
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)
    raw_x, raw_y, raw_z = _read_axes_raw(device, device["reg_accel_xout_h"])
    scale = device["accel_g_per_lsb"]
    return [raw_x * scale, raw_y * scale, raw_z * scale]


def read_acceleration_ms2(bus_number, address):
    device = _require_device(int(bus_number), int(address))
    x_g, y_g, z_g = read_acceleration_g(bus_number, address)
    return [
        x_g * device["standard_gravity"],
        y_g * device["standard_gravity"],
        z_g * device["standard_gravity"],
    ]


def read_angular_velocity_dps(bus_number, address):
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)
    raw_x, raw_y, raw_z = _read_axes_raw(device, device["reg_gyro_xout_h"])
    scale = device["gyro_dps_per_lsb"]
    return [raw_x * scale, raw_y * scale, raw_z * scale]


def read_angular_velocity_rads(bus_number, address):
    degrees_to_radians = math.pi / 180.0
    return [
        axis * degrees_to_radians
        for axis in read_angular_velocity_dps(bus_number, address)
    ]


def read_pose_rpy_complementary(bus_number, address, alpha=0.98, dt_hint=0.0):
    """
    Return [roll, pitch, yaw] in radians using a simple complementary filter.
    Roll/pitch blend gyro integration with accel tilt estimate.
    Yaw integrates gyro z-rate (no magnetometer absolute reference).
    """
    bus_number = int(bus_number)
    address = int(address)
    device = _require_device(bus_number, address)

    alpha = float(alpha)
    if alpha < 0.0:
        alpha = 0.0
    if alpha > 1.0:
        alpha = 1.0

    dt_hint = float(dt_hint)
    now = time.monotonic()
    last_t = device.get("pose_last_time")
    if last_t is None:
        dt = dt_hint if dt_hint > 0.0 else 1.0 / 100.0
    else:
        dt = now - last_t
        if dt <= 0.0:
            dt = dt_hint if dt_hint > 0.0 else 1.0 / 100.0
    device["pose_last_time"] = now

    roll = float(device.get("pose_roll", 0.0))
    pitch = float(device.get("pose_pitch", 0.0))
    yaw = float(device.get("pose_yaw", 0.0))

    ax, ay, az = read_acceleration_ms2(bus_number, address)
    gx, gy, gz = read_angular_velocity_rads(bus_number, address)

    accel_roll = math.atan2(ay, az)
    accel_pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))

    roll_gyro = roll + gx * dt
    pitch_gyro = pitch + gy * dt
    yaw_gyro = yaw + gz * dt

    roll = alpha * roll_gyro + (1.0 - alpha) * accel_roll
    pitch = alpha * pitch_gyro + (1.0 - alpha) * accel_pitch
    yaw = math.atan2(math.sin(yaw_gyro), math.cos(yaw_gyro))

    device["pose_roll"] = roll
    device["pose_pitch"] = pitch
    device["pose_yaw"] = yaw

    return [roll, pitch, yaw]


def read_orientation_quat_complementary(bus_number, address, alpha=0.98, dt_hint=0.0):
    roll, pitch, yaw = read_pose_rpy_complementary(bus_number, address, alpha, dt_hint)

    half_roll = roll * 0.5
    half_pitch = pitch * 0.5
    half_yaw = yaw * 0.5

    cr = math.cos(half_roll)
    sr = math.sin(half_roll)
    cp = math.cos(half_pitch)
    sp = math.sin(half_pitch)
    cy = math.cos(half_yaw)
    sy = math.sin(half_yaw)

    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    w = cr * cp * cy + sr * sp * sy
    return [x, y, z, w]


def cleanup():
    for device in _devices.values():
        try:
            device["bus"].close()
        except Exception:
            pass

    _devices.clear()
