from dataclasses import dataclass

@dataclass #For simple testing floats and ints were both Number literals
class NumberLiteral:
    value: float

@dataclass
class StringLiteral:
    value: str

@dataclass
class BinaryOp:
    op: str
    left: any
    right: any
