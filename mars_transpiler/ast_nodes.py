from dataclasses import dataclass
from typing import List, Any #Signals to type checker that it can be any value.

@dataclass #For simple testing floats and ints were both Number literals
class NumberLiteral:
    value: float

@dataclass
class StringLiteral:
    value: str

@dataclass
class BinaryOp: # (Ex. PLUS, MUL, DIV, MINUS)
    op: str
    left: Any
    right: Any

#used for referencing variables (grabbing their value)
@dataclass
class Var:
    name: str

# used for assigning variables
@dataclass
class Assign:
    name: str
    value: Any

#Uses for printing values to the console/stdout
@dataclass
class Call:
    func: Any      
    args: List[Any] 

#The root node of a program, containing a list of statements. 
# (We havent added in all of our AST stuff yet however I think this is the "expression" part the we previously defined????)
@dataclass
class Program:
    statements: List[Any]