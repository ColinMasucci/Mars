import math
import re
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class UnitSpec:
    dims: Tuple[Tuple[str, int], ...]  # sorted tuple of (dimension, exponent)
    scale: float
    offset: float
    expr: str
    affine: bool


def _dims_tuple(dims: Dict[str, int]) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted((k, v) for k, v in dims.items() if v != 0))


UNIT_TABLE: Dict[str, Tuple[Dict[str, int], float, float, bool]] = {
    # Length
    "m":   ({"L": 1}, 1.0, 0.0, False),
    "km":  ({"L": 1}, 1000.0, 0.0, False),
    "cm":  ({"L": 1}, 0.01, 0.0, False),
    "mm":  ({"L": 1}, 0.001, 0.0, False),
    "um":  ({"L": 1}, 1e-6, 0.0, False),
    "nm":  ({"L": 1}, 1e-9, 0.0, False),
    "pm":  ({"L": 1}, 1e-12, 0.0, False),
    "in":  ({"L": 1}, 0.0254, 0.0, False),
    "ft":  ({"L": 1}, 0.3048, 0.0, False),
    "yd":  ({"L": 1}, 0.9144, 0.0, False),
    "mi":  ({"L": 1}, 1609.344, 0.0, False),

    # Time
    "s":   ({"T": 1}, 1.0, 0.0, False),
    "ms":  ({"T": 1}, 1e-3, 0.0, False),
    "us":  ({"T": 1}, 1e-6, 0.0, False),
    "ns":  ({"T": 1}, 1e-9, 0.0, False),
    "ps":  ({"T": 1}, 1e-12, 0.0, False),
    "min": ({"T": 1}, 60.0, 0.0, False),
    "hr":  ({"T": 1}, 3600.0, 0.0, False),
    "day": ({"T": 1}, 86400.0, 0.0, False),
    "wk":  ({"T": 1}, 604800.0, 0.0, False),
    "yr365":  ({"T": 1}, 31536000.0, 0.0, False),   # common year (365 days)
    "yr":   ({"T": 1}, 31557600.0, 0.0, False),   # Julian year (365.25 days)

    # Mass
    "kg":  ({"M": 1}, 1.0, 0.0, False),
    "g":   ({"M": 1}, 1e-3, 0.0, False),
    "mg":  ({"M": 1}, 1e-6, 0.0, False),
    "ug":  ({"M": 1}, 1e-9, 0.0, False),
    "t":   ({"M": 1}, 1000.0, 0.0, False),
    "lb":  ({"M": 1}, 0.45359237, 0.0, False),
    "oz":  ({"M": 1}, 0.028349523125, 0.0, False),

    # Electric current
    "A":   ({"I": 1}, 1.0, 0.0, False),
    "mA":  ({"I": 1}, 1e-3, 0.0, False),
    "kA":  ({"I": 1}, 1000.0, 0.0, False),

    # Angle
    "rad": ({"A": 1}, 1.0, 0.0, False),
    "deg": ({"A": 1}, math.pi / 180.0, 0.0, False),
    "arcmin": ({"A": 1}, math.pi / 10800.0, 0.0, False),
    "arcsec": ({"A": 1}, math.pi / 648000.0, 0.0, False),
    "rev": ({"A": 1}, 2.0 * math.pi, 0.0, False),

    # Temperature (absolute, affine)
    "K":   ({"Temp": 1}, 1.0, 0.0, True),
    "C":   ({"Temp": 1}, 1.0, 273.15, True),
    "F":   ({"Temp": 1}, 5.0/9.0, 255.3722222222222, True),

    # Temperature deltas (non-affine)
    "dK":  ({"Temp": 1}, 1.0, 0.0, False),
    "dC":  ({"Temp": 1}, 1.0, 0.0, False),
    "dF":  ({"Temp": 1}, 5.0/9.0, 0.0, False),

    # Derived: kinematics
    "m/s":   ({"L": 1, "T": -1}, 1.0, 0.0, False),
    "m/s^2": ({"L": 1, "T": -2}, 1.0, 0.0, False),
    "rad/s": ({"A": 1, "T": -1}, 1.0, 0.0, False),
    "rad/s^2": ({"A": 1, "T": -2}, 1.0, 0.0, False),
    "deg/s": ({"A": 1, "T": -1}, math.pi / 180.0, 0.0, False),
    "deg/s^2": ({"A": 1, "T": -2}, math.pi / 180.0, 0.0, False),
    "rpm":   ({"A": 1, "T": -1}, 2.0 * math.pi / 60.0, 0.0, False),
    "g0":    ({"L": 1, "T": -2}, 9.80665, 0.0, False),
    "gn":    ({"L": 1, "T": -2}, 9.80665, 0.0, False),

    # Derived: force & torque
    "N":     ({"M": 1, "L": 1, "T": -2}, 1.0, 0.0, False),
    "kN":    ({"M": 1, "L": 1, "T": -2}, 1000.0, 0.0, False),
    "N*m":   ({"M": 1, "L": 2, "T": -2}, 1.0, 0.0, False),

    # Derived: pressure
    "Pa":    ({"M": 1, "L": -1, "T": -2}, 1.0, 0.0, False),
    "kPa":   ({"M": 1, "L": -1, "T": -2}, 1000.0, 0.0, False),
    "MPa":   ({"M": 1, "L": -1, "T": -2}, 1_000_000.0, 0.0, False),
    "GPa":   ({"M": 1, "L": -1, "T": -2}, 1_000_000_000.0, 0.0, False),
    "bar":   ({"M": 1, "L": -1, "T": -2}, 100000.0, 0.0, False),
    "atm":   ({"M": 1, "L": -1, "T": -2}, 101325.0, 0.0, False),
    "psi":   ({"M": 1, "L": -1, "T": -2}, 6894.757293168, 0.0, False),

    # Derived: energy
    "J":     ({"M": 1, "L": 2, "T": -2}, 1.0, 0.0, False),
    # torque shares dimensions with energy; use N*m explicitly if you want that display
    "kJ":    ({"M": 1, "L": 2, "T": -2}, 1000.0, 0.0, False),
    "MJ":    ({"M": 1, "L": 2, "T": -2}, 1_000_000.0, 0.0, False),
    "Wh":    ({"M": 1, "L": 2, "T": -2}, 3600.0, 0.0, False),
    "kWh":   ({"M": 1, "L": 2, "T": -2}, 3_600_000.0, 0.0, False),

    # Derived: power
    "W":     ({"M": 1, "L": 2, "T": -3}, 1.0, 0.0, False),
    "kW":    ({"M": 1, "L": 2, "T": -3}, 1000.0, 0.0, False),
    "MW":    ({"M": 1, "L": 2, "T": -3}, 1_000_000.0, 0.0, False),

    # Derived: volume
    "m^3":   ({"L": 3}, 1.0, 0.0, False),
    "L":     ({"L": 3}, 0.001, 0.0, False),
    "mL":    ({"L": 3}, 1e-6, 0.0, False),
    "cm^3":  ({"L": 3}, 1e-6, 0.0, False),

    # Derived: electrical
    "Coul":  ({"I": 1, "T": 1}, 1.0, 0.0, False),
    "Ah":    ({"I": 1, "T": 1}, 3600.0, 0.0, False),
    "mAh":   ({"I": 1, "T": 1}, 3.6, 0.0, False),
    "V":     ({"M": 1, "L": 2, "T": -3, "I": -1}, 1.0, 0.0, False),
    "ohm":   ({"M": 1, "L": 2, "T": -3, "I": -2}, 1.0, 0.0, False),
    "S":     ({"M": -1, "L": -2, "T": 3, "I": 2}, 1.0, 0.0, False),
    "Fd":    ({"M": -1, "L": -2, "T": 4, "I": 2}, 1.0, 0.0, False),
    "H":     ({"M": 1, "L": 2, "T": -2, "I": -2}, 1.0, 0.0, False),
    "Wb":    ({"M": 1, "L": 2, "T": -2, "I": -1}, 1.0, 0.0, False),
    "T":     ({"M": 1, "T": -2, "I": -1}, 1.0, 0.0, False),

    # Derived: frequency
    "Hz":    ({"T": -1}, 1.0, 0.0, False),
    "kHz":   ({"T": -1}, 1000.0, 0.0, False),

    # Derived: photometric
    "lm":    ({"Cd": 1}, 1.0, 0.0, False),
    "lx":    ({"Cd": 1, "L": -2}, 1.0, 0.0, False),
}


def canonical_name(dims: Tuple[Tuple[str, int], ...], scale: float, offset: float, affine: bool) -> str | None:
    for name, (udims, uscale, uoffset, uaffine) in UNIT_TABLE.items():
        if _dims_tuple(udims) == dims and uaffine == affine and \
            math.isclose(uscale, scale, rel_tol=1e-12, abs_tol=1e-12) and \
            math.isclose(uoffset, offset, rel_tol=1e-12, abs_tol=1e-12):
            return name
    return None


_UNIT_TOKENS = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\*|/|\^")


def parse_unit_expr(expr: str) -> UnitSpec:
    tokens = _UNIT_TOKENS.findall(expr)
    if not tokens:
        raise ValueError("Empty unit expression")

    idx = 0
    dims: Dict[str, int] = {}
    scale = 1.0
    offset = 0.0
    affine = False
    saw_any = False

    def apply_unit(unit_name: str, power: int, sign: int):
        nonlocal scale, offset, affine, saw_any
        if unit_name not in UNIT_TABLE:
            raise ValueError(f"Unknown unit '{unit_name}'")
        unit_dims, unit_scale, unit_offset, unit_affine = UNIT_TABLE[unit_name]
        if affine:
            raise ValueError("Affine temperature units cannot be combined or exponentiated")
        if unit_affine:
            if saw_any or power != 1 or sign != 1:
                raise ValueError("Affine temperature units cannot be combined or exponentiated")
            affine = True
            offset = unit_offset
        exp = power * sign
        for dim, val in unit_dims.items():
            dims[dim] = dims.get(dim, 0) + val * exp
        scale *= unit_scale ** exp
        saw_any = True

    def parse_unit_atom(sign: int):
        nonlocal idx
        if idx >= len(tokens):
            raise ValueError("Expected unit identifier")
        name = tokens[idx]
        if not re.match(r"[A-Za-z_]", name):
            raise ValueError("Expected unit identifier")
        idx += 1
        power = 1
        if idx < len(tokens) and tokens[idx] == "^":
            idx += 1
            if idx >= len(tokens) or not tokens[idx].isdigit():
                raise ValueError("Unit exponent must be an integer")
            power = int(tokens[idx])
            idx += 1
        apply_unit(name, power, sign)

    # first atom
    parse_unit_atom(sign=1)
    while idx < len(tokens):
        op = tokens[idx]
        if op not in ("*", "/"):
            raise ValueError(f"Unexpected token '{op}' in unit expression")
        idx += 1
        parse_unit_atom(sign=1 if op == "*" else -1)

    dims_tuple = _dims_tuple(dims)
    canonical = canonical_name(dims_tuple, scale, offset, affine)
    expr_key = "".join(tokens)
    if expr_key in UNIT_TABLE:
        display = expr_key
    elif canonical is not None:
        display = canonical
    else:
        display = expr_key
    return UnitSpec(dims=dims_tuple, scale=scale, offset=offset, expr=display, affine=affine)
