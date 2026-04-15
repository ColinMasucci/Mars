import math
import time
from dataclasses import dataclass

try:
    import tkinter as tk
except Exception:
    tk = None


@dataclass
class _RobotShape:
    track_width: float
    wheelbase: float
    body_width: float
    body_length: float
    wheel_width: float
    wheel_diameter: float


class _VisualizerState:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.status_text = None
        self.shape = None
        self.yaw = 0.0
        self.filtered_gyro = [0.0, 0.0, 0.0]
        self.filtered_accel = [0.0, 0.0, 0.0]
        self.last_time = None
        self.gyro_alpha = 0.22
        self.accel_alpha = 0.18
        self.gravity = 9.80665
        self.vector_gain = 28.0
        self.window_title = "IMU Visualizer"


_STATE = _VisualizerState()


def _ensure_tk():
    if tk is None:
        raise RuntimeError("tkinter is not available in this Python environment.")


def _clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def _rotate_point(x, y, yaw):
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    return (
        x * cos_yaw - y * sin_yaw,
        x * sin_yaw + y * cos_yaw,
    )


def _world_to_canvas(x, y, scale):
    cx = 420 + x * scale
    cy = 280 - y * scale
    return cx, cy


def _poly_points(points, yaw, scale):
    canvas_points = []
    for x, y in points:
        rx, ry = _rotate_point(x, y, yaw)
        cx, cy = _world_to_canvas(rx, ry, scale)
        canvas_points.extend([cx, cy])
    return canvas_points


def _default_if_zero(value, fallback):
    return fallback if value == 0 else value


def configure(
    track_width,
    wheelbase,
    body_width=0.0,
    body_length=0.0,
    wheel_width=0.0,
    wheel_diameter=0.0,
    title="IMU Visualizer",
    gyro_alpha=0.22,
    accel_alpha=0.18,
):
    _ensure_tk()

    track_width = float(track_width)
    wheelbase = float(wheelbase)
    body_width = float(body_width)
    body_length = float(body_length)
    wheel_width = float(wheel_width)
    wheel_diameter = float(wheel_diameter)

    _STATE.shape = _RobotShape(
        track_width=track_width,
        wheelbase=wheelbase,
        body_width=_default_if_zero(body_width, track_width * 0.82),
        body_length=_default_if_zero(body_length, wheelbase * 1.18),
        wheel_width=_default_if_zero(wheel_width, track_width * 0.16),
        wheel_diameter=_default_if_zero(wheel_diameter, wheelbase * 0.26),
    )
    _STATE.window_title = str(title)
    _STATE.gyro_alpha = _clamp(float(gyro_alpha), 0.01, 1.0)
    _STATE.accel_alpha = _clamp(float(accel_alpha), 0.01, 1.0)
    _open_window()
    _redraw()
    return True


def set_filter(gyro_alpha, accel_alpha):
    _STATE.gyro_alpha = _clamp(float(gyro_alpha), 0.01, 1.0)
    _STATE.accel_alpha = _clamp(float(accel_alpha), 0.01, 1.0)
    return True


def set_vector_gain(vector_gain):
    _STATE.vector_gain = float(vector_gain)
    return True


def reset_pose(yaw=0.0):
    _STATE.yaw = float(yaw)
    _STATE.last_time = None
    _redraw()
    return _STATE.yaw


def update(gyro, accel, dt=0.0, yaw_override=None):
    _open_window()

    gyro_vals = _coerce_vec3(gyro)
    accel_vals = _coerce_vec3(accel)
    dt = _resolve_dt(dt)

    for i in range(3):
        _STATE.filtered_gyro[i] = _low_pass(_STATE.filtered_gyro[i], gyro_vals[i], _STATE.gyro_alpha)
        _STATE.filtered_accel[i] = _low_pass(_STATE.filtered_accel[i], accel_vals[i], _STATE.accel_alpha)

    if yaw_override is None:
        _STATE.yaw += _STATE.filtered_gyro[2] * dt
        _STATE.yaw = math.atan2(math.sin(_STATE.yaw), math.cos(_STATE.yaw))
    else:
        yaw_val = float(yaw_override)
        _STATE.yaw = math.atan2(math.sin(yaw_val), math.cos(yaw_val))

    _redraw()
    return _STATE.yaw


def update_samples(gx, gy, gz, ax, ay, az, dt=0.0, yaw_override=None):
    return update([gx, gy, gz], [ax, ay, az], dt, yaw_override)


def render(gyro, accel, dt=0.0, yaw_override=None):
    return update(gyro, accel, dt, yaw_override)


def render_samples(gx, gy, gz, ax, ay, az, dt=0.0, yaw_override=None):
    return update_samples(gx, gy, gz, ax, ay, az, dt, yaw_override)


def render_pose(gyro, accel, orientation, dt=0.0):
    qx, qy, qz, qw = _coerce_quat(orientation)
    yaw = _quat_to_yaw(qx, qy, qz, qw)
    return update(gyro, accel, dt, yaw)


def get_state():
    return {
        "yaw": _STATE.yaw,
        "gyro": list(_STATE.filtered_gyro),
        "accel": list(_STATE.filtered_accel),
    }


def close():
    if _STATE.root is not None:
        try:
            _STATE.root.destroy()
        except Exception:
            pass
    _STATE.root = None
    _STATE.canvas = None
    _STATE.status_text = None
    return True


def cleanup():
    close()


def _coerce_vec3(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise RuntimeError("Expected a 3-element list or tuple.")
    return [_coerce_num(value[0]), _coerce_num(value[1]), _coerce_num(value[2])]


def _coerce_quat(value):
    if not isinstance(value, (list, tuple)) or len(value) < 4:
        return 0.0, 0.0, 0.0, 1.0

    qx = _coerce_num(value[0])
    qy = _coerce_num(value[1])
    qz = _coerce_num(value[2])
    qw = _coerce_num(value[3], 1.0)

    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if norm <= 1e-9:
        return 0.0, 0.0, 0.0, 1.0
    return qx / norm, qy / norm, qz / norm, qw / norm


def _quat_to_yaw(x, y, z, w):
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def _coerce_num(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_dt(dt):
    dt = float(dt)
    now = time.monotonic()
    if dt > 0.0:
        _STATE.last_time = now
        return dt
    if _STATE.last_time is None:
        _STATE.last_time = now
        return 0.0
    elapsed = now - _STATE.last_time
    _STATE.last_time = now
    return elapsed


def _low_pass(old_value, new_value, alpha):
    return old_value * (1.0 - alpha) + new_value * alpha


def _open_window():
    _ensure_tk()

    if _STATE.root is not None:
        try:
            _STATE.root.update_idletasks()
            _STATE.root.update()
            return
        except Exception:
            _STATE.root = None
            _STATE.canvas = None
            _STATE.status_text = None

    root = tk.Tk()
    root.title(_STATE.window_title)
    root.geometry("840x560")
    root.configure(bg="#0d1015")
    canvas = tk.Canvas(root, width=840, height=560, bg="#0d1015", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    _STATE.root = root
    _STATE.canvas = canvas
    _STATE.status_text = None


def _redraw():
    if _STATE.canvas is None:
        return

    canvas = _STATE.canvas
    canvas.delete("all")
    _draw_background(canvas)
    _draw_robot(canvas)
    _draw_axes(canvas)
    _draw_accel_vector(canvas)
    _draw_status(canvas)

    _STATE.root.update_idletasks()
    _STATE.root.update()


def _draw_background(canvas):
    canvas.create_rectangle(0, 0, 840, 560, fill="#0d1015", outline="")
    for x in range(60, 841, 40):
        canvas.create_line(x, 0, x, 560, fill="#171c24")
    for y in range(40, 561, 40):
        canvas.create_line(0, y, 840, y, fill="#171c24")

    canvas.create_oval(250, 110, 590, 450, outline="#1f2b3a", width=2)
    canvas.create_text(420, 34, text=_STATE.window_title, fill="#f1f5f9", font=("Helvetica", 20, "bold"))


def _robot_scale(shape):
    if shape is None:
        return 120.0
    span = max(shape.body_length, shape.body_width, shape.wheelbase, shape.track_width, 0.25)
    return 240.0 / span


def _draw_robot(canvas):
    shape = _STATE.shape or _RobotShape(
        track_width=0.22,
        wheelbase=0.32,
        body_width=0.18,
        body_length=0.36,
        wheel_width=0.035,
        wheel_diameter=0.08,
    )
    scale = _robot_scale(shape)

    half_body_w = shape.body_width / 2.0
    half_body_l = shape.body_length / 2.0
    body_points = [
        (-half_body_l, -half_body_w),
        (half_body_l * 0.72, -half_body_w),
        (half_body_l, 0.0),
        (half_body_l * 0.72, half_body_w),
        (-half_body_l, half_body_w),
    ]
    canvas.create_polygon(
        _poly_points(body_points, _STATE.yaw, scale),
        fill="#2f6fed",
        outline="#dbeafe",
        width=3,
    )

    wheel_x = shape.wheelbase / 2.0
    wheel_y = shape.track_width / 2.0
    wheel_l = shape.wheel_diameter / 2.0
    wheel_w = shape.wheel_width / 2.0
    wheel_rects = [
        [(wheel_x - wheel_l, wheel_y - wheel_w), (wheel_x + wheel_l, wheel_y - wheel_w), (wheel_x + wheel_l, wheel_y + wheel_w), (wheel_x - wheel_l, wheel_y + wheel_w)],
        [(wheel_x - wheel_l, -wheel_y - wheel_w), (wheel_x + wheel_l, -wheel_y - wheel_w), (wheel_x + wheel_l, -wheel_y + wheel_w), (wheel_x - wheel_l, -wheel_y + wheel_w)],
        [(-wheel_x - wheel_l, wheel_y - wheel_w), (-wheel_x + wheel_l, wheel_y - wheel_w), (-wheel_x + wheel_l, wheel_y + wheel_w), (-wheel_x - wheel_l, wheel_y + wheel_w)],
        [(-wheel_x - wheel_l, -wheel_y - wheel_w), (-wheel_x + wheel_l, -wheel_y - wheel_w), (-wheel_x + wheel_l, -wheel_y + wheel_w), (-wheel_x - wheel_l, -wheel_y + wheel_w)],
    ]
    for wheel in wheel_rects:
        canvas.create_polygon(_poly_points(wheel, _STATE.yaw, scale), fill="#111827", outline="#94a3b8", width=2)

    nose = _poly_points([(half_body_l * 0.96, 0.0), (half_body_l * 0.62, 0.06), (half_body_l * 0.62, -0.06)], _STATE.yaw, scale)
    canvas.create_polygon(nose, fill="#f97316", outline="#fdba74", width=2)


def _draw_axes(canvas):
    center_x, center_y = _world_to_canvas(0.0, 0.0, 1.0)
    canvas.create_line(center_x - 150, center_y, center_x + 150, center_y, fill="#334155", width=2)
    canvas.create_line(center_x, center_y - 150, center_x, center_y + 150, fill="#334155", width=2)
    canvas.create_text(center_x + 160, center_y, text="Body X", fill="#94a3b8", anchor="w", font=("Helvetica", 11, "bold"))
    canvas.create_text(center_x, center_y - 160, text="Body Y", fill="#94a3b8", anchor="s", font=("Helvetica", 11, "bold"))


def _draw_accel_vector(canvas):
    ax, ay, az = _STATE.filtered_accel
    ax = _clamp(ax / _STATE.gravity, -2.0, 2.0)
    ay = _clamp(ay / _STATE.gravity, -2.0, 2.0)

    local_dx = ax * _STATE.vector_gain
    local_dy = ay * _STATE.vector_gain
    world_dx, world_dy = _rotate_point(local_dx, local_dy, _STATE.yaw)

    start_x, start_y = _world_to_canvas(0.0, 0.0, 1.0)
    end_x = start_x + world_dx
    end_y = start_y - world_dy
    canvas.create_line(start_x, start_y, end_x, end_y, fill="#22c55e", width=5, arrow=tk.LAST)
    canvas.create_text(end_x + 10, end_y - 10, text="Accel XY", fill="#86efac", anchor="w", font=("Helvetica", 11, "bold"))

    z_bar = _clamp(az / _STATE.gravity, -2.0, 2.0)
    canvas.create_rectangle(690, 140, 730, 420, outline="#475569", width=2)
    if z_bar >= 0:
        top = 280 - z_bar * 120
        bottom = 280
        fill = "#38bdf8"
    else:
        top = 280
        bottom = 280 - z_bar * 120
        fill = "#f87171"
    canvas.create_rectangle(692, top, 728, bottom, fill=fill, outline="")
    canvas.create_text(710, 120, text="Accel Z", fill="#cbd5e1", font=("Helvetica", 11, "bold"))


def _draw_status(canvas):
    gx, gy, gz = _STATE.filtered_gyro
    ax, ay, az = _STATE.filtered_accel
    yaw_deg = math.degrees(_STATE.yaw)
    status = [
        f"Yaw: {yaw_deg:6.1f} deg",
        f"Gyro LPF: [{gx:6.3f}, {gy:6.3f}, {gz:6.3f}] rad/s",
        f"Accel LPF: [{ax:6.3f}, {ay:6.3f}, {az:6.3f}] m/s^2",
    ]
    if _STATE.shape is not None:
        status.append(
            f"shape: track={_STATE.shape.track_width:.3f} m, wheelbase={_STATE.shape.wheelbase:.3f} m"
        )
    canvas.create_text(
        28,
        470,
        text="\n".join(status),
        fill="#e2e8f0",
        anchor="nw",
        font=("Courier", 12),
    )
