import math as _math
import builtins

# --- Helper: assign mars signature ---
def _sig(params, ret):
    def decorator(fn):
        fn._mars_sig = (ret, params)
        return fn
    return decorator

# --- Basic Math ---
@_sig(params=["float"], ret="float")
def sqrt(x):
    return _math.sqrt(x)

@_sig(params=["float"], ret="float")
def abs(x):  
    return _math.fabs(x)

@_sig(params=["float"], ret="float")
def ceil(x):
    return _math.ceil(x)

@_sig(params=["float"], ret="float")
def floor(x):
    return _math.floor(x)

@_sig(params=["float", "int"], ret="int")
def round(x, ndigits=0):
    return builtins.round(x, ndigits)

@_sig(params=["float"], ret="float")
def exp(x):
    return _math.exp(x)

@_sig(params=["float"], ret="float")
def ln(x):
    return _math.log(x)

@_sig(params=["float"], ret="float")
def log10(x):
    return _math.log10(x)

# --- Trigonometry ---
@_sig(params=["float"], ret="float")
def sin(x):
    return _math.sin(x)

@_sig(params=["float"], ret="float")
def cos(x):
    return _math.cos(x)

@_sig(params=["float"], ret="float")
def tan(x):
    return _math.tan(x)

@_sig(params=["float"], ret="float")
def asin(x):
    return _math.asin(x)

@_sig(params=["float"], ret="float")
def acos(x):
    return _math.acos(x)

@_sig(params=["float"], ret="float")
def atan(x):
    return _math.atan(x)

@_sig(params=["float", "float"], ret="float")
def atan2(y, x):
    return _math.atan2(y, x)

# --- Min / Max ---
@_sig(params=["float", "..."], ret="float")  # variadic
def min_val(*args):
    return min(args)

@_sig(params=["float", "..."], ret="float")  # variadic
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
    'E': E
}
