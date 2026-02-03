import math
import re
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class UnitSpec:
    dims: Tuple[Tuple[str, int], ...]  # sorted tuple of (dimension, exponent)
    scale: float
    expr: str


def _dims_tuple(dims: Dict[str, int]) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted((k, v) for k, v in dims.items() if v != 0))


UNIT_TABLE: Dict[str, Tuple[Dict[str, int], float]] = {
    # Length
    "m":   ({"L": 1}, 1.0),
    "cm":  ({"L": 1}, 0.01),
    "mm":  ({"L": 1}, 0.001),
    "km":  ({"L": 1}, 1000.0),
    "in":  ({"L": 1}, 0.0254),
    "ft":  ({"L": 1}, 0.3048),
    "yd":  ({"L": 1}, 0.9144),
    "mi":  ({"L": 1}, 1609.344),

    # Time
    "s":   ({"T": 1}, 1.0),
    "ms":  ({"T": 1}, 0.001),
    "min": ({"T": 1}, 60.0),
    "hr":  ({"T": 1}, 3600.0),

    # Mass
    "kg":  ({"M": 1}, 1.0),
    "g":   ({"M": 1}, 0.001),
    "lb":  ({"M": 1}, 0.45359237),

    # Angle
    "rad": ({"A": 1}, 1.0),
    "deg": ({"A": 1}, math.pi / 180.0),

    # Derived (canonical)
    "N":   ({"M": 1, "L": 1, "T": -2}, 1.0),
    "Pa":  ({"M": 1, "L": -1, "T": -2}, 1.0),
    "J":   ({"M": 1, "L": 2, "T": -2}, 1.0),
    "W":   ({"M": 1, "L": 2, "T": -3}, 1.0),
    "Hz":  ({"T": -1}, 1.0),
    "m/s": ({"L": 1, "T": -1}, 1.0),
}


def canonical_name(dims: Tuple[Tuple[str, int], ...], scale: float) -> str | None:
    for name, (udims, uscale) in UNIT_TABLE.items():
        if _dims_tuple(udims) == dims and math.isclose(uscale, scale, rel_tol=1e-12, abs_tol=1e-12):
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

    def apply_unit(unit_name: str, power: int, sign: int):
        nonlocal scale
        if unit_name not in UNIT_TABLE:
            raise ValueError(f"Unknown unit '{unit_name}'")
        unit_dims, unit_scale = UNIT_TABLE[unit_name]
        exp = power * sign
        for dim, val in unit_dims.items():
            dims[dim] = dims.get(dim, 0) + val * exp
        scale *= unit_scale ** exp

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
    canonical = canonical_name(dims_tuple, scale)
    display = canonical if canonical is not None else "".join(tokens)
    return UnitSpec(dims=dims_tuple, scale=scale, expr=display)

