# src/math_funcs.py
import math

# --- Basic Math ---
def sqrt(x):
    return math.sqrt(x)

def abs(x):
    return abs(x)

def ceil(x):
    return math.ceil(x)

def floor(x):
    return math.floor(x)

def round_val(x, ndigits=0):
    return round(x, ndigits)

def exp(x):
    return math.exp(x) # e^x

def ln(x):
    return math.log(x)  # natural logarithm

def log10(x):
    return math.log10(x)

# --- Trigonometry ---
def sin(x):
    return math.sin(x)

def cos(x):
    return math.cos(x)

def tan(x):
    return math.tan(x)

def asin(x):
    return math.asin(x)

def acos(x):
    return math.acos(x)

def atan(x):
    return math.atan(x)

def atan2(y, x):
    return math.atan2(y, x)

# --- Min / Max ---
def min_val(*args):
    return min(args)  # TODO: allow passing an array later

def max_val(*args):
    return max(args)  # TODO: allow passing an array later
