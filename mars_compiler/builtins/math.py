import math as _math
import builtins

# --- Basic Math ---
def sqrt(x):
    return _math.sqrt(x)

def abs(x):  
    return _math.fabs(x)

def ceil(x):
    return _math.ceil(x)

def floor(x):
    return _math.floor(x)

def round(x, ndigits=0):
    return builtins.round(x, ndigits)

def exp(x):
    return _math.exp(x)

def ln(x):
    return _math.log(x)

def log10(x):
    return _math.log10(x)

# --- Trigonometry ---
def sin(x):
    return _math.sin(x)

def cos(x):
    return _math.cos(x)

def tan(x):
    return _math.tan(x)

def asin(x):
    return _math.asin(x)

def acos(x):
    return _math.acos(x)

def atan(x):
    return _math.atan(x)

def atan2(y, x):
    return _math.atan2(y, x)

# --- Min / Max ---
def min_val(*args):
    return min(args)

def max_val(*args):
    return max(args)

# --- Constants ---
PI = _math.pi
E = _math.e


# expose mapping for the VM
MATH_FUNCS = {
    # Basic Math
    'sqrt': sqrt,
    'abs': abs,
    'ceil': ceil,
    'floor': floor,
    'round': round,
    'exp': exp,
    'ln': ln,
    'log10': log10,

    # Trig
    'sin': sin,
    'cos': cos,
    'tan': tan,
    'asin': asin,
    'acos': acos,
    'atan': atan,
    'atan2': atan2,

    # Min/Max
    'min_val': min_val,
    'max_val': max_val,

    # Constants
    'PI': PI,
    'E': E,
}
